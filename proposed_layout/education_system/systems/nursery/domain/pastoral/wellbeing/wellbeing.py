"""Domain layer for Wellbeing (Nursery System).

Owns the ``wellbeing_records`` table, created on demand inside the shared nursery DB.
Follows the 4-layer pattern: validation + SQLite access here, CLI in
``wellbeing_cli.py``, Tk GUI in ``wellbeing_views.py``.
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

FEATURE_NAME = "Wellbeing"
CATEGORY = "Safeguarding & Welfare"

ID_PREFIX = "NWB"
ID_DIGITS = 3

SUBJECT_TYPES = ('Child', 'Staff',)
AREAS = ('Emotional', 'Social', 'Behavioural', 'Physical',)
RATINGS = ('Thriving', 'Settled', 'Needs support', 'Concern',)
STATUSES = ('open', 'monitoring', 'closed',)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS wellbeing_records (
    record_id        TEXT PRIMARY KEY,
    pupil_id         TEXT,
    subject_type     TEXT,
    staff_id         TEXT,
    record_date      TEXT,
    area             TEXT,
    rating           TEXT,
    observation      TEXT,
    support_offered  TEXT,
    follow_up        TEXT,
    status           TEXT NOT NULL DEFAULT 'open',
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE SET NULL,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_wellbeing_status ON wellbeing_records(status);
"""


class ValidationError(ValueError):
    """Raised for invalid record input."""


@dataclass
class Record:
    record_id: str
    pupil_id: str | None
    subject_type: str | None
    staff_id: str | None
    record_date: str | None
    area: str | None
    rating: str | None
    observation: str | None
    support_offered: str | None
    follow_up: str | None
    status: str
    notes: str | None
    child_name: str | None = None
    room: str | None = None
    staff_id_name: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
        with connect() as conn:
            conn.executescript(_SCHEMA)
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to initialise schema for wellbeing")
        raise


_SELECT = """
SELECT t.*,
       TRIM(COALESCE(p.first_name,'') || ' ' || COALESCE(p.last_name,'')) AS child_name,
       p.room AS room,
       TRIM(COALESCE(s_staff_id.first_name,'') || ' ' || COALESCE(s_staff_id.last_name,'')) AS staff_id_name
FROM wellbeing_records t
LEFT JOIN pupils p ON p.pupil_id = t.pupil_id
LEFT JOIN staff s_staff_id ON s_staff_id.staff_id = t.staff_id
"""


def _row(r: sqlite3.Row) -> Record:
    keys = r.keys()
    return Record(
        record_id=r['record_id'],
        pupil_id=r['pupil_id'],
        subject_type=r['subject_type'],
        staff_id=r['staff_id'],
        record_date=r['record_date'],
        area=r['area'],
        rating=r['rating'],
        observation=r['observation'],
        support_offered=r['support_offered'],
        follow_up=r['follow_up'],
        status=r['status'],
        notes=r['notes'],
        child_name=(r['child_name'] or None) if 'child_name' in keys else None,
        room=r['room'] if 'room' in keys else None,
        staff_id_name=(r['staff_id_name'] or None) if 'staff_id_name' in keys else None,
    )


def _require(value, label):
    if not value or not str(value).strip():
        raise ValidationError(f"{label} is required")
    return str(value).strip()


def _opt(value):
    v = (value or "").strip()
    return v or None


def _opt_date(value, label):
    v = (value or "").strip()
    if v and not _DATE_RE.match(v):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return v or None


def _as_bool(value):
    if isinstance(value, (bool, int)):
        return int(bool(value))
    return int(str(value or "").strip().lower() in ("1", "y", "yes", "true", "on"))


def _validate(data: dict, *, require_pupil: bool = True) -> dict:
    out: dict = {}
    out['pupil_id'] = _opt(data.get('pupil_id'))
    _v = (data.get('subject_type') or '').strip()
    if _v and _v not in SUBJECT_TYPES:
        raise ValidationError('Subject Type must be one of: ' + ', '.join(x for x in SUBJECT_TYPES if x))
    out['subject_type'] = _v or None
    out['staff_id'] = _opt(data.get('staff_id'))
    out['record_date'] = _opt_date(data.get('record_date'), 'Record Date')
    _v = (data.get('area') or '').strip()
    if _v and _v not in AREAS:
        raise ValidationError('Area must be one of: ' + ', '.join(x for x in AREAS if x))
    out['area'] = _v or None
    _v = (data.get('rating') or '').strip()
    if _v and _v not in RATINGS:
        raise ValidationError('Rating must be one of: ' + ', '.join(x for x in RATINGS if x))
    out['rating'] = _v or None
    out['observation'] = _opt(data.get('observation'))
    out['support_offered'] = _opt(data.get('support_offered'))
    out['follow_up'] = _opt(data.get('follow_up'))
    _st = (data.get('status') or 'open').strip().lower()
    if _st not in STATUSES:
        raise ValidationError('Status must be one of ' + ', '.join(STATUSES))
    out['status'] = _st
    out['notes'] = _opt(data.get('notes'))
    return out


def generate_record_id() -> str:
    _ensure_schema()
    with connect() as conn:
        existing = {r[0] for r in conn.execute("SELECT record_id FROM wellbeing_records").fetchall()}
    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"
    for _a in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        rid = f"{ID_PREFIX}{n}"
        if rid not in existing:
            return rid
    raise RuntimeError("Could not allocate a unique id")


def list_records(*, status: str | None = None) -> list[Record]:
    _ensure_schema()
    sql = _SELECT
    params: list = []
    if status:
        sql += " WHERE t.status = ?"
        params.append(status)
    sql += " ORDER BY t.record_id DESC"
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row(r) for r in rows]


def get_record(record_id: str) -> Record | None:
    _ensure_schema()
    with connect() as conn:
        row = conn.execute(_SELECT + " WHERE t.record_id = ?", (record_id,)).fetchone()
    return _row(row) if row else None


def list_pupil_choices() -> list[tuple[str, str]]:
    _ensure_schema()
    with connect() as conn:
        rows = conn.execute(
            "SELECT pupil_id, first_name, last_name, room FROM pupils "
            "WHERE status = 'active' ORDER BY last_name, first_name").fetchall()
    out = []
    for r in rows:
        room = f" \u2014 {r['room']}" if r["room"] else ""
        out.append((r["pupil_id"], f"{r['first_name']} {r['last_name']} ({r['pupil_id']}){room}"))
    return out

def list_staff_choices() -> list[tuple[str, str]]:
    _ensure_schema()
    with connect() as conn:
        rows = conn.execute(
            "SELECT staff_id, first_name, last_name FROM staff "
            "ORDER BY last_name, first_name").fetchall()
    return [(r["staff_id"], f"{r['first_name']} {r['last_name']} ({r['staff_id']})") for r in rows]


def summary() -> dict:
    records = list_records()
    open_n = sum(1 for r in records if r.status in ('open', 'monitoring'))
    return {"total": len(records), "open": open_n}


def create_record(data: dict) -> Record:
    _ensure_schema()
    payload = _validate(data, require_pupil=True)
    rid = generate_record_id()
    try:
        with connect() as conn:
            conn.execute(
                "INSERT INTO wellbeing_records (record_id, pupil_id, subject_type, staff_id, record_date, area, rating, observation, support_offered, follow_up, status, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (rid, payload['pupil_id'], payload['subject_type'], payload['staff_id'], payload['record_date'], payload['area'], payload['rating'], payload['observation'], payload['support_offered'], payload['follow_up'], payload['status'], payload['notes']),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for wellbeing id=%s", rid)
        raise ValidationError(f"Could not create record \u2014 {e}") from e
    rec = get_record(rid)
    assert rec is not None
    logger.info("Created wellbeing record %s", rid)
    return rec


def update_record(record_id: str, data: dict) -> Record:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    try:
        with connect() as conn:
            cur = conn.execute(
                "UPDATE wellbeing_records SET subject_type = ?, staff_id = ?, record_date = ?, area = ?, rating = ?, observation = ?, support_offered = ?, follow_up = ?, status = ?, notes = ? WHERE record_id = ?",
                (payload['subject_type'], payload['staff_id'], payload['record_date'], payload['area'], payload['rating'], payload['observation'], payload['support_offered'], payload['follow_up'], payload['status'], payload['notes'], record_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No record with id {record_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for wellbeing id=%s", record_id)
        raise ValidationError(f"Could not update record \u2014 {e}") from e
    rec = get_record(record_id)
    assert rec is not None
    logger.info("Updated wellbeing record %s", record_id)
    return rec


def delete_record(record_id: str) -> bool:
    _ensure_schema()
    with connect() as conn:
        cur = conn.execute("DELETE FROM wellbeing_records WHERE record_id = ?", (record_id,))
        conn.commit()
        deleted = cur.rowcount > 0
    if deleted:
        logger.info("Deleted wellbeing record %s", record_id)
    return deleted
