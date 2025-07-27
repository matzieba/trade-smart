from trade_smart.utils import tools


def market_node(state):
    ticker = state["ticker"]
    state["last_px"] = tools.last_price(ticker)
    return state
