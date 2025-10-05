"""Lightweight pytest-asyncio compatibility shim for offline test runs."""

from __future__ import annotations

import asyncio
import inspect
from functools import wraps
from typing import Any, Awaitable, Callable

import pytest

FixtureFunc = Callable[..., Any]


def fixture(*decorator_args, **decorator_kwargs):
    """A drop-in replacement for ``pytest_asyncio.fixture``."""

    if decorator_args and callable(decorator_args[0]) and not decorator_kwargs:
        return _wrap_fixture(decorator_args[0])

    def wrapper(func: FixtureFunc) -> FixtureFunc:
        return _wrap_fixture(func, *decorator_args, **decorator_kwargs)

    return wrapper


def _wrap_fixture(func: FixtureFunc, *fixture_args, **fixture_kwargs):
    async_fixture = inspect.iscoroutinefunction(func)
    async_gen_fixture = inspect.isasyncgenfunction(func)

    if not async_fixture and not async_gen_fixture:
        return pytest.fixture(*fixture_args, **fixture_kwargs)(func)

    @pytest.fixture(*fixture_args, **fixture_kwargs)
    @wraps(func)
    def _sync_wrapper(request: pytest.FixtureRequest) -> Any:
        loop = _ensure_loop(request.node)
        signature = inspect.signature(func)
        bound_kwargs: dict[str, Any] = {}
        for name, parameter in signature.parameters.items():
            if name == "request":
                bound_kwargs[name] = request
            elif parameter.kind in {
                parameter.POSITIONAL_ONLY,
                parameter.POSITIONAL_OR_KEYWORD,
                parameter.KEYWORD_ONLY,
            }:
                bound_kwargs[name] = request.getfixturevalue(name)

        if async_fixture:
            return _run_in_loop(loop, func(**bound_kwargs))

        agen = func(**bound_kwargs)
        item = request.node

        result = _run_in_loop(loop, agen.__anext__())

        def finalizer() -> None:
            async def _finalize() -> None:
                try:
                    await agen.__anext__()
                except StopAsyncIteration:
                    return
                finally:
                    await agen.aclose()

            _run_in_loop(loop, _finalize())

        if hasattr(item, "addfinalizer"):
            item.addfinalizer(finalizer)
        else:
            request.addfinalizer(finalizer)

        return result

    return _sync_wrapper


def pytest_configure(config: pytest.Config) -> None:  # pragma: no cover - pytest hook
    config.addinivalue_line("markers", "asyncio: mark test to run inside an event loop")


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> bool | None:
    test_function = pyfuncitem.obj
    if not inspect.iscoroutinefunction(test_function):
        return None

    loop = _ensure_loop(pyfuncitem)
    kwargs = {
        arg: pyfuncitem.funcargs[arg]
        for arg in pyfuncitem._fixtureinfo.argnames  # type: ignore[attr-defined]
    }
    _run_in_loop(loop, test_function(**kwargs))
    return True


@pytest.hookimpl(tryfirst=True)
def pytest_fixture_setup(fixturedef: pytest.FixtureDef, request: pytest.FixtureRequest):
    func = fixturedef.func
    if not inspect.iscoroutinefunction(func) and not inspect.isasyncgenfunction(func):
        return None

    loop = _ensure_loop(request.node)
    kwargs = {name: request.getfixturevalue(name) for name in fixturedef.argnames if name != "request"}
    if "request" in fixturedef.argnames:
        kwargs["request"] = request

    if inspect.iscoroutinefunction(func):
        return _run_in_loop(loop, func(**kwargs))

    agen = func(**kwargs)
    result = _run_in_loop(loop, agen.__anext__())

    def finalizer() -> None:
        async def _finalize() -> None:
            try:
                await agen.__anext__()
            except StopAsyncIteration:
                return
            finally:
                await agen.aclose()

        _run_in_loop(loop, _finalize())

    request.addfinalizer(finalizer)
    return result


def _ensure_loop(node: Any) -> asyncio.AbstractEventLoop:
    loop = getattr(node, "_pytest_asyncio_loop", None)
    if loop is not None:
        return loop

    loop = asyncio.new_event_loop()
    setattr(node, "_pytest_asyncio_loop", loop)

    if hasattr(node, "addfinalizer"):
        node.addfinalizer(loop.close)
    else:  # pragma: no cover - fallback for non-function nodes
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            loop.close()
        else:
            running_loop.call_soon(loop.close)
    return loop


def _run_in_loop(loop: asyncio.AbstractEventLoop, awaitable: Awaitable[Any]) -> Any:
    try:
        current = asyncio.get_running_loop()
    except RuntimeError:
        current = None

    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(awaitable)
    finally:
        asyncio.set_event_loop(current)


__all__ = ["fixture"]
