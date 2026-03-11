"""
Основной модуль Telegram-бота для OpenRouter.
Инициализирует и запускает бота, регистрирует обработчики из других модулей.
"""

import asyncio
from handlers.user import routers as user_routers
from handlers.admin import routers as admin_routers
from api import validate_api_key
from core import bot, config, dp, logger
from utils import ensure_dirs

async def main():
    """Основная функция запуска бота."""
    ensure_dirs()
    logger.info("Starting OpenRouter Bot...")

    # Регистрация всех пользовательских и админских обработчиков
    for router in user_routers + admin_routers:
        dp.include_router(router)

    if not config.admin_users:
        logger.warning("ADMIN_USERS не задан в .env. Функции администратора будут недоступны.")

    # Проверяем API-ключ при старте (но не падаем)
    if config.api_key:
        validation = validate_api_key(config.api_key, config.app_url, config.app_name)
        if not validation["valid"]:
            logger.error("API-ключ недействителен! Функции чата будут недоступны.")
    else:
        logger.warning("OPENROUTER_API_KEY не задан. Функции чата отключены.")

    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())

