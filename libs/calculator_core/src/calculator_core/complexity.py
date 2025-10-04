"""Utility for estimating AST complexity."""

from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(slots=True)
class ComplexityBudget:
    """Simple heuristic scoring for AST complexity."""

    max_depth: int
    max_nodes: int

    def score(self, tree: ast.AST) -> tuple[int, int]:
        """Return the depth and number of nodes for *tree*."""

        max_depth = 0
        total_nodes = 0

        def walk(node: ast.AST, depth: int) -> None:
            nonlocal max_depth, total_nodes
            total_nodes += 1
            max_depth = max(max_depth, depth)
            for child in ast.iter_child_nodes(node):
                walk(child, depth + 1)

        walk(tree, 1)
        return max_depth, total_nodes

    def validate(self, tree: ast.AST) -> None:
        depth, nodes = self.score(tree)
        if depth > self.max_depth:
            raise ValueError(f"AST depth {depth} exceeds limit {self.max_depth}")
        if nodes > self.max_nodes:
            raise ValueError(f"AST node count {nodes} exceeds limit {self.max_nodes}")
