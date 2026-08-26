"""Построение VK-клавиатур (кнопки, callback-кнопки).

Все payload'ы — словари:
  {"a": "action", ...данные...}
vkbottle сам сериализует их в JSON.
"""
from typing import Any

from vkbottle import Keyboard, KeyboardButtonColor, Callback, Text

from models.dialogue import Dialogue
from models.roles import get_role, role_list

# ──────────────────────── Вспомогательные функции ▼

def _payload(action: str, **data: Any) -> dict[str, Any]:
    """Формирует payload кнопки."""
    return {"a": action, **data}


def _add_button(
    kb: Keyboard,
    label: str,
    payload: dict[str, Any],
    color: KeyboardButtonColor = KeyboardButtonColor.SECONDARY,
    callback: bool = True,
) -> None:
    """Добавляет одну кнопку в текущий ряд."""
    if callback:
        kb.add(Callback(label, payload), color=color)
    else:
        kb.add(Text(label, payload), color=color)


# ──────────────────────── Клавиатуры ▼

def main_menu() -> Keyboard:
    """Главное меню."""
    kb = Keyboard(inline=False, one_time=False)
    _add_button(kb, "➕ Новый диалог", _payload("new_dialogue"),
                KeyboardButtonColor.POSITIVE)
    _add_button(kb, "💬 Список диалогов", _payload("list_dialogue"), callback=False)
    kb.row()
    _add_button(kb, "🎭 Сменить режим", _payload("roles"))
    _add_button(kb, "⚙️ Настройки", _payload("settings"))
    kb.row()
    _add_button(kb, "❓ Помощь", _payload("help"))
    return kb


def role_menu() -> Keyboard:
    """Меню выбора режима общения (5 ролей)."""
    kb = Keyboard(inline=False)
    roles = role_list()
    for i in range(0, len(roles), 2):
        pair = roles[i : i + 2]
        for role in pair:
            color = KeyboardButtonColor.POSITIVE
            if role.key == "assistant":
                color = KeyboardButtonColor.SECONDARY
            _add_button(kb, f"{role.emoji} {role.name}",
                        _payload("set_role", role=role.key), color)
        kb.row()
    _add_button(kb, "⬅️ Назад", _payload("menu"))
    return kb


def settings_menu(model: str) -> Keyboard:
    """Меню настроек."""
    kb = Keyboard(inline=False)
    _add_button(kb, "🎭 Выбор режима", _payload("roles"), KeyboardButtonColor.PRIMARY)
    _add_button(kb, "🧹 Очистить историю", _payload("clear_history"),
                KeyboardButtonColor.NEGATIVE)
    kb.row()
    _add_button(kb, "ℹ️ Модель: " + (model or "—"), _payload("model_info"))
    _add_button(kb, "⬅️ В меню", _payload("menu"))
    return kb


def dialogue_list(dialogues: list[Dialogue], active_id: str = "") -> Keyboard:
    """Список диалогов с кнопками переключения и удаления.

    Активный диалог отмечается галочкой.
    """
    kb = Keyboard(inline=False)
    if not dialogues:
        _add_button(kb, "➕ Создать диалог", _payload("new_dialogue"),
                    KeyboardButtonColor.POSITIVE)
        return kb

    for d in dialogues[:6]:
        role = get_role(d.role)
        marker = "✅" if d.id == active_id else ""
        title = f"{marker} {d.title[:18]}" if marker else d.title[:20]
        _add_button(kb, f"{title} · {role.emoji}",
                    _payload("switch_dialogue", id=d.id),
                    KeyboardButtonColor.PRIMARY)
        kb.row()
        _add_button(kb, "✏️ Переименовать", _payload("rename", id=d.id))
        _add_button(kb, "🗑 Удалить", _payload("delete_dialogue", id=d.id),
                    KeyboardButtonColor.NEGATIVE)
        kb.row()
    _add_button(kb, "⬅️ В меню", _payload("menu"))
    return kb


def help_info() -> str:
    """Текст раздела «Помощь»."""
    roles = role_list()
    lines = [
        "🤖 *AI-ассистент VK*",
        "",
        "*Главное меню:*",
        "• ➕ Новый диалог — начать новую беседу",
        "• 💬 Список диалогов — переключение между беседами",
        "• 🎭 Сменить режим — выбрать роль ИИ",
        "• ⚙️ Настройки — очистка истории, информация о модели",
        "",
        "*Режимы общения:*",
    ]
    for r in roles:
        lines.append(f"• {r.emoji} {r.name}")
    lines += [
        "",
        "💡 Просто напишите сообщение — и бот ответит.",
        "Контекст каждого диалога хранится отдельно.",
    ]
    return "\n".join(lines)