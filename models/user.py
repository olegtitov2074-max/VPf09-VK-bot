"""Модель пользователя и всех его данных."""
from dataclasses import dataclass, field
from typing import Any
from time import time

from models.dialogue import Dialogue
from models.roles import DEFAULT_ROLE_KEY


@dataclass
class UserSettings:
    """Настройки пользователя."""
    model: str = ""
    max_history: int = 100

    def to_dict(self) -> dict[str, Any]:
        return {"model": self.model, "max_history": self.max_history}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserSettings":
        return cls(
            model=data.get("model", ""),
            max_history=data.get("max_history", 100),
        )


@dataclass
class UserData:
    """Все данные пользователя: диалоги, активный диалог, настройки."""
    user_id: int
    dialogues: dict[str, Dialogue] = field(default_factory=dict)
    active_dialogue_id: str = ""
    settings: UserSettings = field(default_factory=UserSettings)
    created_at: float = field(default_factory=lambda: time())

    def get_active_dialogue(self) -> Dialogue | None:
        """Возвращает активный диалог или None."""
        return self.dialogues.get(self.active_dialogue_id)

    def set_active(self, dialogue_id: str) -> bool:
        """Делает диалог активным. Возвращает True если найден."""
        if dialogue_id in self.dialogues:
            self.active_dialogue_id = dialogue_id
            return True
        return False

    def create_dialogue(self, title: str = "Новый диалог", role: str = DEFAULT_ROLE_KEY) -> Dialogue:
        """Создаёт новый диалог, делает его активным и возвращает."""
        dialogue = Dialogue(title=title, role=role)
        self.dialogues[dialogue.id] = dialogue
        self.active_dialogue_id = dialogue.id
        return dialogue

    def delete_dialogue(self, dialogue_id: str) -> bool:
        """Удаляет диалог. Если удалили активный — выбирает другой."""
        if dialogue_id not in self.dialogues:
            return False
        del self.dialogues[dialogue_id]
        if self.active_dialogue_id == dialogue_id:
            # выбираем первый оставшийся или пустую строку
            remaining = list(self.dialogues.keys())
            self.active_dialogue_id = remaining[0] if remaining else ""
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "dialogues": {did: d.to_dict() for did, d in self.dialogues.items()},
            "active_dialogue_id": self.active_dialogue_id,
            "settings": self.settings.to_dict(),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserData":
        return cls(
            user_id=data["user_id"],
            dialogues={
                did: Dialogue.from_dict(d)
                for did, d in data.get("dialogues", {}).items()
            },
            active_dialogue_id=data.get("active_dialogue_id", ""),
            settings=UserSettings.from_dict(data.get("settings", {})),
            created_at=data.get("created_at", time()),
        )