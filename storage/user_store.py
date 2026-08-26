"""JSON-хранилище: по одному файлу на пользователя в data/users/."""
import json
import logging
import os
import threading
import uuid
from pathlib import Path

import aiofiles

from config import get_settings
from models.user import UserData

logger = logging.getLogger(__name__)


class UserStore:
    """Менеджер JSON-памяти.

    - один JSON-файл на пользователя в папке users/
    - ленивая загрузка в кэш при обращении
    - асинхронная запись на диск через aiofiles
    """

    def __init__(self, storage_dir: str | None = None) -> None:
        settings = get_settings()
        self.storage_dir = Path(storage_dir or settings.STORAGE_DIR)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        # Кэш user_id -> UserData (пока файл не изменён)
        self._cache: dict[int, UserData] = {}
        # Блокировка для защиты кэша от гонок
        self._lock = threading.Lock()

    def _user_path(self, user_id: int) -> Path:
        return self.storage_dir / f"{user_id}.json"

    async def get_or_create(self, user_id: int) -> UserData:
        """Возвращает данные пользователя. Если нет — создаёт и сохраняет."""
        with self._lock:
            user = self._cache.get(user_id)
        if user is not None:
            return user

        path = self._user_path(user_id)
        if path.exists():
            user = await self._load(path)
        else:
            user = UserData(user_id=user_id)
            await self._dump(path, user)

        with self._lock:
            self._cache[user_id] = user
        return user

    async def save(self, user: UserData) -> None:
        """Сохраняет пользователя на диск и в кэш."""
        with self._lock:
            self._cache[user.user_id] = user
        await self._dump(self._user_path(user.user_id), user)

    async def _load(self, path: Path) -> UserData:
        """Читает JSON и восстанавливает UserData."""
        async with aiofiles.open(path, mode="r", encoding="utf-8") as f:
            raw = await f.read()
        data = json.loads(raw)
        return UserData.from_dict(data)

    async def _dump(self, path: Path, user: UserData) -> None:
        """Атомарно пишет JSON на диск (через временный файл)."""
        tmp = path.with_suffix(".tmp")
        data = user.to_dict()
        async with aiofiles.open(tmp, mode="w", encoding="utf-8") as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=2))
        os.replace(tmp, path)

    async def save_all(self) -> None:
        """Сохраняет весь кэш на диск (вызывается при остановке)."""
        with self._lock:
            users = list(self._cache.values())
        await self.save_batch(users)

    async def save_batch(self, users: list[UserData]) -> None:
        for user in users:
            try:
                await self._dump(self._user_path(user.user_id), user)
            except Exception:
                logger.exception("Не удалось сохранить пользователя %s", user.user_id)


def new_id() -> str:
    """Генерирует короткий uuid для id диалога/файла."""
    return str(uuid.uuid4())