# AI-ассистент в VK (VKBottle + Gemini через ProxyAPI)

Многодиалоговый AI-бот для ВКонтакте: многодиалоговый режим, краткосрочная
память на JSON, переключение ролей общения, интеграция с Gemini через
ProxyAPI.ru. Полностью на русском языке, асинхронный, с системой кнопок VK.

---

## 1. Структура проекта

```
VPf09-VK-bot/
├── run.py                    # точка входа (python run.py)
├── .env                      # конфигурация (создать из .env.example)
├── .env.example              # шаблон конфигурации
├── requirements.txt
├── bot/
│   ├── main.py               # сборка зависимостей и запуск
│   └── handlers.py           # обработчики сообщений и callback-кнопок
├── services/
│   ├── ai_service.py         # AIService, GeminiProvider (единая точка AI)
│   └── context.py            # формирование context window
├── models/
│   ├── user.py               # UserData, UserSettings
│   ├── dialogue.py           # Dialogue (диалог + история)
│   ├── message.py            # Message (role/content/timestamp)
│   └── roles.py              # 5 режимов общения (system prompts)
├── storage/
│   ├── user_store.py         # JSON-хранилище (файл на пользователя)
│   └── dialogue_manager.py   # менеджер диалогов (бизнес-логика)
├── keyboards/
│   └── vk.py                 # VK-клавиатуры (меню, диалоги, роли, настройки)
├── config/
│   └── settings.py           # настройки из .env (pydantic-settings)
├── utils/
│   └── logger.py             # логирование
└── data/
    └── users/                # JSON-файлы пользователей (создаётся автоматически)
```

## 2. Архитектурная схема

```
                     ┌─────────────────────────────┐
                     │         VK LongPoll         │
                     └──────────────┬──────────────┘
                                    ▼
                     ┌─────────────────────────────┐
                     │   bot/handlers.py (UI-слой) │   сообщения + callback-кнопки
                     │  меню, команды, клавиатуры  │
                     └──────┬──────────────┬───────┘
                            ▼              ▼
          ┌──────────────────────────┐  ┌──────────────────────────────┐
          │ DialogueManager (сервис) │  │       AIService (сервис)     │
          │  диалоги/роли/память     │  │  GeminiProvider -> ProxyAPI  │
          └──────┬───────────────────┘  └───────────────┬──────────────┘
                 ▼                                     ▼
          ┌────────────────────┐              ┌───────────────────────┐
          │ UserStore (JSON)   │              │ google-genai SDK      │
          │ data/users/*.json  │              │ api.proxyapi.ru/google│
          └────────────────────┘              └───────────────────────┘
```

Слои зависимостей направлены «вниз»: обработчики → сервисы → хранилище/ИИ.
Логика AI и логика VK полностью разнесены.

## 3. Установка и запуск

```bash
# 1. Создать виртуальное окружение
python -m venv .venv

# 2. Установить зависимости
.venv/Scripts/pip install -r requirements.txt     # Windows
# .venv/bin/pip install -r requirements.txt      # Linux/macOS

# 3. Настроить окружение
cp .env.example .env        # затем заполнить реальными значениями

# 4. Запустить
.venv/Scripts/python run.py
```

### `.env`

```ini
VK_TOKEN=ваш_токен_сообщества
GROUP_ID=123456789
GEMINI_API_KEY=ваш_ключ_proxyapi
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_BASE_URL=https://api.proxyapi.ru/google
LOG_LEVEL=INFO
```

Для VK-токена: сообщество → Настройки → Работа с API → Ключи доступа,
нужные права: `messages`. Включите Long Poll в разделе «Сообщения» →
«Настройки для бота».

## 4. Пример запроса к Gemini через ProxyAPI

Код в `services/ai_service.py` формирует запрос через официальный SDK,
а ProxyAPI подменяет endpoint на `https://api.proxyapi.ru/google`:

```python
from google import genai
from google.genai import types

client = genai.Client(
    api_key=GEMINI_API_KEY,
    http_options={"api_version": "v1beta", "base_url": "https://api.proxyapi.ru/google"},
)
response = await client.aio.models.generate_content(
    model="gemini-2.0-flash",
    contents=[
        {"role": "user", "parts": [{"text": "Привет!"}]},
    ],
    config=types.GenerateContentConfig(system_instruction="Ты — помощник"),
)
print(response.text)
```

Эквивалентный curl:

```bash
curl "https://api.proxyapi.ru/google/v1beta/models/gemini-2.0-flash:generateContent" \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <КЛЮЧ>' \
  -X POST \
  -d '{"contents":[{"parts":[{"text":"Привет!"}]}]}'
```

## 5. Формат JSON-хранилища

Файл `data/users/<user_id>.json`:

```json
{
  "user_id": 123456789,
  "dialogues": {
    "uuid-1": {
      "id": "uuid-1",
      "title": "Диалог 1",
      "role": "programmer",
      "created_at": 1756000000.0,
      "messages": [
        {"role": "user", "content": "Привет", "timestamp": 1756000001.0},
        {"role": "assistant", "content": "Здравствуйте!", "timestamp": 1756000002.0}
      ]
    }
  },
  "active_dialogue_id": "uuid-1",
  "settings": {"model": "", "max_history": 100},
  "created_at": 1756000000.0
}
```

История ограничивается **100 последними сообщениями** (настраивается через
`MAX_HISTORY`): при добавлении нового сообщения старые отбрасываются.

## 6. Режимы общения

| Ключ         | Режим                | Системный промпт                       |
|--------------|----------------------|----------------------------------------|
| `assistant`  | 🤖 Помощник          | общий помощник                         |
| `programmer` | 💻 Программист       | наставник по коду                      |
| `teacher`    | 🎓 Преподаватель     | объяснение материала                   |
| `business`   | 📊 Бизнес-консультант| стратегии и финансы                    |
| `friend`     | 😊 Дружелюбный собеседник | лёгкое живое общение             |

Роль привязана к **конкретному диалогу** (не к пользователю в целом):
смена режима меняет только system prompt активного диалога.

## 7. Ключевые решения

- **Чистая архитектура.** Обработчики VK не знают про AI и JSON — только
  вызывают сервисы. `AIService` скрывает конкретного провайдера.
- **Лёгкая смена модели.** Достаточно поменять `GEMINI_MODEL` в `.env`.
- **Расширяемость.** Новый провайдер = новый класс, реализующий
  `BaseAIProvider` + регистрация в `AIService.set_provider()`.
- **Только JSON.** Никаких SQLite/PostgreSQL — один файл на пользователя,
  асинхронная запись через `aiofiles` с атомарной заменой (tmp-файл).
- **Асинхронность везде.** `asyncio`, `vkbottle` (aiohttp), `google-genai` (aio).
- **Fallback AI.** Любая ошибка API/сети ловится в `AIService.generate_reply`
  и превращается в понятное пользователю сообщение.
- **«Печатает...»** — статус `typing` ставится через `messages.setActivity`.
- **Лимиты.** Длина сообщения ограничена 4000 символов, длинные ответы ИИ
  разбиваются на части, история диалога — максимум 100 сообщений.

## 8. Обработка ошибок

| Ситуация                     | Поведение                                             |
|------------------------------|-------------------------------------------------------|
| Ошибка/таймаут Gemini        | Fallback-сообщение пользователю + лог ошибки          |
| Сбой сети                    | То же (единый `try/except` в AIService)               |
| Пустое сообщение             | Ответ «⚠️ Пустое сообщение...»                        |
| Слишком длинное сообщение    | Предупреждение + отклонение                           |
| Длинный ответ ИИ             | Автоматическое разбиение на части                     |
| Неизвестная кнопка/действие  | Логирование `WARNING`                                 |
| Ошибка VK API                | Обработчик ошибок фреймворка (логируется)             |

## 9. Рекомендации по масштабированию

- **Память в JSON** — отлично для одного процесса и сотен пользователей.
  Для тысяч+ пользователей переведите `UserStore` на Redis/S3, сохранив
  интерфейс `UserStore` (паттерн «заменил реализацию — ничего не сломал»).
- **Параллельные обработчики.** Добавьте rate-limit на сообщения
  (например, `asyncio.Semaphore` или очередь), чтобы не превышать лимиты VK.
- **Смена провайдера.** Реализуйте `OpenAIProvider` для
  `https://api.proxyapi.ru/openai` — интерфейс уже готов
  (`BaseAIProvider.generate(context)`).
- **Разделение контекста.** При росте числа диалогов добавьте
  «заморозку» неактивных диалогов: выгружать их историю из кэша на диск.
- **Наблюдаемость.** Подключите `sentry-sdk` в `utils/logger.py` для
  продакшн-логов; логируйте latency вызовов Gemini.
- **Безопасность.** Не коммитьте `.env`; используйте секреты CI/CD;
  на проде валидируйте входные сообщения на длину и содержимое.
