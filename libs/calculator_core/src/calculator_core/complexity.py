"""Utility for estimating AST complexity."""

from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(slots=True)
class ComplexityMetrics:
    depth: int
    nodes: int
    score: int


@dataclass(slots=True)
class ComplexityBudget:
    """Simple heuristic scoring for AST complexity."""

    max_depth: int
    max_nodes: int
    max_score: int

    def score(self, tree: ast.AST) -> ComplexityMetrics:
        """Return complexity metrics for *tree*."""

        max_depth = 0
        total_nodes = 0

        def walk(node: ast.AST, depth: int) -> None:
            nonlocal max_depth, total_nodes
            total_nodes += 1
            max_depth = max(max_depth, depth)
            for child in ast.iter_child_nodes(node):
                walk(child, depth + 1)

        walk(tree, 1)
        score = max_depth * max_depth + total_nodes
        return ComplexityMetrics(depth=max_depth, nodes=total_nodes, score=score)

    def validate(self, tree: ast.AST) -> ComplexityMetrics:
        metrics = self.score(tree)
        if metrics.depth > self.max_depth:
            raise ValueError(
                f"AST depth {metrics.depth} exceeds limit {self.max_depth}"
            )
        if metrics.nodes > self.max_nodes:
            raise ValueError(
                f"AST node count {metrics.nodes} exceeds limit {self.max_nodes}"
            )
        if metrics.score > self.max_score:
            raise ValueError(
                f"AST complexity score {metrics.score} exceeds limit {self.max_score}"
            )
        return metrics
