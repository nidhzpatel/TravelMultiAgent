from crewai import Task
from app.crew.agents import (
    input_parser_agent,
    itinerary_architect_agent,
    travel_planner_agent,
    stay_planner_agent,
    sightseeing_planner_agent,
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
        "- travel_style: 'budget', 'balanced', or 'luxury' if they mention it (optional)\n"
        "- cover_nearby: true/false — true unless user explicitly says 'only X', 'no nearby', 'single destination'\n"
        "- dietary_notes: any food restrictions\n"
        "- mobility_notes: any walking/access needs\n"
        "- free_text: anything else important\n\n"
        "Rules:\n"
        "1. 'me and my friend' = 2 travelers. 'just me' or 'alone' = 1.\n"
        "2. Keep dates in the user's own words.\n"
        "3. Keep budget as the original number; do not do math.\n"
        "4. Split comma-separated interests into a list.\n"
        "5. Never make up fields.\n"
        "6. Return ONLY raw JSON. No markdown, no comments.\n\n"
        "Example:\n"
        '{{"destination": "Goa", "origin": "Ahmedabad", "start_date": "10/10/2026", "end_date": "16/10/2026", '
        '"travelers": 2, "total_budget_usd": 40000, "interests": ["beaches", "nightlife", "shopping", "historical places"], '
        '"travel_style": "balanced", "cover_nearby": true}}'
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
        "1. Keep the hotel base at the main destination unless a nearby place clearly needs an overnight stay. Minimize hotel changes (1–2 bases per week).\n"
        "2. If cover_nearby is true and the trip is 4+ days, allocate specific days to nearby regions/attractions listed above. For example, a 7-day Goa trip could split days between North Goa beaches and South Goa heritage.\n"
        "3. The 'region' field must be a short area name like 'Manali', 'Old Manali', 'Solang Valley', 'North Goa', or 'South Goa'. Do not paste raw web-search output.\n"
        "4. The 'theme' field must be a short phrase like 'beach day', 'heritage walk', or 'nature day'.\n"
        "5. Include an arrival leg from origin to the first base, and a return leg from the last base to origin.\n"
        "6. Do not invent exact prices; use 0 if unknown.\n"
        "7. Return ONLY raw JSON. No markdown, no comments."
    ),
    expected_output="A raw JSON skeleton itinerary with days, transit_legs, and hotel_regions.",
    agent=itinerary_architect_agent,
)


plan_travel_task = Task(
    description=(
        "Using the parsed request, route skeleton, and real search context, plan all transit.\n"
        "Origin: {origin}\n"
        "Destination: {destination}\n"
        "Start date: {start_date}\n"
        "End date: {end_date}\n"
        "Travelers: {travelers}\n"
        "Travel style: {travel_style}\n"
        "Route skeleton: {skeleton}\n"
        "Real search context: {search_context}\n\n"
        "Rules:\n"
        "1. Use the route skeleton to know the first and last base location.\n"
        "2. Include an outbound leg from origin to the first base on day 1, and a return leg from the last base to origin on the final day.\n"
        "3. Use provider names and rough prices from the search context. Do not use MockAir.\n"
        "4. Plan daily local transport (cab, bus, metro, walk) between the accommodation and activity clusters.\n"
        "5. Estimate costs and durations for every leg.\n"
        "Output ONLY a raw JSON array of transit legs with no markdown or explanations. Each leg must have:\n"
        '{{"day_number": N, "from_location": "...", "to_location": "...", "mode": "flight|train|bus|metro|cab|walk", '
        '"provider": "...", "estimated_cost_usd": N, "duration_minutes": N, "notes": "..."}}'
    ),
    expected_output="A raw JSON array of transit legs using real search context.",
    agent=travel_planner_agent,
    context=[parse_input_task],
)


plan_stay_task = Task(
    description=(
        "Using the parsed request, route skeleton, and real hotel search context, plan accommodation.\n"
        "Route skeleton: {skeleton}\n"
        "Real search context: {search_context}\n\n"
        "Rules:\n"
        "1. Use the skeleton's base_location per night; do not put every night in one generic city-center hotel.\n"
        "2. Recommend real hotel names from the search context. Do not use MockHotel Plus.\n"
        "3. Match the travel_style (budget / balanced / luxury) and choose a convenient area/region.\n"
        "4. Include hotel name, location/neighborhood, room type, nightly cost, and why it was chosen.\n"
        "Output ONLY a raw JSON array of stay options with no markdown or explanations. Each option must have:\n"
        '{{"night_number": N, "hotel_name": "...", "location": "...", "room_type": "...", '
        '"estimated_cost_usd": N, "why_this_choice": "...", "booking_notes": "..."}}'
    ),
    expected_output="A raw JSON array of stay options using real hotel names.",
    agent=stay_planner_agent,
    context=[parse_input_task],
)


plan_sightseeing_task = Task(
    description=(
        "Using the parsed request, route skeleton, and real attraction search context, plan sightseeing and dining for each day.\n"
        "Route skeleton: {skeleton}\n"
        "Real search context: {search_context}\n\n"
        "Rules:\n"
        "1. Use the skeleton's day theme, region, and activity_focus to choose real attractions from the search context.\n"
        "2. Cluster activities by the day's region to minimize transit.\n"
        "3. Assign realistic time slots and meal breaks.\n"
        "4. Respect dietary and mobility notes.\n"
        "5. Do not invent generic attractions like 'Historic Downtown Walk'. Use real place names from the search context.\n"
        "Output ONLY a raw JSON array of day objects with no markdown or explanations. Each day object must have:\n"
        '{{"day_number": N, "theme": "...", "activities": [{{"time_slot": "...", "activity_name": "...", '
        '"location": "...", "category": "sightseeing|food|shopping|rest", "estimated_cost_usd": N, "notes": "..."}}]}}'
    ),
    expected_output="A raw JSON array of day objects with real attractions.",
    agent=sightseeing_planner_agent,
    context=[parse_input_task],
)
