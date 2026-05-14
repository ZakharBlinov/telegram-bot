from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery
from aiogram.filters import StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.service.chat_service import ChatService
from app.service.user_service import UserService
from app.service.match_service import MatchService
from app.keyboards.main_menu import get_main_keyboard
from app.models import User  # Добавляем импорт User

router = Router()

class ChatStates(StatesGroup):
    viewing_chats = State()
    in_chat = State()
    waiting_message = State()

def get_chats_keyboard():
    """Клавиатура для раздела чатов"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💌 Написать сообщение"), KeyboardButton(text="📋 Список чатов")],
            [KeyboardButton(text="🔍 Новые матчи"), KeyboardButton(text="🏠 В главное меню")]
        ],
        resize_keyboard=True
    )

def get_chat_keyboard():
    """Клавиатура внутри чата"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💬 Написать сообщение")],
            [KeyboardButton(text="📋 К списку чатов"), KeyboardButton(text="🚫 Заблокировать")],
            [KeyboardButton(text="🏠 В главное меню")]
        ],
        resize_keyboard=True
    )

def get_back_to_chats_keyboard():
    """Клавиатура для возврата к чатам"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 К списку чатов")],
            [KeyboardButton(text="🏠 В главное меню")]
        ],
        resize_keyboard=True
    )

@router.message(F.text == "💬 Мои чаты")
async def show_my_chats(message: Message, session: AsyncSession, state: FSMContext):
    """Показать список чатов пользователя"""
    chats = await ChatService.get_user_chats(session, message.from_user.id)
    
    if not chats:
        # Показываем матчи, с которыми можно начать чат
        matches = await MatchService.get_mutual_matches(session, message.from_user.id)
        
        if not matches:
            await message.answer(
                "💬 <b>У вас пока нет чатов</b>\n\n"
                "Начните общаться с вашими взаимными матчами!\n"
                "Для этого найдите людей через поиск и дождитесь взаимных лайков.",
                reply_markup=get_chats_keyboard(),
                parse_mode="HTML"
            )
        else:
            response = "💬 <b>Ваши матчи для общения</b>\n\n"
            response += "У вас есть взаимные матчи! Начните общение:\n\n"
            
            for user, goal in matches[:5]:  # Показываем первые 5 матчей
                response += f"👤 <b>{user.full_name}</b> ({user.age} лет)\n"
                response += f"💭 Цель: {goal}\n"
                response += f"💌 Напишите: /chat_{user.telegram_id}\n\n"
            
            if len(matches) > 5:
                response += f"... и еще {len(matches) - 5} матчей\n\n"
            
            response += "👇 <b>Используйте кнопки ниже для управления чатами:</b>"
            
            await message.answer(
                response,
                reply_markup=get_chats_keyboard(),
                parse_mode="HTML"
            )
    else:
        await state.set_state(ChatStates.viewing_chats)
        await show_chats_list(message, session, state)

async def show_chats_list(message: Message, session: AsyncSession, state: FSMContext):
    """Показать список чатов"""
    chats = await ChatService.get_user_chats(session, message.from_user.id)
    
    if not chats:
        await message.answer(
            "💬 <b>Чатов не найдено</b>",
            reply_markup=get_chats_keyboard()
        )
        return
    
    response = "💬 <b>Ваши чаты</b>\n\n"
    
    for i, (chat, user, unread_count) in enumerate(chats[:10], 1):  # Ограничиваем 10 чатами
        last_message = await ChatService.get_last_message(session, message.from_user.id, user.telegram_id)
        
        unread_badge = f" 🔔{unread_count}" if unread_count > 0 else ""
        last_msg_preview = last_message.message_text[:50] + "..." if last_message and len(last_message.message_text) > 50 else last_message.message_text if last_message else "Нет сообщений"
        
        response += f"{i}. <b>{user.full_name}</b>{unread_badge}\n"
        response += f"   💬 {last_msg_preview}\n"
        response += f"   🕐 {chat.last_message_at.strftime('%d.%m.%Y %H:%M') if chat.last_message_at else 'Нет сообщений'}\n"
        response += f"   💌 Напишите: /chat_{user.telegram_id}\n\n"
    
    if len(chats) > 10:
        response += f"... и еще {len(chats) - 10} чатов\n\n"
    
    response += "👇 <b>Выберите чат для общения или используйте кнопки:</b>"
    
    await state.update_data(chats=chats)
    await message.answer(
        response,
        reply_markup=get_chats_keyboard(),
        parse_mode="HTML"
    )

@router.message(F.text.startswith("/chat_"))
async def start_chat(message: Message, session: AsyncSession, state: FSMContext):
    """Начать чат с пользователем по команде"""
    try:
        target_user_id = int(message.text.replace("/chat_", ""))
        
        # Проверяем, есть ли взаимный матч
        matches = await MatchService.get_mutual_matches(session, message.from_user.id)
        target_user = None
        
        for user, goal in matches:
            if user.telegram_id == target_user_id:
                target_user = user
                break
        
        if not target_user:
            await message.answer(
                "❌ <b>Нельзя начать чат</b>\n\n"
                "Чат возможен только с взаимными матчами.",
                reply_markup=get_main_keyboard(),
                parse_mode="HTML"
            )
            return
        
        await state.set_state(ChatStates.in_chat)
        await state.update_data(current_chat_user_id=target_user_id)
        
        # Помечаем сообщения как прочитанные
        await ChatService.mark_messages_as_read(session, message.from_user.id, target_user_id)
        
        # Показываем историю сообщений
        await show_chat_history(message, session, state, target_user)
        
    except ValueError:
        await message.answer("❌ Неверный формат команды")

async def show_chat_history(message: Message, session: AsyncSession, state: FSMContext, target_user: User = None):
    """Показать историю чата"""
    data = await state.get_data()
    target_user_id = data.get('current_chat_user_id')
    
    if not target_user:
        target_user = await UserService.get_user_by_telegram_id(session, target_user_id)
    
    if not target_user:
        await message.answer("❌ Пользователь не найден")
        await state.clear()
        return
    
    # Получаем историю сообщений
    messages = await ChatService.get_chat_messages(session, message.from_user.id, target_user_id, limit=20)
    
    response = f"💬 <b>Чат с {target_user.full_name}</b>\n\n"
    
    if not messages:
        response += "💭 <b>Нет сообщений</b>\n\n"
        response += "Напишите первое сообщение!"
    else:
        for msg in messages:
            time_str = msg.created_at.strftime('%H:%M')
            if msg.from_user_id == message.from_user.id:
                response += f"<b>Вы</b> ({time_str}): {msg.message_text}\n"
            else:
                response += f"<b>{target_user.full_name}</b> ({time_str}): {msg.message_text}\n"
    
    response += "\n👇 <b>Используйте кнопки для управления чатом:</b>"
    
    await message.answer(
        response,
        reply_markup=get_chat_keyboard(),
        parse_mode="HTML"
    )

@router.message(ChatStates.in_chat, F.text == "💬 Написать сообщение")
async def start_writing_message(message: Message, state: FSMContext):
    """Начать ввод сообщения"""
    await state.set_state(ChatStates.waiting_message)
    await message.answer(
        "💭 <b>Введите ваше сообщение:</b>\n\n"
        "Или отправьте /cancel для отмены",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отмена")]],
            resize_keyboard=True
        ),
        parse_mode="HTML"
    )

@router.message(ChatStates.waiting_message, F.text)
async def process_message_input(message: Message, state: FSMContext, session: AsyncSession):
    """Обработать введенное сообщение"""
    if message.text == "❌ Отмена":
        await state.set_state(ChatStates.in_chat)
        data = await state.get_data()
        target_user_id = data.get('current_chat_user_id')
        target_user = await UserService.get_user_by_telegram_id(session, target_user_id)
        await show_chat_history(message, session, state, target_user)
        return
    
    if len(message.text) > 1000:
        await message.answer("❌ Сообщение слишком длинное. Максимум 1000 символов.")
        return
    
    data = await state.get_data()
    target_user_id = data.get('current_chat_user_id')
    
    # Отправляем сообщение
    sent_message = await ChatService.send_message(
        session=session,
        from_user_id=message.from_user.id,
        to_user_id=target_user_id,
        message_text=message.text
    )
    
    if sent_message:
        await message.answer("✅ <b>Сообщение отправлено!</b>", parse_mode="HTML")
        
        # Возвращаемся в чат
        await state.set_state(ChatStates.in_chat)
        target_user = await UserService.get_user_by_telegram_id(session, target_user_id)
        await show_chat_history(message, session, state, target_user)
    else:
        await message.answer(
            "❌ <b>Не удалось отправить сообщение</b>\n\n"
            "Возможно, матч был удален или пользователь заблокирован.",
            parse_mode="HTML"
        )
        await state.set_state(ChatStates.viewing_chats)
        await show_chats_list(message, session, state)

@router.message(ChatStates.in_chat, F.text == "📋 К списку чатов")
async def back_to_chats_list(message: Message, state: FSMContext, session: AsyncSession):
    """Вернуться к списку чатов"""
    await state.set_state(ChatStates.viewing_chats)
    await show_chats_list(message, session, state)

@router.message(ChatStates.in_chat, F.text == "🚫 Заблокировать")
async def block_chat(message: Message, state: FSMContext, session: AsyncSession):
    """Заблокировать чат"""
    data = await state.get_data()
    target_user_id = data.get('current_chat_user_id')
    
    success = await ChatService.delete_chat(session, message.from_user.id, target_user_id)
    
    if success:
        await message.answer(
            "✅ <b>Чат заблокирован</b>\n\n"
            "Вы больше не будете получать сообщения от этого пользователя.",
            reply_markup=get_chats_keyboard(),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "❌ <b>Ошибка блокировки чата</b>",
            reply_markup=get_chats_keyboard(),
            parse_mode="HTML"
        )
    
    await state.set_state(ChatStates.viewing_chats)
    await show_chats_list(message, session, state)

@router.message(F.text == "💌 Написать сообщение")
async def write_to_match(message: Message, session: AsyncSession, state: FSMContext):
    """Написать сообщение матчу"""
    matches = await MatchService.get_mutual_matches(session, message.from_user.id)
    
    if not matches:
        await message.answer(
            "❌ <b>Нет матчей для общения</b>\n\n"
            "Сначала найдите взаимные матчи через поиск людей.",
            reply_markup=get_chats_keyboard(),
            parse_mode="HTML"
        )
        return
    
    response = "💌 <b>Выберите матч для общения:</b>\n\n"
    
    for i, (user, goal) in enumerate(matches[:10], 1):
        response += f"{i}. <b>{user.full_name}</b> ({user.age} лет)\n"
        response += f"   💭 {goal}\n"
        response += f"   💌 Напишите: /chat_{user.telegram_id}\n\n"
    
    if len(matches) > 10:
        response += f"... и еще {len(matches) - 10} матчей\n\n"
    
    response += "👇 <b>Используйте команду /chat_ID для начала общения</b>"
    
    await message.answer(
        response,
        reply_markup=get_chats_keyboard(),
        parse_mode="HTML"
    )

@router.message(StateFilter(ChatStates), F.text == "🏠 В главное меню")
async def back_to_main_from_chat(message: Message, state: FSMContext):
    """Вернуться в главное меню из чата"""
    await state.clear()
    await message.answer(
        "Возвращаемся в главное меню...",
        reply_markup=get_main_keyboard()
    )