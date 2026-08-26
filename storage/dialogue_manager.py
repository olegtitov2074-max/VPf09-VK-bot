"""Менеджер диалогов: операции над диалогами пользователя.

Класс инкапсулирует бизнес-логику работы с диалогами и памятью.
Хранит ссылку на UserStore и точку сохранения данных.
"""
import logging
from typing import TYPE_CHECKING

from models.dialogue import Dialogue
from models.roles import DEFAULT_ROLE_KEY
from storage.user_store import UserStore
from config import get_settings

if TYPE_CHECKING:
    from models.user import UserData

logger = logging.getLogger(__name__)


class DialogueManager:
    """Высокоуровневые операции над диалогами и памятью пользователей."""

    def __init__(self, store: UserStore) -> None:
        self.store = store
        self.settings = get_settings()

    async def get_user(self, user_id: int) -> "UserData":
        return await self.store.get_or_create(user_id)

    async def create_dialogue(self, user_id: int, role: str = DEFAULT_ROLE_KEY) -> Dialogue:
        """Создаёт новый диалог и делает его активным."""
        user = await self.get_user(user_id)
        title = f"Диалог {len(user.dialogues) + 1}"
        dialogue = user.create_dialogue(title=title, role=role)
        await self.store.save(user)
        logger.info("Пользователь %s создал диалог %s", user_id, dialogue.id)
        return dialogue

    async def rename_dialogue(self, user_id: int, dialogue_id: str, title: str) -> bool:
        """Переименовывает диалог."""
        user = await self.get_user(user_id)
        dialogue = user.dialogues.get(dialogue_id)
        if dialogue is None:
            return False
        dialogue.title = title.strip() or dialogue.title
        await self.store.save(user)
        return True

    async def switch_dialogue(self, user_id: int, dialogue_id: str) -> bool:
        """Переключает активный диалог."""
        user = await self.get_user(user_id)
        if user.set_active(dialogue_id):
            await self.store.save(user)
            return True
        return False

    async def delete_dialogue(self, user_id: int, dialogue_id: str) -> bool:
        """Удаляет диалог."""
        user = await self.get_user(user_id)
        removed = user.delete_dialogue(dialogue_id)
        if removed:
            await self.store.save(user)
            logger.info("Пользователь %s удалил диалог %s", user_id, dialogue_id)
        return removed

    async def list_dialogues(self, user_id: int) -> list[Dialogue]:
        """Возвращает список диалогов пользователя."""
        user = await self.get_user(user_id)
        return list(user.dialogues.values())

    async def set_role(self, user_id: int, dialogue_id: str, role_key: str) -> bool:
        """Меняет роль (режим общения) у конкретного диалога."""
        user = await self.get_user(user_id)
        dialogue = user.dialogues.get(dialogue_id)
        if dialogue is None:
            return False
        from models.roles import ROLES
        if role_key not in ROLES:
            return False
        dialogue.role = role_key
        await self.store.save(user)
        logger.info(
            "Пользователь %s сменил режим диалога %s на %s",
            user_id, dialogue_id, role_key,
        )
        return True

    async def set_active_role(self, user_id: int, role_key: str) -> bool:
        """Задаёт роль активному диалогу."""
        user = await self.get_user(user_id)
        dialogue = user.get_active_dialogue()
        if dialogue is None:
            return False
        from models.roles import ROLES
        if role_key not in ROLES:
            return False
        dialogue.role = role_key
        await self.store.save(user)
        return True

    async def clear_history(self, user_id: int, dialogue_id: str | None = None) -> bool:
        """Очищает историю (активного диалога или конкретного)."""
        user = await self.get_user(user_id)
        if dialogue_id is None:
            dialogue = user.get_active_dialogue()
        else:
            dialogue = user.dialogues.get(dialogue_id)
        if dialogue is None:
            return False
        dialogue.clear_history()
        await self.store.save(user)
        return True

    async def add_message(self, user_id: int, role: str, content: str) -> Dialogue | None:
        """Добавляет сообщение в активный диалог и сохраняет."""
        user = await self.get_user(user_id)
        dialogue = user.get_active_dialogue()
        if dialogue is None:
            return None
        user.settings.max_history = self.settings.MAX_HISTORY
        dialogue.add_message(role, content)
        await self.store.save(user)
        return dialogue