import os, time, logging, chromadb

_client = None
logger = logging.getLogger(__name__)


def get_chroma():
    global _client
    if _client is not None:
        return _client

    host = os.getenv("CHROMA_HOST", "127.0.0.1")
    port = int(os.getenv("CHROMA_PORT", 8002))

    for attempt in range(6):  # retry for 30 s
        try:
            _client = chromadb.HttpClient(host=host, port=port)
            return _client
        except Exception as exc:
            logger.info("Chroma not ready (%s) – retry %s/5", exc, attempt)
            time.sleep(5)

    raise RuntimeError(f"Could not connect to Chroma at {host}:{port}")
