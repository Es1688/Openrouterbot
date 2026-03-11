"""
Инициализация пакета handlers.

Экспортирует роутеры из модулей admin_handlers и user_handlers
для удобной регистрации в главном файле бота.
"""
from .admin_handlers import router as admin_router
from .user_handlers import router as user_router

__all__ = [
    "admin_router",
    "user_router",
]

