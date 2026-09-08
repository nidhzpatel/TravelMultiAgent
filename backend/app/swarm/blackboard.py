from typing import Any
from copy import deepcopy


class Blackboard:
    """Shared memory for the swarm.

    Agents read the latest state and write updates. The blackboard is also
    useful for persisting intermediate results like transit options, hotel
    options, and the current itinerary.
    """

    def __init__(self, initial_data: dict[str, Any] | None = None):
        self._data: dict[str, Any] = deepcopy(initial_data) or {}

    def get(self, key: str, default: Any = None) -> Any:
        return deepcopy(self._data.get(key, default))

    def set(self, key: str, value: Any) -> None:
        self._data[key] = deepcopy(value)

    def update(self, updates: dict[str, Any]) -> None:
        for key, value in updates.items():
            self._data[key] = deepcopy(value)

    def has(self, key: str) -> bool:
        return key in self._data

    def snapshot(self) -> dict[str, Any]:
        return deepcopy(self._data)
