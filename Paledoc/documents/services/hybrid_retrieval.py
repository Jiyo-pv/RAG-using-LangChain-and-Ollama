"""
Hybrid retrieval pipeline:
  Semantic (top 10) + BM25 (top 10) → RRF fusion → Cross-Encoder rerank → top 3

Reciprocal Rank Fusion (RRF):
  score(d) = Σ 1 / (k + rank_i(d))   where k=60 (standard)
"""
import logging
from typing import List, Optional

from langchain_core.documents import Document

from .bm25_service import retrieve_bm25
from .reranker_service import rerank
from .retrieval_service import retrieve_semantic

logger = logging.getLogger(__name__)

RRF_K = 60  # Standard RRF constant


def _rrf_fuse(
    ranked_lists: List[List[Document]],
    k: int = RRF_K,
) -> List[Document]:
    """
    Reciprocal Rank Fusion over multiple ranked lists.
    Documents are identified by their page_content (deduplication key).
    """
    scores: dict = {}
    doc_map: dict = {}

    for ranked in ranked_lists:
        for rank, doc in enumerate(ranked, start=1):
            key = doc.page_content[:200]  # first 200 chars as dedup key
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            doc_map[key] = doc

    sorted_keys = sorted(scores, key=lambda x: scores[x], reverse=True)
    return [doc_map[k] for k in sorted_keys]


def hybrid_retrieve(
    question: str,
    user_id: int,
    doc_ids: Optional[List[int]] = None,
    semantic_k: int = 10,
    bm25_k: int = 10,
    rerank_top_n: int = 3,
) -> List[Document]:
    """
    Full hybrid retrieval pipeline.

    Args:
        question: User question.
        user_id: Authenticated user ID (server-side filter).
        doc_ids: Optional list of document IDs to restrict search to.
        semantic_k: Semantic results to fetch.
        bm25_k: BM25 results to fetch.
        rerank_top_n: Final results after reranking.

    Returns:
        List of top-rerank_top_n Documents.
    """
    logger.debug("hybrid_retrieve: user=%s, doc_ids=%s, q=%r", user_id, doc_ids, question[:60])

    semantic_results = retrieve_semantic(question, user_id=user_id, doc_ids=doc_ids, k=semantic_k)
    bm25_results = retrieve_bm25(question, user_id=user_id, doc_ids=doc_ids, k=bm25_k)

    logger.debug("Semantic: %d, BM25: %d", len(semantic_results), len(bm25_results))

    if not semantic_results and not bm25_results:
        return []

    fused = _rrf_fuse([semantic_results, bm25_results])
    final = rerank(question, fused, top_n=rerank_top_n)

    logger.debug("After rerank: %d chunks returned.", len(final))
    return final
