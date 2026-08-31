# VoyageMind AI — MVP Travel Planner Architecture

## 1. Goal

Build a **minimal viable travel planner** that takes a user’s natural-language request plus explicit constraints and returns a complete, day-by-day travel plan covering:

- **How to get there and move around** — flights, trains, buses, local transport, cabs
- **Where to stay** — hotels, hostels, homestays, Airbnb-style options
- **What to do** — sightseeing, attractions, activities, dining
- **Cost and timing** — estimated expenses and time slots per day

This is the first runnable version. It favors clarity and end-to-end coverage over multi-source price war, real-time rebooking, or heavy guardrails.

---

## 2. System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                 FastAPI Gateway (Backend)                           │
│  POST /parse-prompt  →  Extracted fields + missing list             │
│  POST /plan          →  Hierarchical CrewAI Pipeline                │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────┐
│                  VoyageMind MVP Crew                                │
│                                                                     │
│  ┌─────────────────┐                                                │
│  │ Input Parser    │  Extracts destination, origin (required),      │
│  │ Agent           │  dates, travelers, budget, interests, style    │
│  └────────┬────────┘                                                │
│           │                                                         │
│  ┌────────▼────────────┐                                            │
│  │ Itinerary Architect │  Builds day-by-day skeleton: region/base   │
│  │ Agent               │  per day, transit legs, activity themes    │
│  └────────┬────────────┘                                            │
│           │                                                         │
│  ┌────────▼─────────────────────────────────────────────────────┐   │
│  │ Controlled Tool Orchestration (in main.py)                   │   │
│  │  • FlightSearchTool (Serper) for outbound / return legs      │   │
│  │  • HotelSearchTool (Serper) per base region                  │   │
│  │  • AttractionSearchTool (Serper) per day/region              │   │
│  └────────┬─────────────────────────────────────────────────────┘   │
│           │                                                         │
│  ┌────────▼────────────────────────────────────────────────────┐    │
│  │ Specialist crews run in parallel with skeleton + search     │    │
│  │ context injected into their prompts:                        │    │
│  │  • Travel Planner Agent  → transit JSON                     │    │
│  │  • Stay Planner Agent    → stays JSON                       │    │
│  │  • Sightseeing Planner Agent → day-by-day activities JSON   │    │
│  └────────┬────────────────────────────────────────────────────┘    │
│           │                                                         │
│  ┌────────▼─────────────┐                                           │
│  │ Itinerary Assembler  │  Merges outputs, adds meals, region,     │
│  │ (main.py)            │  inclusions/exclusions, cost totals      │
│  └───────────────────────┘                                           │
└─────────────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────┐
│                     Tools Layer                                     │
│  • Web Search (Serper) — real flight/hotel/attraction names         │
│  • Distance Clustering Tool — groups locations by proximity         │
│  • Budget Calculator Tool — sums costs + contingency                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. User Input

The user can submit either a free-text query or a structured form. The MVP accepts both.

### Structured Request

```python
class TravelPlanRequest(BaseModel):
    destination: str
    origin: str                          # required
    start_date: date
    end_date: date
    travelers: int = 1
    total_budget_usd: float
    interests: list[str] = []            # e.g., temples, beaches, museums, food
    travel_style: str = "balanced"       # optional: budget | balanced | luxury
    cover_nearby: bool = True            # auto-include nearby places if days allow
    dietary_notes: str | None = None
    mobility_notes: str | None = None    # e.g., wheelchair access, no long walks
    free_text: str | None = None         # extra natural-language context
```

### Free-Text Example

> "Plan a 4-day trip to Tokyo from Osaka for 2 adults starting March 10. Budget is $3,000. We love tech, street food, historic temples, and easy walking routes."

---

## 4. Agent Breakdown

### Agent 1 — Input Parser

**Responsibility:** Convert messy user input into a clean, validated planning brief.

**Tasks:**
- Extract destination, origin (required), dates, travelers, budget, interests, style
- Detect whether flights are needed
- Normalize interests into standard tags
- Detect explicit "only X / no nearby" intent
- Flag missing critical fields

**Output:** extracted fields + `missing` list

---

### Agent 2 — Itinerary Architect

**Responsibility:** Build the day-by-day route skeleton before any detailed searches run.

**Tasks:**
- Decide region/base for each day
- Keep hotel changes minimal (1–2 bases per week)
- Allocate nearby regions/attractions when `cover_nearby=True` and trip length allows
- Define arrival and return transit legs

**Output:** `DraftItinerary`

```python
class DraftItineraryDay(BaseModel):
    day_number: int
    date: str
    region: str                         # e.g., "North Goa", "Old Manali"
    base_location: str                  # hotel location for the night
    transit_from: str | None
    transit_to: str | None
    theme: str                          # e.g., "beach day", "heritage walk"
    activity_focus: list[str]

class DraftItinerary(BaseModel):
    days: list[DraftItineraryDay]
    transit_legs: list[TransitLeg]
    hotel_regions: list[str]
```

---

### Agent 3 — Travel Planner

**Responsibility:** Plan all movement from origin to destination and within the destination.

**Tasks:**
- Use the skeleton's first/last base for outbound/return legs
- Pick real provider names from Serper search context
- Plan daily local transport (cab, bus, metro, walk)
- Estimate transit time and cost per leg

**Output:** list of `TransitLeg`

```python
class TransitLeg(BaseModel):
    day_number: int | None = None
    from_location: str
    to_location: str
    mode: str                     # flight | train | bus | metro | cab | walk
    provider: str
    estimated_cost_usd: float
    duration_minutes: int
    notes: str
```

---

### Agent 4 — Stay Planner

**Responsibility:** Recommend where the traveler sleeps each night.

**Tasks:**
- Use the skeleton's `base_location` per night
- Recommend real hotel names from Serper search context
- Match `travel_style`:
  - budget → hostels / budget hotels
  - balanced → mid-range hotels / B&Bs
  - luxury → 4–5 star hotels / boutique stays
- Include estimated nightly cost and booking notes

**Output:** list of `StayOption`

```python
class StayOption(BaseModel):
    night_number: int
    hotel_name: str
    location: str
    room_type: str
    estimated_cost_usd: float
    why_this_choice: str
    booking_notes: str
```

---

### Agent 5 — Sightseeing Planner

**Responsibility:** Build a list of attractions, activities, and dining for each day.

**Tasks:**
- Use the skeleton's day theme/region and real attraction search context
- Cluster activities geographically to minimize backtracking
- Respect opening hours and meal buffers
- Suggest breakfast, lunch, dinner options near clusters

**Output:** list of day objects with `ActivityItem`

```python
class ActivityItem(BaseModel):
    time_slot: str
    activity_name: str
    location: str
    category: str              # sightseeing | food | shopping | rest | transit
    estimated_cost_usd: float
    notes: str
```

---

## 5. Data Models

```python
class ParsedTravelRequest(BaseModel):
    destination: str
    origin: str
    start_date: date
    end_date: date
    travelers: int
    total_budget_usd: float
    interests: list[str]
    travel_style: str
    flights_needed: bool
    number_of_days: int
    extra_notes: str | None

class MasterTravelItinerary(BaseModel):
    destination: str
    origin: str | None
    total_budget_usd: float
    actual_calculated_cost_usd: float
    currency: str = "USD"
    travelers: int
    days: list[DayItinerary]
    transit_summary: str
    stay_summary: str
    sightseeing_summary: str
    trip_scope: str | None
    inclusions: list[str]
    exclusions: list[str]
    notes: list[str]

class DayItinerary(BaseModel):
    day_number: int
    date: str
    theme: str
    region: str | None
    meals_included: list[str]
    activities: list[ActivityItem]
    transit_legs: list[TransitLeg]
    stay: StayOption | None
    daily_transit_cost_usd: float
    daily_activity_cost_usd: float
    daily_stay_cost_usd: float
    total_daily_cost_usd: float
```

---

## 6. Flow Pipeline

1. **User submits free-text prompt** → `POST /parse-prompt`
2. **Input Parser Agent** extracts fields; backend returns `extracted` + `missing`
3. **Frontend asks only missing fields**, then submits structured request → `POST /plan`
4. **Itinerary Architect Agent** builds the route skeleton
5. **Controlled tool orchestration** calls Serper for flights, hotels, and attractions per skeleton segment
6. **Travel / Stay / Sightseeing crews** run in parallel using skeleton + search context
7. **Itinerary Assembler (main.py)** merges outputs, adds meals/region/inclusions/exclusions, computes costs
8. **FastAPI returns** `MasterTravelItinerary`

---

## 7. Tools for MVP

| Tool | Purpose | Mock or Real |
|------|---------|--------------|
| **Web Search (Serper)** | Find real flight/hotel/attraction names and rough prices | Real when `SERPER_API_KEY` is set |
| **Flight Search Tool** | Search outbound/return flight options | Serper-backed |
| **Hotel Search Tool** | Search hotels per base region | Serper-backed |
| **Attraction Search Tool** | Search things to do per region/interest | Serper-backed |
| **Distance / Clustering Tool** | Group attractions by proximity | Mock heuristic |
| **Budget Calculator Tool** | Sum costs, add contingency | Local math |

---

## 8. API Endpoints (MVP)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Health check |
| `POST` | `/parse-prompt` | Extract structured fields + missing list |
| `POST` | `/plan` | Generate complete itinerary synchronously |
| `GET` | `/plan/{session_id}/pdf` | Download the generated itinerary as a PDF |

---

## 9. Frontend (MVP)

React + TypeScript + Vite interface:

1. **Prompt screen**
   - Free-text trip description
   - Backend extracts details; only missing fields are asked
2. **Chat follow-ups**
   - Origin (required)
   - Dates, travelers, budget
   - Interests chips
   - Optional travel style chips (defaults to Balanced)
3. **Itinerary view**
   - Day-by-day cards with region, theme, meals, activities, transit, stay
   - Budget meter vs actual cost
   - Inclusions / exclusions
   - Notes
   - Download PDF button (uses `GET /plan/{session_id}/pdf`)

---

## 10. Example Output Snippet

```
Tokyo — 4 Days for 2 Adults from Osaka
Total Budget: $3,000 USD  |  Estimated Cost: $2,780 USD
Scope: Tokyo + nearby attractions

Day 1 — Arrival & Shibuya Tech  (Shibuya)
  Meals: breakfast, dinner
  09:00  Train: Osaka → Tokyo (JR Pass)
  12:00  Check-in: Shibuya Excel Hotel Tokyu
  14:00  Visit Shibuya Crossing & Hachiko (free)
  16:00  Nintendo Tokyo / Pokemon Center (free entry)
  19:00  Dinner: Ichiran Ramen, Shibuya
  Daily total: $220

Day 2 — Historic Temples & Asakusa  (Asakusa)
  ...
```

---

## 11. MVP Scope Limits

| In Scope | Out of Scope |
|----------|--------------|
| Complete itinerary with transit, stay, sightseeing | Real-time price re-optimization |
| Budget summary with 10% contingency | Booking or payment processing |
| Interest-based suggestions with real names from Serper | Multi-source price aggregation across every provider |
| Geographic clustering of activities | Advanced prompt-injection guardrails |
| Hierarchical skeleton + controlled Serper searches | User accounts / long-term memory |
| Basic input validation | Visa document upload or verification |

---

## 12. Next Steps After MVP

1. Improve region splitting for multi-area destinations (e.g., North Goa / South Goa)
2. Consolidate hotels to fewer changes per trip
3. Replace mock fallback with real flight/ground APIs where possible
4. Add the multi-source aggregator and price optimizer from `architecture.md`
5. Add streaming SSE for live agent progress
6. Add post-plan Q&A chat
7. Add user accounts and saved itineraries
