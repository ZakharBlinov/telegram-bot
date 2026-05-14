from .start import router as start_router
from .location import router as location_router
from .buttons import router as buttons_router
from .events import router as events_router
from .profile import router as profile_router
from .event_management import router as event_management_router
from .search import router as search_router
from .notifications import router as notifications_router
from .matches import router as matches_router
from .chat import router as chat_router
from .extended_profile import router as extended_profile_router

def register_handlers(dp):
    dp.include_router(start_router)
    dp.include_router(location_router)
    dp.include_router(buttons_router)
    dp.include_router(events_router)
    dp.include_router(profile_router)
    dp.include_router(event_management_router)
    dp.include_router(search_router)
    dp.include_router(notifications_router)
    dp.include_router(matches_router)
    dp.include_router(chat_router)
    dp.include_router(extended_profile_router)