"""Asyncio compatibility layer for the minimal SQLAlchemy shim."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from .. import Select, _evaluate_select, _store_object


class AsyncEngine:
    def __init__(self, url: str) -> None:
        self.url = url

    def begin(self) -> "_EngineTransaction":
        return _EngineTransaction(self)

    async def dispose(self) -> None:  # pragma: no cover - compatibility shim
        return None


class _EngineTransaction:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    async def __aenter__(self) -> "_EngineTransaction":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    async def run_sync(self, func: Callable[[Any], Any]) -> Any:
        result = func(self.engine)
        if isinstance(result, Awaitable):
            return await result
        return result


def create_async_engine(url: str, pool_size: int | None = None, pool_timeout: int | None = None) -> AsyncEngine:  # noqa: ARG002 - parity only
    return AsyncEngine(url)


class AsyncSession:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._pending: list[Any] = []

    async def __aenter__(self) -> "AsyncSession":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        await self.close()
        return False

    def add(self, obj: Any) -> None:
        self._pending.append(obj)

    async def commit(self) -> None:
        for obj in self._pending:
            _store_object(obj)
        self._pending.clear()

    async def refresh(self, obj: Any) -> None:  # noqa: ARG002 - provided for API compatibility
        return None

    async def close(self) -> None:
        self._pending.clear()

    async def execute(self, statement: Select):
        return _evaluate_select(statement)


class async_sessionmaker:
    def __init__(self, engine: AsyncEngine, expire_on_commit: bool = True) -> None:  # noqa: ARG002
        self._engine = engine

    def __call__(self, **kwargs: Any) -> AsyncSession:  # noqa: ARG002 - parity with real factory
        return AsyncSession(self._engine)


__all__ = [
    "AsyncEngine",
    "AsyncSession",
    "async_sessionmaker",
    "create_async_engine",
]
