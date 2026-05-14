from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import Config
from app.models import Base
from app.models import upgrade_models

config = Config()

engine = create_async_engine(config.DATABASE_URL, echo=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    """Инициализация базы данных"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    upgrade_models()
    
    from app.models import User
    from sqlalchemy import select
    from app.web.auth import get_password_hash
    
    async for session in get_session():
        result = await session.execute(select(User).where(User.telegram_id == int(config.ADMIN_ID)))
        admin = result.scalar_one_or_none()
        
        if admin:
            if admin.role != "admin":
                admin.role = "admin"
                await session.commit()
        else:
            admin = User(
                telegram_id=int(config.ADMIN_ID),
                username="admin",
                full_name="Administrator",
                role="admin",
                password_hash=get_password_hash("admin123"),
                profile_completed=True
            )
            session.add(admin)
            await session.commit()
        
        break
    
    print("✅ База данных инициализирована")

async def get_session():
    """Получение сессии БД"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()