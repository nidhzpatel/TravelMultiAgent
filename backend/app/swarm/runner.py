from typing import Any
import logging
import uuid

logger = logging.getLogger(__name__)

from app.config import get_settings
from app.llm import get_chat_llm
from app.swarm.blackboard import Blackboard
from app.swarm.message import Message
from app.swarm.agents import (
    ConciergeAgent,
    OrchestratorAgent,
    ItineraryArchitectAgent,
    TransitAgent,
    StayAgent,
    ExperienceAgent,
    ResearchAgent,
    CriticAgent,
)

settings = get_settings()


class SwarmRunner:
    """Runs the multi-agent swarm for a single conversation turn."""

    MAX_ITERATIONS = 20

    def __init__(self, blackboard: Blackboard):
        self.blackboard = blackboard
        self.llm = get_chat_llm()

        self.agents: dict[str, Any] = {
            "Concierge": ConciergeAgent(blackboard, self.llm),
            "Orchestrator": OrchestratorAgent(blackboard, self.llm),
            "ItineraryArchitect": ItineraryArchitectAgent(blackboard, self.llm),
            "TransitAgent": TransitAgent(blackboard, self.llm),
            "StayAgent": StayAgent(blackboard, self.llm),
            "ExperienceAgent": ExperienceAgent(blackboard, self.llm),
            "ResearchAgent": ResearchAgent(blackboard, self.llm),
            "Critic": CriticAgent(blackboard, self.llm),
        }

    def run(self, user_input: str) -> dict[str, Any]:
        """Inject a user message and run the swarm until a response is ready."""
        concierge = self.agents["Concierge"]
        concierge.receive(
            Message(
                sender="User",
                recipient="Concierge",
                task="user_message",
                payload={"user_input": user_input},
            )
        )

        iterations = 0
        trace_id = uuid.uuid4().hex
        while iterations < self.MAX_ITERATIONS:
            iterations += 1

            # Find an agent with messages to process.
            processed = False
            for agent in self.agents.values():
                if agent.inbox:
                    logger.info("swarm_step trace_id=%s iteration=%d agent=%s inbox_count=%d",
                                trace_id, iterations, agent.name, len(agent.inbox))
                    result = agent.run()

                    # If the Concierge has a direct response, return it.
                    if agent.name == "Concierge" and result is not None:
                        return result

                    # Dispatch outbox messages to recipient agents.
                    for message in agent.pop_messages():
                        recipient = self.agents.get(message.recipient)
                        if recipient:
                            recipient.receive(message)

                    processed = True

            if not processed:
                break

        # If the swarm finished without a concierge response, build a fallback.
        return {
            "type": "text",
            "message": "I couldn't complete that request. Your previous itinerary is unchanged. Please specify the day and change you want.",
        }
