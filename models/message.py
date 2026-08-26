"""Модель сообщения в истории диалога."""
from dataclasses import dataclass, asdict
from time import time
from typing import Any


@dataclass
class Message:
    """Одно сообщение в истории диалога.

    role: 'user' | 'assistant' | 'system'
    content: текст сообщения
    timestamp: unix-время
    """
    role: str
    content: str
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = time()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp", time()),
        )