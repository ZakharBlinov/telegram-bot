from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from typing import List, Tuple
import logging

from app.models import UserLike, User
from app.service.user_service import UserService

class MatchService:
    
    @staticmethod
    async def check_mutual_like(session: AsyncSession, user1_id: int, user2_id: int, goal_type: str) -> bool:
        """Проверить взаимные лайки между двумя пользователями"""
        try:
            # Проверяем лайк от user1 к user2
            like1 = await session.execute(
                select(UserLike).where(and_(
                    UserLike.from_user_id == user1_id,
                    UserLike.to_user_id == user2_id,
                    UserLike.goal_type == goal_type
                ))
            )
            
            # Проверяем лайк от user2 к user1
            like2 = await session.execute(
                select(UserLike).where(and_(
                    UserLike.from_user_id == user2_id,
                    UserLike.to_user_id == user1_id,
                    UserLike.goal_type == goal_type
                ))
            )
            
            return like1.scalar_one_or_none() is not None and like2.scalar_one_or_none() is not None
            
        except Exception as e:
            logging.error(f"Ошибка проверки взаимных лайков: {e}")
            return False
    
    @staticmethod
    async def get_mutual_matches(session: AsyncSession, user_id: int, goal_type: str = None) -> List[Tuple[User, str]]:
        """Получить список взаимных матчей пользователя"""
        try:
            # Получаем всех, кого лайкнул пользователь
            user_likes = await session.execute(
                select(UserLike.to_user_id, UserLike.goal_type).where(
                    UserLike.from_user_id == user_id
                )
            )
            user_liked_ids = {(row[0], row[1]) for row in user_likes.all()}
            
            if not user_liked_ids:
                return []
            
            # Ищем тех, кто тоже лайкнул пользователя
            matches = []
            for liked_user_id, goal in user_liked_ids:
                if goal_type and goal != goal_type:
                    continue
                    
                mutual = await MatchService.check_mutual_like(
                    session, user_id, liked_user_id, goal
                )
                
                if mutual:
                    # Получаем информацию о пользователе
                    user = await UserService.get_user_by_telegram_id(session, liked_user_id)
                    if user:
                        matches.append((user, goal))
            
            return matches
            
        except Exception as e:
            logging.error(f"Ошибка получения взаимных матчей: {e}")
            return []
    
    @staticmethod
    async def create_match_notification(session: AsyncSession, user1_id: int, user2_id: int, goal_type: str):
        """Создать уведомление о взаимном матче"""
        # Здесь можно добавить логику отправки уведомлений
        # Пока просто логируем
        logging.info(f"МАТЧ! Пользователи {user1_id} и {user2_id} по цели: {goal_type}")
        
    @staticmethod
    async def get_like_history(session: AsyncSession, user_id: int, limit: int = 50) -> List[Tuple[UserLike, User]]:
        """Получить историю лайков пользователя"""
        try:
            result = await session.execute(
                select(UserLike, User)
                .join(User, User.telegram_id == UserLike.to_user_id)
                .where(UserLike.from_user_id == user_id)
                .order_by(UserLike.created_at.desc())
                .limit(limit)
            )
            return result.all()
        except Exception as e:
            logging.error(f"Ошибка получения истории лайков: {e}")
            return []
