import os
import threading
from langchain_ollama import ChatOllama

_llm = None
_lock = threading.Lock()


def get_llm():
    global _llm
    if _llm is None:
        with _lock:
            if _llm is None:
                base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
                _llm = ChatOllama(
                    model="qwen3.5:4b",
                    base_url=base_url,
                    temperature=0,
                )
    return _llm
