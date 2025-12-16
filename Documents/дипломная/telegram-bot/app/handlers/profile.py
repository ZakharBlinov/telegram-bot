# app/handlers/profile.py
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.service.user_service import UserService
from app.keyboards.main_menu import get_main_keyboard

router = Router()

class UserProfile(StatesGroup):
    waiting_for_name = State()
    waiting_for_age = State()
    waiting_for_gender = State()

def get_gender_keyboard():
    """Клавиатура для выбора пола"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👨 Мужской"), KeyboardButton(text="👩 Женский")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )

def get_profile_management_keyboard():
    """Клавиатура управления профилем"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔄 Заполнить профиль заново")],
            [KeyboardButton(text="↩️ Назад")]
        ],
        resize_keyboard=True
    )

@router.message(StateFilter(UserProfile), F.text == "❌ Отмена")
async def cancel_profile(message: Message, state: FSMContext):
    """Отмена заполнения анкеты из любого состояния"""
    await state.clear()
    await message.answer(
        "❌ Заполнение профиля отменено.",
        reply_markup=get_main_keyboard()
    )

@router.message(F.text == "📊 Мой профиль")
async def show_profile(message: Message, session: AsyncSession, state: FSMContext):
    """Показать профиль"""
    user = await UserService.get_or_create_user(
        session=session,
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=f"{message.from_user.first_name} {message.from_user.last_name or ''}"
    )
    
    if not user.profile_completed:
        await state.set_state(UserProfile.waiting_for_name)
        await message.answer(
            "👋 <b>Давайте заполним ваш базовый профиль!</b>\n\n"
            "📝 Введите ваше <b>имя</b> (как к вам обращаться):",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="❌ Отмена")]],
                resize_keyboard=True
            ),
            parse_mode="HTML"
        )
    else:
        gender_text = "👨 Мужской" if user.gender == "male" else "👩 Женский"
        profile_info = (
            f"📊 <b>Ваш профиль</b>\n\n"
            f"👤 <b>Имя:</b> {user.full_name}\n"
            f"🎂 <b>Возраст:</b> {user.age} лет\n"
            f"👫 <b>Пол:</b> {gender_text}\n"
            f"📱 <b>Username:</b> @{user.username or 'не указан'}\n"
        )
        
        if user.description:
            profile_info += f"💬 <b>Анкета:</b> заполнена\n"
            if user.photo_id:
                profile_info += f"📸 <b>Фото в анкете:</b> есть\n"
            else:
                profile_info += f"📸 <b>Фото в анкете:</b> нет\n"
        else:
            profile_info += f"💬 <b>Анкета:</b> не заполнена\n"
        
        user_location = await UserService.get_user_location(session, message.from_user.id)
        if user_location:
            profile_info += f"📍 <b>Локация:</b> установлена\n"
        else:
            profile_info += f"📍 <b>Локация:</b> не установлена\n"
        
        profile_info += f"\n👇 <b>Управление профилем:</b>"
        
        await message.answer(
            profile_info,
            reply_markup=get_profile_management_keyboard(),
            parse_mode="HTML"
        )

@router.message(F.text == "🔄 Заполнить профиль заново")
async def restart_profile(message: Message, state: FSMContext):
    """Начать заполнение профиля заново"""
    await state.set_state(UserProfile.waiting_for_name)
    await message.answer(
        "👋 <b>Давайте заполним ваш профиль заново!</b>\n\n"
        "📝 Введите ваше <b>имя</b> (как к вам обращаться):",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отмена")]],
            resize_keyboard=True
        ),
        parse_mode="HTML"
    )

@router.message(F.text == "↩️ Назад")
async def back_to_main(message: Message):
    """Вернуться в главное меню"""
    await message.answer(
        "Возвращаемся в главное меню...",
        reply_markup=get_main_keyboard()
    )

@router.message(UserProfile.waiting_for_name, F.text)
async def process_name(message: Message, state: FSMContext):
    """Обработка имени"""
    if message.text == "❌ Отмена":
        await cancel_profile(message, state)
        return
    
    if len(message.text) > 50:
        await message.answer("❌ Слишком длинное имя. Максимум 50 символов.")
        return
    
    await state.update_data(full_name=message.text)
    await state.set_state(UserProfile.waiting_for_age)
    
    await message.answer(
        "🎂 Теперь введите ваш <b>возраст</b> (только цифры):",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отмена")]],
            resize_keyboard=True
        ),
        parse_mode="HTML"
    )

@router.message(UserProfile.waiting_for_age, F.text)
async def process_age(message: Message, state: FSMContext):
    """Обработка возраста"""
    if message.text == "❌ Отмена":
        await cancel_profile(message, state)
        return
    
    try:
        age = int(message.text)
        if age < 1 or age > 120:
            await message.answer("❌ Пожалуйста, введите реальный возраст (1-120).")
            return
        
        await state.update_data(age=age)
        await state.set_state(UserProfile.waiting_for_gender)
        
        await message.answer(
            "👫 Выберите ваш <b>пол</b>:",
            reply_markup=get_gender_keyboard(),
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Пожалуйста, введите возраст цифрами.")

@router.message(UserProfile.waiting_for_gender, F.text.in_(["👨 Мужской", "👩 Женский"]))
async def process_gender(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка пола"""
    gender = "male" if message.text == "👨 Мужской" else "female"
    
    data = await state.get_data()
    
    user = await UserService.get_or_create_user(
        session=session,
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=data['full_name']
    )
    
    user.age = data['age']
    user.gender = gender
    user.profile_completed = True
    await session.commit()
    
    await state.clear()
    
    gender_text = "👨 Мужской" if gender == "male" else "👩 Женский"
    await message.answer(
        f"✅ <b>Профиль заполнен!</b>\n\n"
        f"👤 <b>Имя:</b> {data['full_name']}\n"
        f"🎂 <b>Возраст:</b> {data['age']} лет\n"
        f"👫 <b>Пол:</b> {gender_text}\n\n"
        f"Теперь вы можете пользоваться всеми функциями бота!",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )