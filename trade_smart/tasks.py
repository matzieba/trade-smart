from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import List

import pandas as pd
import yfinance as yf
from celery import shared_task
from celery.schedules import crontab
from django.conf import settings
from django.db import IntegrityError, transaction
import datetime as dt

from trade_smart.agent_service.nodes.news_macro_node import web_news_node
from trade_smart.agent_service.runner import run_for_portfolio
from trade_smart.analytics.ta_engine import calculate_indicators
from trade_smart.celery import app
from trade_smart.models import Portfolio, Position
from trade_smart.models.analytics import TechnicalIndicator
from trade_smart.models.market_data import MarketData

from trade_smart.services.email_service import EmailNotificationService
from trade_smart.services.market_data import MarketDataFetcher, UpstreamError

logger = logging.getLogger(__name__)

###############################################################################
# Configuration – override in settings.py if required
###############################################################################

DEFAULT_LOOKBACK_DAYS: int = getattr(settings, "MARKET_LOOKBACK_DAYS", 365)
###############################################################################
# Helpers (single-responsibility functions)
###############################################################################


###############################################################################
# Celery tasks
###############################################################################

_fetcher = MarketDataFetcher()


def _download_ohlcv(
    ticker: str,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> pd.DataFrame:
    """
    Wrapper around MarketDataFetcher that calculates start/end dates.
    Returns a *normalised* pandas DataFrame with columns:
    [open, high, low, close, volume] and index = date (UTC).
    """
    end = dt.date.today()
    start = end - dt.timedelta(days=lookback_days)
    return _fetcher.get_ohlcv(ticker, start=start, end=end, interval="1d")


def _df_to_objects(df: pd.DataFrame, ticker: str) -> list[MarketData]:
    """
    Convert a DataFrame row-by-row into Django ORM objects.
    Works no matter whether the original index was named Date, date or None.
    """
    # 1) Move index -> column called 'date'
    df = df.copy()
    df.index.name = "date"  # guarantees a name
    df.reset_index(inplace=True)

    # 2) Lower-case every column so we can safely do row.xxx
    df.columns = [c.lower() for c in df.columns]

    # 3) Build ORM instances
    return [
        MarketData(
            ticker=ticker.upper(),
            date=pd.to_datetime(row.date).date(),  # cast to python date
            open=row.open,
            high=row.high,
            low=row.low,
            close=row.close,
            volume=int(row.volume),
        )
        for row in df.itertuples(index=False)
    ]


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def fetch_daily_ohlcv(self, ticker: str) -> str:
    """
    Celery task: download OHLCV data for *ticker* and upsert into DB.
    Falls back yfinance ➜ Alpha Vantage ➜ FMP automatically.
    """
    try:
        df = _download_ohlcv(ticker)
        if df.empty:
            return f"No data for {ticker}"

        objects = _df_to_objects(df, ticker)
        if not objects:
            return f"No valid rows for {ticker}"

        with transaction.atomic():
            MarketData.objects.bulk_create(
                objects,
                update_conflicts=True,
                update_fields=["open", "high", "low", "close", "volume"],
                unique_fields=["ticker", "date"],
            )

        msg = f"Stored {len(objects)} OHLCV rows for {ticker}"
        logger.info(msg)
        return msg

    # ------------------------------------------------------------------ #
    # Error handling & retry strategy
    # ------------------------------------------------------------------ #
    except UpstreamError as exc:
        # All providers exhausted → retry later
        logger.warning("Upstream error for %s: %s", ticker, exc)
        raise

    except (IntegrityError, ValueError) as exc:
        # Data integrity problems – do NOT retry
        logger.error("Data error for %s: %s", ticker, exc, exc_info=True)
        raise

    except Exception as exc:  # noqa: BLE001
        # Network hiccup, JSON decode, etc. – safe to retry
        logger.warning("Error fetching data for %s: %s", ticker, exc, exc_info=True)
        raise


@shared_task(bind=True, max_retries=2, default_retry_delay=120)
def fetch_all_tickers(self) -> None:
    """
    Enqueue a download task for every distinct ticker that exists
    in the user's portfolios.
    """
    tickers = Position.objects.values_list("ticker", flat=True).distinct()
    for symbol in tickers:
        fetch_daily_ohlcv.delay(symbol)


@shared_task(bind=True, max_retries=2, default_retry_delay=120)
def compute_indicators(self, ticker: str):
    try:
        dataclasses = calculate_indicators(ticker)
        if not dataclasses:
            return f"No indicator points for {ticker}"

        objects = [
            TechnicalIndicator(
                ticker=dc.ticker,
                date=dc.date,
                name=dc.name,
                value=dc.value,
            )
            for dc in dataclasses
        ]

        with transaction.atomic():
            TechnicalIndicator.objects.bulk_create(
                objects,
                update_conflicts=True,
                update_fields=["value"],
                unique_fields=["ticker", "date", "name"],
            )
        return f"{len(objects)} indicator rows stored for {ticker}"
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task
def compute_all_indicators():
    for sym in [position.ticker for position in Position.objects.all()]:
        compute_indicators.delay(sym)


@shared_task
def issue_portfolio_advice(portfolio_id: int):
    pf = Portfolio.objects.get(id=portfolio_id)
    all_evaluated = run_for_portfolio(pf)
    if all_evaluated:
        EmailNotificationService().send_advice_email(pf)
        logger.info(f"Successfully sent advice email for portfolio {portfolio_id}")
    else:
        logger.warning(
            f"Failed to send advice email for portfolio {portfolio_id} because not all positions were evaluated."
        )


@shared_task
def nightly_all_portfolios():
    for pf_id in Portfolio.objects.values_list("id", flat=True):
        issue_portfolio_advice.delay(pf_id)


@shared_task
def fetch_news_for_all_positions():
    unique_tickers = set()
    for portfolio in Portfolio.objects.all():
        for position in portfolio.positions.all():
            unique_tickers.add(position.ticker)

    for ticker in unique_tickers:
        logger.info(f"Fetching news for ticker: {ticker}")
        web_news_node({"ticker": ticker})


###############################################################################
# Periodic job registration
###############################################################################


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """
    Register the periodic task with Celery Beat when the worker starts.
    """
    sender.add_periodic_task(
        crontab(minute="*/15"),  # every 15 minutes
        fetch_all_tickers.s(),
        name="Fetch OHLCV for tracked tickers",
    )
    sender.add_periodic_task(
        crontab(minute=0, hour=2),
        compute_all_indicators.s(),
        name="Compute daily technical indicators",
    )
    sender.add_periodic_task(
        crontab(minute=30, hour=2),
        nightly_all_portfolios.s(),
        name="Nightly advice generation",
    )
