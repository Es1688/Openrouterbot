"""
Импорт и экспорт всех админских обработчиков.
"""
from .manage_users import router as manage_users_router
from .broadcast import router as broadcast_router

# Экспортируем список роутеров
routers = [
    manage_users_router,
    broadcast_router,
]

