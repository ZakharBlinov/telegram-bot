from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, PhotoSize
from aiogram.filters import StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.service.search_service import SearchService
from app.service.user_service import UserService
from app.service.like_service import LikeService
from app.service.match_service import MatchService
from app.models import SEARCH_GOALS
from app.keyboards.main_menu import get_main_keyboard

router = Router()

class SearchStates(StatesGroup):
    choosing_goal = State()
    viewing_profiles = State()
    editing_profile = State()
    waiting_for_photo = State()

def get_search_main_keyboard(has_goal: bool = False):
    """Главная клавиатура для раздела поиска"""
    keyboard = []
    if has_goal:
        keyboard.append([KeyboardButton(text="👀 Смотреть анкеты"), KeyboardButton(text="✏️ Моя анкета")])
        keyboard.append([KeyboardButton(text="🎯 Сменить цель")])
    else:
        keyboard.append([KeyboardButton(text="🎯 Выбрать цель")])
    keyboard.append([KeyboardButton(text="🏠 В главное меню")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_goal_keyboard():
    """Клавиатура выбора цели"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💑 Вторую половинку")],
            [KeyboardButton(text="👥 Найти общение")],
            [KeyboardButton(text="🎮 С кем поиграть")],
            [KeyboardButton(text="🎨 Общие интересы и хобби")],
            [KeyboardButton(text="💼 Предложенные услуги")],
            [KeyboardButton(text="🏠 В главное меню")]
        ],
        resize_keyboard=True
    )

def get_profile_view_keyboard():
    """Клавиатура для просмотра анкет"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💝 Лайк"), KeyboardButton(text="👎 Пропустить")],
            [KeyboardButton(text="⏹️ Закончить просмотр")],
            [KeyboardButton(text="🏠 В главное меню")]
        ],
        resize_keyboard=True
    )

def get_profile_edit_keyboard():
    """Клавиатура редактирования анкеты"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✏️ Изменить описание"), KeyboardButton(text="📸 Изменить фото")],
            [KeyboardButton(text="👀 Смотреть анкеты")],
            [KeyboardButton(text="🎯 Сменить цель"), KeyboardButton(text="🏠 В главное меню")]
        ],
        resize_keyboard=True
    )

@router.message(F.text == "🔍 Найти людей")
async def start_search(message: Message, state: FSMContext, session: AsyncSession):
    """Начать поиск людей"""
    user = await UserService.get_or_create_user(
        session=session,
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=f"{message.from_user.first_name} {message.from_user.last_name or ''}"
    )
    
    if not user.profile_completed:
        await message.answer(
            "❌ <b>Сначала заполните свой профиль!</b>\n\n"
            "Чтобы искать других людей, нужно сначала рассказать о себе в профиле.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
        return
    
    active_goal = await SearchService.get_user_goal(session, message.from_user.id)
    
    if active_goal:
        goal_text = SEARCH_GOALS.get(active_goal.goal_type, active_goal.goal_type)
        await message.answer(
            f"🔍 <b>Поиск людей</b>\n\n"
            f"🎯 <b>Текущая цель:</b> {goal_text}\n\n"
            f"👇 <b>Выберите действие:</b>",
            reply_markup=get_search_main_keyboard(has_goal=True),
            parse_mode="HTML"
        )
    else:
        await state.set_state(SearchStates.choosing_goal)
        await message.answer(
            "🎯 <b>Выберите цель поиска:</b>\n\n"
            "Для кого вы хотите создать анкету?",
            reply_markup=get_goal_keyboard(),
            parse_mode="HTML"
        )

@router.message(SearchStates.choosing_goal, F.text.in_([
    "💑 Вторую половинку", 
    "👥 Найти общение", 
    "🎮 С кем поиграть",
    "🎨 Общие интересы и хобби", 
    "💼 Предложенные услуги"
]))
async def choose_goal(message: Message, state: FSMContext, session: AsyncSession):
    """Выбор цели поиска и создание анкеты"""
    goal_type = None
    goal_text = message.text
    
    if goal_text == "💑 Вторую половинку":
        goal_type = "relationship"
    elif goal_text == "👥 Найти общение":
        goal_type = "friendship"
    elif goal_text == "🎮 С кем поиграть":
        goal_type = "gaming"
    elif goal_text == "🎨 Общие интересы и хобби":
        goal_type = "hobbies"
    elif goal_text == "💼 Предложенные услуги":
        goal_type = "services"
    
    if not goal_type:
        await message.answer("❌ Неизвестная цель поиска.")
        return
    
    await SearchService.set_user_goal(session, message.from_user.id, goal_type)
    
    profile = await SearchService.get_profile_for_goal(session, message.from_user.id, goal_type)
    
    if profile:
        await state.clear()
        
        await message.answer(
            f"✅ <b>Цель изменена на: {goal_text}</b>\n\n"
            f"У вас уже есть анкета для этой цели.\n\n"
            f"👇 <b>Выберите действие:</b>",
            reply_markup=get_search_main_keyboard(has_goal=True),
            parse_mode="HTML"
        )
    else:
        await state.set_state(SearchStates.editing_profile)
        await state.update_data(
            current_goal=goal_type,
            current_goal_text=goal_text,
            editing_description=False,
            editing_photo=False
        )
        
        await message.answer(
            f"📝 <b>Создание анкеты для: {goal_text}</b>\n\n"
            "Расскажите о себе для этой цели поиска (минимум 20 символов):\n\n"
            "<i>Анкета пройдёт автоматическую проверку на наличие запрещённых слов</i>",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="❌ Отмена")]],
                resize_keyboard=True
            ),
            parse_mode="HTML"
        )

@router.message(F.text == "🎯 Сменить цель")
async def change_goal_from_main(message: Message, state: FSMContext, session: AsyncSession):
    """Сменить цель поиска из главного меню"""
    await state.clear()
    await state.set_state(SearchStates.choosing_goal)
    
    await message.answer(
        "🎯 <b>Выберите новую цель поиска:</b>\n\n"
        "При смене цели нужно будет создать новую анкету для этой цели.",
        reply_markup=get_goal_keyboard(),
        parse_mode="HTML"
    )

@router.message(F.text == "👀 Смотреть анкеты")
async def start_viewing_profiles(message: Message, state: FSMContext, session: AsyncSession):
    """Начать просмотр анкет из главного меню"""
    active_goal = await SearchService.get_user_goal(session, message.from_user.id)
    
    if not active_goal:
        await message.answer(
            "❌ <b>Сначала выберите цель поиска!</b>",
            reply_markup=get_search_main_keyboard(has_goal=False)
        )
        return
    
    profile = await SearchService.get_profile_for_goal(session, message.from_user.id, active_goal.goal_type)
    
    if not profile:
        await message.answer(
            "❌ <b>Сначала создайте анкету для выбранной цели!</b>\n\n"
            "Нажмите «✏️ Моя анкета» для создания.",
            reply_markup=get_search_main_keyboard(has_goal=True)
        )
        return
    
    await state.set_state(SearchStates.viewing_profiles)
    await state.update_data(
        current_goal=active_goal.goal_type, 
        viewed_profiles=[]
    )
    
    await message.answer(
        "🔍 <b>Начинаем просмотр анкет...</b>",
        reply_markup=get_profile_view_keyboard()
    )
    
    await show_next_profile(message, state, session)

@router.message(F.text == "✏️ Моя анкета")
async def show_my_profile(message: Message, state: FSMContext, session: AsyncSession):
    """Показать мою анкету"""
    active_goal = await SearchService.get_user_goal(session, message.from_user.id)
    
    if not active_goal:
        await message.answer(
            "❌ <b>Сначала выберите цель поиска!</b>",
            reply_markup=get_search_main_keyboard(has_goal=False)
        )
        return
    
    profile = await SearchService.get_profile_for_goal(session, message.from_user.id, active_goal.goal_type)
    
    if not profile:
        await state.set_state(SearchStates.editing_profile)
        await state.update_data(
            current_goal=active_goal.goal_type,
            current_goal_text=SEARCH_GOALS.get(active_goal.goal_type, active_goal.goal_type),
            editing_description=False,
            editing_photo=False
        )
        
        await message.answer(
            f"📝 <b>Создание анкеты для цели: {SEARCH_GOALS.get(active_goal.goal_type, active_goal.goal_type)}</b>\n\n"
            "Расскажите о себе (минимум 20 символов):\n\n"
            "<i>Анкета пройдёт автоматическую проверку</i>",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="❌ Отмена")]],
                resize_keyboard=True
            ),
            parse_mode="HTML"
        )
        return
    
    goal_text = SEARCH_GOALS.get(active_goal.goal_type, active_goal.goal_type)
    
    status_text = ""
    if profile.moderation_status == "pending":
        status_text = "\n\n⏳ <b>Статус:</b> Анкета на модерации"
    elif profile.moderation_status == "rejected":
        status_text = f"\n\n❌ <b>Статус:</b> Анкета отклонена\nПричина: {profile.moderation_reason}"
    elif not profile.is_active:
        status_text = "\n\n🔒 <b>Статус:</b> Анкета заблокирована"
    
    profile_text = (
        f"👤 <b>Ваша анкета</b>\n\n"
        f"🎯 <b>Цель:</b> {goal_text}\n\n"
        f"💬 <b>Описание:</b>\n{profile.description}\n\n"
        f"📸 <b>Фото:</b> {'есть' if profile.photo_id else 'нет'}{status_text}"
    )
    
    if profile.photo_id:
        await message.answer_photo(
            profile.photo_id,
            caption=profile_text,
            reply_markup=get_profile_edit_keyboard(),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            profile_text,
            reply_markup=get_profile_edit_keyboard(),
            parse_mode="HTML"
        )

@router.message(F.text == "✏️ Изменить описание")
async def start_edit_description(message: Message, state: FSMContext, session: AsyncSession):
    """Начать изменение описания"""
    active_goal = await SearchService.get_user_goal(session, message.from_user.id)
    
    if not active_goal:
        await message.answer("❌ Цель поиска не найдена.")
        return
    
    await state.set_state(SearchStates.editing_profile)
    await state.update_data(
        editing_description=True, 
        editing_photo=False,
        current_goal=active_goal.goal_type,
        current_goal_text=SEARCH_GOALS.get(active_goal.goal_type, active_goal.goal_type)
    )
    
    await message.answer(
        "📝 <b>Введите новое описание для вашей анкеты:</b>\n\n"
        "Минимум 20 символов, максимум 1000.\n\n"
        "<i>После обновления анкета уйдёт на повторную проверку</i>",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отмена")]],
            resize_keyboard=True
        ),
        parse_mode="HTML"
    )

@router.message(F.text == "📸 Изменить фото")
async def start_edit_photo(message: Message, state: FSMContext, session: AsyncSession):
    """Начать изменение фото"""
    active_goal = await SearchService.get_user_goal(session, message.from_user.id)
    
    if not active_goal:
        await message.answer("❌ Цель поиска не найдена.")
        return
    
    profile = await SearchService.get_profile_for_goal(session, message.from_user.id, active_goal.goal_type)
    
    if not profile:
        await message.answer(
            "❌ <b>Сначала создайте анкету!</b>\n\n"
            "Используйте кнопку «✏️ Моя анкета» для создания.",
            reply_markup=get_search_main_keyboard(has_goal=True)
        )
        return
    
    await state.set_state(SearchStates.waiting_for_photo)
    await state.update_data(
        editing_photo=True,
        editing_description=False,
        current_goal=active_goal.goal_type,
        current_goal_text=SEARCH_GOALS.get(active_goal.goal_type, active_goal.goal_type),
        profile_id=profile.id
    )
    
    await message.answer(
        "📸 <b>Отправьте фото для вашей анкеты:</b>\n\n"
        "Просто отправьте фото в этот чат.\n"
        "Или нажмите ❌ Отмена для отмены",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отмена")]],
            resize_keyboard=True
        ),
        parse_mode="HTML"
    )

@router.message(SearchStates.editing_profile, F.text == "❌ Отмена")
async def cancel_editing(message: Message, state: FSMContext, session: AsyncSession):
    """Отмена редактирования анкеты"""
    await state.clear()
    
    active_goal = await SearchService.get_user_goal(session, message.from_user.id)
    
    if active_goal:
        profile = await SearchService.get_profile_for_goal(session, message.from_user.id, active_goal.goal_type)
        
        if profile:
            goal_text = SEARCH_GOALS.get(active_goal.goal_type, active_goal.goal_type)
            profile_text = (
                f"👤 <b>Ваша анкета</b>\n\n"
                f"🎯 <b>Цель:</b> {goal_text}\n\n"
                f"💬 <b>Описание:</b>\n{profile.description}\n\n"
                f"📸 <b>Фото:</b> {'есть' if profile.photo_id else 'нет'}"
            )
            
            if profile.photo_id:
                await message.answer_photo(
                    profile.photo_id,
                    caption=profile_text,
                    reply_markup=get_profile_edit_keyboard(),
                    parse_mode="HTML"
                )
            else:
                await message.answer(
                    profile_text,
                    reply_markup=get_profile_edit_keyboard(),
                    parse_mode="HTML"
                )
        else:
            await message.answer(
                "❌ <b>Анкета не найдена</b>",
                reply_markup=get_search_main_keyboard(has_goal=True)
            )
    else:
        await message.answer(
            "❌ <b>Цель поиска не найдена</b>",
            reply_markup=get_search_main_keyboard(has_goal=False)
        )

@router.message(SearchStates.waiting_for_photo, F.text == "❌ Отмена")
async def cancel_photo_edit(message: Message, state: FSMContext, session: AsyncSession):
    """Отмена редактирования фото"""
    await state.clear()
    
    active_goal = await SearchService.get_user_goal(session, message.from_user.id)
    
    if active_goal:
        profile = await SearchService.get_profile_for_goal(session, message.from_user.id, active_goal.goal_type)
        
        if profile:
            goal_text = SEARCH_GOALS.get(active_goal.goal_type, active_goal.goal_type)
            profile_text = (
                f"👤 <b>Ваша анкета</b>\n\n"
                f"🎯 <b>Цель:</b> {goal_text}\n\n"
                f"💬 <b>Описание:</b>\n{profile.description}\n\n"
                f"📸 <b>Фото:</b> {'есть' if profile.photo_id else 'нет'}"
            )
            
            if profile.photo_id:
                await message.answer_photo(
                    profile.photo_id,
                    caption=profile_text,
                    reply_markup=get_profile_edit_keyboard(),
                    parse_mode="HTML"
                )
            else:
                await message.answer(
                    profile_text,
                    reply_markup=get_profile_edit_keyboard(),
                    parse_mode="HTML"
                )
        else:
            await message.answer(
                "❌ <b>Анкета не найдена</b>",
                reply_markup=get_search_main_keyboard(has_goal=True)
            )
    else:
        await message.answer(
            "❌ <b>Цель поиска не найдена</b>",
            reply_markup=get_search_main_keyboard(has_goal=False)
        )

@router.message(SearchStates.editing_profile, F.text)
async def process_profile_description(message: Message, state: FSMContext, session: AsyncSession):
    """Обработать описание при создании или редактировании анкеты"""
    if message.text == "❌ Отмена":
        await cancel_editing(message, state, session)
        return
    
    data = await state.get_data()
    
    if data.get('editing_photo'):
        return
    
    if len(message.text) < 20:
        await message.answer("❌ Слишком короткое описание. Напишите хотя бы 20 символов.")
        return
    
    if len(message.text) > 1000:
        await message.answer("❌ Слишком длинное описание. Максимум 1000 символов.")
        return
    
    goal_type = data.get('current_goal')
    goal_text = data.get('current_goal_text')
    editing_description = data.get('editing_description', False)
    
    if not goal_type:
        await message.answer("❌ Цель поиска не найдена.")
        return
    
    logging.info(f"Создание/обновление анкеты: user={message.from_user.id}, goal={goal_type}, editing={editing_description}")
    
    if editing_description:
        profile = await SearchService.update_profile_with_moderation(
            session=session,
            user_id=message.from_user.id,
            goal_type=goal_type,
            description=message.text
        )
        action = "обновлено"
    else:
        profile = await SearchService.create_profile_with_moderation(
            session=session,
            user_id=message.from_user.id,
            goal_type=goal_type,
            description=message.text
        )
        action = "создано"
    
    if profile:
        await state.clear()
        
        if profile.moderation_status == "rejected":
            await message.answer(
                f"❌ <b>Анкета не опубликована</b>\n\n"
                f"🎯 <b>Цель:</b> {goal_text}\n\n"
                f"⚠️ <b>Причина:</b> {profile.moderation_reason}\n\n"
                f"Пожалуйста, создайте анкету без запрещённых слов.",
                reply_markup=get_search_main_keyboard(has_goal=True),
                parse_mode="HTML"
            )
        elif profile.moderation_status == "pending":
            await message.answer(
                f"⏳ <b>Анкета отправлена на модерацию</b>\n\n"
                f"🎯 <b>Цель:</b> {goal_text}\n\n"
                f"Администратор проверит анкету в ближайшее время.\n"
                f"Вы получите уведомление о результате проверки.",
                reply_markup=get_search_main_keyboard(has_goal=True),
                parse_mode="HTML"
            )
        else:
            if action == "обновлено":
                await message.answer(
                    f"✅ <b>Анкета обновлена и опубликована!</b>\n\n"
                    f"🎯 <b>Цель:</b> {goal_text}\n\n"
                    f"Теперь вы можете добавить фото или начать поиск!",
                    reply_markup=get_profile_edit_keyboard(),
                    parse_mode="HTML"
                )
            else:
                await message.answer(
                    f"✅ <b>Анкета создана и опубликована!</b>\n\n"
                    f"🎯 <b>Цель:</b> {goal_text}\n\n"
                    f"Теперь вы можете добавить фото (отправьте фото в чат) или сразу начать поиск!",
                    reply_markup=get_profile_edit_keyboard(),
                    parse_mode="HTML"
                )
    else:
        await message.answer(
            "❌ <b>Ошибка при сохранении анкеты</b>\n\n"
            "Попробуйте позже или обратитесь к администратору.",
            reply_markup=get_search_main_keyboard(has_goal=False)
        )

@router.message(SearchStates.waiting_for_photo, F.photo)
async def process_profile_photo(message: Message, state: FSMContext, session: AsyncSession):
    """Обработать фото при добавлении или редактировании анкеты"""
    data = await state.get_data()
    
    photo = message.photo[-1]
    photo_id = photo.file_id
    
    goal_type = data.get('current_goal')
    goal_text = data.get('current_goal_text')
    
    logging.info(f"Обработка фото для анкеты: user={message.from_user.id}, goal={goal_type}, photo_id={photo_id}")
    
    if not goal_type:
        await message.answer("❌ Цель поиска не найдена.")
        return
    
    # Получаем существующую анкету
    existing_profile = await SearchService.get_profile_for_goal(session, message.from_user.id, goal_type)
    
    if not existing_profile:
        await message.answer(
            "❌ <b>Сначала создайте описание анкеты!</b>\n\n"
            "Используйте кнопку «✏️ Моя анкета» для создания описания.",
            reply_markup=get_search_main_keyboard(has_goal=True)
        )
        await state.clear()
        return
    
    # Обновляем фото через специальный метод
    profile = await SearchService.update_profile_photo(
        session=session,
        user_id=message.from_user.id,
        goal_type=goal_type,
        photo_id=photo_id
    )
    
    if profile:
        await state.clear()
        
        await message.answer_photo(
            photo_id,
            caption=f"✅ <b>Фото для анкеты сохранено!</b>\n\n"
                    f"🎯 <b>Цель:</b> {goal_text}\n\n"
                    f"Теперь ваша анкета полностью готова.\n"
                    f"Другие пользователи смогут видеть вашу анкету при поиске.",
            reply_markup=get_profile_edit_keyboard(),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "❌ <b>Ошибка при сохранении фото</b>\n\n"
            "Попробуйте отправить фото ещё раз.\n"
            "Если ошибка повторяется, обратитесь к администратору.",
            reply_markup=get_search_main_keyboard(has_goal=True)
        )

@router.message(StateFilter(SearchStates), F.text == "🏠 В главное меню")
async def back_to_main(message: Message, state: FSMContext):
    """Вернуться в главное меню"""
    await state.clear()
    await message.answer(
        "Возвращаемся в главное меню...",
        reply_markup=get_main_keyboard()
    )

async def show_next_profile(message: Message, state: FSMContext, session: AsyncSession):
    """Показать следующую анкету"""
    data = await state.get_data()
    current_goal = data.get('current_goal')
    viewed_profiles = data.get('viewed_profiles', [])
    
    profiles = await SearchService.find_profiles_by_goal(
        session, current_goal, message.from_user.id, limit=50
    )
    
    available_profiles = [p for p in profiles if p.user_id not in viewed_profiles]
    
    if not available_profiles:
        await message.answer(
            "🤷 <b>Больше анкет нет!</b>\n\n"
            "Мы показали все доступные анкеты по вашей цели поиска.\n"
            "Попробуйте изменить цель поиска или зайдите позже.",
            reply_markup=get_profile_view_keyboard(),
            parse_mode="HTML"
        )
        return
    
    profile = available_profiles[0]
    user = await UserService.get_user_by_telegram_id(session, profile.user_id)
    
    if not user:
        await show_next_profile(message, state, session)
        return
    
    viewed_profiles.append(user.id)
    await state.update_data(
        current_profile_id=user.id,
        viewed_profiles=viewed_profiles,
        available_profiles=available_profiles[1:]
    )
    
    gender_text = "👨 Мужской" if user.gender == "male" else "👩 Женский"
    profile_text = (
        f"👤 <b>Анкета</b>\n\n"
        f"💭 <b>Цель:</b> {SEARCH_GOALS.get(current_goal, current_goal)}\n\n"
        f"👤 <b>Имя:</b> {user.full_name}\n"
        f"🎂 <b>Возраст:</b> {user.age} лет\n"
        f"👫 <b>Пол:</b> {gender_text}\n"
    )
    
    if user.username:
        profile_text += f"📱 <b>Username:</b> @{user.username}\n"
    
    if profile.description:
        profile_text += f"\n💬 <b>О себе:</b>\n{profile.description}\n"
    
    if profile.photo_id:
        await message.answer_photo(
            profile.photo_id,
            caption=profile_text,
            reply_markup=get_profile_view_keyboard(),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            profile_text,
            reply_markup=get_profile_view_keyboard(),
            parse_mode="HTML"
        )

@router.message(SearchStates.viewing_profiles, F.text == "💝 Лайк")
async def like_profile(message: Message, state: FSMContext, session: AsyncSession):
    """Лайк анкеты"""
    data = await state.get_data()
    current_profile_id = data.get('current_profile_id')
    current_goal = data.get('current_goal')
    
    if not current_profile_id:
        await message.answer("❌ Не удалось найти анкету для лайка.")
        await show_next_profile(message, state, session)
        return
    
    success, result_type = await LikeService.add_like(
        session, message.from_user.id, current_profile_id, current_goal
    )
    
    if success:
        if result_type == "mutual_match":
            liked_user = await UserService.get_user_by_telegram_id(session, current_profile_id)
            username = f"@{liked_user.username}" if liked_user.username else "пользователь"
            
            await message.answer(
                f"💞 <b>Взаимный лайк!</b>\n\n"
                f"Вы понравились {liked_user.full_name}!\n\n"
                f"📱 <b>Username:</b> {username}\n\n"
                f"Хотите начать общение?",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[
                        [KeyboardButton(text="💌 Написать сообщение")],
                        [KeyboardButton(text="👎 Пропустить")],
                        [KeyboardButton(text="🔍 Продолжить просмотр")]
                    ],
                    resize_keyboard=True
                ),
                parse_mode="HTML"
            )
            return
        else:
            await message.answer("💝 Лайк отправлен!")
    else:
        if result_type == "already_liked":
            await message.answer("💝 Вы уже лайкали этого пользователя")
        else:
            await message.answer("❌ Ошибка при отправке лайка")
    
    await show_next_profile(message, state, session)

@router.message(SearchStates.viewing_profiles, F.text == "💌 Написать сообщение")
async def start_chat_after_match(message: Message, state: FSMContext, session: AsyncSession):
    """Начать чат после взаимного лайка"""
    data = await state.get_data()
    current_profile_id = data.get('current_profile_id')
    
    if current_profile_id:
        await message.answer(
            f"💬 <b>Отлично!</b>\n\n"
            f"Теперь вы можете общаться с этим пользователем через раздел «💬 Мои чаты».",
            reply_markup=get_profile_view_keyboard(),
            parse_mode="HTML"
        )
    
    await show_next_profile(message, state, session)

@router.message(SearchStates.viewing_profiles, F.text == "👎 Пропустить")
@router.message(SearchStates.viewing_profiles, F.text == "🔍 Продолжить просмотр")
async def skip_profile(message: Message, state: FSMContext, session: AsyncSession):
    """Пропустить анкету"""
    await show_next_profile(message, state, session)

@router.message(SearchStates.viewing_profiles, F.text == "⏹️ Закончить просмотр")
async def stop_viewing_profiles(message: Message, state: FSMContext, session: AsyncSession):
    """Закончить просмотр анкет"""
    await state.clear()
    
    active_goal = await SearchService.get_user_goal(session, message.from_user.id)
    goal_text = SEARCH_GOALS.get(active_goal.goal_type, active_goal.goal_type) if active_goal else "не выбрана"
    
    await message.answer(
        f"⏹️ <b>Просмотр анкет завершен</b>\n\n"
        f"🎯 <b>Текущая цель:</b> {goal_text}\n\n"
        f"Вы можете продолжить позже.",
        reply_markup=get_search_main_keyboard(has_goal=True),
        parse_mode="HTML"
    )