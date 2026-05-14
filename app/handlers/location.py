from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from app.service.user_service import UserService
from app.keyboards.main_menu import get_main_keyboard

router = Router()

@router.message(F.location)
async def handle_location(message: Message, session: AsyncSession):
    try:
        location = message.location
        latitude = location.latitude
        longitude = location.longitude
        
        user = await UserService.get_or_create_user(
            session=session,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            full_name=f"{message.from_user.first_name} {message.from_user.last_name or ''}"
        )
        
        await UserService.update_user_location(
            session=session,
            telegram_id=message.from_user.id,
            latitude=latitude,
            longitude=longitude
        )
        
        await message.answer(
            f"✅ <b>Локация сохранена!</b>\n\n"
            f"📍 <b>Координаты:</b>\n"
            f"Широта: {latitude}\n"
            f"Долгота: {longitude}\n\n"
            f"Теперь вы можете:\n"
            f"• Создавать события — кнопка «➕ Создать событие»\n"
            f"• Искать события рядом — кнопка «🔍 Найти события»",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
        
        logging.info(f"Пользователь {message.from_user.id} отправил локацию: {latitude}, {longitude}")
        
    except Exception as e:
        logging.error(f"Ошибка обработки локации: {e}")
        await message.answer(
            "❌ Произошла ошибка при сохранении локации.\n"
            "Попробуйте еще раз или перешлите геолокацию.",
            reply_markup=get_main_keyboard()
        )