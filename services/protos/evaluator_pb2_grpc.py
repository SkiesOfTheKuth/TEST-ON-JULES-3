"""gRPC-style stubs for the evaluator service using the local transport."""

from __future__ import annotations

from typing import Sequence

import grpc

from . import evaluator_pb2 as evaluator__pb2


class EvaluatorStub:
    def __init__(self, channel: grpc.aio.Channel) -> None:
        self._channel = channel

    async def Evaluate(
        self,
        request: evaluator__pb2.EvaluateRequest,
        timeout: float | None = None,
        metadata: Sequence[tuple[str, str]] | None = None,
    ) -> evaluator__pb2.EvaluateResponse:
        callable_ = self._channel.unary_unary("/evaluator.v1.Evaluator/Evaluate")
        response_payload = await callable_(request, timeout=timeout, metadata=metadata)
        return evaluator__pb2.EvaluateResponse.from_dict(response_payload)


class EvaluatorServicer:
    async def Evaluate(self, request: evaluator__pb2.EvaluateRequest, context: grpc.ServicerContext) -> evaluator__pb2.EvaluateResponse:
        raise NotImplementedError


def add_EvaluatorServicer_to_server(servicer: EvaluatorServicer, server: grpc.aio.Server) -> None:
    async def evaluate(payload: dict, context: grpc.ServicerContext):
        request = evaluator__pb2.EvaluateRequest.from_dict(payload)
        response = await servicer.Evaluate(request, context)
        return response.to_dict()

    handler = grpc.UnaryUnaryRpcMethodHandler(evaluate)
    generic = grpc.method_handlers_generic_handler(
        "evaluator.v1.Evaluator", {"Evaluate": handler}
    )
    server.add_generic_rpc_handlers([generic])


__all__ = ["EvaluatorStub", "EvaluatorServicer", "add_EvaluatorServicer_to_server"]
