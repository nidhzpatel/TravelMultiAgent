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

This MVP follows the design in `architecture-mvp.md`:

- **5-agent sequential CrewAI pipeline**: Input Parser → Travel Planner → Stay Planner → Sightseeing Planner → Itinerary Assembler
- **FastAPI** backend with `POST /plan` and `GET /health`
- **React + TypeScript + Vite** frontend
- Mocked external APIs (Serper, Amadeus, Booking, maps, E2B) with production hooks

For the full enterprise design, see `architecture.md`.
