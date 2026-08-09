"""Domain layer for Concerns & Referrals (Nursery System).

Owns the ``concern_referrals`` table, created on demand inside the shared nursery DB.
Follows the 4-layer pattern: validation + SQLite access here, CLI in
``concerns_cli.py``, Tk GUI in ``concerns_views.py``.
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

FEATURE_NAME = "Concerns & Referrals"
CATEGORY = "Safeguarding & Welfare"

ID_PREFIX = "NC"
ID_DIGITS = 3

CONCERN_TYPES = ('Safeguarding', 'Welfare', 'Behaviour', 'Attendance', 'Health', 'Other',)
REFERRED_TO = ('', "Children's Services", 'Early Help', 'Health', 'Police', 'Other',)
STATUSES = ('open', 'in_progress', 'referred', 'closed',)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS concern_referrals (
    record_id        TEXT PRIMARY KEY,
    pupil_id         TEXT,
    concern_type     TEXT,
    raised_by        TEXT,
    date_raised      TEXT,
    description      TEXT,
    referred_to      TEXT,
    referral_date    TEXT,
    outcome          TEXT,
    status           TEXT NOT NULL DEFAULT 'open',
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_concerns_status ON concern_referrals(status);
"""


class ValidationError(ValueError):
    """Raised for invalid concern input."""


@dataclass
class Record:
    record_id: str
    pupil_id: str | None
    concern_type: str | None
    raised_by: str | None
    date_raised: str | None
    description: str | None
    referred_to: str | None
    referral_date: str | None
    outcome: str | None
    status: str
    notes: str | None
    child_name: str | None = None
    room: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
        with connect() as conn:
            conn.executescript(_SCHEMA)
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to initialise schema for concerns")
        raise


_SELECT = """
SELECT t.*,
       TRIM(COALESCE(p.first_name,'') || ' ' || COALESCE(p.last_name,'')) AS child_name,
       p.room AS room
FROM concern_referrals t
LEFT JOIN pupils p ON p.pupil_id = t.pupil_id
"""


def _row(r: sqlite3.Row) -> Record:
    keys = r.keys()
    return Record(
        record_id=r['record_id'],
        pupil_id=r['pupil_id'],
        concern_type=r['concern_type'],
        raised_by=r['raised_by'],
        date_raised=r['date_raised'],
        description=r['description'],
        referred_to=r['referred_to'],
        referral_date=r['referral_date'],
        outcome=r['outcome'],
        status=r['status'],
        notes=r['notes'],
        child_name=(r['child_name'] or None) if 'child_name' in keys else None,
        room=r['room'] if 'room' in keys else None,
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
    _v = (data.get('concern_type') or '').strip()
    if _v and _v not in CONCERN_TYPES:
        raise ValidationError('Concern Type must be one of: ' + ', '.join(x for x in CONCERN_TYPES if x))
    out['concern_type'] = _v or None
    out['raised_by'] = _opt(data.get('raised_by'))
    out['date_raised'] = _opt_date(data.get('date_raised'), 'Date Raised')
    out['description'] = _opt(data.get('description'))
    _v = (data.get('referred_to') or '').strip()
    if _v and _v not in REFERRED_TO:
        raise ValidationError('Referred To must be one of: ' + ', '.join(x for x in REFERRED_TO if x))
    out['referred_to'] = _v or None
    out['referral_date'] = _opt_date(data.get('referral_date'), 'Referral Date')
    out['outcome'] = _opt(data.get('outcome'))
    _st = (data.get('status') or 'open').strip().lower()
    if _st not in STATUSES:
        raise ValidationError('Status must be one of ' + ', '.join(STATUSES))
    out['status'] = _st
    out['notes'] = _opt(data.get('notes'))
    return out


def generate_record_id() -> str:
    _ensure_schema()
    with connect() as conn:
        existing = {r[0] for r in conn.execute("SELECT record_id FROM concern_referrals").fetchall()}
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


def summary() -> dict:
    records = list_records()
    open_n = sum(1 for r in records if r.status in ('open', 'in_progress'))
    return {"total": len(records), "open": open_n}


def create_record(data: dict) -> Record:
    _ensure_schema()
    payload = _validate(data, require_pupil=True)
    rid = generate_record_id()
    try:
        with connect() as conn:
            conn.execute(
                "INSERT INTO concern_referrals (record_id, pupil_id, concern_type, raised_by, date_raised, description, referred_to, referral_date, outcome, status, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (rid, payload['pupil_id'], payload['concern_type'], payload['raised_by'], payload['date_raised'], payload['description'], payload['referred_to'], payload['referral_date'], payload['outcome'], payload['status'], payload['notes']),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for concerns id=%s", rid)
        raise ValidationError(f"Could not create concern \u2014 {e}") from e
    rec = get_record(rid)
    assert rec is not None
    logger.info("Created concerns record %s", rid)
    return rec


def update_record(record_id: str, data: dict) -> Record:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    try:
        with connect() as conn:
            cur = conn.execute(
                "UPDATE concern_referrals SET concern_type = ?, raised_by = ?, date_raised = ?, description = ?, referred_to = ?, referral_date = ?, outcome = ?, status = ?, notes = ? WHERE record_id = ?",
                (payload['concern_type'], payload['raised_by'], payload['date_raised'], payload['description'], payload['referred_to'], payload['referral_date'], payload['outcome'], payload['status'], payload['notes'], record_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No record with id {record_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for concerns id=%s", record_id)
        raise ValidationError(f"Could not update concern \u2014 {e}") from e
    rec = get_record(record_id)
    assert rec is not None
    logger.info("Updated concerns record %s", record_id)
    return rec


def delete_record(record_id: str) -> bool:
    _ensure_schema()
    with connect() as conn:
        cur = conn.execute("DELETE FROM concern_referrals WHERE record_id = ?", (record_id,))
        conn.commit()
        deleted = cur.rowcount > 0
    if deleted:
        logger.info("Deleted concerns record %s", record_id)
    return deleted
