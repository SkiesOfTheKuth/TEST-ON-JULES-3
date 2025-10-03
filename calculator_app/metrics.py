"""In-process metrics registry with optional multiprocess aggregation."""

from __future__ import annotations

import atexit
import json
import os
import threading
import time
from collections import defaultdict
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import DefaultDict, Dict, Iterable, Tuple


_HISTOGRAM_BUCKETS = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.0,
)

_METRICS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


class MetricsStore:
    """Thread-safe metrics collector that exports Prometheus text format."""

    def __init__(self, multiprocess_dir: str | None = None) -> None:
        self._lock = threading.Lock()
        self._request_counts: DefaultDict[Tuple[str, str, str], int] = defaultdict(int)
        self._request_latency: DefaultDict[Tuple[str, str], Dict[str, object]] = defaultdict(
            _histogram_template
        )
        self._evaluations: DefaultDict[Tuple[str], int] = defaultdict(int)

        self._multiprocess_dir = Path(multiprocess_dir) if multiprocess_dir else None
        self._process_file: Path | None = None

        if self._multiprocess_dir is not None:
            self._multiprocess_dir.mkdir(parents=True, exist_ok=True)
            self._process_file = self._multiprocess_dir / f"metrics-{os.getpid()}.json"
            atexit.register(self._cleanup_process_file)
            with self._lock:
                self._persist_state_locked()

    @property
    def content_type(self) -> str:
        return _METRICS_CONTENT_TYPE

    def record_request(self, method: str, endpoint: str, status: str) -> None:
        with self._lock:
            self._request_counts[(method, endpoint, status)] += 1
            self._persist_state_locked()

    def record_latency(self, method: str, endpoint: str, seconds: float) -> None:
        with self._lock:
            state = self._request_latency[(method, endpoint)]
            bucket_counts: list[int] = state["bucket_counts"]  # type: ignore[assignment]
            count: int = state["count"]  # type: ignore[assignment]
            total_sum: float = state["sum"]  # type: ignore[assignment]

            for idx, upper in enumerate(_HISTOGRAM_BUCKETS):
                if seconds <= upper:
                    bucket_counts[idx] += 1
                    break
            else:
                bucket_counts[-1] += 1

            state["count"] = count + 1
            state["sum"] = total_sum + seconds
            self._persist_state_locked()

    def record_evaluation(self, outcome: str) -> None:
        with self._lock:
            self._evaluations[(outcome,)] += 1
            self._persist_state_locked()

    def render(self) -> bytes:
        with self._lock:
            local_counts = dict(self._request_counts)
            local_latency = {key: _copy_histogram(value) for key, value in self._request_latency.items()}
            local_evaluations = dict(self._evaluations)

        merged_counts, merged_latency, merged_evaluations = self._merge_external(
            local_counts, local_latency, local_evaluations
        )

        lines: list[str] = []
        lines.extend(
            _render_counter(
                "calculator_http_requests_total",
                "Total HTTP requests processed by method, endpoint, and status",
                ("method", "endpoint", "status"),
                merged_counts.items(),
            )
        )
        lines.extend(
            _render_histogram(
                "calculator_http_request_duration_seconds",
                "HTTP request duration in seconds",
                ("method", "endpoint"),
                merged_latency.items(),
            )
        )
        lines.extend(
            _render_counter(
                "calculator_evaluations_total",
                "Count of calculator evaluations by outcome",
                ("outcome",),
                merged_evaluations.items(),
            )
        )
        timestamp = int(time.time())
        lines.append(f"calculator_metrics_last_scrape_timestamp {float(timestamp)}")
        return ("\n".join(lines) + "\n").encode("utf-8")

    # Internal helpers -------------------------------------------------

    def _persist_state_locked(self) -> None:
        if self._process_file is None:
            return

        payload = {
            "request_counts": [
                {"labels": list(labels), "value": value}
                for labels, value in self._request_counts.items()
            ],
            "request_latency": [
                {
                    "labels": list(labels),
                    "bucket_counts": state["bucket_counts"],
                    "count": state["count"],
                    "sum": state["sum"],
                }
                for labels, state in self._request_latency.items()
            ],
            "evaluations": [
                {"labels": list(labels), "value": value}
                for labels, value in self._evaluations.items()
            ],
        }

        tmp = NamedTemporaryFile("w", delete=False, dir=str(self._multiprocess_dir))
        try:
            json.dump(payload, tmp)
            tmp.flush()
            os.fsync(tmp.fileno())
        finally:
            tmp.close()

        Path(tmp.name).replace(self._process_file)

    def _merge_external(
        self,
        local_counts: Dict[Tuple[str, str, str], int],
        local_latency: Dict[Tuple[str, str], Dict[str, object]],
        local_evaluations: Dict[Tuple[str], int],
    ) -> tuple[
        Dict[Tuple[str, str, str], int],
        Dict[Tuple[str, str], Dict[str, object]],
        Dict[Tuple[str], int],
    ]:
        if self._multiprocess_dir is None:
            return local_counts, local_latency, local_evaluations

        aggregated_counts: Dict[Tuple[str, str, str], int] = defaultdict(int)
        aggregated_latency: Dict[Tuple[str, str], Dict[str, object]] = defaultdict(
            _histogram_template
        )
        aggregated_evaluations: Dict[Tuple[str], int] = defaultdict(int)

        files = list(self._multiprocess_dir.glob("metrics-*.json"))
        if not files:
            for labels, value in local_counts.items():
                aggregated_counts[labels] += value
            for labels, state in local_latency.items():
                aggregated_latency[labels] = _copy_histogram(state)
            for labels, value in local_evaluations.items():
                aggregated_evaluations[labels] += value
            return aggregated_counts, aggregated_latency, aggregated_evaluations

        for file_path in files:
            try:
                with file_path.open("r") as handle:
                    data = json.load(handle)
            except (OSError, json.JSONDecodeError):
                continue

            for sample in data.get("request_counts", []):
                labels = tuple(sample["labels"])
                aggregated_counts[labels] += int(sample["value"])
            for sample in data.get("request_latency", []):
                labels = tuple(sample["labels"])
                state = aggregated_latency[labels]
                bucket_counts: list[int] = state["bucket_counts"]  # type: ignore[assignment]
                local_counts = sample.get("bucket_counts", [])
                for idx, value in enumerate(local_counts):
                    if idx < len(bucket_counts):
                        bucket_counts[idx] += int(value)
                state["count"] = state.get("count", 0) + int(sample.get("count", 0))
                state["sum"] = state.get("sum", 0.0) + float(sample.get("sum", 0.0))
            for sample in data.get("evaluations", []):
                labels = tuple(sample["labels"])
                aggregated_evaluations[labels] += int(sample["value"])

        return aggregated_counts, aggregated_latency, aggregated_evaluations

    def _cleanup_process_file(self) -> None:
        if self._process_file is not None:
            try:
                self._process_file.unlink(missing_ok=True)
            except OSError:
                pass


def _histogram_template() -> Dict[str, object]:
    return {
        "bucket_counts": [0 for _ in range(len(_HISTOGRAM_BUCKETS) + 1)],
        "count": 0,
        "sum": 0.0,
    }


def _copy_histogram(state: Dict[str, object]) -> Dict[str, object]:
    return {
        "bucket_counts": list(state["bucket_counts"]),
        "count": int(state["count"]),
        "sum": float(state["sum"]),
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
    if len(lines) == 2:
        lines.append(f"{name} 0.0")
    return lines


def _render_histogram(
    name: str,
    description: str,
    label_names: Tuple[str, ...],
    samples: Iterable[Tuple[Tuple[str, ...], Dict[str, object]]],
) -> list[str]:
    lines = [f"# HELP {name} {description}", f"# TYPE {name} histogram"]
    any_samples = False
    for labels, data in sorted(samples):
        any_samples = True
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

    if not any_samples:
        lines.extend(
            [
                f"{name}_bucket{{le=\"{upper:g}\"}} 0.0" for upper in _HISTOGRAM_BUCKETS
            ]
        )
        lines.append(f"{name}_bucket{{le=\"+Inf\"}} 0.0")
        lines.append(f"{name}_count 0.0")
        lines.append(f"{name}_sum 0.0")

    return lines


def _format_labels(label_names: Tuple[str, ...], values: Tuple[str, ...]) -> str:
    if not label_names:
        return ""
    parts = [f'{key}="{value}"' for key, value in zip(label_names, values)]
    return "{" + ",".join(parts) + "}"


__all__ = ["MetricsStore", "_METRICS_CONTENT_TYPE"]
