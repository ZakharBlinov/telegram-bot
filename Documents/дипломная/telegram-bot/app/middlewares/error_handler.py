from aiogram import BaseMiddleware
from aiogram.types import Update
from typing import Callable, Dict, Any, Awaitable
import logging

class ErrorHandlerMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception as e:
            logging.error(f"Ошибка в обработчике: {e}", exc_info=True)
            
            # Можно отправить сообщение пользователю
            if hasattr(event, 'message') and event.message:
                try:
                    await event.message.answer(
                        "❌ Произошла ошибка. Пожалуйста, попробуйте позже."
                    )
                except:
                    pass
            
            return None