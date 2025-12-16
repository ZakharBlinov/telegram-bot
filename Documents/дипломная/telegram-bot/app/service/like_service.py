from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
import logging

from app.models import UserLike, User
from app.service.match_service import MatchService
from app.service.notification_service import NotificationService

class LikeService:
    
    @staticmethod
    async def add_like(session: AsyncSession, from_user_id: int, to_user_id: int, goal_type: str) -> Tuple[bool, str]:
        """
        Добавить лайк и проверить взаимность
        
        Args:
            session: Сессия БД
            from_user_id: ID пользователя, который ставит лайк
            to_user_id: ID пользователя, которому ставят лайк
            goal_type: Тип цели поиска
            
        Returns:
            Tuple[bool, str]: (успех, тип результата)
            Типы результата: 
            - "like_added" - лайк добавлен
            - "mutual_match" - взаимный лайк (матч)
            - "already_liked" - уже лайкал ранее
            - "error" - ошибка
        """
        try:
            # Проверяем, не ставил ли уже лайк
            existing_like = await session.execute(
                select(UserLike).where(and_(
                    UserLike.from_user_id == from_user_id,
                    UserLike.to_user_id == to_user_id,
                    UserLike.goal_type == goal_type
                ))
            )
            
            if existing_like.scalar_one_or_none():
                return False, "already_liked"
            
            # Создаем новый лайк
            like = UserLike(
                from_user_id=from_user_id,
                to_user_id=to_user_id,
                goal_type=goal_type
            )
            session.add(like)
            await session.commit()
            
            logging.info(f"Пользователь {from_user_id} лайкнул пользователя {to_user_id} (цель: {goal_type})")
            
            # Отправляем уведомление о новом лайке
            await NotificationService.create_like_notification(
                session, from_user_id, to_user_id, goal_type
            )
            
            # Проверяем взаимный лайк
            mutual_match = await MatchService.check_mutual_like(
                session, from_user_id, to_user_id, goal_type
            )
            
            if mutual_match:
                # Создаем уведомления о взаимном матче
                await NotificationService.create_match_notification(
                    session, from_user_id, to_user_id, goal_type
                )
                return True, "mutual_match"
            
            return True, "like_added"
            
        except Exception as e:
            logging.error(f"Ошибка добавления лайка: {e}")
            await session.rollback()
            return False, "error"
    
    @staticmethod
    async def get_likes_for_user(session: AsyncSession, user_id: int) -> List[Tuple[UserLike, User]]:
        """
        Получить всех, кто лайкнул пользователя
        
        Args:
            session: Сессия БД
            user_id: ID пользователя
            
        Returns:
            List[Tuple[UserLike, User]]: Список лайков и информации о пользователях
        """
        try:
            result = await session.execute(
                select(UserLike, User)
                .join(User, User.telegram_id == UserLike.from_user_id)
                .where(UserLike.to_user_id == user_id)
                .order_by(UserLike.created_at.desc())
            )
            return result.all()
        except Exception as e:
            logging.error(f"Ошибка получения лайков для пользователя {user_id}: {e}")
            return []
    
    @staticmethod
    async def get_mutual_likes(session: AsyncSession, user_id: int) -> List[Tuple[UserLike, User]]:
        """
        Получить взаимные лайки (устаревший метод, используйте MatchService)
        
        Args:
            session: Сессия БД
            user_id: ID пользователя
            
        Returns:
            List[Tuple[UserLike, User]]: Список взаимных лайков
        """
        try:
            user_likes = await session.execute(
                select(UserLike.to_user_id).where(UserLike.from_user_id == user_id)
            )
            liked_user_ids = [row[0] for row in user_likes.all()]
            
            if not liked_user_ids:
                return []
            
            mutual_likes = await session.execute(
                select(UserLike, User)
                .join(User, User.telegram_id == UserLike.from_user_id)
                .where(and_(
                    UserLike.from_user_id.in_(liked_user_ids),
                    UserLike.to_user_id == user_id
                ))
            )
            return mutual_likes.all()
        except Exception as e:
            logging.error(f"Ошибка получения взаимных лайков: {e}")
            return []
    
    @staticmethod
    async def get_new_likes_count(session: AsyncSession, user_id: int, hours: int = 24) -> int:
        """
        Получить количество новых лайков за указанный период
        
        Args:
            session: Сессия БД
            user_id: ID пользователя
            hours: Период в часах (по умолчанию 24 часа)
            
        Returns:
            int: Количество новых лайков
        """
        try:
            time_threshold = datetime.utcnow() - timedelta(hours=hours)
            
            result = await session.execute(
                select(UserLike).where(and_(
                    UserLike.to_user_id == user_id,
                    UserLike.created_at >= time_threshold
                ))
            )
            
            return len(result.scalars().all())
        except Exception as e:
            logging.error(f"Ошибка получения количества новых лайков: {e}")
            return 0
    
    @staticmethod
    async def get_like_history(session: AsyncSession, user_id: int, limit: int = 50) -> List[Tuple[UserLike, User]]:
        """
        Получить историю лайков пользователя (кого он лайкнул)
        
        Args:
            session: Сессия БД
            user_id: ID пользователя
            limit: Ограничение количества записей
            
        Returns:
            List[Tuple[UserLike, User]]: История лайков
        """
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
    
    @staticmethod
    async def remove_like(session: AsyncSession, from_user_id: int, to_user_id: int, goal_type: str) -> bool:
        """
        Удалить лайк
        
        Args:
            session: Сессия БД
            from_user_id: ID пользователя, который ставил лайк
            to_user_id: ID пользователя, которому ставили лайк
            goal_type: Тип цели поиска
            
        Returns:
            bool: Успех операции
        """
        try:
            result = await session.execute(
                select(UserLike).where(and_(
                    UserLike.from_user_id == from_user_id,
                    UserLike.to_user_id == to_user_id,
                    UserLike.goal_type == goal_type
                ))
            )
            
            like = result.scalar_one_or_none()
            if like:
                await session.delete(like)
                await session.commit()
                logging.info(f"Пользователь {from_user_id} удалил лайк пользователю {to_user_id}")
                return True
            return False
        except Exception as e:
            logging.error(f"Ошибка удаления лайка: {e}")
            await session.rollback()
            return False
    
    @staticmethod
    async def get_likes_statistics(session: AsyncSession, user_id: int) -> dict:
        """
        Получить статистику лайков пользователя
        
        Args:
            session: Сессия БД
            user_id: ID пользователя
            
        Returns:
            dict: Статистика лайков
        """
        try:
            # Лайки, отправленные пользователем
            sent_likes = await session.execute(
                select(UserLike).where(UserLike.from_user_id == user_id)
            )
            sent_count = len(sent_likes.scalars().all())
            
            # Лайки, полученные пользователем
            received_likes = await session.execute(
                select(UserLike).where(UserLike.to_user_id == user_id)
            )
            received_count = len(received_likes.scalars().all())
            
            # Взаимные лайки
            mutual_matches = await MatchService.get_mutual_matches(session, user_id)
            mutual_count = len(mutual_matches)
            
            # Статистика по целям
            goals_stats = {}
            sent_by_goal = await session.execute(
                select(UserLike.goal_type).where(UserLike.from_user_id == user_id)
            )
            for row in sent_by_goal.all():
                goal_type = row[0]
                if goal_type not in goals_stats:
                    goals_stats[goal_type] = {"sent": 0, "received": 0, "mutual": 0}
                goals_stats[goal_type]["sent"] += 1
            
            received_by_goal = await session.execute(
                select(UserLike.goal_type).where(UserLike.to_user_id == user_id)
            )
            for row in received_by_goal.all():
                goal_type = row[0]
                if goal_type not in goals_stats:
                    goals_stats[goal_type] = {"sent": 0, "received": 0, "mutual": 0}
                goals_stats[goal_type]["received"] += 1
            
            # Взаимные по целям
            for user, goal in mutual_matches:
                if goal not in goals_stats:
                    goals_stats[goal] = {"sent": 0, "received": 0, "mutual": 0}
                goals_stats[goal]["mutual"] += 1
            
            return {
                "sent_total": sent_count,
                "received_total": received_count,
                "mutual_total": mutual_count,
                "by_goal": goals_stats,
                "success_rate": (mutual_count / sent_count * 100) if sent_count > 0 else 0
            }
            
        except Exception as e:
            logging.error(f"Ошибка получения статистики лайков: {e}")
            return {
                "sent_total": 0,
                "received_total": 0,
                "mutual_total": 0,
                "by_goal": {},
                "success_rate": 0
            }
    
    @staticmethod
    async def has_liked(session: AsyncSession, from_user_id: int, to_user_id: int, goal_type: str = None) -> bool:
        """
        Проверить, ставил ли пользователь лайк другому пользователю
        
        Args:
            session: Сессия БД
            from_user_id: ID пользователя, который мог ставить лайк
            to_user_id: ID пользователя, которому могли ставить лайк
            goal_type: Тип цели поиска (опционально)
            
        Returns:
            bool: True если лайк был поставлен
        """
        try:
            query = select(UserLike).where(and_(
                UserLike.from_user_id == from_user_id,
                UserLike.to_user_id == to_user_id
            ))
            
            if goal_type:
                query = query.where(UserLike.goal_type == goal_type)
            
            result = await session.execute(query)
            return result.scalar_one_or_none() is not None
            
        except Exception as e:
            logging.error(f"Ошибка проверки лайка: {e}")
            return False
    
    @staticmethod
    async def get_recent_likers(session: AsyncSession, user_id: int, limit: int = 10) -> List[User]:
        """
        Получить последних пользователей, которые лайкнули
        
        Args:
            session: Сессия БД
            user_id: ID пользователя
            limit: Ограничение количества
            
        Returns:
            List[User]: Список пользователей
        """
        try:
            result = await session.execute(
                select(User)
                .join(UserLike, User.telegram_id == UserLike.from_user_id)
                .where(UserLike.to_user_id == user_id)
                .order_by(UserLike.created_at.desc())
                .limit(limit)
            )
            return result.scalars().all()
        except Exception as e:
            logging.error(f"Ошибка получения последних лайкнувших: {e}")
            return []
    
    @staticmethod
    async def cleanup_old_likes(session: AsyncSession, days: int = 30) -> int:
        """
        Очистить старые лайки (для админских целей)
        
        Args:
            session: Сессия БД
            days: Удалять лайки старше этого количества дней
            
        Returns:
            int: Количество удаленных лайков
        """
        try:
            time_threshold = datetime.utcnow() - timedelta(days=days)
            
            result = await session.execute(
                select(UserLike).where(UserLike.created_at < time_threshold)
            )
            old_likes = result.scalars().all()
            
            count = len(old_likes)
            for like in old_likes:
                await session.delete(like)
            
            await session.commit()
            logging.info(f"Удалено {count} старых лайков (старше {days} дней)")
            return count
            
        except Exception as e:
            logging.error(f"Ошибка очистки старых лайков: {e}")
            await session.rollback()
            return 0
    
    @staticmethod
    async def get_likes_today(session: AsyncSession, user_id: int) -> Tuple[int, int]:
        """
        Получить статистику лайков за сегодня
        
        Args:
            session: Сессия БД
            user_id: ID пользователя
            
        Returns:
            Tuple[int, int]: (отправлено сегодня, получено сегодня)
        """
        try:
            today = datetime.utcnow().date()
            tomorrow = today + timedelta(days=1)
            
            # Отправленные сегодня
            sent_today = await session.execute(
                select(UserLike).where(and_(
                    UserLike.from_user_id == user_id,
                    UserLike.created_at >= today,
                    UserLike.created_at < tomorrow
                ))
            )
            sent_count = len(sent_today.scalars().all())
            
            # Полученные сегодня
            received_today = await session.execute(
                select(UserLike).where(and_(
                    UserLike.to_user_id == user_id,
                    UserLike.created_at >= today,
                    UserLike.created_at < tomorrow
                ))
            )
            received_count = len(received_today.scalars().all())
            
            return sent_count, received_count
            
        except Exception as e:
            logging.error(f"Ошибка получения статистики лайков за сегодня: {e}")
            return 0, 0
    
    @staticmethod
    async def get_popular_users(session: AsyncSession, limit: int = 10) -> List[Tuple[User, int]]:
        """
        Получить самых популярных пользователей (по количеству полученных лайков)
        
        Args:
            session: Сессия БД
            limit: Ограничение количества
            
        Returns:
            List[Tuple[User, int]]: Список пользователей и количество лайков
        """
        try:
            result = await session.execute(
                select(User, func.count(UserLike.id).label('like_count'))
                .join(UserLike, User.telegram_id == UserLike.to_user_id)
                .group_by(User.id)
                .order_by(func.count(UserLike.id).desc())
                .limit(limit)
            )
            
            return [(user, like_count) for user, like_count in result.all()]
            
        except Exception as e:
            logging.error(f"Ошибка получения популярных пользователей: {e}")
            return []
    
    @staticmethod
    async def get_likes_analytics(session: AsyncSession, days: int = 7) -> dict:
        """
        Получить аналитику лайков за период (для админских целей)
        
        Args:
            session: Сессия БД
            days: Количество дней для анализа
            
        Returns:
            dict: Аналитика лайков
        """
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Общее количество лайков за период
            total_likes = await session.execute(
                select(func.count(UserLike.id)).where(UserLike.created_at >= start_date)
            )
            total_count = total_likes.scalar() or 0
            
            # Лайки по дням
            daily_likes = await session.execute(
                select(
                    func.date(UserLike.created_at).label('date'),
                    func.count(UserLike.id).label('count')
                )
                .where(UserLike.created_at >= start_date)
                .group_by(func.date(UserLike.created_at))
                .order_by(func.date(UserLike.created_at))
            )
            
            daily_stats = {str(row[0]): row[1] for row in daily_likes.all()}
            
            # Лайки по целям
            likes_by_goal = await session.execute(
                select(
                    UserLike.goal_type,
                    func.count(UserLike.id).label('count')
                )
                .where(UserLike.created_at >= start_date)
                .group_by(UserLike.goal_type)
                .order_by(func.count(UserLike.id).desc())
            )
            
            goal_stats = {row[0]: row[1] for row in likes_by_goal.all()}
            
            # Самые активные пользователи
            active_users = await session.execute(
                select(
                    User,
                    func.count(UserLike.id).label('sent_count')
                )
                .join(UserLike, User.telegram_id == UserLike.from_user_id)
                .where(UserLike.created_at >= start_date)
                .group_by(User.id)
                .order_by(func.count(UserLike.id).desc())
                .limit(10)
            )
            
            top_senders = [(user, count) for user, count in active_users.all()]
            
            return {
                "total_likes": total_count,
                "daily_stats": daily_stats,
                "goal_stats": goal_stats,
                "top_senders": top_senders,
                "period_days": days
            }
            
        except Exception as e:
            logging.error(f"Ошибка получения аналитики лайков: {e}")
            return {
                "total_likes": 0,
                "daily_stats": {},
                "goal_stats": {},
                "top_senders": [],
                "period_days": days
            }