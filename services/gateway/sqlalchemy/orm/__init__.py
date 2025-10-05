"""Very small subset of SQLAlchemy's ORM API for tests."""

from __future__ import annotations

from typing import Any, Callable, Dict

__all__ = ["DeclarativeBase", "Mapped", "mapped_column"]


class _MappedColumn:
    def __init__(
        self,
        type_: Any = None,
        *extra: Any,
        primary_key: bool = False,
        default: Any = None,
        nullable: bool = True,
        autoincrement: bool = False,
        unique: bool = False,
    ) -> None:
        self.type_ = type_
        self.extra = extra
        self.primary_key = primary_key
        self.default = default
        self.nullable = nullable
        self.autoincrement = autoincrement
        self.unique = unique
        self.name: str | None = None

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name
        owner.__columns__[name] = self  # type: ignore[attr-defined]

    def default_value(self) -> Any:
        if callable(self.default):
            return self.default()
        return self.default

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        if instance is None:
            return self
        return instance.__dict__.get(self.name, self.default_value())

    def __set__(self, instance: Any, value: Any) -> None:
        instance.__dict__[self.name] = value  # type: ignore[index]

    def __eq__(self, other: Any) -> Callable[[Any], bool]:
        return lambda obj: getattr(obj, self.name) == other  # type: ignore[arg-type]


class _Metadata:
    def __init__(self) -> None:
        self._models: list[type] = []

    def _register(self, model: type) -> None:
        if not getattr(model, "__tablename__", None):
            return
        if model not in self._models:
            self._models.append(model)

    def create_all(self, engine) -> None:
        for model in self._models:
            engine._ensure_table(model)


class DeclarativeMeta(type):
    def __new__(mcls, name: str, bases: tuple[type, ...], namespace: Dict[str, Any]):
        inherited: Dict[str, _MappedColumn] = {}
        metadata = None
        for base in bases:
            metadata = getattr(base, "metadata", None) if metadata is None else metadata
            inherited.update(getattr(base, "__columns__", {}))
        columns = {
            key: value for key, value in namespace.items() if isinstance(value, _MappedColumn)
        }
        cls = super().__new__(mcls, name, bases, namespace)
        cls.__columns__ = {**inherited, **columns}  # type: ignore[attr-defined]
        if metadata is None:
            metadata = _Metadata()
        cls.metadata = metadata  # type: ignore[attr-defined]
        metadata._register(cls)
        for key, column in columns.items():
            column.__set_name__(cls, key)
        return cls


class DeclarativeBase(metaclass=DeclarativeMeta):
    metadata = _Metadata()

    def __init__(self, **kwargs: Any) -> None:
        for name, column in self.__columns__.items():  # type: ignore[attr-defined]
            if name in kwargs:
                value = kwargs.pop(name)
            else:
                value = column.default_value()
            setattr(self, name, value)
        if kwargs:
            raise TypeError(f"Unknown columns: {', '.join(sorted(kwargs))}")


def mapped_column(*args: Any, **kwargs: Any) -> _MappedColumn:
    return _MappedColumn(*args, **kwargs)


Mapped = Any
