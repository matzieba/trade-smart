import logging
from datetime import date, timedelta

import pandas as pd
import pandas_ta as ta

from trade_smart.helpers.helpers import _to_records, _close_series
from trade_smart.models.market_data import MarketData

logger = logging.getLogger(__name__)

INDICATORS = {
    "SMA_50": lambda s: ta.sma(s, length=50),
    "SMA_200": lambda s: ta.sma(s, length=200),
    "RSI_14": lambda s: ta.rsi(s, length=14),
    "MACD": lambda s: ta.macd(s),
    "BBANDS": lambda s: ta.bbands(s),
}


def _load_ohlcv(ticker: str, *, days: int = 365):
    end = date.today()
    start = end - timedelta(days=days)
    qs = (
        MarketData.objects.filter(ticker=ticker, date__gte=start, date__lte=end)
        .values("date", "close")
        .order_by("date")
    )
    if not qs:
        return pd.Series(dtype=float)
    df = pd.DataFrame.from_records(qs).set_index("date")["close"]
    return df.astype(float)


def calculate_indicators(ticker: str):
    close = _close_series(ticker)
    if close.empty:
        logger.info("No OHLCV to compute indicators for %s", ticker)
        return []

    records = []

    for ind_name, func in INDICATORS.items():
        try:
            raw = func(close)

            # Function may legitimately return None
            if raw is None:
                logger.debug(
                    "%s not available for %s (too few data-points)", ind_name, ticker
                )
                continue

            # DataFrame (MACD, BBANDS)  --> split into individual columns
            if isinstance(raw, pd.DataFrame):
                for col in raw.columns:
                    col_name = f"{ind_name}_{col}"
                    series = raw[col].dropna()
                    records.extend(_to_records(ticker, col_name, series))
            else:
                series = raw.dropna()
                records.extend(_to_records(ticker, ind_name, series))

        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to compute %s for %s: %s",
                ind_name,
                ticker,
                exc,
                exc_info=True,
            )
            continue

    return records
