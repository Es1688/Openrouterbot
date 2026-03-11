"""
Обработчики команд для администраторов бота.
"""
from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from core import IsAdminFilter, MAIN_KEYBOARD, config, logger
from utils import load_authorized_users, save_authorized_users

# ИСПРАВЛЕНИЕ: Стандартизированное имя переменной
router = Router()
router.message.filter(IsAdminFilter())


@router.message(Command("adduser"))
async def adduser_handler(message: Message, command: CommandObject):
    """Добавляет пользователя в whitelist."""
    if not command.args:
        await message.answer("Укажите user_id: /adduser <telegram_id>", reply_markup=MAIN_KEYBOARD)
        return
    try:
        new_user_id = int(command.args.split()[0])
        authorized = load_authorized_users()
        if new_user_id in authorized:
            await message.answer(f"Пользователь {new_user_id} уже авторизован.", reply_markup=MAIN_KEYBOARD)
            return
        authorized.append(new_user_id)
        save_authorized_users(authorized)
        logger.info(f"Admin {message.from_user.id} added user {new_user_id}")
        await message.answer(f"✅ Пользователь {new_user_id} добавлен в whitelist.", reply_markup=MAIN_KEYBOARD)
    except (ValueError, IndexError):
        await message.answer("Ошибка: user_id должен быть целым числом.", reply_markup=MAIN_KEYBOARD)


@router.message(Command("removeuser"))
async def removeuser_handler(message: Message, command: CommandObject):
    """Удаляет пользователя из whitelist."""
    if not command.args:
        await message.answer("Укажите user_id: /removeuser <telegram_id>", reply_markup=MAIN_KEYBOARD)
        return
    try:
        remove_id = int(command.args.split()[0])
        if remove_id in config.admin_users:
            await message.answer("❌ Нельзя удалить администратора.", reply_markup=MAIN_KEYBOARD)
            return
        authorized = load_authorized_users()
        if remove_id not in authorized:
            await message.answer(f"Пользователь {remove_id} не найден в whitelist.", reply_markup=MAIN_KEYBOARD)
            return
        authorized.remove(remove_id)
        save_authorized_users(authorized)
        logger.info(f"Admin {message.from_user.id} removed user {remove_id}")
        await message.answer(f"✅ Пользователь {remove_id} удален из whitelist.", reply_markup=MAIN_KEYBOARD)
    except (ValueError, IndexError):
        await message.answer("Ошибка: user_id должен быть целым числом.", reply_markup=MAIN_KEYBOARD)


@router.message(Command("listusers"))
async def listusers_handler(message: Message):
    """Показывает список всех авторизованных пользователей."""
    authorized = load_authorized_users()
    admins = sorted(config.admin_users)
    users = sorted([u for u in authorized if u not in admins])

    text = f"<b>Авторизованные пользователи ({len(authorized)}):</b>\n\n"
    if admins:
        text += f"<u>Администраторы ({len(admins)}):</u>\n" + "\n".join(f"• <code>{uid}</code>" for uid in admins) + "\n\n"
    if users:
        text += f"<u>Пользователи ({len(users)}):</u>\n" + "\n".join(f"• <code>{uid}</code>" for uid in users)
    elif not admins:
        text += "Whitelist пуст."
    
    await message.answer(text, reply_markup=MAIN_KEYBOARD)


@router.message(Command("clearusers"))
async def clearusers_handler(message: Message):
    """Очищает whitelist, оставляя только администраторов."""
    save_authorized_users([])  # Сохраняет пустой список, админы остаются через config
    logger.info(f"Admin {message.from_user.id} cleared whitelist")
    await message.answer("✅ Whitelist очищен (остались только администраторы).", reply_markup=MAIN_KEYBOARD)

