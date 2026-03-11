"""
Обработчики основного функционала: чат, выбор модели, управление сессиями и бюджетом.
"""
import asyncio
import re
import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.exceptions import TelegramBadRequest

from api import chat_completion, get_balance, pick_models_in_order
from budget import can_send, get_today_spent, reset_daily, set_daily_limit, update_spent
from core import (ALLOWED_MODES, MAIN_KEYBOARD, IsAuthorizedFilter, config,
                  load_user_config, logger, save_user_config, set_mode_and_reply)
from history import (add_message, create_session, delete_session, export_session,
                     list_sessions, load_session)
from states import Confirmation
from utils import split_long_message, ts_to_time, clean_and_format_ai_response, is_admin

router = Router()
router.message.filter(IsAuthorizedFilter())

# --- Клавиатура подтверждения для сброса ---
CONFIRM_RESET_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="✅ Да, очистить"),
            KeyboardButton(text="❌ Нет")
        ]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

# Стандартное сообщение об ошибке
ERROR_MESSAGE = "❌ Произошла ошибка при обработке запроса. Администратор уведомлён. Попробуйте позже."


@router.message(F.text.startswith("Выбрать "))
async def handle_model_button(message: Message):
    user_id = message.from_user.id
    logger.info(f"Model button pressed by user {user_id}: {message.text}")

    try:
        match = re.search(r'\((\w+)\)', message.text)
        if match:
            mode = match.group(1).lower()
            if mode in ALLOWED_MODES:
                await set_mode_and_reply(message, mode)
                logger.info(f"Mode changed to {mode} for user {user_id}")
            else:
                logger.warning(f"Invalid mode '{mode}' from button '{message.text}' for user {user_id}")
                await message.answer(f"Режим {mode} не разрешен. Доступны: {', '.join(ALLOWED_MODES)}", reply_markup=MAIN_KEYBOARD)
        else:
            await message.answer("Не удалось распознать кнопку модели.", reply_markup=MAIN_KEYBOARD)
    except Exception as e:
        logger.exception(f"Error in handle_model_button for user {user_id}: {e}")
        await message.answer(ERROR_MESSAGE, reply_markup=MAIN_KEYBOARD)


@router.message(Command("paid1", "paid2", "free"))
async def mode_command_handler(message: Message, command: CommandObject):
    user_id = message.from_user.id
    logger.info(f"Mode command '{command.command}' from user {user_id}")

    try:
        await set_mode_and_reply(message, command.command)
        logger.info(f"Mode set to {command.command} for user {user_id}")
    except Exception as e:
        logger.exception(f"Error in mode_command_handler for user {user_id}: {e}")
        await message.answer(ERROR_MESSAGE, reply_markup=MAIN_KEYBOARD)


@router.message(Command("setmodel"))
async def setmodel_handler(message: Message, command: CommandObject):
    user_id = message.from_user.id
    logger.info(f"Setmodel command from user {user_id}: {command.args}")

    try:
        if not command.args:
            await message.answer("Укажите режим: /setmodel <paid1|paid2|free>", reply_markup=MAIN_KEYBOARD)
            return
        await set_mode_and_reply(message, command.args.lower())
        logger.info(f"Mode set via /setmodel to {command.args.lower()} for user {user_id}")
    except Exception as e:
        logger.exception(f"Error in setmodel_handler for user {user_id}: {e}")
        await message.answer(ERROR_MESSAGE, reply_markup=MAIN_KEYBOARD)


@router.message(Command("resetmodel"))
async def resetmodel_handler(message: Message):
    user_id = message.from_user.id
    logger.info(f"Resetmodel command from user {user_id}")

    try:
        await set_mode_and_reply(message, "free")
        logger.info(f"Mode reset to free for user {user_id}")
    except Exception as e:
        logger.exception(f"Error in resetmodel_handler for user {user_id}: {e}")
        await message.answer(ERROR_MESSAGE, reply_markup=MAIN_KEYBOARD)


@router.message(Command("models"))
async def models_handler(message: Message):
    user_id = message.from_user.id
    logger.info(f"Models info requested by user {user_id}")

    try:
        user_cfg = load_user_config(user_id)
        current_mode = user_cfg["mode"]
        
        text = "<b>Доступные режимы и модели (из .env):</b>\n\n"
        models = [
            (config.paid_model_1, "paid1"),
            (config.paid_model_2, "paid2"),
            (config.free_model, "free")
        ]
        
        for model_id, mode in models:
            text += f"<b>{mode.upper()}</b>: <code>{model_id}</code>\n\n"
        
        text += f"Текущий режим: <b>{current_mode}</b>"
        await message.answer(text, reply_markup=MAIN_KEYBOARD)
    except Exception as e:
        logger.exception(f"Error in models_handler for user {user_id}: {e}")
        await message.answer(ERROR_MESSAGE, reply_markup=MAIN_KEYBOARD)


# --- Обновленный обработчик сброса ---
@router.message(F.text == "Очистить контекст")
@router.message(Command("reset"))
async def reset_handler(message: Message, state: FSMContext):
    user_id = message.from_user.id
    logger.info(f"Reset requested by user {user_id}")

    try:
        await message.answer(
            "⚠️ Вы уверены, что хотите очистить контекст и начать новую сессию?\n"
            "Дневной лимит токенов не будет сброшен.",
            reply_markup=CONFIRM_RESET_KEYBOARD
        )
        await state.set_state(Confirmation.awaiting_reset_confirmation)
    except Exception as e:
        logger.exception(f"Error in reset_handler for user {user_id}: {e}")
        await message.answer(ERROR_MESSAGE, reply_markup=MAIN_KEYBOARD)


@router.message(Confirmation.awaiting_reset_confirmation, F.text == "✅ Да, очистить")
async def confirm_reset(message: Message, state: FSMContext):
    user_id = message.from_user.id
    logger.info(f"Reset confirmed by user {user_id}")

    try:
        user_cfg = load_user_config(user_id)
        new_session_id = create_session(user_id, "Сброшенная сессия")
        user_cfg["session_id"] = new_session_id
        save_user_config(user_id, user_cfg)
        
        await message.answer(f"✅ Контекст очищен. Создана новая сессия: <code>{new_session_id}</code>", reply_markup=MAIN_KEYBOARD)
        logger.info(f"Reset completed for user {user_id}, new session {new_session_id}. Budget was not reset.")
    except Exception as e:
        logger.exception(f"Error in confirm_reset for user {user_id}: {e}")
        await message.answer(ERROR_MESSAGE, reply_markup=MAIN_KEYBOARD)
    finally:
        await state.clear()


@router.message(Confirmation.awaiting_reset_confirmation, F.text == "❌ Нет")
async def cancel_reset(message: Message, state: FSMContext):
    user_id = message.from_user.id
    logger.info(f"Reset cancelled by user {user_id}")

    try:
        await message.answer("❌ Сброс отменён.", reply_markup=MAIN_KEYBOARD)
    except Exception as e:
        logger.exception(f"Error in cancel_reset for user {user_id}: {e}")
        await message.answer(ERROR_MESSAGE, reply_markup=MAIN_KEYBOARD)
    finally:
        await state.clear()


@router.message(Confirmation.awaiting_reset_confirmation)
async def unexpected_input_during_confirmation(message: Message, state: FSMContext):
    user_id = message.from_user.id
    logger.warning(f"Unexpected input during confirmation from user {user_id}: {message.text}")

    try:
        await message.answer(
            "Пожалуйста, используйте кнопки для подтверждения.",
            reply_markup=CONFIRM_RESET_KEYBOARD
        )
    except Exception as e:
        logger.exception(f"Error in unexpected_input_during_confirmation for user {user_id}: {e}")
        await message.answer(ERROR_MESSAGE, reply_markup=MAIN_KEYBOARD)


@router.message(Command("budget"))
async def budget_handler(message: Message):
    user_id = message.from_user.id
    logger.info(f"Budget info requested by user {user_id}")

    try:
        today_data = get_today_spent(user_id)
        status = "✅ Можно отправлять" if can_send(user_id) else "❌ Лимит исчерпан"

        text = (
            f"<b>Токены на сегодня:</b>\n"
            f"Использовано: {today_data['used_tokens']} / Лимит: {today_data['limit']}\n"
            f"Статус: {status}"
        )

        if is_admin(user_id):
            balance_info = get_balance(config.api_key, config.app_url, config.app_name)
            balance = balance_info["balance"] if balance_info else 0.0
            text += f"\n\n<b>Баланс OpenRouter:</b> ${balance:.2f}"
        else:
            text += "\n\n<i>Баланс OpenRouter доступен только администраторам.</i>"

        await message.answer(text, reply_markup=MAIN_KEYBOARD)
        logger.debug(f"Budget shown for user {user_id}: used_tokens={today_data['used_tokens']}")
    except Exception as e:
        logger.exception(f"Error in budget_handler for user {user_id}: {e}")
        await message.answer(ERROR_MESSAGE, reply_markup=MAIN_KEYBOARD)


@router.message(Command("setlimit"))
async def setlimit_handler(message: Message, command: CommandObject):
    user_id = message.from_user.id
    logger.info(f"Setlimit command from user {user_id}: {command.args}")

    try:
        if not command.args:
            await message.answer("Укажите лимит: /setlimit <число_токенов>", reply_markup=MAIN_KEYBOARD)
            return
        limit = int(command.args.split()[0])
        if limit < 0:
            raise ValueError("Лимит не может быть отрицательным")
        set_daily_limit(user_id, limit)
        await message.answer(f"✅ Личный дневной лимит установлен: {limit} токенов/день", reply_markup=MAIN_KEYBOARD)
        logger.info(f"Daily limit set to {limit} tokens for user {user_id}")
    except (ValueError, IndexError) as e:
        logger.warning(f"Invalid limit input from user {user_id}: {e}")
        await message.answer("Ошибка: Лимит должен быть целым числом >= 0.", reply_markup=MAIN_KEYBOARD)
    except Exception as e:
        logger.exception(f"Error in setlimit_handler for user {user_id}: {e}")
        await message.answer(ERROR_MESSAGE, reply_markup=MAIN_KEYBOARD)


@router.message(Command("sessions"))
async def sessions_handler(message: Message):
    user_id = message.from_user.id
    logger.info(f"Sessions list requested by user {user_id}")

    try:
        sessions = list_sessions(user_id)
        if not sessions:
            await message.answer("У вас пока нет сессий.", reply_markup=MAIN_KEYBOARD)
            return
        
        text = "<b>Ваши последние сессии:</b>\n\n"
        for s in sessions[:10]:
            created = ts_to_time(s["created"])
            text += f"• {s['title']} (<code>{s['id']}</code>)\n  <i>{s['turns']} сообщ., созд. {created}</i>\n"
        await message.answer(text, reply_markup=MAIN_KEYBOARD)
        logger.debug(f"Sessions list shown for user {user_id}: {len(sessions)} sessions")
    except Exception as e:
        logger.exception(f"Error in sessions_handler for user {user_id}: {e}")
        await message.answer(ERROR_MESSAGE, reply_markup=MAIN_KEYBOARD)


@router.message(Command("newsession"))
async def newsession_handler(message: Message, command: CommandObject):
    user_id = message.from_user.id
    title = command.args if command.args else "Новая сессия"
    logger.info(f"New session creation requested by user {user_id}: title='{title}'")

    try:
        session_id = create_session(user_id, title)
        user_cfg = load_user_config(user_id)
        user_cfg["session_id"] = session_id
        save_user_config(user_id, user_cfg)
        await message.answer(f"✅ Создана и активирована новая сессия «{title}» (<code>{session_id}</code>)", reply_markup=MAIN_KEYBOARD)
        logger.info(f"New session created for user {user_id}: {session_id}")
    except Exception as e:
        logger.exception(f"Error in newsession_handler for user {user_id}: {e}")
        await message.answer(ERROR_MESSAGE, reply_markup=MAIN_KEYBOARD)


@router.message(Command("switchsession"))
async def switchsession_handler(message: Message, command: CommandObject):
    user_id = message.from_user.id
    logger.info(f"Switch session command from user {user_id}: {command.args}")

    try:
        if not command.args:
            await message.answer("Укажите ID сессии для переключения: /switchsession <id>", reply_markup=MAIN_KEYBOARD)
            return
        
        session_id_prefix = command.args.strip()
        sessions = list_sessions(user_id)
        full_session_id = next((s['id'] for s in sessions if s['id'].startswith(session_id_prefix)), None)
        
        if full_session_id:
            user_cfg = load_user_config(user_id)
            user_cfg["session_id"] = full_session_id
            save_user_config(user_id, user_cfg)
            await message.answer(f"✅ Переключено на сессию <code>{full_session_id}</code>", reply_markup=MAIN_KEYBOARD)
            logger.info(f"Session switched to {full_session_id} for user {user_id}")
        else:
            await message.answer(f"❌ Сессия с ID, начинающимся на <code>{session_id_prefix}</code>, не найдена.", reply_markup=MAIN_KEYBOARD)
    except Exception as e:
        logger.exception(f"Error in switchsession_handler for user {user_id}: {e}")
        await message.answer(ERROR_MESSAGE, reply_markup=MAIN_KEYBOARD)


@router.message(Command("deletesession"))
async def deletesession_handler(message: Message, command: CommandObject):
    user_id = message.from_user.id
    logger.info(f"Delete session command from user {user_id}: {command.args}")

    try:
        if not command.args:
            await message.answer("Укажите ID сессии для удаления: /deletesession <id>", reply_markup=MAIN_KEYBOARD)
            return
        
        session_id_prefix = command.args.strip()
        sessions = list_sessions(user_id)
        full_session_id = next((s['id'] for s in sessions if s['id'].startswith(session_id_prefix)), None)

        if not full_session_id:
            await message.answer(f"❌ Сессия с ID, начинающимся на <code>{session_id_prefix}</code>, не найдена.", reply_markup=MAIN_KEYBOARD)
            return

        if delete_session(user_id, full_session_id):
            await message.answer(f"✅ Сессия <code>{full_session_id}</code> удалена.", reply_markup=MAIN_KEYBOARD)
            logger.info(f"Session {full_session_id} deleted for user {user_id}")
        else:
            await message.answer(f"❌ Не удалось удалить сессию <code>{full_session_id}</code>.", reply_markup=MAIN_KEYBOARD)
    except Exception as e:
        logger.exception(f"Error in deletesession_handler for user {user_id}: {e}")
        await message.answer(ERROR_MESSAGE, reply_markup=MAIN_KEYBOARD)


@router.message(Command("export"))
async def export_handler(message: Message):
    user_id = message.from_user.id
    logger.info(f"Export session requested by user {user_id}")

    try:
        user_cfg = load_user_config(user_id)
        session_id = user_cfg["session_id"]
        export_path = export_session(user_id, session_id)
        document = FSInputFile(export_path)
        await message.answer_document(document, caption=f"Экспорт текущей сессии <code>{session_id}</code>", reply_markup=MAIN_KEYBOARD)
        logger.info(f"Session {session_id} exported for user {user_id}")
    except ValueError as e:
        logger.warning(f"ValueError in export_handler for user {user_id}: {e}")
        await message.answer(str(e), reply_markup=MAIN_KEYBOARD)
    except Exception as e:
        logger.exception(f"Error in export_handler for user {user_id}: {e}")
        await message.answer(ERROR_MESSAGE, reply_markup=MAIN_KEYBOARD)


@router.message(F.text & ~F.text.startswith("/"))
async def chat_handler(message: Message):
    user_id = message.from_user.id
    logger.info(f"Chat message from user {user_id}: len={len(message.text)}")

    try:
        if not config.api_key:
            await message.answer("❌ OPENROUTER_API_KEY не настроен. Обратитесь к администратору.", reply_markup=MAIN_KEYBOARD)
            logger.warning(f"API key missing in chat_handler for user {user_id}")
            return

        if not can_send(user_id):
            today_data = get_today_spent(user_id)
            await message.answer(f"❌ Лимит исчерпан: {today_data['used_tokens']} / {today_data['limit']} токенов", reply_markup=MAIN_KEYBOARD)
            return

        user_cfg = load_user_config(user_id)
        session_id = user_cfg["session_id"]
        mode = user_cfg["mode"]

        add_message(user_id, session_id, "user", message.text)
        history = load_session(user_id, session_id)
        context_messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in history[-config.context_turns * 2:]
        ]

        placeholder = await message.answer("🤖 Думаю...", reply_markup=MAIN_KEYBOARD)

        response = await asyncio.to_thread(
            chat_completion,
            messages=context_messages,
            mode=mode,
            api_key=config.api_key,
            app_url=config.app_url,
            app_name=config.app_name,
            max_tokens=config.max_tokens,
            temperature=config.temperature
        )
        
        ai_content = clean_and_format_ai_response(response["content"])
        tokens = response["tokens"]
        used_model = response.get("used_model", "unknown")

        add_message(user_id, session_id, "assistant", ai_content)
        update_spent(user_id, tokens)

        full_text = f"{ai_content}"
        model_signature = f"\n\n<i>(Модель: {used_model})</i>"
        
        parts = split_long_message(full_text, model_signature=model_signature)
        
        try:
            await placeholder.edit_text(parts[0])
        except TelegramBadRequest:
            await message.answer(parts[0])

        for part in parts[1:]:
            await message.answer(part)

        logger.info(f"Chat response sent to user {user_id}: model={used_model}, tokens={tokens}")

    except ValueError as e:
        logger.warning(f"ValueError in chat_handler for user {user_id}: {e}")
        error_msg = f"<b>Ошибка API:</b>\n{e}"
        try:
            await placeholder.edit_text(error_msg)
        except (TelegramBadRequest, NameError):
            await message.answer(error_msg)
    except Exception as e:
        logger.exception(f"Unhandled error in chat_handler for user {user_id}: {e}")
        error_msg = ERROR_MESSAGE
        try:
            await placeholder.edit_text(error_msg)
        except (TelegramBadRequest, NameError):
            await message.answer(error_msg)

