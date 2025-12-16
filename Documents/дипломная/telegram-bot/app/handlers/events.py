from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.service.event_service import EventService
from app.service.user_service import UserService
from app.keyboards.main_menu import get_main_keyboard, get_cancel_keyboard

router = Router()

class CreateEvent(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()

# Обработчик отмены должен работать во всех состояниях
@router.message(StateFilter(CreateEvent), F.text == "❌ Отмена")
async def cancel_creation(message: Message, state: FSMContext):
    """Отмена создания события из любого состояния"""
    await state.clear()
    await message.answer(
        "❌ Создание события отменено.",
        reply_markup=get_main_keyboard()
    )

@router.message(F.text == "➕ Создать событие")
async def cmd_create_event(message: Message, state: FSMContext, session: AsyncSession):
    """Начало создания события"""
    # Проверяем есть ли локация у пользователя
    user_location = await UserService.get_user_location(
        session=session,
        telegram_id=message.from_user.id
    )
    
    if not user_location:
        await message.answer(
            "📍 <b>Сначала поделитесь локацией</b>\n\n"
            "Чтобы создать событие, нужно сначала поделиться своей геолокацией.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
        return
    
    await state.set_state(CreateEvent.waiting_for_title)
    await state.update_data(user_location=user_location)
    
    await message.answer(
        "📝 <b>Создание нового события</b>\n\n"
        "Введите <b>название</b> для вашего события:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )

@router.message(CreateEvent.waiting_for_title, F.text)
async def process_title(message: Message, state: FSMContext):
    """Обработка названия события"""
    # Проверяем не является ли сообщение отменой
    if message.text == "❌ Отмена":
        await cancel_creation(message, state)
        return
    
    if len(message.text) > 200:
        await message.answer("❌ Слишком длинное название. Максимум 200 символов.")
        return
    
    await state.update_data(title=message.text)
    await state.set_state(CreateEvent.waiting_for_description)
    
    await message.answer(
        "📄 Теперь введите <b>описание</b> события:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )

@router.message(CreateEvent.waiting_for_description, F.text)
async def process_description(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка описания события"""
    # Проверяем не является ли сообщение отменой
    if message.text == "❌ Отмена":
        await cancel_creation(message, state)
        return
    
    data = await state.get_data()
    
    # Создаем событие
    event = await EventService.create_event(
        session=session,
        title=data['title'],
        description=message.text,
        latitude=float(data['user_location'].latitude),
        longitude=float(data['user_location'].longitude),
        author_id=message.from_user.id
    )
    
    await state.clear()
    
    await message.answer(
        f"🎉 <b>Событие создано!</b>\n\n"
        f"📌 <b>Название:</b> {event.title}\n"
        f"📄 <b>Описание:</b> {event.description}\n\n"
        f"Теперь другие пользователи смогут найти ваше событие рядом!",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )