"""Implementation of the evaluator RPC service."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Dict, Iterable, List

from services.common.grpc import grpc
from opentelemetry import trace
from opentelemetry.propagate import extract
from opentelemetry.trace import SpanKind, Status, StatusCode

from calculator_core import (
    ComplexityBudget,
    ComplexityMetrics,
    ExpressionValidator,
    SandboxConfig,
    SandboxRunner,
    ValidationError,
)
from services.protos import evaluator_pb2, evaluator_pb2_grpc

from .allowlist import AllowListError, AllowListManager
from .config import EvaluatorSettings
from .observability import (
    decrement_inflight,
    increment_inflight,
    record_evaluation,
    record_sandbox_restart,
    reset_request_id,
    set_request_id,
)

logger = logging.getLogger(__name__)

tracer = trace.get_tracer(__name__)


class EvaluatorService(evaluator_pb2_grpc.EvaluatorServicer):
    def __init__(self, settings: EvaluatorSettings) -> None:
        self._settings = settings
        self._validator = ExpressionValidator.default()
        self._budget = ComplexityBudget(
            max_depth=settings.max_ast_depth,
            max_nodes=settings.max_ast_nodes,
            max_score=settings.max_complexity_score,
        )
        self._sandbox = SandboxRunner(
            SandboxConfig(
                max_runtime_seconds=settings.max_runtime_seconds,
                max_result_magnitude=settings.max_result_magnitude,
                max_memory_bytes=settings.max_memory_bytes,
            )
        )
        self._allowlist = AllowListManager(settings.allowlist_path)

    async def Evaluate(
        self,
        request: evaluator_pb2.EvaluateRequest,
        context: grpc.ServicerContext,
    ) -> evaluator_pb2.EvaluateResponse:
        metadata_carrier = _metadata_to_carrier(context)
        request_id = _resolve_request_id(metadata_carrier)
        token = set_request_id(request_id)
        parent_context = extract(_MetadataGetter(), metadata_carrier)
        increment_inflight()
        start_time = time.perf_counter()
        context.set_trailing_metadata((("x-request-id", request_id),))

        logger.debug(
            "Received evaluation request",
            extra={"expression": request.expression, "context_keys": list(request.context.keys())},
        )

        try:
            with tracer.start_as_current_span(
                "Evaluator.Evaluate",
                context=parent_context,
                kind=SpanKind.SERVER,
            ) as span:
                span.set_attribute("rpc.system", "grpc")
                span.set_attribute("rpc.service", "calculator.Evaluator")
                span.set_attribute("rpc.method", "Evaluate")
                span.set_attribute("request.id", request_id)
                span.set_attribute("expression.length", len(request.expression))
                span.set_attribute("context.entries", len(request.context))
                peer = context.peer() or ""
                if peer:
                    span.set_attribute("net.peer.addr", peer)

                try:
                    snapshot = self._allowlist.snapshot()
                except AllowListError as exc:
                    duration_ms = (time.perf_counter() - start_time) * 1000.0
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                    logger.error("Allow list load failed", exc_info=exc)
                    record_evaluation(duration_ms / 1000.0, "allowlist_error")
                    return evaluator_pb2.EvaluateResponse(error=str(exc), duration_ms=duration_ms)

                try:
                    sanitized_context = _sanitize_context(request.context, snapshot.names)
                except ValueError as exc:
                    duration_ms = (time.perf_counter() - start_time) * 1000.0
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                    logger.info("Context validation failed", extra={"error": str(exc)})
                    record_evaluation(duration_ms / 1000.0, "context_error")
                    return evaluator_pb2.EvaluateResponse(error=str(exc), duration_ms=duration_ms)

                allowed_identifiers = snapshot.names | set(sanitized_context.keys())

                try:
                    tree = self._validator.validate(
                        request.expression,
                        allowed_identifiers=allowed_identifiers,
                    )
                    metrics = self._budget.validate(tree)
                except ValidationError as exc:
                    duration_ms = (time.perf_counter() - start_time) * 1000.0
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                    logger.info("Expression validation failed", extra={"error": str(exc)})
                    record_evaluation(duration_ms / 1000.0, "validation_error")
                    return evaluator_pb2.EvaluateResponse(error=str(exc), duration_ms=duration_ms)
                except ValueError as exc:
                    duration_ms = (time.perf_counter() - start_time) * 1000.0
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                    logger.info("Complexity validation failed", extra={"error": str(exc)})
                    record_evaluation(duration_ms / 1000.0, "complexity_error")
                    return evaluator_pb2.EvaluateResponse(error=str(exc), duration_ms=duration_ms)

                sandbox_result = self._sandbox.run(
                    request.expression,
                    sanitized_context,
                    snapshot.symbols,
                )

                span.set_attribute("sandbox.duration_ms", sandbox_result.duration_ms)

                if not sandbox_result.ok:
                    reason = sandbox_result.error or "unknown"
                    logger.info(
                        "Sandbox execution rejected",
                        extra={"error": sandbox_result.error, "duration_ms": sandbox_result.duration_ms},
                    )
                    span.set_status(Status(StatusCode.ERROR, reason))
                    if sandbox_result.error:
                        span.record_exception(RuntimeError(sandbox_result.error))
                    record_sandbox_restart(_normalize_reason(reason))
                    record_evaluation(sandbox_result.duration_ms / 1000.0, "sandbox_failure")
                    return evaluator_pb2.EvaluateResponse(
                        error=sandbox_result.error or "Unknown error",
                        duration_ms=sandbox_result.duration_ms,
                    )

                _log_success(metrics, sandbox_result.duration_ms)
                span.set_attribute("calculator.ast.depth", metrics.depth)
                span.set_attribute("calculator.ast.nodes", metrics.nodes)
                span.set_attribute("calculator.ast.score", metrics.score)
                span.set_status(Status(StatusCode.OK))
                record_evaluation(sandbox_result.duration_ms / 1000.0, "success")

                return evaluator_pb2.EvaluateResponse(
                    value=sandbox_result.value,
                    duration_ms=sandbox_result.duration_ms,
                )
        finally:
            decrement_inflight()
            reset_request_id(token)


class _MetadataGetter:
    def get(self, carrier: Dict[str, List[str]], key: str) -> Iterable[str]:  # noqa: D401
        return carrier.get(key, [])


def _metadata_to_carrier(context: grpc.ServicerContext) -> Dict[str, List[str]]:
    carrier: Dict[str, List[str]] = {}
    for item in context.invocation_metadata() or ():
        carrier.setdefault(item.key, []).append(item.value)
    return carrier


def _resolve_request_id(carrier: Dict[str, List[str]]) -> str:
    values = carrier.get("x-request-id")
    if values:
        return values[-1]
    return uuid.uuid4().hex


def _normalize_reason(reason: str) -> str:
    sanitized = reason.strip().lower().replace(" ", "_")
    if not sanitized:
        return "unknown"
    return sanitized[:64]


def _sanitize_context(context: Dict[str, str], reserved: set[str]) -> Dict[str, float]:
    sanitized: Dict[str, float] = {}
    for key, value in context.items():
        if not key.isidentifier():
            raise ValueError(f"Context key {key!r} is not a valid identifier")
        if key in reserved:
            raise ValueError(f"Context key {key!r} collides with a reserved name")
        sanitized[key] = float(value)
    return sanitized


def _log_success(metrics: ComplexityMetrics, duration_ms: float) -> None:
    logger.info(
        "Evaluated expression",
        extra={
            "duration_ms": duration_ms,
            "ast_depth": metrics.depth,
            "ast_nodes": metrics.nodes,
            "ast_score": metrics.score,
        },
    )
