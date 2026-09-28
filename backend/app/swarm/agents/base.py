from abc import ABC, abstractmethod
from typing import Any
import logging
import time

logger = logging.getLogger(__name__)

from app.swarm.message import Message
from app.swarm.blackboard import Blackboard


class BaseAgent(ABC):
    """Base class for all swarm agents.

    Each agent has an inbox of messages, access to the shared blackboard,
    and the ability to send messages to other agents.
    """

    name: str = "base"

    def __init__(self, blackboard: Blackboard, llm: Any | None = None):
        self.blackboard = blackboard
        self.llm = llm
        self.inbox: list[Message] = []
        self.outbox: list[Message] = []

    def receive(self, message: Message) -> None:
        self.inbox.append(message)

    def send(self, recipient: str, task: str, payload: dict[str, Any] | None = None) -> None:
        message = Message(
            sender=self.name,
            recipient=recipient,
            task=task,
            payload=payload or {},
        )
        self.outbox.append(message)

    def pop_messages(self) -> list[Message]:
        messages = self.outbox
        self.outbox = []
        return messages

    @abstractmethod
    def run(self) -> dict[str, Any] | None:
        """Process the next message in the inbox and optionally return a result."""
        raise NotImplementedError

    def _next_message(self) -> Message | None:
        if not self.inbox:
            return None
        return self.inbox.pop(0)

    def _llm_invoke(self, prompt: str) -> str:
        """Call the shared LLM if available."""
        if self.llm is None:
            return ""
        started = time.perf_counter()
        try:
            response = str(self.llm.invoke(prompt).content)
            logger.info("swarm_llm agent=%s outcome=ok prompt_chars=%d response_chars=%d elapsed_ms=%d",
                        self.name, len(prompt), len(response), (time.perf_counter() - started) * 1000)
            return response
        except Exception as exc:
            logger.warning("swarm_llm agent=%s outcome=error error_type=%s elapsed_ms=%d",
                           self.name, type(exc).__name__, (time.perf_counter() - started) * 1000)
            return ""

    def _context(self, current: dict[str, Any] | None) -> str:
        import json
        return json.dumps({
            "itinerary": current,
            "recent_conversation": self.blackboard.get("conversation", []),
            "evidence_status": "Unverified planning estimates; no live inventory was retrieved for this turn.",
        })
