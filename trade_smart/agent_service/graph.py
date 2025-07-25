from typing import TypedDict, Dict, Any

from langchain_core.runnables import Runnable
from langgraph.graph import StateGraph, END

from trade_smart.agent_service import tools
from trade_smart.agent_service.news_macro import web_news_node
from trade_smart.agent_service.synth_llm import synth_llm_node
from trade_smart.services.email_service import send_advice_email

from trade_smart.analytics.portfolio_analyser import analyse
from trade_smart.analytics.ta_engine import calculate_indicators
from trade_smart.models import Portfolio


class AdviceState(TypedDict, total=False):
    ticker: str
    portfolio: Portfolio
    last_px: float
    tech: Dict[str, float]
    pf_metrics: Dict[str, Any]
    news_macro: Dict[str, Any]
    advice: Dict[str, Any]


# --- Node-1 Market node ------------------------------------------------------
def market_node(state):
    ticker = state["ticker"]
    state["last_px"] = tools.last_price(ticker)
    return state


# --- Node-2 Technical node ---------------------------------------------------
def tech_node(state):
    ticker = state["ticker"]
    ind = calculate_indicators(ticker)  # returns list[TechnicalIndicator]
    # convert to dict latest values
    latest = {obj.name: float(obj.value) for obj in ind[-6:]} if ind else {}
    state["tech"] = latest
    return state


# --- Node-3 Portfolio node ---------------------------------------------------
def pf_node(state):
    pf = state["portfolio"]
    metrics = analyse(pf)
    state["pf_metrics"] = metrics
    return state


# -------- Assemble DAG -------------------------------------------------------
def build_graph() -> Runnable:
    g = StateGraph(AdviceState)
    g.add_node("market", market_node)
    g.add_node("tech", tech_node)
    g.add_node("pf", pf_node)
    g.add_node("news_macro", web_news_node)
    g.add_node("synth", synth_llm_node)

    g.set_entry_point("market")
    g.add_edge("market", "tech")
    g.add_edge("tech", "pf")
    g.add_edge("pf", "news_macro")
    g.add_edge("news_macro", "synth")
    g.add_edge("synth", END)
    return g.compile()
