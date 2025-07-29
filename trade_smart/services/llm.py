"""
llm_factory.py
Utility to obtain a LangChain ChatOpenAI instance that talks to Groq Cloud.

Required env-vars
-----------------
GROQ_API_KEY   : your Groq Cloud key (https://console.groq.com)
GROQ_MODEL     : optional; overrides the default model
GROQ_API_BASE  : optional; defaults to "https://api.groq.com/openai/v1"
"""

import os
from langchain_openai import ChatOpenAI
import settings
from tenacity import retry, stop_after_attempt, wait_exponential


@retry(wait=wait_exponential(multiplier=1, min=4, max=10), stop=stop_after_attempt(5))
def get_llm(
    model: str | None = None,
    temperature: float = 0.0,
    timeout: int | float | None = None,
) -> ChatOpenAI:
    return ChatOpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=settings.GROQ_API_KEY,
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        temperature=temperature,
        timeout=timeout,
    )
