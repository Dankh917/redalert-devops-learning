# RedAlert DevOps Learning Project

Hands-on RedAlert learning project focused on backend development, Docker, testing, and CI/CD automation.

## Current Status

The app is now containerized with Docker Compose:

- `mongo` service for MongoDB with a persistent named volume
- `backend` service for the FastAPI API
- `frontend` service for the static UI served by Nginx
- first backend tests added with `pytest`
- GitHub Actions CI workflow for pushes and pull requests
- Compose-based smoke test in CI for the full stack
- tag-based release workflow with GitHub Releases

Current learning progress:

- Dockerized full app stack with Compose
- persistent MongoDB storage with a named volume
- frontend-to-backend container communication through Nginx proxying
- initial backend automated tests
- CI on `push` and `pull_request`
- Compose smoke test that starts the full stack in GitHub Actions
- release workflow triggered by version tags like `v0.1.0`
- branch protection on `main` requiring a pull request plus passing `backend-tests` and `compose-smoke`
- release workflow prepared to publish versioned backend and frontend images to GitHub Container Registry (`ghcr.io`)
- manual deployment verified on an Ubuntu Server VM using Docker, Compose, GHCR image pulls, SSH, and bridged VirtualBox networking
- automatic deployment enabled for trusted release tags, promoting released container images onto the Ubuntu VM
- manual redeploy workflow added for rollback to any previously published release tag

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

The repo now includes a GitHub Actions CI workflow:

- workflow file: `.github/workflows/ci.yml`
- triggers:
  - every `push`
  - every `pull_request`
- current jobs:
  - `backend-tests`: install backend dev dependencies and run backend tests
  - `compose-smoke`: start the full stack with `docker compose`, bootstrap Mongo data, and call a backend API endpoint

This means CI now checks both code correctness and whether the containerized app can actually start and respond inside GitHub Actions.

## Releases

The repo also includes a release workflow:

- workflow file: `.github/workflows/release.yml`
- trigger: every pushed Git tag matching `v*`, for example `v0.1.0`
- current job:
  - start the full stack with Docker Compose
  - bootstrap Mongo data
  - verify the backend API responds
  - log in to GitHub Container Registry and push versioned backend/frontend images
  - create a GitHub Release entry for the tag
  - deploy the released version onto the Ubuntu VM using the VM deployment Compose file

This makes version tags part of the learning flow, connecting Git versioning with automated release validation.

## Manual VM Deployment

A deployment target was set up on an Ubuntu Server VM running locally in VirtualBox.

High-level flow:

- install Docker and Docker Compose on the Ubuntu VM
- log in to GitHub Container Registry from the VM
- create a deployment `docker-compose.yml` that uses released images from `ghcr.io`
- pull the images and start the stack with `docker compose up -d`
- bootstrap Mongo data from the backend container
- verify backend and frontend responses from the VM
- switch VirtualBox networking from NAT to bridged mode so the VM receives its own LAN IP
- access the deployed frontend from the Windows host through the VM IP

The VM now acts as the deployment target for the project and is reachable on the local network like a separate Linux server.

Useful commands used during the first deployment:

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2
sudo usermod -aG docker $USER
docker login ghcr.io -u <github-username>
mkdir -p ~/redalert-deploy
cd ~/redalert-deploy
docker compose pull
docker compose up -d
docker compose exec backend python -m scripts.sync_mongo_data --drop-existing
curl http://127.0.0.1:8000/api/alerts/today
curl -I http://<vm-lan-ip>:4173
```

## CD

The project now includes a first CD path:

- trusted release tags trigger the release workflow
- the release workflow builds and publishes versioned backend/frontend images to GitHub Container Registry
- after the release job succeeds, the same workflow deploys that released version onto the Ubuntu VM
- the VM deployment uses a deployment-specific Docker Compose file that pulls the tagged images from `ghcr.io`
- a separate manual redeploy workflow can redeploy an older published tag as a rollback path

This gives the project an end-to-end flow from code changes to validated release artifacts to deployed application updates on the Linux VM.


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

