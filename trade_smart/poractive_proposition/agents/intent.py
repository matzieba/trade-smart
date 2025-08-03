from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from langchain.chat_models import ChatOpenAI
import os


class Intent(BaseModel):
    amount: float
    currency: str
    horizon: int
    risk: str


def _model():
    return ChatOpenAI(
        model_name=os.getenv("INTENT_MODEL", "gpt-3.5-turbo"), temperature=0
    )


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
    text = (
        f"I want to invest {state['amount']} {state['currency']} "
        f"for {state['horizon']} months with {state['risk']} risk."
    )
    chain = prompt | _model() | _parser
    result: Intent = chain.invoke({"text": text})
    return {**state, **result.dict()}
