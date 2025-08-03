from langgraph.graph import StateGraph, END
from langchain.chat_models import ChatOpenAI
from agents.intent import parse_intent
from agents.screener import get_hot_tickers
from agents.filter import quick_filter
from agents.optimise import optimise_portfolio
from agents.fx import convert_amount
from agents.synth import synthesise_proposal


# ─── state schema ────────────────────────────────────────────
def build_graph():
    sg = StateGraph()

    sg.add_node("parse", parse_intent)
    sg.add_node("screener", get_hot_tickers)
    sg.add_node("filter", quick_filter)
    sg.add_node("optimise", optimise_portfolio)
    sg.add_node("fx", convert_amount)
    sg.add_node("synth", synthesise_proposal)

    sg.set_entry_node("parse")

    sg.add_edge("parse", "screener")
    sg.add_edge("screener", "filter")
    sg.add_edge("filter", "optimise")
    sg.add_edge("optimise", "fx")
    sg.add_edge("fx", "synth")
    sg.add_edge("synth", END)

    return sg.compile()
