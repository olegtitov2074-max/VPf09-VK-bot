"""Централизованный AIService: работа с LLM через Google GenAI SDK и ProxyAPI.

- Легко заменить модель (поле settings.GEMINI_MODEL).
- Легко добавить новую модель/провайдера: достаточно реализовать
  протокол BaseAIProvider и зарегистрировать его в AIService.
"""
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

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


class GeminiProvider(BaseAIProvider):
    """Провайдер Gemini через ProxyAPI.ru (совместим с Google GenAI SDK)."""

    def __init__(self) -> None:
        from google import genai  # импорт только при реальном использовании

        settings = get_settings()
        self._client = genai.Client(
            api_key=settings.GEMINI_API_KEY,
            http_options={
                "api_version": settings.API_VERSION,
                "base_url": settings.GEMINI_BASE_URL,
                "timeout": 60_000,  # миллисекунды, чтобы не зависать надолго
                # ProxyAPI ожидает Authorization: Bearer, а SDK по умолчанию
                # шлёт ключ в x-goog-api-key. Добавляем оба заголовка.
                "headers": {
                    "Authorization": f"Bearer {settings.GEMINI_API_KEY}",
                },
            },
        )
        self._model = settings.GEMINI_MODEL
        logger.info("AI-провайдер инициализирован: модель %s, base_url=%s",
                    self._model, settings.GEMINI_BASE_URL)

    async def generate(self, context: dict[str, Any]) -> str:
        """Генерация контента Gemini (асинхронно)."""
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=context["system_instruction"],
        )
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=context["contents"],
            config=config,
        )
        if not response.candidates:
            raise RuntimeError("Модель вернула пустой ответ (нет candidates)")
        return response.text or ""


class AIService:
    """Сервис, который знает о режиме и провайдерах.

    Предоставляет единую точку вызова генерации ответа.
    """

    def __init__(self, provider: BaseAIProvider | None = None) -> None:
        self.settings = get_settings()
        self._provider = provider or GeminiProvider()

    def set_provider(self, provider: BaseAIProvider) -> None:
        """Позволяет подменить провайдера в рантайме (для будущих моделей)."""
        self._provider = provider
        logger.info("Провайдер заменён на %s", type(provider).__name__)

    @property
    def model(self) -> str:
        return self.settings.GEMINI_MODEL

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