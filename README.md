# Paledoc

A local document intelligence web application built with Django that lets you upload, search, analyze, and query PDF documents using local AI models through Ollama.

Everything runs on your machine — documents and embeddings are stored locally, and queries are answered without sending data to third-party cloud APIs.

---

## What It Does

- **PDF Ingestion & Indexing:** Uploads PDFs, checks for valid PDF headers, splits text into overlapping chunks using PyMuPDF, and generates 384-dimensional embeddings into a local ChromaDB collection.
- **Hybrid Retrieval (RAG):**
  - Runs dense semantic search (ChromaDB) and keyword search (BM25) in parallel.
  - Merges both result sets using Reciprocal Rank Fusion (RRF).
  - Reranks the candidates using a Cross-Encoder (`ms-marco-MiniLM-L-6-v2`) to pass the top 3 chunks to the LLM.
- **Source Citations:** Answers include the source document name, page number, and relevant text excerpt.
- **Persistent Chat:** Saves conversations and message histories per user, with the ability to limit questions to specific selected PDFs.
- **Document Summarization:** Generates executive, detailed, section-wise, or key-findings summaries.
- **Paper Analysis:** Breaks down research papers into problem statement, methodology, dataset, algorithms, findings, limitations, and future work.
- **Document Comparison:** Compares 2 or more PDFs side-by-side to highlight common themes, differing methods, and findings.
- **Reference Generator:** Extracts bibliographic information from the document to generate APA 7th and IEEE format citations.
- **Word Export:** Exports generated summaries, comparisons, and analysis reports as formatted `.docx` files.
- **User Authentication & Isolation:** Built on Django's auth system. Users can only search, view, and delete their own files and chats; vector queries are strictly filtered by user ID on the server.

---

## Retrieval Pipeline

```text
User Question
    ├── 1. Semantic Search (ChromaDB) ───────► Top 10 chunks
    └── 2. Keyword Search (BM25) ─────────────► Top 10 chunks
                     │
                     ▼
             3. RRF Fusion (k=60)
                     │
                     ▼
         4. Cross-Encoder Reranker ───────────► Top 3 chunks
                     │
                     ▼
         5. Qwen 3.5 4B (via Ollama)
                     │
                     ▼
              Answer + Citations
```

---

## Tech Stack

- **Backend:** Python, Django 6
- **Database:** SQLite (default for local dev) / PostgreSQL 16 (via Docker)
- **Vector Database:** ChromaDB (vector embeddings)
- **Local LLM:** Ollama running `qwen3.5:4b`
- **Embeddings:** `sentence-transformers/all-MiniLM-L6-v2`
- **Reranker:** `cross-encoder/ms-marco-MiniLM-L-6-v2`
- **Lexical Search:** `rank-bm25` (BM25Okapi)
- **PDF Extraction:** PyMuPDF (`pymupdf`)
- **Word Export:** `python-docx`
- **Containerization:** Docker & Docker Compose
- **Frontend:** HTML5, Bootstrap 5, Bootstrap Icons, vanilla JavaScript

Both the embedding model and the cross-encoder are loaded as process-level singletons so they only load into memory once when the Django server starts.

---

## Getting Started

### 1. Prerequisites

- Python 3.11+ (or Docker Desktop)
- [Ollama](https://ollama.ai/) installed and running
- Pull the local model:
  ```bash
  ollama pull qwen3.5:4b
  ```

---

### Option A: Run with Docker & PostgreSQL (Recommended)

Docker sets up both the Django web application and a **PostgreSQL 16** database container automatically with persistent storage:

1. Start Ollama on your host machine:
   ```bash
   ollama run qwen3.5:4b
   ```
2. In your terminal, go to the project folder and launch:
   ```powershell
   cd Paledoc
   docker compose up --build
   ```
3. Open [http://localhost:8000](http://localhost:8000) in your browser.

Useful Docker commands:
- Run in background: `docker compose up -d`
- View logs: `docker compose logs -f`
- Stop containers: `docker compose down`

---

### Option B: Run Locally (with SQLite)

If you prefer to run directly without Docker:

```powershell
cd Paledoc

# 1. Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run database migrations
python manage.py migrate

# 4. Start the development server
python manage.py runserver
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

---

## Running Tests

To run the full automated test suite:

```powershell
cd Paledoc
python manage.py test documents
```

Or inside Docker:
```powershell
docker compose exec web python manage.py test documents
```

The test suite covers:
- Registration, login, logout, and password validation
- PDF upload validation (file extensions, corrupt files, magic byte verification)
- Server-side user isolation (ensuring users cannot view, delete, or retrieve another user's documents or chats)
- RRF rank fusion and candidate deduplication
- Chat persistence and missing-information fallback responses

---

## Directory Layout

```text
Paledoc/
├── accounts/               # User authentication (register, login, logout)
├── config/                 # Django settings and root URLs
├── documents/
│   ├── models.py           # Document, Conversation, Message, AnalysisReport
│   ├── views.py            # Dashboard, document manager, chat, analysis views
│   ├── urls.py             # Route definitions
│   ├── forms.py            # PDF upload & validation form
│   ├── services/
│   │   ├── embedding_service.py   # Singleton embedding loader
│   │   ├── vector_store.py        # ChromaDB client wrapper
│   │   ├── pdf_processor.py       # PDF chunking, indexing, and vector deletion
│   │   ├── bm25_service.py        # In-memory BM25 retrieval
│   │   ├── reranker_service.py    # Cross-Encoder reranker singleton
│   │   ├── hybrid_retrieval.py    # BM25 + ChromaDB + RRF + Reranker pipeline
│   │   ├── llm_service.py         # ChatOllama client singleton
│   │   ├── rag_service.py         # Main RAG question-answering logic
│   │   ├── intelligence_service.py# Summarization, paper analysis, comparison
│   │   └── export_service.py      # .docx Word document generator
│   └── tests.py            # Automated test suite
├── templates/
│   ├── base.html           # Sidebar layout template
│   ├── accounts/           # Login and register pages
│   └── documents/          # Dashboard, chat, upload, analysis templates
├── Dockerfile              # Container image specification
├── docker-compose.yml      # Orchestrates Django + PostgreSQL
├── .dockerignore           # Excludes local files from image build
├── manage.py
├── requirements.txt
└── README.md
```
