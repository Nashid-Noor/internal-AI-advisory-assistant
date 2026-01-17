# Quick Setup

## Install
```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Config
Copy `.env.example` to `.env` and set `OPENAI_API_KEY`.

## Init Local DB
```bash
python scripts/init_db.py --reset
```

## Run
```bash
uvicorn app.main:app --reload
```

## Test
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-key-change-me" \
  -d '{"query": "Summarize the risk management playbook"}'
```
