from typing import TypedDict, List, Dict, Any

from langgraph.graph import StateGraph, END

from trade_smart.poractive_proposition.agents.filter import quick_filter
from trade_smart.poractive_proposition.agents.fx import convert_amount
from trade_smart.poractive_proposition.agents.intent import parse_intent
from trade_smart.poractive_proposition.agents.optimise import optimise_portfolio
from trade_smart.poractive_proposition.agents.screener import (
    get_hot_tickers,
    screener_agent,
)
from trade_smart.poractive_proposition.agents.synth import synthesise_proposal


# ─── state schema ────────────────────────────────────────────
class ProactivePropositionState(TypedDict):
    user_request: Dict[str, Any]
    intent: Dict[str, Any]
    hot_tickers: List[str]
    filtered_tickers: List[str]
    optimised_portfolio: Dict[str, Any]
    converted_amount: float
    proposal: str


def build_graph():
    sg = StateGraph(ProactivePropositionState)

    sg.add_node("parse", parse_intent)
    sg.add_node("screener", screener_agent)
    sg.add_node("filter", quick_filter)
    sg.add_node("optimise", optimise_portfolio)
    sg.add_node("fx", convert_amount)
    sg.add_node("synth", synthesise_proposal)

    sg.set_entry_point("parse")

    sg.add_edge("parse", "screener")
    sg.add_edge("screener", "filter")
    sg.add_edge("filter", "optimise")
    sg.add_edge("optimise", "fx")
    sg.add_edge("fx", "synth")
    sg.add_edge("synth", END)

    return sg.compile()
