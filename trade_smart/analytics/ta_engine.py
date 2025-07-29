"""
ta_engine – compute technical indicators

Public function:
    calculate_indicators(ticker: str) -> list[TechnicalIndicator]

Nothing else in the code-base has to change; tech_node already imports
and uses this symbol.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import List

import pandas as pd
import pandas_ta as ta

from trade_smart.helpers.helpers import _to_records
from trade_smart.models.market_data import MarketData

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Return type
# ------------------------------------------------------------------ #
@dataclass
class TechnicalIndicator:
    ticker: str
    name: str
    date: pd.Timestamp
    value: float


# ------------------------------------------------------------------ #
# Internal helpers
# ------------------------------------------------------------------ #
def _load_ohlcv(ticker: str, *, days: int = 365) -> pd.DataFrame:
    """Return OHLCV DataFrame indexed by date."""
    end = date.today()
    start = end - timedelta(days=days)

    qs = (
        MarketData.objects.filter(
            ticker=ticker,
            date__gte=start,
            date__lte=end,
        )
        .values("date", "open", "high", "low", "close", "volume")
        .order_by("date")
    )
    if not qs:
        return pd.DataFrame()

    return pd.DataFrame.from_records(qs).set_index("date").astype(float)


# ------------------------------------------------------------------ #
# Core
# ------------------------------------------------------------------ #
def calculate_indicators(ticker: str) -> List[TechnicalIndicator]:
    """
    Compute a broad set of indicators and return them as a flat list of
    TechnicalIndicator records (name, date, value).
    """
    df = _load_ohlcv(ticker)
    if df.empty:
        logger.info("No OHLCV found for %s", ticker)
        return []

    close, high, low, volume = (
        df["close"],
        df["high"],
        df["low"],
        df["volume"],
    )

    # ---------------- indicator calculations ----------------------- #
    results = {
        # ── Trend
        "SMA_50": ta.sma(close, length=50),
        "SMA_200": ta.sma(close, length=200),
        "EMA_12": ta.ema(close, length=12),
        "EMA_26": ta.ema(close, length=26),
        # ── Momentum
        "RSI_14": ta.rsi(close, length=14),
        "MOM_10": ta.mom(close, length=10),
        "STOCH": ta.stoch(high=high, low=low, close=close),
        "MACD": ta.macd(close),
        # ── Volatility
        "BBANDS": ta.bbands(close, length=20),
        "ATR_14": ta.atr(high=high, low=low, close=close, length=14),
        # ── Volume / Flow
        "OBV": ta.obv(close, volume),
        "CMF_20": ta.cmf(high=high, low=low, close=close, volume=volume, length=20),
    }

    # ---------------- flatten into dataclass list ------------------ #
    records: list[TechnicalIndicator] = []

    for ind_name, raw in results.items():
        try:
            if raw is None:
                continue

            if isinstance(raw, pd.DataFrame):  # MACD, BBANDS, STOCH
                for col in raw.columns:
                    col_name = f"{ind_name}_{col}"
                    series = raw[col].dropna()
                    records.extend(
                        TechnicalIndicator(ticker, col_name, idx, float(val))
                        for idx, val in series.items()
                    )
            else:
                series = raw.dropna()
                records.extend(
                    TechnicalIndicator(ticker, ind_name, idx, float(val))
                    for idx, val in series.items()
                )

        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to compute %s for %s: %s", ind_name, ticker, exc, exc_info=True
            )
            continue

    return records
