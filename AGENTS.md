# VoyageMind AI — Agent Instructions

## Project Structure
- `backend/` — FastAPI + CrewAI orchestration service.
- `frontend/` — React + TypeScript + Vite client.
- `backend/app/skills/` — CrewAI `SKILL.md` definitions.
- `frontend/SKILL.md` — Frontend development conventions.
- `architecture-mvp.md` — Current MVP architecture.
- `architecture.md` — Full enterprise architecture (future).

## Common Commands

### Backend (Python 3.12 required)
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Conventions
- Keep the backend/frontend separation clean.
- Mirror Pydantic schemas in `frontend/src/types.ts`.
- The MVP uses a synchronous `POST /plan` endpoint.
- External integrations (Serper, Amadeus, Booking, maps, E2B) are mocked with clear production hooks.
