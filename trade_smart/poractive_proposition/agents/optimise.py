from yahooquery import Ticker
from pypfopt import EfficientFrontier, risk_models, expected_returns


def optimise_portfolio(state):
    symbols = state["filtered"][:20]  # keep runtime sane

    tk = Ticker(symbols)
    prices = (
        tk.history(period="1y")["close"].unstack(level=0).dropna(axis=1, thresh=200)
    )

    mu = expected_returns.mean_historical_return(prices)
    S = risk_models.sample_cov(prices)

    ef = EfficientFrontier(mu, S)

    risk = state["risk"]
    max_w = {"low": 0.10, "medium": 0.20, "high": 0.35}[risk]
    ef.add_constraint(lambda w: w <= max_w)

    if risk == "low":
        ef.efficient_risk(target_volatility=0.05)
    elif risk == "medium":
        ef.efficient_risk(target_volatility=0.10)
    else:
        ef.max_sharpe()

    weights = ef.clean_weights()
    state["weights"] = weights
    return state
