"""CSV export helpers."""

from __future__ import annotations

from typing import Any

#: A cell starting with one of these is run as a formula by spreadsheets.
_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value: Any) -> str:
    """A CSV cell that a spreadsheet can't run as a formula (``'`` in front)."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in _FORMULA_START else text
