"""Domain layer for Welfare Requirements (Nursery System).

Owns the ``welfare_requirements`` table, created on demand inside the shared nursery DB.
Follows the 4-layer pattern: validation + SQLite access here, CLI in
``welfare_cli.py``, Tk GUI in ``welfare_views.py``.
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

FEATURE_NAME = "Welfare Requirements"
CATEGORY = "Safeguarding & Welfare"

ID_PREFIX = "NWR"
ID_DIGITS = 3

AREAS = ('Safeguarding', 'Suitable people', 'Staff qualifications', 'Key person', 'Staff:child ratios', 'Health', 'Managing behaviour', 'Safety & suitability of premises', 'Special educational needs', 'Information & records',)
STATUSES = ('met', 'partial', 'not_met', 'review',)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS welfare_requirements (
    record_id        TEXT PRIMARY KEY,
    area             TEXT,
    requirement      TEXT,
    status           TEXT NOT NULL DEFAULT 'review',
    responsible      TEXT,
    last_reviewed    TEXT,
    next_review      TEXT,
    evidence         TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (responsible) REFERENCES staff(staff_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_welfare_status ON welfare_requirements(status);
"""


class ValidationError(ValueError):
    """Raised for invalid requirement input."""


@dataclass
class Record:
    record_id: str
    area: str | None
    requirement: str | None
    status: str
    responsible: str | None
    last_reviewed: str | None
    next_review: str | None
    evidence: str | None
    notes: str | None
    responsible_name: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
        with connect() as conn:
            conn.executescript(_SCHEMA)
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to initialise schema for welfare")
        raise


_SELECT = """
SELECT t.*,
       TRIM(COALESCE(s_responsible.first_name,'') || ' ' || COALESCE(s_responsible.last_name,'')) AS responsible_name
FROM welfare_requirements t
LEFT JOIN staff s_responsible ON s_responsible.staff_id = t.responsible
"""


def _row(r: sqlite3.Row) -> Record:
    keys = r.keys()
    return Record(
        record_id=r['record_id'],
        area=r['area'],
        requirement=r['requirement'],
        status=r['status'],
        responsible=r['responsible'],
        last_reviewed=r['last_reviewed'],
        next_review=r['next_review'],
        evidence=r['evidence'],
        notes=r['notes'],
        responsible_name=(r['responsible_name'] or None) if 'responsible_name' in keys else None,
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
    _v = (data.get('area') or '').strip()
    if _v and _v not in AREAS:
        raise ValidationError('Area must be one of: ' + ', '.join(x for x in AREAS if x))
    out['area'] = _v or None
    out['requirement'] = _opt(data.get('requirement'))
    _st = (data.get('status') or 'review').strip().lower()
    if _st not in STATUSES:
        raise ValidationError('Status must be one of ' + ', '.join(STATUSES))
    out['status'] = _st
    out['responsible'] = _opt(data.get('responsible'))
    out['last_reviewed'] = _opt_date(data.get('last_reviewed'), 'Last Reviewed')
    out['next_review'] = _opt_date(data.get('next_review'), 'Next Review')
    out['evidence'] = _opt(data.get('evidence'))
    out['notes'] = _opt(data.get('notes'))
    return out


def generate_record_id() -> str:
    _ensure_schema()
    with connect() as conn:
        existing = {r[0] for r in conn.execute("SELECT record_id FROM welfare_requirements").fetchall()}
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


def list_staff_choices() -> list[tuple[str, str]]:
    _ensure_schema()
    with connect() as conn:
        rows = conn.execute(
            "SELECT staff_id, first_name, last_name FROM staff "
            "ORDER BY last_name, first_name").fetchall()
    return [(r["staff_id"], f"{r['first_name']} {r['last_name']} ({r['staff_id']})") for r in rows]


def summary() -> dict:
    records = list_records()
    open_n = sum(1 for r in records if r.status in ('partial', 'not_met', 'review'))
    return {"total": len(records), "open": open_n}


def create_record(data: dict) -> Record:
    _ensure_schema()
    payload = _validate(data, require_pupil=True)
    rid = generate_record_id()
    try:
        with connect() as conn:
            conn.execute(
                "INSERT INTO welfare_requirements (record_id, area, requirement, status, responsible, last_reviewed, next_review, evidence, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (rid, payload['area'], payload['requirement'], payload['status'], payload['responsible'], payload['last_reviewed'], payload['next_review'], payload['evidence'], payload['notes']),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for welfare id=%s", rid)
        raise ValidationError(f"Could not create requirement \u2014 {e}") from e
    rec = get_record(rid)
    assert rec is not None
    logger.info("Created welfare record %s", rid)
    return rec


def update_record(record_id: str, data: dict) -> Record:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    try:
        with connect() as conn:
            cur = conn.execute(
                "UPDATE welfare_requirements SET area = ?, requirement = ?, status = ?, responsible = ?, last_reviewed = ?, next_review = ?, evidence = ?, notes = ? WHERE record_id = ?",
                (payload['area'], payload['requirement'], payload['status'], payload['responsible'], payload['last_reviewed'], payload['next_review'], payload['evidence'], payload['notes'], record_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No record with id {record_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for welfare id=%s", record_id)
        raise ValidationError(f"Could not update requirement \u2014 {e}") from e
    rec = get_record(record_id)
    assert rec is not None
    logger.info("Updated welfare record %s", record_id)
    return rec


def delete_record(record_id: str) -> bool:
    _ensure_schema()
    with connect() as conn:
        cur = conn.execute("DELETE FROM welfare_requirements WHERE record_id = ?", (record_id,))
        conn.commit()
        deleted = cur.rowcount > 0
    if deleted:
        logger.info("Deleted welfare record %s", record_id)
    return deleted
