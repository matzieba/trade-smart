import logging

from langchain.prompts import ChatPromptTemplate
import os, datetime

from trade_smart.services.llm import get_llm

logger = logging.getLogger(__name__)

tmpl = """You are a professional investment assistant.
Date: {date}

Given this portfolio draft:
{draft}

User parameters:
amount: {amount} {currency}
horizon: {horizon} months
risk: {risk}

1. For every ticker write:
   • recommended quantity
   • expected 1y return range
   • one-sentence rationale
2. Return JSON list with keys:
   ticker, qty, weight_pct, confidence, rationale

If you think fewer than 3 assets suffice, say so. """


def synthesise_proposal(state):
    logger.info("Synthesising proposal...")
    llm = get_llm()
    prompt = ChatPromptTemplate.from_template(tmpl)
    msg = prompt.format(
        date=datetime.date.today(),
        draft=state["portfolio"],
        **{k: state[k] for k in ("amount", "currency", "horizon", "risk")},
    )
    logger.debug(f"LLM prompt: {msg}")
    resp = llm.invoke(msg).content
    logger.debug(f"LLM response: {resp}")
    # Assume valid JSON is returned
    import json, textwrap

    proposal = json.loads(resp)
    logger.info(f"Proposal synthesised: {proposal}")
    return {
        "portfolio": proposal,
        "message_markdown": textwrap.dedent(
            f"""
        ## Your Proactive Proposal  

        ```json
        {json.dumps(proposal, indent=2)}
        ```
        _Disclaimer: Generated automatically. Not financial advice._
        """
        ),
    }
