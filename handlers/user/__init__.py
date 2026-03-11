"""
Импорт и экспорт всех пользовательских обработчиков.
"""
from .start import router as start_router
from .menu import router as menu_router
from .subscription import router as subscription_router

# Экспортируем список роутеров для удобного подключения в основном файле
routers = [
    start_router,
    menu_router,
    subscription_router,
]

