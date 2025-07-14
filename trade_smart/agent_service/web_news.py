from __future__ import annotations
import os, json, datetime as dt, logging
from typing import Dict, Any, List

from duckduckgo_search import DDGS
from bs4 import BeautifulSoup
import requests

from trade_smart.agent_service.llm import get_llm

logger = logging.getLogger(__name__)
llm = get_llm()


# ------------------------------------------------------------------ #
def _search_urls(query: str, *, k: int = 10) -> List[dict]:
    with DDGS() as ddgs:
        return list(ddgs.text(query, safesearch="off", max_results=k))


def _scrape_title(url: str) -> str | None:
    try:
        html = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"}).text
        soup = BeautifulSoup(html, "html.parser")
        return soup.title.text.strip() if soup.title else None
    except Exception as exc:
        logger.debug("Scrape failed for %s: %s", url, exc)
        return None


# ------------------------------------------------------------------ #
def web_news_node(state: Dict[str, Any]) -> Dict[str, Any]:
    ticker = state["ticker"]
    query = f"{ticker} stock news last 24 hours"
    hits = _search_urls(query, k=10)

    headlines = []
    for h in hits:
        title = h.get("title") or _scrape_title(h["href"])
        if title:
            headlines.append(title)

    if not headlines:
        state["news_macro"] = {"score": 0.0, "summary": "No fresh web headlines"}
        return state

    joined = "\n".join(f"- {t}" for t in headlines[:10])

    prompt = f"""
You are a sentiment classifier for equity news.
HEADLINES (latest first):
{joined}

Return JSON exactly like:
{{"summary": "...", "score": 0.25}}
Where score ∈ [-1,1].
"""
    resp = llm.predict(prompt)
    try:
        js = json.loads(resp)
        score = float(js["score"])
        summary = js["summary"]
    except Exception:
        score, summary = 0.0, "LLM parse error"

    state["news_macro"] = {"score": score, "summary": summary}
    state["raw_headlines"] = headlines  # optional: for audit
    return state
