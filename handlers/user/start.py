"""
Обработчики команд, связанных со стартом и справкой: /start, /help, Help.
"""
import logging
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from api import validate_api_key
from core import (IsAuthorizedFilter, MAIN_KEYBOARD, config, logger,
                  load_user_config, pick_models_in_order, is_admin)
from utils import is_authorized, save_last_help_message_id

router = Router()
router.message.filter(IsAuthorizedFilter())

# Стандартное сообщение об ошибке
ERROR_MESSAGE = "❌ Произошла ошибка при обработке запроса. Администратор уведомлён. Попробуйте позже."


@router.message(CommandStart())
async def start_handler(message: Message):
    user_id = message.from_user.id
    user = message.from_user
    logger.info(f"User {user_id} ({user.full_name}) started bot")

    try:
        if not is_authorized(user_id):
            await message.answer("❌ Доступ запрещен. Обратитесь к администратору для добавления в whitelist.", reply_markup=MAIN_KEYBOARD)
            return

        # Проверка API-ключа
        if not config.api_key:
            await message.answer("❌ OPENROUTER_API_KEY не настроен. Обратитесь к администратору.", reply_markup=MAIN_KEYBOARD)
            logger.warning(f"API key missing for user {user_id}")
            return

        validation = validate_api_key(config.api_key, config.app_url, config.app_name)
        if not validation["valid"]:
            await message.answer("❌ Недействительный API-ключ OpenRouter. Обратитесь к администратору.", reply_markup=MAIN_KEYBOARD)
            logger.error(f"Invalid API key for user {user_id}")
            return

        # Показываем баланс только администраторам
        if is_admin(user_id):
            balance = validation["balance"]
            balance_msg = f"Баланс: ${balance:.2f}" if balance is not None else "Не удалось получить баланс."
        else:
            balance_msg = "Баланс OpenRouter скрыт (только для админов)."

        user_cfg = load_user_config(user_id)
        mode = user_cfg["mode"]
        session_id = user_cfg["session_id"]
        current_model_list = pick_models_in_order(config.paid_model_1, config.paid_model_2, config.free_model, mode)
        current_model = current_model_list[0]

        welcome_msg = (
            f"Привет! Я бот для чата с AI через OpenRouter.\n"
            f"Текущий режим: <b>{mode}</b> (модель: {current_model})\n"
            f"Сессия: <code>{session_id[:8]}...</code>\n{balance_msg}\n\n"
            f"Отправьте сообщение для чата или используйте кнопки. 'Help' для списка команд."
        )
        await message.answer(welcome_msg, reply_markup=MAIN_KEYBOARD)
        logger.info(f"Welcome sent to user {user_id}, mode={mode}")

    except Exception as e:
        logger.exception(f"Error in start_handler for user {user_id}: {e}")
        await message.answer(ERROR_MESSAGE, reply_markup=MAIN_KEYBOARD)


@router.message(F.text == "Help")
@router.message(Command("help"))
async def help_handler(message: Message):
    user_id = message.from_user.id
    logger.info(f"Help requested by user {user_id}")

    try:
        help_text = (
            "<b>Основные команды:</b>\n"
            "/paid1, /paid2, /free — Быстрый выбор режима\n"
            "/models — Информация о доступных моделях\n"
            "/budget — Текущий расход и лимит токенов (баланс OpenRouter — только для админов)\n"
            "/reset — Очистить контекст и начать новую сессию (бюджет не сбрасывается)\n\n"
            
            "<b>Управление сессиями:</b>\n"
            "/sessions — Список ваших сессий\n"
            "/newsession [название] — Создать новую сессию\n"
            "/switchsession <code>id</code> — Переключиться на сессию\n"
            "/deletesession <code>id</code> — Удалить сессию\n"
            "/export — Экспорт текущей сессии в JSON\n\n"
            
            "<b>Настройки:</b>\n"
            "/setmodel <code>paid1|paid2|free</code> — Установить режим\n"
            "/setlimit <code>число</code> — Установить дневной лимит в токенах\n"
            "/resetmodel — Сбросить режим на 'free'\n"
        )

        # Добавляем админские команды только для админов
        if is_admin(user_id):
            help_text += (
                "\n<b>Админ-команды:</b>\n"
                "/adduser, /removeuser, /listusers, /clearusers, /broadcast"
            )

        sent_message = await message.answer(help_text, reply_markup=MAIN_KEYBOARD)
        # Сохраняем message_id для последующего удаления
        save_last_help_message_id(user_id, sent_message.message_id)
    except Exception as e:
        logger.exception(f"Error in help_handler for user {user_id}: {e}")
        await message.answer(ERROR_MESSAGE, reply_markup=MAIN_KEYBOARD)

