"""
Модуль истории чата для OpenRouter Bot.
Управляет сессиями: create/load/add/list/delete/update/export.
Хранение: data/sessions/{user_id}/{session_id}.json (messages: [{'role': 'user/assistant', 'content': str, 'ts': int}]).
Index: data/sessions/{user_id}/index.json (list [{'id': str, 'title': str, 'turns': int, 'created': int}]).
Функции: create_session (UUID + index), add_message (append + update turns), load_session (messages), list_sessions (sorted desc), delete_session (remove index + file), update_title, export_session (copy to temp).
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import uuid

from config import config
# ИСПРАВЛЕНИЕ: Добавлен импорт DATA_DIR
from utils import ensure_user_dirs, session_path, user_sessions_index_path, load_json, save_json, now_ts, DATA_DIR

def create_session(user_id: int | str, title: str = "Новая сессия") -> str:
    """Создает новую сессию: UUID id, с системным промтом, добавляет в index.json."""
    ensure_user_dirs(user_id)
    session_id = str(uuid.uuid4())[:8]  # Короткий ID (e.g., 'a1b2c3d4')
    created = now_ts()
    
    # Системный промт для чистого и структурированного ответа
    system_prompt = (
        " Отвечай на русском языке простым, понятным текстом. "
        "Не используй markdown, звёздочки, решётки, backticks, XML-теги или другие спецсимволы. "
        "Разбивай длинные ответы на логические абзацы с помощью пустых строк. "
        
    )
    
    # Формируем session_data ОДИН РАЗ
    session_data = {
        "messages": [{"role": "system", "content": system_prompt}],
        "title": title,
        "turns": 0,
        "created": created
    }
    
    # Сохраняем файл сессии
    session_path_full = session_path(user_id, session_id)
    save_json(session_path_full, session_data)
    
    # Добавляем запись в index
    index_path = user_sessions_index_path(user_id)
    index = load_json(index_path, [])
    index.append({
        "id": session_id,
        "title": title,
        "turns": 0,
        "created": created
    })
    save_json(index_path, index)
    
    return session_id


def add_message(user_id: int | str, session_id: str, role: str, content: str) -> None:
    """Добавляет сообщение в сессию (append to messages), обновляет turns в session.json и index.json."""
    ensure_user_dirs(user_id)
    session_path_full = session_path(user_id, session_id)
    if not session_path_full.exists():
        raise ValueError(f"Сессия {session_id} не найдена.")
    
    # Load session
    session_data = load_json(session_path_full, {})
    messages = session_data.get("messages", [])
    messages.append({
        "role": role,
        "content": content,
        "ts": now_ts()
    })
    turns = len([m for m in messages if m["role"] == "user"])  # Turns = user messages count
    
    # Update session
    session_data["messages"] = messages
    session_data["turns"] = turns
    save_json(session_path_full, session_data)
    
    # Update index
    index_path = user_sessions_index_path(user_id)
    index = load_json(index_path, [])
    for entry in index:
        if entry["id"] == session_id:
            entry["turns"] = turns
            break
    save_json(index_path, index)

def load_session(user_id: int | str, session_id: str) -> List[Dict[str, Any]]:
    """Загружает messages из сессии (list [{'role', 'content', 'ts'}])."""
    ensure_user_dirs(user_id)
    session_path_full = session_path(user_id, session_id)
    if not session_path_full.exists():
        raise ValueError(f"Сессия {session_id} не найдена.")
    
    session_data = load_json(session_path_full, {})
    return session_data.get("messages", [])

def list_sessions(user_id: int | str) -> List[Dict[str, Any]]:
    """Загружает список сессий из index.json, sorted by created desc."""
    ensure_user_dirs(user_id)
    index_path = user_sessions_index_path(user_id)
    index = load_json(index_path, [])
    # Sort by created desc (новые сверху)
    return sorted(index, key=lambda s: s["created"], reverse=True)

def delete_session(user_id: int | str, session_id: str) -> bool:
    """Удаляет сессию: remove from index.json + delete session.json. Returns True if deleted."""
    ensure_user_dirs(user_id)
    session_path_full = session_path(user_id, session_id)
    if not session_path_full.exists():
        return False
    
    # Delete session file
    session_path_full.unlink()
    
    # Remove from index
    index_path = user_sessions_index_path(user_id)
    index = load_json(index_path, [])
    index = [s for s in index if s["id"] != session_id]
    save_json(index_path, index)
    
    return True

def update_title(user_id: int | str, session_id: str, new_title: str) -> None:
    """Обновляет title в session.json и index.json."""
    ensure_user_dirs(user_id)
    session_path_full = session_path(user_id, session_id)
    if not session_path_full.exists():
        raise ValueError(f"Сессия {session_id} не найдена.")
    
    # Update session
    session_data = load_json(session_path_full, {})
    session_data["title"] = new_title
    save_json(session_path_full, session_data)
    
    # Update index
    index_path = user_sessions_index_path(user_id)
    index = load_json(index_path, [])
    for entry in index:
        if entry["id"] == session_id:
            entry["title"] = new_title
            break
    save_json(index_path, index)

def export_session(user_id: int | str, session_id: str) -> Path:
    """Экспортирует сессию: copy session.json to data/export/{session_id}_{ts}.json. Returns path."""
    ensure_user_dirs(user_id)
    session_path_full = session_path(user_id, session_id)
    if not session_path_full.exists():
        raise ValueError(f"Сессия {session_id} не найдена.")
    
    export_dir = DATA_DIR / "export"
    export_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_path = export_dir / f"{session_id}_{ts}.json"
    
    shutil.copy2(session_path_full, export_path)
    return export_path

