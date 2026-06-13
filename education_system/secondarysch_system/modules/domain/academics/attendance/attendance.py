"""Daily attendance data layer for the Secondary School System.

Each pupil has two marks per school day: one for the AM session and one
for the PM session. A row in ``attendance_records`` represents one such
mark, identified by ``(pupil_id, date, session)`` (unique).

The mark codes follow the DfE statistical-return conventions:

* ``/`` Present                 — present for the morning session
* ``\\`` Present                 — present for the afternoon session
* ``L`` Late (before register closed)
* ``U`` Late after register closed (counts as unauthorised absent)
* ``I`` Illness (authorised)
* ``M`` Medical / dental appointment (authorised)
* ``H`` Holiday with leave (authorised)
* ``O`` Other unauthorised absence
* ``E`` Excluded
* ``X`` Not required to attend (e.g. before/after roll)

For ergonomics we expose them via short labels too; see ``MARK_CODES``.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Any

from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
    ValidationError, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

SESSIONS: tuple[str, ...] = ("AM", "PM")

# Mark code -> (label, category)
# category one of: "present" / "auth_absent" / "unauth_absent" /
# "late" / "excluded" / "not_required"
MARK_CODES: dict[str, tuple[str, str]] = {
    "/":  ("Present (AM)",       "present"),
    "\\": ("Present (PM)",       "present"),
    "P":  ("Present",            "present"),
    "L":  ("Late (in time)",     "late"),
    "U":  ("Late after close",   "unauth_absent"),
    "I":  ("Illness",            "auth_absent"),
    "M":  ("Medical appt.",      "auth_absent"),
    "H":  ("Holiday (authorised)", "auth_absent"),
    "C":  ("Other authorised",   "auth_absent"),
    "O":  ("Unauthorised",       "unauth_absent"),
    "E":  ("Excluded",           "excluded"),
    "X":  ("Not required",       "not_required"),
}

PRESENT_LIKE = {"present", "late"}
AUTH_ABSENT_LIKE = {"auth_absent"}
UNAUTH_ABSENT_LIKE = {"unauth_absent"}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_records (
    record_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id     TEXT NOT NULL,
    date         TEXT NOT NULL,
    session      TEXT NOT NULL,
    mark         TEXT NOT NULL,
    notes        TEXT,
    recorded_at  TEXT DEFAULT (datetime('now')),
    UNIQUE (pupil_id, date, session)
);

CREATE INDEX IF NOT EXISTS idx_att_pupil
    ON attendance_records(pupil_id);
CREATE INDEX IF NOT EXISTS idx_att_date
    ON attendance_records(date);
"""


@dataclass
class AttendanceRecord:
    record_id: int
    pupil_id: str
    date: str
    session: str
    mark: str
    notes: str | None
    recorded_at: str | None = None

    @property
    def label(self) -> str:
        return MARK_CODES.get(self.mark, (self.mark, "unknown"))[0]

    @property
    def category(self) -> str:
        return MARK_CODES.get(self.mark, (self.mark, "unknown"))[1]


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise attendance_records table")
        raise
    logger.info("Secondary attendance_records table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> AttendanceRecord:
    return AttendanceRecord(
        record_id=r["record_id"],
        pupil_id=r["pupil_id"],
        date=r["date"],
        session=r["session"],
        mark=r["mark"],
        notes=r["notes"],
        recorded_at=r["recorded_at"],
    )


def _validate_date(value: Any, label: str = "Date") -> str:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{label} is required")
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _validate_session(value: Any) -> str:
    s = (str(value or "").strip()).upper()
    if s not in SESSIONS:
        raise ValidationError(
            f"Session must be one of {', '.join(SESSIONS)}")
    return s


def _validate_mark(value: Any) -> str:
    s = str(value or "").strip()
    if not s:
        raise ValidationError("Mark is required")
    if s not in MARK_CODES:
        valid = ", ".join(sorted(MARK_CODES.keys()))
        raise ValidationError(f"Mark must be one of: {valid}")
    return s


def _pupil_exists(pupil_id: str) -> bool:
    from education_system.secondarysch_system.modules.domain.pupils.pupils import (
        pupils as pupils_data,
    )
    return pupils_data.get_pupil(pupil_id) is not None


def record_mark(pupil_id: str, date_iso: str, session: str,
                mark: str, notes: str | None = None
                ) -> AttendanceRecord:
    """Insert or update the mark for (pupil_id, date, session)."""
    init_db()
    pid = (pupil_id or "").strip()
    if not pid:
        raise ValidationError("Pupil ID is required")
    if not _pupil_exists(pid):
        raise ValidationError(f"No pupil with id {pid}")
    date_s = _validate_date(date_iso)
    sess = _validate_session(session)
    code = _validate_mark(mark)
    note_s = (notes or "").strip() or None
    try:
        with _connect() as conn:
            existing = conn.execute(
                "SELECT record_id FROM attendance_records "
                "WHERE pupil_id = ? AND date = ? AND session = ?",
                (pid, date_s, sess),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE attendance_records SET mark = ?, notes = ?, "
                    "recorded_at = datetime('now') WHERE record_id = ?",
                    (code, note_s, existing["record_id"]),
                )
                rid = existing["record_id"]
                changed = "updated"
            else:
                cur = conn.execute(
                    "INSERT INTO attendance_records "
                    "(pupil_id, date, session, mark, notes) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (pid, date_s, sess, code, note_s),
                )
                rid = cur.lastrowid
                changed = "inserted"
            conn.commit()
    except sqlite3.Error:
        logger.exception(
            "Failed to record attendance for pupil %s on %s/%s",
            pid, date_s, sess)
        raise
    logger.info("Attendance %s: pupil %s %s/%s mark=%s",
                changed, pid, date_s, sess, code)
    rec = get_record(rid)
    assert rec is not None
    return rec


def bulk_record(date_iso: str, session: str,
                marks: dict[str, str]) -> dict[str, AttendanceRecord | str]:
    """Record marks for many pupils at once.

    ``marks`` maps ``pupil_id`` → mark code. Returns a dict mapping each
    pupil_id either to the saved ``AttendanceRecord`` (success) or to an
    error string (failure). One bad row does not abort the others.
    """
    init_db()
    date_s = _validate_date(date_iso)
    sess = _validate_session(session)
    out: dict[str, AttendanceRecord | str] = {}
    for pid, code in marks.items():
        try:
            rec = record_mark(pid, date_s, sess, code)
            out[pid] = rec
        except ValidationError as e:
            out[pid] = str(e)
        except Exception as e:
            logger.exception("bulk_record entry failed for %s", pid)
            out[pid] = f"Unexpected error: {e}"
    ok = sum(1 for v in out.values() if isinstance(v, AttendanceRecord))
    bad = len(out) - ok
    logger.info("Bulk attendance %s/%s: ok=%d failed=%d", date_s, sess,
                ok, bad)
    return out


def get_record(record_id: int) -> AttendanceRecord | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM attendance_records WHERE record_id = ?",
                (record_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_record(%s) failed", record_id)
        raise
    return _row(r) if r else None


def get_for(pupil_id: str, date_iso: str,
            session: str) -> AttendanceRecord | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM attendance_records "
                "WHERE pupil_id = ? AND date = ? AND session = ?",
                ((pupil_id or "").strip(), date_iso, session.upper()),
            ).fetchone()
    except sqlite3.Error:
        logger.exception(
            "get_for(%s,%s,%s) failed", pupil_id, date_iso, session)
        raise
    return _row(r) if r else None


def list_for_date(date_iso: str, *,
                  session: str | None = None) -> list[AttendanceRecord]:
    init_db()
    date_s = _validate_date(date_iso)
    sql = ("SELECT * FROM attendance_records WHERE date = ?")
    params: list[Any] = [date_s]
    if session:
        sql += " AND session = ?"
        params.append(_validate_session(session))
    sql += " ORDER BY pupil_id, session"
    try:
        with _connect() as conn:
            return [_row(r) for r in conn.execute(sql,
                                                    tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_for_date(%s) failed", date_iso)
        raise


def list_for_pupil(pupil_id: str, *,
                   date_from: str | None = None,
                   date_to: str | None = None) -> list[AttendanceRecord]:
    init_db()
    pid = (pupil_id or "").strip()
    if not pid:
        raise ValidationError("Pupil ID is required")
    where = ["pupil_id = ?"]
    params: list[Any] = [pid]
    if date_from:
        where.append("date >= ?")
        params.append(_validate_date(date_from, "From date"))
    if date_to:
        where.append("date <= ?")
        params.append(_validate_date(date_to, "To date"))
    sql = ("SELECT * FROM attendance_records WHERE "
           + " AND ".join(where)
           + " ORDER BY date DESC, session")
    try:
        with _connect() as conn:
            return [_row(r) for r in conn.execute(sql,
                                                    tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_for_pupil(%s) failed", pupil_id)
        raise


def delete_record(record_id: int) -> bool:
    init_db()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM attendance_records WHERE record_id = ?",
                (record_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete attendance #%d", record_id)
        raise
    if deleted:
        logger.info("Deleted attendance record #%d", record_id)
    return deleted


def daily_summary(date_iso: str) -> dict[str, Any]:
    init_db()
    records = list_for_date(date_iso)
    by_session: dict[str, Counter] = {s: Counter() for s in SESSIONS}
    for r in records:
        by_session.setdefault(r.session, Counter())[r.mark] += 1
    out: dict[str, Any] = {"date": _validate_date(date_iso), "sessions": {}}
    for sess, marks in by_session.items():
        total = sum(marks.values())
        present = sum(n for code, n in marks.items()
                      if MARK_CODES.get(code, (None, None))[1]
                      in PRESENT_LIKE)
        auth = sum(n for code, n in marks.items()
                   if MARK_CODES.get(code, (None, None))[1]
                   in AUTH_ABSENT_LIKE)
        unauth = sum(n for code, n in marks.items()
                     if MARK_CODES.get(code, (None, None))[1]
                     in UNAUTH_ABSENT_LIKE)
        out["sessions"][sess] = {
            "total": total,
            "present": present,
            "authorised_absent": auth,
            "unauthorised_absent": unauth,
            "other": total - present - auth - unauth,
            "marks": dict(marks),
        }
    return out


def pupil_summary(pupil_id: str, *,
                  date_from: str | None = None,
                  date_to: str | None = None) -> dict[str, Any]:
    records = list_for_pupil(pupil_id, date_from=date_from, date_to=date_to)
    total = len(records)
    present = sum(1 for r in records if r.category in PRESENT_LIKE)
    auth = sum(1 for r in records if r.category in AUTH_ABSENT_LIKE)
    unauth = sum(1 for r in records if r.category in UNAUTH_ABSENT_LIKE)
    other = total - present - auth - unauth
    pct = round(100.0 * present / total, 2) if total else 0.0
    return {
        "pupil_id": (pupil_id or "").strip(),
        "total_sessions": total,
        "present": present,
        "authorised_absent": auth,
        "unauthorised_absent": unauth,
        "other": other,
        "attendance_pct": pct,
        "records": records,
    }
