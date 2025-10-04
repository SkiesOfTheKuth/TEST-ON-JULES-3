"""Expression validation before entering the sandbox."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Iterable, Set


class ValidationError(ValueError):
    """Raised when the expression AST violates the policy."""


@dataclass(slots=True)
class ExpressionValidator:
    """Validate Python expressions against an allow list of AST nodes."""

    allowed_nodes: Set[type]
    banned_names: Set[str]

    def validate(self, expression: str) -> ast.AST:
        if not expression:
            raise ValidationError("Expression cannot be empty")
        if len(expression) > 512:
            raise ValidationError("Expression length exceeds maximum of 512 characters")

        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise ValidationError(f"Invalid expression syntax: {exc.msg}") from exc

        for node in ast.walk(tree):
            if type(node) not in self.allowed_nodes:
                raise ValidationError(f"Node {type(node).__name__} is not permitted")
            if isinstance(node, ast.Name) and node.id in self.banned_names:
                raise ValidationError(f"Name {node.id!r} is not permitted")
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    raise ValidationError("Attribute access is not permitted")
                if isinstance(node.func, ast.Name) and node.func.id.startswith("__"):
                    raise ValidationError("Dunder call targets are not permitted")
        return tree

    @classmethod
    def default(cls) -> "ExpressionValidator":
        allowed_nodes: Iterable[type] = (
            ast.Expression,
            ast.BinOp,
            ast.UnaryOp,
            ast.Num,
            ast.Constant,
            ast.Add,
            ast.Sub,
            ast.Mult,
            ast.Div,
            ast.Pow,
            ast.Mod,
            ast.FloorDiv,
            ast.USub,
            ast.UAdd,
            ast.Call,
            ast.Load,
            ast.Name,
            ast.keyword,
            ast.Tuple,
            ast.List,
        )
        return cls(set(allowed_nodes), {"__import__", "eval", "exec", "open", "input", "print"})
