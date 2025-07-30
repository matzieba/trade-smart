from collections import defaultdict
from trade_smart.analytics.ta_engine import calculate_indicators


def tech_node(state):
    """
    Calculates a history of technical indicators for a given ticker and updates the state.

    Args:
        state (dict): The current state of the graph.

    Returns:
        dict: The updated state with a history of technical indicators.
    """
    ticker = state["ticker"]
    indicators = calculate_indicators(ticker)
    if not indicators:
        state["tech"] = {}
        return state

    # Group indicators by name
    grouped_indicators = defaultdict(list)
    for ind in indicators:
        grouped_indicators[ind.name].append((ind.date, ind.value))

    # Sort by date and keep the last 5 values for each indicator
    indicator_history = {}
    for name, values in grouped_indicators.items():
        sorted_values = sorted(values, key=lambda x: x[0])
        latest_values = [float(val[1]) for val in sorted_values[-5:]]
        indicator_history[name] = latest_values

    state["tech"] = indicator_history
    return state
