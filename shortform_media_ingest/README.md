# Shortform Media Ingest — Places to Visit

Minimal backend to ingest short-form video metadata (URL, caption, hashtags, transcript), perform a placeholder NLP/classification step to detect place name and category, store results in a local SQLite DB, and expose results via a FastAPI API and tiny dashboard.

Quickstart (PowerShell):

```powershell
cd social_media_organizer\shortform_media_ingest
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Endpoints:
- `POST /ingest` — JSON body with `url` (required), optional `caption`, `hashtags`, `transcript`. Returns stored place object.
- `GET /locations` — list stored places
- `GET /health` — health check

Dashboard: open `app/static/dashboard.html` in a browser (or serve it) to see a simple list and map placeholder.

This is a scaffold — replace `app/classifier.py` with a real NLP model for production.
