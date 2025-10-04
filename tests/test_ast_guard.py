import pytest

from calculator_core import ExpressionValidator, ValidationError


def test_validator_allows_simple_expression():
    validator = ExpressionValidator.default()
    tree = validator.validate("1 + 2 * 3")
    assert tree is not None


def test_validator_blocks_attribute_access():
    validator = ExpressionValidator.default()
    try:
        validator.validate("__import__('os').system('ls')")
    except ValidationError as exc:
        assert "Attribute access" in str(exc)
    else:
        raise AssertionError("attribute access should be blocked")


def test_validator_rejects_unknown_identifier():
    validator = ExpressionValidator.default()
    with pytest.raises(ValidationError):
        validator.validate("foo + 1", allowed_identifiers={"bar"})
