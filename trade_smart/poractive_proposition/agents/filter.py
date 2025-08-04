import logging
from yahooquery import Ticker
import pandas as pd

logger = logging.getLogger(__name__)


def quick_filter(state):
    symbols = state["hot_tickers"]
    if not symbols:
        logger.info("No symbols to filter.")
        return {"filtered_tickers": []}

    logger.info(f"Starting quick filter for {len(symbols)} candidates...")
    tk = Ticker(symbols, asynchronous=True)

    # Fetch data in bulk
    price_df = tk.price
    pe_df = tk.key_stats
    history_df = tk.history(period="3mo")

    whitelist = []
    for sym in symbols:
        try:
            logger.debug(f"Processing symbol: {sym}")

            # Safely get data from dictionaries
            price_data = price_df.get(sym, {})
            if not isinstance(price_data, dict):
                logger.warning(f"Price data for {sym} is not a dict, skipping.")
                continue

            price = price_data.get("regularMarketPrice")
            cap = price_data.get("marketCap")

            pe_data = pe_df.get(sym, {})
            pe = pe_data.get("forwardPE") if isinstance(pe_data, dict) else None

            # Check for history data
            if history_df.empty or sym not in history_df.index.get_level_values(
                "symbol"
            ):
                logger.warning(f"No history data for {sym}, skipping.")
                continue

            sym_history = history_df.loc[sym]
            sma50 = sym_history["close"].rolling(50).mean().iloc[-1]

            # RSI calculation
            rsi = (
                sym_history["close"]
                .pct_change()
                .rolling(14)
                .apply(
                    lambda x: (
                        100 - (100 / (1 + (x[x > 0].sum() / -x[x < 0].sum())))
                        if -x[x < 0].sum() != 0
                        else 100
                    ),
                    raw=True,
                )
                .iloc[-1]
            )

            if price is not None and sma50 is not None and rsi is not None:
                if price > sma50 and rsi < 70 and (pe or 0) < 60 and (cap or 0) > 5e8:
                    logger.info(f"Symbol {sym} passed filter.")
                    whitelist.append(sym)

        except Exception as e:
            logger.warning(f"Could not process symbol {sym}: {e}")
            continue

    logger.info(f"Filtering complete. Found {len(whitelist)} matching tickers.")
    return {"filtered_tickers": whitelist[:30]}
