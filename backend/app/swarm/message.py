from dataclasses import dataclass, field
from typing import Any
from datetime import datetime
import uuid


@dataclass
class Message:
    """A message passed from one agent to another in the swarm."""

    sender: str
    recipient: str
    task: str
    payload: dict[str, Any] = field(default_factory=dict)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def __repr__(self) -> str:
        return f"Message({self.sender} -> {self.recipient}: {self.task})"
