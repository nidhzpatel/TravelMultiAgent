 # VoyageMind AI — Travel Multi-Agent Architecture

## 1. Vision & Goals

Build a **deep-agentic autonomous travel planner** that:

1. **Plans first** — understands the user’s intent, constraints, and preferences and produces a structured, feasible baseline itinerary.
2. **Aggregates across every major travel source** — normalizes data from flights, hotels, ground transport, and activities across all relevant online travel platforms.
3. **Optimizes price in real time** — finds the cheapest valid combination across all aggregated sources while respecting user preferences and non-negotiable constraints.
4. **Executes safely** — returns a validated, bookable itinerary with cost breakdowns, risk flags, and alternatives, protected by strong guardrails.

The system uses **CrewAI** for agent orchestration, **FastAPI** as the API gateway, and a **React + TypeScript + Vite** frontend.

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    API Gateway & Safety Gate (FastAPI)                      │
│   POST /plan  →  Safety Layer  →  Orchestration  →  SSE /plan/stream       │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                         VoyageMind Orchestration Layer                      │
│                         (CrewAI Flows / Sequential Crew)                    │
└──────┬───────────────────────────────┬───────────────────────────────┬──────┘
       │                               │                               │
┌──────▼──────────────┐  ┌─────────────▼──────────────┐  ┌─────────────▼──────┐
│   Planning Crew     │  │  Universal Source          │  │  Execution/Guard   │
│                     │  │  Aggregator & Optimizer    │  │      Crew          │
│ • Intent Parser     │  │  Crew                      │  │ • Budget Auditor   │
│ • Constraint        │  │                            │  │ • Safety Auditor   │
│   Validator         │  │ • Flight Aggregator        │  │ • Visa/Advisory    │
│ • Itinerary         │  │ • Hotel Aggregator         │  │   Checker          │
│   Architect         │  │ • Ground Transport         │  │ • Final Formatter  │
│                     │  │   Aggregator               │  │ • Risk Flagging    │
│                     │  │ • Activity Aggregator      │  │                    │
│                     │  │ • Cross-Source Price       │  │                    │
│                     │  │   Optimizer                │  │                    │
└──────┬──────────────┘  └─────────────┬──────────────┘  └─────────────┬──────┘
       │                               │                               │
       └───────────────────────────────┼───────────────────────────────┘
                                       │
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                     Tooling & Sandbox Layer                                 │
│  • Web Search (Serper)  • Flight APIs (Amadeus, Skyscanner, Google Flights) │
│  • Hotel APIs (Booking, Expedia, Agoda, Airbnb, MakeMyTrip, Trip.com)      │
│  • Maps/Distance (OSRM/Google)  • E2B Python Sandbox (math/optimization)    │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                     Persistence & Memory Layer                              │
│  • PostgreSQL (sessions, users, audit trails)                               │
│  • ChromaDB (vector memory / preference embeddings)                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Agent Breakdown

### Phase 1: Planning Crew

| Agent | Responsibility | Key Tools | Output |
|-------|---------------|-----------|--------|
| **Intent Parser** | Extract destination, dates, budget, travelers, interests, dietary/mobility constraints from free text. | LLM + classification prompt | `ParsedTravelRequest` |
| **Constraint Validator** | Check budget feasibility, passport/visa needs, travel advisories, seasonality. | Web search, visa API stubs | `ConstraintReport` |
| **Itinerary Architect** | Build day-by-day skeleton: regions/clusters, anchors, rest/meal buffers, activity shortlist. | Route clustering SKILL, maps tool | `DraftItinerary` |

### Phase 2: Universal Source Aggregator & Optimizer Crew

This crew queries **every relevant travel platform**, normalizes results into a common schema, and then runs price optimization across all sources.

| Agent | Responsibility | Sources Considered | Output |
|-------|---------------|--------------------|--------|
| **Flight Aggregator** | Search and normalize flight options across all available flight sources. | Amadeus, Skyscanner, Google Flights, Kayak, Expedia Flights, MakeMyTrip, Cleartrip | `FlightOptions` |
| **Hotel Aggregator** | Search and normalize hotel/home-stay options across all accommodation sources. | Booking.com, Expedia, Hotels.com, Agoda, Airbnb, Vrbo, MakeMyTrip, Goibibo, Trip.com | `HotelOptions` |
| **Ground Transport Aggregator** | Search trains, buses, metros, taxis, rental cars, ferries across all relevant sources. | Rome2Rio, Google Transit, Amtrak, IRCTC, FlixBus, BlaBlaCar, Uber API, rental APIs | `GroundTransportOptions` |
| **Activity Aggregator** | Find activities, tours, attractions, restaurants with pricing across sources. | GetYourGuide, Viator, Klook, Google Places, TripAdvisor, Yelp, Tiqets, Fever | `ActivityOptions` |
| **Cross-Source Price Optimizer** | Combine cheapest valid options from all aggregators, score against user preferences, and re-balance if over budget. | All above + E2B sandbox | `OptimizedItinerary` |

**Aggregation rule:** No single source is trusted blindly. Every agent returns at least 3 candidates per category with normalized fields: `price`, `currency`, `provider`, `url`, `rating`, `duration`, `cancellation_policy`. The optimizer compares across providers and picks the globally cheapest valid combination.

### Phase 3: Execution / Guard Crew

| Agent | Responsibility | Key Tools | Output |
|-------|---------------|-----------|--------|
| **Budget Auditor** | Recompute TCO with taxes, fees, tips, contingency; fail hard if over budget. | E2B sandbox stub | `BudgetAudit` |
| **Compliance Checker** | Verify visa, passport validity, advisories, cancellation policies. | Web search, visa stubs | `ComplianceReport` |
| **Safety Auditor** | Run prompt/output safety checks, detect policy violations, flag scams/untrusted providers. | Guardrails layer | `SafetyReport` |
| **Final Formatter** | Combine everything into `MasterTravelItinerary` schema. | — | `MasterTravelItinerary` |

---

## 4. Safety & Guardrails

Safety is a first-class concern, not an afterthought.

### 4.1 Input Safety

- **Prompt Injection Detection**
  - A dedicated pre-processing guard scans the raw user prompt for:
    - Instruction override attempts (`ignore previous instructions`, `you are now...`, `disregard...`)
    - Delimiter confusion (`###`, `<<<`, XML tag injection)
    - Role-switch attempts (`act as a system administrator`, `pretend you are...`)
    - Unicode homoglyphs, zero-width characters, excessive repetition
  - Suspicious prompts are blocked or sanitized before reaching the LLM.

- **Jailbreak / Harmful Request Filtering**
  - Detect requests for illegal activities, fraud, self-harm, or bypassing payment.
  - Block and return a safe refusal with logging.

- **PII Scrubbing**
  - Remove or mask before any external LLM or third-party API call:
    - Passport numbers, credit card numbers, exact home addresses
    - Phone numbers, national IDs, dates of birth
  - Use regex + NER-based PII detector.
  - Store raw PII only in PostgreSQL with encryption; never in vector memory or logs.

- **Input Validation**
  - Strict Pydantic validation on every API request.
  - Budget must be numeric and > 0.
  - Dates must be realistic (not in the past, return after departure).
  - Destination/country inferred or explicitly provided.

### 4.2 Output Safety

- **Schema Enforcement**
  - Final output must pass `MasterTravelItinerary` Pydantic validation.
  - Any agent output that does not match schema triggers a retry with the Financial/Safety Auditor.

- **Budget Hard Guardrail**
  - If `actual_calculated_cost_usd > total_budget_usd`, the plan is rejected.
  - The optimizer must trim optional items or downgrade options until within budget.

- **Price Sanity Checks**
  - Flag prices that are statistically anomalous (e.g., 90% below median) as potential scams or errors.
  - Reject providers with no verifiable URL or rating below threshold.

- **No Hallucinated Bookings**
  - Every bookable item must include a `provider` and `url`.
  - Fake URLs or unreachable links are caught by a validation tool.

### 4.3 Operational Safety

- **Sandboxed Execution**
  - All math, optimization, and code generation runs inside the **E2B sandbox**.
  - No agent-generated code runs on the host.

- **Rate Limiting & Abuse Prevention**
  - Per-user and per-IP rate limits on `/plan` and `/plan/stream`.
  - Quotas on external API calls per session.
  - Exponential backoff on external API failures.

- **Audit Trails**
  - Every agent action, tool call, LLM prompt, and output is logged with `session_id`.
  - Logs are immutable and retained for compliance.

- **Content Moderation**
  - Moderate agent-generated content for offensive or biased output.
  - Flag destinations under active travel advisories.

---

## 5. Data Models

### Request

```python
class TravelPlanRequest(BaseModel):
    user_query: str
    total_budget_usd: float
    travelers: int = 1
    currency: str = "USD"
    departure_city: str | None = None
    departure_date: date | None = None
    return_date: date | None = None
    interests: list[str] = []
    preferences: TravelPreferences | None = None
```

### Preferences

```python
class TravelPreferences(BaseModel):
    flight_priority: str = "cheapest"   # cheapest | fastest | fewest_stops
    hotel_priority: str = "location"    # cheapest | location | rating
    transit_priority: str = "cheapest"  # cheapest | fastest | least_walking
    food_budget: str = "mixed"          # street_food | mixed | fine_dining
    pace: str = "moderate"              # relaxed | moderate | packed
    flexibility: int = 50               # 0 = rigid locks, 100 = fully flexible
```

### Normalized Option (used by aggregators)

```python
class TravelOption(BaseModel):
    provider: str
    source_name: str
    title: str
    price: float
    currency: str
    url: str
    rating: float | None = None
    duration_minutes: int | None = None
    cancellation_policy: str = "unknown"
    is_refundable: bool = False
```

### Output

```python
class ActivityItem(BaseModel):
    time_slot: str
    activity_name: str
    location: str
    estimated_cost_usd: float
    notes: str
    provider: str
    booking_url: str | None = None

class DayItinerary(BaseModel):
    day_number: int
    theme: str
    activities: list[ActivityItem]
    daily_transit_cost_usd: float
    total_daily_cost_usd: float

class MasterTravelItinerary(BaseModel):
    destination: str
    total_budget_usd: float
    actual_calculated_cost_usd: float
    currency: str
    visa_requirements_summary: str
    days: list[DayItinerary]
    flight_summary: str
    hotel_summary: str
    alternatives: list[str]
    safety_flags: list[str] = []
```

---

## 6. Flow Pipeline

1. **Safety Gate** runs first on every request:
   - Prompt injection / jailbreak detection
   - PII scrubbing
   - Input validation
2. **User request passes** → `POST /plan` returns `session_id` immediately.
3. **Planning Crew** runs:
   - Parse intent
   - Validate constraints
   - Draft skeleton itinerary (clusters, anchors, buffers)
4. **Universal Source Aggregator & Optimizer Crew** runs:
   - Each aggregator queries multiple travel platforms
   - Results normalized to `TravelOption`
   - Cross-Source Price Optimizer finds cheapest valid combination across all sources
   - If over budget, re-runs with cheaper options or trimmed activities
5. **Execution / Guard Crew** runs:
   - Budget audit with contingency
   - Visa/advisory check
   - Safety audit
   - Format final output into `MasterTravelItinerary`
6. **SSE stream** emits step-by-step progress; frontend renders live logs + final itinerary.

---

## 7. Real-Time Cost Optimization Strategy

- **Multi-source coverage:** every aggregator must query all configured providers, not just one.
- **Normalization:** all prices converted to USD, durations to minutes, ratings to 0–10 scale.
- **Combination search:** optimizer evaluates combinations of (flight, hotel, transport, activities) from different providers.
- **Preference scoring:**
  - `flight_priority`, `hotel_priority`, `transit_priority`
  - Total cost vs. budget headroom
  - Geographic fit (hotel close to daily clusters)
- **Budget enforcement:** if total exceeds budget, trim optional activities, downgrade hotel class, or switch to cheaper transport; never exceed the user’s stated budget.
- **Price anomaly rejection:** options priced far below median for the route/date are flagged as suspicious.

---

## 8. External Integrations (Mocked with Production Hooks)

| Category | Providers Considered | Mock Behavior |
|----------|---------------------|---------------|
| **Flights** | Amadeus, Skyscanner, Google Flights, Kayak, Expedia Flights, MakeMyTrip, Cleartrip | Returns sample options per provider |
| **Hotels** | Booking.com, Expedia, Hotels.com, Agoda, Airbnb, Vrbo, MakeMyTrip, Goibibo, Trip.com | Returns sample options per provider |
| **Ground Transport** | Rome2Rio, Google Transit, Amtrak, IRCTC, FlixBus, BlaBlaCar, Uber, rental APIs | Returns route/time/price estimates |
| **Activities** | GetYourGuide, Viator, Klook, Google Places, TripAdvisor, Yelp, Tiqets, Fever | Returns activity options and prices |
| **Search** | Serper / SerpAPI | Web search for advisories, deals, reviews |
| **Math/Sandbox** | E2B Code Interpreter | Runs isolated budget/optimization scripts |
| **Maps** | OpenStreetMap / OSRM / Google Distance Matrix | Distance matrix and route time estimates |

**Integration policy:** Each tool returns a list of `TravelOption` objects. The system does not depend on any single provider being available; it optimizes across whatever sources return valid data.

---

## 9. API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Health check |
| `POST` | `/plan` | Kick off planning + optimization |
| `GET` | `/plan/stream?session_id={id}` | SSE progress/events |
| `GET` | `/plan/{session_id}` | Fetch final result |

---

## 10. Frontend

- React + TypeScript + Vite
- Form captures query, budget, dates, travelers, interests, and preferences
- Live SSE stream panel showing per-agent progress
- Final itinerary renderer with:
  - Daily cards and activities
  - Per-item provider and booking URL
  - Total cost vs. budget
  - Safety flags and alternatives

---

## 11. Non-Functional Requirements

- Initial ACK `< 1.5s`
- Full plan delivered via SSE within target runtime
- Pydantic schema compliance > 99.9%
- All PII scrubbed before external LLM calls
- Prompt injection / jailbreak detection blocks unsafe requests
- Tool calls isolated in E2B sandbox
- Per-user rate limiting and audit logging

---

## 12. Open Decisions

1. **Dynamic re-optimization:** Should the optimizer keep checking for cheaper options while the crew runs, or return a single cheapest snapshot?
2. **Booking scope:** Should the system generate bookable itineraries with direct links, or stop at recommendations?
3. **Provider priority:** If two sources return the same price, should we prefer the provider with the best rating, the best cancellation policy, or user preference?
