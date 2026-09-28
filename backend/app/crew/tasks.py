from crewai import Task
from app.crew.agents import (
    input_parser_agent,
    itinerary_architect_agent,
    travel_planner_agent,
    transit_mode_selector_agent,
    stay_planner_agent,
    sightseeing_planner_agent,
    itinerary_assembler_agent,
)


parse_input_task = Task(
    description=(
        "Extract travel details from the user's message into a JSON object.\n\n"
        "User request: {free_text}\n\n"
        "Fields (only include what is actually in the message):\n"
        "- destination: city/country they want to visit\n"
        "- origin: city/country they are leaving from (required)\n"
        "- start_date: start date as written (e.g., '10/10/2026', 'tomorrow', 'next week')\n"
        "- end_date: end date as written\n"
        "- travelers: number of people\n"
        "- total_budget_usd: budget number exactly as written (do NOT convert currency)\n"
        "- interests: list of things they want to do\n"
        "- radius_km: integer — how far from the destination they will travel, ONLY if stated "
        "(e.g., 'within 200 km', 'under 100 miles' → convert miles to km). Omit if unstated.\n"
        "- food_preference: what they eat, ONLY if stated — vegetarian/veg, non-vegetarian/non-veg, "
        "vegan, jain, halal, kosher, gluten-free, or a cuisine style\n"
        "- travel_style: 'budget', 'balanced', or 'luxury' if they mention it (optional)\n"
        "- transport_preference: 'flight', 'train', or 'bus' ONLY if they explicitly say how they want to travel (e.g., 'by train', 'want flight', 'bus is fine')\n"
        "- cover_nearby: true/false — true unless user explicitly says 'only X', 'no nearby', 'single destination'\n"
        "- dietary_notes: any food restrictions\n"
        "- mobility_notes: any walking/access needs\n"
        "- free_text: anything else important\n\n"
        "Rules:\n"
        "1. 'me and my friend' = 2 travelers. 'just me' or 'alone' = 1.\n"
        "2. Keep dates in the user's own words.\n"
        "3. Keep budget as the original number; do not do math.\n"
        "4. Split comma-separated interests into a list.\n"
        "5. Never make up fields — omit anything the user did not state.\n"
        "6. Return ONLY raw JSON. No markdown, no comments.\n\n"
        "Example:\n"
        '{{"destination": "Goa", "origin": "Ahmedabad", "start_date": "10/10/2026", "end_date": "16/10/2026", '
        '"travelers": 2, "total_budget_usd": 40000, "interests": ["beaches", "nightlife", "shopping", "historical places"], '
        '"radius_km": 200, "food_preference": "vegetarian", "travel_style": "balanced", "cover_nearby": true}}'
    ),
    expected_output="A raw JSON object containing the extracted travel request fields.",
    agent=input_parser_agent,
)


build_skeleton_task = Task(
    description=(
        "Build a day-by-day skeleton itinerary for this trip.\n\n"
        "Destination: {destination}\n"
        "Origin: {origin}\n"
        "Start date: {start_date}\n"
        "End date: {end_date}\n"
        "Travelers: {travelers}\n"
        "Interests: {interests}\n"
        "Travel style: {travel_style}\n"
        "Cover nearby places: {cover_nearby}\n"
        "Travel radius from destination: {radius_km} km (hard boundary — nothing outside it)\n"
        "Nearby places to consider: {nearby_places}\n\n"
        "Output ONLY a raw JSON object with this exact shape:\n"
        '{{\n'
        '  "days": [\n'
        '    {{\n'
        '      "day_number": 1,\n'
        '      "date": "YYYY-MM-DD",\n'
        '      "region": "region or area for the day (e.g., North Goa, Old Manali)",\n'
        '      "base_location": "city/area where the hotel is for this night",\n'
        '      "transit_from": "origin or previous base, if moving that day",\n'
        '      "transit_to": "next base, if moving that day",\n'
        '      "theme": "short theme like \'beach day\' or \'heritage day\'",\n'
        '      "activity_focus": ["interest tag"]\n'
        '    }}\n'
        '  ],\n'
        '  "transit_legs": [\n'
        '    {{\n'
        '      "day_number": 1,\n'
        '      "from_location": "...",\n'
        '      "to_location": "...",\n'
        '      "mode": "flight|train|bus|cab",\n'
        '      "provider": "...",\n'
        '      "estimated_cost_usd": 0,\n'
        '      "duration_minutes": 0,\n'
        '      "notes": "..."\n'
        '    }}\n'
        '  ],\n'
        '  "hotel_regions": ["distinct base locations"]\n'
        '}}\n\n'
        "Rules:\n"
        "1. Every day's region, base, and any nearby place MUST lie within {radius_km} km of {destination}. "
        "Drop any nearby place beyond the radius.\n"
        "2. Keep the hotel base at the main destination unless a nearby place within the radius clearly needs an overnight stay. Minimize hotel changes (1–2 bases per week).\n"
        "3. If cover_nearby is true and the trip is 4+ days, allocate specific days to nearby regions/attractions listed above. For example, a 7-day Goa trip could split days between North Goa beaches and South Goa heritage.\n"
        "4. The 'region' field must be a short area name like 'Manali', 'Old Manali', 'Solang Valley', 'North Goa', or 'South Goa'. Do not paste raw web-search output.\n"
        "5. The 'theme' field must be a short phrase like 'beach day', 'heritage walk', or 'nature day'.\n"
        "6. Include an arrival leg from origin to the first base, and a return leg from the last base to origin.\n"
        "7. Do not invent exact prices; use 0 if unknown.\n"
        "8. Return ONLY raw JSON. No markdown, no comments."
    ),
    expected_output="A raw JSON skeleton itinerary with days, transit_legs, and hotel_regions.",
    agent=itinerary_architect_agent,
)


select_transit_mode_task = Task(
    description=(
        "Decide the best transport mode for the main intercity route: {origin} -> {destination} "
        "on {start_date} for {travelers} traveler(s), style {travel_style}.\n"
        "User's transport preference (if any): {transport_preference}\n"
        "User's food preference (if any): {food_preference}\n\n"
        "Use your search tools to check real flight, train, and bus options for this route, then decide.\n\n"
        "Decision policy (apply in this order):\n"
        "1. If the user explicitly asked for a mode (e.g., 'by train', 'want flight', 'bus is fine'), choose it. State that the preference was explicit.\n"
        "2. Route distance decides what competes: under ~300 km, buses and trains beat flying; over ~300 km, include flights in the comparison.\n"
        "3. Among the reasonable options, choose the CHEAPEST total for the group.\n"
        "4. If two options cost about the same (within ~15%), choose the FASTER one.\n"
        "5. If still tied, prefer the option with meal service matching the user's food preference (e.g., veg meals on board).\n"
        "6. Overnight trains and comfortable Volvo buses are valid choices and often beat flights on short/medium routes.\n\n"
        "Output ONLY a raw JSON object:\n"
        '{{"mode": "flight|train|bus", "provider_hint": "a real operator name like IndiGo, Indian Railways, or RedBus Volvo", '
        '"estimated_cost_usd_per_person": N, "duration_minutes": N, "alternatives_considered": "...", "reasoning": "one or two sentences"}}'
    ),
    expected_output="A raw JSON object with the chosen mode, per-person cost, duration, and reasoning.",
    agent=transit_mode_selector_agent,
)


plan_travel_task = Task(
    description=(
        "Using the parsed request, route skeleton, selected transport mode, and real search context, plan all transit.\n"
        "Origin: {origin}\n"
        "Destination: {destination}\n"
        "Start date: {start_date}\n"
        "End date: {end_date}\n"
        "Travelers: {travelers}\n"
        "Travel style: {travel_style}\n"
        "Food preference: {food_preference}\n"
        "Total transit budget (USD): {budget_transit_usd}\n"
        "Route skeleton: {skeleton}\n"
        "Selected intercity mode decision: {transit_mode_decision}\n"
        "Real search context: {search_context}\n\n"
        "Rules:\n"
        "1. Use the route skeleton to know the first and last base location.\n"
        "2. You MUST include an outbound leg from origin to the first base on day 1, and a return leg from the last base to origin on the final day. Use the selected mode decision's mode, cost, and duration for these main legs unless the user explicitly asked otherwise. These two legs are mandatory — outputting only local hops is a failure.\n"
        "3. Choose the mode of every leg by distance: walk under 2 km; auto/rickshaw/cab for 2–15 km; bus/metro/train for 15–300 km; flight only beyond ~300 km or when the user prefers it.\n"
        "4. When a long leg is taken around mealtime, note where the group eats en route and that it matches their food preference (or warn if it cannot).\n"
        "5. Use provider names and rough prices from the search context. Do not use MockAir.\n"
        "6. Keep the sum of all transit legs within the Total transit budget (USD).\n"
        "7. Estimate costs and durations for every leg, and put the approximate distance plus why this mode in each leg's notes.\n"
        "Output ONLY a raw JSON array of transit legs with no markdown or explanations. Each leg must have:\n"
        '{{"day_number": N, "from_location": "...", "to_location": "...", "mode": "flight|train|bus|metro|cab|walk", '
        '"provider": "...", "estimated_cost_usd": N, "duration_minutes": N, "notes": "..."}}'
    ),
    expected_output="A raw JSON array of transit legs using real search context, within budget.",
    agent=travel_planner_agent,
    context=[parse_input_task],
)


plan_stay_task = Task(
    description=(
        "Using the parsed request, route skeleton, and real hotel search context, plan accommodation.\n"
        "Travelers: {travelers}\n"
        "Travel style: {travel_style}\n"
        "Food preference: {food_preference}\n"
        "Total stay budget (USD): {budget_stay_usd}\n"
        "Route skeleton: {skeleton}\n"
        "Real search context: {search_context}\n\n"
        "Rules:\n"
        "1. Use the skeleton's base_location per night; do not put every night in one generic city-center hotel.\n"
        "2. Recommend real hotel names from the search context. Do not use MockHotel Plus.\n"
        "3. HARD REQUIREMENTS for every recommended stay:\n"
        "   a. It must serve the user's food preference: {food_preference}. If the preference is 'none', any good kitchen is fine.\n"
        "   b. Breakfast and dinner must be included in the rate; lunch is always on the traveler.\n"
        "   c. It must match the travel_style (budget / balanced / luxury) and be in a convenient area near the next day's activities.\n"
        "4. Keep the sum of all nightly stay costs within the Total stay budget (USD).\n"
        "5. The why_this_choice field must state the food match and that breakfast + dinner are included.\n"
        "Output ONLY a raw JSON array of stay options with no markdown or explanations. Each option must have:\n"
        '{{"night_number": N, "hotel_name": "...", "location": "...", "room_type": "...", '
        '"estimated_cost_usd": N, "why_this_choice": "...", "booking_notes": "..."}}'
    ),
    expected_output="A raw JSON array of stay options using real hotel names, matching food preference with breakfast and dinner included, within budget.",
    agent=stay_planner_agent,
    context=[parse_input_task],
)


plan_sightseeing_task = Task(
    description=(
        "Using the parsed request, route skeleton, place rankings, and real attraction/blog context, plan places to visit, food, and local roaming for each day.\n"
        "Travelers: {travelers}\n"
        "Travel radius from destination: {radius_km} km\n"
        "Food preference: {food_preference}\n"
        "Total food/local-roaming budget (USD): {budget_food_usd}\n"
        "Route skeleton: {skeleton}\n"
        "Place rankings (JSON — top places by rating x review count, plus iconic places): {place_rankings}\n"
        "Real search context (includes blog/review research): {search_context}\n\n"
        "Business model (important):\n"
        "- This is a travel package: travel, stay, meals, and local cabs are included.\n"
        "- Breakfast and dinner are served at the hotel; do NOT schedule or cost them.\n"
        "- Lunch is self-paid by the traveler and must match the food preference ({food_preference}).\n"
        "- Activity entrance fees and optional experiences are NOT included.\n"
        "- Therefore, every activity's estimated_cost_usd must cover ONLY lunch or local cab transport to the spot.\n"
        "- Use category 'food' for lunch and 'transit' for local cab to the spot; use 'sightseeing' for places visited (cost 0).\n\n"
        "Rules:\n"
        "1. Coverage is mandatory: EVERY place in the place rankings above must appear somewhere in the plan — every famous/iconic place (ignore its rating) and every top_by_score place. Spread them sensibly across the days.\n"
        "2. Use the skeleton's day theme, region, and activity_focus; every activity must belong to the day's region and lie within {radius_km} km of {destination}.\n"
        "3. Cluster activities by the day's region to minimize transit.\n"
        "4. Lunch stops must respect the food preference; pick real restaurant/food spots from the search context or blog research.\n"
        "5. Mine the search context and blog research for notes: best time to visit, what the place is famous for, or an honest review highlight. Put 1–2 such details in the activity notes.\n"
        "6. Assign realistic time slots and breaks.\n"
        "7. Keep the sum of all food/transit costs within the Total food/local-roaming budget (USD).\n"
        "8. Do not invent generic attractions. Use real place names from the place rankings and search context.\n"
        "Output ONLY a raw JSON array of day objects with no markdown or explanations. Each day object must have:\n"
        '{{"day_number": N, "theme": "...", "activities": [{{"time_slot": "...", "activity_name": "...", '
        '"location": "...", "category": "sightseeing|food|transit|rest", "estimated_cost_usd": N, "notes": "..."}}]}}'
    ),
    expected_output="A raw JSON array of day objects covering all ranked and famous places; food costs limited to lunch and local transit.",
    agent=sightseeing_planner_agent,
    context=[parse_input_task],
)


assemble_itinerary_task = Task(
    description=(
        "You are the Itinerary Assembler. Refine the baseline itinerary below using the route skeleton, "
        "place rankings, search context, and specialist outputs. Do NOT change the number of days, dates, or overall structure. "
        "Your job is to improve quality: fix bad hotel names, relocate activities that are far from the day's region, "
        "consolidate duplicate hotels, improve activity names with real places from the search context, and make sure costs are reasonable.\n\n"
        "Destination: {destination}\n"
        "Origin: {origin}\n"
        "Travelers: {travelers}\n"
        "Travel style: {travel_style}\n"
        "Travel radius from destination: {radius_km} km\n"
        "Total budget (USD): {total_budget_usd}\n"
        "Food preference: {food_preference}\n"
        "Dietary notes: {dietary_notes}\n"
        "Mobility notes: {mobility_notes}\n\n"
        "Original currency: {currency}\n"
        "Total budget (USD): {total_budget_usd}\n"
        "Baseline itinerary (use this as your starting point): {baseline_itinerary}\n\n"
        "Route skeleton (JSON): {skeleton}\n\n"
        "Place rankings (JSON): {place_rankings}\n\n"
        "Real search context (JSON): {search_context}\n\n"
        "Transit legs (JSON array): {transit_raw}\n\n"
        "Stay options (JSON array): {stay_raw}\n\n"
        "Sightseeing days (JSON array): {sightseeing_raw}\n\n"
        "Famous attractions that MUST appear in the final plan: {must_see}\n\n"
        "Business model (important):\n"
        "- Travel, stay, and meals (breakfast + dinner at the hotel, lunch self-paid) and local cabs are included.\n"
        "- Activity entrance fees and optional experiences are NOT included.\n"
        "- Activity costs should only cover lunch and local cab transport to the spot.\n\n"
        "Rules:\n"
        "1. Keep exactly the same number of days and dates as the baseline.\n"
        "2. Coverage is mandatory: every place listed in the place rankings AND every famous attraction above must appear at least once.\n"
        "3. Nothing may be scheduled outside {radius_km} km of {destination} or outside the day's region; remove or relocate violations.\n"
        "4. Use the skeleton's region and theme for each day; do not change them unless the baseline is clearly wrong.\n"
        "5. Replace generic or invalid hotel names with real hotel names from the search context, and make sure each stay notes the food preference match and that breakfast + dinner are included.\n"
        "6. Replace generic activity names like 'Historic Downtown Walk' with real place names from the search context and place rankings.\n"
        "7. Lunch activities must match the food preference ({food_preference}); breakfast and dinner are at the hotel and must not appear as paid activities.\n"
        "8. Consolidate consecutive nights at the same base to a single hotel.\n"
        "9. Ensure every day has at least 2–3 activities with realistic time slots.\n"
        "10. Keep arrival/return transit legs on day 1 and the last day.\n"
        "11. Preserve meals_included and compute daily costs correctly: daily_transit + daily_activity + daily_stay = total_daily.\n"
        "12. Keep the actual_calculated_cost_usd at or below total_budget_usd; if it exceeds, add an over-budget note. Prefer best-value options (high rating/reviews for the price) over the absolute cheapest when quality differs.\n"
        "13. Keep top-level inclusions, exclusions, and notes; inclusions must mention breakfast and dinner at the hotel.\n"
        "14. Return ONLY raw JSON with no markdown or explanations.\n\n"
        "Output shape (match the baseline exactly)."
    ),
    expected_output="A refined raw JSON object matching the MasterTravelItinerary schema.",
    agent=itinerary_assembler_agent,
    context=[parse_input_task],
)
