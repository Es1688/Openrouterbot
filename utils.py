"""
Утилиты для OpenRouter Bot: JSON load/save, paths, timestamps.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
import uuid  # Для session_id (если нужно)
import logging
import re

logger = logging.getLogger(__name__)
DATA_DIR = Path("data")
USERS_DIR = DATA_DIR / "users"
SESSIONS_DIR = DATA_DIR / "sessions"

AUTHORIZED_USERS_PATH = DATA_DIR / "authorized_users.json"  # Global whitelist

def ensure_dirs():
    """Создает data/, users/, sessions/ если нет. Инициализирует authorized_users.json как [] если отсутствует."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    USERS_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Инициализация authorized_users.json если нет
    if not AUTHORIZED_USERS_PATH.exists():
        save_json(AUTHORIZED_USERS_PATH, [])  # Пустой список

def ensure_user_dirs(user_id: int | str):
    """Создает data/users/{user_id}/ и data/sessions/{user_id}/."""
    ensure_dirs()  # Ensure base dirs first
    user_dir = USERS_DIR / str(user_id)
    user_sessions_dir = SESSIONS_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    user_sessions_dir.mkdir(parents=True, exist_ok=True)

def load_json(path: Path, default: Any = None) -> Any:
    """Загружает JSON из path; возвращает default если нет/ошибка."""
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"JSON load error {path}: {e}")
        return default

def save_json(path: Path, data: Any) -> None:
    """Сохраняет data как JSON в path (indent=2)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"JSON save error {path}: {e}")

def user_config_path(user_id: int | str) -> Path:
    """Path к data/users/{user_id}/config.json (mode, session_id)."""
    return USERS_DIR / str(user_id) / "config.json"

def user_budget_path(user_id: int | str) -> Path:
    """Path к data/users/{user_id}/budget.json (used_tokens, limit, date)."""
    return USERS_DIR / str(user_id) / "budget.json"

def session_path(user_id: int | str, session_id: str) -> Path:
    """Path к data/sessions/{user_id}/{session_id}.json (messages, title, turns)."""
    return SESSIONS_DIR / str(user_id) / f"{session_id}.json"

def user_sessions_index_path(user_id: int | str) -> Path:
    """Path к data/sessions/{user_id}/index.json (list сессий: [{'id', 'title', 'turns', 'created'}])."""
    return SESSIONS_DIR / str(user_id) / "index.json"

def now_ts() -> int:
    """Текущий timestamp (int)."""
    return int(datetime.now().timestamp())

def ts_to_time(ts: int) -> str:
    """Timestamp → читаемая дата/время (YYYY-MM-DD HH:MM)."""
    dt = datetime.fromtimestamp(ts)
    return dt.strftime("%Y-%m-%d %H:%M")

# Authorized users utils
def load_authorized_users() -> List[int]:
    """Загружает authorized_users.json (dynamic); всегда union с permanent (config.authorized_users) и admins."""
    ensure_dirs()
    users_dynamic = load_json(AUTHORIZED_USERS_PATH, [])
    
    # Инициализация из .env если JSON пустой
    from config import config  # Lazy import
    permanent = config.authorized_users.copy()
    if not users_dynamic and permanent:
        save_authorized_users(permanent)  # Init JSON with permanent
        users_dynamic = permanent.copy()
    
    # Всегда union: dynamic + permanent + admins (unique, sorted)
    admins = set(config.admin_users)
    all_users = list(set(users_dynamic + permanent) | admins)
    return sorted(all_users)

def save_authorized_users(users: List[int]) -> None:
    """Сохраняет list в authorized_users.json (только non-admins; permanent остаются в config)."""
    from config import config  # Lazy
    # Удаляем admins из списка (они bypass, не сохраняем)
    filtered_users = [u for u in users if u not in config.admin_users]
    save_json(AUTHORIZED_USERS_PATH, filtered_users)

def is_authorized(user_id: int) -> bool:
    """Проверка: user_id в authorized_users (включая admins и permanent)."""
    authorized = load_authorized_users()
    return user_id in authorized

def is_admin(user_id: int) -> bool:
    """Проверка: user_id в ADMIN_USERS (fixed из .env)."""
    from config import config  # Lazy
    return user_id in config.admin_users

def clean_and_format_ai_response(text: str) -> str:
    """
    Очищает и форматирует ответ от AI:
    - Удаляет или заменяет специальные символы (кроме пунктуации и пробелов)
    - Нормализует пробелы и переносы строк
    - Разбивает на абзацы по двойным переносам строк или логическим блокам
    """
    # Удаляем control-символы, кроме \n и \t
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    
    # Заменяем множественные переносы строк на двойные (для абзацев)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Убираем пробелы в начале и конце каждой строки
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)
    
    # Убираем лишние пробелы между словами
    text = re.sub(r' +', ' ', text)
    
    # Убедимся, что нет пустых строк в начале/конце
    text = text.strip()
    
    return text

# Функция для разбивки длинных сообщений (используется в bot.py)
def split_long_message(text: str, max_len: int = 4096, model_signature: str = None) -> List[str]:
    """
    Разбивает длинный текст на части ≤ max_len (по словам, без обрезки).
    Возвращает list[str]; если короткий — [text].
    Если model_signature предоставлен, добавляется к последней части (или новой, если не влезает).
    """
    if model_signature and len(text + model_signature) <= max_len:
        # Short + sig fits
        return [text + model_signature]
    elif model_signature and len(text) <= max_len:
        # Short, but + sig > max_len → separate
        return [text, model_signature]
    elif len(text) <= max_len:
        # Short without sig
        return [text]
    
    # Long text: split first, then add sig if provided
    parts = []
    current_part = ""
    words = text.split()
    
    for word in words:
        test_part = current_part + (" " if current_part else "") + word
        if len(test_part) <= max_len:
            current_part = test_part
        else:
            if current_part:
                parts.append(current_part)
            current_part = word  # Start new with word (even if word > max_len)
    
    if current_part:
        parts.append(current_part)
    
    # Add model_signature to last part if fits, else new part
    if model_signature and parts:
        last_part = parts[-1]
        if len(last_part + model_signature) <= max_len:
            parts[-1] += model_signature
        else:
            parts.append(model_signature)
    
    return parts
def user_help_message_path(user_id: int | str) -> Path:
    return USERS_DIR / str(user_id) / "last_help_message_id.json"

def save_last_help_message_id(user_id: int | str, message_id: int) -> None:
    save_json(user_help_message_path(user_id), {"message_id": message_id})

def get_last_help_message_id(user_id: int | str) -> int | None:
    data = load_json(user_help_message_path(user_id), {})
    return data.get("message_id")

def clear_last_help_message_id(user_id: int | str) -> None:
    path = user_help_message_path(user_id)
    if path.exists():
        path.unlink()

async def delete_last_help_message(bot, user_id: int):
    message_id = get_last_help_message_id(user_id)
    if message_id:
        try:
            await bot.delete_message(chat_id=user_id, message_id=message_id)
        except Exception:
            pass
        finally:
            clear_last_help_message_id(user_id)
