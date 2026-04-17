"""SQLAlchemy async engine and session factory."""

from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from obsidian_sync.config import settings

# Ensure SQLite directory exists before engine creation
if settings.database_url.startswith("sqlite"):
    db_path = settings.database_url.split("///")[-1]
    if db_path:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {},
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
