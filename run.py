"""Простой запуск проекта.

    python run.py
"""
from bot.main import main
import asyncio

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
