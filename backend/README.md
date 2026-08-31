# VoyageMind MVP Backend

FastAPI + CrewAI orchestration for the MVP travel planner.

## Setup

Requires Python 3.12 (Python 3.14 is not supported by the locked dependency set).

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file:

```env
OPENAI_API_KEY=sk-...
SERPER_API_KEY=...
```

## Run

```bash
uvicorn app.main:app --reload
```

## Endpoints

- `GET /health` — health check
- `POST /plan` — generate a complete itinerary (transit + stay + sightseeing)

## Architecture

The MVP uses a 5-agent sequential CrewAI pipeline:

1. **Input Parser** — extracts structured parameters from the request
2. **Travel Planner** — plans flights, trains, buses, metro, cabs, walking
3. **Stay Planner** — recommends hotels, hostels, homestays
4. **Sightseeing Planner** — curates attractions, activities, dining
5. **Itinerary Assembler** — merges plans, computes costs, enforces budget

All external APIs are mocked with production hooks.
