---
name: route-clustering-optimization
description: Guidelines and mathematical strategies for clustering travel itinerary locations to minimize travel time and prevent backtracking.
version: 1.0.0
---

# Route Clustering & Geographic Optimization Skill

## Core Operational Directives
* **Geographic Clustering:** Group daily activities within a 5km radius to minimize intra-day travel.
* **Travel Time Buffers:** Always add a 25% time buffer to raw Google Maps/OSM transit estimates to account for local traffic and navigation friction.
* **Anchor Points:** Designate one major attraction per day as the primary anchor, building secondary activities within immediate walking/short-transit proximity.

---

## Step-by-Step Execution Workflow

### Step 1: Spatial Grouping
1. Retrieve latitude and longitude for all selected venues.
2. Group coordinates using basic proximity heuristics or run a K-Means clustering script via the python sandbox environment.

### Step 2: Sequential Ordering (TSP Resolution)
1. Order venues within each daily cluster to form a continuous unidirectional loop.
2. Ensure start and end points align with the user's accommodation or primary transit hub.

---

## Verification & Guardrails Checklist
Before submitting the routing plan, verify:
- [ ] No single day contains more than 90 minutes of total intra-city transit.
- [ ] Venues are cross-checked for opening hours against the planned arrival window.
- [ ] Meal stops are inserted near the active cluster between 12:00-14:00 and 19:00-21:00.
