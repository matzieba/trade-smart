# wisetrade/services/market_data.py
#
# Usage:
#   fetcher = MarketDataFetcher()
#   df      = fetcher.get_ohlcv("AAPL", start="2024-01-01", end="2024-03-31")
#   # df is a pandas.DataFrame[date, open, high, low, close, volume]

from __future__ import annotations

import datetime as dt
import logging
import os
import time
from typing import Literal

import pandas as pd
import requests
import yfinance as yf
from django.conf import settings


log = logging.getLogger(__name__)

ALPHAVANTAGE_KEY = getattr(settings, "ALPHAVANTAGE_KEY", os.getenv("ALPHAVANTAGE_KEY"))
FMP_KEY = getattr(settings, "FMP_KEY", os.getenv("FMP_KEY"))
AlphaFunc = Literal["TIME_SERIES_DAILY_ADJUSTED", "TIME_SERIES_INTRADAY"]
CFD_ALIASES: dict[str, dict[str, str]] = {
    "US100": {"yf": "NQ=F", "av": "NDX", "fmp": "NDX"},
    "US500": {"yf": "ES=F", "av": "SPX", "fmp": "SPX"},
    "US30": {"yf": "YM=F", "av": "DJI", "fmp": "DJI"},
    "DE40": {"yf": "FDAX.DE", "av": "GDAXI", "fmp": "GDAXI"},
}
CFD_ALIASES.update(
    {
        "VVSM.HA": {"yf": "VVSM.DE"},
        "ETFBCASH.WA": {"yf": "ETFBCASH.WA"},
    }
)


class UpstreamError(RuntimeError):
    """Raised when *all* upstream APIs fail."""


class MarketDataFetcher:
    """Unified façade around several free market-data providers."""

    # --------------------------------------------------------------------- #
    # Public
    # --------------------------------------------------------------------- #
    def get_ohlcv(
        self,
        symbol: str,
        start: str | dt.date | None = None,
        end: str | dt.date | None = None,
        interval: Literal["1d", "1h", "30m", "15m"] = "1d",
        max_retries: int = 2,
    ) -> pd.DataFrame:
        """
        Returns OHLCV as a pandas DataFrame indexed by UTC date/datetime.
        Raises UpstreamError if every provider fails.
        """
        # 1) yfinance ------------------------------------------------------ #
        try:
            df = self._from_yf(symbol, start, end, interval)
            if not df.empty:
                return df
            log.warning("yfinance returned empty dataframe for %s", symbol)
        except Exception as exc:
            log.warning("yfinance failed for %s: %s", symbol, exc)

        # 2) Alpha Vantage -------------------------------------------------- #
        try:
            df = self._from_alphavantage(
                symbol, interval=interval, max_retries=max_retries
            )
            if not df.empty:
                return df
            log.warning("Alpha Vantage returned empty dataframe for %s", symbol)
        except Exception as exc:
            log.warning("Alpha Vantage failed for %s: %s", symbol, exc)

        # 3) FinancialModelingPrep ----------------------------------------- #
        try:
            df = self._from_fmp(symbol, start, end)
            if not df.empty:
                return df
            log.warning("FMP returned empty dataframe for %s", symbol)
        except Exception as exc:
            log.warning("FMP failed for %s: %s", symbol, exc)

        raise UpstreamError(f"Could not fetch OHLCV for {symbol} from any provider.")

    def _alias(self, symbol: str, provider: str) -> str:
        """
        Return the provider-specific symbol.
        If no alias exists we simply return the original ticker.
        """
        base = symbol.upper()
        if base in CFD_ALIASES and provider in CFD_ALIASES[base]:
            return CFD_ALIASES[base][provider]

        # Previous generic index aliases (still useful)
        GENERIC = {
            "^": "" if provider == "av" else "^",
        }
        if base.startswith("^") and provider == "av":
            return base.lstrip("^")
        return base

    # --------------------------------------------------------------------- #
    # Providers
    # --------------------------------------------------------------------- #
    def _from_yf(
        self,
        symbol: str,
        start: str | dt.date | None,
        end: str | dt.date | None,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """
        yfinance needs no key and is usually the quickest.
        """
        start = _parse_date(start)
        end = _parse_date(end)
        symbol = self._alias(symbol, provider="yf")
        yf_ticker = yf.Ticker(symbol)
        df = yf_ticker.history(
            start=start, end=end, interval=interval, auto_adjust=False
        )

        # yfinance always returns columns in title-case, rename to lower.
        df.rename(
            columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            },
            inplace=True,
        )

        return df.astype(float)

    def _from_alphavantage(
        self,
        symbol: str,
        *,
        interval: str = "1d",
        max_retries: int = 2,
    ) -> pd.DataFrame:
        if not ALPHAVANTAGE_KEY:
            raise RuntimeError("ALPHAVANTAGE_KEY not configured")
        symbol = self._alias(symbol, provider="av")

        # Map WiseTrade interval → Alpha Vantage parameters.
        if interval == "1d":
            function: AlphaFunc = "TIME_SERIES_DAILY_ADJUSTED"
            url = (
                "https://www.alphavantage.co/query?"
                f"function={function}&symbol={symbol}&outputsize=compact&apikey={ALPHAVANTAGE_KEY}"
            )
        else:  # intraday
            function = "TIME_SERIES_INTRADAY"
            url = (
                "https://www.alphavantage.co/query?"
                f"function={function}&symbol={symbol}&interval={interval}&outputsize=compact"
                f"&apikey={ALPHAVANTAGE_KEY}"
            )

        for attempt in range(max_retries + 1):
            resp = requests.get(url, timeout=15)
            payload = resp.json()

            # Alpha Vantage returns {"Note": "... throttled ..."} when rate limited.
            if "Note" in payload:
                if attempt >= max_retries:
                    raise RuntimeError(f"Alpha Vantage rate-limit: {payload['Note']}")
                sleep_for = 12  # seconds
                log.info("Alpha Vantage throttled, sleeping %.0fs", sleep_for)
                time.sleep(sleep_for)
                continue  # retry

            if "Error Message" in payload:
                raise RuntimeError(payload["Error Message"])

            key = next(k for k in payload if k.startswith("Time Series"))
            raw = payload[key]

            df = (
                pd.DataFrame(raw)
                .T.rename(columns=lambda c: c.split(". ")[1])
                .rename(columns=_alpha_column_map)
                .astype(float)
                .sort_index()
            )
            return df

        # Fallback should already have happened; but keep mypy happy.
        return pd.DataFrame()

    def _from_fmp(
        self,
        symbol: str,
        start: str | dt.date | None,
        end: str | dt.date | None,
    ) -> pd.DataFrame:
        if not FMP_KEY:
            raise RuntimeError("FMP_KEY not configured")
        symbol = self._alias(symbol, provider="fmp")

        url = (
            "https://financialmodelingprep.com/api/v3/historical-price-full/"
            f"{symbol}?from={_date_str(start)}&to={_date_str(end)}&apikey={FMP_KEY}"
        )
        resp = requests.get(url, timeout=15)
        payload = resp.json()

        if "historical" not in payload or not payload["historical"]:
            return pd.DataFrame()

        df = (
            pd.DataFrame(payload["historical"])
            .rename(
                columns={
                    "date": "date",
                    "open": "open",
                    "high": "high",
                    "low": "low",
                    "close": "close",
                    "volume": "volume",
                }
            )
            .set_index("date")
            .sort_index()
        )
        return df.astype(float)


# ------------------------------------------------------------------------- #
# Helpers
# ------------------------------------------------------------------------- #
_alpha_column_map = {
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "adjusted close": "close",  # keep naming consistent
    "volume": "volume",
}


def _parse_date(d: str | dt.date | None) -> str | None:
    if d is None:
        return None
    if isinstance(d, dt.date):
        return d.strftime("%Y-%m-%d")
    return d  # already str


def _date_str(d: str | dt.date | None) -> str:
    return _parse_date(d) or ""
