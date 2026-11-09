import threading
from django.conf import settings
from langchain_chroma import Chroma
from .embedding_service import get_embedding_model

_vector_store = None
_lock = threading.Lock()


def get_vector_store():
    global _vector_store
    if _vector_store is None:
        with _lock:
            if _vector_store is None:
                embeddings = get_embedding_model()
                _vector_store = Chroma(
                    collection_name="paledoc_documents",
                    embedding_function=embeddings,
                    persist_directory=settings.CHROMA_DATA_DIR
                )
    return _vector_store
