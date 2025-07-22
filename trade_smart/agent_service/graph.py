from typing import TypedDict, Dict, Any

from langchain_core.runnables import Runnable
from langgraph.graph import StateGraph, END

from trade_smart.agent_service import tools
from trade_smart.agent_service.news_macro import web_news_node
from trade_smart.agent_service.synth_llm import synth_llm_node

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


# --- Node-4 Macro node -------------------------------------------------------
def macro_node(state):
    state["macro"] = tools.macro_sentiment()
    return state


# --- Node-5 Synthesizer w/ RULES --------------------------------------------
def rule_engine(state):
    tech = state.get("tech", {})
    macro = state.get("macro")
    close = state.get("last_px")
    weights = state["pf_metrics"].get("weights", {})

    action, conf, why = "HOLD", 0.5, []

    # MA crossover
    if close and tech.get("SMA_50") and tech.get("SMA_200"):
        if close > tech["SMA_50"] > tech["SMA_200"]:
            action, conf = "BUY", 0.7
            why.append("bullish golden-cross")
        elif close < tech["SMA_50"] < tech["SMA_200"]:
            action, conf = "SELL", 0.7
            why.append("bearish death-cross")

    # RSI extremes
    if tech.get("RSI_14"):
        if tech["RSI_14"] > 70:
            action, conf = "SELL", max(conf, 0.6)
            why.append("RSI overbought")
        elif tech["RSI_14"] < 35:
            action, conf = "BUY", max(conf, 0.6)
            why.append("RSI oversold")

    # Macro override
    if macro == "RISK_OFF" and action == "BUY":
        action, conf = "HOLD", 0.4
        why.append("macro risk-off override")

    state["advice"] = {
        "action": action,
        "confidence": round(conf, 3),
        "rationale": "; ".join(why) or "No strong signal.",
    }
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
