from crewai import Crew, Process
from app.crew.tasks import (
    parse_input_task,
    build_skeleton_task,
    plan_travel_task,
    plan_stay_task,
    plan_sightseeing_task,
)
from app.crew.agents import (
    input_parser_agent,
    itinerary_architect_agent,
    travel_planner_agent,
    stay_planner_agent,
    sightseeing_planner_agent,
)


def build_mvp_crew() -> Crew:
    """Factory that returns the configured 4-agent MVP crew (sequential)."""
    return Crew(
        agents=[
            input_parser_agent,
            travel_planner_agent,
            stay_planner_agent,
            sightseeing_planner_agent,
        ],
        tasks=[
            parse_input_task,
            plan_travel_task,
            plan_stay_task,
            plan_sightseeing_task,
        ],
        process=Process.sequential,
        memory=False,
        verbose=True,
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
    """Transit planner crew (runs after parsing)."""
    return Crew(
        agents=[travel_planner_agent],
        tasks=[plan_travel_task],
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
