import json, textwrap, datetime
from typing import List
from pydantic import BaseModel, Field, RootModel
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import ChatPromptTemplate
from trade_smart.services.llm import get_llm


class Asset(BaseModel):
    ticker: str
    cash_usd: float = Field(..., gt=0)
    weight_pct: float = Field(..., ge=0, le=100)
    confidence: float = Field(..., ge=0, le=1)
    ticker_rationale: str = Field(
        description="One sentence (≤30 words) explaining why the ticker was picked e.g. 'Solid cash-flow, undervalued vs. peers, bullish price"
    )


class Proposal(RootModel[List[Asset]]):
    pass


parser = PydanticOutputParser(pydantic_object=Proposal)

PROMPT_TMPL = ChatPromptTemplate.from_template(
    """
You are a professional investment assistant.
Return ONLY valid JSON that matches the schema. {format_instructions}

Date: {date}
Draft: {draft}
User:
  amount   : {amount} {currency}
  horizon  : {horizon} months
  risk     : {risk}
  currency : {currency}
"""
)


def synthesise_proposal(state: dict) -> dict:
    llm = get_llm()
    prompt = PROMPT_TMPL.format(
        format_instructions=parser.get_format_instructions(),
        date=datetime.date.today(),
        draft=state["optimised_portfolio"],
        amount=state["intent"]["amount"],
        currency=state["intent"]["currency"],
        horizon=state["intent"]["horizon"],
        risk=state["intent"]["risk"],
    )

    llm_resp = llm.invoke(prompt)
    proposal: Proposal = parser.parse(llm_resp.content)

    # ---- convert to plain python before json.dumps ----------------------
    proposal_list = [a.model_dump() for a in proposal.root]
    proposal_json = json.dumps(proposal_list, indent=2)

    return {
        "proposal": proposal_list,
        "message_markdown": textwrap.dedent(
            f"""
            ## Your Proactive Proposal  

            ```json
            {proposal_json}
            ```
            _Disclaimer: Generated automatically. Not financial advice._
        """
        ),
    }
