# OpenRouter Telegram Bot

Telegram-бот для взаимодействия с [OpenRouter](https://openrouter.ai) — агрегатором множества AI-моделей. Позволяет общаться с моделями через Telegram, управлять сессиями, контролировать бюджет и настраивать режимы работы.

## 🚀 Быстрый старт

1. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```

2. Создайте `.env` файл на основе `.env.example` (см. ниже) и укажите:
   - `OPENROUTER_API_KEY` — ваш ключ от OpenRouter
   - `BOT_TOKEN` — токен Telegram-бота от [@BotFather](https://t.me/BotFather)
   - `PAID_MODEL_1`, `PAID_MODEL_2`, `FREE_MODEL` — ID моделей из [OpenRouter Models](https://openrouter.ai/models)
   - `ADMIN_USERS` — список ID администраторов (например, `[123456789]`)

3. Запустите:
   ```bash
   python bot.py
   ```

Или через Docker:
```bash
docker-compose up --build
```

---

## 📁 Структура проекта

| Файл / Модуль           | Описание |
|------------------------|----------|
| **`bot.py`**           | Точка входа. Инициализирует бота, регистрирует роутеры и запускает polling. |
| **`core.py`**          | Ядро: глобальные объекты (`bot`, `dp`), фильтры (`IsAdminFilter`, `IsAuthorizedFilter`), клавиатура, вспомогательные функции. |
| **`api.py`**           | Работа с OpenRouter API: валидация ключа, получение баланса, отправка запросов. Поддерживает fallback-модели. |
| **`config.py`**        | Загрузка и валидация конфигурации из `.env`. Обязательные поля: API-ключи, модели, лимиты. |
| **`handlers/`**        | Обработчики команд и сообщений. |
| &nbsp;&nbsp;├─ `user_handlers.py` | Команды для пользователей: чат, выбор модели, управление сессиями, бюджет. |
| &nbsp;&nbsp;└─ `admin_handlers.py` | Админ-команды: управление whitelist (`/adduser`, `/removeuser`, `/listusers`). |
| **`history.py`**       | Управление историей чата: создание, загрузка, экспорт сессий. Хранение в `data/sessions/`. |
| **`budget.py`**        | Контроль дневного бюджета в USD. Хранение расходов в `data/users/{id}/budget.json`. |
| **`utils.py`**         | Вспомогательные функции: работа с JSON, пути, авторизация, форматирование ответов. |
| **`states.py`**        | FSM-состояния (например, подтверждение сброса). |
| **`requirements.txt`** | Зависимости проекта. |
| **`Dockerfile`**       | Конфигурация для сборки Docker-образа. |
| **`docker-compose.yml`** | Запуск в контейнере с монтированием `./data`. |
| **`.dockerignore`**, **`.gitignore`** | Исключение чувствительных и временных файлов. |

---

## ⚙️ Конфигурация (`.env`)

Обязательные переменные:
```env
OPENROUTER_API_KEY=sk-or-v1-...
BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
PAID_MODEL_1=google/gemini-2.5-pro
PAID_MODEL_2=x-ai/grok-4-fast
FREE_MODEL=mistralai/devstral-2512:free

ADMIN_USERS=[123456789]
AUTHORIZED_USERS=[987654321]  # опционально

# Опционально (дефолты в коде)
BUDGET_USD_PER_DAY=10.0
MAX_TOKENS=8192
CONTEXT_TURNS=5
TEMPERATURE=0.2
APP_URL=https://your-site.com
APP_NAME=My OpenRouter Bot
```

> **Важно**: Все модели **должны быть указаны в `.env`**. Бот не загружает список моделей из API.

---

## 🔐 Авторизация

- Только пользователи из `AUTHORIZED_USERS` или `ADMIN_USERS` могут использовать бота.
- Администраторы могут управлять whitelist через команды:
  - `/adduser <id>` — добавить
  - `/removeuser <id>` — удалить
  - `/listusers` — список
  - `/clearusers` — очистить (остаются только админы)

---

## 💬 Использование

- Отправьте сообщение — бот ответит через выбранную модель.
- Кнопки и команды:
  - `/paid1`, `/paid2`, `/free` — смена режима
  - `/reset` — сброс сессии и бюджета (с подтверждением)
  - `/sessions`, `/newsession`, `/switchsession` — управление сессиями
  - `/budget`, `/setlimit` — контроль расходов
  - `/export` — экспорт текущей сессии в JSON

---

## 📦 Данные

Все данные хранятся локально в папке `data/`:
- `data/authorized_users.json` — динамический whitelist
- `data/users/{id}/config.json` — режим и активная сессия
- `data/users/{id}/budget.json` — дневной бюджет
- `data/sessions/{id}/` — история чата

Папка `data/` монтируется в Docker и исключена из Git.

---

## 📝 Примечания

- Стоимость запросов **не рассчитывается** — используется фиксированный лимит в USD.
- Ответы AI автоматически очищаются от markdown и спецсимволов.
- Все тексты на русском языке.
- Поддержка длинных ответов (разбивка на части ≤4096 символов).

---

> ✨ Проект готов к развертыванию в продакшене. Используйте `.env` для безопасной настройки.

