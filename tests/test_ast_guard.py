import pytest

from calculator_core import ExpressionValidator, ValidationError


def test_validator_allows_simple_expression():
    validator = ExpressionValidator.default()
    tree = validator.validate("1 + 2 * 3")
    assert tree is not None


def test_validator_blocks_attribute_access():
    validator = ExpressionValidator.default()
    with pytest.raises(ValidationError) as exc:
        validator.validate("__import__('os').system('ls')")
    assert "Attribute access" in str(exc.value)


@pytest.mark.parametrize(
    "payload",
    [
        "sum(x for x in range(5))",
        "[__import__('os') for _ in range(2)]",
        "(lambda: exec('1+1'))()",
        "(__import__('os'), 42)[0]",
    ],
)
def test_validator_rejects_malicious_payloads(payload: str) -> None:
    validator = ExpressionValidator.default()
    with pytest.raises(ValidationError):
        validator.validate(payload)


def test_validator_rejects_unknown_identifier():
    validator = ExpressionValidator.default()
    with pytest.raises(ValidationError):
        validator.validate("foo + 1", allowed_identifiers={"bar"})
