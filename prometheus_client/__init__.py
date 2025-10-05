"""Minimal Prometheus client shim for the unit tests."""

from __future__ import annotations

from typing import Any, Dict, Tuple


class _MetricHandle:
    def __init__(self, storage: Dict[Tuple[Any, ...], float], key: Tuple[Any, ...]) -> None:
        self._storage = storage
        self._key = key

    def inc(self, amount: float = 1.0) -> None:
        self._storage[self._key] = self._storage.get(self._key, 0.0) + amount

    def dec(self, amount: float = 1.0) -> None:
        self._storage[self._key] = self._storage.get(self._key, 0.0) - amount

    def set(self, value: float) -> None:
        self._storage[self._key] = value

    def observe(self, value: float) -> None:
        self.inc(value)


class _Collector:
    def __init__(
        self,
        name: str,
        documentation: str,
        *,
        labelnames: Tuple[str, ...] = (),
        namespace: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.original_name = name
        self.namespace = namespace
        full_name = f"{namespace}_{name}" if namespace else name
        if full_name in REGISTRY._names_to_collectors:
            raise ValueError(f"Collector {full_name} already registered")
        self.name = full_name
        self.documentation = documentation
        self.labelnames = tuple(labelnames)
        self._values: Dict[Tuple[Any, ...], float] = {}
        REGISTRY._names_to_collectors[full_name] = self

    def labels(self, *args: Any, **kwargs: Any) -> _MetricHandle:
        if args and kwargs:
            raise TypeError("Provide labels as positional or keyword arguments, not both")
        if args:
            key = tuple(args)
        else:
            key = tuple(kwargs.get(name) for name in self.labelnames)
        if len(key) != len(self.labelnames):
            raise ValueError("Incorrect number of label values")
        self._values.setdefault(key, 0.0)
        return _MetricHandle(self._values, key)

    def _default_handle(self) -> _MetricHandle:
        if self.labelnames:
            raise ValueError("Metric requires label values")
        self._values.setdefault(tuple(), 0.0)
        return _MetricHandle(self._values, tuple())

    def inc(self, amount: float = 1.0) -> None:
        self._default_handle().inc(amount)

    def dec(self, amount: float = 1.0) -> None:
        self._default_handle().dec(amount)

    def set(self, value: float) -> None:
        self._default_handle().set(value)

    def observe(self, value: float) -> None:
        self._default_handle().observe(value)

    @property
    def samples(self):  # pragma: no cover - compatibility shim
        return [
            _Sample(self.name, dict(zip(self.labelnames, labels)), value)
            for labels, value in self._values.items()
        ]

    def collect(self):  # pragma: no cover - compatibility shim
        return [self]


class _Sample:
    def __init__(self, name: str, labels: Dict[str, Any], value: float) -> None:
        self.name = name
        self.labels = labels
        self.value = value


class Counter(_Collector):
    pass


class Gauge(_Collector):
    pass


class Histogram(_Collector):
    pass


class _Registry:
    def __init__(self) -> None:
        self._names_to_collectors: Dict[str, _Collector] = {}

    def collect(self):  # pragma: no cover - compatibility shim
        return self._names_to_collectors.values()


class CollectorRegistry(_Registry):
    """Minimal CollectorRegistry implementation for local tests."""

    pass


REGISTRY = _Registry()


def generate_latest(registry: _Registry = REGISTRY) -> bytes:
    lines: list[str] = []
    for collector in registry.collect():
        lines.append(f"# HELP {collector.name} {collector.documentation}")
        metric_type = "counter"
        if isinstance(collector, Gauge):
            metric_type = "gauge"
        elif isinstance(collector, Histogram):
            metric_type = "histogram"
        lines.append(f"# TYPE {collector.name} {metric_type}")
        for labels, value in collector._values.items():
            if collector.labelnames:
                label_parts = [f'{name}="{label}"' for name, label in zip(collector.labelnames, labels)]
                label_str = "{" + ",".join(label_parts) + "}"
            else:
                label_str = ""
            lines.append(f"{collector.name}{label_str} {value}")
    return ("\n".join(lines) + "\n").encode("utf-8")


__all__ = [
    "CollectorRegistry",
    "Counter",
    "Gauge",
    "Histogram",
    "REGISTRY",
    "generate_latest",
]
