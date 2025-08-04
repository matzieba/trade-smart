import logging
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field


from trade_smart.services.llm import get_llm

logger = logging.getLogger(__name__)


class Intent(BaseModel):
    amount: float
    currency: str
    horizon: int
    risk: str


def _model():
    return get_llm()


_parser = PydanticOutputParser(pydantic_object=Intent)

prompt = PromptTemplate(
    template="""
You are an assistant extracting structured info.

Text: "{text}"

{format_instructions}
""",
    input_variables=["text"],
    partial_variables={"format_instructions": _parser.get_format_instructions()},
)


def parse_intent(state):
    logger.info("Parsing intent...")
    text = (
        f"I want to invest {state['user_request']['amount']} {state['user_request']['currency']} "
        f"for {state['user_request']['horizon']} months with {state['user_request']['risk']} risk."
    )
    chain = prompt | _model() | _parser
    result: Intent = chain.invoke({"text": text})
    logger.info(f"Intent parsed: {result.dict()}")
    return {**state, **result.dict()}
