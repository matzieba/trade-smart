import logging

from trade_smart.poractive_proposition.utils.hot_tickers import get_hot_tickers

logger = logging.getLogger(__name__)


def screener_agent(state: dict) -> dict:
    logger.info("Getting hot tickers...")
    state["candidates"] = get_hot_tickers(limit=100)
    logger.info(f"Found {len(state['candidates'])} hot tickers.")
    return state
