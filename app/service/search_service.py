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
    async def get_profile_for_goal_any_status(session: AsyncSession, user_id: int, goal_type: str):
        """Получить анкету пользователя для конкретной цели (любой статус)"""
        result = await session.execute(
            select(UserProfileByGoal).where(and_(
                UserProfileByGoal.user_id == user_id,
                UserProfileByGoal.goal_type == goal_type
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
                is_active = False
                moderation_status = "rejected"
                moderation_reason = check_result["reason"]
                logging.info(f"Анкета ОТКЛОНЕНА автоматически: user={user_id}, причина: {moderation_reason}")
                
            elif action == "pending":
                is_active = False
                moderation_status = "pending"
                moderation_reason = check_result["reason"]
                logging.info(f"Анкета отправлена на МОДЕРАЦИЮ: user={user_id}, причина: {moderation_reason}")
                
                result = await session.execute(
                    select(User).where(User.role.in_(["admin", "moderator"]))
                )
                admins = result.scalars().all()
                goal_text = SEARCH_GOALS.get(goal_type, goal_type)
                for admin in admins:
                    await NotificationService.create_notification(
                        session, admin.telegram_id, "system",
                        "📝 Новая анкета на модерацию",
                        f"Пользователь создал анкету для цели '{goal_text}'.\nПричина: {moderation_reason}"
                    )
            else:
                is_active = True
                moderation_status = "published"
                moderation_reason = None
                logging.info(f"Анкета ОПУБЛИКОВАНА автоматически: user={user_id}")
            
            profile = UserProfileByGoal(
                user_id=user_id,
                goal_type=goal_type,
                description=description,
                photo_id=photo_id,
                is_active=is_active,
                moderation_status=moderation_status,
                moderation_reason=moderation_reason
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
            
            return profile
            
        except Exception as e:
            await session.rollback()
            logging.error(f"Ошибка создания анкеты с модерацией: {e}")
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
                logging.error(f"Анкета не найдена для обновления: user={user_id}, goal={goal_type}")
                return None
            
            if photo_id is not None:
                profile.photo_id = photo_id
                profile.updated_at = datetime.utcnow()
                
                if description is None:
                    await session.commit()
                    await session.refresh(profile)
                    logging.info(f"Фото анкеты обновлено: user={user_id}, goal={goal_type}")
                    
                    await NotificationService.create_notification(
                        session, user_id, "system",
                        "📸 Фото анкеты обновлено",
                        f"Фото для анкеты '{SEARCH_GOALS.get(goal_type, goal_type)}' успешно обновлено."
                    )
                    return profile
            
            if description is not None:
                check_result = await ModerationService.check_profile_content(description)
                action = check_result["action"]
                
                if action == "rejected":
                    profile.is_active = False
                    profile.moderation_status = "rejected"
                    profile.moderation_reason = check_result["reason"]
                    profile.description = description
                    logging.info(f"Анкета ОТКЛОНЕНА при обновлении: user={user_id}, причина: {check_result['reason']}")
                    
                    await NotificationService.create_notification(
                        session, user_id, "system",
                        "❌ Анкета отклонена",
                        f"Ваша обновлённая анкета для цели '{SEARCH_GOALS.get(goal_type, goal_type)}' отклонена.\nПричина: {check_result['reason']}"
                    )
                    
                elif action == "pending":
                    profile.is_active = False
                    profile.moderation_status = "pending"
                    profile.moderation_reason = check_result["reason"]
                    profile.description = description
                    logging.info(f"Анкета отправлена на МОДЕРАЦИЮ при обновлении: user={user_id}")
                    
                    result = await session.execute(
                        select(User).where(User.role.in_(["admin", "moderator"]))
                    )
                    admins = result.scalars().all()
                    goal_text = SEARCH_GOALS.get(goal_type, goal_type)
                    for admin in admins:
                        await NotificationService.create_notification(
                            session, admin.telegram_id, "system",
                            "📝 Анкета обновлена и требует модерации",
                            f"Пользователь обновил анкету для цели '{goal_text}'.\nПричина: {check_result['reason']}"
                        )
                    
                    await NotificationService.create_notification(
                        session, user_id, "system",
                        "⏳ Анкета на модерации",
                        f"Обновлённая анкета для цели '{SEARCH_GOALS.get(goal_type, goal_type)}' отправлена на проверку."
                    )
                    
                else:
                    profile.is_active = True
                    profile.moderation_status = "published"
                    profile.moderation_reason = None
                    profile.description = description
                    logging.info(f"Анкета ОПУБЛИКОВАНА при обновлении: user={user_id}")
                    
                    await NotificationService.create_notification(
                        session, user_id, "system",
                        "✅ Анкета обновлена",
                        f"Ваша анкета для цели '{SEARCH_GOALS.get(goal_type, goal_type)}' успешно обновлена и опубликована."
                    )
            
            profile.updated_at = datetime.utcnow()
            await session.commit()
            await session.refresh(profile)
            return profile
            
        except Exception as e:
            await session.rollback()
            logging.error(f"Ошибка обновления анкеты с модерацией: {e}")
            return None
    
    @staticmethod
    async def save_profile_for_goal(session: AsyncSession, user_id: int, goal_type: str, description: str, photo_id: str = None):
        """Сохранить анкету для конкретной цели (с модерацией)"""
        return await SearchService.create_profile_with_moderation(
            session, user_id, goal_type, description, photo_id
        )
    
    @staticmethod
    async def get_profile_for_goal(session: AsyncSession, user_id: int, goal_type: str):
        """Получить анкету пользователя для конкретной цели (только опубликованные)"""
        result = await session.execute(
            select(UserProfileByGoal).where(and_(
                UserProfileByGoal.user_id == user_id,
                UserProfileByGoal.goal_type == goal_type,
                UserProfileByGoal.is_active == True,
                UserProfileByGoal.moderation_status == "published"
            ))
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_all_user_profiles(session: AsyncSession, user_id: int):
        """Получить все анкеты пользователя (для админ-панели)"""
        result = await session.execute(
            select(UserProfileByGoal).where(
                UserProfileByGoal.user_id == user_id
            ).order_by(UserProfileByGoal.created_at.desc())
        )
        return result.scalars().all()
    
    @staticmethod
    async def find_profiles_by_goal(session: AsyncSession, goal_type: str, exclude_user_id: int, limit: int = 20):
        """Найти анкеты по цели поиска (только опубликованные)"""
        result = await session.execute(
            select(UserProfileByGoal)
            .join(User, UserProfileByGoal.user_id == User.id)
            .where(and_(
                UserProfileByGoal.goal_type == goal_type,
                UserProfileByGoal.is_active == True,
                UserProfileByGoal.moderation_status == "published",
                UserProfileByGoal.user_id != exclude_user_id,
                User.profile_completed == True,
                UserProfileByGoal.description.isnot(None)
            ))
            .order_by(UserProfileByGoal.updated_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    @staticmethod
    async def get_user_profiles(session: AsyncSession, user_id: int):
        """Получить все активные анкеты пользователя по разным целям"""
        result = await session.execute(
            select(UserProfileByGoal)
            .where(and_(
                UserProfileByGoal.user_id == user_id,
                UserProfileByGoal.is_active == True,
                UserProfileByGoal.moderation_status == "published"
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
                UserProfileByGoal.is_active == True,
                UserProfileByGoal.moderation_status == "published"
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
                UserProfileByGoal.is_active == True,
                UserProfileByGoal.moderation_status == "published"
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
                UserProfileByGoal.moderation_status == "published",
                UserProfileByGoal.user_id != current_user_id,
                User.profile_completed == True,
                UserProfileByGoal.description.isnot(None)
            ))
        )
        
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
        """Обновить фото в анкете для цели (без изменения статуса)"""
        try:
            # Ищем анкету в ЛЮБОМ статусе
            result = await session.execute(
                select(UserProfileByGoal).where(and_(
                    UserProfileByGoal.user_id == user_id,
                    UserProfileByGoal.goal_type == goal_type
                ))
            )
            profile = result.scalar_one_or_none()
            
            if not profile:
                logging.error(f"Анкета не найдена для обновления фото: user={user_id}, goal={goal_type}")
                return None
            
            profile.photo_id = photo_id
            profile.updated_at = datetime.utcnow()
            await session.commit()
            await session.refresh(profile)
            
            logging.info(f"Фото анкеты обновлено: user={user_id}, goal={goal_type}, photo_id={photo_id}")
            return profile
            
        except Exception as e:
            await session.rollback()
            logging.error(f"Ошибка обновления фото анкеты: {e}")
            return None
    
    @staticmethod
    async def update_profile_description(session: AsyncSession, user_id: int, goal_type: str, description: str):
        """Обновить описание в анкете для цели (с повторной модерацией)"""
        return await SearchService.update_profile_with_moderation(
            session, user_id, goal_type, description=description
        )
    
    @staticmethod
    async def get_pending_profiles(session: AsyncSession, limit: int = 50) -> list:
        """Получить анкеты на модерации (для админ-панели)"""
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
        """Модерация анкеты (одобрить/отклонить)"""
        try:
            result = await session.execute(
                select(UserProfileByGoal).where(UserProfileByGoal.id == profile_id)
            )
            profile = result.scalar_one_or_none()
            
            if not profile:
                return False
            
            if status == "approved":
                profile.is_active = True
                profile.moderation_status = "published"
                profile.moderation_reason = None
                action_text = "одобрена"
                notification_title = "✅ Анкета одобрена"
                notification_message = f"Ваша анкета для цели '{SEARCH_GOALS.get(profile.goal_type, profile.goal_type)}' одобрена и опубликована!"
            else:
                profile.is_active = False
                profile.moderation_status = "rejected"
                profile.moderation_reason = rejection_reason
                action_text = "отклонена"
                notification_title = "❌ Анкета отклонена"
                notification_message = f"Ваша анкета для цели '{SEARCH_GOALS.get(profile.goal_type, profile.goal_type)}' отклонена.\nПричина: {rejection_reason}"
            
            await session.commit()
            
            await NotificationService.create_notification(
                session, profile.user_id, "system",
                notification_title,
                notification_message
            )
            
            logging.info(f"Анкета {profile_id} {action_text} модератором {moderator_id}")
            return True
            
        except Exception as e:
            await session.rollback()
            logging.error(f"Ошибка модерации анкеты {profile_id}: {e}")
            return False