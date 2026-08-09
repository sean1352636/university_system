"""Spreadsheet (CSV/XLSX) formula-injection protection.

A cell whose text begins with ``=``, ``+``, ``-``, ``@``, a tab or a carriage
return is interpreted as a formula by Excel, LibreOffice and Google Sheets when
the exported file is opened. An attacker who can get a value into an exported
report (a student name, a free-text comment, an address) can therefore run a
formula on the recipient's machine — data exfiltration via ``=WEBSERVICE(...)``
or command execution via DDE.

The defence is to prefix any such cell with a single quote so the spreadsheet
treats it as literal text. This is the single shared implementation; exporters
must not re-derive it.
"""

from __future__ import annotations

from typing import Any, Iterable

__all__ = ["sanitize_cell", "sanitize_row", "DANGEROUS_PREFIXES"]

#: Leading characters that make a spreadsheet treat a cell as a formula.
DANGEROUS_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_cell(value: Any) -> Any:
    """Return *value* safe for a spreadsheet cell.

    Strings starting with a formula-trigger character are prefixed with a
    single quote. Non-string values are returned unchanged so numbers and
    dates keep their type in XLSX output.
    """
    if not isinstance(value, str):
        return value
    if value.startswith(DANGEROUS_PREFIXES):
        return "'" + value
    return value


def sanitize_row(row: Iterable[Any]) -> list[Any]:
    """Apply :func:`sanitize_cell` to every cell in *row*."""
    return [sanitize_cell(cell) for cell in row]
