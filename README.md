# Red Alert

This repo currently contains only the backend project, prepared for a future sibling `frontend/` folder.

## Install

```bash
cd backend
python -m pip install -r requirements.txt
```

## MongoDB

MongoDB Server should be running on `mongodb://127.0.0.1:27017`.

Default database name:

`red_alert`

Override it with `MONGO_URI` and `MONGO_DB` if needed.

## Bootstrap the database

This creates the collections, indexes, and imports the current official datasets into MongoDB directly:

```bash
cd backend
python -m scripts.sync_mongo_data --drop-existing
```

Collections created:

- `alerts`
- `cities`
- `polygons`
- `dataset_meta`

## Refresh alert history

This fetches from the official historical API and upserts into MongoDB directly:

```bash
cd backend
python -m scripts.update_tzevaadom_history
```

## Run the API

```bash
cd backend
python -m uvicorn app.main:app --reload
```

Then open `http://127.0.0.1:8000/docs`.

## Endpoints

- `GET /api/alerts/today` returns how many alert records happened today in `Asia/Jerusalem` time.
- `GET /api/alerts/map` returns city markers with cumulative alert counts, coordinates, and last alert time.

The backend reads from MongoDB, and the bootstrap/import scripts fetch the source data from the official Tzeva Adom APIs.

When the latest stored alert is less than 60 seconds old, each API request first attempts a guarded history refresh. That refresh is throttled with a short cooldown so bursts of client traffic do not trigger repeated upstream syncs.

## Layout

```text
backend/
  app/
  scripts/
  requirements.txt
README.md
```
