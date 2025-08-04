import logging
from trade_smart.utils.tools import get_hot_tickers

logger = logging.getLogger(__name__)


def screener_agent(state: dict) -> dict:
    logger.info("Getting hot tickers...")
    state["candidates"] = get_hot_tickers(limit=4)
    logger.info(f"Found {len(state['candidates'])} hot tickers.")
    return state
