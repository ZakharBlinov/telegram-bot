from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean, UniqueConstraint, Index
from sqlalchemy.ext.declarative import declarative_base
import uuid
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(100))
    full_name = Column(String(200))
    age = Column(Integer)
    gender = Column(String(10))
    description = Column(Text)
    photo_id = Column(String(300))
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    profile_completed = Column(Boolean, default=False)
    profile_type = Column(String(20), default='basic')

class UserLocation(Base):
    __tablename__ = 'user_locations'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    latitude = Column(String(50), nullable=False)
    longitude = Column(String(50), nullable=False)
    address = Column(String(300))
    created_at = Column(DateTime, default=datetime.utcnow)

class Event(Base):
    __tablename__ = 'events'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    latitude = Column(String(50), nullable=False)
    longitude = Column(String(50), nullable=False)
    address = Column(String(300))
    author_id = Column(Integer, nullable=False)
    category = Column(String(50), default='other')
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

class UserSearchGoal(Base):
    __tablename__ = 'user_search_goals'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    goal_type = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class UserLike(Base):
    __tablename__ = 'user_likes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    from_user_id = Column(Integer, nullable=False)
    to_user_id = Column(Integer, nullable=False)
    goal_type = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class UserProfileByGoal(Base):
    __tablename__ = 'user_profiles_by_goal'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    goal_type = Column(String(50), nullable=False)
    description = Column(Text)
    photo_id = Column(String(300))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ChatMessage(Base):
    __tablename__ = 'chat_messages'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    from_user_id = Column(Integer, nullable=False, index=True)
    to_user_id = Column(Integer, nullable=False, index=True)
    message_text = Column(Text, nullable=False)
    message_type = Column(String(20), default='text')
    media_id = Column(String(300))
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('ix_chat_messages_users', 'from_user_id', 'to_user_id'),
        Index('ix_chat_messages_created', 'created_at'),
        Index('ix_chat_messages_unread', 'to_user_id', 'is_read'),
    )

class UserChat(Base):
    __tablename__ = 'user_chats'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user1_id = Column(Integer, nullable=False, index=True)
    user2_id = Column(Integer, nullable=False, index=True)
    last_message_id = Column(Integer, ForeignKey('chat_messages.id'))
    last_message_at = Column(DateTime, default=datetime.utcnow)
    unread_count_user1 = Column(Integer, default=0)
    unread_count_user2 = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    is_blocked = Column(Boolean, default=False)
    blocked_by = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('user1_id', 'user2_id', name='uq_user_chat_pair'),
        Index('ix_user_chats_last_message', 'last_message_at'),
        Index('ix_user_chats_active', 'is_active'),
    )

class Notification(Base):
    __tablename__ = 'notifications'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    notification_type = Column(String(50), nullable=False)
    title = Column(String(200))
    message = Column(Text)
    related_user_id = Column(Integer)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('ix_notifications_user_unread', 'user_id', 'is_read'),
        Index('ix_notifications_created', 'created_at'),
    )

class UserBlock(Base):
    __tablename__ = 'user_blocks'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    blocker_id = Column(Integer, nullable=False, index=True)
    blocked_id = Column(Integer, nullable=False, index=True)
    reason = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('blocker_id', 'blocked_id', name='uq_user_block_pair'),
    )

class SearchFilter(Base):
    __tablename__ = 'search_filters'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, unique=True, index=True)
    min_age = Column(Integer, default=18)
    max_age = Column(Integer, default=99)
    gender_preference = Column(String(20), default='any')
    max_distance_km = Column(Integer, default=50)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

SEARCH_GOALS = {
    "relationship": "💑 Вторую половинку",
    "friendship": "👥 Найти общение", 
    "gaming": "🎮 С кем поиграть",
    "hobbies": "🎨 Общие интересы",
    "services": "💼 Предложенные услуги"
}

NOTIFICATION_TYPES = {
    "new_like": "💝 Новый лайк",
    "new_match": "💞 Новый матч", 
    "new_message": "💬 Новое сообщение",
    "profile_view": "👀 Просмотр профиля",
    "event_nearby": "📍 Событие рядом",
    "system": "🔔 Системное уведомление"
}

MESSAGE_TYPES = {
    "text": "Текст",
    "photo": "Фото",
    "voice": "Голосовое сообщение",
    "document": "Документ",
    "sticker": "Стикер"
}

GENDER_PREFERENCES = {
    "any": "Любой",
    "male": "Мужской", 
    "female": "Женский",
    "both": "Оба"
}