# Internal AI Advisory Assistant 

Production-ready RAG system designed for advisory firms. Allows consultants to query internal documents, generate summaries, and analyze risks using institutional knowledge.

## Features

- **RAG Pipeline**: Hybrid search (Vector + BM25) for high-recall retrieval.
- **Task Workflows**: Specialized modes for summaries, risk analysis, and drafting recommendations.
- **Structured Output**: Returns valid JSON for frontend integration.
- **RBAC**: Filters results based on user role (Analyst, Consultant, Partner).
- **Local-First**: Runs totally locally with Qdrant (or connects to cloud).

## Quick Start

### Prerequisites
- Python 3.10+
- OpenAI API Key

### Setup

1. **Clone & Install**
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure**
   ```bash
   cp .env.example .env
   # Add your OPENAI_API_KEY to .env
   ```

3. **Initialize Database**
   ```bash
   python scripts/init_db.py
   ```

4. **Add Data**
   Place your PDF/DOCX files in `data/raw/` and run:
   ```bash
   python scripts/ingest_documents.py
   ```

5. **Run Server**
   ```bash
   uvicorn app.main:app --reload
   ```

## Usage

Send a POST request to `/api/v1/query`:

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-key-change-me" \
  -H "X-User-Role: consultant" \
  -d '{
    "query": "Summarize the risk management framework",
    "task_type": "summarize_client"
  }'
```

## Architecture

- **Backend**: FastAPI
- **DB**: Qdrant (Vectors), SQLite (Feedback)
- **LLM**: OpenAI (configurable)
- **Monitoring**: Structured JSON logs
