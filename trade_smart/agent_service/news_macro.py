from __future__ import annotations

import json
import os
from typing import Dict, Any, List
import numpy as np, datetime as dt

import chromadb

from trade_smart.agent_service.chroma import get_chroma
from trade_smart.agent_service.llm import get_llm

llm = get_llm()

collection = get_chroma().get_or_create_collection("news")

PROMPT = """\
You are a financial news analyst. Summarise the following headlines in one \
sentence and output a sentiment score between -1 (very negative) and 1 (very positive) \
from the perspective of someone holding the equity.

Return JSON exactly like
{{
 "summary": "...",
 "score": 0.25
}}
HEADLINES:
{headlines}
"""


def news_macro_node(state: Dict[str, Any]) -> Dict[str, Any]:
    ticker = state["ticker"]
    # ① pull embeddings within last 48h
    docs = collection.query(
        query_texts=[ticker],
        n_results=10,
        where={"ticker": ticker},
        where_document={"$contains": ""},
    )
    headlines: List[str] = docs["documents"][0] if docs["documents"] else []

    if not headlines:
        state["news_macro"] = {"score": 0.0, "summary": "No recent coverage"}
        return state

    joined = "\n".join(f"- {h}" for h in headlines[:10])
    resp = llm.predict(PROMPT.format(headlines=joined))
    # expect JSON, guard against bad format
    try:
        js = json.loads(resp)
        score = float(js["score"])
        summary = js["summary"]
    except Exception:
        score, summary = 0.0, "LLM parse error"

    state["news_macro"] = {"score": score, "summary": summary}
    return state
