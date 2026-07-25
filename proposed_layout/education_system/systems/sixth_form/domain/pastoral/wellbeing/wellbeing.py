"""Wellbeing data layer for the Sixth Form System.

Three linked but independent record types:

* **Check-ins** — quick wellbeing pulse: mood / stress / sleep scores
  on a 1-5 scale plus optional notes. Used for regular weekly
  pastoral check-ins.
* **Sessions** — scheduled or completed support meetings
  (counselling, mentoring, study support, group workshops).
* **Flags** — long-running pastoral tags such as Young Carer,
  Bereavement, EAL Support. ``end_date IS NULL`` means the flag is
  currently active.

Distinct from safeguarding (which is for child-protection incidents
with formal DSL workflow). This module is general pastoral support.

Cascade: deleting a student wipes all three record types.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.systems.sixth_form.infrastructure import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.WELLBEING_DB

SCORE_MIN: int = 1
SCORE_MAX: int = 5

SESSION_TYPES: tuple[str, ...] = (
    "Counselling", "Mentoring", "Check-in", "Study Support",
    "Pastoral", "Group Session", "Wellbeing Workshop",
    "Mindfulness", "Other",
)
DEFAULT_SESSION_TYPE: str = "Counselling"

SESSION_STATUSES: tuple[str, ...] = (
    "Scheduled", "Completed", "Cancelled", "No-Show",
)
DEFAULT_SESSION_STATUS: str = "Completed"

FLAG_TYPES: tuple[str, ...] = (
    "Young Carer", "Bereavement", "Mental Health",
    "Eating Disorder Support", "Anxiety / Stress",
    "Physical Health", "LGBTQ+ Support",
    "Looked-After Child", "Care Leaver", "EAL Support",
    "SEND", "Pupil Premium / Bursary",
    "Free School Meals", "Other",
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS wellbeing_checkins (
    checkin_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL,
    checkin_date TEXT NOT NULL,
    mood_score   INTEGER,
    stress_score INTEGER,
    sleep_score  INTEGER,
    notes        TEXT,
    recorded_by  TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS wellbeing_sessions (
    session_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id       TEXT NOT NULL,
    session_date     TEXT NOT NULL,
    session_type     TEXT NOT NULL DEFAULT 'Counselling',
    duration_minutes INTEGER,
    provider         TEXT,
    topics           TEXT,
    action_plan      TEXT,
    follow_up_date   TEXT,
    status           TEXT NOT NULL DEFAULT 'Completed',
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS wellbeing_flags (
    flag_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  TEXT NOT NULL,
    flag_type   TEXT NOT NULL,
    start_date  TEXT,
    end_date    TEXT,
    notes       TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_wci_student ON wellbeing_checkins(student_id);
CREATE INDEX IF NOT EXISTS idx_wci_date    ON wellbeing_checkins(checkin_date);
CREATE INDEX IF NOT EXISTS idx_wss_student ON wellbeing_sessions(student_id);
CREATE INDEX IF NOT EXISTS idx_wss_date    ON wellbeing_sessions(session_date);
CREATE INDEX IF NOT EXISTS idx_wss_status  ON wellbeing_sessions(status);
CREATE INDEX IF NOT EXISTS idx_wfl_student ON wellbeing_flags(student_id);
CREATE INDEX IF NOT EXISTS idx_wfl_type    ON wellbeing_flags(flag_type);
CREATE INDEX IF NOT EXISTS idx_wfl_active  ON wellbeing_flags(end_date);
"""


@dataclass
class CheckIn:
    checkin_id: int
    student_id: str
    checkin_date: str
    mood_score: int | None
    stress_score: int | None
    sleep_score: int | None
    notes: str | None
    recorded_by: str | None
    created_at: str


@dataclass
class Session:
    session_id: int
    student_id: str
    session_date: str
    session_type: str
    duration_minutes: int | None
    provider: str | None
    topics: str | None
    action_plan: str | None
    follow_up_date: str | None
    status: str
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class Flag:
    flag_id: int
    student_id: str
    flag_type: str
    start_date: str | None
    end_date: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def active(self) -> bool:
        return self.end_date is None


@dataclass
class CheckInRow:
    checkin: CheckIn
    student_name: str


@dataclass
class SessionRow:
    session: Session
    student_name: str


@dataclass
class FlagRow:
    flag: Flag
    student_name: str


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Wellbeing schema ready at %s", DB_PATH)

    _DB_READY = True


def _row_checkin(r: sqlite3.Row) -> CheckIn:
    return CheckIn(
        checkin_id=r["checkin_id"], student_id=r["student_id"],
        checkin_date=r["checkin_date"],
        mood_score=r["mood_score"], stress_score=r["stress_score"],
        sleep_score=r["sleep_score"],
        notes=r["notes"], recorded_by=r["recorded_by"],
        created_at=r["created_at"],
    )


def _row_session(r: sqlite3.Row) -> Session:
    return Session(
        session_id=r["session_id"], student_id=r["student_id"],
        session_date=r["session_date"], session_type=r["session_type"],
        duration_minutes=r["duration_minutes"], provider=r["provider"],
        topics=r["topics"], action_plan=r["action_plan"],
        follow_up_date=r["follow_up_date"],
        status=r["status"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_flag(r: sqlite3.Row) -> Flag:
    return Flag(
        flag_id=r["flag_id"], student_id=r["student_id"],
        flag_type=r["flag_type"], start_date=r["start_date"],
        end_date=r["end_date"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for any invalid wellbeing input."""


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_date_required(value: Any, label: str) -> str:
    v = _require(value, label)
    s = str(v).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return s


def _validate_date(value: Any, label: str) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return s


def _validate_score(value: Any, label: str) -> int | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a number 1-5") from None
    if n < SCORE_MIN or n > SCORE_MAX:
        raise ValidationError(f"{label} must be between 1 and 5")
    return n


def _validate_student(value: Any) -> str:
    sid = _require(value, "Student ID").strip()
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    return sid


# ── Check-in validation + CRUD ─────────────────────────────────────

def _validate_checkin_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["student_id"] = _validate_student(data.get("student_id"))
    out["checkin_date"] = _validate_date_required(
        data.get("checkin_date"), "Check-in date")
    out["mood_score"] = _validate_score(data.get("mood_score"), "Mood")
    out["stress_score"] = _validate_score(
        data.get("stress_score"), "Stress")
    out["sleep_score"] = _validate_score(data.get("sleep_score"), "Sleep")
    if all(out[k] is None for k in ("mood_score", "stress_score", "sleep_score")) \
            and not (data.get("notes") or "").strip():
        raise ValidationError(
            "Provide at least one score or a note for the check-in")
    out["notes"]       = (data.get("notes") or "").strip() or None
    out["recorded_by"] = (data.get("recorded_by") or "").strip() or None
    return out


def create_checkin(data: dict[str, Any]) -> CheckIn:
    init_db()
    try:
        p = _validate_checkin_payload(data)
    except ValidationError as e:
        logger.warning("create_checkin validation failed: %s", e)
        raise
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO wellbeing_checkins
                   (student_id, checkin_date, mood_score, stress_score,
                    sleep_score, notes, recorded_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (p["student_id"], p["checkin_date"], p["mood_score"],
             p["stress_score"], p["sleep_score"], p["notes"],
             p["recorded_by"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_checkin(new_id)
    assert out is not None
    logger.info(
        "Created wellbeing check-in #%d for %s (mood=%s, stress=%s, sleep=%s)",
        new_id, p["student_id"], p["mood_score"], p["stress_score"],
        p["sleep_score"],
    )
    return out


def get_checkin(checkin_id: int) -> CheckIn | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM wellbeing_checkins WHERE checkin_id = ?",
            (checkin_id,),
        ).fetchone()
        return _row_checkin(r) if r else None


def list_checkins(
    *,
    student_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    low_mood: int | None = None,
    high_stress: int | None = None,
) -> list[CheckIn]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if date_from:
        clauses.append("checkin_date >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("checkin_date <= ?")
        args.append(_validate_date(date_to, "date_to"))
    if low_mood is not None:
        clauses.append("mood_score IS NOT NULL AND mood_score <= ?")
        args.append(low_mood)
    if high_stress is not None:
        clauses.append("stress_score IS NOT NULL AND stress_score >= ?")
        args.append(high_stress)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM wellbeing_checkins {where} "
           "ORDER BY checkin_date DESC, checkin_id DESC")
    with _connect() as conn:
        return [_row_checkin(r) for r in conn.execute(sql, args).fetchall()]


def list_checkins_with_detail(**kwargs) -> list[CheckInRow]:
    rows = list_checkins(**kwargs)
    if not rows:
        return []
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    names = {s.student_id: s.full_name for s in _students.list_students()}
    return [CheckInRow(checkin=c,
                        student_name=names.get(c.student_id, "(unknown)"))
            for c in rows]


def update_checkin(checkin_id: int, data: dict[str, Any]) -> CheckIn:
    init_db()
    existing = get_checkin(checkin_id)
    if existing is None:
        raise ValidationError(f"No check-in with id {checkin_id}")
    p = _validate_checkin_payload({
        "student_id":   existing.student_id,
        "checkin_date": data.get("checkin_date", existing.checkin_date),
        "mood_score":   data.get("mood_score", existing.mood_score),
        "stress_score": data.get("stress_score", existing.stress_score),
        "sleep_score":  data.get("sleep_score", existing.sleep_score),
        "notes":        data.get("notes", existing.notes),
        "recorded_by":  data.get("recorded_by", existing.recorded_by),
    })
    with _connect() as conn:
        conn.execute(
            """UPDATE wellbeing_checkins SET
                   checkin_date = ?, mood_score = ?, stress_score = ?,
                   sleep_score = ?, notes = ?, recorded_by = ?
               WHERE checkin_id = ?""",
            (p["checkin_date"], p["mood_score"], p["stress_score"],
             p["sleep_score"], p["notes"], p["recorded_by"], checkin_id),
        )
        conn.commit()
    out = get_checkin(checkin_id)
    assert out is not None
    logger.info("Updated wellbeing check-in #%d", checkin_id)
    return out


def delete_checkin(checkin_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM wellbeing_checkins WHERE checkin_id = ?",
            (checkin_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted wellbeing check-in #%d", checkin_id)
            return True
        return False


# ── Session validation + CRUD ──────────────────────────────────────

def _validate_session_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["student_id"] = _validate_student(data.get("student_id"))
    out["session_date"] = _validate_date_required(
        data.get("session_date"), "Session date")

    stype = (data.get("session_type") or DEFAULT_SESSION_TYPE).strip()
    if stype not in SESSION_TYPES:
        raise ValidationError(
            f"Session type must be one of: {', '.join(SESSION_TYPES)}")
    out["session_type"] = stype

    duration = data.get("duration_minutes")
    if duration in (None, ""):
        out["duration_minutes"] = None
    else:
        try:
            d = int(duration)
        except (TypeError, ValueError):
            raise ValidationError(
                "Duration must be a whole number of minutes") from None
        if d <= 0 or d > 600:
            raise ValidationError(
                "Duration must be between 1 and 600 minutes")
        out["duration_minutes"] = d

    status = (data.get("status") or DEFAULT_SESSION_STATUS).strip()
    if status not in SESSION_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(SESSION_STATUSES)}")
    out["status"] = status

    out["follow_up_date"] = _validate_date(
        data.get("follow_up_date"), "Follow-up date")
    out["provider"]    = (data.get("provider") or "").strip() or None
    out["topics"]      = (data.get("topics") or "").strip() or None
    out["action_plan"] = (data.get("action_plan") or "").strip() or None
    out["notes"]       = (data.get("notes") or "").strip() or None
    return out


def create_session(data: dict[str, Any]) -> Session:
    init_db()
    try:
        p = _validate_session_payload(data)
    except ValidationError as e:
        logger.warning("create_session validation failed: %s", e)
        raise
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO wellbeing_sessions
                   (student_id, session_date, session_type, duration_minutes,
                    provider, topics, action_plan, follow_up_date, status,
                    notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["student_id"], p["session_date"], p["session_type"],
             p["duration_minutes"], p["provider"], p["topics"],
             p["action_plan"], p["follow_up_date"], p["status"],
             p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_session(new_id)
    assert out is not None
    logger.info(
        "Created wellbeing session #%d for %s (%s, %s, status=%s)",
        new_id, p["student_id"], p["session_date"], p["session_type"],
        p["status"],
    )
    return out


def get_session(session_id: int) -> Session | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM wellbeing_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return _row_session(r) if r else None


def list_sessions(
    *,
    student_id: str | None = None,
    session_type: str | None = None,
    status: str | None = None,
    provider_like: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[Session]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if session_type:
        if session_type not in SESSION_TYPES:
            raise ValidationError(
                f"Session type must be one of: {', '.join(SESSION_TYPES)}")
        clauses.append("session_type = ?")
        args.append(session_type)
    if status:
        if status not in SESSION_STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(SESSION_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if provider_like:
        clauses.append("provider LIKE ?")
        args.append(f"%{provider_like.strip()}%")
    if date_from:
        clauses.append("session_date >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("session_date <= ?")
        args.append(_validate_date(date_to, "date_to"))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM wellbeing_sessions {where} "
           "ORDER BY session_date DESC, session_id DESC")
    with _connect() as conn:
        return [_row_session(r) for r in conn.execute(sql, args).fetchall()]


def list_sessions_with_detail(**kwargs) -> list[SessionRow]:
    rows = list_sessions(**kwargs)
    if not rows:
        return []
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    names = {s.student_id: s.full_name for s in _students.list_students()}
    return [SessionRow(session=s,
                        student_name=names.get(s.student_id, "(unknown)"))
            for s in rows]


def update_session(session_id: int, data: dict[str, Any]) -> Session:
    init_db()
    existing = get_session(session_id)
    if existing is None:
        raise ValidationError(f"No session with id {session_id}")
    p = _validate_session_payload({
        "student_id":       existing.student_id,
        "session_date":     data.get("session_date", existing.session_date),
        "session_type":     data.get("session_type", existing.session_type),
        "duration_minutes": data.get("duration_minutes",
                                      existing.duration_minutes),
        "provider":         data.get("provider", existing.provider),
        "topics":           data.get("topics", existing.topics),
        "action_plan":      data.get("action_plan", existing.action_plan),
        "follow_up_date":   data.get("follow_up_date",
                                      existing.follow_up_date),
        "status":           data.get("status", existing.status),
        "notes":            data.get("notes", existing.notes),
    })
    with _connect() as conn:
        conn.execute(
            """UPDATE wellbeing_sessions SET
                   session_date = ?, session_type = ?, duration_minutes = ?,
                   provider = ?, topics = ?, action_plan = ?,
                   follow_up_date = ?, status = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE session_id = ?""",
            (p["session_date"], p["session_type"], p["duration_minutes"],
             p["provider"], p["topics"], p["action_plan"],
             p["follow_up_date"], p["status"], p["notes"], session_id),
        )
        conn.commit()
    out = get_session(session_id)
    assert out is not None
    logger.info("Updated wellbeing session #%d (status=%s)",
                session_id, out.status)
    return out


def delete_session(session_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM wellbeing_sessions WHERE session_id = ?",
            (session_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted wellbeing session #%d", session_id)
            return True
        return False


# ── Flag validation + CRUD ─────────────────────────────────────────

def _validate_flag_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["student_id"] = _validate_student(data.get("student_id"))

    flag_type = _require(data.get("flag_type"), "Flag type").strip()
    if flag_type not in FLAG_TYPES:
        raise ValidationError(
            f"Flag type must be one of: {', '.join(FLAG_TYPES)}")
    out["flag_type"] = flag_type

    out["start_date"] = _validate_date(
        data.get("start_date"), "Start date")
    out["end_date"]   = _validate_date(data.get("end_date"), "End date")
    if out["start_date"] and out["end_date"] \
            and out["end_date"] < out["start_date"]:
        raise ValidationError("End date cannot be before start date")
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def create_flag(data: dict[str, Any]) -> Flag:
    init_db()
    try:
        p = _validate_flag_payload(data)
    except ValidationError as e:
        logger.warning("create_flag validation failed: %s", e)
        raise
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO wellbeing_flags
                   (student_id, flag_type, start_date, end_date, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            (p["student_id"], p["flag_type"], p["start_date"],
             p["end_date"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_flag(new_id)
    assert out is not None
    logger.info(
        "Created wellbeing flag #%d for %s (%s, %s)",
        new_id, p["student_id"], p["flag_type"],
        "active" if not p["end_date"] else f"closed {p['end_date']}",
    )
    return out


def get_flag(flag_id: int) -> Flag | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM wellbeing_flags WHERE flag_id = ?", (flag_id,),
        ).fetchone()
        return _row_flag(r) if r else None


def list_flags(
    *,
    student_id: str | None = None,
    flag_type: str | None = None,
    active_only: bool = False,
) -> list[Flag]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if flag_type:
        if flag_type not in FLAG_TYPES:
            raise ValidationError(
                f"Flag type must be one of: {', '.join(FLAG_TYPES)}")
        clauses.append("flag_type = ?")
        args.append(flag_type)
    if active_only:
        clauses.append("end_date IS NULL")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM wellbeing_flags {where} "
           "ORDER BY end_date IS NOT NULL, student_id, flag_type")
    with _connect() as conn:
        return [_row_flag(r) for r in conn.execute(sql, args).fetchall()]


def list_flags_with_detail(**kwargs) -> list[FlagRow]:
    rows = list_flags(**kwargs)
    if not rows:
        return []
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    names = {s.student_id: s.full_name for s in _students.list_students()}
    return [FlagRow(flag=f,
                     student_name=names.get(f.student_id, "(unknown)"))
            for f in rows]


def update_flag(flag_id: int, data: dict[str, Any]) -> Flag:
    init_db()
    existing = get_flag(flag_id)
    if existing is None:
        raise ValidationError(f"No flag with id {flag_id}")
    p = _validate_flag_payload({
        "student_id": existing.student_id,
        "flag_type":  data.get("flag_type", existing.flag_type),
        "start_date": data.get("start_date", existing.start_date),
        "end_date":   data.get("end_date", existing.end_date),
        "notes":      data.get("notes", existing.notes),
    })
    with _connect() as conn:
        conn.execute(
            """UPDATE wellbeing_flags SET
                   flag_type = ?, start_date = ?, end_date = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE flag_id = ?""",
            (p["flag_type"], p["start_date"], p["end_date"],
             p["notes"], flag_id),
        )
        conn.commit()
    out = get_flag(flag_id)
    assert out is not None
    logger.info("Updated wellbeing flag #%d (active=%s)",
                flag_id, out.active)
    return out


def close_flag(flag_id: int, end_date: str | None = None) -> Flag:
    """Convenience: set end_date (default today) so the flag is no
    longer active."""
    import datetime as _dt
    end = end_date or _dt.date.today().isoformat()
    return update_flag(flag_id, {"end_date": end})


def reopen_flag(flag_id: int) -> Flag:
    """Convenience: clear end_date so the flag is active again."""
    return update_flag(flag_id, {"end_date": ""})


def delete_flag(flag_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM wellbeing_flags WHERE flag_id = ?", (flag_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted wellbeing flag #%d", flag_id)
            return True
        return False


# ── Summaries ─────────────────────────────────────────────────────

@dataclass
class StudentWellbeingSummary:
    student_id: str
    checkin_count: int
    session_count: int
    active_flags: list[str]
    latest_mood: int | None
    latest_stress: int | None
    latest_sleep: int | None
    latest_checkin_date: str | None
    avg_mood: float | None
    avg_stress: float | None
    avg_sleep: float | None


def per_student_summary(student_id: str) -> StudentWellbeingSummary:
    checkins = list_checkins(student_id=student_id)
    sessions = list_sessions(student_id=student_id)
    flags = list_flags(student_id=student_id, active_only=True)

    def _avg(scores: list[int | None]) -> float | None:
        nums = [s for s in scores if s is not None]
        if not nums:
            return None
        return round(sum(nums) / len(nums), 1)

    latest = checkins[0] if checkins else None
    return StudentWellbeingSummary(
        student_id=student_id,
        checkin_count=len(checkins),
        session_count=len(sessions),
        active_flags=[f.flag_type for f in flags],
        latest_mood=latest.mood_score if latest else None,
        latest_stress=latest.stress_score if latest else None,
        latest_sleep=latest.sleep_score if latest else None,
        latest_checkin_date=latest.checkin_date if latest else None,
        avg_mood=_avg([c.mood_score for c in checkins]),
        avg_stress=_avg([c.stress_score for c in checkins]),
        avg_sleep=_avg([c.sleep_score for c in checkins]),
    )


@dataclass
class Summary:
    total_checkins: int
    total_sessions: int
    active_flags: int
    closed_flags: int
    by_flag_type: dict[str, int]            # active only
    by_session_type: dict[str, int]
    sessions_scheduled_upcoming: int        # status=Scheduled in window
    upcoming_follow_ups: int                # follow_up_date within window
    low_mood_count: int                     # check-ins with mood <= 2
    high_stress_count: int                  # check-ins with stress >= 4
    students_with_flag: int
    students_with_session: int
    students_low_recent_mood: int           # students whose latest mood ≤ 2


def summary(
    *,
    upcoming_window_days: int = 14,
    low_mood_threshold: int = 2,
    high_stress_threshold: int = 4,
) -> Summary:
    import datetime as _dt
    init_db()
    today = _dt.date.today().isoformat()
    cutoff = (_dt.date.today() + _dt.timedelta(days=upcoming_window_days)
              ).isoformat()

    checkins = list_checkins()
    sessions = list_sessions()
    flags = list_flags()

    by_flag = {t: 0 for t in FLAG_TYPES}
    active = 0
    closed = 0
    for f in flags:
        if f.active:
            active += 1
            by_flag[f.flag_type] = by_flag.get(f.flag_type, 0) + 1
        else:
            closed += 1

    by_stype = {t: 0 for t in SESSION_TYPES}
    upcoming_sch = 0
    upcoming_fu = 0
    for s in sessions:
        by_stype[s.session_type] = by_stype.get(s.session_type, 0) + 1
        if (s.status == "Scheduled"
                and today <= s.session_date <= cutoff):
            upcoming_sch += 1
        if s.follow_up_date and today <= s.follow_up_date <= cutoff:
            upcoming_fu += 1

    low_mood = sum(1 for c in checkins
                    if c.mood_score is not None
                    and c.mood_score <= low_mood_threshold)
    high_stress = sum(1 for c in checkins
                       if c.stress_score is not None
                       and c.stress_score >= high_stress_threshold)

    students_with_flag = len({f.student_id for f in flags if f.active})
    students_with_session = len({s.student_id for s in sessions})

    # Latest mood per student (most recent check-in).
    latest_by_student: dict[str, int] = {}
    for c in checkins:  # checkins are ordered most-recent first
        if c.mood_score is None:
            continue
        if c.student_id in latest_by_student:
            continue
        latest_by_student[c.student_id] = c.mood_score
    low_recent = sum(1 for m in latest_by_student.values()
                      if m <= low_mood_threshold)

    return Summary(
        total_checkins=len(checkins),
        total_sessions=len(sessions),
        active_flags=active,
        closed_flags=closed,
        by_flag_type=by_flag,
        by_session_type=by_stype,
        sessions_scheduled_upcoming=upcoming_sch,
        upcoming_follow_ups=upcoming_fu,
        low_mood_count=low_mood,
        high_stress_count=high_stress,
        students_with_flag=students_with_flag,
        students_with_session=students_with_session,
        students_low_recent_mood=low_recent,
    )
