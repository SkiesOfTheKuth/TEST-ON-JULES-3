"""Lightweight subset of Pydantic for local testing."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, get_origin, get_type_hints


@dataclass
class FieldInfo:
    default: Any = None
    default_factory: Callable[[], Any] | None = None


class ConfigDict(dict):
    pass


class BaseModel:
    model_config: ConfigDict = ConfigDict()

    def __init__(self, **data: Any) -> None:
        fields = self.__class__._collect_fields()
        annotations = get_type_hints(self.__class__)
        for name, info in fields.items():
            if name in data:
                value = self._coerce_value(name, data[name], annotations.get(name))
            else:
                value = self.__class__._get_default(name, info)
                if value is _Missing:
                    raise TypeError(f"Missing required field: {name}")
            setattr(self, name, value)

    @classmethod
    def _collect_fields(cls) -> Dict[str, Any]:
        annotations = cls._annotations()
        fields: Dict[str, Any] = {}
        for name in annotations:
            value = getattr(cls, name, _Missing)
            fields[name] = value
        return fields

    @classmethod
    def _get_default(cls, name: str, value: Any) -> Any:
        if isinstance(value, FieldInfo):
            if value.default_factory is not None:
                return value.default_factory()
            if value.default is _Missing:
                return _Missing
            return value.default
        if value is _Missing:
            return _Missing
        if callable(value) and not isinstance(value, type):
            try:
                return value()
            except TypeError:
                return value
        return value

    def _coerce_value(self, name: str, value: Any, annotation: Any) -> Any:
        if isinstance(value, dict) and isinstance(annotation, type) and issubclass(annotation, BaseModel):
            return annotation(**value)
        origin = get_origin(annotation)
        if origin is dict and isinstance(value, dict):
            return dict(value)
        if origin in {list, tuple} and isinstance(value, origin):
            return origin(value)
        return value

    @classmethod
    def _annotations(cls) -> Dict[str, Any]:
        hints: Dict[str, Any] = {}
        for base in reversed(cls.__mro__):
            if issubclass(base, BaseModel):
                hints.update(get_type_hints(base))
        return hints

    @classmethod
    def model_validate(cls, value: Any, *, from_attributes: bool = False) -> "BaseModel":
        if isinstance(value, cls):
            return value
        if from_attributes:
            data = {}
            for name in cls._annotations():
                if hasattr(value, name):
                    data[name] = getattr(value, name)
            return cls(**data)
        if isinstance(value, Mapping):
            return cls(**value)
        raise TypeError("Unsupported value for model_validate")

    def model_dump(self, mode: str = "python") -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        for name in self.__class__._annotations():
            value = getattr(self, name)
            payload[name] = _convert_value(value, mode=mode)
        return payload

    def dict(self) -> Dict[str, Any]:  # pragma: no cover - compatibility
        return self.model_dump()


class _MissingType:
    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return "MISSING"


_Missing = _MissingType()


def Field(
    default: Any = _Missing,
    *,
    default_factory: Callable[[], Any] | None = None,
    **kwargs: Any,
) -> FieldInfo:
    return FieldInfo(default=default, default_factory=default_factory)


def _convert_value(value: Any, *, mode: str) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode=mode)
    if mode == "json":
        if isinstance(value, dt.datetime):
            return value.isoformat()
        if isinstance(value, dt.date):
            return value.isoformat()
    if isinstance(value, list):
        return [_convert_value(item, mode=mode) for item in value]
    if isinstance(value, dict):
        return {k: _convert_value(v, mode=mode) for k, v in value.items()}
    return value


__all__ = ["BaseModel", "ConfigDict", "Field"]
