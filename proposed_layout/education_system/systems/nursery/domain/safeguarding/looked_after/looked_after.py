"""Domain layer for Looked-After Children (Nursery System).

Owns the ``looked_after_children`` table, created on demand inside the shared nursery DB.
Follows the 4-layer pattern: validation + SQLite access here, CLI in
``looked_after_cli.py``, Tk GUI in ``looked_after_views.py``.
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

FEATURE_NAME = "Looked-After Children"
CATEGORY = "Safeguarding & Welfare"

ID_PREFIX = "NLA"
ID_DIGITS = 3

LEGAL_STATUSES = ('Section 20', 'Care order', 'Interim care order', 'Emergency protection order', 'Special guardianship', 'Other',)
STATUSES = ('current', 'former',)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS looked_after_children (
    record_id        TEXT PRIMARY KEY,
    pupil_id         TEXT,
    legal_status     TEXT,
    social_worker    TEXT,
    local_authority  TEXT,
    virtual_school_head TEXT,
    carer_name       TEXT,
    pep_review_date  TEXT,
    status           TEXT NOT NULL DEFAULT 'current',
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_looked_after_status ON looked_after_children(status);
"""


class ValidationError(ValueError):
    """Raised for invalid record input."""


@dataclass
class Record:
    record_id: str
    pupil_id: str | None
    legal_status: str | None
    social_worker: str | None
    local_authority: str | None
    virtual_school_head: str | None
    carer_name: str | None
    pep_review_date: str | None
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
        logger.exception("Failed to initialise schema for looked_after")
        raise


_SELECT = """
SELECT t.*,
       TRIM(COALESCE(p.first_name,'') || ' ' || COALESCE(p.last_name,'')) AS child_name,
       p.room AS room
FROM looked_after_children t
LEFT JOIN pupils p ON p.pupil_id = t.pupil_id
"""


def _row(r: sqlite3.Row) -> Record:
    keys = r.keys()
    return Record(
        record_id=r['record_id'],
        pupil_id=r['pupil_id'],
        legal_status=r['legal_status'],
        social_worker=r['social_worker'],
        local_authority=r['local_authority'],
        virtual_school_head=r['virtual_school_head'],
        carer_name=r['carer_name'],
        pep_review_date=r['pep_review_date'],
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
    if require_pupil:
        pid = (data.get('pupil_id') or '').strip()
        if not pid:
            raise ValidationError('Child (pupil ID) is required')
        out['pupil_id'] = pid
    _v = (data.get('legal_status') or '').strip()
    if _v and _v not in LEGAL_STATUSES:
        raise ValidationError('Legal Status must be one of: ' + ', '.join(x for x in LEGAL_STATUSES if x))
    out['legal_status'] = _v or None
    out['social_worker'] = _opt(data.get('social_worker'))
    out['local_authority'] = _opt(data.get('local_authority'))
    out['virtual_school_head'] = _opt(data.get('virtual_school_head'))
    out['carer_name'] = _opt(data.get('carer_name'))
    out['pep_review_date'] = _opt_date(data.get('pep_review_date'), 'Pep Review Date')
    _st = (data.get('status') or 'current').strip().lower()
    if _st not in STATUSES:
        raise ValidationError('Status must be one of ' + ', '.join(STATUSES))
    out['status'] = _st
    out['notes'] = _opt(data.get('notes'))
    return out


def generate_record_id() -> str:
    _ensure_schema()
    with connect() as conn:
        existing = {r[0] for r in conn.execute("SELECT record_id FROM looked_after_children").fetchall()}
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
    open_n = sum(1 for r in records if r.status in ('current',))
    return {"total": len(records), "open": open_n}


def create_record(data: dict) -> Record:
    _ensure_schema()
    payload = _validate(data, require_pupil=True)
    rid = generate_record_id()
    try:
        with connect() as conn:
            if not conn.execute('SELECT 1 FROM pupils WHERE pupil_id = ?', (payload['pupil_id'],)).fetchone():
                raise ValidationError(f"No child on roll with id {payload['pupil_id']}")
            conn.execute(
                "INSERT INTO looked_after_children (record_id, pupil_id, legal_status, social_worker, local_authority, virtual_school_head, carer_name, pep_review_date, status, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (rid, payload['pupil_id'], payload['legal_status'], payload['social_worker'], payload['local_authority'], payload['virtual_school_head'], payload['carer_name'], payload['pep_review_date'], payload['status'], payload['notes']),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for looked_after id=%s", rid)
        raise ValidationError(f"Could not create record \u2014 {e}") from e
    rec = get_record(rid)
    assert rec is not None
    logger.info("Created looked_after record %s", rid)
    return rec


def update_record(record_id: str, data: dict) -> Record:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    try:
        with connect() as conn:
            cur = conn.execute(
                "UPDATE looked_after_children SET legal_status = ?, social_worker = ?, local_authority = ?, virtual_school_head = ?, carer_name = ?, pep_review_date = ?, status = ?, notes = ? WHERE record_id = ?",
                (payload['legal_status'], payload['social_worker'], payload['local_authority'], payload['virtual_school_head'], payload['carer_name'], payload['pep_review_date'], payload['status'], payload['notes'], record_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No record with id {record_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for looked_after id=%s", record_id)
        raise ValidationError(f"Could not update record \u2014 {e}") from e
    rec = get_record(record_id)
    assert rec is not None
    logger.info("Updated looked_after record %s", record_id)
    return rec


def delete_record(record_id: str) -> bool:
    _ensure_schema()
    with connect() as conn:
        cur = conn.execute("DELETE FROM looked_after_children WHERE record_id = ?", (record_id,))
        conn.commit()
        deleted = cur.rowcount > 0
    if deleted:
        logger.info("Deleted looked_after record %s", record_id)
    return deleted
