# ✈️ Airspace Intelligence

A real-time aviation tracking platform providing live updates and visualizations of aircraft positions worldwide.

## Overview
Airspace Intelligence aggregates ADS-B flight data and streams it to a modern, interactive web map. It leverages real-time WebSocket communication to ensure low-latency updates for flight tracking.

## Architecture
See our [Architecture Document](docs/architecture.md) for a detailed breakdown of the system design. 
Key components include a FastAPI backend for data ingestion, PostgreSQL/Redis for persistence and caching, and a Next.js frontend with MapLibre for visualization.

## Tech Stack

| Layer | Technologies |
|-------|--------------|
| **Frontend** | Next.js, React, MapLibre GL JS, Tailwind CSS |
| **Backend** | Python, FastAPI, WebSockets |
| **Infrastructure** | PostgreSQL, Redis, Docker, Docker Compose |

## Prerequisites
- Node.js 18+
- Python 3.11+
- Docker & Docker Compose

## Quick Start

```bash
# 1. Clone and enter the project
git clone <repo-url>
cd airspace-intelligence

# 2. Start PostgreSQL and Redis
cd infrastructure
docker compose up -d
cd ..

# 3. Start the backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 4. Start the frontend (in a new terminal)
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

## Development
- **Backend Tests**: Run `pytest` within the `backend/` directory.
- **Frontend Linting**: Run `npm run lint` within the `frontend/` directory.

## Environment Variables
Environment variables are managed through `.env` files. See `.env.example` in the root (and potentially within `backend`/`frontend` directories) for required configurations.

## Project Structure
```text
airspace-intelligence/
├── backend/           # FastAPI backend
├── docs/              # Documentation files
├── frontend/          # Next.js frontend
└── infrastructure/    # Docker Compose, init scripts
```

## License
MIT
