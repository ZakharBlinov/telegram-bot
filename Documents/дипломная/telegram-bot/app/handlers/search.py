from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, PhotoSize
from aiogram.filters import StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

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
    
    # Проверяем есть ли активная цель
    active_goal = await SearchService.get_user_goal(session, message.from_user.id)
    
    if active_goal:
        # Есть активная цель - показываем главное меню поиска
        goal_text = SEARCH_GOALS.get(active_goal.goal_type, active_goal.goal_type)
        await message.answer(
            f"🔍 <b>Поиск людей</b>\n\n"
            f"🎯 <b>Текущая цель:</b> {goal_text}\n\n"
            f"👇 <b>Выберите действие:</b>",
            reply_markup=get_search_main_keyboard(has_goal=True),
            parse_mode="HTML"
        )
    else:
        # Нет цели - выбираем
        await state.set_state(SearchStates.choosing_goal)
        await message.answer(
            "🎯 <b>Выберите цель поиска:</b>\n\n"
            "Для кого вы хотите создать анкету?",
            reply_markup=get_goal_keyboard(),
            parse_mode="HTML"
        )

@router.message(SearchStates.choosing_goal, F.text.in_(list(SEARCH_GOALS.values())))
async def choose_goal(message: Message, state: FSMContext, session: AsyncSession):
    """Выбор цели поиска"""
    goal_type = None
    for key, value in SEARCH_GOALS.items():
        if value == message.text:
            goal_type = key
            break
    
    if not goal_type:
        await message.answer("❌ Неизвестная цель поиска.")
        return
    
    # Устанавливаем цель
    await SearchService.set_user_goal(session, message.from_user.id, goal_type)
    
    # Проверяем есть ли анкета для этой цели
    profile = await SearchService.get_profile_for_goal(session, message.from_user.id, goal_type)
    
    if profile:
        # Анкета есть - возвращаемся в главное меню поиска
        await state.set_state(None)
        goal_text = SEARCH_GOALS.get(goal_type, goal_type)
        
        await message.answer(
            f"✅ <b>Цель изменена на: {goal_text}</b>\n\n"
            f"У вас уже есть анкета для этой цели.\n\n"
            f"👇 <b>Выберите действие:</b>",
            reply_markup=get_search_main_keyboard(has_goal=True),
            parse_mode="HTML"
        )
    else:
        # Нужно создать новую анкету
        await state.set_state(SearchStates.editing_profile)
        await state.update_data(current_goal=goal_type)
        
        await message.answer(
            f"📝 <b>Создание анкеты для: {message.text}</b>\n\n"
            "Расскажите о себе для этой цели поиска (минимум 20 символов):",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="❌ Отмена")]],
                resize_keyboard=True
            ),
            parse_mode="HTML"
        )

@router.message(F.text == "🎯 Сменить цель")
async def change_goal_from_main(message: Message, state: FSMContext, session: AsyncSession):
    """Сменить цель поиска из главного меню"""
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
    # Проверяем есть ли активная цель
    active_goal = await SearchService.get_user_goal(session, message.from_user.id)
    
    if not active_goal:
        await message.answer(
            "❌ <b>Сначала выберите цель поиска!</b>",
            reply_markup=get_search_main_keyboard(has_goal=False)
        )
        return
    
    # Проверяем есть ли анкета для этой цели
    profile = await SearchService.get_profile_for_goal(session, message.from_user.id, active_goal.goal_type)
    
    if not profile:
        await message.answer(
            "❌ <b>Сначала создайте анкету для выбранной цели!</b>",
            reply_markup=get_search_main_keyboard(has_goal=True)
        )
        return
    
    # Начинаем просмотр
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
    # Проверяем есть ли активная цель
    active_goal = await SearchService.get_user_goal(session, message.from_user.id)
    
    if not active_goal:
        await message.answer(
            "❌ <b>Сначала выберите цель поиска!</b>",
            reply_markup=get_search_main_keyboard(has_goal=False)
        )
        return
    
    profile = await SearchService.get_profile_for_goal(session, message.from_user.id, active_goal.goal_type)
    user = await UserService.get_user_by_telegram_id(session, message.from_user.id)
    
    if not profile:
        await message.answer(
            "❌ <b>Анкета не найдена для выбранной цели!</b>\n\n"
            "Создайте анкету для начала поиска.",
            reply_markup=get_search_main_keyboard(has_goal=True)
        )
        return
    
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
        current_goal=active_goal.goal_type,
        editing_photo=False
    )
    
    await message.answer(
        "📝 <b>Введите новое описание для вашей анкеты:</b>\n\n"
        "Минимум 20 символов, максимум 1000.",
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
    
    await state.set_state(SearchStates.editing_profile)
    await state.update_data(
        editing_photo=True,
        editing_description=False,
        current_goal=active_goal.goal_type
    )
    
    await message.answer(
        "📸 <b>Отправьте новое фото для вашей анкеты:</b>\n\n"
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
    await state.set_state(None)
    
    # Возвращаемся к просмотру своей анкеты
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
async def process_edited_description(message: Message, state: FSMContext, session: AsyncSession):
    """Обработать новое описание при редактировании"""
    if message.text == "❌ Отмена":
        await cancel_editing(message, state, session)
        return
    
    # Проверяем не редактируем ли мы фото (тогда текст не обрабатываем)
    data = await state.get_data()
    if data.get('editing_photo'):
        return
    
    if len(message.text) < 20:
        await message.answer("❌ Слишком короткое описание. Напишите хотя бы 20 символов.")
        return
    
    if len(message.text) > 1000:
        await message.answer("❌ Слишком длинное описание. Максимум 1000 символов.")
        return
    
    goal_type = data['current_goal']
    
    # Обновляем описание
    profile = await SearchService.update_profile_description(
        session=session,
        user_id=message.from_user.id,
        goal_type=goal_type,
        description=message.text
    )
    
    await state.set_state(None)
    
    if profile:
        await message.answer(
            "✅ <b>Описание обновлено!</b>",
            reply_markup=get_profile_edit_keyboard(),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "❌ <b>Ошибка при обновлении описания</b>",
            reply_markup=get_profile_edit_keyboard()
        )

@router.message(SearchStates.editing_profile, F.photo)
async def process_edited_photo(message: Message, state: FSMContext, session: AsyncSession):
    """Обработать новое фото"""
    data = await state.get_data()
    
    if not data.get('editing_photo'):
        return
    
    # Берем самое большое фото
    photo: PhotoSize = message.photo[-1]
    photo_id = photo.file_id
    
    goal_type = data['current_goal']
    
    # Обновляем фото
    profile = await SearchService.update_profile_photo(
        session=session,
        user_id=message.from_user.id,
        goal_type=goal_type,
        photo_id=photo_id
    )
    
    await state.set_state(None)
    
    if profile:
        await message.answer(
            "✅ <b>Фото обновлено!</b>",
            reply_markup=get_profile_edit_keyboard(),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "❌ <b>Ошибка при обновлении фото</b>",
            reply_markup=get_profile_edit_keyboard()
        )

async def show_next_profile(message: Message, state: FSMContext, session: AsyncSession):
    """Показать следующую анкету"""
    data = await state.get_data()
    current_goal = data.get('current_goal')
    viewed_profiles = data.get('viewed_profiles', [])
    
    # Ищем анкеты
    profiles = await SearchService.find_profiles_by_goal(
        session, current_goal, message.from_user.id, limit=50
    )
    
    # Фильтруем просмотренные
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
    
    # Берем первую доступную анкету
    profile = available_profiles[0]
    user = profile.user
    viewed_profiles.append(user.id)
    await state.update_data(
        current_profile_id=user.id,
        viewed_profiles=viewed_profiles,
        available_profiles=available_profiles[1:]
    )
    
    # Формируем текст анкеты
    gender_text = "👨 Мужской" if user.gender == "male" else "👩 Женский"
    profile_text = (
        f"👤 <b>Анкета</b>\n\n"
        f"💭 <b>Цель:</b> {SEARCH_GOALS[current_goal]}\n\n"
        f"👤 <b>Имя:</b> {user.full_name}\n"
        f"🎂 <b>Возраст:</b> {user.age} лет\n"
        f"👫 <b>Пол:</b> {gender_text}\n"
    )
    
    if user.username:
        profile_text += f"📱 <b>Username:</b> @{user.username}\n"
    
    if profile.description:
        profile_text += f"\n💬 <b>О себе:</b>\n{profile.description}\n"
    
    # Отправляем анкету
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
    
    # Ставим лайк
    success, result_type = await LikeService.add_like(
        session, message.from_user.id, current_profile_id, current_goal
    )
    
    if success:
        if result_type == "mutual_match":
            # Взаимный лайк - предлагаем написать
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
async def start_chat_after_match(message: Message, state: FSMContext):
    """Начать чат после взаимного лайка"""
    await message.answer(
        "💬 <b>Отлично!</b>\n\n"
        "Теперь вы можете общаться с этим пользователем через Telegram.\n"
        "Используйте полученный username для связи!",
        reply_markup=get_profile_view_keyboard(),
        parse_mode="HTML"
    )
    await show_next_profile(message, state, session)

@router.message(SearchStates.viewing_profiles, F.text == "👎 Пропустить")
@router.message(SearchStates.viewing_profiles, F.text == "🔍 Продолжить просмотр")
async def skip_profile(message: Message, state: FSMContext, session: AsyncSession):
    """Пропустить анкету"""
    await message.answer("👎 Анкета пропущена")
    await show_next_profile(message, state, session)

@router.message(SearchStates.viewing_profiles, F.text == "⏹️ Закончить просмотр")
async def stop_viewing_profiles(message: Message, state: FSMContext, session: AsyncSession):
    """Закончить просмотр анкет"""
    await state.set_state(None)
    
    active_goal = await SearchService.get_user_goal(session, message.from_user.id)
    goal_text = SEARCH_GOALS.get(active_goal.goal_type, active_goal.goal_type) if active_goal else "не выбрана"
    
    await message.answer(
        f"⏹️ <b>Просмотр анкет завершен</b>\n\n"
        f"🎯 <b>Текущая цель:</b> {goal_text}\n\n"
        f"Вы можете продолжить позже.",
        reply_markup=get_search_main_keyboard(has_goal=True),
        parse_mode="HTML"
    )

@router.message(StateFilter(SearchStates), F.text == "🏠 В главное меню")
async def back_to_main(message: Message, state: FSMContext):
    """Вернуться в главное меню"""
    await state.clear()
    await message.answer(
        "Возвращаемся в главное меню...",
        reply_markup=get_main_keyboard()
    )