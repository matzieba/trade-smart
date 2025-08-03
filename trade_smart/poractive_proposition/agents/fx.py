import requests


def convert_amount(state):
    amount_pln = state["amount"]
    fx_url = f"https://api.exchangerate.host/latest?base={state['currency']}"
    rates = requests.get(fx_url, timeout=10).json()["rates"]

    portfolio = []
    for sym, w in state["weights"].items():
        if w <= 0:
            continue
        tk_cur = "USD"  # simple approx
        cash = amount_pln * w * rates.get(tk_cur, 1)
        price = 1  # placeholder, will replace in synth
        qty = round(cash / price, 4)
        portfolio.append(
            {"ticker": sym, "qty_est": qty, "weight_pct": round(w * 100, 2)}
        )

    state["portfolio"] = portfolio
    return state
