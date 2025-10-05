"""Minimal SQLAlchemy compatibility layer for unit tests."""

from __future__ import annotations

from typing import Any, Callable, Iterable, List, Sequence

__all__ = [
    "Boolean",
    "DateTime",
    "Float",
    "ForeignKey",
    "Index",
    "Integer",
    "String",
    "Text",
    "UniqueConstraint",
    "select",
    "func",
]


class _Type:
    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"Type({self.name})"

    def __call__(self, *args, **kwargs):  # noqa: D401, ARG002 - compatibility shim
        return self


Boolean = _Type("BOOLEAN")
DateTime = _Type("DATETIME")
Float = _Type("FLOAT")
Integer = _Type("INTEGER")
String = _Type("STRING")
Text = _Type("TEXT")


def ForeignKey(target: str, ondelete: str | None = None) -> str:
    return target


class Index:
    def __init__(self, name: str, *columns: Sequence[str]) -> None:
        self.name = name
        self.columns = columns


class UniqueConstraint:
    def __init__(self, *columns: Sequence[str], name: str | None = None) -> None:
        self.columns = list(columns)
        self.name = name


class _FuncNamespace:
    def count(self) -> "_Function":
        return _Function("count")


class _Function:
    def __init__(self, name: str) -> None:
        self.name = name


func = _FuncNamespace()


class _Condition:
    def __init__(self, getter: Callable[[Any], Any], expected: Any) -> None:
        self.getter = getter
        self.expected = expected

    def evaluate(self, obj: Any) -> bool:
        return self.getter(obj) == self.expected


class Select:
    def __init__(self, entity: Any) -> None:
        self._entity = entity
        self._from_entity = None
        self._conditions: list[_Condition] = []

    def select_from(self, entity: Any) -> "Select":
        self._from_entity = entity
        return self

    def where(self, condition: _Condition) -> "Select":
        self._conditions.append(condition)
        return self

    def with_for_update(self) -> "Select":
        return self

    @property
    def entity(self) -> Any:
        return self._entity

    @property
    def from_entity(self) -> Any:
        return self._from_entity

    @property
    def conditions(self) -> Sequence[_Condition]:
        return list(self._conditions)


def select(entity: Any) -> Select:
    return Select(entity)


class Result:
    def __init__(self, *, scalar: Any | None = None, rows: Iterable[Any] | None = None) -> None:
        self._scalar = scalar
        self._rows = list(rows or [])

    def scalar_one(self) -> Any:
        if self._scalar is None:
            raise ValueError("No scalar value available")
        return self._scalar

    def scalars(self) -> "ScalarResult":
        return ScalarResult(self._rows)


class ScalarResult:
    def __init__(self, rows: Iterable[Any]) -> None:
        self._rows = list(rows)

    def first(self) -> Any | None:
        return self._rows[0] if self._rows else None


# runtime helpers used by async session implementation
class _SelectEvaluator:
    def __init__(self, statement: Select, storage: "_Storage") -> None:
        self.statement = statement
        self.storage = storage

    def execute(self) -> Result:
        entity = self.statement.entity
        table = self.statement.from_entity or entity
        if table is None:
            return Result(rows=[])
        records = list(self.storage.get(table))
        for condition in self.statement.conditions:
            records = [row for row in records if condition.evaluate(row)]
        if isinstance(entity, _Function) and entity.name == "count":
            return Result(scalar=len(records))
        return Result(rows=records)


class _Storage:
    def __init__(self) -> None:
        self.tables: dict[str, list[Any]] = {}

    def ensure_table(self, model: Any) -> None:
        name = getattr(model, "__tablename__", model.__name__)
        self.tables.setdefault(name, [])

    def add(self, obj: Any) -> None:
        name = getattr(obj.__class__, "__tablename__", obj.__class__.__name__)
        self.tables.setdefault(name, []).append(obj)

    def get(self, model: Any) -> List[Any]:
        name = getattr(model, "__tablename__", model.__name__)
        return list(self.tables.get(name, []))


__storage = _Storage()


def _evaluate_select(statement: Select) -> Result:
    evaluator = _SelectEvaluator(statement, __storage)
    return evaluator.execute()


def _register_model(model: Any) -> None:
    __storage.ensure_table(model)


def _store_object(obj: Any) -> None:
    __storage.add(obj)


def _get_storage() -> _Storage:
    return __storage


