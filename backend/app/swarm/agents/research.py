import json
from typing import Any

from app.swarm.agents.base import BaseAgent


class ResearchAgent(BaseAgent):
    """Answers general travel questions using knowledge and optionally search."""

    name = "ResearchAgent"

    def run(self) -> dict[str, Any] | None:
        message = self._next_message()
        if message is None:
            return None

        task = message.task
        payload = message.payload
        user_input = payload.get("user_input", "")

        if task == "answer_question":
            answer = self._answer(user_input)
            self.send(
                "Orchestrator",
                "agent_result",
                {
                    "sender": self.name,
                    "type": "answer",
                    "answer": answer,
                },
            )
            return None

        return None

    def _answer(self, user_input: str) -> str:
        prompt = (
            "You are a knowledgeable travel assistant. Answer the user's question in plain natural language.\n\n"
            f"User question: {user_input}\n\n"
            "Respond in 1-3 sentences. Do not use JSON or bullet points. "
            "If you don't know, say so honestly. Do not make up specific prices or schedules."
        )
        raw = self._llm_invoke(prompt)
        # Strip JSON wrapping if the model returns one anyway.
        import re
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, dict):
                    return " ".join(str(v) for v in parsed.values())
            except Exception:
                pass
        return raw
