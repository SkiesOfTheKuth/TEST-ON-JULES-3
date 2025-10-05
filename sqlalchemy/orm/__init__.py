"""Minimal ORM primitives required by the tests."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from .. import _Condition, _register_model

Mapped = Any


class Column:
    def __init__(
        self,
        type_: Any | None = None,
        *,
        default: Any | None = None,
        default_factory: Callable[[], Any] | None = None,
        nullable: bool = True,
        primary_key: bool = False,
        **kwargs,
    ) -> None:
        self.type = type_
        self.default = default
        self.default_factory = default_factory
        self.nullable = nullable
        self.primary_key = primary_key
        self.name: str | None = None

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        if instance is None:
            return self
        return instance.__dict__.get(self.name, None)

    def __set__(self, instance: Any, value: Any) -> None:
        instance.__dict__[self.name] = value

    def __eq__(self, other: Any) -> _Condition:  # type: ignore[override]
        if self.name is None:
            raise AttributeError("Column is not bound to a name")
        return _Condition(lambda obj: getattr(obj, self.name), other)

    def default_value(self) -> Any:
        if self.default_factory is not None:
            return self.default_factory()
        if callable(self.default):
            try:
                return self.default()
            except TypeError:
                return self.default
        return self.default


class _Metadata:
    def __init__(self) -> None:
        self._models: List[type] = []

    def _register(self, model: type) -> None:
        if model not in self._models:
            self._models.append(model)
            _register_model(model)

    def create_all(self, engine: Any) -> None:  # noqa: ARG002 - compatibility shim
        for model in self._models:
            _register_model(model)


class DeclarativeMeta(type):
    def __new__(mcls, name: str, bases: tuple[type, ...], attrs: Dict[str, Any]):
        columns = {key: value for key, value in attrs.items() if isinstance(value, Column)}
        cls = super().__new__(mcls, name, bases, attrs)
        setattr(cls, "__columns__", columns)
        if not hasattr(cls, "metadata"):
            cls.metadata = _Metadata()
        if name != "DeclarativeBase":
            if not hasattr(cls, "__tablename__"):
                cls.__tablename__ = name.lower()
            cls.metadata._register(cls)
        return cls


class DeclarativeBase(metaclass=DeclarativeMeta):
    metadata = _Metadata()

    def __init__(self, **kwargs: Any) -> None:
        for name, column in getattr(self, "__columns__", {}).items():
            if name in kwargs:
                value = kwargs[name]
            else:
                value = column.default_value()
            setattr(self, name, value)


def mapped_column(
    type_: Any | None = None,
    *_,
    default: Any | None = None,
    default_factory: Callable[[], Any] | None = None,
    nullable: bool = True,
    primary_key: bool = False,
    autoincrement: bool = False,  # noqa: ARG001 - compatibility shim
    **kwargs,
) -> Column:
    return Column(
        type_,
        default=default,
        default_factory=default_factory,
        nullable=nullable,
        primary_key=primary_key,
        **kwargs,
    )


__all__ = ["DeclarativeBase", "Mapped", "mapped_column"]
