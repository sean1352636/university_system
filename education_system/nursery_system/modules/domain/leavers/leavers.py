"""Domain layer for Leavers (Nursery System).

Owns the ``leavers`` table — children who have left the setting. Records the
leaving date, last day attended, reason and destination. Recording a leaver also
flips the child's ``pupils.status`` to 'left' so they drop off the active roll;
reinstating one puts them back to 'active' and removes the leaver record.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``leavers_cli.py``, Tk GUI in ``leavers_views.py``.
"""

from __future__ import annotations

import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.nursery_system.core.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Leavers"
CATEGORY = "Children & Admissions"

ID_PREFIX = "NLV"
ID_DIGITS = 3

REASONS = (
    "Moved to school", "Relocated", "Moved to other provider",
    "Parent choice", "Funding ended", "Withdrawn", "Other",
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid leaver input."""


@dataclass
class Leaver:
    leaver_id: str
    pupil_id: str
    leaving_date: str | None
    last_day_attended: str | None
    reason: str | None
    destination: str | None
    records_transferred: bool
    notes: str | None
    child_name: str | None = None
    room: str | None = None
    pupil_status: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for leavers")
        raise


_SELECT = """
SELECT lv.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       p.room AS room,
       p.status AS pupil_status
FROM leavers lv
LEFT JOIN pupils p ON p.pupil_id = lv.pupil_id
"""


def _row(r: sqlite3.Row) -> Leaver:
    keys = r.keys()
    return Leaver(
        leaver_id=r["leaver_id"],
        pupil_id=r["pupil_id"],
        leaving_date=r["leaving_date"],
        last_day_attended=r["last_day_attended"],
        reason=r["reason"],
        destination=r["destination"],
        records_transferred=bool(r["records_transferred"]),
        notes=r["notes"],
        child_name=r["child_name"] if "child_name" in keys else None,
        room=r["room"] if "room" in keys else None,
        pupil_status=r["pupil_status"] if "pupil_status" in keys else None,
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


def _as_bool(value: Any) -> int:
    if isinstance(value, (bool, int)):
        return int(bool(value))
    return int(str(value or "").strip().lower() in ("1", "y", "yes", "true", "on"))


def _validate(data: dict[str, Any], *, require_pupil: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if require_pupil:
        pid = (data.get("pupil_id") or "").strip()
        if not pid:
            raise ValidationError("Child (pupil ID) is required")
        out["pupil_id"] = pid

    out["leaving_date"] = _opt_date(data.get("leaving_date"), "Leaving date")
    out["last_day_attended"] = _opt_date(data.get("last_day_attended"),
                                         "Last day attended")
    reason = (data.get("reason") or "").strip()
    if reason and reason not in REASONS:
        raise ValidationError("Reason must be one of: " + ", ".join(REASONS))
    out["reason"] = reason or None
    out["destination"] = _opt(data.get("destination"))
    out["records_transferred"] = _as_bool(data.get("records_transferred"))
    out["notes"] = _opt(data.get("notes"))
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_leaver_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT leaver_id FROM leavers").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing leaver ids")
        raise
    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"
    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        lid = f"{ID_PREFIX}{n}"
        if lid not in existing:
            return lid
    raise RuntimeError("Could not allocate a unique leaver id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_leavers() -> list[Leaver]:
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                _SELECT + " ORDER BY lv.leaving_date DESC, lv.leaver_id DESC"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("list_leavers failed")
        raise
    return [_row(r) for r in rows]


def get_leaver(leaver_id: str) -> Leaver | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE lv.leaver_id = ?", (leaver_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_leaver(%s) failed", leaver_id)
        raise
    return _row(row) if row else None


def list_active_pupil_choices() -> list[tuple[str, str]]:
    """Active children (still on roll) — candidates for becoming a leaver."""
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT pupil_id, first_name, last_name, room FROM pupils "
                "WHERE status = 'active' ORDER BY last_name, first_name").fetchall()
    except sqlite3.Error:
        logger.exception("list_active_pupil_choices failed")
        raise
    out = []
    for r in rows:
        room = f" — {r['room']}" if r["room"] else ""
        out.append((r["pupil_id"],
                    f"{r['first_name']} {r['last_name']} ({r['pupil_id']}){room}"))
    return out


# ── Writes ───────────────────────────────────────────────────────────────────

def record_leaver(data: dict[str, Any]) -> Leaver:
    """Record a child leaving and take them off the active roll."""
    _ensure_schema()
    payload = _validate(data, require_pupil=True)
    lid = generate_leaver_id()
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM pupils WHERE pupil_id = ?",
                                (payload["pupil_id"],)).fetchone():
                raise ValidationError(
                    f"No child on roll with id {payload['pupil_id']}")
            conn.execute(
                """
                INSERT INTO leavers (
                    leaver_id, pupil_id, leaving_date, last_day_attended,
                    reason, destination, records_transferred, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (lid, payload["pupil_id"], payload["leaving_date"],
                 payload["last_day_attended"], payload["reason"],
                 payload["destination"], payload["records_transferred"],
                 payload["notes"]),
            )
            conn.execute("UPDATE pupils SET status = 'left' WHERE pupil_id = ?",
                         (payload["pupil_id"],))
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for leaver id=%s", lid)
        raise ValidationError(f"Could not record leaver — {e}") from e
    lv = get_leaver(lid)
    assert lv is not None
    logger.info("Recorded leaver %s for pupil %s; child taken off roll",
                lid, payload["pupil_id"])
    return lv


def update_leaver(leaver_id: str, data: dict[str, Any]) -> Leaver:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    try:
        with connect() as conn:
            cur = conn.execute(
                """
                UPDATE leavers SET
                    leaving_date = ?, last_day_attended = ?, reason = ?,
                    destination = ?, records_transferred = ?, notes = ?
                WHERE leaver_id = ?
                """,
                (payload["leaving_date"], payload["last_day_attended"],
                 payload["reason"], payload["destination"],
                 payload["records_transferred"], payload["notes"], leaver_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No leaver with id {leaver_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for leaver id=%s", leaver_id)
        raise ValidationError(f"Could not update leaver — {e}") from e
    lv = get_leaver(leaver_id)
    assert lv is not None
    logger.info("Updated leaver %s", leaver_id)
    return lv


def delete_leaver(leaver_id: str) -> bool:
    """Remove a leaver record. Does not change the child's roll status."""
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM leavers WHERE leaver_id = ?", (leaver_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting leaver id=%s", leaver_id)
        raise
    if deleted:
        logger.info("Deleted leaver record %s", leaver_id)
    return deleted


def reinstate(leaver_id: str) -> str:
    """Reverse a leaver: put the child back on the active roll, drop the record.

    Returns the reinstated ``pupil_id``.
    """
    _ensure_schema()
    lv = get_leaver(leaver_id)
    if lv is None:
        raise ValidationError(f"No leaver with id {leaver_id}")
    try:
        with connect() as conn:
            conn.execute("UPDATE pupils SET status = 'active' WHERE pupil_id = ?",
                         (lv.pupil_id,))
            conn.execute("DELETE FROM leavers WHERE leaver_id = ?", (leaver_id,))
            conn.commit()
    except sqlite3.Error:
        logger.exception("Database error reinstating leaver id=%s", leaver_id)
        raise
    logger.info("Reinstated leaver %s -> pupil %s back on roll",
                leaver_id, lv.pupil_id)
    return lv.pupil_id
