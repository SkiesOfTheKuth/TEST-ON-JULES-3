"""Database session management for the gateway service."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .config import GatewaySettings, get_settings
from .models import Base

_engine: AsyncEngine | None = None
_Session: async_sessionmaker[AsyncSession] | None = None


async def get_engine(settings: GatewaySettings | None = None) -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = settings or get_settings()
        _engine = create_async_engine(settings.database.url, pool_size=settings.database.pool_size)
    return _engine


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    global _Session
    if _Session is None:
        engine = await get_engine()
        _Session = async_sessionmaker(engine, expire_on_commit=False)
    async with _Session() as session:
        yield session


async def init_db(settings: GatewaySettings | None = None) -> None:
    engine = await get_engine(settings)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
