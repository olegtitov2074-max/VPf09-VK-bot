"""Обработчики сообщений и callback-событий VK.

Используется актуальный API vkbottle 4.x:
  - @bot.on.message           → входящее сообщение (Message)
  - @bot.on.raw_event(...)    → callback от кнопок (MessageEventObject)

Чистое разделение: здесь нет логики AI напрямую — только оркестрация
между пользователем, менеджером диалогов и AIService.
"""
import logging
from typing import Any

from vkbottle import Bot, GroupEventType, GroupTypes
from vkbottle.bot import Message

from config import Settings
from keyboards.vk import (
    dialogue_list,
    help_info,
    main_menu,
    role_menu,
    settings_menu,
)
from models.roles import get_role
from services.ai_service import AIService
from storage.dialogue_manager import DialogueManager

logger = logging.getLogger(__name__)

# Тексты команд, которые не отправляются в ИИ
MENU_COMMANDS = {"меню", "начать", "start", "/start", "hi", "привет-бот"}
NEW_DIALOGUE_COMMANDS = {"новый диалог", "новая беседа", "/new"}
LIST_COMMANDS = {"диалоги", "список", "/list"}
SETTINGS_COMMANDS = {"настройки", "/settings"}
ROLES_COMMANDS = {"режим", "сменить режим", "роли", "/role"}
HELP_COMMANDS = {"помощь", "справка", "/help"}


class InputState:
    """Простое in-memory состояние для ввода от пользователя (переименование)."""

    def __init__(self) -> None:
        self._states: dict[int, dict[str, Any]] = {}

    def set(self, user_id: int, action: str, **data: Any) -> None:
        self._states[user_id] = {"action": action, **data}

    def get(self, user_id: int) -> dict[str, Any] | None:
        return self._states.get(user_id)

    def clear(self, user_id: int) -> None:
        self._states.pop(user_id, None)


# ──────────────────────── Утилиты ▼

async def _send(
    bot: Bot,
    peer_id: int,
    text: str,
    keyboard=None,
) -> None:
    """Универсальная отправка сообщения с клавиатурой."""
    kwargs: dict[str, Any] = {
        "peer_id": peer_id,
        "message": text,
        "random_id": 0,
    }
    if keyboard is not None:
        kwargs["keyboard"] = keyboard.get_json()
    await bot.api.messages.send(**kwargs)


async def _typing(bot: Bot, peer_id: int, settings: Settings) -> None:
    """Ставит статус «печатает...» у бота."""
    try:
        await bot.api.messages.set_activity(
            group_id=settings.GROUP_ID,
            peer_id=peer_id,
            type="typing",
        )
    except Exception:  # noqa: BLE001 — статус не критичен
        logger.debug("Не удалось установить typing-статус", exc_info=True)


def _split_text(text: str, limit: int) -> list[str]:
    """Разбивает длинный текст на части не длиннее limit."""
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    while text:
        cut = text[:limit]
        # стараемся разрезать по переносу строки
        nl = cut.rfind("\n")
        if nl > limit * 0.5:
            parts.append(text[:nl])
            text = text[nl + 1 :]
        else:
            parts.append(cut)
            text = text[limit:]
    return parts


async def _answer_ai(
    bot: Bot,
    peer_id: int,
    user_id: int,
    text: str,
    dm: DialogueManager,
    ai: AIService,
    settings: Settings,
) -> None:
    """Полный цикл ответа ИИ: сохранение вопроса, генерация, сохранение ответа."""
    text = text.strip()
    if not text:
        await _send(bot, peer_id, "⚠️ Пустое сообщение. Напишите что-нибудь 🙂")
        return
    if len(text) > settings.MESSAGE_LIMIT:
        await _send(
            bot, peer_id,
            f"⚠️ Сообщение слишком длинное (максимум {settings.MESSAGE_LIMIT} символов).",
        )
        return

    # Гарантируем наличие активного диалога
    user = await dm.get_user(user_id)
    if user.get_active_dialogue() is None:
        await dm.create_dialogue(user_id)

    dialogue = await dm.add_message(user_id, "user", text)
    if dialogue is None:
        await _send(bot, peer_id, "❌ Не удалось создать диалог.")
        return

    # Имитация набора текста
    await _typing(bot, peer_id, settings)

    reply = await ai.generate_reply(dialogue, text)

    # Дробим длинный ответ на части (лимит VK ~4096)
    for chunk in _split_text(reply, settings.MESSAGE_LIMIT):
        await _send(bot, peer_id, chunk)

    # Сохраняем ответ ассистента в историю
    await dm.add_message(user_id, "assistant", reply)


def register_handlers(
    bot: Bot,
    dm: DialogueManager,
    ai: AIService,
    settings: Settings,
) -> None:
    """Регистрирует все обработчики на боте."""
    state = InputState()

    # ──────────────────────── Текстовые сообщения ▼

    @bot.on.message()
    async def handle_message(event: Message) -> None:
        peer_id = event.peer_id
        user_id = event.from_id
        text = (event.text or "").strip()

        # Сначала проверяем состояние ввода (переименование)
        st = state.get(user_id)
        if st and st.get("action") == "rename":
            dialogue_id = st.get("dialogue_id", "")
            state.clear(user_id)
            ok = await dm.rename_dialogue(user_id, dialogue_id, text)
            if ok:
                await _send(bot, peer_id, f"✅ Диалог переименован в «{text}»")
            else:
                await _send(bot, peer_id, "❌ Не удалось переименовать диалог.")
            return

        low = text.lower()

        if low in MENU_COMMANDS:
            await _send(bot, peer_id, "👋 Главное меню AI-ассистента",
                        keyboard=main_menu())
            return

        if low in NEW_DIALOGUE_COMMANDS:
            await _create_new_dialogue(bot, peer_id, user_id, dm)
            return

        if low in LIST_COMMANDS:
            await _show_dialogues(bot, peer_id, user_id, dm)
            return

        if low in SETTINGS_COMMANDS:
            await _send(bot, peer_id, "⚙️ Настройки",
                        keyboard=settings_menu(ai.model))
            return

        if low in ROLES_COMMANDS:
            await _send(bot, peer_id, "🎭 Выберите режим общения:",
                        keyboard=role_menu())
            return

        if low in HELP_COMMANDS:
            await _send(bot, peer_id, help_info())
            return

        # Иначе — сообщение для ИИ
        await _answer_ai(bot, peer_id, user_id, text, dm, ai, settings)

    # ──────────────────────── Callback-события (кнопки) ▼

    @bot.on.raw_event(GroupEventType.MESSAGE_EVENT, dataclass=GroupTypes.MessageEvent)
    async def handle_event(event: GroupTypes.MessageEvent) -> None:
        """Обрабатывает нажатия на кнопки (callback)."""
        obj = event.object
        peer_id = obj.peer_id
        user_id = obj.user_id
        payload = obj.payload or {}
        action = payload.get("a", "")

        # Подтверждаем событие (снимаем «загрузку» кнопки)
        try:
            await bot.api.messages.send_message_event_answer(
                event_id=obj.event_id,
                peer_id=peer_id,
                user_id=user_id,
                event_data='{"type": "show_snackbar", "text": ""}',
            )
        except Exception:  # noqa: BLE001 — ack не критичен
            logger.debug("Не удалось подтвердить событие", exc_info=True)

        if action == "menu":
            await _send(bot, peer_id, "👋 Главное меню", keyboard=main_menu())

        elif action == "new_dialogue":
            await _create_new_dialogue(bot, peer_id, user_id, dm)

        elif action == "list_dialogue":
            await _show_dialogues(bot, peer_id, user_id, dm)

        elif action == "switch_dialogue":
            did = payload.get("id", "")
            ok = await dm.switch_dialogue(user_id, did)
            user = await dm.get_user(user_id)
            d = user.get_active_dialogue()
            role = get_role(d.role) if d else None
            if ok and d and role:
                await _send(
                    bot, peer_id,
                    f"✅ Переключено на диалог «{d.title}»\n"
                    f"Режим: {role.emoji} {role.name}",
                )
            else:
                await _send(bot, peer_id, "❌ Диалог не найден.")

        elif action == "delete_dialogue":
            did = payload.get("id", "")
            ok = await dm.delete_dialogue(user_id, did)
            if ok:
                await _send(bot, peer_id, "🗑 Диалог удалён.",
                            keyboard=main_menu())
            else:
                await _send(bot, peer_id, "❌ Не удалось удалить диалог.")

        elif action == "rename":
            did = payload.get("id", "")
            state.set(user_id, "rename", dialogue_id=did)
            await _send(
                bot, peer_id,
                "✏️ Введите новое название диалога (следующим сообщением):",
            )

        elif action == "roles":
            await _send(bot, peer_id, "🎭 Выберите режим общения:",
                        keyboard=role_menu())

        elif action == "set_role":
            role_key = payload.get("role", "")
            ok = await dm.set_active_role(user_id, role_key)
            role = get_role(role_key)
            if ok:
                await _send(
                    bot, peer_id,
                    f"✅ Режим изменён: {role.emoji} {role.name}\n"
                    f"Применён к текущему диалогу.",
                    keyboard=main_menu(),
                )
            else:
                await _send(bot, peer_id, "❌ Не удалось сменить режим.")

        elif action == "settings":
            await _send(bot, peer_id, "⚙️ Настройки",
                        keyboard=settings_menu(ai.model))

        elif action == "clear_history":
            ok = await dm.clear_history(user_id)
            if ok:
                await _send(bot, peer_id, "🧹 История диалога очищена.",
                            keyboard=main_menu())
            else:
                await _send(bot, peer_id, "❌ Нет активного диалога.")

        elif action == "model_info":
            await _send(
                bot, peer_id,
                f"ℹ️ Текущая модель: {ai.model}\n"
                f"Провайдер: Gemini через ProxyAPI",
            )

        elif action == "help":
            await _send(bot, peer_id, help_info())

        else:
            logger.warning("Неизвестное callback-действие: %s", action)

    # ──────────────────────── Вспомогательные сценарии ▼

    async def _create_new_dialogue(
        bot: Bot, peer_id: int, user_id: int, dm: DialogueManager,
    ) -> None:
        dialogue = await dm.create_dialogue(user_id)
        role = get_role(dialogue.role)
        await _send(
            bot, peer_id,
            f"✅ Создан новый диалог: «{dialogue.title}»\n"
            f"Режим: {role.emoji} {role.name}\n\n"
            f"Напишите сообщение, чтобы начать беседу.",
            keyboard=main_menu(),
        )

    async def _show_dialogues(
        bot: Bot, peer_id: int, user_id: int, dm: DialogueManager,
    ) -> None:
        user = await dm.get_user(user_id)
        dialogues = await dm.list_dialogues(user_id)
        if not dialogues:
            await _send(bot, peer_id,
                        "У вас пока нет диалогов. Создайте первый!",
                        keyboard=main_menu())
            return
        await _send(
            bot, peer_id,
            f"💬 Ваши диалоги ({len(dialogues)}):",
            keyboard=dialogue_list(dialogues, active_id=user.active_dialogue_id),
        )