from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, update, func
from typing import List, Tuple, Optional
from datetime import datetime
import logging

from app.models import ChatMessage, UserChat, User
from app.service.user_service import UserService
from app.service.notification_service import NotificationService
from app.service.match_service import MatchService

class ChatService:
    
    @staticmethod
    async def send_message(
        session: AsyncSession, 
        from_user_id: int, 
        to_user_id: int, 
        message_text: str,
        message_type: str = 'text',
        media_id: str = None
    ) -> Optional[ChatMessage]:
        """Отправить сообщение"""
        try:
            # Проверяем, есть ли взаимный матч
            mutual_match = False
            matches = await MatchService.get_mutual_matches(session, from_user_id)
            
            for user, goal in matches:
                if user.telegram_id == to_user_id:
                    mutual_match = True
                    break
            
            if not mutual_match:
                logging.warning(f"Попытка отправить сообщение без матча: {from_user_id} -> {to_user_id}")
                return None
            
            # Проверяем, не заблокирован ли чат
            user1, user2 = sorted([from_user_id, to_user_id])
            chat = await session.execute(
                select(UserChat).where(and_(
                    UserChat.user1_id == user1,
                    UserChat.user2_id == user2,
                    UserChat.is_active == True,
                    UserChat.is_blocked == False
                ))
            )
            chat = chat.scalar_one_or_none()
            
            if not chat:
                # Создаем новый чат, если его нет
                chat = UserChat(
                    user1_id=user1,
                    user2_id=user2,
                    is_active=True
                )
                session.add(chat)
            
            # Создаем сообщение
            message = ChatMessage(
                from_user_id=from_user_id,
                to_user_id=to_user_id,
                message_text=message_text,
                message_type=message_type,
                media_id=media_id
            )
            session.add(message)
            await session.commit()
            await session.refresh(message)
            
            # Обновляем или создаем чат
            await ChatService._update_user_chat(session, from_user_id, to_user_id, message.id)
            
            logging.info(f"Сообщение отправлено: {from_user_id} -> {to_user_id}")
            
            # Отправляем уведомление о новом сообщении
            await NotificationService.create_message_notification(
                session, from_user_id, to_user_id, message_text
            )
            
            return message
            
        except Exception as e:
            logging.error(f"Ошибка отправки сообщения: {e}")
            await session.rollback()
            return None
    
    @staticmethod
    async def _update_user_chat(session: AsyncSession, user1_id: int, user2_id: int, message_id: int):
        """Обновить или создать чат между пользователями"""
        # Упорядочиваем ID для уникальности
        user1, user2 = sorted([user1_id, user2_id])
        
        # Ищем существующий чат
        chat = await session.execute(
            select(UserChat).where(and_(
                UserChat.user1_id == user1,
                UserChat.user2_id == user2
            ))
        )
        chat = chat.scalar_one_or_none()
        
        if chat:
            # Обновляем существующий чат
            chat.last_message_id = message_id
            chat.last_message_at = datetime.utcnow()
            chat.is_active = True
            chat.is_blocked = False  # Снимаем блокировку при новом сообщении
            
            # Увеличиваем счетчик непрочитанных для получателя
            if user1_id == user1:  # user1 отправил сообщение user2
                chat.unread_count_user2 += 1
            else:  # user2 отправил сообщение user1
                chat.unread_count_user1 += 1
        else:
            # Создаем новый чат
            chat = UserChat(
                user1_id=user1,
                user2_id=user2,
                last_message_id=message_id,
                last_message_at=datetime.utcnow(),
                is_active=True
            )
            
            # Устанавливаем счетчик непрочитанных
            if user1_id == user1:
                chat.unread_count_user2 = 1
            else:
                chat.unread_count_user1 = 1
            
            session.add(chat)
        
        await session.commit()
    
    @staticmethod
    async def get_chat_messages(
        session: AsyncSession, 
        user1_id: int, 
        user2_id: int, 
        limit: int = 50,
        offset: int = 0
    ) -> List[ChatMessage]:
        """Получить историю сообщений между пользователями"""
        try:
            result = await session.execute(
                select(ChatMessage).where(
                    or_(
                        and_(ChatMessage.from_user_id == user1_id, ChatMessage.to_user_id == user2_id),
                        and_(ChatMessage.from_user_id == user2_id, ChatMessage.to_user_id == user1_id)
                    )
                )
                .order_by(ChatMessage.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            
            messages = result.scalars().all()
            return list(reversed(messages))  # Возвращаем в хронологическом порядке
            
        except Exception as e:
            logging.error(f"Ошибка получения сообщений чата: {e}")
            return []
    
    @staticmethod
    async def get_user_chats(session: AsyncSession, user_id: int) -> List[Tuple[UserChat, User, int]]:
        """Получить список чатов пользователя с информацией о собеседнике"""
        try:
            # Ищем чаты где пользователь является user1 или user2
            result = await session.execute(
                select(UserChat, User).where(
                    or_(
                        UserChat.user1_id == user_id,
                        UserChat.user2_id == user_id
                    ),
                    UserChat.is_active == True,
                    UserChat.is_blocked == False
                )
                .join(
                    User, 
                    and_(
                        User.telegram_id != user_id,
                        or_(
                            User.telegram_id == UserChat.user1_id,
                            User.telegram_id == UserChat.user2_id
                        )
                    )
                )
                .order_by(UserChat.last_message_at.desc())
            )
            
            chats_with_users = []
            for chat, user in result.all():
                # Определяем количество непрочитанных для текущего пользователя
                if chat.user1_id == user_id:
                    unread_count = chat.unread_count_user1
                else:
                    unread_count = chat.unread_count_user2
                
                chats_with_users.append((chat, user, unread_count))
            
            return chats_with_users
            
        except Exception as e:
            logging.error(f"Ошибка получения чатов пользователя: {e}")
            return []
    
    @staticmethod
    async def mark_messages_as_read(
        session: AsyncSession, 
        user_id: int, 
        other_user_id: int
    ) -> bool:
        """Пометить сообщения как прочитанные"""
        try:
            # Помечаем сообщения как прочитанные
            await session.execute(
                update(ChatMessage).where(and_(
                    ChatMessage.from_user_id == other_user_id,
                    ChatMessage.to_user_id == user_id,
                    ChatMessage.is_read == False
                )).values(is_read=True)
            )
            
            # Обновляем счетчик непрочитанных в чате
            user1, user2 = sorted([user_id, other_user_id])
            
            chat = await session.execute(
                select(UserChat).where(and_(
                    UserChat.user1_id == user1,
                    UserChat.user2_id == user2
                ))
            )
            chat = chat.scalar_one_or_none()
            
            if chat:
                if chat.user1_id == user_id:
                    chat.unread_count_user1 = 0
                else:
                    chat.unread_count_user2 = 0
                
                await session.commit()
            
            return True
            
        except Exception as e:
            logging.error(f"Ошибка пометки сообщений как прочитанных: {e}")
            await session.rollback()
            return False
    
    @staticmethod
    async def get_unread_messages_count(session: AsyncSession, user_id: int) -> int:
        """Получить общее количество непрочитанных сообщений"""
        try:
            result = await session.execute(
                select(func.count(ChatMessage.id)).where(and_(
                    ChatMessage.to_user_id == user_id,
                    ChatMessage.is_read == False
                ))
            )
            return result.scalar() or 0
        except Exception as e:
            logging.error(f"Ошибка получения количества непрочитанных сообщений: {e}")
            return 0
    
    @staticmethod
    async def get_last_message(session: AsyncSession, user1_id: int, user2_id: int) -> Optional[ChatMessage]:
        """Получить последнее сообщение в чате"""
        try:
            result = await session.execute(
                select(ChatMessage).where(
                    or_(
                        and_(ChatMessage.from_user_id == user1_id, ChatMessage.to_user_id == user2_id),
                        and_(ChatMessage.from_user_id == user2_id, ChatMessage.to_user_id == user1_id)
                    )
                )
                .order_by(ChatMessage.created_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logging.error(f"Ошибка получения последнего сообщения: {e}")
            return None
    
    @staticmethod
    async def delete_chat(session: AsyncSession, user_id: int, other_user_id: int) -> bool:
        """Удалить чат (архивировать)"""
        try:
            user1, user2 = sorted([user_id, other_user_id])
            
            chat = await session.execute(
                select(UserChat).where(and_(
                    UserChat.user1_id == user1,
                    UserChat.user2_id == user2
                ))
            )
            chat = chat.scalar_one_or_none()
            
            if chat:
                chat.is_active = False
                await session.commit()
                logging.info(f"Чат между {user1} и {user2} удален пользователем {user_id}")
                return True
            
            return False
            
        except Exception as e:
            logging.error(f"Ошибка удаления чата: {e}")
            await session.rollback()
            return False
    
    @staticmethod
    async def block_chat(session: AsyncSession, blocker_id: int, blocked_id: int, reason: str = None) -> bool:
        """Заблокировать чат с пользователем"""
        try:
            user1, user2 = sorted([blocker_id, blocked_id])
            
            chat = await session.execute(
                select(UserChat).where(and_(
                    UserChat.user1_id == user1,
                    UserChat.user2_id == user2
                ))
            )
            chat = chat.scalar_one_or_none()
            
            if chat:
                chat.is_blocked = True
                chat.blocked_by = blocker_id
                await session.commit()
                
                logging.info(f"Чат между {user1} и {user2} заблокирован пользователем {blocker_id}")
                return True
            
            return False
            
        except Exception as e:
            logging.error(f"Ошибка блокировки чата: {e}")
            await session.rollback()
            return False
    
    @staticmethod
    async def unblock_chat(session: AsyncSession, user1_id: int, user2_id: int) -> bool:
        """Разблокировать чат"""
        try:
            user1, user2 = sorted([user1_id, user2_id])
            
            chat = await session.execute(
                select(UserChat).where(and_(
                    UserChat.user1_id == user1,
                    UserChat.user2_id == user2,
                    UserChat.is_blocked == True
                ))
            )
            chat = chat.scalar_one_or_none()
            
            if chat:
                chat.is_blocked = False
                chat.blocked_by = None
                await session.commit()
                
                logging.info(f"Чат между {user1} и {user2} разблокирован")
                return True
            
            return False
            
        except Exception as e:
            logging.error(f"Ошибка разблокировки чата: {e}")
            await session.rollback()
            return False
    
    @staticmethod
    async def get_chat_info(session: AsyncSession, user1_id: int, user2_id: int) -> Optional[Tuple[UserChat, User]]:
        """Получить информацию о чате и собеседнике"""
        try:
            user1, user2 = sorted([user1_id, user2_id])
            
            result = await session.execute(
                select(UserChat, User).where(and_(
                    UserChat.user1_id == user1,
                    UserChat.user2_id == user2
                ))
                .join(
                    User,
                    and_(
                        User.telegram_id != user1_id,
                        or_(
                            User.telegram_id == UserChat.user1_id,
                            User.telegram_id == UserChat.user2_id
                        )
                    )
                )
            )
            
            return result.first()
            
        except Exception as e:
            logging.error(f"Ошибка получения информации о чате: {e}")
            return None
    
    @staticmethod
    async def get_message_by_id(session: AsyncSession, message_id: int) -> Optional[ChatMessage]:
        """Получить сообщение по ID"""
        try:
            result = await session.execute(
                select(ChatMessage).where(ChatMessage.id == message_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logging.error(f"Ошибка получения сообщения по ID: {e}")
            return None
    
    @staticmethod
    async def delete_message(session: AsyncSession, message_id: int, user_id: int) -> bool:
        """Удалить сообщение (только для отправителя)"""
        try:
            result = await session.execute(
                select(ChatMessage).where(and_(
                    ChatMessage.id == message_id,
                    ChatMessage.from_user_id == user_id
                ))
            )
            message = result.scalar_one_or_none()
            
            if message:
                await session.delete(message)
                await session.commit()
                
                # Обновляем последнее сообщение в чате если нужно
                last_message = await ChatService.get_last_message(
                    session, message.from_user_id, message.to_user_id
                )
                
                if last_message:
                    await ChatService._update_user_chat(
                        session, message.from_user_id, message.to_user_id, last_message.id
                    )
                else:
                    # Если сообщений больше нет, деактивируем чат
                    user1, user2 = sorted([message.from_user_id, message.to_user_id])
                    chat = await session.execute(
                        select(UserChat).where(and_(
                            UserChat.user1_id == user1,
                            UserChat.user2_id == user2
                        ))
                    )
                    chat = chat.scalar_one_or_none()
                    if chat:
                        chat.is_active = False
                        await session.commit()
                
                logging.info(f"Сообщение {message_id} удалено пользователем {user_id}")
                return True
            
            return False
            
        except Exception as e:
            logging.error(f"Ошибка удаления сообщения: {e}")
            await session.rollback()
            return False
    
    @staticmethod
    async def get_chat_analytics(session: AsyncSession, days: int = 7) -> dict:
        """Получить аналитику чатов за период (для админских целей)"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Общее количество сообщений
            total_messages = await session.execute(
                select(func.count(ChatMessage.id)).where(ChatMessage.created_at >= start_date)
            )
            total_messages_count = total_messages.scalar() or 0
            
            # Активные чаты
            active_chats = await session.execute(
                select(func.count(UserChat.id)).where(and_(
                    UserChat.is_active == True,
                    UserChat.last_message_at >= start_date
                ))
            )
            active_chats_count = active_chats.scalar() or 0
            
            # Сообщения по дням
            daily_messages = await session.execute(
                select(
                    func.date(ChatMessage.created_at).label('date'),
                    func.count(ChatMessage.id).label('count')
                )
                .where(ChatMessage.created_at >= start_date)
                .group_by(func.date(ChatMessage.created_at))
                .order_by(func.date(ChatMessage.created_at))
            )
            
            daily_stats = {str(row[0]): row[1] for row in daily_messages.all()}
            
            # Самые активные пользователи в чатах
            active_chatters = await session.execute(
                select(
                    User,
                    func.count(ChatMessage.id).label('message_count')
                )
                .join(ChatMessage, User.telegram_id == ChatMessage.from_user_id)
                .where(ChatMessage.created_at >= start_date)
                .group_by(User.id)
                .order_by(func.count(ChatMessage.id).desc())
                .limit(10)
            )
            
            top_chatters = [(user, count) for user, count in active_chatters.all()]
            
            return {
                "total_messages": total_messages_count,
                "active_chats": active_chats_count,
                "daily_stats": daily_stats,
                "top_chatters": top_chatters,
                "period_days": days
            }
            
        except Exception as e:
            logging.error(f"Ошибка получения аналитики чатов: {e}")
            return {
                "total_messages": 0,
                "active_chats": 0,
                "daily_stats": {},
                "top_chatters": [],
                "period_days": days
            }
    
    @staticmethod
    async def search_messages(
        session: AsyncSession,
        user_id: int,
        search_query: str,
        limit: int = 20
    ) -> List[Tuple[ChatMessage, User]]:
        """Поиск сообщений по тексту"""
        try:
            result = await session.execute(
                select(ChatMessage, User).where(and_(
                    or_(
                        ChatMessage.from_user_id == user_id,
                        ChatMessage.to_user_id == user_id
                    ),
                    ChatMessage.message_text.ilike(f"%{search_query}%")
                ))
                .join(
                    User,
                    and_(
                        User.telegram_id != user_id,
                        or_(
                            User.telegram_id == ChatMessage.from_user_id,
                            User.telegram_id == ChatMessage.to_user_id
                        )
                    )
                )
                .order_by(ChatMessage.created_at.desc())
                .limit(limit)
            )
            
            return result.all()
            
        except Exception as e:
            logging.error(f"Ошибка поиска сообщений: {e}")
            return []
    
    @staticmethod
    async def get_recent_chats_with_unread(session: AsyncSession, user_id: int, limit: int = 10) -> List[Tuple[UserChat, User, int]]:
        """Получить последние чаты с непрочитанными сообщениями"""
        try:
            chats = await ChatService.get_user_chats(session, user_id)
            
            # Фильтруем чаты с непрочитанными сообщениями
            chats_with_unread = [(chat, user, unread) for chat, user, unread in chats if unread > 0]
            
            # Сортируем по времени последнего сообщения и ограничиваем количество
            chats_with_unread.sort(key=lambda x: x[0].last_message_at or datetime.min, reverse=True)
            
            return chats_with_unread[:limit]
            
        except Exception as e:
            logging.error(f"Ошибка получения чатов с непрочитанными сообщениями: {e}")
            return []
    
    @staticmethod
    async def can_send_message(session: AsyncSession, from_user_id: int, to_user_id: int) -> Tuple[bool, str]:
        """
        Проверить, может ли пользователь отправить сообщение
        
        Returns:
            Tuple[bool, str]: (может отправить, причина если нет)
        """
        try:
            # Проверяем взаимный матч
            mutual_match = False
            matches = await MatchService.get_mutual_matches(session, from_user_id)
            
            for user, goal in matches:
                if user.telegram_id == to_user_id:
                    mutual_match = True
                    break
            
            if not mutual_match:
                return False, "Нет взаимного матча"
            
            # Проверяем блокировку чата
            user1, user2 = sorted([from_user_id, to_user_id])
            chat = await session.execute(
                select(UserChat).where(and_(
                    UserChat.user1_id == user1,
                    UserChat.user2_id == user2
                ))
            )
            chat = chat.scalar_one_or_none()
            
            if chat and chat.is_blocked:
                if chat.blocked_by == from_user_id:
                    return False, "Вы заблокировали этот чат"
                else:
                    return False, "Пользователь заблокировал чат"
            
            return True, "Можно отправлять сообщения"
            
        except Exception as e:
            logging.error(f"Ошибка проверки возможности отправки сообщения: {e}")
            return False, "Ошибка проверки"