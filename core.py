# FILE: core.py (обновленный фрагмент)
"""
Ядро бота: содержит глобальные объекты, фильтры, клавиатуру и общие функции.
"""

import logging
import logging.handlers  # Для ротации
from pathlib import Path
from typing import Dict, Any

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import BaseFilter
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.default import DefaultBotProperties

from api import pick_models_in_order
from config import config
from history import create_session
from utils import (is_admin, is_authorized, ensure_user_dirs, load_json, save_json, user_config_path)

# --- Настройка логирования ---
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
    handlers=[
        logging.StreamHandler(),  # stdout для Docker
        logging.handlers.RotatingFileHandler(
            LOGS_DIR / "bot.log",
            maxBytes=10*1024*1024,  # 10 MB
            backupCount=5,  # 5 ротаций
            encoding="utf-8"
        )
    ]
)
logger = logging.getLogger(__name__)


bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage()) # <<< НАСТРОЕНО ХРАНИЛИЩЕ

ALLOWED_MODES = ["paid1", "paid2", "free"]



# --- Фильтры для авторизации ---

class IsAdminFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return is_admin(message.from_user.id)


class IsAuthorizedFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        if is_authorized(message.from_user.id):
            return True
        await message.answer("❌ Доступ запрещен. Обратитесь к администратору.")
        return False


# --- Клавиатура (создается один раз при старте) ---

def create_main_keyboard() -> ReplyKeyboardMarkup:
    """Создает и возвращает основную клавиатуру. Использует ID моделей из .env (без API-запросов)."""
    # Используем ID моделей напрямую
    model_names = [
        config.paid_model_1,
        config.paid_model_2,
        config.free_model
    ]

    def get_button_text(model_id: str, mode: str) -> str:
        # Обрезаем длинные ID для удобства
        display_name = model_id[:25] + "..." if len(model_id) > 25 else model_id
        return f"Выбрать {display_name} ({mode.upper()})"

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=get_button_text(model_names[0], ALLOWED_MODES[0])),
                KeyboardButton(text=get_button_text(model_names[1], ALLOWED_MODES[1])),
            ],
            [
                KeyboardButton(text=get_button_text(model_names[2], ALLOWED_MODES[2])),
                KeyboardButton(text="Очистить контекст"),
            ],
            [KeyboardButton(text="Menu")]
        ],
        resize_keyboard=True,
    )
    return keyboard


MAIN_KEYBOARD = create_main_keyboard()


# --- Вспомогательные функции ---

def load_user_config(user_id: int | str) -> Dict[str, Any]:
    """Загружает конфигурацию пользователя, создавая ее при необходимости."""
    ensure_user_dirs(user_id)
    path = user_config_path(user_id)
    user_cfg = load_json(path, {})
    if "mode" not in user_cfg:
        user_cfg["mode"] = "free"
    if "session_id" not in user_cfg:
        session_id = create_session(user_id, "Основная сессия")
        user_cfg["session_id"] = session_id
        save_json(path, user_cfg)
    return user_cfg


def save_user_config(user_id: int | str, user_cfg: Dict[str, Any]) -> None:
    """Сохраняет конфигурацию пользователя."""
    path = user_config_path(user_id)
    save_json(path, user_cfg)


async def set_mode_and_reply(message: Message, mode: str):
    """Устанавливает режим для пользователя и отправляет подтверждение."""
    user_id = message.from_user.id
    if mode not in ALLOWED_MODES:
        await message.answer(f"Режим {mode} не разрешен. Доступны: {', '.join(ALLOWED_MODES)}", reply_markup=MAIN_KEYBOARD)
        return

    user_cfg = load_user_config(user_id)
    old_mode = user_cfg.get("mode", "N/A")
    user_cfg["mode"] = mode
    save_user_config(user_id, user_cfg)

    current_model_list = pick_models_in_order(config.paid_model_1, config.paid_model_2, config.free_model, mode)
    confirm_msg = f"✅ Режим изменен на: <b>{mode}</b> (модели: {', '.join(current_model_list[:2])}...)\nБыло: {old_mode}"
    await message.answer(confirm_msg, reply_markup=MAIN_KEYBOARD)

