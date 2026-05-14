from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.service.event_service import EventService
from app.service.user_service import UserService
from app.keyboards.main_menu import get_main_keyboard, get_cancel_keyboard

router = Router()

class CreateEvent(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()

@router.message(StateFilter(CreateEvent), F.text == "❌ Отмена")
async def cancel_creation(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Создание события отменено.",
        reply_markup=get_main_keyboard()
    )

@router.message(F.text == "➕ Создать событие")
async def cmd_create_event(message: Message, state: FSMContext, session: AsyncSession):
    user_location = await UserService.get_user_location(
        session=session,
        telegram_id=message.from_user.id
    )
    
    if not user_location:
        await message.answer(
            "📍 <b>Сначала поделитесь локацией</b>\n\n"
            "Чтобы создать событие, нужно сначала поделиться своей геолокацией.\n\n"
            "Нажмите кнопку «📍 Поделиться локацией» в главном меню.",
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
    if message.text == "❌ Отмена":
        await cancel_creation(message, state)
        return
    
    data = await state.get_data()
    
    logging.info(f"Создание события: title={data['title']}, description={message.text[:50]}")
    
    event = await EventService.create_event(
        session=session,
        title=data['title'],
        description=message.text,
        latitude=float(data['user_location'].latitude),
        longitude=float(data['user_location'].longitude),
        author_id=message.from_user.id
    )
    
    await state.clear()
    
    logging.info(f"Результат создания: status={event.status}, rejection_reason={event.rejection_reason}")
    
    if event.status == "rejected":
        await message.answer(
            f"❌ <b>Событие НЕ опубликовано</b>\n\n"
            f"📌 <b>Название:</b> {event.title}\n\n"
            f"⚠️ <b>Причина отклонения:</b>\n{event.rejection_reason}\n\n"
            f"Пожалуйста, создайте событие без нецензурной лексики.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
    elif event.status == "pending":
        await message.answer(
            f"⏳ <b>Событие отправлено на модерацию</b>\n\n"
            f"📌 <b>Название:</b> {event.title}\n"
            f"📄 <b>Описание:</b> {event.description[:100]}\n\n"
            f"Администратор проверит событие в ближайшее время.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"✅ <b>Событие опубликовано!</b>\n\n"
            f"📌 <b>Название:</b> {event.title}\n"
            f"📄 <b>Описание:</b> {event.description}\n\n"
            f"Теперь другие пользователи смогут найти ваше событие!",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )