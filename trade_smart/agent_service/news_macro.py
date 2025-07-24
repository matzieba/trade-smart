from __future__ import annotations

import re
import json
import logging
import datetime as dt
from typing import List, Dict, Any
from decimal import Decimal

import requests
from duckduckgo_search import DDGS

import settings
from trade_smart.agent_service.etf_utils import get_etf_constituents, is_etf
from trade_smart.models.news_article import NewsArticle
from trade_smart.models.llm_sentiment import LLMSentiment

try:
    import feedparser
except ImportError:
    feedparser = None

logger = logging.getLogger(__name__)
ALPHAV_KEY = settings.ALPHAVANTAGE_KEY
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


def _etf_sentiment(ticker: str) -> Dict[str, Any]:
    holdings = get_etf_constituents(ticker, top_n=3)
    if not holdings:
        headlines, raw_news = gather_recent_headlines(ticker)
        sentiment_result = classify_sentiment(ticker, headlines)
        _save_news_articles(ticker, raw_news, sentiment_result["score"])
        return sentiment_result

    total_score = Decimal(0)
    num_scores = 0
    all_summaries = []

    # Translate holding names to tickers where necessary
    translated_holdings = []
    for holding_identifier, weight in holdings:
        # Heuristic: if it contains a space, it's likely a name
        if " " in holding_identifier:
            try:
                ticker_from_name = translate_holding_to_ticker(holding_identifier)
                translated_holdings.append((ticker_from_name, weight))
                logger.info(
                    f"Translated '{holding_identifier}' to '{ticker_from_name}'"
                )
            except Exception as e:
                logger.warning(
                    f"Could not translate '{holding_identifier}' to ticker, using original: {e}"
                )
                translated_holdings.append((holding_identifier, weight))
        else:
            translated_holdings.append((holding_identifier, weight))
    holdings = translated_holdings

    for holding_ticker, _ in holdings:
        try:
            headlines, raw_news = gather_recent_headlines(holding_ticker)
            sentiment_result = classify_sentiment(holding_ticker, headlines)
            score = Decimal(str(sentiment_result.get("score", 0.0)))
            summary = sentiment_result.get("summary", "")

            total_score += score
            num_scores += 1
            if summary:
                all_summaries.append(f"{holding_ticker}: {summary}")

            _save_news_articles(holding_ticker, raw_news, score)

        except Exception as exc:
            logger.warning(f"Error processing sentiment for {holding_ticker}: {exc}")

    if num_scores > 0:
        avg_score = total_score / num_scores
        overall_summary = (
            f"Aggregated sentiment for {ticker} constituents: "
            + "; ".join(all_summaries)
        )
        return {"summary": overall_summary, "score": float(avg_score)}
    else:
        return {
            "summary": f"Could not determine sentiment for {ticker} constituents.",
            "score": 0.0,
        }


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


def _yfinance_news(ticker: str, limit: int = 25) -> List[Dict]:
    """
    Fetch news via yfinance.  Returns list[{title, link, provider, …}].
    No API-key, no quota, one HTTPS call.
    """
    try:
        import yfinance as yf

        news = yf.Ticker(ticker).news or []
        return news
    except Exception as exc:
        logger.debug("yFinance news error: %s", exc)
        return []


def _save_news_articles(
    ticker: str, raw_news_data: List[Dict], sentiment_score: float | None = None
):
    articles_to_create = []
    for item in raw_news_data:
        title = item.get("title") or item.get("title_text", "")
        url = item.get("link") or item.get("url", "")
        source = item.get("provider", "") or item.get("source", "")

        published_at = None
        if "published" in item:
            published_at = dt.datetime.fromtimestamp(
                item["published"], tz=dt.timezone.utc
            )
        elif "time_published" in item:
            published_at = dt.datetime.strptime(item["time_published"], "%Y%m%d%H%M%S")
            # Alpha Vantage times are UTC, but not timezone-aware
            published_at = published_at.replace(tzinfo=dt.timezone.utc)
        elif "date" in item:
            try:
                # DDG news date format: 'YYYY-MM-DDTHH:MM:SS'
                published_at = dt.datetime.fromisoformat(item["date"]).replace(
                    tzinfo=dt.timezone.utc
                )
            except ValueError:
                pass  # Fallback if format is unexpected

        sentiment = None
        if "overall_sentiment_score" in item:
            try:
                sentiment = Decimal(str(item["overall_sentiment_score"]))
            except (ValueError, TypeError):
                pass
        elif sentiment_score is not None:
            sentiment = Decimal(str(sentiment_score))

        if title and url and published_at:
            articles_to_create.append(
                NewsArticle(
                    ticker=ticker,
                    headline=title,
                    source=source,
                    url=url,
                    published_at=published_at,
                    sentiment=sentiment,
                )
            )
    if articles_to_create:
        # Filter out duplicates based on URL and published_at before bulk_create
        existing_articles = NewsArticle.objects.filter(
            url__in=[a.url for a in articles_to_create],
            published_at__in=[a.published_at for a in articles_to_create],
        ).values_list("url", "published_at")
        existing_articles_set = set(existing_articles)

        unique_articles = []
        for article in articles_to_create:
            if (article.url, article.published_at) not in existing_articles_set:
                unique_articles.append(article)
                existing_articles_set.add(
                    (article.url, article.published_at)
                )  # Add to set to handle duplicates within the current batch

        if unique_articles:
            NewsArticle.objects.bulk_create(unique_articles, ignore_conflicts=True)
            logger.info(f"Saved {len(unique_articles)} news articles for {ticker}")


# --------------------------------------------------------------------------- #
def gather_recent_headlines(ticker: str) -> tuple[List[str], List[Dict]]:
    """
    (1) yfinance  → (2) Alpha-Vantage  → (3) Yahoo-RSS  → (4) DuckDuckGo
    Stop at first source that returns anything ≥1 headline.
    """
    raw = (
        _yfinance_news(ticker)
        or _alpha_vantage_news(ticker)
        or _yahoo_rss_news(ticker)
        or _duckduckgo_news(ticker)
    )

    titles = [r.get("content").get("title") or r.get("title_text", "") for r in raw]
    seen, uniq = set(), []
    for t in titles:
        if t and t not in seen:
            uniq.append(t)
            seen.add(t)
    return uniq[:25], raw


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


def classify_sentiment(ticker: str, headlines: List[str]) -> Dict[str, Any]:
    if not headlines:
        return {"summary": "No fresh headlines", "score": 0.0}

    joined = "\n".join(f"- {h}" for h in headlines)
    llm = _get_llm()
    prompt = f"{_SYSTEM_PROMPT}\n" f"HEADLINES (newest first):\n{joined}"

    resp = llm.invoke(prompt)
    js = _safe_json(resp.content)
    if js:
        sentiment_score = float(js.get("score", 0.0))
        sentiment_summary = str(js.get("summary", ""))
        LLMSentiment.objects.create(
            ticker=ticker,
            score=Decimal(str(sentiment_score)),
            summary=sentiment_summary,
        )
        return {
            "summary": sentiment_summary,
            "score": sentiment_score,
        }

    return {"summary": "LLM parse error", "score": 0.0}


# --------------------------------------------------------------------------- #
def web_news_node(state: Dict[str, Any]) -> Dict[str, Any]:
    ticker = state["ticker"]
    if is_etf(ticker):
        state["raw_headlines"] = []
        state["news_macro"] = _etf_sentiment(ticker)
    else:
        headlines, raw_news = gather_recent_headlines(ticker)
        state["raw_headlines"] = headlines
        sentiment_result = classify_sentiment(ticker, headlines)
        state["news_macro"] = sentiment_result
        _save_news_articles(ticker, raw_news, sentiment_result["score"])
    return state


def translate_holding_to_ticker(holding_name: str) -> str:
    """
    Translate a holding name (e.g., 'Nvidia Corp') to a ticker (e.g., 'NVDA').
    """
    llm = _get_llm()
    prompt = (
        f"You are a financial expert. Your task is to return just ticker for a given company name. Nothing else."
        f"Given the holding name '{holding_name}', what is its stock ticker?"
    )
    response = llm.invoke(prompt)
    # The response should be just the ticker, so we can strip any extra whitespace.
    return response.content.strip()


# manual test:  python -m trade_smart.agent_service.news_macro AAPL
if __name__ == "__main__":  # pragma: no cover
    import sys
    import pprint

    pprint.pp(web_news_node({"ticker": sys.argv[1] if len(sys.argv) > 1 else "AAPL"}))
