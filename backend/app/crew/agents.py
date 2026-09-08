from crewai import Agent

from app.config import get_settings
from app.llm import get_chat_llm
from app.crew.tools import (
    distance_clustering_tool,
    flight_search_tool,
    ground_transport_tool,
    hotel_search_tool,
    attraction_search_tool,
)

settings = get_settings()

# Gemini primary with Ollama fallback (see app/llm.py). If no Gemini key is set, Ollama only.
primary_llm = get_chat_llm()


input_parser_agent = Agent(
    role="Travel Request Parser",
    goal="Extract clean, structured travel parameters from the user's raw input and output them as JSON.",
    backstory=(
        "You are a meticulous travel intake specialist. You read messy user messages and "
        "extract destination, origin, dates, budget, travelers, interests, travel style, "
        "dietary/mobility notes, and whether flights are needed. You always output valid JSON."
    ),
    memory=False,
    verbose=True,
    allow_delegation=False,
    max_iter=5,
    llm=primary_llm,
)


itinerary_architect_agent = Agent(
    role="Itinerary Architect",
    goal="Build a feasible day-by-day skeleton itinerary that decides region/base per day and required transit legs.",
    backstory=(
        "You are an expert route planner. Given a destination, origin, dates, interests, and optional "
        "nearby places, you decide where the traveler sleeps each night and which region they explore each day. "
        "You minimize hotel changes while avoiding backtracking. You output a strict JSON skeleton."
    ),
    memory=False,
    verbose=True,
    allow_delegation=False,
    max_iter=5,
    tools=[],
    llm=primary_llm,
)


travel_planner_agent = Agent(
    role="Transit & Logistics Planner",
    goal="Plan all travel legs and output them as a JSON array.",
    backstory=(
        "You are a logistics expert. You know how to get travelers from origin to destination "
        "and move them efficiently within the city using the cheapest suitable options for their style. "
        "You always output a valid JSON array of transit legs."
    ),
    memory=False,
    verbose=True,
    allow_delegation=False,
    max_iter=5,
    tools=[flight_search_tool, ground_transport_tool],
    llm=primary_llm,
)


transit_mode_selector_agent = Agent(
    role="Transit Mode Selector",
    goal="Choose the best transport mode (flight, train, or bus) for the main intercity route and justify it with live prices and durations.",
    backstory=(
        "You are a sharp travel economist. You compare flight, train, and bus options for a route "
        "using real search results: an explicit user preference always wins; otherwise short routes "
        "favor bus or train, the cheapest reasonable option wins, and when prices are close the "
        "fastest option wins. You always output a strict JSON decision."
    ),
    memory=False,
    verbose=True,
    allow_delegation=False,
    max_iter=10,
    tools=[flight_search_tool, ground_transport_tool],
    llm=primary_llm,
)


stay_planner_agent = Agent(
    role="Accommodation Planner",
    goal="Recommend accommodations and output them as a JSON array.",
    backstory=(
        "You are a hospitality curator. You match travelers with stays that fit their budget, "
        "location needs, and travel style, and you explain why each choice works. "
        "You always output a valid JSON array of stay options."
    ),
    memory=False,
    verbose=True,
    allow_delegation=False,
    max_iter=5,
    tools=[hotel_search_tool],
    llm=primary_llm,
)


sightseeing_planner_agent = Agent(
    role="Sightseeing & Activities Planner",
    goal="Build a day-by-day activity plan and output it as a JSON array.",
    backstory=(
        "You are a passionate local guide. You know the must-see sights, hidden gems, "
        "and best food spots, and you cluster them geographically to avoid backtracking. "
        "You always output a valid JSON array of day objects with activities."
    ),
    memory=False,
    verbose=True,
    allow_delegation=False,
    max_iter=5,
    tools=[attraction_search_tool, distance_clustering_tool],
    llm=primary_llm,
)


itinerary_assembler_agent = Agent(
    role="Itinerary Assembler",
    goal="Merge the route skeleton, transit, stay, and sightseeing outputs into one coherent final itinerary JSON.",
    backstory=(
        "You are a meticulous travel coordinator. You take a route skeleton, transit legs, "
        "accommodation options, and day-by-day activities, then produce a single validated itinerary. "
        "You fix mismatches (e.g., activities far from the day's region), consolidate duplicate hotels, "
        "add inclusions/exclusions/notes, and ensure every day has activities and a stay. "
        "You always output valid JSON matching the requested schema."
    ),
    memory=False,
    verbose=True,
    allow_delegation=False,
    max_iter=5,
    llm=primary_llm,
)
