"""
BM25 keyword retrieval over a user's document corpus.

BM25 operates on a snapshot of text from ChromaDB for the given user/docs.
This is in-memory per request — no external indexing server needed.
"""
import logging
from typing import List, Optional

from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

from .vector_store import get_vector_store

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> List[str]:
    """Simple whitespace+lowercase tokenization for BM25."""
    return text.lower().split()


def retrieve_bm25(
    question: str,
    user_id: int,
    doc_ids: Optional[List[int]] = None,
    k: int = 10,
) -> List[Document]:
    """
    BM25 keyword retrieval over the user's corpus from ChromaDB.

    1. Fetches all chunks (up to 2000) belonging to this user/docs from ChromaDB.
    2. Builds an in-memory BM25 index on those chunks.
    3. Returns top-k by BM25 score.
    """
    vector_store = get_vector_store()
    collection = vector_store._collection

    # Build where filter
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
        results = collection.get(
            where=where_filter,
            include=["documents", "metadatas"],
            limit=2000,
        )
    except Exception as exc:
        logger.warning("BM25 corpus fetch failed: %s", exc)
        return []

    corpus_texts = results.get("documents", [])
    corpus_metas = results.get("metadatas", [])

    if not corpus_texts:
        return []

    tokenized_corpus = [_tokenize(t) for t in corpus_texts]
    bm25 = BM25Okapi(tokenized_corpus)

    tokenized_query = _tokenize(question)
    scores = bm25.get_scores(tokenized_query)

    # Pick top-k indices
    top_k_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]

    docs = []
    for idx in top_k_indices:
        if scores[idx] <= 0:
            continue
        docs.append(Document(
            page_content=corpus_texts[idx],
            metadata=corpus_metas[idx],
        ))

    return docs
