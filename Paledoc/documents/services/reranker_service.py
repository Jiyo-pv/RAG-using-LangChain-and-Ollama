"""
Cross-Encoder reranker using ms-marco-MiniLM-L-6-v2.
Singleton pattern — loads once per process.
"""
import logging
import threading
from typing import List, Tuple

from langchain_core.documents import Document

logger = logging.getLogger(__name__)

_reranker = None
_lock = threading.Lock()


def get_reranker():
    """Return the singleton CrossEncoder instance."""
    global _reranker
    if _reranker is None:
        with _lock:
            if _reranker is None:
                try:
                    from sentence_transformers import CrossEncoder
                    _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
                    logger.info("Cross-Encoder reranker loaded.")
                except Exception as exc:
                    logger.error("Failed to load reranker: %s", exc)
                    raise
    return _reranker


def rerank(
    question: str,
    candidates: List[Document],
    top_n: int = 3,
) -> List[Document]:
    """
    Rerank candidate documents using the Cross-Encoder.

    Returns top_n documents ordered by reranker score (highest first).
    Falls back to returning candidates[:top_n] if reranker fails.
    """
    if not candidates:
        return []

    try:
        reranker = get_reranker()
        pairs = [(question, doc.page_content) for doc in candidates]
        scores = reranker.predict(pairs)

        scored = list(zip(scores, candidates))
        scored.sort(key=lambda x: x[0], reverse=True)

        return [doc for _, doc in scored[:top_n]]

    except Exception as exc:
        logger.warning("Reranker failed, returning top candidates as-is: %s", exc)
        return candidates[:top_n]
