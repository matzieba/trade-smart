import os

from langchain_community.chat_models import ChatOllama


def get_llm():
    # if os.getenv("OPENAI_API_KEY"):
    #     # cheap gpt-3.5 is fine for classification & synthesis
    #     return ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0.2)
    # else fall back to local Llama-2 via Ollama
    return ChatOllama(model="llama2:13b", temperature=0.2)
