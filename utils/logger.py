"""Настройка логирования."""
import logging
import sys

from config import get_settings


def setup_logging() -> logging.Logger:
    """Инициализирует корневой логгер и возвращает его."""
    settings = get_settings()
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        root.addHandler(handler)
    root.setLevel(level)

    # Подавляем лишний шум у сторонних библиотек
    for noisy in ("google.genai", "urllib3", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return root