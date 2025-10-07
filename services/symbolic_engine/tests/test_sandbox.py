import pytest

from services.symbolic_engine.app import sandbox
from services.symbolic_engine.app.config import get_settings


def test_run_operation_simplify_returns_metadata():
    settings = get_settings()
    data = sandbox.run_operation("simplify", {"expression": "x + x", "variables": ["x"]}, settings)
    assert "result" in data
    assert data["result"] == "2*x"
    diagnostics = data.get("diagnostics", {})
    assert diagnostics["memory_limit_mb"] == settings.sandbox_memory_limit_mb


def test_run_operation_blocks_unsafe_tokens():
    with pytest.raises(sandbox.SandboxExecutionError):
        sandbox.run_operation("simplify", {"expression": "__import__('os')", "variables": []})
