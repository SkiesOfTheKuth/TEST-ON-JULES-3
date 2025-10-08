"""Database session management for the gateway service."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .config import GatewaySettings, get_settings
from .models import Base

_engine: AsyncEngine | None = None
_Session: async_sessionmaker[AsyncSession] | None = None
_engine_loop: asyncio.AbstractEventLoop | None = None
_migration_lock: asyncio.Lock | None = None
_migrations_ran = False


async def get_engine(settings: GatewaySettings | None = None) -> AsyncEngine:
    global _engine, _Session, _engine_loop
    loop = asyncio.get_running_loop()
    if _engine is None or _engine_loop is None or _engine_loop is not loop:
        settings = settings or get_settings()
        if _engine is not None and _engine_loop is not loop:
            await _engine.dispose()
        _engine = create_async_engine(settings.database.url, pool_size=settings.database.pool_size)
        _Session = None
        _engine_loop = loop
    return _engine


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    global _Session
    engine = await get_engine()
    if _Session is None:
        _Session = async_sessionmaker(engine, expire_on_commit=False)
    async with _Session() as session:
        yield session


async def init_db(settings: GatewaySettings | None = None) -> None:
    global _migration_lock, _migrations_ran
    settings = settings or get_settings()

    if _migrations_ran:
        return

    if _migration_lock is None:
        _migration_lock = asyncio.Lock()

    async with _migration_lock:
        if _migrations_ran:
            return

        alembic_config = AlembicConfig(str(_alembic_ini_path()))
        alembic_config.set_main_option("sqlalchemy.url", settings.database.url)
        alembic_config.set_main_option("script_location", str(_alembic_script_path()))

        await asyncio.to_thread(command.upgrade, alembic_config, "head")

        engine = await get_engine(settings)
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT to_regclass('alembic_version')"))
            has_version = result.scalar() is not None

        if not has_version:
            script_dir = ScriptDirectory.from_config(alembic_config)
            head_revision = script_dir.get_current_head()

            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                await conn.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
                await conn.execute(
                    text("INSERT INTO alembic_version (version_num) VALUES (:rev) ON CONFLICT (version_num) DO NOTHING"),
                    {"rev": head_revision},
                )

        _migrations_ran = True


def _alembic_ini_path() -> Path:
    return Path(__file__).resolve().parent.parent / "alembic.ini"


def _alembic_script_path() -> Path:
    return Path(__file__).resolve().parent.parent / "alembic"
