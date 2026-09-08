from crewai import Crew, Process
from app.crew.tasks import (
    parse_input_task,
    build_skeleton_task,
    select_transit_mode_task,
    plan_travel_task,
    plan_stay_task,
    plan_sightseeing_task,
    assemble_itinerary_task,
)
from app.crew.agents import (
    input_parser_agent,
    itinerary_architect_agent,
    travel_planner_agent,
    transit_mode_selector_agent,
    stay_planner_agent,
    sightseeing_planner_agent,
    itinerary_assembler_agent,
)


def build_parse_crew() -> Crew:
    """Single-agent crew that extracts structured fields from raw input."""
    return Crew(
        agents=[input_parser_agent],
        tasks=[parse_input_task],
        process=Process.sequential,
        memory=False,
        verbose=True,
    )


def build_skeleton_crew() -> Crew:
    """Itinerary architect crew that builds a day-by-day route skeleton."""
    return Crew(
        agents=[itinerary_architect_agent],
        tasks=[build_skeleton_task],
        process=Process.sequential,
        memory=False,
        verbose=True,
    )


def build_travel_crew() -> Crew:
    """Transit planner crew (runs after the mode selector decision is known)."""
    return Crew(
        agents=[travel_planner_agent],
        tasks=[plan_travel_task],
        process=Process.sequential,
        memory=False,
        verbose=True,
    )


def build_transit_mode_crew() -> Crew:
    """Single-agent crew that picks flight/train/bus for the main route."""
    return Crew(
        agents=[transit_mode_selector_agent],
        tasks=[select_transit_mode_task],
        process=Process.sequential,
        memory=False,
        verbose=True,
    )


def build_stay_crew() -> Crew:
    """Accommodation planner crew (runs after parsing)."""
    return Crew(
        agents=[stay_planner_agent],
        tasks=[plan_stay_task],
        process=Process.sequential,
        memory=False,
        verbose=True,
    )


def build_sightseeing_crew() -> Crew:
    """Sightseeing planner crew (runs after parsing)."""
    return Crew(
        agents=[sightseeing_planner_agent],
        tasks=[plan_sightseeing_task],
        process=Process.sequential,
        memory=False,
        verbose=True,
    )


def build_assembly_crew() -> Crew:
    """Final assembler crew that merges skeleton, transit, stay, and sightseeing into one itinerary."""
    return Crew(
        agents=[itinerary_assembler_agent],
        tasks=[assemble_itinerary_task],
        process=Process.sequential,
        memory=False,
        verbose=True,
    )
