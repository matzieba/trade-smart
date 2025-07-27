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
