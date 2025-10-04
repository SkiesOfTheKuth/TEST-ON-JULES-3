from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from services.common.grpc import grpc
from services.protos import evaluator_pb2, evaluator_pb2_grpc

_SERVER_KEY = b"""-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQCxPAAI1CuC267K\nLURdMtgFE5L22EnoIIJuQikgjp7XAdzqjTOwNAV3LaWaAFPegChxm/l8sK4jP10K\nOCBwxqN4wNU+ONK93gXSksdtCc64JaBn06sW0EO3Yj2kBiyVF00i2Maiv8Pxs6gf\nHclG+GuwU64gZkaYMMBp/i4rX5WyR+AOHls0ADqgioNz7ewILCGlhuGUZ3UZ8n88\n9zdJyGqvvz/WBPG829XJ+CB4xv1lWuHPpK3ZXnnTZyu4RtG+wb1GUx/nXKRNj6lq\nDJeeC734EfqA2Kyd5qRr1e+d8Eed1bKldZy8dbyzCDL8Qxql0vV0YpE9o1Z2eSpV\nBgcT3ZXnAgMBAAECggEAAZxFdc8TvCMp4e1qXxxsqRMl9Tc+6KyO8tiIDiMtn0+F\nhd4Vl6bJW+1ewVj6ah2pAGtF55OlaW2Ud1jONqgfaSP7bA7RH2eKjwDFbiC2L6cr\n33WlatYmn151p+1kb1BgY44rs+PhMGuM/gdjwlDUjawc+29iedSLkwr7uWorbozD\nxYuaG3kRQyw+aDGSvxycvnCxfNugTStZdmHpUZS0D/Cgyfc7bbM19NT/+i+BZv+o\nh90floODhHVIXOLw0whXeyBhf+Ec6yOAXhSXJH2iDzpIS/mGSYrpW40ODLBWx++h\nHSXkHMBp536OgECKFalWY1UtShDKpZ6HgM+a/hWXVQKBgQDbItKuy7ZAolb4Wj+u\n1b54AEfvTXyzsES1kSm7iAXFuQPMYNVLhqHmkE4meQQTXWe8q4o+AprXmQoR/YmL\n9XE8Vc6i6ynUM3H97DSPOsxv4NKYDW7iPcy0OAGsjN/wDQ3VW9i8i/NhePhRT2sb\nZohFgq5t3CfCUyMupVf39dNUwwKBgQDPDKqdHTKpSP/sEU5mLAprgPJ08RrVtKFD\nqRAHsI4i3DZNKDoDGO8Q9ApapQ/TrMlu25m0kADhOBXQykzD+If0KfelEW4CgYn/\n7hBAqyKyGa4SKmiaaedBCbzKKZ2S/LjL+QGSv2/N1Q3y8/krOYWPoRI7WbW8zREl\n4lw/1BAYDQKBgHPczp5C8ULtUqSPOxqawtE5/M7HHob3TOzfKryPp9WqBBscm8oK\nDjIU3G01EPWYLlAwNrCgufQCY7OtZPtOM6feCppTUlNzO/Mw331Xbl489bwVZipS\n2Jf1ANWVypVmoYjMviS6rl08E7cSEaR0KtrtxIIrpA333SM9ouxk2m73AoGBAKAx\nuqfI+XOE6Y2qbjAbDwzSPcVA7nQ+Ry9kVOS+M5rBKrpTz16qIf3J82DiqPYrj8ZX\n3fqYGDYpAKgEfZR6bCX7eoGalLUXqL/9X1HJlxSZTdb8POaL3cKyWAFKZYJeSlR2\nmkMCHuzwVNSO81AAN1hDVSnaZQRo3UWkd59i4fjZAoGBALFg5t7eIHJ604Rg/swH\nVUtWdoaMBX9r2ams8w/XHjXVUPBwfrDkkWDUcaNyRj299mHyEeBsuRUCnb7F3GRV\n/vLO1aR114ryIVczkXyPsaNpFGXJN20XHFagS4GFb3akooIhWfO2z6eqPjt4AAUT\nEXL6/F66zFyECNNqK0ptwpW8\n-----END PRIVATE KEY-----\n"""

_SERVER_CERT = b"""-----BEGIN CERTIFICATE-----\nMIIDCTCCAfGgAwIBAgIUFXyWOzF/7LntgyEVWeaWgtad7vIwDQYJKoZIhvcNAQEL\nBQAwFDESMBAGA1UEAwwJbG9jYWxob3N0MB4XDTI1MTAwNDA5MTYyOVoXDTI2MTAw\nNDA5MTYyOVowFDESMBAGA1UEAwwJbG9jYWxob3N0MIIBIjANBgkqhkiG9w0BAQEF\nAAOCAQ8AMIIBCgKCAQEAsTwACNQrgtuuyi1EXTLYBROS9thJ6CCCbkIpII6e1wHc\n6o0zsDQFdy2lmgBT3oAocZv5fLCuIz9dCjggcMajeMDVPjjSvd4F0pLHbQnOuCWg\nZ9OrFtBDt2I9pAYslRdNItjGor/D8bOoHx3JRvhrsFOuIGZGmDDAaf4uK1+Vskfg\nDh5bNAA6oIqDc+3sCCwhpYbhlGd1GfJ/PPc3Schqr78/1gTxvNvVyfggeMb9ZVrh\nz6St2V5502cruEbRvsG9RlMf51ykTY+pagyXngu9+BH6gNisneaka9XvnfBHndWy\npXWcvHW8swgy/EMapdL1dGKRPaNWdnkqVQYHE92V5wIDAQABo1MwUTAdBgNVHQ4E\nFgQUVgo2+ySqqzxThyBIAy7aRJoenaswHwYDVR0jBBgwFoAUVgo2+ySqqzxThyBI\nAy7aRJoenaswDwYDVR0TAQH/BAUwAwEB/zANBgkqhkiG9w0BAQsFAAOCAQEAgKQN\ni6AKAF9R5cN1nkGrHGCqIbOjWnZ0bgJ6zQg3s+DczFTBKR7Huwar4QnSZbJJ7qiX\ncrxnbvMQeWeVx6mg3KbnwDtttIDAjCXG919cWNxumepPn+319qY4f0FbO6LE+p7a\n0yKlW/3/v7cLaFQiuwYQ3UK2bcBtm6fDSQAMFFvXNBmSy+tZ7R7BCT/Mqh4GaZL3\nZldA+gkT/xXHT/MOG6zc8/Y9FGB4gMvwD39tOHbAJrzJourPYZfckUG2AAHezrR3\nCVDqMfnOo+SKtoJ8+PrsPz+OLtlq+3vKg8JcchUIFYJO6YJIHc9ycdlq88RWH89Y\n1ZKkUq511aJKz+lbRw==\n-----END CERTIFICATE-----\n"""


def _install_safe_evaluator_stubs() -> None:
    otel = types.ModuleType("opentelemetry")

    class _SpanContext:
        def __init__(self) -> None:
            self.trace_id = 0
            self.span_id = 0

        @property
        def is_valid(self) -> bool:
            return False

    class _Span:
        def __enter__(self) -> "_Span":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:  # noqa: D401
            return None

        def set_attribute(self, *args, **kwargs) -> None:  # noqa: D401
            return None

        def set_status(self, *args, **kwargs) -> None:  # noqa: D401
            return None

        def record_exception(self, *args, **kwargs) -> None:  # noqa: D401
            return None

        def get_span_context(self) -> _SpanContext:
            return _SpanContext()

    class _Tracer:
        def start_as_current_span(self, *args, **kwargs):  # noqa: D401
            return _Span()

    trace_module = types.ModuleType("opentelemetry.trace")
    trace_module.get_tracer = lambda name: _Tracer()
    trace_module.get_current_span = lambda: _Span()
    trace_module.SpanKind = types.SimpleNamespace(SERVER="SERVER")

    class _Status:
        def __init__(self, code, description=None) -> None:  # noqa: D401
            self.code = code
            self.description = description

    trace_module.Status = _Status
    trace_module.StatusCode = types.SimpleNamespace(OK="OK", ERROR="ERROR")

    def _set_tracer_provider(provider) -> None:  # noqa: D401
        return None

    trace_module.set_tracer_provider = _set_tracer_provider
    otel.trace = trace_module

    propagate_module = types.ModuleType("opentelemetry.propagate")
    propagate_module.extract = lambda getter, carrier: None

    exporter_module = types.ModuleType("opentelemetry.exporter")
    proto_module = types.ModuleType("opentelemetry.exporter.otlp")
    proto_http_module = types.ModuleType("opentelemetry.exporter.otlp.proto")
    proto_http_module_http = types.ModuleType(
        "opentelemetry.exporter.otlp.proto.http"
    )
    trace_exporter_module = types.ModuleType(
        "opentelemetry.exporter.otlp.proto.http.trace_exporter"
    )

    class _OTLPSpanExporter:  # noqa: D401 - placeholder implementation
        def __init__(self, *args, **kwargs) -> None:
            return None

    trace_exporter_module.OTLPSpanExporter = _OTLPSpanExporter
    proto_http_module_http.trace_exporter = trace_exporter_module
    proto_module.proto = types.SimpleNamespace(http=proto_http_module_http)
    exporter_module.otlp = proto_module

    sdk_module = types.ModuleType("opentelemetry.sdk")
    resources_module = types.ModuleType("opentelemetry.sdk.resources")

    class _Resource:
        @staticmethod
        def create(attrs):  # noqa: D401
            return attrs

    resources_module.Resource = types.SimpleNamespace(create=_Resource.create)
    sdk_trace_module = types.ModuleType("opentelemetry.sdk.trace")

    class _TracerProvider:
        def __init__(self, *args, **kwargs) -> None:
            self._processors = []

        def add_span_processor(self, processor) -> None:  # noqa: D401
            self._processors.append(processor)

    sdk_trace_module.TracerProvider = _TracerProvider
    export_module = types.ModuleType("opentelemetry.sdk.trace.export")

    class _Processor:
        def __init__(self, *args, **kwargs) -> None:
            return None

    export_module.BatchSpanProcessor = _Processor
    export_module.ConsoleSpanExporter = _Processor
    export_module.SimpleSpanProcessor = _Processor
    sdk_trace_module.export = export_module
    sdk_module.trace = sdk_trace_module
    sdk_module.resources = resources_module

    otel.exporter = exporter_module
    otel.propagate = propagate_module
    otel.sdk = sdk_module

    sys.modules["opentelemetry"] = otel
    sys.modules["opentelemetry.trace"] = trace_module
    sys.modules["opentelemetry.propagate"] = propagate_module
    sys.modules[
        "opentelemetry.exporter.otlp.proto.http.trace_exporter"
    ] = trace_exporter_module
    sys.modules["opentelemetry.sdk.resources"] = resources_module
    sys.modules["opentelemetry.sdk.trace"] = sdk_trace_module
    sys.modules["opentelemetry.sdk.trace.export"] = export_module

    prometheus = types.ModuleType("prometheus_client")

    class _Metric:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def labels(self, **kwargs):  # noqa: D401
            return self

        def observe(self, *args, **kwargs) -> None:  # noqa: D401
            return None

        def inc(self, *args, **kwargs) -> None:  # noqa: D401
            return None

        def dec(self, *args, **kwargs) -> None:  # noqa: D401
            return None

    prometheus.Counter = _Metric
    prometheus.Gauge = _Metric
    prometheus.Histogram = _Metric
    prometheus.start_http_server = lambda *args, **kwargs: None
    sys.modules["prometheus_client"] = prometheus

    jsonlogger_module = types.ModuleType("pythonjsonlogger.jsonlogger")

    class _Formatter:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def format(self, record) -> str:  # noqa: D401
            return str(record)

    jsonlogger_module.JsonFormatter = _Formatter
    sys.modules["pythonjsonlogger.jsonlogger"] = jsonlogger_module


_install_safe_evaluator_stubs()


def _load_evaluator_service_module():
    module_path = Path(__file__).resolve().parents[1] / "services/safe_evaluator/app/service.py"
    spec = importlib.util.spec_from_file_location("calculator_safe_evaluator_service", module_path)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise RuntimeError("Unable to load evaluator service module")
    root_services = Path(__file__).resolve().parents[1] / "services"
    if "services" not in sys.modules:
        services_pkg = types.ModuleType("services")
        services_pkg.__path__ = [str(root_services)]  # type: ignore[attr-defined]
        sys.modules["services"] = services_pkg
    safe_root = module_path.parent.parent
    if "services.safe_evaluator" not in sys.modules:
        safe_pkg = types.ModuleType("services.safe_evaluator")
        safe_pkg.__path__ = [str(safe_root)]  # type: ignore[attr-defined]
        sys.modules["services.safe_evaluator"] = safe_pkg
    package_name = "services.safe_evaluator.app"
    if "services.safe_evaluator.app.config" not in sys.modules:
        config_stub = types.ModuleType("services.safe_evaluator.app.config")

        class _StubSettings:
            pass

        config_stub.EvaluatorSettings = _StubSettings
        sys.modules["services.safe_evaluator.app.config"] = config_stub
    if "services.safe_evaluator.app.observability" not in sys.modules:
        observability_stub = types.ModuleType("services.safe_evaluator.app.observability")

        def _noop(*args, **kwargs):  # noqa: D401
            return None

        observability_stub.configure_logging = _noop
        observability_stub.configure_tracing = _noop
        observability_stub.configure_metrics = _noop
        observability_stub.increment_inflight = _noop
        observability_stub.decrement_inflight = _noop
        observability_stub.record_evaluation = _noop
        observability_stub.record_sandbox_restart = _noop
        observability_stub.set_request_id = lambda value: value
        observability_stub.reset_request_id = _noop
        sys.modules["services.safe_evaluator.app.observability"] = observability_stub
    if package_name not in sys.modules:
        package_module = types.ModuleType(package_name)
        package_module.__path__ = [str(module_path.parent)]  # type: ignore[attr-defined]
        sys.modules[package_name] = package_module
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "services.safe_evaluator.app"
    spec.loader.exec_module(module)
    return module


_service_module = _load_evaluator_service_module()
EvaluatorService = _service_module.EvaluatorService


def _build_settings() -> SimpleNamespace:
    root = Path(__file__).resolve().parents[1]
    allowlist = root / "services/safe_evaluator/app/allowlist.json"
    return SimpleNamespace(
        max_ast_depth=25,
        max_ast_nodes=128,
        max_complexity_score=1024,
        max_runtime_seconds=0.25,
        max_result_magnitude=1e12,
        max_memory_bytes=64 * 1024 * 1024,
        allowlist_path=allowlist,
    )


def test_evaluator_handles_valid_request_insecure() -> None:
    async def _run() -> None:
        with patch.object(_service_module, "SandboxRunner") as sandbox_mock, patch.object(
            _service_module, "AllowListManager"
        ) as allowlist_mock:
            sandbox_instance = sandbox_mock.return_value
            sandbox_instance.run.return_value = SimpleNamespace(
                ok=True,
                error=None,
                duration_ms=12.3,
                value=3.0,
            )
            allowlist_instance = allowlist_mock.return_value
            allowlist_instance.snapshot.return_value = SimpleNamespace(
                names=set(), symbols={}
            )

            server = grpc.aio.server()
            service = EvaluatorService(_build_settings())
            evaluator_pb2_grpc.add_EvaluatorServicer_to_server(service, server)
            server.add_insecure_port("localhost:0")
            await server.start()
            port = server.bound_port

            channel = grpc.aio.insecure_channel(f"localhost:{port}")
            stub = evaluator_pb2_grpc.EvaluatorStub(channel)
            try:
                response = await stub.Evaluate(
                    evaluator_pb2.EvaluateRequest(expression="1 + 2")
                )
                assert response.value == pytest.approx(3.0)
                assert response.WhichOneof("result") == "value"
            finally:
                await channel.close()
                await server.stop(0)

    asyncio.run(_run())


def test_evaluator_handles_valid_request_tls() -> None:
    async def _run() -> None:
        with patch.object(_service_module, "SandboxRunner") as sandbox_mock, patch.object(
            _service_module, "AllowListManager"
        ) as allowlist_mock:
            sandbox_instance = sandbox_mock.return_value
            sandbox_instance.run.return_value = SimpleNamespace(
                ok=True,
                error=None,
                duration_ms=10.0,
                value=3.0,
            )
            allowlist_instance = allowlist_mock.return_value
            allowlist_instance.snapshot.return_value = SimpleNamespace(
                names=set(), symbols={}
            )

            server = grpc.aio.server()
            service = EvaluatorService(_build_settings())
            evaluator_pb2_grpc.add_EvaluatorServicer_to_server(service, server)
            server.add_secure_port(
                "localhost:0",
                grpc.ssl_server_credentials([(_SERVER_KEY, _SERVER_CERT)]),
            )
            await server.start()
            port = server.bound_port

            credentials = grpc.ssl_channel_credentials(root_certificates=_SERVER_CERT)
            channel = grpc.aio.secure_channel(f"localhost:{port}", credentials)
            stub = evaluator_pb2_grpc.EvaluatorStub(channel)
            try:
                response = await stub.Evaluate(
                    evaluator_pb2.EvaluateRequest(expression="6 / 2")
                )
                assert response.value == pytest.approx(3.0)
                assert response.WhichOneof("result") == "value"
            finally:
                await channel.close()
                await server.stop(0)

    asyncio.run(_run())
