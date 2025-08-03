from yahooquery import Ticker
import pandas as pd


def quick_filter(state):
    symbols = state["candidates"]
    tk = Ticker(symbols, asynchronous=True)

    # Price filter
    price_df = tk.price
    pe_df = tk.key_stats

    whitelist = []
    for sym in symbols:
        try:
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
                whitelist.append(sym)
        except Exception:
            continue

    state["filtered"] = whitelist[:30]
    return state
