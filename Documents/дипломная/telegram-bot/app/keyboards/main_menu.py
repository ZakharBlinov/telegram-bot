from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_keyboard():
    """Главное меню бота"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Поделиться локацией", request_location=True)],
            [KeyboardButton(text="🔍 Найти события"), KeyboardButton(text="🔍 Найти людей")],
            [KeyboardButton(text="📅 Мои события"), KeyboardButton(text="📊 Мой профиль")],
            [KeyboardButton(text="🔔 Уведомления"), KeyboardButton(text="➕ Создать событие")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )

def get_cancel_keyboard():
    """Клавиатура для отмены действий"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )

async def get_main_keyboard_with_badges(session, user_id: int):
    """Главное меню с бейджами уведомлений"""
    from app.service.notification_service import NotificationService
    
    unread_count = await NotificationService.get_unread_count(session, user_id)
    
    notifications_text = f"🔔 Уведомления ({unread_count})" if unread_count > 0 else "🔔 Уведомления"
    
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Поделиться локацией", request_location=True)],
            [KeyboardButton(text="🔍 Найти события"), KeyboardButton(text="🔍 Найти людей")],
            [KeyboardButton(text="📅 Мои события"), KeyboardButton(text="📊 Мой профиль")],
            [KeyboardButton(text="💝 Мои матчи"), KeyboardButton(text="💬 Мои чаты")],
            [KeyboardButton(text=notifications_text), KeyboardButton(text="➕ Создать событие")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )