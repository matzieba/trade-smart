from typing import TypedDict, Dict, Any

from langchain_core.runnables import Runnable
from langgraph.graph import StateGraph, END

from trade_smart.agent_service.nodes.news_macro_node import web_news_node
from trade_smart.agent_service.nodes.market_node import market_node
from trade_smart.agent_service.nodes.pf_node import pf_node
from trade_smart.agent_service.nodes.tech_node import tech_node
from trade_smart.agent_service.nodes.synth_llm import synth_llm_node
from trade_smart.models import Portfolio


class AdviceState(TypedDict, total=False):
    ticker: str
    portfolio: Portfolio
    last_px: float
    tech: Dict[str, float]
    pf_metrics: Dict[str, Any]
    news_macro: Dict[str, Any]
    advice: Dict[str, Any]


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
