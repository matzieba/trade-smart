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

from trade_smart.celery import app
from trade_smart.models.market_data import MarketData

logger = logging.getLogger(__name__)

###############################################################################
# Configuration – override in settings.py if required
###############################################################################

DEFAULT_LOOKBACK_DAYS: int = getattr(settings, "MARKET_LOOKBACK_DAYS", 10)
TICKERS: List[str] = getattr(settings, "MARKET_TICKERS", ["AAPL", "MSFT", "TSLA"])

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
    """
    Convert a MultiIndex OHLCV DataFrame into MarketData Django objects.
    """
    objects: List[MarketData] = []

    for ts, row in df.iterrows():
        try:
            objects.append(
                MarketData(
                    ticker=ticker,
                    date=ts.date(),
                    open=row["Open"][ticker],
                    high=row["High"][ticker],
                    low=row["Low"][ticker],
                    close=row["Close"][ticker],
                    volume=row["Volume"][ticker],
                )
            )
        except KeyError as exc:  # malformed data row
            logger.warning(
                "Malformed row for %s on %s: %s",
                ticker,
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
    for symbol in TICKERS:
        fetch_daily_ohlcv.delay(symbol)


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
