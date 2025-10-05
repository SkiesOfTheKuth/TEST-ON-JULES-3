"""Package marker for the gateway application modules."""

try:  # pragma: no cover - optional dependency for tests
    from .main import app  # type: ignore F401
except ModuleNotFoundError:  # FastAPI not available in the offline test harness
    app = None

__all__ = ["app"]
