from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.fsm.context import FSMContext

from app.service.user_service import UserService
from app.keyboards.main_menu import get_main_keyboard, get_main_keyboard_with_badges
from app.handlers.profile import UserProfile

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext):
    """Обработка команды /start"""
    user = await UserService.get_or_create_user(
        session=session,
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=f"{message.from_user.first_name} {message.from_user.last_name or ''}"
    )
    
    if not user.profile_completed:
        await state.set_state(UserProfile.waiting_for_name)
        await message.answer(
            "👋 <b>Добро пожаловать!</b>\n\n"
            "📝 Давайте заполним ваш профиль!\n\n"
            "Введите ваше <b>имя</b> (как к вам обращаться):",
            parse_mode="HTML"
        )
    else:
        welcome_text = (
            f"👋 Привет, {user.full_name}!\n\n"
            "Я - геолокационная платформа для поиска событий и людей рядом с вами.\n\n"
            "📍 <b>Доступные функции:</b>\n"
            "• Создание событий и поиск рядом\n"
            "• Поиск людей по интересам\n"
            "• Лайки и взаимные матчи\n"
            "• Личные сообщения\n"
            "• Уведомления о активности\n\n"
            "🔔 <b>Новые уведомления</b> будут появляться на кнопке меню!"
        )
        
        keyboard = await get_main_keyboard_with_badges(session, message.from_user.id)
        
        await message.answer(
            welcome_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )