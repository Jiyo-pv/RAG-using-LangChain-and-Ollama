import threading
from langchain_ollama import ChatOllama

_llm = None
_lock = threading.Lock()


def get_llm():
    global _llm
    if _llm is None:
        with _lock:
            if _llm is None:
                _llm = ChatOllama(
                    model="qwen3.5:4b",
                    temperature=0
                )
    return _llm
