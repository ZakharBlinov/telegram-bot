# app/service/search_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from app.models import User, UserSearchGoal, UserProfileByGoal, SEARCH_GOALS

class SearchService:
    
    @staticmethod
    async def set_user_goal(session: AsyncSession, user_id: int, goal_type: str):
        """Установить цель поиска для пользователя"""
        # Деактивируем старые цели
        old_goals = await session.execute(
            select(UserSearchGoal)
            .where(and_(
                UserSearchGoal.user_id == user_id,
                UserSearchGoal.is_active == True
            ))
        )
        for goal in old_goals.scalars():
            goal.is_active = False
        
        # Создаем новую цель
        goal = UserSearchGoal(
            user_id=user_id,
            goal_type=goal_type,
            is_active=True
        )
        session.add(goal)
        await session.commit()
        await session.refresh(goal)
        return goal
    
    @staticmethod
    async def get_user_goal(session: AsyncSession, user_id: int):
        """Получить активную цель поиска пользователя"""
        result = await session.execute(
            select(UserSearchGoal)
            .where(and_(
                UserSearchGoal.user_id == user_id,
                UserSearchGoal.is_active == True
            ))
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def save_profile_for_goal(session: AsyncSession, user_id: int, goal_type: str, description: str, photo_id: str = None):
        """Сохранить анкету для конкретной цели"""
        # Проверяем есть ли уже анкета для этой цели
        existing_profile = await session.execute(
            select(UserProfileByGoal).where(and_(
                UserProfileByGoal.user_id == user_id,
                UserProfileByGoal.goal_type == goal_type
            ))
        )
        profile = existing_profile.scalar_one_or_none()
        
        if profile:
            # Обновляем существующую анкету
            profile.description = description
            if photo_id is not None:
                profile.photo_id = photo_id
            profile.is_active = True
        else:
            # Создаем новую анкету
            profile = UserProfileByGoal(
                user_id=user_id,
                goal_type=goal_type,
                description=description,
                photo_id=photo_id
            )
            session.add(profile)
        
        await session.commit()
        await session.refresh(profile)
        return profile
    
    @staticmethod
    async def get_profile_for_goal(session: AsyncSession, user_id: int, goal_type: str):
        """Получить анкету пользователя для конкретной цели"""
        result = await session.execute(
            select(UserProfileByGoal).where(and_(
                UserProfileByGoal.user_id == user_id,
                UserProfileByGoal.goal_type == goal_type,
                UserProfileByGoal.is_active == True
            ))
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def find_users_by_goal(session: AsyncSession, goal_type: str, current_user_id: int, limit: int = 10):
        """Найти пользователей по цели поиска"""
        result = await session.execute(
            select(User, UserProfileByGoal)
            .join(UserProfileByGoal, UserProfileByGoal.user_id == User.id)
            .where(and_(
                UserProfileByGoal.goal_type == goal_type,
                UserProfileByGoal.is_active == True,
                User.id != current_user_id,
                User.profile_completed == True
            ))
            .order_by(UserProfileByGoal.updated_at.desc())
            .limit(limit)
        )
        return result.all()

    # НОВЫЕ МЕТОДЫ ДЛЯ РАБОТЫ С ОТДЕЛЬНЫМИ АНКЕТАМИ ПО ЦЕЛЯМ

    @staticmethod
    async def create_or_update_profile(session: AsyncSession, user_id: int, goal_type: str, description: str, photo_id: str = None):
        """Создать или обновить анкету для конкретной цели"""
        return await SearchService.save_profile_for_goal(session, user_id, goal_type, description, photo_id)
    
    @staticmethod
    async def find_profiles_by_goal(session: AsyncSession, goal_type: str, exclude_user_id: int, limit: int = 20):
        """Найти анкеты по цели поиска"""
        result = await session.execute(
            select(UserProfileByGoal)
            .join(User, UserProfileByGoal.user_id == User.id)
            .where(and_(
                UserProfileByGoal.goal_type == goal_type,
                UserProfileByGoal.is_active == True,
                UserProfileByGoal.user_id != exclude_user_id,
                User.profile_completed == True,
                UserProfileByGoal.description.isnot(None)  # Убедимся что есть описание
            ))
            .order_by(UserProfileByGoal.updated_at.desc())
            .limit(limit)
        )
        profiles = result.scalars().all()
        
        # Получаем пользователей для каждого профиля
        profiles_with_users = []
        for profile in profiles:
            user_result = await session.execute(
                select(User).where(User.id == profile.user_id)
            )
            user = user_result.scalar_one()
            profiles_with_users.append(profile)
        
        return profiles_with_users
    
    @staticmethod
    async def get_user_profiles(session: AsyncSession, user_id: int):
        """Получить все анкеты пользователя по разным целям"""
        result = await session.execute(
            select(UserProfileByGoal)
            .where(and_(
                UserProfileByGoal.user_id == user_id,
                UserProfileByGoal.is_active == True
            ))
            .order_by(UserProfileByGoal.goal_type)
        )
        return result.scalars().all()
    
    @staticmethod
    async def deactivate_profile(session: AsyncSession, user_id: int, goal_type: str):
        """Деактивировать анкету для определенной цели"""
        profile = await SearchService.get_profile_for_goal(session, user_id, goal_type)
        if profile:
            profile.is_active = False
            await session.commit()
        return profile
    
    @staticmethod
    async def get_active_profiles_count(session: AsyncSession, user_id: int):
        """Получить количество активных анкет пользователя"""
        result = await session.execute(
            select(UserProfileByGoal)
            .where(and_(
                UserProfileByGoal.user_id == user_id,
                UserProfileByGoal.is_active == True
            ))
        )
        return len(result.scalars().all())
    
    @staticmethod
    async def has_profile_for_goal(session: AsyncSession, user_id: int, goal_type: str):
        """Проверить есть ли у пользователя анкета для указанной цели"""
        profile = await SearchService.get_profile_for_goal(session, user_id, goal_type)
        return profile is not None
    
    @staticmethod
    async def get_profile_with_user(session: AsyncSession, user_id: int, goal_type: str):
        """Получить анкету с информацией о пользователе"""
        result = await session.execute(
            select(UserProfileByGoal, User)
            .join(User, UserProfileByGoal.user_id == User.id)
            .where(and_(
                UserProfileByGoal.user_id == user_id,
                UserProfileByGoal.goal_type == goal_type,
                UserProfileByGoal.is_active == True
            ))
        )
        return result.first()
    
    @staticmethod
    async def find_compatible_profiles(session: AsyncSession, goal_type: str, current_user_id: int, user_gender: str = None, age_range: tuple = None, limit: int = 20):
        """Найти совместимые анкеты с дополнительными фильтрами"""
        query = (
            select(UserProfileByGoal)
            .join(User, UserProfileByGoal.user_id == User.id)
            .where(and_(
                UserProfileByGoal.goal_type == goal_type,
                UserProfileByGoal.is_active == True,
                UserProfileByGoal.user_id != current_user_id,
                User.profile_completed == True,
                UserProfileByGoal.description.isnot(None)
            ))
        )
        
        # Добавляем фильтры если указаны
        if user_gender:
            query = query.where(User.gender == user_gender)
        
        if age_range:
            min_age, max_age = age_range
            query = query.where(and_(
                User.age >= min_age,
                User.age <= max_age
            ))
        
        query = query.order_by(UserProfileByGoal.updated_at.desc()).limit(limit)
        
        result = await session.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def update_profile_photo(session: AsyncSession, user_id: int, goal_type: str, photo_id: str):
        """Обновить фото в анкете для цели"""
        profile = await SearchService.get_profile_for_goal(session, user_id, goal_type)
        if profile:
            profile.photo_id = photo_id
            await session.commit()
            await session.refresh(profile)
        return profile
    
    @staticmethod
    async def update_profile_description(session: AsyncSession, user_id: int, goal_type: str, description: str):
        """Обновить описание в анкете для цели"""
        profile = await SearchService.get_profile_for_goal(session, user_id, goal_type)
        if profile:
            profile.description = description
            await session.commit()
            await session.refresh(profile)
        return profile