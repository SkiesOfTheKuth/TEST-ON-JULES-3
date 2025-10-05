"""Minimal Celery-compatible façade for offline testing.

The real Celery dependency is unavailable in the execution environment, so we
provide a tiny subset that satisfies the gateway's test-suite.  Only the eager
execution behaviour exercised in tests is implemented; any attempt to use other
features raises ``NotImplementedError`` to keep unsupported usage obvious.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable, Dict, Optional

from .result import EagerResult


class _Config(SimpleNamespace):
    """Configuration namespace that mimics ``celery.Celery.conf``."""

    def update(self, values: Dict[str, Any] | None = None, /, **kwargs: Any) -> None:
        items = dict(values or {})
        items.update(kwargs)
        for key, value in items.items():
            setattr(self, key, value)


class Celery:
    """Greatly simplified Celery application used for tests."""

    def __init__(self, name: str, *args: Any, **kwargs: Any) -> None:  # noqa: D401
        self.main = name
        self.conf = _Config(task_always_eager=False, task_eager_propagates=False)
        self._tasks: Dict[str, _Task] = {}

    def task(self, *task_args: Any, **task_kwargs: Any) -> Callable[[Callable[..., Any]], "_Task"]:
        def decorator(func: Callable[..., Any]) -> "_Task":
            name = task_kwargs.get("name") or func.__name__
            task = _Task(self, func, name, task_kwargs)
            self._tasks[name] = task
            return task

        if task_args and callable(task_args[0]) and not task_kwargs:
            return decorator(task_args[0])
        return decorator

    def send_task(
        self,
        name: str,
        args: Optional[list[Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        queue: str | None = None,
    ) -> EagerResult:
        task = self._tasks.get(name)
        if task is None:
            raise KeyError(f"Task {name} not registered")
        return task.apply(args=args or [], kwargs=kwargs or {})


class _Task:
    def __init__(self, app: Celery, func: Callable[..., Any], name: str, options: Dict[str, Any]) -> None:
        self.app = app
        self.func = func
        self.name = name
        self.max_retries = options.get("retry_kwargs", {}).get("max_retries")
        self.autoretry_for = tuple(options.get("autoretry_for", ()))

    def apply(self, args: Optional[list[Any]] = None, kwargs: Optional[Dict[str, Any]] = None) -> EagerResult:
        args = args or []
        kwargs = kwargs or {}
        if not getattr(self.app.conf, "task_always_eager", False):
            raise RuntimeError("Only eager execution is supported in the Celery test stub")

        request = SimpleNamespace(retries=0)
        context = _BoundTaskContext(self, request)
        try:
            result = self.func(context, *args, **kwargs)
        except Exception as exc:  # pragma: no cover - surfaced in pytest failures
            if getattr(self.app.conf, "task_eager_propagates", False):
                raise
            return EagerResult(exception=exc)
        return EagerResult(result=result)


class _BoundTaskContext:
    def __init__(self, task: _Task, request: SimpleNamespace) -> None:
        self._task = task
        self.request = request
        self.max_retries = task.max_retries

    def retry(self, exc: Exception | None = None) -> None:  # pragma: no cover - not used in tests
        raise exc or RuntimeError("Retry not supported in Celery test stub")


__all__ = ["Celery"]
