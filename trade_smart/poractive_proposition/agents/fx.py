import logging
import requests

logger = logging.getLogger(__name__)


def convert_amount(state):
    logger.info("Converting amount...")
    amount_pln = state["amount"]
    fx_url = f"https://api.exchangerate.host/latest?base={state['currency']}"
    logger.info(f"Fetching FX rates from {fx_url}")
    rates = requests.get(fx_url, timeout=10).json()["rates"]

    portfolio = []
    for sym, w in state["weights"].items():
        if w <= 0:
            continue
        tk_cur = "USD"  # simple approx
        cash = amount_pln * w * rates.get(tk_cur, 1)
        price = 1  # placeholder, will replace in synth
        qty = round(cash / price, 4)
        logger.debug(f"Symbol: {sym}, Weight: {w}, Cash: {cash}, Qty: {qty}")
        portfolio.append(
            {"ticker": sym, "qty_est": qty, "weight_pct": round(w * 100, 2)}
        )

    state["portfolio"] = portfolio
    logger.info(f"Amount converted. Portfolio: {portfolio}")
    return state
