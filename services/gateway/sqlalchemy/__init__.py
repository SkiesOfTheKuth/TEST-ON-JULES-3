"""Extremely small SQLAlchemy compatibility layer for offline tests."""

from __future__ import annotations

from typing import Any, Callable, Iterable, List, Optional

from .ext.asyncio import AsyncEngine
from .orm import DeclarativeBase
from .types import JSON, TypeDecorator

__all__ = [
    "Boolean",
    "DateTime",
    "Float",
    "ForeignKey",
    "Index",
    "Integer",
    "String",
    "Text",
    "JSON",
    "TypeDecorator",
    "func",
    "select",
]


class _SimpleType:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass


Boolean = DateTime = Float = Integer = String = Text = _SimpleType


def ForeignKey(column: str, ondelete: str | None = None) -> tuple[str, Optional[str]]:
    return (column, ondelete)


class Index:
    def __init__(self, name: str, *columns: str) -> None:
        self.name = name
        self.columns = columns


class _Count:
    def evaluate(self, rows: Iterable[Any]) -> int:
        return len(list(rows))


class _Func:
    def count(self) -> _Count:
        return _Count()


func = _Func()


class Select:
    def __init__(self, target: Any) -> None:
        self.target = target
        self._model = target if isinstance(target, type) and hasattr(target, "__tablename__") else None
        self._conditions: list[Callable[[Any], bool]] = []

    def where(self, predicate: Callable[[Any], bool]) -> "Select":
        self._conditions.append(predicate)
        return self

    def select_from(self, model: type[DeclarativeBase]) -> "Select":
        self._model = model
        return self

    def with_for_update(self) -> "Select":  # pragma: no cover - for API compatibility
        return self

    def _evaluate(self, engine: AsyncEngine) -> List[Any]:
        if self._model is None:
            raise ValueError("No model specified for select statement")
        rows = engine._rows(self._model)
        for predicate in self._conditions:
            rows = [row for row in rows if predicate(row)]
        if isinstance(self.target, _Count):
            return [self.target.evaluate(rows)]
        return rows


def select(target: Any) -> Select:
    return Select(target)
