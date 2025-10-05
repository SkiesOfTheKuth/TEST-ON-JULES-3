"""Minimal Celery stub used for offline testing."""

from __future__ import annotations

from types import SimpleNamespace
from types import SimpleNamespace
from typing import Any, Callable, Dict, Iterable, Optional

from .result import EagerResult


class _CeleryConfig(SimpleNamespace):
    def update(self, mapping: Optional[Dict[str, Any]] = None, **kwargs: Any) -> None:
        data: Dict[str, Any] = {}
        if mapping:
            data.update(mapping)
        data.update(kwargs)
        for key, value in data.items():
            setattr(self, key, value)


class Celery:
    """Very small subset of :class:`celery.Celery` for unit tests."""

    def __init__(self, name: str) -> None:
        self.main = name
        self.conf = _CeleryConfig(
            task_always_eager=True,
            task_eager_propagates=True,
            task_default_queue="default",
            task_serializer="json",
            result_serializer="json",
            accept_content=["json"],
            task_acks_late=False,
            task_track_started=False,
            worker_prefetch_multiplier=1,
        )
        self.tasks: Dict[str, _CeleryTask] = {}

    def task(self, *decorator_args: Any, **decorator_kwargs: Any) -> Callable[[Callable[..., Any]], "_CeleryTask"]:
        def decorator(func: Callable[..., Any]) -> _CeleryTask:
            name = decorator_kwargs.get("name") or func.__name__
            task = _CeleryTask(
                app=self,
                func=func,
                name=name,
                bind=decorator_kwargs.get("bind", False),
                autoretry_for=tuple(decorator_kwargs.get("autoretry_for", ()) or ()),
                retry_backoff=decorator_kwargs.get("retry_backoff", 0),
                retry_jitter=decorator_kwargs.get("retry_jitter", False),
                retry_kwargs=decorator_kwargs.get("retry_kwargs") or {},
            )
            self.tasks[name] = task
            return task

        if decorator_args and callable(decorator_args[0]):
            return decorator(decorator_args[0])
        return decorator

    def send_task(
        self,
        name: str,
        args: Optional[Iterable[Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        queue: Optional[str] = None,
    ) -> EagerResult:
        task = self.tasks.get(name)
        if task is None:
            raise KeyError(f"Task {name!r} is not registered")
        return task.apply(args=args, kwargs=kwargs)


class _CeleryTask:
    def __init__(
        self,
        app: Celery,
        func: Callable[..., Any],
        *,
        name: str,
        bind: bool,
        autoretry_for: Iterable[type[BaseException]],
        retry_backoff: float,
        retry_jitter: bool,
        retry_kwargs: Dict[str, Any],
    ) -> None:
        self.app = app
        self.func = func
        self.name = name
        self.bind = bind
        self.autoretry_for = tuple(autoretry_for)
        self.retry_backoff = retry_backoff
        self.retry_jitter = retry_jitter
        self.retry_kwargs = retry_kwargs
        self.max_retries = retry_kwargs.get("max_retries")

    def apply(
        self,
        args: Optional[Iterable[Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> EagerResult:
        call_args = list(args or [])
        call_kwargs = dict(kwargs or {})
        context = _TaskContext(self)
        if self.bind:
            call_args.insert(0, context)
        try:
            value = self.func(*call_args, **call_kwargs)
            return EagerResult(value=value, successful=True)
        except Exception as exc:  # noqa: BLE001 - mimic Celery eager behaviour
            if self.app.conf.task_eager_propagates:
                raise
            return EagerResult(value=None, successful=False, exception=exc)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        context = _TaskContext(self)
        if self.bind:
            return self.func(context, *args, **kwargs)
        return self.func(*args, **kwargs)


class _TaskContext:
    def __init__(self, task: _CeleryTask) -> None:
        self.task = task
        self.request = SimpleNamespace(retries=0)
        self.max_retries = task.max_retries

    def retry(self, exc: Optional[BaseException] = None) -> None:
        self.request.retries += 1
        if exc is None:
            raise RuntimeError("Retry requested")
        raise exc


__all__ = ["Celery", "EagerResult"]
