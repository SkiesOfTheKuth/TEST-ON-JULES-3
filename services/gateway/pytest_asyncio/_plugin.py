"""Pytest plugin hooks that execute coroutine tests using ``asyncio``.

Only the features required by the gateway test-suite are implemented here: any
``async def`` test function is awaited inside a fresh event loop and any test
marked with ``@pytest.mark.asyncio`` is recognised so pytest does not emit
"unknown marker" warnings.
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any

import pytest


@pytest.hookimpl
def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "asyncio: execute the decorated test function inside an asyncio event loop",
    )


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> bool | None:
    test_func = pyfuncitem.obj
    if not inspect.iscoroutinefunction(test_func):
        return None

    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(test_func(**pyfuncitem.funcargs))
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        asyncio.set_event_loop(None)
        loop.close()
    return True
