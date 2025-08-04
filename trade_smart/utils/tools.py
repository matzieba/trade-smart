# agent_service/tools.py
from __future__ import annotations
import os, json, logging
from datetime import datetime, timedelta
from typing import Optional

import requests
import yfinance as yf
import redis

logger = logging.getLogger(__name__)

# ---------- optional cache --------------------------------------------------
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
try:
    rds: Optional[redis.Redis] = redis.Redis.from_url(REDIS_URL)  # type: ignore
except Exception:
    rds = None


def _cache_get(key: str) -> Optional[str]:
    if rds:
        try:
            val = rds.get(key)
            return val.decode() if val else None
        except Exception:
            pass
    return None


def _cache_set(key: str, value: str, ttl: int = 900):
    if rds:
        try:
            rds.set(key, value, ex=ttl)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def last_price(ticker: str) -> Optional[float]:
    from trade_smart.models.market_data import MarketData

    row = MarketData.objects.filter(ticker=ticker).order_by("-date").first()
    if row:
        return float(row.close)

    # Fallback to yfinance live call – only happens if DB empty
    try:
        px = yf.Ticker(ticker).history(period="1d")["Close"].iloc[-1]
        return float(px)
    except Exception as exc:
        logger.warning("Could not fetch last price for %s: %s", ticker, exc)
        return None


# ──── keep everything you already have above here ─────────────────────────
import hashlib, time, random
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

import pandas as pd  #  ← add to requirements.txt
import requests

# ---------------------------------------------------------------------------
# Yahoo + fallback screener helpers
# ---------------------------------------------------------------------------

_YF_URL = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/"
_YF_SCREENS = [
    "most_actives",
    "day_gainers",
    "day_losers",
    "undervalued_growth",
    "undervalued_large_caps",
]
_YF_REGIONS = ["US", "DE", "GB", "FR", "IN", "HK", "AU", "CA"]

_FMP_KEY = os.getenv("FMP_KEY", "demo")
_FMP_URL = "https://financialmodelingprep.com/api/v3/stock/actives"
_STOOQ_URL = "https://stooq.com/t/?i=505"  # CSV of world most active
_HEADERS = {"User-Agent": "Mozilla/5.0 WiseTrade/0.1"}


def _cache_key(url: str, params: dict) -> str:
    raw = url + "?" + "&".join(f"{k}={params[k]}" for k in sorted(params))
    return "http:" + hashlib.sha1(raw.encode()).hexdigest()


def _http_get_json(
    url: str,
    params: dict,
    ttl: int = 300,
    max_attempts: int = 5,
    backoff_base: float = 1.2,
):
    """
    Cached HTTP GET with exponential back-off on 429/5xx.
    Returns python dict (json-decoded) or raises last error.
    """
    key = _cache_key(url, params)
    if cached := _cache_get(key):
        return json.loads(cached)

    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.get(url, params=params, headers=_HEADERS, timeout=10)
            if resp.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(
                    f"{resp.status_code} from {url}", response=resp
                )
            resp.raise_for_status()
            data = resp.json()
            _cache_set(key, json.dumps(data), ttl)
            return data
        except Exception as exc:
            if attempt == max_attempts:
                raise
            sleep_for = backoff_base**attempt + random.uniform(0, 0.3)
            time.sleep(sleep_for)


# ─── Yahoo helpers ─────────────────────────────────────────────────────────
def _yf_screen(screen: str, region: str) -> List[str]:
    params = {"scrIds": screen, "count": 30, "region": region}
    data = _http_get_json(_YF_URL, params, ttl=300)
    items = data["finance"]["result"][0]["quotes"]
    return [x["symbol"] for x in items]


def _yahoo_candidates(max_workers: int = 4) -> List[str]:
    tickers: set[str] = set()
    with ThreadPoolExecutor(max_workers=max_workers) as tp:
        futs = [tp.submit(_yf_screen, s, r) for s in _YF_SCREENS for r in _YF_REGIONS]
        for f in as_completed(futs):
            try:
                tickers.update(f.result())
            except Exception:
                # already logged by _http_get_json, proceed
                pass
            if len(tickers) >= 4:
                break
    return list(tickers)


# ─── Fallback helpers ──────────────────────────────────────────────────────
def _fmp_candidates(limit: int = 120) -> List[str]:
    key = "fmp_actives"
    if cached := _cache_get(key):
        return json.loads(cached)[:limit]

    params = {"apikey": _FMP_KEY}
    try:
        data = _http_get_json(_FMP_URL, params, ttl=600)
        tickers = [row["ticker"] for row in data][:limit]
        _cache_set(key, json.dumps(tickers), 600)
        return tickers
    except Exception:
        return []


def _stooq_candidates(limit: int = 120) -> List[str]:
    key = "stooq_actives"
    if cached := _cache_get(key):
        return json.loads(cached)[:limit]

    try:
        df = pd.read_csv(_STOOQ_URL)
        tickers = df["Symbol"].head(limit).tolist()
        _cache_set(key, json.dumps(tickers), 600)
        return tickers
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Public screener API
# ---------------------------------------------------------------------------
def get_hot_tickers(limit: int = 120) -> List[str]:
    """
    Returns up to `limit` unique tickers world-wide.
    Order is arbitrary but deterministic within one run.
    Strategy:
        1. Yahoo predefined screens (throttled & cached)
        2. FMP actives  (if still short)
        3. Stooq list   (final fallback)
    """
    tickers = _yahoo_candidates()
    if len(tickers) < limit:
        tickers.extend(x for x in _fmp_candidates(limit) if x not in tickers)
    if len(tickers) < limit:
        tickers.extend(x for x in _stooq_candidates(limit) if x not in tickers)

    return tickers[:limit]
