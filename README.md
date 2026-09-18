# SATNO Bale Market Intelligence — MVP

MVP for collecting, normalizing, classifying, searching and reviewing market messages exported/received from Bale.

## What this MVP does
- FastAPI web app
- SQLite storage
- Import messages from JSON
- Rule-based Persian market classification:
  - supplier / seller
  - buyer / demand
  - stock / availability
  - inquiry / project
- Extract common solar brands, price-like values, quantities, power ratings, phone numbers and Iranian provinces/cities
- Search/filter API and a lightweight RTL dashboard
- Prepared adapter boundary for a future authorized Bale connector

## Important
This starter intentionally does **not** ask you to paste Bale passwords or session secrets into source code. Put credentials only in environment variables when an authorized Bale API/connector is configured.

## Quick start
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open `/` for the dashboard and `/docs` for API docs.

## Import sample/real JSON
Expected array:
```json
[
  {
    "external_id": "123",
    "chat_name": "بازار خورشیدی",
    "sender_name": "فروشنده",
    "text": "موجودی پنل Trina 720W ...",
    "sent_at": "2026-09-18T10:00:00"
  }
]
```

Run:
```bash
python scripts/import_json.py data/sample_messages.json
```

## Next production steps
1. Connect an authorized Bale message source/API.
2. Replace/augment rule classification with a Persian NLP/LLM classifier.
3. Add authentication and roles.
4. Add lead scoring, deduplication, alerts and daily digests.
5. Deploy with PostgreSQL for multi-user production use.
