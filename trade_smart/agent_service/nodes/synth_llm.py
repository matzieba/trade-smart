import json

from langchain.schema import SystemMessage, HumanMessage, AIMessage

from trade_smart.services.llm import get_llm

llm = get_llm()


SYS = SystemMessage(
    content=(
        "You are WiseTrade – a disciplined, risk-aware investment assistant.\n\n"
        "Decision hierarchy you MUST follow:\n"
        "  1. PORTFOLIO METRICS (position size, target weight, realised P/L, "
        "     user risk score).  Action MUST respect the user’s risk profile; "
        "     e.g. never increase an overweight position.\n"
        "  2. TECHNICALS (RSI, MACD, SMA/EMA crossover, Bollinger Band, etc.) "
        "     – these determine timing.  Ignore technicals only if missing.\n"
        "  3. MACRO / NEWS sentiment acts as a final filter; lower confidence "
        "     when macro contradicts the trade idea.\n\n"
        "Rules:\n"
        "• Combine all three sources logically; if signals conflict, prefer HOLD.\n"
        "• Never invent data; when something is missing, down-weight confidence.\n"
        "• Output ONLY a minified JSON object with exactly these keys:\n"
        '      {"action": "BUY|SELL|HOLD|REBAL", '
        '       "confidence": 0.0, '
        '       "rationale": "≤50 words"}\n'
        "• confidence must be between 0.0 and 1.0 and represent the strength / "
        "  agreement of the signals.\n"
        "• You must reason internally but expose ONLY the JSON in the final answer."
    )
)
FMT = """
PORTFOLIO METRICS (risk first, weights second):
{pf}

TECHNICAL INDICATORS:
{tech}

MACRO / NEWS SENTIMENT:
{news}

Current Price = {price}

Generate advice strictly per the JSON schema in the system instructions.
"""


def synth_llm_node(state):
    prompt = FMT.format(
        pf=json.dumps(state.get("pf_metrics"), indent=2),
        tech=json.dumps(state.get("tech"), indent=2),
        news=json.dumps(state.get("news_macro"), indent=2),
        price=state.get("last_px"),
    )
    resp = llm.invoke(
        [SYS, HumanMessage(content=prompt)], response_format={"type": "json_object"}
    )
    try:
        js = json.loads(resp.content if hasattr(resp, "content") else resp)
        state["advice"] = {
            "action": js["action"],
            "confidence": js["confidence"],
            "rationale": js["rationale"],
        }
    except Exception as e:
        state["advice"] = {
            "action": "HOLD",
            "confidence": 0.3,
            "rationale": "Could not parse LLM response, default to HOLD.",
        }
    return state
