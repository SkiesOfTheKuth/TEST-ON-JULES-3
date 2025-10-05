"""Lightweight stand-in for Pydantic used in offline tests."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, MutableMapping, Sequence

__all__ = ["BaseModel", "Field", "ConfigDict", "FieldInfo"]


class FieldInfo:
    def __init__(self, default: Any = ..., *, default_factory=None, **kwargs: Any) -> None:
        self.default = default
        self.default_factory = default_factory
        self.metadata = kwargs


def Field(default: Any = ..., *, default_factory=None, **kwargs: Any) -> FieldInfo:
    return FieldInfo(default, default_factory=default_factory, **kwargs)


class _FieldDef:
    def __init__(self, annotation: Any, default: Any, default_factory=None) -> None:
        self.annotation = annotation
        self.default = default
        self.default_factory = default_factory

    def get_default(self) -> Any:
        if self.default_factory is not None:
            return self.default_factory()
        if self.default is ...:
            raise TypeError("Missing required field")
        return self.default


class BaseModelMeta(type):
    def __new__(mcls, name: str, bases: tuple[type, ...], namespace: Dict[str, Any]):
        annotations = dict(namespace.get("__annotations__", {}))
        fields: Dict[str, _FieldDef] = {}
        for base in reversed(bases):
            inherited = {
                key: value for key, value in getattr(base, "__fields__", {}).items() if key != "model_config"
            }
            fields.update(inherited)
        new_namespace = {key: value for key, value in namespace.items() if key not in annotations}
        for key, annotation in annotations.items():
            if key == "model_config":
                continue
            default = namespace.get(key, ...)
            if isinstance(default, FieldInfo):
                field = _FieldDef(annotation, default.default, default.default_factory)
            else:
                field = _FieldDef(annotation, default)
            fields[key] = field
        cls = super().__new__(mcls, name, bases, new_namespace)
        cls.__fields__ = fields  # type: ignore[attr-defined]
        return cls


class BaseModel(metaclass=BaseModelMeta):
    model_config: Dict[str, Any] = {}

    def __init__(self, **data: Any) -> None:
        unknown = set(data.keys()) - set(self.__fields__.keys())
        if unknown:
            raise TypeError(f"Unexpected fields: {', '.join(sorted(unknown))}")
        for name, field in self.__fields__.items():  # type: ignore[attr-defined]
            if name in data:
                value = data[name]
            else:
                value = field.get_default()
            setattr(self, name, value)

    def model_dump(self, *, mode: str | None = None) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for name in self.__fields__:  # type: ignore[attr-defined]
            value = getattr(self, name)
            if mode == "json":
                value = _to_json(value)
            result[name] = value
        return result

    @classmethod
    def model_validate(cls, obj: Any, *, from_attributes: bool = False) -> "BaseModel":
        if isinstance(obj, cls):
            return obj
        values: Dict[str, Any] = {}
        if isinstance(obj, MutableMapping):
            for name in cls.__fields__:  # type: ignore[attr-defined]
                values[name] = obj.get(name)
        else:
            for name in cls.__fields__:  # type: ignore[attr-defined]
                if from_attributes:
                    try:
                        values[name] = getattr(obj, name)
                    except AttributeError:
                        values[name] = cls.__fields__[name].get_default()
                else:
                    values[name] = obj[name]
        return cls(**values)


def ConfigDict(**kwargs: Any) -> Dict[str, Any]:
    return dict(kwargs)


def _to_json(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, MutableMapping):
        return {k: _to_json(v) for k, v in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_to_json(item) for item in value]
    return value
