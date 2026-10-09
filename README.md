# VoyageMind AI

Versioned, evidence-aware travel planning workspace with a legacy CrewAI planner and a production-oriented v2 API.

## Quick Start

1. Configure environment:
   ```bash
   cp backend/.env.example backend/.env
   # Edit backend/.env with your API keys
   ```

2. Start the backend (requires Python 3.12):
   ```bash
   cd backend
   python3.12 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```

3. Start the frontend:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

4. Open http://localhost:5173 and submit a travel request.

## Architecture

The repository currently contains two paths:

- The legacy CrewAI planner builds conversational itineraries.
- The v2 workspace stores immutable trip versions, validates typed edits, preserves provider evidence, and keeps unknown or unavailable facts explicit.

The v2 provider boundary uses typed Search, Weather, Flight, and Hotel adapters. Development fixtures are visibly marked `MOCK`; production configuration never falls back to them. Serper and Open-Meteo have live adapters. Flight and hotel inventory use configured aggregator endpoints and remain explicitly unavailable when credentials are absent.

The legacy planner works as follows:

1. **Input Parser** extracts structured fields from free-text prompts.
2. **Itinerary Architect** (supervisor) builds a day-by-day route skeleton.
3. **Parallel Serper searches** fetch real flight, hotel, and attraction data per skeleton segment.
4. **Specialist crews run in parallel**:
   - Travel Planner — outbound/return and local transit
   - Stay Planner — accommodation per base region
   - Sightseeing Planner — activities and dining per day
5. **Itinerary Assembler** merges and refines everything into the final itinerary.

## API Endpoints

- `GET /health` — health check
- `POST /parse-prompt` — extract travel fields + missing list
- `POST /plan` — generate a complete itinerary
- `GET /plan/{session_id}/pdf` — download the itinerary as PDF
- `POST /v2/trips` / `GET /v2/trips/{id}` — create and read immutable v2 trip snapshots
- `POST /v2/trips/{id}/proposals` — preview a typed change
- `POST /v2/trips/{id}/proposals/{proposal_id}/commit` — commit a validated proposal
- `GET /v2/trips/{id}/provider-data` — read version-pinned provider evidence and alternatives
- `POST /v2/trips/{id}/provider-data/refresh` — run explicitly configured provider requests

## Tech Stack

- **FastAPI** backend
- **CrewAI** multi-agent orchestration
- **React + TypeScript + Vite** frontend
- **Serper** for live web search and **Open-Meteo** for supported forecasts
- Configurable live flight and hotel aggregator adapters
- Explicit development fixtures that cannot be selected in production
