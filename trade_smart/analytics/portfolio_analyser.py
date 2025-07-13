from __future__ import annotations
import logging
from decimal import Decimal
from typing import Dict, List

import numpy as np
import pandas as pd
from django.db.models import F

from trade_smart.models.market_data import MarketData
from trade_smart.models.portfolio import Portfolio

logger = logging.getLogger(__name__)

BENCHMARK = "SPY"


def _price_matrix(tickers: List[str], days: int = 252) -> pd.DataFrame:
    qs = MarketData.objects.filter(
        ticker__in=tickers, date__gte=pd.Timestamp.today() - pd.Timedelta(days=days)
    ).values("ticker", "date", "close")
    df = pd.DataFrame.from_records(qs)
    if df.empty:
        return pd.DataFrame()
    return df.pivot(index="date", columns="ticker", values="close").sort_index().ffill()


def analyse(portfolio: Portfolio) -> Dict:
    if not portfolio.positions.exists():
        return {"error": "Portfolio empty"}

    tickers = list(portfolio.positions.values_list("ticker", flat=True))
    weights = {}
    total_mv = Decimal(portfolio.market_value())
    for pos in portfolio.positions.all():
        weights[pos.ticker] = (pos.qty * pos.avg_price) / total_mv

    price_df = _price_matrix(tickers + [BENCHMARK])
    if price_df.empty or price_df.shape[0] < 60:
        return {"error": "Not enough price history"}

    returns = price_df.pct_change().dropna()
    port_ret = (returns[tickers] * pd.Series(weights)).sum(axis=1)

    bench_ret = returns[BENCHMARK]
    cov = np.cov(port_ret, bench_ret)[0][1]
    beta = cov / bench_ret.var()

    # 95 % historical VaR (1-day)
    var_95 = np.percentile(port_ret, 5)

    ann_vol = port_ret.std() * np.sqrt(252)

    return {
        "weights": {k: float(w) for k, w in weights.items()},
        "beta": round(float(beta), 4),
        "var_95_daily": round(float(var_95), 4),
        "vol_annual": round(float(ann_vol), 4),
        "data_points": int(len(port_ret)),
    }
