# middleware.py
from aiogram import BaseMiddleware
from aiogram.types import Message
from utils import delete_last_help_message

class HelpMessageCleanupMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Message, data):
        if event.from_user:
            await delete_last_help_message(event.bot, event.from_user.id)
        return await handler(event, data)
