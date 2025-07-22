"""
Pull *full* news articles (url, title, published_at, source) for a given
ticker symbol.  Priority order is:

    1. Alpha Vantage NEWS_SENTIMENT   (500 calls / day free tier)
    2. Yahoo-Finance RSS              (no key)
    3. DuckDuckGo news vertical       (fallback)

Returned list is already de-duplicated and bounded.
"""

from __future__ import annotations

import os, logging, datetime as dt, requests, feedparser
from typing import List, Dict, Any
from dateutil import parser as date_parser  # pip install python-dateutil
from duckduckgo_search import DDGS

# --------------------------------------------------------------------------- #
logger = logging.getLogger(__name__)
AV_KEY = os.getenv("ALPHAVANTAGE_KEY", "")
UTC = dt.timezone.utc


def _parse_dt(raw: str | None) -> dt.datetime | None:
    """Robust ISO/HTTP date → tz-aware UTC datetime or None."""
    if not raw:
        return None
    try:
        dt_obj = date_parser.parse(raw)
        if dt_obj.tzinfo is None:
            dt_obj = dt_obj.replace(tzinfo=UTC)
        return dt_obj.astimezone(UTC)
    except Exception:
        logger.debug("Date-parse failed for %s", raw)
        return None


# --------------------------------------------------------------------------- #
#  1) Alpha Vantage
# --------------------------------------------------------------------------- #
def _alpha_vantage_articles(
    tkr: str, lookback_h: int = 72, limit: int = 40
) -> List[Dict[str, Any]]:
    if not AV_KEY:
        return []
    since = (dt.datetime.now(UTC) - dt.timedelta(hours=lookback_h)).isoformat(
        timespec="seconds"
    )
    url = (
        "https://www.alphavantage.co/query"
        f"?function=NEWS_SENTIMENT&tickers={tkr}"
        f"&time_from={since}&limit={limit}&apikey={AV_KEY}"
    )
    try:
        feed = requests.get(url, timeout=8).json().get("feed", [])
    except Exception as exc:
        logger.debug("AV news error: %s", exc)
        return []

    out = []
    for item in feed:
        out.append(
            {
                "url": item.get("url"),
                "title": item.get("title"),
                "publishedAt": _parse_dt(item.get("time_published")),
                "source": item.get("source"),
            }
        )
    return out


# --------------------------------------------------------------------------- #
#  2) Yahoo Finance RSS
# --------------------------------------------------------------------------- #
def _yahoo_rss_articles(tkr: str, limit: int = 25) -> List[Dict[str, Any]]:
    url = (
        "https://feeds.finance.yahoo.com/rss/2.0/headline"
        f"?s={tkr}&region=US&lang=en-US"
    )
    try:
        feed = feedparser.parse(url)
    except Exception as exc:
        logger.debug("Yahoo RSS error: %s", exc)
        return []

    out = []
    for e in feed.entries[:limit]:
        pub = None
        if e.get("published"):
            pub = _parse_dt(e.published)
        elif e.get("updated"):
            pub = _parse_dt(e.updated)
        out.append(
            {
                "url": e.link,
                "title": e.title,
                "publishedAt": pub,
                "source": "Yahoo Finance",
            }
        )
    return out


# --------------------------------------------------------------------------- #
#  3) DuckDuckGo News (fallback)
# --------------------------------------------------------------------------- #
def _ddg_articles(tkr: str, lookback_h: int = 72, k: int = 20) -> List[Dict[str, Any]]:
    q = f"{tkr} stock news business after:{lookback_h}h"
    try:
        with DDGS() as ddgs:
            hits = ddgs.news(q, max_results=k)
    except Exception as exc:
        logger.debug("DDG news error: %s", exc)
        return []

    out = []
    for h in hits:
        out.append(
            {
                "url": h.get("href"),
                "title": h.get("title"),
                "publishedAt": _parse_dt(h.get("date")),
                "source": h.get("source"),
            }
        )
    return out


# --------------------------------------------------------------------------- #
#  PUBLIC ENTRY POINT
# --------------------------------------------------------------------------- #
def fetch_articles_for_ticker(
    ticker: str, lookback_h: int = 72, hard_limit: int = 40
) -> List[Dict[str, Any]]:
    """
    Deduplicated, newest-first list of article dicts with keys:
        url, title, publishedAt (tz-aware UTC), source
    """
    articles = (
        _alpha_vantage_articles(ticker, lookback_h)
        or _yahoo_rss_articles(ticker)
        or _ddg_articles(ticker, lookback_h)
    )

    # ---- de-dup by URL ----------------------------------------------------- #
    seen, uniq = set(), []
    for art in articles:
        if not art["url"] or art["url"] in seen:
            continue
        uniq.append(art)
        seen.add(art["url"])

    # ---- newest first & hard cap ------------------------------------------ #
    uniq.sort(
        key=lambda a: a["publishedAt"] or dt.datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )
    return uniq[:hard_limit]
