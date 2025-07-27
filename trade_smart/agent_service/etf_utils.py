# trade_smart/agent_service/etf_utils.py
from __future__ import annotations
import logging, datetime as dt
from typing import List, Tuple

import yfinance as yf  # >=0.2.65
import pandas as pd  # yfinance dep
import requests  # only for the FMP fall-back

log = logging.getLogger(__name__)

CACHE_TTL = dt.timedelta(hours=12)
_cache: dict[str, tuple[dt.datetime, list[Tuple[str, float]]]] = {}

FMP_KEY = ""  # set in env if you want the fallback

# ------------------------------------------------------------------ helpers


def _yfinance(sym: str, top_n: int = 10) -> list[tuple[str, float]]:
    """
    Return list[(ticker, weight 0-1)] using yfinance 0.2.65.

    Handles two observed table shapes:

    A) Long  (your current case)  rows = ticker, name, weight
           NVDA  NVIDIA Corp                 0.050926
           MSFT  Microsoft Corp              0.046407
           …

    B) Wide  index contains "Holding Percent", columns are tickers
           index → ["Name", "Holding Percent", …]
           cols  → NVDA  MSFT  AAPL …

    Any other shape ⇒ assume 'not an ETF' and return [].
    """
    import pandas as pd
    import yfinance as yf

    try:
        funds = yf.Ticker(sym).get_funds_data()
        if not funds or not hasattr(funds, "top_holdings"):
            return []
        df: pd.DataFrame = funds.top_holdings
    except Exception as exc:
        log.debug("yfinance holdings failed for %s: %s", sym, exc)
        return []

    if df.empty:
        return []

    rows: list[tuple[str, float]]

    # ---------------------------------------------------------------- case B – wide
    if "Holding Percent" in df.index:
        weights: pd.Series = df.loc["Holding Percent"]
        rows = [(tic.upper(), float(w)) for tic, w in weights.items()][:top_n]

    # ---------------------------------------------------------------- case A – long
    else:
        # ensure column names we can reference
        df = df.copy()
        df.columns = [str(c).strip().lower() for c in df.columns]

        # find the two essential columns
        sym_col = next(
            (c for c in df.columns if c in ("symbol", "ticker", "0")),
            df.columns[0],
        )
        w_col = next(
            (
                c
                for c in df.columns
                if c.replace(" ", "") in ("holdingpercent", "weight", "holding%")
            ),
            None,
        )
        if w_col is None:
            # choose first numeric column from the right
            w_col = next(
                (
                    c
                    for c in reversed(df.columns)
                    if pd.api.types.is_numeric_dtype(df[c])
                ),
                None,
            )
        if w_col is None:
            log.debug("No weight column found in holdings for %s", sym)
            return []

        rows = []
        for _, r in df.head(top_n).iterrows():
            tic = str(r[sym_col]).upper().strip()
            if not tic:
                continue
            wt = float(r[w_col])
            if wt > 1.01:  # convert 0-100 → 0-1
                wt /= 100.0
            rows.append((tic, wt))

    # normalise slice to exactly 1.0
    total = sum(w for _, w in rows) or 1.0
    return [(t, w / total) for t, w in rows]


def _fmp(sym: str, top_n: int = 10) -> list[Tuple[str, float]]:
    if not FMP_KEY:
        return []
    url = (
        f"https://financialmodelingprep.com/api/v3/etf-holdings/{sym}"
        f"?apikey={FMP_KEY}"
    )
    try:
        js = requests.get(url, timeout=8).json()
        rows = [(r["asset"], float(r["weight"]) / 100.0) for r in js[:top_n]]
        tot = sum(w for _, w in rows) or 1.0
        return [(t, w / tot) for t, w in rows]
    except Exception as exc:
        log.debug("FMP holdings err: %s", exc)
        return []


# ------------------------------------------------------------------ public
def get_etf_constituents(symbol: str, top_n: int = 10) -> list[tuple[str, float]]:
    """
    1) yfinance (free, no key, new endpoint)
    2) Financial-Modeling-Prep (free tier but needs API key)
    3) return []  -> treat as 'probably not an ETF'
    """
    res = _yfinance(symbol, top_n) or _fmp(symbol, top_n) or []
    _cache[symbol] = (dt.datetime.now(dt.timezone.utc), res)
    return res


def is_etf(symbol: str) -> bool:
    return bool(get_etf_constituents(symbol, top_n=4))
