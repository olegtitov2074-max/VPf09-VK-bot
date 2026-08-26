"""Точка входа: запуск VK-бота.

Запуск:
    python -m bot.main
или
    python bot/main.py
"""
import asyncio
import logging

from vkbottle import Bot

from bot.handlers import register_handlers
from config import get_settings
from services.ai_service import AIService
from storage.dialogue_manager import DialogueManager
from storage.user_store import UserStore
from utils.logger import setup_logging

logger = logging.getLogger(__name__)


async def main() -> None:
    setup_logging()
    settings = get_settings()

    logger.info("Запуск бота для группы %s", settings.GROUP_ID)

    bot = Bot(token=settings.VK_TOKEN)

    # Слои зависимостей (чистая архитектура, снизу вверх)
    store = UserStore()                       # хранилище (JSON)
    dialogue_manager = DialogueManager(store)  # бизнес-логика диалогов
    ai_service = AIService()                   # сервис ИИ

    register_handlers(bot, dialogue_manager, ai_service, settings)

    try:
        await bot.run_polling()
    finally:
        logger.info("Остановка бота, сохраняем данные...")
        await store.save_all()
        logger.info("Данные сохранены. До встречи!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Остановлено пользователем.")
