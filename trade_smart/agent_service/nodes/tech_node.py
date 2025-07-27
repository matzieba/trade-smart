from trade_smart.analytics.ta_engine import calculate_indicators


def tech_node(state):
    """
    Calculates technical indicators for a given ticker and updates the state.

    Args:
        state (dict): The current state of the graph.

    Returns:
        dict: The updated state with the technical indicators.
    """
    ticker = state["ticker"]
    ind = calculate_indicators(ticker)  # returns list[TechnicalIndicator]
    # convert to dict latest values
    latest = {obj.name: float(obj.value) for obj in ind[-6:]} if ind else {}
    state["tech"] = latest
    return state
