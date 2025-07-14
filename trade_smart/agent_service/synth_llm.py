import json

from langchain.schema import SystemMessage, HumanMessage, AIMessage

from trade_smart.agent_service.llm import get_llm

llm = get_llm()

SYS = SystemMessage(
    content=(
        "You are WiseTrade, a disciplined investment assistant. "
        "You never guess wildly, you reason step-by-step, and you output ONLY valid JSON."
    )
)

FMT = """
PORTFOLIO METRICS:
{pf}

TECHNICALS:
{tech}

MACRO / NEWS:
{news}

Current Price = {price}

Return a JSON with fields:
action: BUY | SELL | HOLD | REBAL
confidence: float 0-1
rationale: short explanation (≤ 50 words)
"""


def synth_llm_node(state):
    prompt = FMT.format(
        pf=state.get("pf_metrics"),
        tech=state.get("tech"),
        news=state.get("news_macro"),
        price=state.get("last_px"),
    )
    resp = llm.predict_messages([SYS, HumanMessage(content=prompt)])
    try:
        js = json.loads(resp.content if hasattr(resp, "content") else resp)
        state["advice"] = {
            "action": js["action"],
            "confidence": js["confidence"],
            "rationale": js["rationale"],
        }
    except Exception:
        state["advice"] = {
            "action": "HOLD",
            "confidence": 0.3,
            "rationale": "Could not parse LLM response, default to HOLD.",
        }
    return state
