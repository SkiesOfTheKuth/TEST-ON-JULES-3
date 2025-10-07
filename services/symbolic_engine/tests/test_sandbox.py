import time

import pytest

from app.sandbox import SandboxRunner, SandboxTimeout


def slow_function(delay: float) -> str:
    time.sleep(delay)
    return "done"


def boom() -> None:
    raise ValueError("boom")


@pytest.mark.parametrize("delay", [0.1])
def test_sandbox_success(delay: float) -> None:
    runner = SandboxRunner(timeout_seconds=1.0, memory_mb=64)
    outcome = runner.run(slow_function, delay)
    assert outcome == "done"


def test_sandbox_timeout() -> None:
    runner = SandboxRunner(timeout_seconds=0.1, memory_mb=64)
    with pytest.raises(SandboxTimeout):
        runner.run(slow_function, 1.0)


def test_sandbox_error() -> None:
    runner = SandboxRunner(timeout_seconds=1.0, memory_mb=64)
    with pytest.raises(ValueError) as excinfo:
        runner.run(boom)
    assert str(excinfo.value) == "boom"
