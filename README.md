# VoyageMind AI

Deep-Agentic Autonomous Travel Planning System — MVP.

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

This MVP follows the design in `architecture-mvp.md`. It is a **hierarchical / parallel multi-agent travel planner** built with CrewAI and FastAPI:

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

## Tech Stack

- **FastAPI** backend
- **CrewAI** multi-agent orchestration
- **React + TypeScript + Vite** frontend
- **Serper** for live web search (flights, hotels, attractions)
- Mocked external APIs (Amadeus, Booking, maps, E2B) with production hooks

For the full enterprise design, see `architecture.md`.
