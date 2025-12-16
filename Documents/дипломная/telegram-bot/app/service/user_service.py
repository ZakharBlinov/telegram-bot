from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import User, UserLocation

class UserService:
    
    @staticmethod
    async def get_or_create_user(session: AsyncSession, telegram_id: int, username: str, full_name: str) -> User:
        """Получить или создать пользователя"""
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(
                telegram_id=telegram_id,
                username=username,
                full_name=full_name
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        
        return user
    
    @staticmethod
    async def update_user_location(session: AsyncSession, telegram_id: int, latitude: float, longitude: float, address: str = None):
        """Обновить локацию пользователя"""
        # Находим пользователя
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            # Создаем запись о локации
            location = UserLocation(
                user_id=user.id,
                latitude=str(latitude),
                longitude=str(longitude),
                address=address
            )
            session.add(location)
            await session.commit()
    
    @staticmethod
    async def get_user_location(session: AsyncSession, telegram_id: int):
        """Получить последнюю локацию пользователя"""
        result = await session.execute(
            select(UserLocation)
            .join(User)
            .where(User.telegram_id == telegram_id)
            .order_by(UserLocation.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def update_user_profile(session: AsyncSession, telegram_id: int, description: str = None, photo_id: str = None):
        """Обновить расширенный профиль пользователя"""
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            if description is not None:
                user.description = description
            if photo_id is not None:
                user.photo_id = photo_id
            user.profile_type = 'extended'  # Помечаем как расширенный профиль
            
            await session.commit()
            await session.refresh(user)
        
        return user
    
    @staticmethod
    async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int):
        """Получить пользователя по Telegram ID"""
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_users_with_extended_profiles(session: AsyncSession, exclude_telegram_id: int = None, limit: int = 50):
        """Получить пользователей с заполненными расширенными профилями"""
        query = select(User).where(
            User.profile_completed == True,
            User.description.isnot(None)
        )
        
        if exclude_telegram_id:
            query = query.where(User.telegram_id != exclude_telegram_id)
        
        query = query.order_by(User.created_at.desc()).limit(limit)
        
        result = await session.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def update_basic_profile(session: AsyncSession, telegram_id: int, full_name: str, age: int, gender: str):
        """Обновить базовый профиль пользователя"""
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.full_name = full_name
            user.age = age
            user.gender = gender
            user.profile_completed = True
            
            await session.commit()
            await session.refresh(user)
        
        return user
    
    @staticmethod
    async def reset_user_profile(session: AsyncSession, telegram_id: int):
        """Сбросить профиль пользователя (для повторного заполнения)"""
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.full_name = None
            user.age = None
            user.gender = None
            user.description = None
            user.photo_id = None
            user.profile_completed = False
            user.profile_type = 'basic'
            
            await session.commit()
            await session.refresh(user)
        
        return user