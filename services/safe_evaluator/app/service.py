"""Implementation of the evaluator RPC service."""

from __future__ import annotations

import logging
from typing import Dict

import grpc

from calculator_core import ComplexityBudget, ExpressionValidator, SandboxConfig, SandboxRunner
from services.protos import evaluator_pb2, evaluator_pb2_grpc

from .config import EvaluatorSettings

logger = logging.getLogger(__name__)


class EvaluatorService(evaluator_pb2_grpc.EvaluatorServicer):
    def __init__(self, settings: EvaluatorSettings) -> None:
        self._settings = settings
        self._validator = ExpressionValidator.default()
        self._budget = ComplexityBudget(max_depth=25, max_nodes=128)
        self._sandbox = SandboxRunner(
            SandboxConfig(
                max_runtime_seconds=settings.max_runtime_seconds,
                max_result_magnitude=settings.max_result_magnitude,
                max_memory_bytes=settings.max_memory_bytes,
            )
        )

    async def Evaluate(
        self,
        request: evaluator_pb2.EvaluateRequest,
        context: grpc.ServicerContext,
    ) -> evaluator_pb2.EvaluateResponse:
        logger.debug("Received evaluation request", extra={"expression": request.expression})
        try:
            tree = self._validator.validate(request.expression)
            self._budget.validate(tree)
        except ValueError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))

        try:
            sandbox_result = self._sandbox.run(request.expression, _sanitize_context(request.context))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Sandbox execution failed")
            await context.abort(grpc.StatusCode.INTERNAL, str(exc))

        if not sandbox_result.ok:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, sandbox_result.error or "Unknown error")

        return evaluator_pb2.EvaluateResponse(
            value=sandbox_result.value,
            duration_ms=sandbox_result.duration_ms,
        )


def _sanitize_context(context: Dict[str, str]) -> Dict[str, float]:
    sanitized: Dict[str, float] = {}
    for key, value in context.items():
        sanitized[key] = float(value)
    return sanitized
