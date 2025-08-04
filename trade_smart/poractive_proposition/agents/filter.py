import logging
from yahooquery import Ticker
import pandas as pd

logger = logging.getLogger(__name__)


def quick_filter(state):
    symbols = state["candidates"]
    logger.info(f"Starting quick filter for {len(symbols)} candidates...")
    tk = Ticker(symbols, asynchronous=True)

    # Price filter
    price_df = tk.price
    pe_df = tk.key_stats

    whitelist = []
    for sym in symbols:
        try:
            logger.debug(f"Processing symbol: {sym}")
            price = price_df.loc[sym]["regularMarketPrice"]
            sma50 = tk.history(sym, period="3mo")["close"].rolling(50).mean().iloc[-1]
            rsi = (
                pd.Series(tk.history(sym, period="3mo")["close"])
                .pct_change()
                .rolling(14)
                .apply(
                    lambda x: 100 - (100 / (1 + (x[x > 0].sum() / -x[x < 0].sum())))
                )[-1]
            )

            pe = pe_df.loc[sym]["forwardPE"]
            cap = price_df.loc[sym]["marketCap"]

            if price > sma50 and rsi < 70 and (pe or 0) < 60 and (cap or 0) > 5e8:
                logger.info(f"Symbol {sym} passed filter.")
                whitelist.append(sym)
        except Exception as e:
            logger.warning(f"Could not process symbol {sym}: {e}")
            continue

    state["filtered"] = whitelist[:30]
    logger.info(f"Filtering complete. Found {len(state['filtered'])} matching tickers.")
    return state
