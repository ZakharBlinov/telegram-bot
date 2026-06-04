from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime
import logging

from app.models import User, UserSearchGoal, UserProfileByGoal, SEARCH_GOALS
from app.service.moderation_service import ModerationService
from app.service.notification_service import NotificationService

class SearchService:
    
    @staticmethod
    async def set_user_goal(session: AsyncSession, user_id: int, goal_type: str):
        """Установить цель поиска для пользователя"""
        old_goals = await session.execute(
            select(UserSearchGoal)
            .where(and_(
                UserSearchGoal.user_id == user_id,
                UserSearchGoal.is_active == True
            ))
        )
        for goal in old_goals.scalars():
            goal.is_active = False
        
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
    async def create_profile_with_moderation(
        session: AsyncSession, 
        user_id: int, 
        goal_type: str, 
        description: str, 
        photo_id: str = None
    ) -> UserProfileByGoal:
        """Создать анкету с автоматической модерацией"""
        try:
            check_result = await ModerationService.check_profile_content(description)
            action = check_result["action"]
            
            if action == "rejected":
                moderation_status = "rejected"
                is_active = False
                moderation_reason = check_result["reason"]
                logging.info(f"Анкета ОТКЛОНЕНА: user={user_id}, причина={moderation_reason}")
                
            elif action == "pending":
                moderation_status = "pending"
                is_active = False
                moderation_reason = check_result["reason"]
                logging.info(f"Анкета отправлена на МОДЕРАЦИЮ: user={user_id}, причина={moderation_reason}")
                
                result = await session.execute(
                    select(User).where(User.role.in_(["admin", "moderator"]))
                )
                admins = result.scalars().all()
                goal_text = SEARCH_GOALS.get(goal_type, goal_type)
                for admin in admins:
                    await NotificationService.create_notification(
                        session, admin.telegram_id, "system",
                        "📝 Новая анкета на модерацию",
                        f"Пользователь создал анкету для цели '{goal_text}' и требует проверки."
                    )
            else:
                moderation_status = "published"
                is_active = True
                moderation_reason = None
                logging.info(f"Анкета ОПУБЛИКОВАНА: user={user_id}")
            
            profile = UserProfileByGoal(
                user_id=user_id,
                goal_type=goal_type,
                description=description,
                photo_id=photo_id,
                is_active=is_active,
                moderation_status=moderation_status,
                moderation_reason=moderation_reason,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            session.add(profile)
            await session.commit()
            await session.refresh(profile)
            
            if moderation_status == "rejected":
                await NotificationService.create_notification(
                    session, user_id, "system",
                    "❌ Анкета отклонена",
                    f"Ваша анкета для цели '{SEARCH_GOALS.get(goal_type, goal_type)}' отклонена.\nПричина: {moderation_reason}"
                )
            elif moderation_status == "pending":
                await NotificationService.create_notification(
                    session, user_id, "system",
                    "⏳ Анкета на модерации",
                    f"Ваша анкета для цели '{SEARCH_GOALS.get(goal_type, goal_type)}' отправлена на проверку администратору."
                )
            else:
                await NotificationService.create_notification(
                    session, user_id, "system",
                    "✅ Анкета опубликована",
                    f"Ваша анкета для цели '{SEARCH_GOALS.get(goal_type, goal_type)}' опубликована и видна другим пользователям."
                )
            
            logging.info(f"Создана анкета: user={user_id}, goal={goal_type}, status={moderation_status}")
            return profile
            
        except Exception as e:
            await session.rollback()
            logging.error(f"Ошибка создания анкеты: {e}")
            return None
    
    @staticmethod
    async def update_profile_with_moderation(
        session: AsyncSession, 
        user_id: int, 
        goal_type: str, 
        description: str = None,
        photo_id: str = None
    ) -> UserProfileByGoal:
        """Обновить анкету с повторной модерацией"""
        try:
            existing_profile = await session.execute(
                select(UserProfileByGoal).where(and_(
                    UserProfileByGoal.user_id == user_id,
                    UserProfileByGoal.goal_type == goal_type
                ))
            )
            profile = existing_profile.scalar_one_or_none()
            
            if not profile:
                logging.error(f"Анкета не найдена: user={user_id}, goal={goal_type}")
                return None
            
            if photo_id is not None:
                profile.photo_id = photo_id
                profile.updated_at = datetime.utcnow()
                await session.commit()
                await session.refresh(profile)
                return profile
            
            if description is not None:
                check_result = await ModerationService.check_profile_content(description)
                action = check_result["action"]
                
                if action == "rejected":
                    profile.moderation_status = "rejected"
                    profile.is_active = False
                    profile.moderation_reason = check_result["reason"]
                    profile.description = description
                elif action == "pending":
                    profile.moderation_status = "pending"
                    profile.is_active = False
                    profile.moderation_reason = check_result["reason"]
                    profile.description = description
                else:
                    profile.moderation_status = "published"
                    profile.is_active = True
                    profile.moderation_reason = None
                    profile.description = description
                
                profile.updated_at = datetime.utcnow()
                await session.commit()
                await session.refresh(profile)
                return profile
            
            return profile
            
        except Exception as e:
            await session.rollback()
            logging.error(f"Ошибка обновления анкеты: {e}")
            return None
    
    @staticmethod
    async def save_profile_for_goal(session: AsyncSession, user_id: int, goal_type: str, description: str, photo_id: str = None):
        """Сохранить анкету"""
        return await SearchService.create_profile_with_moderation(session, user_id, goal_type, description, photo_id)
    
    @staticmethod
    async def get_profile_for_goal(session: AsyncSession, user_id: int, goal_type: str):
        """Получить анкету пользователя для конкретной цели (только опубликованные)"""
        result = await session.execute(
            select(UserProfileByGoal).where(and_(
                UserProfileByGoal.user_id == user_id,
                UserProfileByGoal.goal_type == goal_type,
                UserProfileByGoal.moderation_status == "published",
                UserProfileByGoal.is_active == True
            )).limit(1)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_profile_for_goal_any_status(session: AsyncSession, user_id: int, goal_type: str):
        """Получить анкету пользователя для конкретной цели (любой статус)"""
        result = await session.execute(
            select(UserProfileByGoal).where(and_(
                UserProfileByGoal.user_id == user_id,
                UserProfileByGoal.goal_type == goal_type
            )).limit(1)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_all_user_profiles(session: AsyncSession, user_id: int):
        """Получить все анкеты пользователя"""
        result = await session.execute(
            select(UserProfileByGoal).where(
                UserProfileByGoal.user_id == user_id
            ).order_by(UserProfileByGoal.created_at.desc())
        )
        return result.scalars().all()
    
    @staticmethod
    async def find_profiles_by_goal(session: AsyncSession, goal_type: str, exclude_user_id: int, limit: int = 20):
        """Найти анкеты по цели (только опубликованные)"""
        result = await session.execute(
            select(UserProfileByGoal)
            .join(User, UserProfileByGoal.user_id == User.id)
            .where(and_(
                UserProfileByGoal.goal_type == goal_type,
                UserProfileByGoal.moderation_status == "published",
                UserProfileByGoal.is_active == True,
                User.telegram_id != exclude_user_id,
                User.profile_completed == True
            ))
            .order_by(UserProfileByGoal.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    @staticmethod
    async def update_profile_photo(session: AsyncSession, user_id: int, goal_type: str, photo_id: str):
        """Обновить фото"""
        try:
            result = await session.execute(
                select(UserProfileByGoal).where(and_(
                    UserProfileByGoal.user_id == user_id,
                    UserProfileByGoal.goal_type == goal_type
                ))
            )
            profile = result.scalar_one_or_none()
            
            if not profile:
                return None
            
            profile.photo_id = photo_id
            profile.updated_at = datetime.utcnow()
            await session.commit()
            await session.refresh(profile)
            return profile
            
        except Exception as e:
            await session.rollback()
            logging.error(f"Ошибка обновления фото: {e}")
            return None
    
    @staticmethod
    async def update_profile_description(session: AsyncSession, user_id: int, goal_type: str, description: str):
        """Обновить описание"""
        return await SearchService.update_profile_with_moderation(session, user_id, goal_type, description=description)
    
    @staticmethod
    async def get_pending_profiles(session: AsyncSession, limit: int = 50) -> list:
        """Получить анкеты на модерации"""
        try:
            result = await session.execute(
                select(UserProfileByGoal, User)
                .join(User, UserProfileByGoal.user_id == User.id)
                .where(UserProfileByGoal.moderation_status == "pending")
                .order_by(UserProfileByGoal.created_at.desc())
                .limit(limit)
            )
            return result.all()
        except Exception as e:
            logging.error(f"Ошибка получения анкет на модерации: {e}")
            return []
    
    @staticmethod
    async def moderate_profile(
        session: AsyncSession, 
        profile_id: int, 
        status: str, 
        moderator_id: int,
        rejection_reason: str = None
    ) -> bool:
        """Модерация анкеты"""
        try:
            result = await session.execute(
                select(UserProfileByGoal).where(UserProfileByGoal.id == profile_id)
            )
            profile = result.scalar_one_or_none()
            
            if not profile:
                return False
            
            if status == "approved":
                profile.moderation_status = "published"
                profile.is_active = True
                profile.moderation_reason = None
                notification_title = "✅ Анкета одобрена"
                notification_message = f"Ваша анкета для цели '{SEARCH_GOALS.get(profile.goal_type, profile.goal_type)}' одобрена и опубликована!"
            else:
                profile.moderation_status = "rejected"
                profile.is_active = False
                profile.moderation_reason = rejection_reason
                notification_title = "❌ Анкета отклонена"
                notification_message = f"Ваша анкета для цели '{SEARCH_GOALS.get(profile.goal_type, profile.goal_type)}' отклонена.\nПричина: {rejection_reason}"
            
            profile.updated_at = datetime.utcnow()
            await session.commit()
            
            await NotificationService.create_notification(
                session, profile.user_id, "system",
                notification_title,
                notification_message
            )
            
            logging.info(f"Анкета {profile_id} промодерирована: {status}")
            return True
            
        except Exception as e:
            await session.rollback()
            logging.error(f"Ошибка модерации анкеты: {e}")
            return False