"""Domain layer for 2-Year-Old Progress Check (Nursery System).

Owns the ``progress_check_2yr`` table — the statutory EYFS progress check
completed at approximately two years of age. Records the three prime areas
(communication & language, physical development, personal-social-emotional),
a summary and sharing flags for parents and the health visitor.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``progress_check_2yr_cli.py``, Tk GUI in ``progress_check_2yr_views.py``.
"""

from __future__ import annotations

import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.nursery.infrastructure.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "2-Year-Old Progress Check"
CATEGORY = "EYFS Learning & Development"

ID_PREFIX = "NP2"
ID_DIGITS = 3

STATUSES = ("draft", "finalised")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid progress-check input."""


@dataclass
class ProgressCheck:
    check_id: str
    pupil_id: str
    check_date: str | None
    age_months: int | None
    comm_language: str | None
    physical_development: str | None
    pse_development: str | None
    summary: str | None
    strengths: str | None
    areas_of_concern: str | None
    shared_with_parents: bool
    shared_with_hv: bool
    staff_id: str | None
    status: str | None
    created_at: str | None
    child_name: str | None = None
    room: str | None = None
    staff_name: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for 2-year-old progress check")
        raise


_SELECT = """
SELECT pc.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       p.room AS room,
       TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, ''))
           AS staff_name
FROM progress_check_2yr pc
LEFT JOIN pupils p ON p.pupil_id = pc.pupil_id
LEFT JOIN staff s ON s.staff_id = pc.staff_id
"""


def _row(r: sqlite3.Row) -> ProgressCheck:
    keys = r.keys()
    return ProgressCheck(
        check_id=r["check_id"],
        pupil_id=r["pupil_id"],
        check_date=r["check_date"],
        age_months=r["age_months"],
        comm_language=r["comm_language"],
        physical_development=r["physical_development"],
        pse_development=r["pse_development"],
        summary=r["summary"],
        strengths=r["strengths"],
        areas_of_concern=r["areas_of_concern"],
        shared_with_parents=bool(r["shared_with_parents"]),
        shared_with_hv=bool(r["shared_with_hv"]),
        staff_id=r["staff_id"],
        status=r["status"],
        created_at=r["created_at"],
        child_name=r["child_name"] if "child_name" in keys else None,
        room=r["room"] if "room" in keys else None,
        staff_name=(r["staff_name"] or None) if "staff_name" in keys else None,
    )


# ── Validation ───────────────────────────────────────────────────────────────

def _opt(value: str | None) -> str | None:
    v = (value or "").strip()
    return v or None


def _opt_date(value: str | None, label: str) -> str | None:
    v = (value or "").strip()
    if v and not _DATE_RE.match(v):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return v or None


def _opt_int(value: Any, label: str) -> int | None:
    raw = str(value if value is not None else "").strip()
    if not raw:
        return None
    try:
        n = int(raw)
    except ValueError as e:
        raise ValidationError(f"{label} must be a whole number") from e
    if n < 0:
        raise ValidationError(f"{label} cannot be negative")
    return n


def _as_bool(value: Any) -> int:
    if isinstance(value, str):
        return 1 if value.strip().lower() in ("1", "y", "yes", "true", "on") else 0
    return 1 if value else 0


def _validate(data: dict[str, Any], *, require_pupil: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if require_pupil:
        pid = (data.get("pupil_id") or "").strip()
        if not pid:
            raise ValidationError("Child (pupil ID) is required")
        out["pupil_id"] = pid

    out["check_date"] = _opt_date(data.get("check_date"), "Check date")
    out["age_months"] = _opt_int(data.get("age_months"), "Age (months)")
    out["comm_language"] = _opt(data.get("comm_language"))
    out["physical_development"] = _opt(data.get("physical_development"))
    out["pse_development"] = _opt(data.get("pse_development"))
    out["summary"] = _opt(data.get("summary"))
    out["strengths"] = _opt(data.get("strengths"))
    out["areas_of_concern"] = _opt(data.get("areas_of_concern"))
    out["shared_with_parents"] = _as_bool(data.get("shared_with_parents"))
    out["shared_with_hv"] = _as_bool(data.get("shared_with_hv"))
    out["staff_id"] = _opt(data.get("staff_id"))

    status = (data.get("status") or "").strip()
    if status and status not in STATUSES:
        raise ValidationError("Status must be one of: " + ", ".join(STATUSES))
    out["status"] = status or "draft"

    return out


# ── ID allocation ─────────────────────────────────────────────────────────────

def generate_check_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT check_id FROM progress_check_2yr").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing progress-check-2yr ids")
        raise
    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"
    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        cid = f"{ID_PREFIX}{n}"
        if cid not in existing:
            return cid
    raise RuntimeError("Could not allocate a unique progress-check-2yr id")


# ── Reads ─────────────────────────────────────────────────────────────────────

def list_checks(*, pupil_id: str | None = None) -> list[ProgressCheck]:
    _ensure_schema()
    sql = _SELECT
    params: list[Any] = []
    if pupil_id:
        sql += " WHERE pc.pupil_id = ?"
        params.append(pupil_id)
    sql += " ORDER BY pc.check_date DESC, pc.check_id DESC"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_checks failed")
        raise
    return [_row(r) for r in rows]


def get_check(check_id: str) -> ProgressCheck | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE pc.check_id = ?", (check_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_check(%s) failed", check_id)
        raise
    return _row(row) if row else None


def list_pupil_choices() -> list[tuple[str, str]]:
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT pupil_id, first_name, last_name, room FROM pupils "
                "WHERE status = 'active' ORDER BY last_name, first_name").fetchall()
    except sqlite3.Error:
        logger.exception("list_pupil_choices failed")
        raise
    out = []
    for r in rows:
        room = f" — {r['room']}" if r["room"] else ""
        out.append((r["pupil_id"],
                    f"{r['first_name']} {r['last_name']} ({r['pupil_id']}){room}"))
    return out


def list_staff_choices() -> list[tuple[str, str]]:
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT staff_id, first_name, last_name FROM staff "
                "ORDER BY last_name, first_name").fetchall()
    except sqlite3.Error:
        logger.exception("list_staff_choices failed")
        raise
    return [(r["staff_id"], f"{r['first_name']} {r['last_name']} ({r['staff_id']})")
            for r in rows]


# ── Writes ────────────────────────────────────────────────────────────────────

def create_check(data: dict[str, Any]) -> ProgressCheck:
    _ensure_schema()
    payload = _validate(data, require_pupil=True)
    cid = generate_check_id()
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM pupils WHERE pupil_id = ?",
                                (payload["pupil_id"],)).fetchone():
                raise ValidationError(
                    f"No child on roll with id {payload['pupil_id']}")
            conn.execute(
                """
                INSERT INTO progress_check_2yr (
                    check_id, pupil_id, check_date, age_months,
                    comm_language, physical_development, pse_development,
                    summary, strengths, areas_of_concern,
                    shared_with_parents, shared_with_hv, staff_id, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (cid, payload["pupil_id"], payload["check_date"],
                 payload["age_months"], payload["comm_language"],
                 payload["physical_development"], payload["pse_development"],
                 payload["summary"], payload["strengths"],
                 payload["areas_of_concern"], payload["shared_with_parents"],
                 payload["shared_with_hv"], payload["staff_id"], payload["status"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for progress-check-2yr id=%s", cid)
        raise ValidationError(f"Could not create progress check — {e}") from e
    c = get_check(cid)
    assert c is not None
    logger.info("Created 2-year-old progress check %s for pupil %s",
                cid, payload["pupil_id"])
    return c


def update_check(check_id: str, data: dict[str, Any]) -> ProgressCheck:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    existing = get_check(check_id)
    if existing is None:
        raise ValidationError(f"No progress check with id {check_id}")
    try:
        with connect() as conn:
            cur = conn.execute(
                """
                UPDATE progress_check_2yr SET
                    check_date = ?, age_months = ?,
                    comm_language = ?, physical_development = ?, pse_development = ?,
                    summary = ?, strengths = ?, areas_of_concern = ?,
                    shared_with_parents = ?, shared_with_hv = ?,
                    staff_id = ?, status = ?
                WHERE check_id = ?
                """,
                (payload["check_date"], payload["age_months"],
                 payload["comm_language"], payload["physical_development"],
                 payload["pse_development"], payload["summary"],
                 payload["strengths"], payload["areas_of_concern"],
                 payload["shared_with_parents"], payload["shared_with_hv"],
                 payload["staff_id"], payload["status"], check_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No progress check with id {check_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for progress-check-2yr id=%s", check_id)
        raise ValidationError(f"Could not update progress check — {e}") from e
    c = get_check(check_id)
    assert c is not None
    logger.info("Updated 2-year-old progress check %s", check_id)
    return c


def delete_check(check_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM progress_check_2yr WHERE check_id = ?", (check_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting progress-check-2yr id=%s", check_id)
        raise
    if deleted:
        logger.info("Deleted 2-year-old progress check %s", check_id)
    return deleted
