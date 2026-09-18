# SATNO Bale Market Intelligence — Flat MVP v0.2

Mobile-friendly flat repository layout.

## Run
```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Health check: `/health`

Import demo data:
```bash
python import_json.py sample_messages.json
```

The Bale adapter is intentionally a boundary for an authorized Bale source/API. Never commit passwords, OTPs or session secrets.
