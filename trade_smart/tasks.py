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

from trade_smart.agent_service.runner import run_for_portfolio
from trade_smart.analytics.ta_engine import calculate_indicators
from trade_smart.celery import app
from trade_smart.models import Portfolio, Position
from trade_smart.models.analytics import TechnicalIndicator
from trade_smart.models.market_data import MarketData

logger = logging.getLogger(__name__)

###############################################################################
# Configuration – override in settings.py if required
###############################################################################

DEFAULT_LOOKBACK_DAYS: int = getattr(settings, "MARKET_LOOKBACK_DAYS", 365)
###############################################################################
# Helpers (single-responsibility functions)
###############################################################################


def _download_ohlcv(ticker: str, *, days: int = DEFAULT_LOOKBACK_DAYS) -> pd.DataFrame:
    """
    Download the last *days* of adjusted OHLCV data for *ticker* and
    guarantee a MultiIndex column layout (Open/High/… , <TICKER>).
    """
    end = date.today()
    start = end - timedelta(days=days)

    df = yf.download(
        ticker,
        start=start.isoformat(),
        end=end.isoformat(),
        progress=False,
        auto_adjust=True,
    )

    if df.empty:
        logger.info("No market data returned for ticker=%s", ticker)
        return df

    # Force a unified MultiIndex regardless of number of tickers requested
    if not isinstance(df.columns, pd.MultiIndex):
        df.columns = pd.MultiIndex.from_product([df.columns, [ticker]])

    return df


def _df_to_objects(df: pd.DataFrame, ticker: str) -> List[MarketData]:

    objects: List[MarketData] = []
    logger.debug("DataFrame columns for %s: %s", ticker, df.columns)
    col_tickers = df.columns.get_level_values(1).unique()
    if ticker not in col_tickers:
        actual_ticker = col_tickers[0] if len(col_tickers) == 1 else None
        logger.warning(
            "Expected ticker '%s' not in DataFrame columns: %s", ticker, col_tickers
        )
    else:
        actual_ticker = ticker

    if not actual_ticker:
        logger.error(
            "Frame columns do not contain expected ticker, skipping all rows for %s",
            ticker,
        )
        return []

    for ts, row in df.iterrows():
        try:
            objects.append(
                MarketData(
                    ticker=actual_ticker,
                    date=ts.date(),
                    open=row["Open"][actual_ticker],
                    high=row["High"][actual_ticker],
                    low=row["Low"][actual_ticker],
                    close=row["Close"][actual_ticker],
                    volume=row["Volume"][actual_ticker],
                )
            )
        except (KeyError, IndexError, TypeError) as exc:  # malformed data row
            logger.warning(
                "Malformed row for %s on %s: %s",
                actual_ticker,
                ts,
                exc,
                exc_info=True,
            )

    return objects


###############################################################################
# Celery tasks
###############################################################################


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def fetch_daily_ohlcv(self, ticker: str) -> str:
    """
    Celery task: download OHLCV data for *ticker* and upsert into DB.
    """
    try:
        df = _download_ohlcv(ticker)
        if df.empty:
            return f"No data for {ticker}"

        objects = _df_to_objects(df, ticker)
        if not objects:
            return f"No valid rows for {ticker}"

        # Atomic upsert (Django ≥4.1)
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

    except (IntegrityError, ValueError) as exc:
        # Data problems – do not retry
        logger.error("Data error for %s: %s", ticker, exc, exc_info=True)
        raise
    except Exception as exc:  # noqa: BLE001
        # Network / API problems – retry
        logger.warning("Error fetching data for %s: %s", ticker, exc, exc_info=True)
        raise self.retry(exc=exc)


@shared_task
def fetch_all_tickers() -> None:
    """
    Enqueue a download task for every configured ticker.
    """
    tickers = [position.ticker for position in Position.objects.all()]
    for symbol in tickers:
        fetch_daily_ohlcv.delay(symbol)


@shared_task(bind=True, max_retries=2, default_retry_delay=120)
def compute_indicators(self, ticker: str):
    try:
        objects = calculate_indicators(ticker)
        if not objects:
            return f"No indicator points for {ticker}"

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
    run_for_portfolio(pf)


@shared_task
def nightly_all_portfolios():
    for pf_id in Portfolio.objects.values_list("id", flat=True):
        issue_portfolio_advice.delay(pf_id)


# @shared_task
# def ingest_news_all():
#     for tkr in TICKERS:
#         ingest_news_ticker.delay(tkr)
#
#
# @shared_task
# def ingest_news_ticker(ticker: str):
#     cnt = ingest_for_ticker(ticker)
#     logger.info("Ingested %s news docs for %s", cnt, ticker)


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
