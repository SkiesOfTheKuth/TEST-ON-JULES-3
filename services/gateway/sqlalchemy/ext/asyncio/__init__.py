"""Tiny async engine/session compatible facade for tests."""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from ...orm import DeclarativeBase

__all__ = ["AsyncEngine", "AsyncSession", "async_sessionmaker", "create_async_engine"]


class AsyncEngine:
    def __init__(self, url: str) -> None:
        self.url = url
        self._tables: Dict[str, List[Any]] = {}

    def begin(self) -> "_AsyncConnection":
        return _AsyncConnection(self)

    async def dispose(self) -> None:
        self._tables.clear()

    def _ensure_table(self, model: type[DeclarativeBase]) -> None:
        self._tables.setdefault(model.__tablename__, [])

    def _add(self, instance: DeclarativeBase) -> None:
        table = self._tables.setdefault(instance.__class__.__tablename__, [])
        if instance not in table:
            table.append(instance)

    def _rows(self, model: type[DeclarativeBase]) -> List[DeclarativeBase]:
        return list(self._tables.get(model.__tablename__, []))


class _AsyncConnection:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def __aenter__(self) -> "_AsyncConnection":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def run_sync(self, func: Callable[[Any], Any]) -> Any:
        return func(self._engine)


class async_sessionmaker:
    def __init__(self, engine: AsyncEngine, *, expire_on_commit: bool = False) -> None:
        self._engine = engine
        self._expire_on_commit = expire_on_commit

    def __call__(self, **kwargs: Any) -> "AsyncSession":
        return AsyncSession(self._engine)


class AsyncSession:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._pending: list[Any] = []

    async def __aenter__(self) -> "AsyncSession":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if exc_type is not None:
            await self.rollback()
        else:
            await self.commit()

    def add(self, instance: DeclarativeBase) -> None:
        self._pending.append(instance)

    async def commit(self) -> None:
        for instance in self._pending:
            self._engine._add(instance)
        self._pending.clear()

    async def rollback(self) -> None:
        self._pending.clear()

    async def refresh(self, instance: DeclarativeBase) -> None:
        return None

    async def execute(self, statement) -> "_Result":
        rows = statement._evaluate(self._engine)
        return _Result(rows)


class _Result:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalar_one(self) -> Any:
        if len(self._rows) != 1:
            raise ValueError("Expected exactly one row")
        return self._rows[0]

    def scalars(self) -> "_ScalarResult":
        return _ScalarResult(self._rows)


class _ScalarResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def first(self) -> Any:
        return self._rows[0] if self._rows else None


def create_async_engine(url: str, pool_size: int | None = None, pool_timeout: int | None = None) -> AsyncEngine:
    return AsyncEngine(url)
