import os

from langchain_ollama import ChatOllama


def get_llm(model: str | None = None, temperature: float = 0.0):
    return ChatOllama(
        base_url=os.getenv("OLLAMA_BASE_URL"),
        model=model or os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
    )
