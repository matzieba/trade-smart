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
    """
    Return the most recent close for *ticker* from DB (preferred) or yfinance.
    """
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


def macro_sentiment() -> str:
    """
    Very simple macro regime detector based on the VIX level.
    Possible outputs: "RISK_ON" | "NEUTRAL" | "RISK_OFF" | "UNKNOWN"
    Cached 15 minutes in Redis.
    """
    cache_key = "macro:vix_sentiment"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    # --- fetch VIX value ----------------------------------------------------
    vix_val: Optional[float] = None

    # ① Try yfinance (most robust, 100 % free)
    try:
        vix_val = float(yf.Ticker("^VIX").history(period="1d")["Close"].iloc[-1])
    except Exception:
        pass

    # ② Fallback to St. Louis FRED if we have an API key
    if vix_val is None and (fred_key := os.getenv("FRED_API_KEY")):
        try:
            uri = (
                "https://api.stlouisfed.org/fred/series/observations?"
                f"series_id=VIXCLS&api_key={fred_key}&file_type=json&"
                "sort_order=desc&limit=1"
            )
            js = requests.get(uri, timeout=8).json()
            vix_val = float(js["observations"][0]["value"])
        except Exception:
            pass

    if vix_val is None:
        logger.warning("Could not obtain VIX – defaulting to UNKNOWN sentiment")
        _cache_set(cache_key, "UNKNOWN", ttl=300)
        return "UNKNOWN"

    # --- classify -----------------------------------------------------------
    sentiment = "RISK_OFF" if vix_val > 25 else "NEUTRAL" if vix_val > 18 else "RISK_ON"

    _cache_set(cache_key, sentiment)
    return sentiment
