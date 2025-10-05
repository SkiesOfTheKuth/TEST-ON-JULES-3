"""Minimal asyncio wrapper for sqlite3 used in tests."""

from __future__ import annotations

import asyncio
import sqlite3
from typing import Any, Iterable, Optional, Sequence

__all__ = [
    "connect",
    "Connection",
    "Cursor",
    "Error",
    "DatabaseError",
    "OperationalError",
    "IntegrityError",
    "ProgrammingError",
    "NotSupportedError",
    "PARSE_DECLTYPES",
    "PARSE_COLNAMES",
    "Row",
    "sqlite_version",
    "sqlite_version_info",
]

Error = sqlite3.Error
DatabaseError = sqlite3.DatabaseError
OperationalError = sqlite3.OperationalError
IntegrityError = sqlite3.IntegrityError
ProgrammingError = sqlite3.ProgrammingError
NotSupportedError = sqlite3.NotSupportedError
PARSE_DECLTYPES = sqlite3.PARSE_DECLTYPES
PARSE_COLNAMES = sqlite3.PARSE_COLNAMES
Row = sqlite3.Row
sqlite_version = sqlite3.sqlite_version
sqlite_version_info = sqlite3.sqlite_version_info


async def _to_thread(func, /, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)


class Cursor:
    """Async wrapper for sqlite3.Cursor."""

    def __init__(self, connection: "Connection") -> None:
        self._connection = connection
        self._cursor: Optional[sqlite3.Cursor] = None

    async def _ensure_cursor(self) -> sqlite3.Cursor:
        if self._cursor is None:
            conn = await self._connection._ensure_connection()
            self._cursor = await _to_thread(conn.cursor)
        return self._cursor

    def __await__(self):
        return self._ensure_cursor().__await__()

    async def execute(self, sql: str, parameters: Sequence[Any] | None = None) -> "Cursor":
        cursor = await self._ensure_cursor()
        await _to_thread(cursor.execute, sql, parameters or [])
        return self

    async def executemany(
        self, sql: str, seq_of_parameters: Iterable[Sequence[Any]]
    ) -> "Cursor":
        cursor = await self._ensure_cursor()
        await _to_thread(cursor.executemany, sql, seq_of_parameters)
        return self

    async def fetchone(self) -> Any:
        cursor = await self._ensure_cursor()
        return await _to_thread(cursor.fetchone)

    async def fetchmany(self, size: int | None = None) -> Sequence[Any]:
        cursor = await self._ensure_cursor()
        if size is None:
            size = cursor.arraysize
        return await _to_thread(cursor.fetchmany, size)

    async def fetchall(self) -> Sequence[Any]:
        cursor = await self._ensure_cursor()
        return await _to_thread(cursor.fetchall)

    async def close(self) -> None:
        if self._cursor is not None:
            await _to_thread(self._cursor.close)
            self._cursor = None

    async def __aenter__(self) -> "Cursor":
        await self._ensure_cursor()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    @property
    def rowcount(self) -> int:
        return -1 if self._cursor is None else self._cursor.rowcount

    @property
    def lastrowid(self) -> int | None:
        if self._cursor is None:
            return None
        return self._cursor.lastrowid

    @property
    def description(self):
        if self._cursor is None:
            return None
        return self._cursor.description


class Connection:
    """Async wrapper for sqlite3 connection."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("check_same_thread", False)
        self._connect_args = args
        self._connect_kwargs = kwargs
        self._conn: Optional[sqlite3.Connection] = None
        self.daemon = True
        self._row_factory = kwargs.get("row_factory", None)
        self._isolation_level = kwargs.get("isolation_level")

    async def _ensure_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            conn = await _to_thread(sqlite3.connect, *self._connect_args, **self._connect_kwargs)
            if self._row_factory is not None:
                conn.row_factory = self._row_factory
            if self._isolation_level is not None:
                conn.isolation_level = self._isolation_level
            self._conn = conn
        return self._conn

    def __await__(self):
        async def _await_conn():
            await self._ensure_connection()
            return self

        return _await_conn().__await__()

    async def cursor(self) -> Cursor:
        cursor = Cursor(self)
        await cursor
        return cursor

    async def execute(self, sql: str, parameters: Sequence[Any] | None = None) -> Cursor:
        cursor = await self.cursor()
        await cursor.execute(sql, parameters)
        return cursor

    async def executemany(
        self, sql: str, seq_of_parameters: Iterable[Sequence[Any]]
    ) -> Cursor:
        cursor = await self.cursor()
        await cursor.executemany(sql, seq_of_parameters)
        return cursor

    async def executescript(self, script: str) -> None:
        conn = await self._ensure_connection()
        await _to_thread(conn.executescript, script)

    async def create_function(self, *args: Any, **kwargs: Any) -> None:
        conn = await self._ensure_connection()
        await _to_thread(conn.create_function, *args, **kwargs)

    async def commit(self) -> None:
        conn = await self._ensure_connection()
        await _to_thread(conn.commit)

    async def rollback(self) -> None:
        if self._conn is None:
            return
        await _to_thread(self._conn.rollback)

    async def close(self) -> None:
        if self._conn is None:
            return
        await _to_thread(self._conn.close)
        self._conn = None

    @property
    def row_factory(self):
        return self._row_factory

    @row_factory.setter
    def row_factory(self, factory):
        self._row_factory = factory
        if self._conn is not None:
            self._conn.row_factory = factory

    @property
    def isolation_level(self):
        return self._isolation_level

    @isolation_level.setter
    def isolation_level(self, level):
        self._isolation_level = level
        if self._conn is not None:
            self._conn.isolation_level = level

    async def __aenter__(self) -> "Connection":
        await self._ensure_connection()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if exc_type:
            await self.rollback()
        else:
            await self.commit()
        await self.close()


def connect(*args: Any, **kwargs: Any) -> Connection:
    return Connection(*args, **kwargs)
