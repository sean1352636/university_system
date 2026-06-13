"""Bulk operations data layer for the Secondary School System.

Provides CSV import/export and bulk update/delete helpers built on top
of the ``pupils`` data layer. Each operation returns a structured
``BulkResult`` so the CLI/GUI can surface counts and per-row errors
without coupling to the raw exceptions.
"""

from __future__ import annotations

import csv
import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from education_system.secondarysch_system.modules.domain.pupils.pupils import pupils as pupils_data
from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
    Pupil, ValidationError, YEAR_GROUPS,
)

logger = logging.getLogger(__name__)

# CSV columns accepted on import. ``year_group`` and the names are
# required; everything else is optional.
IMPORT_COLUMNS: tuple[str, ...] = (
    "first_name", "last_name", "year_group", "form_group",
    "date_of_birth", "phone", "parent_name", "parent_phone", "send_status",
)
REQUIRED_COLUMNS: tuple[str, ...] = ("first_name", "last_name", "year_group")

EXPORT_COLUMNS: tuple[str, ...] = (
    "pupil_id", "first_name", "last_name", "year_group", "form_group",
    "date_of_birth", "email", "phone", "parent_name", "parent_phone",
    "send_status",
)

# Fields the bulk-update helper is willing to set in one go. Keeping
# this tight (vs. exposing every pupil column) avoids accidental
# unique-key collisions (email) and keeps the UI tractable.
BULK_UPDATABLE: tuple[str, ...] = (
    "year_group", "form_group", "send_status",
)


@dataclass
class RowError:
    row_number: int
    message: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class BulkResult:
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    errors: list[RowError] = field(default_factory=list)
    created_ids: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.failed == 0 and self.processed > 0

    def add_error(self, row_number: int, message: str,
                  raw: dict[str, Any] | None = None) -> None:
        self.failed += 1
        self.errors.append(RowError(row_number, message, dict(raw or {})))


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

def _normalise_header(name: str) -> str:
    return (name or "").strip().lower().replace(" ", "_")


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValidationError("CSV file has no header row")
        headers = [_normalise_header(h) for h in reader.fieldnames]
        # Rebuild rows keyed by normalised headers so callers don't care
        # about capitalisation or spacing in the source file.
        rows: list[dict[str, str]] = []
        for raw in reader:
            row = {
                _normalise_header(k): (v or "").strip()
                for k, v in raw.items()
            }
            rows.append(row)
    return headers, rows


def import_pupils_csv(path: str | Path) -> BulkResult:
    """Import pupils from a CSV file.

    The CSV must contain a header row. Required columns:
    ``first_name``, ``last_name``, ``year_group``. Any other columns in
    :data:`IMPORT_COLUMNS` are honoured if present; unknown columns are
    ignored. Each row is validated and inserted via ``create_pupil`` so
    the same rules apply as the single-record path.

    Returns a :class:`BulkResult` with per-row errors collected — the
    operation is not transactional. The caller can decide how to handle
    partial success.
    """
    result = BulkResult()
    p = Path(path)
    if not p.exists():
        raise ValidationError(f"CSV file not found: {p}")
    if not p.is_file():
        raise ValidationError(f"Not a file: {p}")

    try:
        headers, rows = _read_csv(p)
    except csv.Error as e:
        logger.exception("Could not parse CSV %s", p)
        raise ValidationError(f"Could not parse CSV: {e}") from e
    except OSError as e:
        logger.exception("Could not read CSV %s", p)
        raise ValidationError(f"Could not read CSV file: {e}") from e

    missing = [c for c in REQUIRED_COLUMNS if c not in headers]
    if missing:
        raise ValidationError(
            f"CSV is missing required column(s): {', '.join(missing)}"
        )

    logger.info("Bulk import started: %s (%d row(s))", p, len(rows))
    for line_no, row in enumerate(rows, start=2):  # header is row 1
        result.processed += 1
        # Strip to only the columns the data layer knows.
        payload = {k: row.get(k, "") for k in IMPORT_COLUMNS}
        # Skip silently-blank lines so accidental trailing newlines
        # don't show as errors.
        if not any(payload.get(c) for c in REQUIRED_COLUMNS):
            result.processed -= 1
            continue
        try:
            pupil = pupils_data.create_pupil(payload)
        except ValidationError as e:
            logger.warning("Bulk import row %d failed validation: %s",
                           line_no, e)
            result.add_error(line_no, str(e), raw=row)
            continue
        except sqlite3.Error as e:
            logger.exception("Bulk import row %d DB error", line_no)
            result.add_error(line_no, f"Database error: {e}", raw=row)
            continue
        result.succeeded += 1
        result.created_ids.append(pupil.pupil_id)

    logger.info("Bulk import finished: processed=%d succeeded=%d failed=%d",
                result.processed, result.succeeded, result.failed)
    return result


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_pupils_csv(path: str | Path, *,
                      pupils: Iterable[Pupil] | None = None) -> int:
    """Write every pupil (or the supplied iterable) to a CSV file.

    Returns the number of rows written. Creates parent directories if
    needed. Overwrites the target file.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    rows = list(pupils) if pupils is not None else pupils_data.list_pupils()
    try:
        with p.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(EXPORT_COLUMNS))
            writer.writeheader()
            for pupil in rows:
                writer.writerow({c: getattr(pupil, c, "") or ""
                                 for c in EXPORT_COLUMNS})
    except OSError as e:
        logger.exception("Bulk export failed writing %s", p)
        raise ValidationError(f"Could not write CSV: {e}") from e
    logger.info("Bulk export wrote %d row(s) to %s", len(rows), p)
    return len(rows)


# ---------------------------------------------------------------------------
# Bulk update / delete
# ---------------------------------------------------------------------------

def _validate_update_payload(field: str, value: str) -> str | None:
    """Coerce/validate a single field=value pair. Returns the cleaned
    value (or None if the field should be cleared). Raises
    ValidationError for bad input."""
    if field not in BULK_UPDATABLE:
        raise ValidationError(
            f"Field {field!r} is not bulk-updatable. "
            f"Allowed: {', '.join(BULK_UPDATABLE)}"
        )
    v = (value or "").strip()
    if field == "year_group":
        if not v:
            raise ValidationError("Year group cannot be blank")
        if v not in YEAR_GROUPS:
            raise ValidationError(
                f"Year group must be one of {', '.join(YEAR_GROUPS)}"
            )
        return v
    if field == "send_status":
        if not v:
            return None  # clear the flag
        if v.lower() not in ("yes", "no"):
            raise ValidationError("SEND status must be 'yes' or 'no'")
        return v.lower()
    if field == "form_group":
        return v or None
    return v or None


def bulk_update(pupil_ids: Iterable[str], field: str,
                value: str) -> BulkResult:
    """Apply the same field=value update to a list of pupils.

    Each pupil is updated individually so we can collect per-row errors
    without rolling back successful updates. The operation runs through
    ``pupils.update_pupil`` so all the usual validation applies.
    """
    cleaned = _validate_update_payload(field, value)
    ids = [pid.strip() for pid in pupil_ids if pid and pid.strip()]
    result = BulkResult()
    logger.info("bulk_update field=%s value=%r count=%d",
                field, cleaned, len(ids))
    for pid in ids:
        result.processed += 1
        existing = pupils_data.get_pupil(pid)
        if existing is None:
            result.add_error(result.processed, f"No pupil with id {pid}",
                             raw={"pupil_id": pid})
            continue
        payload = {
            "first_name":    existing.first_name,
            "last_name":     existing.last_name,
            "year_group":    existing.year_group,
            "form_group":    existing.form_group,
            "date_of_birth": existing.date_of_birth,
            "phone":         existing.phone,
            "parent_name":   existing.parent_name,
            "parent_phone":  existing.parent_phone,
            "send_status":   existing.send_status,
        }
        payload[field] = cleaned
        try:
            pupils_data.update_pupil(pid, payload)
        except ValidationError as e:
            result.add_error(result.processed, str(e), raw={"pupil_id": pid})
            continue
        except sqlite3.Error as e:
            logger.exception("bulk_update DB error for %s", pid)
            result.add_error(result.processed, f"Database error: {e}",
                             raw={"pupil_id": pid})
            continue
        result.succeeded += 1
    logger.info("bulk_update finished: succeeded=%d failed=%d",
                result.succeeded, result.failed)
    return result


def bulk_delete(pupil_ids: Iterable[str]) -> BulkResult:
    """Delete a list of pupils. Missing ids are reported as errors."""
    ids = [pid.strip() for pid in pupil_ids if pid and pid.strip()]
    result = BulkResult()
    logger.info("bulk_delete count=%d", len(ids))
    for pid in ids:
        result.processed += 1
        try:
            deleted = pupils_data.delete_pupil(pid)
        except sqlite3.Error as e:
            logger.exception("bulk_delete DB error for %s", pid)
            result.add_error(result.processed, f"Database error: {e}",
                             raw={"pupil_id": pid})
            continue
        if not deleted:
            result.add_error(result.processed, f"No pupil with id {pid}",
                             raw={"pupil_id": pid})
            continue
        result.succeeded += 1
    logger.info("bulk_delete finished: succeeded=%d failed=%d",
                result.succeeded, result.failed)
    return result
