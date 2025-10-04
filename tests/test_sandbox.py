import math

from calculator_core import SandboxConfig, SandboxRunner, default_allowlist, filter_allowlist


def test_sandbox_evaluates_expression():
    runner = SandboxRunner(SandboxConfig(max_runtime_seconds=1.0))
    allowlist = default_allowlist()
    result = runner.run("add(1, 2) + sqrt(16)", {}, allowlist)
    assert result.ok
    assert math.isclose(result.value, 7.0)


def test_sandbox_validates_context_identifiers():
    runner = SandboxRunner(SandboxConfig(max_runtime_seconds=1.0))
    allowlist = default_allowlist()
    result = runner.run("divide(10, value)", {"invalid key": 2}, allowlist)
    assert not result.ok
    assert "valid identifier" in (result.error or "")


def test_sandbox_respects_allowlist():
    runner = SandboxRunner(SandboxConfig(max_runtime_seconds=1.0))
    limited_allowlist = filter_allowlist(["add"])
    result = runner.run("sqrt(9)", {}, limited_allowlist)
    assert not result.ok
    assert "not defined" in (result.error or "")
