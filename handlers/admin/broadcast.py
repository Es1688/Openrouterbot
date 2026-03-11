#**Примечание**:  
# - В продакшене стоит добавить **подтверждение** (FSM) перед отправкой, чтобы избежать случайных рассылок.  
# - Также можно добавить **ограничение длины** и **форматирование**.  
# - Для 100+ пользователей — добавить **задержку** между отправками, чтобы не превысить лимиты Telegram API.



"""
Обработчики для рассылки сообщений администратором всем пользователям.
"""
import logging
from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from core import IsAdminFilter, MAIN_KEYBOARD, logger
from utils import load_authorized_users

router = Router()
router.message.filter(IsAdminFilter())


@router.message(Command("broadcast"))
async def broadcast_handler(message: Message, command: CommandObject):
    """Рассылка сообщения всем авторизованным пользователям."""
    if not command.args:
        await message.answer(
            "Использование: /broadcast <сообщение>\n"
            "Сообщение будет отправлено всем авторизованным пользователям.",
            reply_markup=MAIN_KEYBOARD
        )
        return

    text = command.args
    authorized_users = load_authorized_users()
    success_count = 0
    error_count = 0

    await message.answer(f"📤 Начинаю рассылку для {len(authorized_users)} пользователей...", reply_markup=MAIN_KEYBOARD)

    for user_id in authorized_users:
        try:
            await message.bot.send_message(user_id, f"📢 <b>Сообщение от администратора:</b>\n\n{text}")
            success_count += 1
        except Exception as e:
            logger.warning(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
            error_count += 1

    await message.answer(
        f"✅ Рассылка завершена!\n"
        f"Успешно: {success_count}\n"
        f"Ошибок: {error_count}",
        reply_markup=MAIN_KEYBOARD
    )
    logger.info(f"Broadcast completed: {success_count} success, {error_count} errors")

