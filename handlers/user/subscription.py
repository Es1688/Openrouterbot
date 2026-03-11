"""
Обработчики, связанные с управлением подписками (заглушка для будущей функциональности).

В текущей версии бота подписки не поддерживаются.
Все пользователи используют общий дневной лимит токенов (MAX_TOKENS_PER_DAY).
"""
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from core import IsAuthorizedFilter, MAIN_KEYBOARD

router = Router()
router.message.filter(IsAuthorizedFilter())


@router.message(Command("mysub"))
async def my_subscription_handler(message: Message):
    """
    Заглушка команды для просмотра подписки.
    В будущем здесь будет отображаться:
    - текущий тариф
    - дата окончания
    - использованные ресурсы
    - кнопка продления
    """
    await message.answer(
        "ℹ️ Подписки пока не поддерживаются.\n"
        "Все пользователи используют общий дневной лимит токенов.\n"
        "Следите за обновлениями!",
        reply_markup=MAIN_KEYBOARD
    )

