from calculator_core import SandboxConfig, SandboxRunner


def test_sandbox_evaluates_expression():
    runner = SandboxRunner(SandboxConfig(max_runtime_seconds=1.0))
    result = runner.run("add(1, 2) + sqrt(16)", {"addend": 0})
    assert result.ok
    assert abs(result.value - 7.0) < 1e-6


def test_sandbox_validates_context_identifiers():
    runner = SandboxRunner(SandboxConfig(max_runtime_seconds=1.0))
    result = runner.run("divide(10, value)", {"invalid key": 2})
    assert not result.ok
    assert "valid identifier" in (result.error or "")
