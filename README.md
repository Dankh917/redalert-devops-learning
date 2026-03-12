# RedAlert DevOps Learning Project

Hands-on RedAlert learning project focused on backend development, Docker, testing, and CI/CD automation.

## Current Status

The app is now containerized with Docker Compose:

- `mongo` service for MongoDB with a persistent named volume
- `backend` service for the FastAPI API
- `frontend` service for the static UI served by Nginx
- first backend tests added with `pytest`
- first GitHub Actions CI workflow added for push-based backend test runs

Current learning progress:

- Dockerized full app stack with Compose
- persistent MongoDB storage with a named volume
- frontend-to-backend container communication through Nginx proxying
- initial backend automated tests
- initial GitHub Actions CI workflow

## Tech Stack

- Python
- FastAPI
- MongoDB
- Uvicorn
- Vanilla JavaScript
- Leaflet
- Nginx
- Docker
- Docker Compose
- Pytest
- GitHub Actions

## Run With Docker Compose

### 1. Start the full stack

```bash
docker compose up --build
```

### 2. Open the app

- Frontend: `http://127.0.0.1:4173`
- Backend docs: `http://127.0.0.1:8000/docs`

### 3. Bootstrap the database on first setup

Run this once after the services are up to import the source datasets into MongoDB:

```bash
docker compose exec backend python -m scripts.sync_mongo_data --drop-existing
```

This creates and populates:

- `alerts`
- `cities`
- `polygons`
- `dataset_meta`

### 4. Stop the stack

```bash
docker compose down
```

The MongoDB data remains because it is stored in the named volume `mongo-data`.

## Run Locally Without Docker

### 1. Install backend dependencies

```bash
cd backend
python -m pip install -r requirements.txt
```

### 2. Make sure MongoDB is running

Default backend connection settings:

- `MONGO_URI=mongodb://127.0.0.1:27017`
- `MONGO_DB=red_alert`

### 3. Bootstrap the database

```bash
cd backend
python -m scripts.sync_mongo_data --drop-existing
```

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

## Testing

Install backend dev dependencies:

```bash
python -m pip install -r backend/requirements-dev.txt
```

Run backend tests:

```bash
python -m pytest backend/tests -q
```

Current test coverage includes:

- alert document generation
- polygon geometry generation

## CI

The repo now includes a first GitHub Actions workflow:

- workflow file: `.github/workflows/ci.yml`
- trigger: every `push`
- current job: install backend dev dependencies and run backend tests

This is the first CI step before adding image builds, stronger branch protection, and deployment workflows.

## API Endpoints

- `GET /api/alerts/today` returns how many alert records happened today in `Asia/Jerusalem` time.
- `GET /api/alerts/map` returns city markers with cumulative alert counts, coordinates, and last alert time.
- `GET /api/alerts/summary` returns either today's summary or a range-based summary with `from_date`.

## Frontend

The `frontend/` folder contains a static map-first dashboard for exploring the backend API.

It includes:

- interactive Leaflet map markers sized by total alerts
- city spotlight and hotspot list interactions
- today's alert summary cards and kind breakdown
- unmapped area visibility for coverage gaps
- a containerized Nginx frontend that proxies API requests to the backend service

## Notes

- The backend reads from MongoDB, and the bootstrap script fetches source data from the official Tzeva Adom APIs.
- When the latest stored alert is less than 60 seconds old, each API request first attempts a guarded refresh.
- That refresh is throttled with a short cooldown so bursts of traffic do not trigger repeated upstream syncs.
- Compose service names are used for internal container-to-container communication, for example `mongodb://mongo:27017` and backend proxying from the frontend container.
- Local development and containerized development are both supported, depending on what is being learned or changed.
