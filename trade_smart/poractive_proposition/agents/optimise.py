import logging
from yahooquery import Ticker
from pypfopt import EfficientFrontier, risk_models, expected_returns

logger = logging.getLogger(__name__)


def _build_frontier(mu, S, max_weight):
    """Utility helper so we don’t repeat the same two lines everywhere."""
    ef = EfficientFrontier(mu, S)
    ef.add_constraint(lambda w: w <= max_weight)
    return ef


def optimise_portfolio(state):
    symbols = state["filtered_tickers"]
    if not symbols:
        logger.warning("No symbols to optimise, skipping.")
        return {"optimised_portfolio": {}}

    logger.info("Optimising portfolio for %d symbols …", len(symbols))

    # -------------------- price matrix --------------------
    tk = Ticker(symbols)
    prices = (
        tk.history(period="1y")["close"].unstack(level=0).dropna(axis=1, thresh=200)
    )

    if prices.shape[1] < 2:  # not enough good columns
        logger.warning("Only %d valid symbols – abort optimisation.", prices.shape[1])
        return {"optimised_portfolio": {}}

    # -------------------- expected return & cov --------------------
    mu = expected_returns.mean_historical_return(prices)
    S = risk_models.sample_cov(prices)

    risk_level = state["intent"]["risk"]
    max_w = {"low": 0.10, "medium": 0.20, "high": 0.35}[risk_level]

    # ========== STEP 1: figure out minimum volatility ==========
    ef_min = _build_frontier(mu, S, max_w)
    ef_min.min_volatility()
    _, min_vol, _ = ef_min.portfolio_performance()  # we only need the vol number

    # ========== STEP 2: build the final portfolio ==============
    ef = _build_frontier(mu, S, max_w)

    if risk_level == "high":
        ef.max_sharpe()

    else:  # low / medium  → use efficient_risk with scaled target
        factor = 1.20 if risk_level == "low" else 1.50
        target_vol = min_vol * factor
        try:
            ef.efficient_risk(target_vol)
        except ValueError:
            # If target vol is infeasible fall back to the true min‐vol portfolio
            logger.warning(
                "Target volatility %.4f infeasible – using min_volatility", target_vol
            )
            ef.min_volatility()

    cleaned = ef.clean_weights()
    logger.info("Optimised weights: %s", cleaned)
    return {"optimised_portfolio": cleaned}
