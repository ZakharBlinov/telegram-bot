# app/handlers/event_management.py
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.service.event_service import EventService
from app.keyboards.main_menu import get_main_keyboard

router = Router()

class EditEvent(StatesGroup):
    waiting_for_event_choice = State()
    waiting_for_edit_choice = State()
    waiting_for_new_title = State()
    waiting_for_new_description = State()

def get_events_keyboard(events):
    """Клавиатура со списком событий"""
    keyboard = []
    for event in events:
        keyboard.append([KeyboardButton(text=f"📅 {event.title}")])
    keyboard.append([KeyboardButton(text="❌ Отмена")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_edit_options_keyboard():
    """Клавиатура с опциями редактирования"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✏️ Редактировать название"), KeyboardButton(text="📝 Редактировать описание")],
            [KeyboardButton(text="🗑️ Удалить событие"), KeyboardButton(text="↩️ Назад к списку")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )

# ОБРАБОТЧИК ОТМЕНЫ ДЛЯ ВСЕХ СОСТОЯНИЙ РЕДАКТИРОВАНИЯ
@router.message(StateFilter(EditEvent), F.text == "❌ Отмена")
async def cancel_edit(message: Message, state: FSMContext, session: AsyncSession):
    """Отмена редактирования из любого состояния"""
    current_state = await state.get_state()
    
    if current_state == EditEvent.waiting_for_event_choice:
        # Если отмена на этапе выбора события - возврат в главное меню
        await state.clear()
        await message.answer(
            "❌ Управление событиями отменено.",
            reply_markup=get_main_keyboard()
        )
    elif current_state in [EditEvent.waiting_for_new_title, EditEvent.waiting_for_new_description]:
        # Если отмена при редактировании названия/описания - возврат к меню управления событием
        data = await state.get_data()
        event = await EventService.get_event_by_id(session, data['selected_event_id'])
        
        if event:
            await state.set_state(EditEvent.waiting_for_edit_choice)
            await message.answer(
                f"❌ Редактирование отменено.\n\n"
                f"🎯 <b>Управление событием</b>\n\n"
                f"📌 <b>Название:</b> {event.title}\n"
                f"📄 <b>Описание:</b> {event.description}\n"
                f"📍 <b>Создано:</b> {event.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                f"👇 <b>Выберите действие:</b>",
                reply_markup=get_edit_options_keyboard(),
                parse_mode="HTML"
            )
        else:
            await state.clear()
            await message.answer(
                "❌ Событие не найдено.",
                reply_markup=get_main_keyboard()
            )
    else:
        # Для других состояний - очистка и возврат в главное меню
        await state.clear()
        await message.answer(
            "❌ Управление событиями отменено.",
            reply_markup=get_main_keyboard()
        )

@router.message(F.text == "📅 Мои события")
async def show_my_events(message: Message, session: AsyncSession, state: FSMContext):
    """Показать события пользователя с опциями управления"""
    events = await EventService.get_user_events(
        session=session,
        author_id=message.from_user.id
    )
    
    if not events:
        await message.answer(
            "📅 <b>Ваши события</b>\n\n"
            "У вас пока нет созданных событий.\n"
            "Создайте первое событие кнопкой ниже!",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
        return
    
    await state.set_state(EditEvent.waiting_for_event_choice)
    await state.update_data(events={event.title: event.id for event in events})
    
    events_text = "\n".join([f"• {event.title} ({event.created_at.strftime('%d.%m.%Y')})" for event in events])
    
    await message.answer(
        f"📅 <b>Ваши события</b>\n\n"
        f"Всего событий: {len(events)}\n\n"
        f"{events_text}\n\n"
        f"👇 <b>Выберите событие для управления:</b>",
        reply_markup=get_events_keyboard(events),
        parse_mode="HTML"
    )

@router.message(EditEvent.waiting_for_event_choice, F.text.startswith("📅 "))
async def select_event_for_edit(message: Message, state: FSMContext, session: AsyncSession):
    """Выбор события для редактирования"""
    # Проверяем не является ли сообщение отменой
    if message.text == "❌ Отмена":
        await cancel_edit(message, state, session)
        return
    
    event_title = message.text[2:]  # Убираем эмодзи
    data = await state.get_data()
    event_id = data['events'].get(event_title)
    
    if not event_id:
        await message.answer("❌ Событие не найдено.")
        return
    
    event = await EventService.get_event_by_id(session, event_id)
    if not event:
        await message.answer("❌ Событие не найдено.")
        return
    
    await state.set_state(EditEvent.waiting_for_edit_choice)
    await state.update_data(selected_event_id=event_id, selected_event_title=event_title)
    
    await message.answer(
        f"🎯 <b>Управление событием</b>\n\n"
        f"📌 <b>Название:</b> {event.title}\n"
        f"📄 <b>Описание:</b> {event.description}\n"
        f"📍 <b>Создано:</b> {event.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"👇 <b>Выберите действие:</b>",
        reply_markup=get_edit_options_keyboard(),
        parse_mode="HTML"
    )

@router.message(EditEvent.waiting_for_edit_choice, F.text == "✏️ Редактировать название")
async def start_edit_title(message: Message, state: FSMContext):
    """Начало редактирования названия"""
    await state.set_state(EditEvent.waiting_for_new_title)
    await message.answer(
        "📝 Введите <b>новое название</b> для события:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отмена")]],
            resize_keyboard=True
        ),
        parse_mode="HTML"
    )

@router.message(EditEvent.waiting_for_new_title, F.text)
async def process_new_title(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка нового названия"""
    # Проверяем не является ли сообщение отменой
    if message.text == "❌ Отмена":
        await cancel_edit(message, state, session)
        return
    
    if len(message.text) > 200:
        await message.answer("❌ Слишком длинное название. Максимум 200 символов.")
        return
    
    data = await state.get_data()
    event = await EventService.update_event(
        session=session,
        event_id=data['selected_event_id'],
        title=message.text
    )
    
    await state.set_state(EditEvent.waiting_for_edit_choice)
    await state.update_data(selected_event_title=message.text)
    
    await message.answer(
        f"✅ <b>Название обновлено!</b>\n\n"
        f"📌 Новое название: {message.text}",
        reply_markup=get_edit_options_keyboard(),
        parse_mode="HTML"
    )

@router.message(EditEvent.waiting_for_edit_choice, F.text == "📝 Редактировать описание")
async def start_edit_description(message: Message, state: FSMContext):
    """Начало редактирования описания"""
    await state.set_state(EditEvent.waiting_for_new_description)
    await message.answer(
        "📄 Введите <b>новое описание</b> для события:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отмена")]],
            resize_keyboard=True
        ),
        parse_mode="HTML"
    )

@router.message(EditEvent.waiting_for_new_description, F.text)
async def process_new_description(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка нового описания"""
    # Проверяем не является ли сообщение отменой
    if message.text == "❌ Отмена":
        await cancel_edit(message, state, session)
        return
    
    data = await state.get_data()
    event = await EventService.update_event(
        session=session,
        event_id=data['selected_event_id'],
        description=message.text
    )
    
    await state.set_state(EditEvent.waiting_for_edit_choice)
    
    await message.answer(
        "✅ <b>Описание обновлено!</b>",
        reply_markup=get_edit_options_keyboard(),
        parse_mode="HTML"
    )

@router.message(EditEvent.waiting_for_edit_choice, F.text == "🗑️ Удалить событие")
async def delete_event_confirmation(message: Message, state: FSMContext):
    """Подтверждение удаления события"""
    data = await state.get_data()
    
    await message.answer(
        f"⚠️ <b>Подтверждение удаления</b>\n\n"
        f"Вы действительно хотите удалить событие:\n"
        f"<b>«{data['selected_event_title']}»</b>?\n\n"
        f"Это действие нельзя отменить!",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="✅ Да, удалить"), KeyboardButton(text="❌ Нет, отменить")],
                [KeyboardButton(text="❌ Отмена")]
            ],
            resize_keyboard=True
        ),
        parse_mode="HTML"
    )

@router.message(EditEvent.waiting_for_edit_choice, F.text == "✅ Да, удалить")
async def confirm_delete_event(message: Message, state: FSMContext, session: AsyncSession):
    """Подтвержденное удаление события"""
    data = await state.get_data()
    
    success = await EventService.delete_event(session, data['selected_event_id'])
    
    await state.clear()
    
    if success:
        await message.answer(
            f"✅ <b>Событие удалено!</b>\n\n"
            f"Событие «{data['selected_event_title']}» было успешно удалено.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "❌ Не удалось удалить событие.",
            reply_markup=get_main_keyboard()
        )

@router.message(EditEvent.waiting_for_edit_choice, F.text == "↩️ Назад к списку")
async def back_to_events_list(message: Message, state: FSMContext, session: AsyncSession):
    """Вернуться к списку событий"""
    await show_my_events(message, session, state)

@router.message(EditEvent.waiting_for_edit_choice, F.text == "❌ Нет, отменить")
async def cancel_delete(message: Message, state: FSMContext):
    """Отмена удаления"""
    await message.answer(
        "❌ Удаление отменено.",
        reply_markup=get_edit_options_keyboard()
    )