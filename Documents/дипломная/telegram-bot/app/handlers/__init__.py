from .start import router as start_router
from .location import router as location_router
from .buttons import router as buttons_router
from .events import router as events_router
from .profile import router as profile_router
from .event_management import router as event_management_router
from .search import router as search_router
from .notifications import router as notifications_router

def register_handlers(dp):
    """Регистрация всех обработчиков - ВАЖЕН ПОРЯДОК!"""
    dp.include_router(start_router)
    dp.include_router(location_router)
    dp.include_router(buttons_router)
    dp.include_router(events_router)
    dp.include_router(profile_router)
    dp.include_router(event_management_router)
    dp.include_router(search_router)
    dp.include_router(notifications_router)