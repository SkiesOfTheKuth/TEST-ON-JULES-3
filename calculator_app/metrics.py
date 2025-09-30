"""Lightweight metrics instrumentation without external dependencies."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, Tuple


_HISTOGRAM_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0)


class MetricsStore:
    """In-memory metrics store suitable for single-process deployments."""

    def __init__(self) -> None:
        self._request_counts: Dict[Tuple[str, str, str], int] = defaultdict(int)
        self._request_latency: Dict[Tuple[str, str], dict[str, object]] = defaultdict(
            _histogram_template
        )
        self._evaluations: Dict[Tuple[str], int] = defaultdict(int)

    def record_request(self, method: str, endpoint: str, status: str) -> None:
        self._request_counts[(method, endpoint, status)] += 1

    def record_latency(self, method: str, endpoint: str, seconds: float) -> None:
        data = self._request_latency[(method, endpoint)]
        bucket_counts: list[int] = data["bucket_counts"]  # type: ignore[assignment]
        count: int = data["count"]  # type: ignore[assignment]
        total_sum: float = data["sum"]  # type: ignore[assignment]

        for idx, upper in enumerate(_HISTOGRAM_BUCKETS):
            if seconds <= upper:
                bucket_counts[idx] += 1
                break
        else:
            bucket_counts[-1] += 1

        data["count"] = count + 1
        data["sum"] = total_sum + seconds

    def record_evaluation(self, outcome: str) -> None:
        self._evaluations[(outcome,)] += 1

    def render(self) -> bytes:
        lines: list[str] = []
        lines.extend(_render_counter(
            "calculator_http_requests_total",
            "Total HTTP requests processed by method, endpoint, and status",
            ("method", "endpoint", "status"),
            self._request_counts.items(),
        ))
        lines.extend(_render_histogram(
            "calculator_http_request_duration_seconds",
            "HTTP request duration in seconds",
            ("method", "endpoint"),
            self._request_latency.items(),
        ))
        lines.extend(_render_counter(
            "calculator_evaluations_total",
            "Count of calculator evaluations by outcome",
            ("outcome",),
            self._evaluations.items(),
        ))
        return ("\n".join(lines) + "\n").encode("utf-8")


def _histogram_template() -> dict[str, object]:
    return {
        "bucket_counts": [0 for _ in range(len(_HISTOGRAM_BUCKETS) + 1)],
        "count": 0,
        "sum": 0.0,
    }


def _render_counter(
    name: str,
    description: str,
    label_names: Tuple[str, ...],
    samples: Iterable[Tuple[Tuple[str, ...], int]],
) -> list[str]:
    lines = [f"# HELP {name} {description}", f"# TYPE {name} counter"]
    for labels, value in sorted(samples):
        formatted_labels = _format_labels(label_names, labels)
        lines.append(f"{name}{formatted_labels} {float(value)}")
    return lines


def _render_histogram(
    name: str,
    description: str,
    label_names: Tuple[str, ...],
    samples: Iterable[Tuple[Tuple[str, ...], dict[str, object]]],
) -> list[str]:
    lines = [f"# HELP {name} {description}", f"# TYPE {name} histogram"]
    for labels, data in sorted(samples):
        bucket_counts: list[int] = data["bucket_counts"]  # type: ignore[assignment]
        count: int = data["count"]  # type: ignore[assignment]
        total_sum: float = data["sum"]  # type: ignore[assignment]

        cumulative = 0
        for idx, upper in enumerate(_HISTOGRAM_BUCKETS):
            cumulative += bucket_counts[idx]
            bucket_labels = _format_labels(
                label_names + ("le",), labels + (f"{upper:g}",)
            )
            lines.append(f"{name}_bucket{bucket_labels} {float(cumulative)}")

        cumulative += bucket_counts[-1]
        bucket_labels = _format_labels(label_names + ("le",), labels + ("+Inf",))
        lines.append(f"{name}_bucket{bucket_labels} {float(cumulative)}")

        count_labels = _format_labels(label_names, labels)
        lines.append(f"{name}_count{count_labels} {float(count)}")
        lines.append(f"{name}_sum{count_labels} {float(total_sum)}")

    return lines


def _format_labels(label_names: Tuple[str, ...], values: Tuple[str, ...]) -> str:
    if not label_names:
        return ""

    parts = [f'{key}="{value}"' for key, value in zip(label_names, values)]
    return "{" + ",".join(parts) + "}"
