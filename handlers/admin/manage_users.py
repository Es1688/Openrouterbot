"""
Обработчики команд для управления whitelist: добавление, удаление, список пользователей.
"""
from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from core import IsAdminFilter, MAIN_KEYBOARD, config, logger
from utils import load_authorized_users, save_authorized_users
from budget import set_daily_limit

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

@router.message(Command("setlimit"))
async def admin_setlimit_handler(message: Message, command: CommandObject):
    """Устанавливает дневной лимит токенов для указанного пользователя (только админ)."""
    if not command.args:
        await message.answer(
            "Использование: /setlimit <code>user_id</code> <code>лимит_токенов</code>\n"
            "Пример: /setlimit <code>123456789</code> <code>5000</code>",
            reply_markup=MAIN_KEYBOARD
        )
        return

    try:
        args = command.args.split()
        if len(args) != 2:
            raise ValueError("Неверное количество аргументов")
        target_user_id = int(args[0])
        limit = int(args[1])
        if limit < 0:
            raise ValueError("Лимит не может быть отрицательным")

        set_daily_limit(target_user_id, limit)
        await message.answer(
            f"✅ Установлен дневной лимит для пользователя <code>{target_user_id}</code>: {limit} токенов/день",
            reply_markup=MAIN_KEYBOARD
        )
        logger.info(f"Admin {message.from_user.id} set daily limit {limit} for user {target_user_id}")
    except (ValueError, IndexError) as e:
        logger.warning(f"Invalid /setlimit args from admin {message.from_user.id}: {e}")
        await message.answer(
            "Ошибка: Используйте /setlimit <user_id> <лимит_токенов> (оба — целые числа, лимит ≥ 0).",
            reply_markup=MAIN_KEYBOARD
        )
    except Exception as e:
        logger.exception(f"Error in admin_setlimit_handler: {e}")
        await message.answer(ERROR_MESSAGE, reply_markup=MAIN_KEYBOARD)

