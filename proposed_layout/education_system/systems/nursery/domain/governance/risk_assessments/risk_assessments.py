"""Domain layer for Risk Assessments (Nursery System).

Owns the ``risk_assessments`` table, created on demand inside the shared nursery DB.
Follows the 4-layer pattern: validation + SQLite access here, CLI in
``risk_assessments_cli.py``, Tk GUI in ``risk_assessments_views.py``.
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

FEATURE_NAME = "Risk Assessments"
CATEGORY = "Safeguarding & Welfare"

ID_PREFIX = "NRA"
ID_DIGITS = 3

AREAS = ('Premises', 'Outing', 'Activity', 'Individual child', 'Allergy', 'Fire', 'Other',)
RISK_LEVELS = ('low', 'medium', 'high',)
STATUSES = ('active', 'archived',)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS risk_assessments (
    record_id        TEXT PRIMARY KEY,
    pupil_id         TEXT,
    title            TEXT NOT NULL,
    area             TEXT,
    assessor         TEXT,
    date_assessed    TEXT,
    review_date      TEXT,
    hazards          TEXT,
    control_measures TEXT,
    risk_level       TEXT,
    status           TEXT NOT NULL DEFAULT 'active',
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE SET NULL,
    FOREIGN KEY (assessor) REFERENCES staff(staff_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_risk_assessments_status ON risk_assessments(status);
"""


class ValidationError(ValueError):
    """Raised for invalid assessment input."""


@dataclass
class Record:
    record_id: str
    pupil_id: str | None
    title: str | None
    area: str | None
    assessor: str | None
    date_assessed: str | None
    review_date: str | None
    hazards: str | None
    control_measures: str | None
    risk_level: str | None
    status: str
    notes: str | None
    child_name: str | None = None
    room: str | None = None
    assessor_name: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
        with connect() as conn:
            conn.executescript(_SCHEMA)
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to initialise schema for risk_assessments")
        raise


_SELECT = """
SELECT t.*,
       TRIM(COALESCE(p.first_name,'') || ' ' || COALESCE(p.last_name,'')) AS child_name,
       p.room AS room,
       TRIM(COALESCE(s_assessor.first_name,'') || ' ' || COALESCE(s_assessor.last_name,'')) AS assessor_name
FROM risk_assessments t
LEFT JOIN pupils p ON p.pupil_id = t.pupil_id
LEFT JOIN staff s_assessor ON s_assessor.staff_id = t.assessor
"""


def _row(r: sqlite3.Row) -> Record:
    keys = r.keys()
    return Record(
        record_id=r['record_id'],
        pupil_id=r['pupil_id'],
        title=r['title'],
        area=r['area'],
        assessor=r['assessor'],
        date_assessed=r['date_assessed'],
        review_date=r['review_date'],
        hazards=r['hazards'],
        control_measures=r['control_measures'],
        risk_level=r['risk_level'],
        status=r['status'],
        notes=r['notes'],
        child_name=(r['child_name'] or None) if 'child_name' in keys else None,
        room=r['room'] if 'room' in keys else None,
        assessor_name=(r['assessor_name'] or None) if 'assessor_name' in keys else None,
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
    out['title'] = _require(data.get('title'), 'Title')
    _v = (data.get('area') or '').strip()
    if _v and _v not in AREAS:
        raise ValidationError('Area must be one of: ' + ', '.join(x for x in AREAS if x))
    out['area'] = _v or None
    out['assessor'] = _opt(data.get('assessor'))
    out['date_assessed'] = _opt_date(data.get('date_assessed'), 'Date Assessed')
    out['review_date'] = _opt_date(data.get('review_date'), 'Review Date')
    out['hazards'] = _opt(data.get('hazards'))
    out['control_measures'] = _opt(data.get('control_measures'))
    _v = (data.get('risk_level') or '').strip()
    if _v and _v not in RISK_LEVELS:
        raise ValidationError('Risk Level must be one of: ' + ', '.join(x for x in RISK_LEVELS if x))
    out['risk_level'] = _v or None
    _st = (data.get('status') or 'active').strip().lower()
    if _st not in STATUSES:
        raise ValidationError('Status must be one of ' + ', '.join(STATUSES))
    out['status'] = _st
    out['notes'] = _opt(data.get('notes'))
    return out


def generate_record_id() -> str:
    _ensure_schema()
    with connect() as conn:
        existing = {r[0] for r in conn.execute("SELECT record_id FROM risk_assessments").fetchall()}
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
    open_n = sum(1 for r in records if r.status in ('active',))
    return {"total": len(records), "open": open_n}


def create_record(data: dict) -> Record:
    _ensure_schema()
    payload = _validate(data, require_pupil=True)
    rid = generate_record_id()
    try:
        with connect() as conn:
            conn.execute(
                "INSERT INTO risk_assessments (record_id, pupil_id, title, area, assessor, date_assessed, review_date, hazards, control_measures, risk_level, status, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (rid, payload['pupil_id'], payload['title'], payload['area'], payload['assessor'], payload['date_assessed'], payload['review_date'], payload['hazards'], payload['control_measures'], payload['risk_level'], payload['status'], payload['notes']),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for risk_assessments id=%s", rid)
        raise ValidationError(f"Could not create assessment \u2014 {e}") from e
    rec = get_record(rid)
    assert rec is not None
    logger.info("Created risk_assessments record %s", rid)
    return rec


def update_record(record_id: str, data: dict) -> Record:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    try:
        with connect() as conn:
            cur = conn.execute(
                "UPDATE risk_assessments SET title = ?, area = ?, assessor = ?, date_assessed = ?, review_date = ?, hazards = ?, control_measures = ?, risk_level = ?, status = ?, notes = ? WHERE record_id = ?",
                (payload['title'], payload['area'], payload['assessor'], payload['date_assessed'], payload['review_date'], payload['hazards'], payload['control_measures'], payload['risk_level'], payload['status'], payload['notes'], record_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No record with id {record_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for risk_assessments id=%s", record_id)
        raise ValidationError(f"Could not update assessment \u2014 {e}") from e
    rec = get_record(record_id)
    assert rec is not None
    logger.info("Updated risk_assessments record %s", record_id)
    return rec


def delete_record(record_id: str) -> bool:
    _ensure_schema()
    with connect() as conn:
        cur = conn.execute("DELETE FROM risk_assessments WHERE record_id = ?", (record_id,))
        conn.commit()
        deleted = cur.rowcount > 0
    if deleted:
        logger.info("Deleted risk_assessments record %s", record_id)
    return deleted
