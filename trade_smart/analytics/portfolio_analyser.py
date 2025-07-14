from __future__ import annotations
import logging
from decimal import Decimal
from typing import Dict, List, Any

import numpy as np
import pandas as pd
from django.db.models import F

from trade_smart.models.market_data import MarketData
from trade_smart.models.portfolio import Portfolio

logger = logging.getLogger(__name__)

BENCHMARK = "MSFT"


def _price_matrix(tickers: List[str], days: int = 252) -> pd.DataFrame:
    qs = MarketData.objects.filter(
        ticker__in=tickers, date__gte=pd.Timestamp.today() - pd.Timedelta(days=days)
    ).values("ticker", "date", "close")
    df = pd.DataFrame.from_records(qs)
    if df.empty:
        return pd.DataFrame()

    # ① make sure 'close' is float, not Decimal
    df["close"] = df["close"].astype(float)

    return (
        df.pivot(index="date", columns="ticker", values="close")
        .sort_index()
        .ffill()
        .astype(float)  # ② enforce float dtype on the whole frame
    )


def analyse(portfolio: Portfolio) -> Dict[str, Any]:
    if not portfolio.positions.exists():
        return {"error": "Portfolio empty"}

    # convert to float right away for NumPy / Pandas
    total_mv = float(portfolio.market_value() or 0)
    if total_mv == 0:
        return {"error": "No market value yet (quotes missing)"}

    weights = {
        p.ticker: (float(p.qty) * float(p.avg_price)) / total_mv
        for p in portfolio.positions.all()
    }

    tickers = list(weights.keys())
    price_df = _price_matrix(tickers + [BENCHMARK])
    if price_df.shape[0] < 60:
        return {"error": "Not enough price history"}

    returns = price_df.pct_change().dropna()
    port_ret = (returns[tickers] * pd.Series(weights)).sum(axis=1)

    # ---------- beta --------------------------------------------------------
    beta = None
    if BENCHMARK in returns.columns:
        pair = pd.concat(
            [port_ret.rename("pf"), returns[BENCHMARK].rename("bm")],
            axis=1,
            join="inner",
        ).dropna()

        if len(pair) > 30 and pair["bm"].var() != 0:
            beta = pair.cov().iloc[0, 1] / pair["bm"].var()

    # ---------- risk --------------------------------------------------------
    var_95 = np.percentile(port_ret, 5)
    ann_vol = port_ret.std() * np.sqrt(252)

    return {
        "weights": {k: round(v, 6) for k, v in weights.items()},
        "beta": round(beta, 4) if beta is not None else None,
        "var_95_daily": round(float(var_95), 4),
        "vol_annual": round(float(ann_vol), 4),
        "data_points": int(len(port_ret)),
    }
