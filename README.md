# RedAlert DevOps Learning Project

Ongoing RedAlert learning project focused on backend development, Docker, and Kubernetes. Next phase: building CI/CD pipelines and improving deployment workflows.

## Current Focus

The project currently includes a Python backend built with FastAPI and MongoDB. It is being used as a hands-on learning project to improve backend, infrastructure, and deployment skills step by step.

## Tech Stack

- Python
- FastAPI
- MongoDB
- Uvicorn
- Vanilla JavaScript
- Leaflet

## Run Locally

### 1. Install backend dependencies

```bash
cd backend
python -m pip install -r requirements.txt
```

### 2. Make sure MongoDB is running

Default connection settings:

- `MONGO_URI=mongodb://127.0.0.1:27017`
- `MONGO_DB=red_alert`

### 3. Bootstrap the database

This creates the collections, indexes, and imports the current official datasets into MongoDB:

```bash
cd backend
python -m scripts.sync_mongo_data --drop-existing
```

Collections created:

- `alerts`
- `cities`
- `polygons`
- `dataset_meta`

### 4. Run the API

```bash
cd backend
python -m uvicorn app.main:app --reload
```

Then open `http://127.0.0.1:8000/docs`.

### 5. Run the frontend

```bash
cd frontend
python -m http.server 4173
```

Then open `http://127.0.0.1:4173`.

## API Endpoints

- `GET /api/alerts/today` returns how many alert records happened today in `Asia/Jerusalem` time.
- `GET /api/alerts/map` returns city markers with cumulative alert counts, coordinates, and last alert time.

## Frontend

The `frontend/` folder contains a static map-first dashboard for exploring the backend API.

It includes:

- a configurable backend URL field
- interactive Leaflet map markers sized by total alerts
- city spotlight and hotspot list interactions
- today's alert summary cards and kind breakdown
- unmapped area visibility for coverage gaps

## Notes

- The backend reads from MongoDB, and the bootstrap script fetches source data from the official Tzeva Adom APIs.
- When the latest stored alert is less than 60 seconds old, each API request first attempts a guarded refresh.
- That refresh is throttled with a short cooldown so bursts of traffic do not trigger repeated upstream syncs.
