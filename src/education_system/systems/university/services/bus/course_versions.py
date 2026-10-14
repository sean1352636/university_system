"""Effective-dated versions of a course's catalogue entry.

Programmes already have ``programme_versions``, ``programme_amendments`` and
``programme_approvals``. Courses had only ``course_history`` — a field-level
change log (one row in it) that records *that* ``credits`` changed but cannot
reconstruct the entry a student was admitted under. So "what were this
course's credits and outcomes in 2024/25?" had no answer.

This module snapshots the whole catalogue entry, dated:

* ``snapshot_course`` captures the current row (plus its learning outcomes and
  assessment components) as a new version, effective from a date.
* ``course_as_of`` returns the version in force on a date or in an academic
  year — the question the audit trail could not answer.
* ``diff_versions`` shows what changed between two of them.

The snapshot is a JSON blob rather than a mirrored set of columns on purpose:
``courses`` has 31 columns and an unfinished rename among them, and a version
table that had to track that shape would need migrating every time the live
table moved. A blob keeps history readable even after the live schema changes.

Versions are closed on supersession: writing version N sets version N-1's
``effective_to`` to the day before, so exactly one version is in force on any
date and ``course_as_of`` is a simple range query.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any, Optional

from education_system.systems.university.infrastructure.database.db import (
    sqlite3,
    get_connection,
)

logger = logging.getLogger(__name__)

#: Catalogue fields worth versioning. Deliberately not "every column":
#: counters and timestamps (``current_enrollment``, ``updated_at``) are state,
#: not catalogue content, and would produce a new version on every enrolment.
VERSIONED_FIELDS = (
    "course_code", "course_name", "description", "department", "level",
    "credit_hours", "credits", "contact_hours_per_week", "duration",
    "course_type", "status", "max_enrollment", "course_fee", "lab_required",
    "online_available", "learning_outcomes", "assessment_methods",
    "required_textbooks", "min_ucas_tariff", "tags", "availability_periods",
)

_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS course_versions (
        version_id     INTEGER PRIMARY KEY AUTOINCREMENT,
        course_code    TEXT NOT NULL,
        version_no     INTEGER NOT NULL,
        academic_year  TEXT NOT NULL DEFAULT '',
        effective_from TEXT NOT NULL,
        effective_to   TEXT,
        snapshot       TEXT NOT NULL,
        change_reason  TEXT,
        created_by     TEXT,
        created_at     TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (course_code, version_no)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_course_versions_lookup "
    "ON course_versions (course_code, effective_from)",
)


def ensure_schema(conn=None) -> bool:
    """Create the version table. Idempotent."""
    own = conn is None
    try:
        if own:
            conn = get_connection()
        for stmt in _SCHEMA:
            conn.execute(stmt)
        conn.commit()
        return True
    except Exception as exc:
        logger.warning("course version schema init failed: %s", exc)
        return False
    finally:
        if own and conn is not None:
            try:
                conn.close()
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------

def _course_row(conn, course_code: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM courses WHERE COALESCE(NULLIF(TRIM(course_code), ''), code) = ? "
        "OR code = ? LIMIT 1",
        (course_code, course_code),
    ).fetchone()
    if row is None:
        return None
    if hasattr(row, "keys"):
        return {k: row[k] for k in row.keys()}
    return None


def build_snapshot(conn, course_code: str) -> Optional[dict[str, Any]]:
    """The catalogue content of *course_code* right now.

    Includes the structured outcomes and assessment components, which live in
    their own tables and are as much a part of "what this course was" as the
    credit value.
    """
    row = _course_row(conn, course_code)
    if row is None:
        return None
    snapshot: dict[str, Any] = {
        field: row.get(field) for field in VERSIONED_FIELDS if field in row
    }
    snapshot["learning_outcomes_detail"] = _fetch(
        conn, "SELECT outcome_code, description FROM course_learning_outcomes "
              "WHERE course_code = ? ORDER BY outcome_code", course_code)
    snapshot["assessment_components"] = _fetch(
        conn, "SELECT name, weight, notes FROM course_assessment_components "
              "WHERE course_code = ? ORDER BY name", course_code)
    snapshot["modules"] = [
        r["module_code"] if hasattr(r, "keys") else r[0]
        for r in _rows(conn, "SELECT DISTINCT module_code FROM course_curriculum "
                             "WHERE course_code = ? ORDER BY module_code", course_code)
    ]
    return snapshot


def _rows(conn, sql: str, *params):
    try:
        return conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        return []


def _fetch(conn, sql: str, *params) -> list[dict]:
    out = []
    for r in _rows(conn, sql, *params):
        out.append({k: r[k] for k in r.keys()} if hasattr(r, "keys") else list(r))
    return out


def snapshot_course(course_code: str, *, effective_from: Optional[str] = None,
                    academic_year: str = "", change_reason: str = "",
                    created_by: Optional[str] = None,
                    skip_if_unchanged: bool = True, conn=None) -> Optional[int]:
    """Record the course's current catalogue entry as a new version.

    Returns the new version number, or None when nothing was written —
    including the common case where the entry is identical to the version
    already in force, so calling this on every save does not fill the table
    with duplicates.
    """
    own = conn is None
    try:
        if own:
            conn = get_connection()
        ensure_schema(conn)
        snapshot = build_snapshot(conn, course_code)
        if snapshot is None:
            logger.info("snapshot_course: no course %r", course_code)
            return None

        latest = _latest_version(conn, course_code)
        if skip_if_unchanged and latest and latest["snapshot"] == snapshot:
            return None

        effective = effective_from or date.today().isoformat()
        version_no = (latest["version_no"] + 1) if latest else 1

        if latest:
            # Close the outgoing version the day before this one starts, so
            # exactly one version is in force on any given date.
            previous_end = _day_before(effective)
            conn.execute(
                "UPDATE course_versions SET effective_to = ? "
                "WHERE course_code = ? AND version_no = ?",
                (previous_end, course_code, latest["version_no"]),
            )

        conn.execute(
            "INSERT INTO course_versions (course_code, version_no, academic_year, "
            "effective_from, effective_to, snapshot, change_reason, created_by) "
            "VALUES (?,?,?,?,NULL,?,?,?)",
            (course_code, version_no, academic_year, effective,
             json.dumps(snapshot, default=str, sort_keys=True),
             change_reason, str(created_by) if created_by else None),
        )
        conn.commit()
        return version_no
    except Exception as exc:
        logger.warning("snapshot_course(%s) failed: %s", course_code, exc)
        return None
    finally:
        if own and conn is not None:
            try:
                conn.close()
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)


def _day_before(iso_date: str) -> str:
    try:
        return (date.fromisoformat(iso_date[:10]) - timedelta(days=1)).isoformat()
    except ValueError:
        return iso_date


def _latest_version(conn, course_code: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT version_id, version_no, academic_year, effective_from, effective_to, "
        "snapshot FROM course_versions WHERE course_code = ? "
        "ORDER BY version_no DESC LIMIT 1",
        (course_code,),
    ).fetchone()
    return _row_to_version(row) if row else None


def _row_to_version(row) -> dict:
    keys = ("version_id", "version_no", "academic_year", "effective_from",
            "effective_to", "snapshot")
    data = {k: row[k] for k in keys} if hasattr(row, "keys") else dict(zip(keys, row))
    try:
        data["snapshot"] = json.loads(data["snapshot"])
    except (TypeError, ValueError):
        data["snapshot"] = {}
    return data


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def course_as_of(course_code: str, *, when=None, academic_year: Optional[str] = None,
                 conn=None) -> Optional[dict]:
    """The version of *course_code* in force on a date, or for a year.

    ``academic_year`` matches the label a version was filed under ("2024/25");
    ``when`` matches by effective date range. With neither, the current
    version is returned.
    """
    own = conn is None
    try:
        if own:
            conn = get_connection()
        ensure_schema(conn)
        if academic_year:
            row = conn.execute(
                "SELECT version_id, version_no, academic_year, effective_from, "
                "effective_to, snapshot FROM course_versions "
                "WHERE course_code = ? AND academic_year = ? "
                "ORDER BY version_no DESC LIMIT 1",
                (course_code, academic_year),
            ).fetchone()
            return _row_to_version(row) if row else None

        target = _as_iso(when) or date.today().isoformat()
        row = conn.execute(
            "SELECT version_id, version_no, academic_year, effective_from, "
            "effective_to, snapshot FROM course_versions "
            "WHERE course_code = ? AND effective_from <= ? "
            "AND (effective_to IS NULL OR effective_to >= ?) "
            "ORDER BY version_no DESC LIMIT 1",
            (course_code, target, target),
        ).fetchone()
        return _row_to_version(row) if row else None
    except Exception as exc:
        logger.warning("course_as_of(%s) failed: %s", course_code, exc)
        return None
    finally:
        if own and conn is not None:
            try:
                conn.close()
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)


def _as_iso(when) -> Optional[str]:
    if when is None:
        return None
    if isinstance(when, (date, datetime)):
        return when.date().isoformat() if isinstance(when, datetime) else when.isoformat()
    return str(when)[:10]


def list_versions(course_code: str, *, conn=None) -> list[dict]:
    """Every recorded version of a course, newest first."""
    own = conn is None
    try:
        if own:
            conn = get_connection()
        ensure_schema(conn)
        rows = conn.execute(
            "SELECT version_id, version_no, academic_year, effective_from, "
            "effective_to, snapshot, change_reason, created_by, created_at "
            "FROM course_versions WHERE course_code = ? ORDER BY version_no DESC",
            (course_code,),
        ).fetchall()
    except Exception as exc:
        logger.warning("list_versions(%s) failed: %s", course_code, exc)
        return []
    finally:
        if own and conn is not None:
            try:
                conn.close()
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

    out = []
    for row in rows:
        entry = _row_to_version(row)
        for extra in ("change_reason", "created_by", "created_at"):
            entry[extra] = row[extra] if hasattr(row, "keys") else None
        out.append(entry)
    return out


def diff_versions(course_code: str, version_a: int, version_b: int,
                  *, conn=None) -> dict[str, dict[str, Any]]:
    """Fields that differ between two versions: ``{field: {from, to}}``."""
    versions = {v["version_no"]: v for v in list_versions(course_code, conn=conn)}
    a, b = versions.get(version_a), versions.get(version_b)
    if not a or not b:
        return {}
    snap_a, snap_b = a["snapshot"], b["snapshot"]
    changed: dict[str, dict[str, Any]] = {}
    for field in sorted(set(snap_a) | set(snap_b)):
        old, new = snap_a.get(field), snap_b.get(field)
        if old != new:
            changed[field] = {"from": old, "to": new}
    return changed
