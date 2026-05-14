from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from app.service.match_service import MatchService
from app.service.search_service import SearchService
from app.keyboards.main_menu import get_main_keyboard
from app.models import SEARCH_GOALS

router = Router()

def get_matches_keyboard():
    """Клавиатура для раздела матчей"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💝 Мои матчи"), KeyboardButton(text="📈 Статистика")],
            [KeyboardButton(text="🏠 В главное меню")]
        ],
        resize_keyboard=True
    )

@router.message(F.text == "💝 Мои матчи")
async def show_my_matches(message: Message, session: AsyncSession):
    """Показать взаимные матчи пользователя"""
    matches = await MatchService.get_mutual_matches(session, message.from_user.id)
    
    if not matches:
        await message.answer(
            "💔 <b>У вас пока нет взаимных матчей</b>\n\n"
            "Продолжайте просматривать анкеты и ставить лайки!\n"
            "Когда кто-то ответит вам взаимностью, вы увидите его здесь.",
            reply_markup=get_matches_keyboard(),
            parse_mode="HTML"
        )
        return
    
    matches_by_goal = {}
    for user, goal in matches:
        if goal not in matches_by_goal:
            matches_by_goal[goal] = []
        matches_by_goal[goal].append(user)
    
    response = "💝 <b>Ваши взаимные матчи</b>\n\n"
    
    for goal, users in matches_by_goal.items():
        goal_text = SEARCH_GOALS.get(goal, goal)
        response += f"🎯 <b>{goal_text}</b> - {len(users)} матчей\n"
        
        for user in users[:3]:  # Показываем первые 3 матча в каждой категории
            response += f"   👤 {user.full_name} ({user.age} лет)\n"
        
        if len(users) > 3:
            response += f"   ... и еще {len(users) - 3}\n"
        response += "\n"
    
    response += "👇 <b>Используйте кнопки ниже для управления матчами:</b>"
    
    await message.answer(
        response,
        reply_markup=get_matches_keyboard(),
        parse_mode="HTML"
    )

@router.message(F.text == "📈 Статистика")
async def show_likes_statistics(message: Message, session: AsyncSession):
    """Показать статистику лайков"""
    from app.service.like_service import LikeService
    
    # Получаем историю лайков
    like_history = await LikeService.get_like_history(session, message.from_user.id)
    mutual_matches = await MatchService.get_mutual_matches(session, message.from_user.id)
    
    sent_likes = len(like_history)
    received_likes = await LikeService.get_likes_for_user(session, message.from_user.id)
    mutual_count = len(mutual_matches)
    
    # Группируем по целям
    goals_stats = {}
    for like, user in like_history:
        if like.goal_type not in goals_stats:
            goals_stats[like.goal_type] = 0
        goals_stats[like.goal_type] += 1
    
    response = (
        "📈 <b>Ваша статистика лайков</b>\n\n"
        f"💝 <b>Отправлено лайков:</b> {sent_likes}\n"
        f"💌 <b>Получено лайков:</b> {len(received_likes)}\n"
        f"💞 <b>Взаимных матчей:</b> {mutual_count}\n\n"
    )
    
    if goals_stats:
        response += "<b>По целям поиска:</b>\n"
        for goal_type, count in goals_stats.items():
            goal_text = SEARCH_GOALS.get(goal_type, goal_type)
            response += f"  {goal_text}: {count} лайков\n"
    
    await message.answer(
        response,
        reply_markup=get_matches_keyboard(),
        parse_mode="HTML"
    )

@router.message(F.text == "🏠 В главное меню")
async def back_to_main_from_matches(message: Message):
    """Вернуться в главное меню из раздела матчей"""
    await message.answer(
        "Возвращаемся в главное меню...",
        reply_markup=get_main_keyboard()
    )