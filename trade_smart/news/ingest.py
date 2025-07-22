"""
Vector-store & DB ingestion for the newest articles produced by
news_sources.fetch_articles_for_ticker().
Keeps the original SBERT + Chroma logic.
"""

from __future__ import annotations

import logging, os, datetime as dt
from typing import List

from sentence_transformers import SentenceTransformer

from trade_smart.agent_service.news_sources import fetch_articles_for_ticker
from trade_smart.agent_service.chroma import get_chroma
from trade_smart.models import NewsArticle

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
EMBED_MODEL = os.getenv("EMBED_MODEL", "all-mpnet-base-v2")
sbert = SentenceTransformer(EMBED_MODEL)

collection = get_chroma().get_or_create_collection("news")
MAX_AGE_DAYS = int(os.getenv("NEWS_MAX_AGE_DAYS", 5))
UTC = dt.timezone.utc


# --------------------------------------------------------------------------- #
def ingest_for_ticker(ticker: str) -> int:
    """
    1. Pull newest articles from free sources.
    2. Store in Postgres (NewsArticle) if not seen.
    3. Embed + push to Chroma vector-store.
    Returns number of *new* docs persisted.
    """
    articles = fetch_articles_for_ticker(ticker)
    if not articles:
        return 0

    horizon = dt.datetime.now(UTC) - dt.timedelta(days=MAX_AGE_DAYS)
    new_objs, embeds, metad = [], [], []

    for art in articles:
        pub_ts = art["publishedAt"]
        if not pub_ts or pub_ts < horizon:
            continue

        if NewsArticle.objects.filter(url=art["url"]).exists():
            continue  # de-dup DB

        headline = art["title"] or art["url"]
        emb = sbert.encode(headline)

        new_objs.append(
            NewsArticle(
                ticker=ticker,
                headline=headline,
                source=art["source"] or "",
                url=art["url"],
                published_at=pub_ts.replace(tzinfo=None),  # Django naive UTC
            )
        )
        embeds.append(emb)
        metad.append({"ticker": ticker, "headline": headline})

    if new_objs:
        NewsArticle.objects.bulk_create(new_objs)

        collection.add(
            ids=[obj.url for obj in new_objs],
            documents=[obj.headline for obj in new_objs],
            embeddings=embeds,
            metadatas=metad,
        )

    return len(new_objs)
