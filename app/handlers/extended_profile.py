# app/handlers/extended_profile.py
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, PhotoSize
from aiogram.filters import StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.service.user_service import UserService
from app.keyboards.main_menu import get_main_keyboard

router = Router()

class ExtendedProfile(StatesGroup):
    waiting_for_description = State()
    waiting_for_photo = State()

@router.message(F.text == "📝 Заполнить анкету")
async def start_extended_profile(message: Message, state: FSMContext, session: AsyncSession):
    """Начало заполнения расширенной анкеты"""
    # Проверяем заполнен ли базовый профиль
    user = await UserService.get_or_create_user(
        session=session,
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=f"{message.from_user.first_name} {message.from_user.last_name or ''}"
    )
    
    if not user.profile_completed:
        await message.answer(
            "❌ <b>Сначала заполните базовый профиль!</b>\n\n"
            "Перед созданием анкеты нужно указать имя, возраст и пол.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
        return
    
    await state.set_state(ExtendedProfile.waiting_for_description)
    await message.answer(
        "📝 <b>Создание анкеты для поиска</b>\n\n"
        "Расскажите о себе подробнее:\n\n"
        "💬 <b>Напишите описание</b> (о себе, своих интересах, увлечениях, "
        "что ищете в людях и т.д.):\n\n"
        "<i>Можно писать много текста - это поможет другим лучше вас узнать</i>",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отмена")]],
            resize_keyboard=True
        ),
        parse_mode="HTML"
    )

@router.message(ExtendedProfile.waiting_for_description, F.text)
async def process_description(message: Message, state: FSMContext):
    """Обработка описания анкеты"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(
            "❌ Создание анкеты отменено.",
            reply_markup=get_main_keyboard()
        )
        return
    
    if len(message.text) < 10:
        await message.answer("❌ Слишком короткое описание. Напишите хотя бы 10 символов.")
        return
    
    if len(message.text) > 1000:
        await message.answer("❌ Слишком длинное описание. Максимум 1000 символов.")
        return
    
    await state.update_data(description=message.text)
    await state.set_state(ExtendedProfile.waiting_for_photo)
    
    await message.answer(
        "📸 <b>Теперь пришлите ваше фото</b>\n\n"
        "Фото поможет другим пользователям лучше вас узнать.\n"
        "Отправьте одно фото для вашей анкеты:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отмена"), KeyboardButton(text="⏭ Пропустить")]],
            resize_keyboard=True
        ),
        parse_mode="HTML"
    )

@router.message(ExtendedProfile.waiting_for_photo, F.photo)
async def process_photo(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка фото анкеты"""
    # Берем самое большое фото
    photo: PhotoSize = message.photo[-1]
    photo_id = photo.file_id
    
    data = await state.get_data()
    description = data['description']
    
    # Сохраняем анкету
    user = await UserService.update_user_profile(
        session=session,
        telegram_id=message.from_user.id,
        description=description,
        photo_id=photo_id
    )
    
    await state.clear()
    
    # Показываем результат
    await message.answer_photo(
        photo_id,
        caption=(
            f"✅ <b>Анкета создана!</b>\n\n"
            f"👤 <b>Имя:</b> {user.full_name}\n"
            f"🎂 <b>Возраст:</b> {user.age} лет\n"
            f"👫 <b>Пол:</b> {'👨 Мужской' if user.gender == 'male' else '👩 Женский'}\n\n"
            f"💬 <b>Описание:</b>\n{user.description}\n\n"
            f"Теперь ваша анкета будет показываться другим пользователям!"
        ),
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )

@router.message(ExtendedProfile.waiting_for_photo, F.text == "⏭ Пропустить")
async def skip_photo(message: Message, state: FSMContext, session: AsyncSession):
    """Пропуск добавления фото"""
    data = await state.get_data()
    description = data['description']
    
    # Сохраняем анкету без фото
    user = await UserService.update_user_profile(
        session=session,
        telegram_id=message.from_user.id,
        description=description,
        photo_id=None
    )
    
    await state.clear()
    
    await message.answer(
        f"✅ <b>Анкета создана!</b>\n\n"
        f"👤 <b>Имя:</b> {user.full_name}\n"
        f"🎂 <b>Возраст:</b> {user.age} лет\n"
        f"👫 <b>Пол:</b> {'👨 Мужской' if user.gender == 'male' else '👩 Женский'}\n\n"
        f"💬 <b>Описание:</b>\n{user.description}\n\n"
        f"📸 <b>Фото:</b> не добавлено\n\n"
        f"Теперь ваша анкета будет показываться другим пользователям!",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )

@router.message(ExtendedProfile.waiting_for_photo, F.text == "❌ Отмена")
async def cancel_extended_profile(message: Message, state: FSMContext):
    """Отмена создания анкеты"""
    await state.clear()
    await message.answer(
        "❌ Создание анкеты отменено.",
        reply_markup=get_main_keyboard()
    )