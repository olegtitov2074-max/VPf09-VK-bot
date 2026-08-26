"""Модель диалога."""
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from models.message import Message
from models.roles import DEFAULT_ROLE_KEY


@dataclass
class Dialogue:
    """Один независимый диалог пользователя.

    id: уникальный идентификатор
    title: название диалога
    role: ключ роли (режима общения)
    created_at: unix-время создания
    messages: список сообщений истории
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    title: str = "Новый диалог"
    role: str = DEFAULT_ROLE_KEY
    created_at: float = field(default_factory=lambda: 0.0)
    messages: list[Message] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.created_at:
            from time import time
            self.created_at = time()

    def add_message(self, role: str, content: str) -> Message:
        """Добавляет сообщение в историю и обрезает до MAX_HISTORY."""
        from config import get_settings
        settings = get_settings()

        msg = Message(role=role, content=content)
        self.messages.append(msg)
        # Автоматически удаляем старые сообщения, оставляя MAX_HISTORY последних
        if len(self.messages) > settings.MAX_HISTORY:
            self.messages = self.messages[-settings.MAX_HISTORY:]
        return msg

    def clear_history(self) -> None:
        """Очищает историю сообщений диалога."""
        self.messages.clear()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "role": self.role,
            "created_at": self.created_at,
            "messages": [m.to_dict() for m in self.messages],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Dialogue":
        return cls(
            id=data["id"],
            title=data.get("title", "Новый диалог"),
            role=data.get("role", DEFAULT_ROLE_KEY),
            created_at=data.get("created_at", 0.0),
            messages=[
                Message.from_dict(m) for m in data.get("messages", [])
            ],
        )