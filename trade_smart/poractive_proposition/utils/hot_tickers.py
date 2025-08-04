"""
Get up-to-120 “hot” tickers world-wide – fast & in the free tier.

Strategy
1. Primary  : FinancialModelingPrep stock-screener  (1 HTTP call)
2. Fallback : Stooq CSV if FMP quota / network fails
Both results are cached in Redis for 15 min (900 s).
"""

from __future__ import annotations
import os, json, logging, hashlib, random, time
from typing import List, Optional

import requests
import pandas as pd  # already in requirements
from trade_smart.utils.tools import _cache_get, _cache_set  # keep!

logger = logging.getLogger(__name__)
_HEADERS = {"User-Agent": "WiseTrade/0.1 (+https://github.com/yourrepo)"}
_FMP_KEY = os.getenv("FMP_KEY", "demo")
_FMP_URL = "https://financialmodelingprep.com/api/v3/stock-screener"
_STOOQ_URL = "https://stooq.com/t/?i=505"  # CSV, no key


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _http_get_json(url: str, params: dict, ttl: int = 900) -> list[dict]:
    """
    Cached GET that returns a decoded JSON list.
    Raises last HTTP error on failure.
    """
    raw_key = url + "?" + "&".join(f"{k}={params[k]}" for k in sorted(params))
    cache_key = "http:" + hashlib.sha1(raw_key.encode()).hexdigest()

    if cached := _cache_get(cache_key):
        return json.loads(cached)

    for attempt in range(1, 4):  # at most 3 tries
        try:
            r = requests.get(url, params=params, headers=_HEADERS, timeout=10)
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"{r.status_code} from {url}", response=r)
            r.raise_for_status()
            data = r.json()
            _cache_set(cache_key, json.dumps(data), ttl)
            return data
        except Exception as exc:
            logger.warning("GET %s (try %s/3) failed: %s", url, attempt, exc)
            time.sleep(1.5 * attempt + random.uniform(0, 0.3))

    raise RuntimeError(f"GET {url} failed after 3 attempts")


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------
def get_hot_tickers(limit: int = 120) -> List[str]:
    """
    Returns ≤ `limit` unique tickers, world-wide.
    Typical latency: 1–2 s when FMP is available.
    """
    # 1. --- FinancialModelingPrep -------------------------------------------
    try:
        fmp_params = {
            "marketCapMoreThan": 1_000_000_000,  # > 1 B $
            "volumeMoreThan": 2_000_000,  # decent liquidity
            "limit": limit,
            "apikey": _FMP_KEY,
        }
        data = _http_get_json(_FMP_URL, fmp_params, ttl=900)
        tickers = [row["symbol"] for row in data][:limit]
        if tickers:
            return tickers
    except Exception as exc:
        logger.warning("FMP screener failed, falling back to Stooq: %s", exc)

    # 2. --- Stooq fallback ---------------------------------------------------
    try:
        cache_key = f"stooq_hot:{limit}"
        if cached := _cache_get(cache_key):
            return json.loads(cached)

        r = requests.get(_STOOQ_URL, headers=_HEADERS, timeout=10)
        r.raise_for_status()
        import io

        df = pd.read_csv(io.StringIO(r.text))
        tickers = df["Symbol"].head(limit).tolist()
        _cache_set(cache_key, json.dumps(tickers), ttl=3600)
        return tickers
    except Exception as exc:
        logger.error("Stooq fallback failed as well: %s", exc)

    # 3. --- give up – empty list keeps pipeline alive -----------------------
    return []
