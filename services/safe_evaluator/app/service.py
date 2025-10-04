"""Implementation of the evaluator RPC service."""

from __future__ import annotations

import logging
import time
from typing import Dict

import grpc

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

logger = logging.getLogger(__name__)


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
        start_time = time.perf_counter()
        logger.debug(
            "Received evaluation request",
            extra={"expression": request.expression, "context_keys": list(request.context.keys())},
        )

        try:
            snapshot = self._allowlist.snapshot()
        except AllowListError as exc:
            logger.error("Allow list load failed", exc_info=exc)
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return evaluator_pb2.EvaluateResponse(error=str(exc), duration_ms=duration_ms)

        try:
            sanitized_context = _sanitize_context(request.context, snapshot.names)
        except ValueError as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.info("Context validation failed", extra={"error": str(exc)})
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
            logger.info("Expression validation failed", extra={"error": str(exc)})
            return evaluator_pb2.EvaluateResponse(error=str(exc), duration_ms=duration_ms)
        except ValueError as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.info("Complexity validation failed", extra={"error": str(exc)})
            return evaluator_pb2.EvaluateResponse(error=str(exc), duration_ms=duration_ms)

        sandbox_result = self._sandbox.run(
            request.expression,
            sanitized_context,
            snapshot.symbols,
        )

        if not sandbox_result.ok:
            logger.info(
                "Sandbox execution rejected",
                extra={"error": sandbox_result.error, "duration_ms": sandbox_result.duration_ms},
            )
            return evaluator_pb2.EvaluateResponse(
                error=sandbox_result.error or "Unknown error",
                duration_ms=sandbox_result.duration_ms,
            )

        _log_success(metrics, sandbox_result.duration_ms)

        return evaluator_pb2.EvaluateResponse(
            value=sandbox_result.value,
            duration_ms=sandbox_result.duration_ms,
        )


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
