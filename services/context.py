"""Формирование context window для запроса к модели."""
from typing import Any

from config import get_settings
from models.dialogue import Dialogue
from models.roles import get_role


def build_context(
    dialogue: Dialogue,
    user_message: str | None = None,
) -> dict[str, Any]:
    """Собирает контекст из истории активного диалога.

    Возвращает структуру для google-genai SDK:
      {
        "system_instruction": "...",
        "contents": [{"role": "user"|"model", "parts": [{"text": "..."}]}, ...]
      }
    """
    settings = get_settings()
    role = get_role(dialogue.role)

    # История диалога (последние MAX_HISTORY уже обеспечены менеджером памяти)
    contents: list[dict[str, Any]] = []
    for msg in dialogue.messages:
        gemini_role = "model" if msg.role == "assistant" else "user"
        if msg.role == "system":
            continue
        contents.append(
            {"role": gemini_role, "parts": [{"text": msg.content[:settings.MESSAGE_LIMIT]}]}
        )

    # Текущий вопрос пользователя (будет добавлен позже)
    if user_message:
        contents.append(
            {"role": "user", "parts": [{"text": user_message[:settings.MESSAGE_LIMIT]}]}
        )

    # Если истории нет — добавляем системный промпт как отдельный user маркер,
    # чтобы у модели всегда был контекст роли (для совместимости SDK).
    if not contents and not user_message:
        contents.append({"role": "user", "parts": [{"text": "..."}]})

    return {
        "system_instruction": role.system_prompt,
        "contents": contents,
    }