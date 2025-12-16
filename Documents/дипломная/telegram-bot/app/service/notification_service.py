from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from typing import List, Optional
from datetime import datetime, timedelta
import logging

from app.models import Notification, User, NOTIFICATION_TYPES
from app.service.user_service import UserService

class NotificationService:
    
    @staticmethod
    async def create_notification(
        session: AsyncSession,
        user_id: int,
        notification_type: str,
        title: str = None,
        message: str = None,
        related_user_id: int = None
    ) -> Optional[Notification]:
        """Создать уведомление для пользователя"""
        try:
            # Проверяем существование пользователя
            user = await UserService.get_user_by_telegram_id(session, user_id)
            if not user:
                logging.warning(f"Пользователь {user_id} не найден для уведомления")
                return None
            
            # Создаем уведомление
            notification = Notification(
                user_id=user_id,
                notification_type=notification_type,
                title=title,
                message=message,
                related_user_id=related_user_id
            )
            
            session.add(notification)
            await session.commit()
            await session.refresh(notification)
            
            logging.info(f"Создано уведомление {notification_type} для пользователя {user_id}")
            return notification
            
        except Exception as e:
            logging.error(f"Ошибка создания уведомления: {e}")
            await session.rollback()
            return None
    
    @staticmethod
    async def create_like_notification(
        session: AsyncSession,
        from_user_id: int,
        to_user_id: int,
        goal_type: str
    ) -> Optional[Notification]:
        """Создать уведомление о новом лайке"""
        try:
            # Получаем информацию о пользователе, который поставил лайк
            from_user = await UserService.get_user_by_telegram_id(session, from_user_id)
            if not from_user:
                return None
            
            # Определяем текст уведомления в зависимости от цели
            goal_texts = {
                "relationship": "💑 Кто-то ищет вторую половинку в вас!",
                "friendship": "👥 Кто-то хочет с вами пообщаться!",
                "gaming": "🎮 Кто-то ищет партнера для игр!",
                "hobbies": "🎨 У вас общие интересы с кем-то!",
                "services": "💼 Кому-то интересны ваши услуги!"
            }
            
            title = "💝 Новый лайк!"
            message = (
                f"{goal_texts.get(goal_type, '💝 Кто-то вас лайкнул!')}\n\n"
                f"👤 <b>{from_user.full_name}</b> ({from_user.age} лет)\n"
                f"🎯 Цель: {goal_type}\n\n"
                f"💌 Посмотрите кто это в разделе «💝 Мои лайки»!"
            )
            
            notification = await NotificationService.create_notification(
                session=session,
                user_id=to_user_id,
                notification_type="new_like",
                title=title,
                message=message,
                related_user_id=from_user_id
            )
            
            return notification
            
        except Exception as e:
            logging.error(f"Ошибка создания уведомления о лайке: {e}")
            return None
    
    @staticmethod
    async def create_match_notification(
        session: AsyncSession,
        user1_id: int,
        user2_id: int,
        goal_type: str
    ) -> List[Optional[Notification]]:
        """Создать уведомления о взаимном матче для обоих пользователей"""
        try:
            notifications = []
            
            # Получаем информацию о пользователях
            user1 = await UserService.get_user_by_telegram_id(session, user1_id)
            user2 = await UserService.get_user_by_telegram_id(session, user2_id)
            
            if not user1 or not user2:
                return notifications
            
            # Уведомление для первого пользователя
            notification1 = await NotificationService.create_notification(
                session=session,
                user_id=user1_id,
                notification_type="new_match",
                title="💞 Новый матч!",
                message=(
                    f"💞 <b>У вас взаимный лайк с {user2.full_name}!</b>\n\n"
                    f"🎯 Цель: {goal_type}\n"
                    f"👤 Возраст: {user2.age} лет\n\n"
                    f"💬 Начните общение в разделе «💬 Мои чаты»!"
                ),
                related_user_id=user2_id
            )
            
            # Уведомление для второго пользователя
            notification2 = await NotificationService.create_notification(
                session=session,
                user_id=user2_id,
                notification_type="new_match",
                title="💞 Новый матч!",
                message=(
                    f"💞 <b>У вас взаимный лайк с {user1.full_name}!</b>\n\n"
                    f"🎯 Цель: {goal_type}\n"
                    f"👤 Возраст: {user1.age} лет\n\n"
                    f"💬 Начните общение в разделе «💬 Мои чаты»!"
                ),
                related_user_id=user1_id
            )
            
            notifications = [notification1, notification2]
            logging.info(f"Созданы уведомления о матче для пользователей {user1_id} и {user2_id}")
            
            return notifications
            
        except Exception as e:
            logging.error(f"Ошибка создания уведомлений о матче: {e}")
            return []
    
    @staticmethod
    async def get_user_notifications(
        session: AsyncSession,
        user_id: int,
        limit: int = 20,
        unread_only: bool = False
    ) -> List[Notification]:
        """Получить уведомления пользователя"""
        try:
            query = select(Notification).where(Notification.user_id == user_id)
            
            if unread_only:
                query = query.where(Notification.is_read == False)
            
            query = query.order_by(Notification.created_at.desc()).limit(limit)
            
            result = await session.execute(query)
            return result.scalars().all()
            
        except Exception as e:
            logging.error(f"Ошибка получения уведомлений пользователя {user_id}: {e}")
            return []
    
    @staticmethod
    async def get_unread_count(session: AsyncSession, user_id: int) -> int:
        """Получить количество непрочитанных уведомлений"""
        try:
            result = await session.execute(
                select(func.count(Notification.id)).where(and_(
                    Notification.user_id == user_id,
                    Notification.is_read == False
                ))
            )
            return result.scalar() or 0
        except Exception as e:
            logging.error(f"Ошибка получения количества непрочитанных уведомлений: {e}")
            return 0
    
    @staticmethod
    async def mark_as_read(
        session: AsyncSession,
        notification_id: int = None,
        user_id: int = None
    ) -> bool:
        """Пометить уведомления как прочитанные"""
        try:
            if notification_id:
                # Пометить конкретное уведомление
                result = await session.execute(
                    select(Notification).where(Notification.id == notification_id)
                )
                notification = result.scalar_one_or_none()
                
                if notification:
                    notification.is_read = True
                    await session.commit()
                    return True
                    
            elif user_id:
                # Пометить все уведомления пользователя как прочитанные
                await session.execute(
                    select(Notification).where(and_(
                        Notification.user_id == user_id,
                        Notification.is_read == False
                    )).update({Notification.is_read: True})
                )
                await session.commit()
                return True
            
            return False
            
        except Exception as e:
            logging.error(f"Ошибка пометки уведомлений как прочитанных: {e}")
            await session.rollback()
            return False
    
    @staticmethod
    async def delete_notification(session: AsyncSession, notification_id: int) -> bool:
        """Удалить уведомление"""
        try:
            result = await session.execute(
                select(Notification).where(Notification.id == notification_id)
            )
            notification = result.scalar_one_or_none()
            
            if notification:
                await session.delete(notification)
                await session.commit()
                return True
            
            return False
            
        except Exception as e:
            logging.error(f"Ошибка удаления уведомления: {e}")
            await session.rollback()
            return False
    
    @staticmethod
    async def cleanup_old_notifications(session: AsyncSession, days: int = 30) -> int:
        """Очистить старые уведомления"""
        try:
            time_threshold = datetime.utcnow() - timedelta(days=days)
            
            result = await session.execute(
                select(Notification).where(Notification.created_at < time_threshold)
            )
            old_notifications = result.scalars().all()
            
            count = len(old_notifications)
            for notification in old_notifications:
                await session.delete(notification)
            
            await session.commit()
            logging.info(f"Удалено {count} старых уведомлений (старше {days} дней)")
            return count
            
        except Exception as e:
            logging.error(f"Ошибка очистки старых уведомлений: {e}")
            await session.rollback()
            return 0
    
    @staticmethod
    async def create_message_notification(
        session: AsyncSession,
        from_user_id: int,
        to_user_id: int,
        message_preview: str
    ) -> Optional[Notification]:
        """Создать уведомление о новом сообщении"""
        try:
            from_user = await UserService.get_user_by_telegram_id(session, from_user_id)
            if not from_user:
                return None
            
            title = "💬 Новое сообщение"
            message = (
                f"👤 <b>{from_user.full_name}</b> написал(а) вам:\n"
                f"💬 {message_preview[:100]}{'...' if len(message_preview) > 100 else ''}\n\n"
                f"💌 Ответьте в разделе «💬 Мои чаты»!"
            )
            
            notification = await NotificationService.create_notification(
                session=session,
                user_id=to_user_id,
                notification_type="new_message",
                title=title,
                message=message,
                related_user_id=from_user_id
            )
            
            return notification
            
        except Exception as e:
            logging.error(f"Ошибка создания уведомления о сообщении: {e}")
            return None