"""Local fallback implementation of the pytest-asyncio interface used in tests.

This module provides a minimal subset of the external package so that we can
exercise async fixtures and test coroutines in environments without access to
PyPI.  It intentionally mirrors the public API surface that our test-suite
relies on: the ``fixture`` decorator and the ``asyncio`` pytest mark support.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import AsyncGenerator, Callable
from functools import wraps
from typing import Any, TypeVar, overload

import pytest

pytest_plugins = ["pytest_asyncio._plugin"]

_FixtureFunc = TypeVar("_FixtureFunc", bound=Callable[..., Any])


def _create_loop() -> asyncio.AbstractEventLoop:
    """Provision a fresh event loop for fixture execution."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop


def _teardown_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Close a fixture-managed loop once work completes."""
    try:
        loop.run_until_complete(loop.shutdown_asyncgens())
    finally:
        asyncio.set_event_loop(None)
        loop.close()


@overload
def fixture(__func: _FixtureFunc) -> _FixtureFunc:  # pragma: no cover - signature overload
    ...


@overload
def fixture(*args: Any, **kwargs: Any) -> Callable[[_FixtureFunc], _FixtureFunc]:
    ...


def fixture(*args: Any, **kwargs: Any):
    """Compat wrapper that turns async fixtures into sync ones for pytest.

    The real ``pytest_asyncio.fixture`` decorator ensures that asynchronous
    fixtures integrate with pytest's fixture system.  We emulate that behaviour
    by eagerly executing the coroutine or async generator inside a temporary
    event loop and handing the yielded value back to pytest synchronously.
    """

    if args and callable(args[0]) and not kwargs:
        # Decorator used without parentheses: ``@fixture``.
        return fixture()(args[0])

    def decorator(func: _FixtureFunc) -> _FixtureFunc:
        if inspect.isasyncgenfunction(func):

            @wraps(func)
            @pytest.fixture(*args, **kwargs)
            def wrapper(*f_args: Any, **f_kwargs: Any):
                loop = _create_loop()
                agen: AsyncGenerator[Any, Any] = func(*f_args, **f_kwargs)
                try:
                    value = loop.run_until_complete(agen.__anext__())
                    try:
                        yield value
                    finally:
                        try:
                            loop.run_until_complete(agen.__anext__())
                        except StopAsyncIteration:
                            pass
                finally:
                    _teardown_loop(loop)

            wrapper.__signature__ = inspect.signature(func)  # type: ignore[attr-defined]
            return wrapper  # type: ignore[return-value]

        if inspect.iscoroutinefunction(func):

            @wraps(func)
            @pytest.fixture(*args, **kwargs)
            def wrapper(*f_args: Any, **f_kwargs: Any):
                loop = _create_loop()
                try:
                    return loop.run_until_complete(func(*f_args, **f_kwargs))
                finally:
                    _teardown_loop(loop)

            wrapper.__signature__ = inspect.signature(func)  # type: ignore[attr-defined]
            return wrapper  # type: ignore[return-value]

        return pytest.fixture(*args, **kwargs)(func)

    return decorator
