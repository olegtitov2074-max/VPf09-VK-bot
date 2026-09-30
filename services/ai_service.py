"""Централизованный AIService: работа с LLM через OpenAI-совместимый ProxyAPI.

- Легко заменить модель (поле settings.AI_MODEL).
- Легко добавить новую модель/провайдера: достаточно реализовать
  протокол BaseAIProvider и зарегистрировать его в AIService.
"""
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from openai import AsyncOpenAI

from config import get_settings
from services.context import build_context

if TYPE_CHECKING:
    from models.dialogue import Dialogue

logger = logging.getLogger(__name__)


class BaseAIProvider(ABC):
    """Абстрактный провайдер LLM."""

    @abstractmethod
    async def generate(self, context: dict[str, Any]) -> str:
        """Отправляет контекст модели и возвращает текст ответа."""
        raise NotImplementedError


class OpenAIProvider(BaseAIProvider):
    """Провайдер OpenAI-совместимого API через ProxyAPI.ru."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = AsyncOpenAI(
            api_key=settings.AI_API_KEY,
            base_url=settings.AI_BASE_URL,
            timeout=60.0,  # секунды, чтобы не зависать надолго
        )
        self._model = settings.AI_MODEL
        logger.info("AI-провайдер инициализирован: модель %s, base_url=%s",
                    self._model, settings.AI_BASE_URL)

    @staticmethod
    def _to_messages(context: dict[str, Any]) -> list[dict[str, str]]:
        """Переводит контекст build_context() в формат OpenAI chat completions."""
        messages: list[dict[str, str]] = []
        system_instruction = context.get("system_instruction")
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        for item in context.get("contents", []):
            role = "assistant" if item.get("role") == "model" else "user"
            parts = item.get("parts") or []
            text = parts[0].get("text", "") if parts else ""
            messages.append({"role": role, "content": text})
        return messages

    async def generate(self, context: dict[str, Any]) -> str:
        """Генерация ответа моделью (асинхронно)."""
        context_messages = self._to_messages(context)
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=context_messages,
        )
        if not response.choices:
            raise RuntimeError("Модель вернула пустой ответ (нет choices)")
        return response.choices[0].message.content or ""


class AIService:
    """Сервис, который знает о режиме и провайдерах.

    Предоставляет единую точку вызова генерации ответа.
    """

    def __init__(self, provider: BaseAIProvider | None = None) -> None:
        self.settings = get_settings()
        self._provider = provider or OpenAIProvider()

    def set_provider(self, provider: BaseAIProvider) -> None:
        """Позволяет подменить провайдера в рантайме (для будущих моделей)."""
        self._provider = provider
        logger.info("Провайдер заменён на %s", type(provider).__name__)

    @property
    def model(self) -> str:
        return self.settings.AI_MODEL

    async def generate_reply(
        self,
        dialogue: "Dialogue",
        user_message: str,
    ) -> str:
        """Формирует контекст, вызывает модель и возвращает ответ.

        Обрабатывает ошибки API и сетевые сбои, возвращает fallback.
        """
        context = build_context(dialogue, user_message)
        try:
            reply = await self._provider.generate(context)
            reply = reply.strip()
            if not reply:
                raise RuntimeError("Пустой ответ модели")
            return reply
        except Exception as exc:  # noqa: BLE001 — единая точка fallback
            logger.exception("Ошибка при генерации ответа: %s", exc)
            return (
                "😔 Не удалось получить ответ от ИИ. Возможно, проблема "
                "с сетью или сервисом. Попробуйте ещё раз через несколько секунд."
            )
