"""Prometheus client stubs used for unit tests."""

from __future__ import annotations

from typing import Any, Dict, Tuple

__all__ = ["Counter", "Gauge", "Histogram", "REGISTRY"]


class _Collector:
    def __init__(self, name: str, doc: str, labelnames: Tuple[str, ...], namespace: str | None = None, buckets=None):
        self._bare_name = name
        self._namespace = namespace
        self._name = name if namespace in (None, "") else f"{namespace}_{name}"
        self._doc = doc
        self._labelnames = labelnames
        self._values: Dict[Tuple[Any, ...], Any] = {}
        self._buckets = buckets
        REGISTRY._names_to_collectors[self._name] = self

    def labels(self, *args: Any, **kwargs: Any) -> "_BoundCollector":
        if kwargs:
            items = tuple(sorted(kwargs.items()))
        else:
            items = ()
        key = (args, items)
        if key not in self._values:
            self._values[key] = 0
        return _BoundCollector(self, key)


class _BoundCollector:
    def __init__(self, collector: _Collector, key: Tuple[Any, ...]) -> None:
        self._collector = collector
        self._key = key

    def inc(self, amount: float = 1.0) -> None:
        self._collector._values[self._key] = self._collector._values.get(self._key, 0) + amount

    def dec(self, amount: float = 1.0) -> None:
        self._collector._values[self._key] = self._collector._values.get(self._key, 0) - amount

    def observe(self, value: float) -> None:
        self.inc(value)

    def set(self, value: float) -> None:
        self._collector._values[self._key] = value


class Counter(_Collector):
    pass


class Gauge(_Collector):
    pass


class Histogram(_Collector):
    pass


class _Registry:
    def __init__(self) -> None:
        self._names_to_collectors: Dict[str, _Collector] = {}


REGISTRY = _Registry()
