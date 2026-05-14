import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import BaseMiddleware
from typing import Callable, Dict, Any, Awaitable

from app.config import Config
from app.database import init_db, get_session
from app.handlers import register_handlers

class DatabaseMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        async for session in get_session():
            data["session"] = session
            try:
                return await handler(event, data)
            except Exception as e:
                await session.rollback()
                raise e
            finally:
                await session.close()

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    config = Config()
    
    await init_db()
    logging.info("База данных инициализирована")
    
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())
    
    dp.update.middleware(DatabaseMiddleware())
    
    register_handlers(dp)
    
    try:
        logging.info("Бот запущен!")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logging.error(f"Ошибка при запуске бота: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())