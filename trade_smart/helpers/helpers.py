from datetime import date, timedelta
from typing import List

import pandas as pd


from trade_smart.models.market_data import MarketData
from trade_smart.models.analytics import TechnicalIndicator

_MAX_LOOKBACK = 250


def _close_series(ticker: str, *, days: int = _MAX_LOOKBACK) -> pd.Series:
    """Return a pd.Series(date -> close) for *ticker*."""
    start = date.today() - timedelta(days=days * 2)  # *2 for weekends
    qs = (
        MarketData.objects.filter(ticker=ticker, date__gte=start)
        .values("date", "close")
        .order_by("date")
    )
    if not qs:
        return pd.Series(dtype=float)
    return pd.DataFrame.from_records(qs).set_index("date")["close"].astype(float)


def _to_records(
    ticker: str, name: str, series: pd.Series, *, limit: int = 30
) -> List[TechnicalIndicator]:
    """Turn a Series into a list[TechnicalIndicator] (last *limit* rows)."""
    return [
        TechnicalIndicator(
            ticker=ticker,
            date=idx,
            name=name,
            value=round(val, 6),
        )
        for idx, val in series.tail(limit).items()
    ]
