from crewai import Agent, Crew, Process, Task
from app.crew.tasks import (
    parse_input_task,
    build_skeleton_task,
    select_transit_mode_task,
    plan_travel_task,
    plan_stay_task,
    plan_sightseeing_task,
    assemble_itinerary_task,
)


def _request_local(agent_template, task_template):
    """Clone legacy templates so no mutable Agent or Task crosses requests."""
    agent = Agent(
        role=agent_template.role,
        goal=agent_template.goal,
        backstory=agent_template.backstory,
        cache=agent_template.cache,
        verbose=agent_template.verbose,
        max_rpm=agent_template.max_rpm,
        allow_delegation=agent_template.allow_delegation,
        tools=list(agent_template.tools),
        max_iter=agent_template.max_iter,
        llm=agent_template.llm,
        max_execution_time=agent_template.max_execution_time,
        max_retry_limit=agent_template.max_retry_limit,
    )
    task = Task(
        description=task_template.description,
        expected_output=task_template.expected_output,
        agent=agent,
        async_execution=task_template.async_execution,
        output_json=task_template.output_json,
        output_pydantic=task_template.output_pydantic,
        callback=task_template.callback,
        tools=list(task_template.tools or []),
    )
    # The old specialist tasks referenced the parser task even though it was not
    # part of their Crew. Inputs are now passed explicitly by each request.
    task.context = []
    return agent, task


def _crew(agent_template, task_template) -> Crew:
    agent, task = _request_local(agent_template, task_template)
    return Crew(agents=[agent], tasks=[task], process=Process.sequential, memory=False, verbose=False)
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
    return _crew(input_parser_agent, parse_input_task)


def build_skeleton_crew() -> Crew:
    """Itinerary architect crew that builds a day-by-day route skeleton."""
    return _crew(itinerary_architect_agent, build_skeleton_task)


def build_travel_crew() -> Crew:
    """Transit planner crew (runs after the mode selector decision is known)."""
    return _crew(travel_planner_agent, plan_travel_task)


def build_transit_mode_crew() -> Crew:
    """Single-agent crew that picks flight/train/bus for the main route."""
    return _crew(transit_mode_selector_agent, select_transit_mode_task)


def build_stay_crew() -> Crew:
    """Accommodation planner crew (runs after parsing)."""
    return _crew(stay_planner_agent, plan_stay_task)


def build_sightseeing_crew() -> Crew:
    """Sightseeing planner crew (runs after parsing)."""
    return _crew(sightseeing_planner_agent, plan_sightseeing_task)


def build_assembly_crew() -> Crew:
    """Final assembler crew that merges skeleton, transit, stay, and sightseeing into one itinerary."""
    return _crew(itinerary_assembler_agent, assemble_itinerary_task)
