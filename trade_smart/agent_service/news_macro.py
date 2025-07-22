# trade_smart/agent_service/news_macro.py
from __future__ import annotations

import os, re, json, logging, datetime as dt
from typing import List, Dict, Any

import requests
from duckduckgo_search import DDGS

try:
    import feedparser  # for Yahoo-RSS
except ImportError:  # pragma: no cover
    feedparser = None  # will raise at runtime

logger = logging.getLogger(__name__)
ALPHAV_KEY = os.getenv("ALPHAVANTAGE_KEY", "")
_llm = None  # lazy-load to avoid circular import


# --------------------------------------------------------------------------- #
#   HELPERS
# --------------------------------------------------------------------------- #
def _utc_now() -> dt.datetime:
    """timezone-aware ‘now’ in UTC (no deprecation warnings)."""
    return dt.datetime.now(dt.timezone.utc)


def _get_llm():
    global _llm
    if _llm is None:
        from trade_smart.agent_service.llm import get_llm

        _llm = get_llm()
    return _llm


# --------------------------------------------------------------------------- #
#   NEWS FETCHERS  (AV → Yahoo → DDG)
# --------------------------------------------------------------------------- #
def _alpha_vantage_news(
    ticker: str, lookback_h: int = 24, limit: int = 40
) -> List[Dict]:
    if not ALPHAV_KEY:
        return []
    time_from = (_utc_now() - dt.timedelta(hours=lookback_h)).isoformat(
        timespec="seconds"
    )
    url = (
        "https://www.alphavantage.co/query"
        f"?function=NEWS_SENTIMENT&tickers={ticker}"
        f"&time_from={time_from}&limit={limit}&apikey={ALPHAV_KEY}"
    )
    try:
        return requests.get(url, timeout=8).json().get("feed", [])
    except Exception as exc:
        logger.debug("AV news error: %s", exc)
        return []


def _yahoo_rss_news(ticker: str, limit: int = 25) -> List[Dict]:
    if feedparser is None:  # pragma: no cover
        raise RuntimeError("pip install feedparser")
    url = (
        "https://feeds.finance.yahoo.com/rss/2.0/headline"
        f"?s={ticker}&region=US&lang=en-US"
    )
    try:
        feed = feedparser.parse(url)
        return [{"title": e.title, "link": e.link} for e in feed.entries[:limit]]
    except Exception as exc:
        logger.debug("Yahoo RSS error: %s", exc)
        return []


def _duckduckgo_news(ticker: str, lookback_h: int = 24, k: int = 15) -> List[Dict]:
    q = f"{ticker} stock news business after:{lookback_h}h"
    try:
        with DDGS() as ddgs:
            return list(ddgs.news(q, max_results=k))
    except Exception as exc:
        logger.debug("DDG news error: %s", exc)
        return []


# --------------------------------------------------------------------------- #
def gather_recent_headlines(ticker: str) -> List[str]:
    raw = (
        _alpha_vantage_news(ticker)
        or _yahoo_rss_news(ticker)
        or _duckduckgo_news(ticker)
    )
    titles = [r.get("title") or r.get("title_text", "") for r in raw]
    seen, uniq = set(), []
    for t in titles:
        if t and t not in seen:
            uniq.append(t)
            seen.add(t)
    return uniq[:15]


# --------------------------------------------------------------------------- #
#   SENTIMENT  (robust JSON extraction)
# --------------------------------------------------------------------------- #
_SYSTEM_PROMPT = (
    "You are a JSON-only sentiment classifier for equity news.\n"
    'Return exactly: {"summary": "…", "score": 0.34}\n'
    "score ∈ [-1,1]. No other text."
)

_JSON_RE = re.compile(r"\{.*?\}", re.DOTALL)


def _safe_json(response: str) -> Dict[str, Any] | None:
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        m = _JSON_RE.search(response)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    return None


def classify_sentiment(headlines: List[str]) -> Dict[str, Any]:
    if not headlines:
        return {"summary": "No fresh headlines", "score": 0.0}

    joined = "\n".join(f"- {h}" for h in headlines)
    llm = _get_llm()
    prompt = f"{_SYSTEM_PROMPT}\n" f"HEADLINES (newest first):\n{joined}"

    try:

        resp = llm.invoke(prompt)
        js = _safe_json(resp.content)
        if js:
            return {
                "summary": str(js.get("summary", "")),
                "score": float(js.get("score", 0.0)),
            }
    except Exception as exc:
        logger.debug("LLM sentiment err: %s", exc)

    return {"summary": "LLM parse error", "score": 0.0}


# --------------------------------------------------------------------------- #
def web_news_node(state: Dict[str, Any]) -> Dict[str, Any]:
    ticker = state["ticker"]
    headlines = gather_recent_headlines(ticker)
    state["raw_headlines"] = headlines
    state["news_macro"] = classify_sentiment(headlines)
    return state


# manual test:  python -m trade_smart.agent_service.news_macro AAPL
if __name__ == "__main__":  # pragma: no cover
    import sys, pprint

    pprint.pp(web_news_node({"ticker": sys.argv[1] if len(sys.argv) > 1 else "AAPL"}))
