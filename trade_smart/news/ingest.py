import logging, os, requests
from datetime import datetime, timedelta
from typing import List
from sentence_transformers import SentenceTransformer
import chromadb

from trade_smart.agent_service.chroma import get_chroma
from trade_smart.agent_service.web_news import _search_urls
from trade_smart.models import NewsArticle

logger = logging.getLogger(__name__)

EMBED_MODEL = os.getenv("EMBED_MODEL", "all-mpnet-base-v2")
sbert = SentenceTransformer(EMBED_MODEL)

collection = get_chroma().get_or_create_collection("news")

NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")  # free dev tier
MAX_AGE_HRS = 350


def _fetch_headlines(ticker: str) -> List[dict]:
    """
    Very light wrapper around newsapi.org Everything endpoint.
    """
    if not NEWSAPI_KEY:
        return []
    url = (
        f"https://newsapi.org/v2/everything?"
        f"q={ticker}&language=en&sortBy=publishedAt&pageSize=20&apiKey={NEWSAPI_KEY}"
    )
    js = requests.get(url, timeout=10).json()
    return js.get("articles", [])


def ingest_for_ticker(ticker: str):
    articles = _search_urls(f"{ticker} stock news last 6 months", k=15)
    if not articles:
        return 0

    new_objs, embeds, metad = [], [], []
    horizon = datetime.utcnow() - timedelta(days=MAX_AGE_HRS)

    for art in articles:
        published = datetime.fromisoformat(art["publishedAt"].rstrip("Z"))
        if published < horizon:
            continue
        if NewsArticle.objects.filter(url=art["url"]).exists():
            continue  # dedupe

        head = art["title"] or art["description"][:120]
        emb = sbert.encode(head)

        new_objs.append(
            NewsArticle(
                ticker=ticker,
                headline=head,
                source=art["source"]["name"],
                url=art["url"],
                published_at=published,
            )
        )
        embeds.append(emb)
        metad.append({"ticker": ticker, "headline": head})

    if new_objs:
        NewsArticle.objects.bulk_create(new_objs)
        collection.add(
            ids=[obj.url for obj in new_objs],
            documents=[obj.headline for obj in new_objs],
            embeddings=embeds,
            metadatas=metad,
        )
    return len(new_objs)
