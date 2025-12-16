from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery
from aiogram.filters import StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.service.notification_service import NotificationService
from app.service.user_service import UserService
from app.keyboards.main_menu import get_main_keyboard

router = Router()

class NotificationStates(StatesGroup):
    viewing_notifications = State()

def get_notifications_keyboard():
    """Клавиатура для раздела уведомлений"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔔 Непрочитанные")],
            [KeyboardButton(text="🗑️ Очистить все"), KeyboardButton(text="✅ Прочитать все")],
            [KeyboardButton(text="🏠 В главное меню")]
        ],
        resize_keyboard=True
    )

@router.message(F.text == "🔔 Уведомления")
async def show_notifications_menu(message: Message, session: AsyncSession):
    """Показать меню уведомлений"""
    unread_count = await NotificationService.get_unread_count(session, message.from_user.id)
    
    unread_badge = f" ({unread_count} новых)" if unread_count > 0 else ""
    
    await message.answer(
        f"🔔 <b>Уведомления{unread_badge}</b>\n\n"
        f"💝 Новые лайки, матчи и сообщения\n"
        f"👀 Просмотры вашего профиля\n"
        f"📍 События рядом с вами\n\n"
        f"👇 <b>Выберите действие:</b>",
        reply_markup=get_notifications_keyboard(),
        parse_mode="HTML"
    )

@router.message(F.text == "🔔 Непрочитанные")
async def show_unread_notifications(message: Message, session: AsyncSession, state: FSMContext):
    """Показать непрочитанные уведомления"""
    notifications = await NotificationService.get_user_notifications(
        session, message.from_user.id, unread_only=True, limit=20
    )
    
    if not notifications:
        await message.answer(
            "✅ <b>Нет непрочитанных уведомлений</b>\n\n"
            "Все уведомления прочитаны!",
            reply_markup=get_notifications_keyboard(),
            parse_mode="HTML"
        )
        return
    
    await state.set_state(NotificationStates.viewing_notifications)
    await show_notifications_list(message, session, notifications, "непрочитанные")

@router.message(F.text == "📋 Все уведомления")
async def show_all_notifications(message: Message, session: AsyncSession, state: FSMContext):
    """Показать все уведомления"""
    notifications = await NotificationService.get_user_notifications(
        session, message.from_user.id, limit=30
    )
    
    if not notifications:
        await message.answer(
            "📭 <b>Уведомлений нет</b>\n\n"
            "Здесь будут появляться уведомления о:\n"
            "• Новых лайках и матчах\n"
            "• Сообщениях от других пользователей\n"
            "• Просмотрах вашего профиля\n"
            "• Событиях рядом с вами",
            reply_markup=get_notifications_keyboard(),
            parse_mode="HTML"
        )
        return
    
    await state.set_state(NotificationStates.viewing_notifications)
    await show_notifications_list(message, session, notifications, "все")

async def show_notifications_list(message: Message, session: AsyncSession, notifications: list, list_type: str):
    """Показать список уведомлений"""
    response = f"🔔 <b>Ваши {list_type} уведомления</b>\n\n"
    
    for i, notification in enumerate(notifications, 1):
        type_emojis = {
            "new_like": "💝",
            "new_match": "💞",
            "new_message": "💬",
            "profile_view": "👀",
            "event_nearby": "📍",
            "system": "🔔"
        }
        
        emoji = type_emojis.get(notification.notification_type, "🔔")
        read_status = " ✅" if notification.is_read else " 🔔"
        
        from datetime import datetime
        time_diff = datetime.utcnow() - notification.created_at
        if time_diff.days > 0:
            time_str = f"{time_diff.days}д назад"
        elif time_diff.seconds > 3600:
            time_str = f"{time_diff.seconds // 3600}ч назад"
        elif time_diff.seconds > 60:
            time_str = f"{time_diff.seconds // 60}м назад"
        else:
            time_str = "только что"
        
        response += f"{i}. {emoji}{read_status} <b>{notification.title}</b>\n"
        response += f"   {notification.message}\n"
        response += f"   🕐 {time_str}\n\n"
    
    response += "👇 <b>Используйте кнопки для управления уведомлениями:</b>"
    
    await message.answer(
        response,
        reply_markup=get_notifications_keyboard(),
        parse_mode="HTML"
    )

@router.message(F.text == "✅ Прочитать все")
async def mark_all_as_read(message: Message, session: AsyncSession):
    """Пометить все уведомления как прочитанные"""
    success = await NotificationService.mark_as_read(session, user_id=message.from_user.id)
    
    if success:
        await message.answer(
            "✅ <b>Все уведомления помечены как прочитанные!</b>",
            reply_markup=get_notifications_keyboard(),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "❌ <b>Ошибка при обновлении уведомлений</b>",
            reply_markup=get_notifications_keyboard(),
            parse_mode="HTML"
        )

@router.message(F.text == "🗑️ Очистить все")
async def clear_all_notifications(message: Message, session: AsyncSession):
    """Очистить все уведомления"""
    success = await NotificationService.mark_as_read(session, user_id=message.from_user.id)
    
    if success:
        await message.answer(
            "🗑️ <b>Все уведомления очищены!</b>",
            reply_markup=get_notifications_keyboard(),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "❌ <b>Ошибка при очистке уведомлений</b>",
            reply_markup=get_notifications_keyboard(),
            parse_mode="HTML"
        )

@router.message(F.text == "🏠 В главное меню")
async def back_to_main_from_notifications(message: Message, state: FSMContext):
    """Вернуться в главное меню из уведомлений"""
    await state.clear()
    await message.answer(
        "Возвращаемся в главное меню...",
        reply_markup=get_main_keyboard()
    )