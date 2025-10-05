"""Simple asyncio support for pytest without external dependency."""

from __future__ import annotations

import asyncio
import inspect
from typing import Any, Callable

import pytest

FixtureFunc = Callable[..., Any]


def fixture(*decorator_args, **decorator_kwargs):
    if decorator_args and callable(decorator_args[0]) and not decorator_kwargs:
        return _wrap_fixture(decorator_args[0])

    def wrapper(func: FixtureFunc) -> FixtureFunc:
        return _wrap_fixture(func, *decorator_args, **decorator_kwargs)

    return wrapper


def _wrap_fixture(func: FixtureFunc, *fixture_args, **fixture_kwargs):
    if not inspect.iscoroutinefunction(func):
        return pytest.fixture(*fixture_args, **fixture_kwargs)(func)

    @pytest.fixture(*fixture_args, **fixture_kwargs)
    def _sync_fixture(**kwargs: Any):
        return asyncio.run(func(**kwargs))

    return _sync_fixture


def pytest_configure(config: pytest.Config) -> None:  # pragma: no cover - pytest hook
    config.addinivalue_line("markers", "asyncio: mark test to run inside an event loop")


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> bool | None:
    test_function = pyfuncitem.obj
    if not inspect.iscoroutinefunction(test_function):
        return None

    kwargs = {
        arg: pyfuncitem.funcargs[arg]
        for arg in pyfuncitem._fixtureinfo.argnames  # type: ignore[attr-defined]
    }
    asyncio.run(test_function(**kwargs))
    return True


__all__ = ["fixture"]
