import threading
from langchain_huggingface import HuggingFaceEmbeddings

_embedding_model = None
_lock = threading.Lock()


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        with _lock:
            if _embedding_model is None:
                _embedding_model = HuggingFaceEmbeddings(
                    model_name="sentence-transformers/all-MiniLM-L6-v2"
                )
    return _embedding_model
