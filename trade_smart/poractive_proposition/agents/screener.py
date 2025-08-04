import logging

from trade_smart.poractive_proposition.utils.hot_tickers import get_hot_tickers

logger = logging.getLogger(__name__)


def screener_agent(state: dict) -> dict:
    logger.info("Getting hot tickers...")
    hot_tickers = get_hot_tickers(limit=100)
    logger.info(f"Found {len(hot_tickers)} hot tickers.")
    return {"hot_tickers": hot_tickers}
