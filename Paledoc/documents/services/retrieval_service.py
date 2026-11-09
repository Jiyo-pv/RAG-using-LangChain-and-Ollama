"""
Retrieval service — semantic search with user+document filters.
"""
import logging
from typing import List, Optional

from langchain_core.documents import Document

from .vector_store import get_vector_store

logger = logging.getLogger(__name__)


def retrieve_semantic(
    question: str,
    user_id: int,
    doc_ids: Optional[List[int]] = None,
    k: int = 10,
) -> List[Document]:
    """
    Semantic similarity search filtered by user_id and optionally doc_ids.

    Args:
        question: The user's question.
        user_id: The authenticated user's ID — NEVER skip this.
        doc_ids: If supplied, restrict to these document IDs only.
        k: Number of results to fetch.
    """
    vector_store = get_vector_store()

    # Build ChromaDB where-filter
    if doc_ids:
        where_filter = {
            "$and": [
                {"user_id": {"$eq": str(user_id)}},
                {"doc_id": {"$in": [str(d) for d in doc_ids]}},
            ]
        }
    else:
        where_filter = {"user_id": {"$eq": str(user_id)}}

    try:
        results = vector_store.similarity_search(
            question,
            k=k,
            filter=where_filter,
        )
    except Exception as exc:
        logger.warning("Semantic search failed: %s", exc)
        results = []

    return results


def retrieve_documents(question: str) -> List[Document]:
    """Legacy wrapper — no user filter. Only used by old unguarded code paths."""
    vector_store = get_vector_store()
    return vector_store.similarity_search(question, k=3)
