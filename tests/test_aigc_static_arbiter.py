"""Regression tests for fail-closed AST screening of model-generated Python."""
from __future__ import annotations

import pytest

from core.arbiter import audit_python_source


def test_simple_data_expression_passes_static_screen_only() -> None:
    report = audit_python_source("result = sum([1, 2, 3])")
    assert report.status == "PASS_STATIC_SCREEN_ONLY"
    assert report.execution_performed is False
    assert report.findings == ()


@pytest.mark.parametrize(
    "source, rule_id",
    [
        ("import os", "AST-006"),
        ("result = eval('1 + 1')", "AST-007"),
        ("result = value.__class__", "AST-008"),
        ("while True:\n    pass", "AST-009"),
    ],
)
def test_dangerous_or_unbounded_constructs_fail_closed(source: str, rule_id: str) -> None:
    report = audit_python_source(source)
    assert report.status == "BLOCK"
    assert report.execution_performed is False
    assert any(finding.rule_id == rule_id for finding in report.findings)


def test_ast_node_limit_is_enforced_during_traversal() -> None:
    report = audit_python_source("result = 1", max_nodes=1)
    assert report.status == "BLOCK"
    assert report.findings[0].rule_id == "AST-003"


def test_invalid_utf8_surrogate_is_blocked_without_raising() -> None:
    report = audit_python_source("result = '\ud800'")
    assert report.status == "BLOCK"
    assert report.findings[0].rule_id == "AST-012"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_bytes": 0},
        {"max_nodes": True},
        {"max_nodes": 100001},
        {"max_nesting": 257},
    ],
)
def test_audit_limits_must_be_validated(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        audit_python_source("result = 1", **kwargs)
