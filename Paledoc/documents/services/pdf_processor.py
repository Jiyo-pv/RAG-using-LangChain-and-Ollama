"""
PDF processing service.

Responsibilities:
- Load PDF with PyMuPDF
- Split into chunks
- Inject per-chunk metadata: doc_id, user_id, filename, page, chunk_index
- Generate deterministic, unique vector IDs
- Check if document is already indexed before adding
- Delete all vectors for a document
"""

import hashlib
import logging
from pathlib import Path

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .vector_store import get_vector_store

logger = logging.getLogger(__name__)


def _make_chunk_id(doc_id: int, page: int, chunk_index: int) -> str:
    """Create a deterministic, unique vector ID for a chunk."""
    raw = f"doc:{doc_id}:page:{page}:chunk:{chunk_index}"
    return hashlib.sha256(raw.encode()).hexdigest()


def is_document_indexed(doc_id: int) -> bool:
    """Return True if the document already has vectors in ChromaDB."""
    vector_store = get_vector_store()
    collection = vector_store._collection
    results = collection.get(where={"doc_id": str(doc_id)}, limit=1)
    return len(results.get("ids", [])) > 0


def process_and_index_document(document) -> int:
    """
    Load, split, enrich and index a Document model instance.
    Returns the number of chunks stored.
    Raises on failure.
    """
    file_path = document.file.path
    doc_id = document.id
    user_id = document.user_id
    original_filename = document.original_filename or Path(file_path).name

    if is_document_indexed(doc_id):
        logger.info("Document %s already indexed — skipping.", doc_id)
        # Count and return existing chunks
        vector_store = get_vector_store()
        existing = vector_store._collection.get(where={"doc_id": str(doc_id)})
        return len(existing.get("ids", []))

    loader = PyMuPDFLoader(file_path)
    raw_docs = loader.load()

    if not raw_docs:
        raise ValueError(f"PDF produced no pages: {file_path}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
    )
    chunks = splitter.split_documents(raw_docs)

    if not chunks:
        raise ValueError(f"PDF produced no text chunks: {file_path}")

    # Enrich metadata and assign deterministic IDs
    ids = []
    for idx, chunk in enumerate(chunks):
        page = chunk.metadata.get("page", 0)
        chunk.metadata.update({
            "doc_id": str(doc_id),
            "user_id": str(user_id),
            "filename": original_filename,
            "page": page,
            "chunk_index": idx,
        })
        ids.append(_make_chunk_id(doc_id, page, idx))

    vector_store = get_vector_store()
    vector_store.add_documents(chunks, ids=ids)

    logger.info("Indexed %d chunks for document %d.", len(chunks), doc_id)
    return len(chunks)


def delete_document_vectors(doc_id: int) -> None:
    """Remove all ChromaDB vectors belonging to this document."""
    vector_store = get_vector_store()
    collection = vector_store._collection
    results = collection.get(where={"doc_id": str(doc_id)})
    ids_to_delete = results.get("ids", [])
    if ids_to_delete:
        collection.delete(ids=ids_to_delete)
        logger.info("Deleted %d vectors for document %d.", len(ids_to_delete), doc_id)
    else:
        logger.info("No vectors found for document %d.", doc_id)


# Keep backward-compatible names used in older views (Phase 1 views still call these)
def process_pdf(file_path: str):
    """Legacy: Load and split only. No metadata injection. Use process_and_index_document instead."""
    loader = PyMuPDFLoader(file_path)
    raw_docs = loader.load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    return splitter.split_documents(raw_docs)


def store_chunks(chunks):
    """Legacy: Add chunks to vector store without metadata. Use process_and_index_document instead."""
    vector_store = get_vector_store()
    vector_store.add_documents(chunks)
    return vector_store
