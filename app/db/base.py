from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from typing import AsyncGenerator

from app.config import settings

# Create async engine for SQLAlchemy with production settings
engine_kwargs = {
    "echo": settings.DEBUG,
    "future": True
}

# Add connection pooling for PostgreSQL in production
if settings.DATABASE_URL.startswith("postgresql"):
    engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
        "pool_pre_ping": True,
        "pool_recycle": 300
    })

engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)

# Create async session factory
async_session_factory = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False,
    autoflush=False  # Added for better performance
)

# Create a base class for declarative models
Base = declarative_base()

# Dependency to get DB session
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting an async database session.
    Yields a SQLAlchemy AsyncSession that will be automatically
    committed or rolled back based on whether the request succeeds or fails.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise