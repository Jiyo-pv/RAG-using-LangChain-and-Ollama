"""
RAG service — orchestrates retrieval and LLM generation.

Supports:
- Hybrid retrieval (semantic + BM25 + RRF + Cross-Encoder reranker)
- User isolation via server-side filters
- Conversation history
- Graceful fallback if Ollama is unavailable
"""
import logging
from typing import List, Optional, Tuple

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate

from .hybrid_retrieval import hybrid_retrieve
from .llm_service import get_llm

logger = logging.getLogger(__name__)

RAG_PROMPT = ChatPromptTemplate.from_template("""
You are Paledoc, an AI document assistant. Answer the question using ONLY the provided context.

Rules:
1. Do not invent or assume any information not present in the context.
2. If the answer is not available in the context, say: "The information is not available in the selected documents."
3. Always cite the source filename and page number for each fact you state.
4. Keep answers clear, structured and concise.

CONTEXT:
{context}

CONVERSATION HISTORY:
{history}

QUESTION:
{question}

ANSWER:
""")


def _build_context(docs: List[Document]) -> str:
    """Format retrieved documents into a context string for the prompt."""
    parts = []
    for i, doc in enumerate(docs, start=1):
        filename = doc.metadata.get("filename") or doc.metadata.get("source", "Unknown")
        page = int(doc.metadata.get("page", 0)) + 1
        parts.append(
            f"[Source {i}] File: {filename} | Page: {page}\n{doc.page_content}"
        )
    return "\n\n---\n\n".join(parts)


def ask_paledoc(
    question: str,
    user_id: Optional[int] = None,
    doc_ids: Optional[List[int]] = None,
    history: Optional[List[dict]] = None,
) -> Tuple[str, List[Document]]:
    """
    Main RAG entry point.

    Args:
        question: The user's question.
        user_id: Authenticated user's ID. Required for filtered retrieval.
        doc_ids: Optional list of document IDs to restrict search to.
        history: Optional list of {'role': 'user'|'assistant', 'content': str} dicts.

    Returns:
        (answer_text, source_documents)
    """
    if user_id is None:
        # Legacy / unauthenticated fallback — no user filter
        from .retrieval_service import retrieve_documents
        source_docs = retrieve_documents(question)
    else:
        source_docs = hybrid_retrieve(
            question,
            user_id=user_id,
            doc_ids=doc_ids,
        )

    context = _build_context(source_docs)

    # Format conversation history
    history_text = ""
    if history:
        for turn in history[-6:]:  # last 3 turns (user+assistant pairs)
            role = turn.get("role", "user").capitalize()
            content = turn.get("content", "")
            history_text += f"{role}: {content}\n"

    try:
        llm = get_llm()
        chain = RAG_PROMPT | llm
        response = chain.invoke({
            "context": context if context else "No relevant documents found.",
            "history": history_text or "None",
            "question": question,
        })
        return response.content, source_docs

    except Exception as exc:
        logger.error("LLM generation failed: %s", exc)
        error_msg = (
            "⚠️ Could not connect to the AI service. "
            "Please ensure Ollama is running and the qwen3.5:4b model is available.\n\n"
            f"Technical detail: {exc}"
        )
        return error_msg, source_docs
