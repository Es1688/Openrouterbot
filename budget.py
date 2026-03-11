"""
Модуль бюджета: daily spent в ТОКЕНАХ.
Хранение: data/{user_id}/budget.json (used_tokens: int, limit: int, date: str).
Функции: get_today_spent (load/reset), can_send (check limit), update_spent (add tokens), set_daily_limit, reset_daily.
Импорт: from utils import load_json, save_json, ensure_user_dirs, user_budget_path.
Fallback: used_tokens=0, limit из config (токены).
"""

import logging
from datetime import date
from typing import Dict, Any
from config import config
from utils import load_json, save_json, ensure_user_dirs, user_budget_path

logger = logging.getLogger(__name__)

def get_today_spent(user_id: int | str) -> Dict[str, Any]:
    """Загружает used_tokens/limit/date для сегодня. Fallback: used_tokens=0, limit из config (токены).
    При новом дне: reset used_tokens, сохраняет limit, обновляет date."""
    ensure_user_dirs(user_id)
    path = user_budget_path(user_id)
    budget_data = load_json(path, {})
    
    today = date.today().isoformat()
    if budget_data.get("date") != today:
        # Новый день: reset used_tokens, но сохраняем limit если был set
        old_limit = budget_data.get("limit", config.max_tokens_per_day)  # <<< ИСПРАВЛЕНО ЗДЕСЬ
        budget_data = {
            "used_tokens": 0,
            "limit": old_limit,
            "date": today
        }
        save_json(path, budget_data)
        logger.info(f"New day reset for user {user_id}: used_tokens=0, limit={old_limit}")
    
    return budget_data

def can_send(user_id: int | str) -> bool:
    """Проверяет, можно ли отправить сообщение (used_tokens < limit)."""
    today_data = get_today_spent(user_id)
    return today_data["used_tokens"] < today_data["limit"]

def update_spent(user_id: int | str, tokens: int):
    """Обновляет used_tokens за день."""
    if tokens < 0:
        logger.warning(f"Invalid update for {user_id}: tokens={tokens}")
        return
    
    today_data = get_today_spent(user_id)
    today_data["used_tokens"] += tokens
    path = user_budget_path(user_id)
    save_json(path, today_data)
    logger.debug(f"Updated budget for {user_id}: +{tokens} tokens (total used_tokens={today_data['used_tokens']})")

def set_daily_limit(user_id: int | str, limit_tokens: int):
    """Устанавливает daily limit в токенах (per user; сохраняет в JSON)."""
    if limit_tokens < 0:
        logger.warning(f"Invalid limit {limit_tokens} for {user_id}")
        return
    
    ensure_user_dirs(user_id)
    path = user_budget_path(user_id)
    budget_data = load_json(path, {})
    budget_data["limit"] = limit_tokens
    # Не меняем used_tokens/date — только limit
    save_json(path, budget_data)
    logger.info(f"Set daily limit for {user_id}: {limit_tokens} tokens")

def reset_daily(user_id: int | str):
    """Сброс used_tokens на 0 (не меняет limit/date)."""
    ensure_user_dirs(user_id)
    path = user_budget_path(user_id)
    budget_data = load_json(path, {})
    budget_data["used_tokens"] = 0
    save_json(path, budget_data)
    logger.info(f"Reset daily budget for {user_id}: used_tokens=0")

