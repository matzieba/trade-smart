import logging
from yahooquery import Ticker
from pypfopt import EfficientFrontier, risk_models, expected_returns

logger = logging.getLogger(__name__)


def optimise_portfolio(state):
    symbols = state["filtered"][:20]  # keep runtime sane
    logger.info(f"Optimising portfolio for {len(symbols)} symbols...")

    tk = Ticker(symbols)
    prices = (
        tk.history(period="1y")["close"].unstack(level=0).dropna(axis=1, thresh=200)
    )

    mu = expected_returns.mean_historical_return(prices)
    S = risk_models.sample_cov(prices)

    ef = EfficientFrontier(mu, S)

    risk = state["risk"]
    logger.info(f"Using risk profile: {risk}")
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
    logger.info(f"Portfolio optimised with weights: {weights}")
    return state
