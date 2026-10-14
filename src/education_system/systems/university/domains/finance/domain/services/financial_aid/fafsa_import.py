"""FAFSA data file import.

Reads a CSV of FAFSA records and upserts each row through
``FinancialAidManager.import_fafsa_data`` — the same path as single-record
entry — so the admin portal GUI and the financial aid CLI share one importer.

Expected columns (header names are case-insensitive)::

    student_id, academic_year, efc[, submission_date, sai, dependency_status,
    pell_eligible, pell_amount]

``submission_date`` defaults to today; ``pell_eligible`` accepts
yes/no/true/false/1/0.
"""

from __future__ import annotations

import csv
from datetime import date
from typing import Any, Dict, Optional

REQUIRED_COLUMNS: tuple[str, ...] = ("student_id", "academic_year", "efc")
OPTIONAL_COLUMNS: tuple[str, ...] = (
    "submission_date", "sai", "dependency_status", "pell_eligible", "pell_amount",
)
_TRUE_WORDS = {"1", "true", "yes", "y", "t"}


def _clean_headers(fieldnames) -> list[str]:
    return [(name or "").strip().lower() for name in (fieldnames or [])]


def _parse_bool(raw: Optional[str]) -> bool:
    return (raw or "").strip().lower() in _TRUE_WORDS


def _parse_int(raw: Optional[str], field: str, *, required: bool) -> Optional[int]:
    text = (raw or "").strip()
    if not text:
        if required:
            raise ValueError(f"{field} is required")
        return None
    try:
        return int(float(text))
    except ValueError as exc:
        raise ValueError(f"{field} must be a whole number, got {text!r}") from exc


def _parse_float(raw: Optional[str], field: str) -> float:
    text = (raw or "").strip()
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"{field} must be a number, got {text!r}") from exc


def _parse_date(raw: Optional[str]) -> date:
    text = (raw or "").strip()
    if not text:
        return date.today()
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise ValueError(f"submission_date must be YYYY-MM-DD, got {text!r}") from exc


def parse_fafsa_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Validate one CSV row into ``import_fafsa_data`` keyword arguments."""
    cleaned = {(k or "").strip().lower(): v for k, v in row.items()}
    academic_year = (cleaned.get("academic_year") or "").strip()
    if not academic_year:
        raise ValueError("academic_year is required")
    return {
        "student_id": _parse_int(cleaned.get("student_id"), "student_id", required=True),
        "academic_year": academic_year,
        "efc": _parse_int(cleaned.get("efc"), "efc", required=True),
        "submission_date": _parse_date(cleaned.get("submission_date")),
        "sai": _parse_int(cleaned.get("sai"), "sai", required=False),
        "dependency_status": (cleaned.get("dependency_status") or "").strip() or "dependent",
        "pell_eligible": _parse_bool(cleaned.get("pell_eligible")),
        "pell_amount": _parse_float(cleaned.get("pell_amount"), "pell_amount"),
    }


def import_fafsa_file(path: str, manager=None) -> Dict[str, Any]:
    """Import every row of the CSV at ``path``.

    Returns ``{"imported": n, "failed": n, "errors": [str, ...]}``. A bad row
    is reported and skipped; it never stops the rest of the file.
    """
    summary: Dict[str, Any] = {"imported": 0, "failed": 0, "errors": []}
    if manager is None:
        from education_system.systems.university.domains.finance.domain.services.financial_aid.aid_manager import (
            FinancialAidManager,
        )

        manager = FinancialAidManager()

    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        headers = _clean_headers(reader.fieldnames)
        missing = [col for col in REQUIRED_COLUMNS if col not in headers]
        if missing:
            summary["errors"].append(f"Missing required column(s): {', '.join(missing)}")
            return summary
        for line_no, row in enumerate(reader, start=2):
            try:
                record = parse_fafsa_row(row)
                if manager.import_fafsa_data(**record) is None:
                    raise ValueError("database rejected the record")
                summary["imported"] += 1
            except (ValueError, TypeError) as exc:
                summary["failed"] += 1
                summary["errors"].append(f"Line {line_no}: {exc}")
    return summary


__all__ = ["REQUIRED_COLUMNS", "OPTIONAL_COLUMNS", "parse_fafsa_row", "import_fafsa_file"]
