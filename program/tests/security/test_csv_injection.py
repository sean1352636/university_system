"""Spreadsheet formula-injection protection for exports (task 14)."""

from __future__ import annotations

import pytest

from education_system.platform.kernel.core.csv_safety import sanitize_cell, sanitize_row

pytestmark = pytest.mark.security


@pytest.mark.parametrize("payload", [
    "=SUM(A1:A2)",
    "+1+1",
    "-2+3",
    "@SUM(1)",
    "=cmd|'/c calc'!A1",
    "\t=1",
    "\r=1",
])
def test_formula_triggers_are_neutralised(payload):
    out = sanitize_cell(payload)
    assert out.startswith("'"), f"{payload!r} was not escaped"


@pytest.mark.parametrize("safe", ["Alice", "123 Main St", "42", "student@example.com is fine mid-string"])
def test_safe_values_untouched(safe):
    assert sanitize_cell(safe) == safe


def test_non_strings_pass_through():
    assert sanitize_cell(42) == 42
    assert sanitize_cell(None) is None


def test_sanitize_row():
    assert sanitize_row(["=1", "ok", 3]) == ["'=1", "ok", 3]
