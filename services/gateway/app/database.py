"""Database session management for the gateway service."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .config import GatewaySettings, get_settings

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
    settings = settings or get_settings()
    alembic_config = AlembicConfig(str(_alembic_ini_path()))
    alembic_config.set_main_option("sqlalchemy.url", settings.database.url)
    alembic_config.set_main_option("script_location", str(_alembic_script_path()))
    await asyncio.to_thread(command.upgrade, alembic_config, "head")


def _alembic_ini_path() -> Path:
    return Path(__file__).resolve().parent.parent / "alembic.ini"


def _alembic_script_path() -> Path:
    return Path(__file__).resolve().parent.parent / "alembic"
