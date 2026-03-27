# Estech ContentOS

A lightweight SaaS-style web dashboard to run AI content workflows for businesses.

## What version 1 includes
- Brand setup module (stored in SQLite)
- Dynamic prompt engine from brand context
- Content generator (Mistral API)
- Saved content library

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export MISTRAL_API_KEY=your_key_here
python app.py
```

Open: `http://localhost:5000`

## Environment variables
- `MISTRAL_API_KEY` (required for live AI generation)
- `MISTRAL_MODEL` (optional, default: `open-mistral-7b`)
- `CONTENTOS_DB` (optional SQLite file path)

## Routes
- `GET /` dashboard
- `POST /brand` save business profile
- `POST /generate` generate + save content
- `GET /health` health check
