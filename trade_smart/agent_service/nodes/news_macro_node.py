from typing import Any, Dict

from trade_smart.agent_service.data_providers.etf_utils import is_etf
from trade_smart.agent_service.data_providers.news_macro import (
    _etf_sentiment,
    gather_recent_headlines,
    classify_sentiment,
    _save_news_articles,
)


def web_news_node(state: Dict[str, Any]) -> Dict[str, Any]:
    ticker = state["ticker"]
    if is_etf(ticker):
        state["raw_headlines"] = []
        state["news_macro"] = _etf_sentiment(ticker)
    else:
        headlines, raw_news = gather_recent_headlines(ticker)
        state["raw_headlines"] = headlines
        sentiment_results = classify_sentiment([(ticker, headlines)])
        sentiment_result = (
            sentiment_results[0]
            if sentiment_results
            else {"summary": "No sentiment", "score": 0.0}
        )
        _save_news_articles(ticker, raw_news, sentiment_result["score"])
    return state
