"""Domain layer for Bottle Feeds (Nursery System).

Owns the ``bottle_feeds`` table — the milk-feed log for babies. Each record
captures the milk type (formula / expressed breast milk / cow's milk / water),
the amount offered vs taken, whether the temperature was checked and the baby
winded, plus the staff member who gave the feed.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``bottle_feeds_cli.py``, Tk GUI in ``bottle_feeds_views.py``.
"""

from __future__ import annotations

import datetime as _dt
import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.nursery.infrastructure.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Bottle Feeds"
CATEGORY = "Daily Care & Routines"

ID_PREFIX = "NBF"
ID_DIGITS = 3

MILK_TYPES = ("Formula", "Expressed breast milk", "Cow's milk", "Water", "Other")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid bottle-feed input."""


@dataclass
class BottleFeed:
    feed_id: str
    pupil_id: str
    feed_date: str
    feed_time: str | None
    milk_type: str
    offered_ml: int | None
    taken_ml: int | None
    temperature_checked: int
    winded: int
    staff_id: str | None
    notes: str | None
    child_name: str | None = None
    staff_name: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for bottle feeds")
        raise


_SELECT = """
SELECT b.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       TRIM(s.first_name || ' ' || s.last_name) AS staff_name
FROM bottle_feeds b
LEFT JOIN pupils p ON p.pupil_id = b.pupil_id
LEFT JOIN staff  s ON s.staff_id = b.staff_id
"""


def _row(r: sqlite3.Row) -> BottleFeed:
    keys = r.keys()
    return BottleFeed(
        feed_id=r["feed_id"],
        pupil_id=r["pupil_id"],
        feed_date=r["feed_date"],
        feed_time=r["feed_time"],
        milk_type=r["milk_type"],
        offered_ml=r["offered_ml"],
        taken_ml=r["taken_ml"],
        temperature_checked=int(r["temperature_checked"]),
        winded=int(r["winded"]),
        staff_id=r["staff_id"],
        notes=r["notes"],
        child_name=r["child_name"] if "child_name" in keys else None,
        staff_name=r["staff_name"] if "staff_name" in keys else None,
    )


# ── Validation ───────────────────────────────────────────────────────────────

def _opt(value: str | None) -> str | None:
    v = (value or "").strip()
    return v or None


def _coerce_bool(value: Any, default: int) -> int:
    if value is None or (isinstance(value, str) and not value.strip()):
        return default
    if isinstance(value, (bool, int)):
        return int(bool(value))
    return int(str(value).strip().lower() in ("1", "y", "yes", "true", "on"))


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


def _validate(data: dict[str, Any], *, require_pupil: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if require_pupil:
        pid = (data.get("pupil_id") or "").strip()
        if not pid:
            raise ValidationError("Child (pupil ID) is required")
        out["pupil_id"] = pid

    feed_date = (data.get("feed_date") or "").strip() or _dt.date.today().isoformat()
    if not _DATE_RE.match(feed_date):
        raise ValidationError("Feed date must be YYYY-MM-DD")
    out["feed_date"] = feed_date

    feed_time = (data.get("feed_time") or "").strip()
    if feed_time and not _TIME_RE.match(feed_time):
        raise ValidationError("Feed time must be HH:MM")
    out["feed_time"] = feed_time or None

    milk_type = (data.get("milk_type") or "Formula").strip() or "Formula"
    if milk_type not in MILK_TYPES:
        raise ValidationError("Milk type must be one of: " + ", ".join(MILK_TYPES))
    out["milk_type"] = milk_type

    out["offered_ml"] = _opt_int(data.get("offered_ml"), "Offered ml")
    out["taken_ml"] = _opt_int(data.get("taken_ml"), "Taken ml")

    out["temperature_checked"] = _coerce_bool(data.get("temperature_checked"), 1)
    out["winded"] = _coerce_bool(data.get("winded"), 0)

    out["staff_id"] = _opt(data.get("staff_id"))
    out["notes"] = _opt(data.get("notes"))
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_record_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT feed_id FROM bottle_feeds").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing bottle-feed ids")
        raise
    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"
    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        rid = f"{ID_PREFIX}{n}"
        if rid not in existing:
            return rid
    raise RuntimeError("Could not allocate a unique bottle-feed id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_records(*, feed_date: str | None = None,
                 pupil_id: str | None = None) -> list[BottleFeed]:
    _ensure_schema()
    sql = _SELECT
    clauses: list[str] = []
    params: list[Any] = []
    if feed_date:
        clauses.append("b.feed_date = ?")
        params.append(feed_date.strip())
    if pupil_id:
        clauses.append("b.pupil_id = ?")
        params.append(pupil_id.strip())
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY b.feed_date DESC, b.feed_time DESC, b.feed_id DESC"
    try:
        with connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_records failed")
        raise
    return [_row(r) for r in rows]


def get_record(feed_id: str) -> BottleFeed | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE b.feed_id = ?", (feed_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_record(%s) failed", feed_id)
        raise
    return _row(row) if row else None


def list_pupil_choices() -> list[tuple[str, str]]:
    """Return ``(pupil_id, "Name (id) — room")`` pairs for child pickers."""
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
    """Return ``(staff_id, "Name (id) — role")`` pairs for staff pickers."""
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT staff_id, first_name, last_name, role FROM staff "
                "WHERE end_date IS NULL OR end_date = '' "
                "ORDER BY last_name, first_name").fetchall()
    except sqlite3.Error:
        logger.exception("list_staff_choices failed")
        raise
    out = []
    for r in rows:
        role = f" — {r['role']}" if r["role"] else ""
        out.append((r["staff_id"],
                    f"{r['first_name']} {r['last_name']} ({r['staff_id']}){role}"))
    return out


# ── Writes ───────────────────────────────────────────────────────────────────

def create_record(data: dict[str, Any]) -> BottleFeed:
    _ensure_schema()
    payload = _validate(data, require_pupil=True)
    rid = generate_record_id()
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM pupils WHERE pupil_id = ?",
                                (payload["pupil_id"],)).fetchone():
                raise ValidationError(
                    f"No child on roll with id {payload['pupil_id']}")
            conn.execute(
                """
                INSERT INTO bottle_feeds (
                    feed_id, pupil_id, feed_date, feed_time, milk_type,
                    offered_ml, taken_ml, temperature_checked, winded,
                    staff_id, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (rid, payload["pupil_id"], payload["feed_date"],
                 payload["feed_time"], payload["milk_type"],
                 payload["offered_ml"], payload["taken_ml"],
                 payload["temperature_checked"], payload["winded"],
                 payload["staff_id"], payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for bottle-feed id=%s", rid)
        raise ValidationError(f"Could not create record — {e}") from e
    rec = get_record(rid)
    assert rec is not None
    logger.info("Created bottle-feed record %s for pupil %s",
                rid, payload["pupil_id"])
    return rec


def update_record(feed_id: str, data: dict[str, Any]) -> BottleFeed:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    existing = get_record(feed_id)
    if existing is None:
        raise ValidationError(f"No bottle-feed record with id {feed_id}")
    try:
        with connect() as conn:
            conn.execute(
                """
                UPDATE bottle_feeds SET
                    feed_date = ?, feed_time = ?, milk_type = ?,
                    offered_ml = ?, taken_ml = ?, temperature_checked = ?,
                    winded = ?, staff_id = ?, notes = ?
                WHERE feed_id = ?
                """,
                (payload["feed_date"], payload["feed_time"],
                 payload["milk_type"], payload["offered_ml"],
                 payload["taken_ml"], payload["temperature_checked"],
                 payload["winded"], payload["staff_id"], payload["notes"],
                 feed_id),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for bottle-feed id=%s", feed_id)
        raise ValidationError(f"Could not update record — {e}") from e
    rec = get_record(feed_id)
    assert rec is not None
    logger.info("Updated bottle-feed record %s", feed_id)
    return rec


def delete_record(feed_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM bottle_feeds WHERE feed_id = ?", (feed_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting bottle-feed id=%s", feed_id)
        raise
    if deleted:
        logger.info("Deleted bottle-feed record %s", feed_id)
    return deleted
