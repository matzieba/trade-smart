from trade_smart.analytics.portfolio_analyser import analyse


def pf_node(state):
    """
    Analyzes the portfolio and updates the state with the metrics.

    Args:
        state (dict): The current state of the graph.

    Returns:
        dict: The updated state with the portfolio metrics.
    """
    pf = state["portfolio"]
    metrics = analyse(pf)
    state["pf_metrics"] = metrics
    return state
