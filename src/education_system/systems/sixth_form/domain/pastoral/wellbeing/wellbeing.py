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
from dataclasses import dataclass, field
from typing import Any
from education_system import paths
from education_system.systems.sixth_form.domain.pastoral import _records

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_WELLBEING_DB

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
    "Previously Looked-After",
)

#: Who wrote a check-in: pastoral staff, or the student's own journal
#: (Student Wellbeing). Both live in ``wellbeing_checkins``.
CHECKIN_SOURCES: tuple[str, ...] = ("staff", "self")

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
    # Added when Student Wellbeing's journal moved into this table.
    energy_score: int | None = None
    sleep_hours: float | None = None
    gratitude: str | None = None
    source: str = "staff"
    updated_at: str | None = None


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
    # Set when the flag is derived from a structured vulnerable-groups
    # record, e.g. 'vg_lac:3' (see sync_vulnerable_flags).
    source_ref: str | None = None

    @property
    def derived(self) -> bool:
        return bool(self.source_ref)

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
    paths.ensure_sixth_form_directories()
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
        _ensure_unified_checkin_columns(conn)
        _records.ensure_columns(conn, "wellbeing_flags",
                                {"source_ref": "TEXT"})
        conn.executescript(_VG_SCHEMA)
        migrate_student_wellbeing_entries(conn)
        conn.commit()
    logger.debug("Wellbeing schema ready at %s", DB_PATH)

    _DB_READY = True


def _ensure_unified_checkin_columns(conn: sqlite3.Connection) -> None:
    """Columns that let ``wellbeing_checkins`` hold Student Wellbeing
    journal entries too (energy, sleep hours, gratitude, who wrote it)."""
    _records.ensure_columns(conn, "wellbeing_checkins", {
        "energy_score": "INTEGER",
        "sleep_hours": "REAL",
        "gratitude": "TEXT",
        "source": "TEXT NOT NULL DEFAULT 'staff'",
        "legacy_entry_id": "INTEGER",
        "updated_at": "TEXT",
    })
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_wci_legacy "
        "ON wellbeing_checkins(legacy_entry_id) "
        "WHERE legacy_entry_id IS NOT NULL")
    # A student keeps one journal entry per day (the old
    # student_wellbeing_entries UNIQUE rule); staff check-ins are free.
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_wci_self_day "
        "ON wellbeing_checkins(student_id, checkin_date) "
        "WHERE source = 'self'")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_wci_source "
        "ON wellbeing_checkins(source)")


def migrate_student_wellbeing_entries(
        conn: sqlite3.Connection | None = None) -> int:
    """Copy rows from the retired ``student_wellbeing_entries`` table
    into ``wellbeing_checkins`` (source='self').

    Idempotent: each old row is copied once, keyed on
    ``legacy_entry_id``. The old table is left in place, unchanged.
    Returns the number of rows copied.
    """
    own = conn is None
    if own:
        conn = _connect()
    try:
        if not _records.table_exists(conn, "student_wellbeing_entries"):
            return 0
        cur = conn.execute(
            """INSERT OR IGNORE INTO wellbeing_checkins
                   (student_id, checkin_date, mood_score, stress_score,
                    sleep_score, energy_score, sleep_hours, notes,
                    gratitude, recorded_by, source, legacy_entry_id,
                    created_at, updated_at)
               SELECT e.student_id, e.entry_date, e.mood_score,
                      e.stress_score, NULL, e.energy_score,
                      e.sleep_hours, e.notes, e.gratitude, NULL,
                      'self', e.entry_id, e.created_at, e.updated_at
                 FROM student_wellbeing_entries e
                WHERE NOT EXISTS (
                      SELECT 1 FROM wellbeing_checkins c
                       WHERE c.legacy_entry_id = e.entry_id)
                  AND EXISTS (
                      SELECT 1 FROM students s
                       WHERE s.student_id = e.student_id)""")
        n = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
        if own:
            conn.commit()
        if n:
            logger.info("Copied %d student wellbeing journal entr%s into "
                        "wellbeing_checkins", n, "y" if n == 1 else "ies")
        return n
    finally:
        if own:
            conn.close()


def _row_checkin(r: sqlite3.Row) -> CheckIn:
    keys = set(r.keys())

    def _opt(k: str) -> Any:
        return r[k] if k in keys else None

    return CheckIn(
        checkin_id=r["checkin_id"], student_id=r["student_id"],
        checkin_date=r["checkin_date"],
        mood_score=r["mood_score"], stress_score=r["stress_score"],
        sleep_score=r["sleep_score"],
        notes=r["notes"], recorded_by=r["recorded_by"],
        created_at=r["created_at"],
        energy_score=_opt("energy_score"),
        sleep_hours=_opt("sleep_hours"),
        gratitude=_opt("gratitude"),
        source=_opt("source") or "staff",
        updated_at=_opt("updated_at"),
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
        source_ref=r["source_ref"] if "source_ref" in r.keys() else None,
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
    out["energy_score"] = _validate_score(data.get("energy_score"), "Energy")
    out["sleep_hours"] = _validate_sleep_hours(data.get("sleep_hours"))
    out["gratitude"] = (data.get("gratitude") or "").strip() or None
    if all(out[k] is None for k in ("mood_score", "stress_score",
                                    "sleep_score", "energy_score",
                                    "sleep_hours", "gratitude")) \
            and not (data.get("notes") or "").strip():
        raise ValidationError(
            "Provide at least one score or a note for the check-in")
    out["notes"]       = (data.get("notes") or "").strip() or None
    out["recorded_by"] = (data.get("recorded_by") or "").strip() or None
    source = (data.get("source") or "staff").strip()
    if source not in CHECKIN_SOURCES:
        raise ValidationError(
            f"Source must be one of: {', '.join(CHECKIN_SOURCES)}")
    out["source"] = source
    return out


def _validate_sleep_hours(value: Any) -> float | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    try:
        h = float(value)
    except (TypeError, ValueError):
        raise ValidationError("Sleep hours must be a number") from None
    if h < 0 or h > 24:
        raise ValidationError("Sleep hours must be between 0 and 24")
    return round(h, 2)


def create_checkin(data: dict[str, Any]) -> CheckIn:
    init_db()
    try:
        p = _validate_checkin_payload(data)
    except ValidationError as e:
        logger.warning("create_checkin validation failed: %s", e)
        raise
    with _connect() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO wellbeing_checkins
                       (student_id, checkin_date, mood_score, stress_score,
                        sleep_score, energy_score, sleep_hours, gratitude,
                        source, notes, recorded_by, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           datetime('now'), datetime('now'))""",
                (p["student_id"], p["checkin_date"], p["mood_score"],
                 p["stress_score"], p["sleep_score"], p["energy_score"],
                 p["sleep_hours"], p["gratitude"], p["source"],
                 p["notes"], p["recorded_by"]),
            )
        except sqlite3.IntegrityError as e:
            raise ValidationError(
                f"A journal entry for {p['student_id']} on "
                f"{p['checkin_date']} already exists — edit it instead."
            ) from e
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
    source: str | None = None,
) -> list[CheckIn]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if source:
        if source not in CHECKIN_SOURCES:
            raise ValidationError(
                f"Source must be one of: {', '.join(CHECKIN_SOURCES)}")
        clauses.append("source = ?")
        args.append(source)
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
        "energy_score": data.get("energy_score", existing.energy_score),
        "sleep_hours":  data.get("sleep_hours", existing.sleep_hours),
        "gratitude":    data.get("gratitude", existing.gratitude),
        "notes":        data.get("notes", existing.notes),
        "recorded_by":  data.get("recorded_by", existing.recorded_by),
        "source":       existing.source,
    })
    with _connect() as conn:
        try:
            conn.execute(
                """UPDATE wellbeing_checkins SET
                       checkin_date = ?, mood_score = ?, stress_score = ?,
                       sleep_score = ?, energy_score = ?, sleep_hours = ?,
                       gratitude = ?, notes = ?, recorded_by = ?,
                       updated_at = datetime('now')
                   WHERE checkin_id = ?""",
                (p["checkin_date"], p["mood_score"], p["stress_score"],
                 p["sleep_score"], p["energy_score"], p["sleep_hours"],
                 p["gratitude"], p["notes"], p["recorded_by"],
                 checkin_id),
            )
        except sqlite3.IntegrityError as e:
            raise ValidationError(
                f"Another journal entry for {p['student_id']} on "
                f"{p['checkin_date']} already exists.") from e
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


# ══ Vulnerable groups ═════════════════════════════════════════════
#
# Structured records behind the "Looked-After Child", "Care Leaver",
# "Previously Looked-After" and "Young Carer" flags. The flags stay
# (other screens read them) but are now derived from these records by
# sync_vulnerable_flags(); hand-made flags are left alone.
#
# Access: PASTORAL capability, object-level can_see_student, and every
# read/write is written to the sensitive-access log.

CARE_STATUSES: tuple[str, ...] = (
    "Looked-After Child",
    "Previously Looked-After",
    "Care Leaver (Eligible)",
    "Care Leaver (Relevant)",
    "Care Leaver (Former Relevant)",
)
LEGAL_STATUSES: tuple[str, ...] = (
    "Section 20 (voluntary)", "Care Order (s31)",
    "Interim Care Order", "Placement Order",
    "Special Guardianship Order", "Child Arrangements Order",
    "Adoption Order", "Remand", "Other",
)
PLACEMENT_TYPES: tuple[str, ...] = (
    "Foster Care", "Kinship / Family & Friends", "Residential",
    "Semi-Independent", "Supported Lodgings", "Independent",
    "Staying Put", "Home with Parents", "Other",
)

#: Care status -> wellbeing flag it derives.
_CARE_FLAG: dict[str, str] = {
    "Looked-After Child": "Looked-After Child",
    "Previously Looked-After": "Previously Looked-After",
    "Care Leaver (Eligible)": "Care Leaver",
    "Care Leaver (Relevant)": "Care Leaver",
    "Care Leaver (Former Relevant)": "Care Leaver",
}

#: Groups that the 16-19 Bursary Fund treats as "defined vulnerable"
#: (up to £1,200 a year). Recorded here; the bursary itself is finance's.
BURSARY_VULNERABLE_STATUSES: frozenset[str] = frozenset({
    "Looked-After Child", "Care Leaver (Eligible)",
    "Care Leaver (Relevant)", "Care Leaver (Former Relevant)",
})

_VG_SCHEMA = """
CREATE TABLE IF NOT EXISTS vg_care_records (
    record_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id             TEXT NOT NULL,
    care_status            TEXT NOT NULL,
    local_authority        TEXT NOT NULL,
    legal_status           TEXT,
    placement_type         TEXT,
    start_date             TEXT,
    end_date               TEXT,
    social_worker          TEXT,
    social_worker_phone    TEXT,
    social_worker_email    TEXT,
    personal_adviser       TEXT,
    virtual_school_contact TEXT,
    virtual_school_phone   TEXT,
    virtual_school_email   TEXT,
    designated_teacher     TEXT,
    last_pep_on            TEXT,
    next_pep_due           TEXT,
    bursary_eligible       INTEGER NOT NULL DEFAULT 0,
    bursary_notes          TEXT,
    notes                  TEXT,
    created_at             TEXT DEFAULT (datetime('now')),
    updated_at             TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS vg_pep_reviews (
    review_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id        INTEGER NOT NULL,
    student_id       TEXT NOT NULL,
    review_date      TEXT NOT NULL,
    attendees        TEXT,
    progress_summary TEXT,
    targets          TEXT,
    support_agreed   TEXT,
    pupil_voice      TEXT,
    next_review_due  TEXT,
    recorded_by      TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (record_id) REFERENCES vg_care_records(record_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS vg_young_carers (
    carer_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id       TEXT NOT NULL,
    cares_for        TEXT NOT NULL,
    relationship     TEXT,
    care_tasks       TEXT,
    hours_per_week   INTEGER,
    identified_on    TEXT,
    assessment_date  TEXT,
    support_provider TEXT,
    support_plan     TEXT,
    last_reviewed    TEXT,
    next_review_due  TEXT,
    end_date         TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_vgc_student ON vg_care_records(student_id);
CREATE INDEX IF NOT EXISTS idx_vgp_record  ON vg_pep_reviews(record_id);
CREATE INDEX IF NOT EXISTS idx_vgy_student ON vg_young_carers(student_id);
"""


@dataclass
class CareRecord:
    record_id: int
    student_id: str
    care_status: str
    local_authority: str
    legal_status: str | None
    placement_type: str | None
    start_date: str | None
    end_date: str | None
    social_worker: str | None
    social_worker_phone: str | None
    social_worker_email: str | None
    personal_adviser: str | None
    virtual_school_contact: str | None
    virtual_school_phone: str | None
    virtual_school_email: str | None
    designated_teacher: str | None
    last_pep_on: str | None
    next_pep_due: str | None
    bursary_eligible: bool
    bursary_notes: str | None
    notes: str | None
    created_at: str | None
    updated_at: str | None

    @property
    def active(self) -> bool:
        return not self.end_date or self.end_date >= _records.today()

    @property
    def pep_overdue(self) -> bool:
        return bool(self.active and self.next_pep_due
                    and self.next_pep_due < _records.today())


@dataclass
class PEPReview:
    review_id: int
    record_id: int
    student_id: str
    review_date: str
    attendees: str | None
    progress_summary: str | None
    targets: str | None
    support_agreed: str | None
    pupil_voice: str | None
    next_review_due: str | None
    recorded_by: str | None
    notes: str | None
    created_at: str | None
    updated_at: str | None


@dataclass
class YoungCarer:
    carer_id: int
    student_id: str
    cares_for: str
    relationship: str | None
    care_tasks: str | None
    hours_per_week: int | None
    identified_on: str | None
    assessment_date: str | None
    support_provider: str | None
    support_plan: str | None
    last_reviewed: str | None
    next_review_due: str | None
    end_date: str | None
    notes: str | None
    created_at: str | None
    updated_at: str | None

    @property
    def active(self) -> bool:
        return not self.end_date or self.end_date >= _records.today()

    @property
    def review_overdue(self) -> bool:
        return bool(self.active and self.next_review_due
                    and self.next_review_due < _records.today())


_C = _records.Col

CARE_SPEC = _records.TableSpec(
    table="vg_care_records", id_col="record_id", row_type=CareRecord,
    label="Care record", order_by="end_date IS NOT NULL, student_id",
    cols=(
        _C("student_id", "Student", "student", required=True, fixed=True),
        _C("care_status", "Care status", "choice", required=True,
           choices=CARE_STATUSES),
        _C("local_authority", "Local authority", required=True),
        _C("legal_status", "Legal status", "choice",
           choices=LEGAL_STATUSES, listed=False),
        _C("placement_type", "Placement", "choice",
           choices=PLACEMENT_TYPES, listed=False),
        _C("start_date", "Start date", "date", listed=False),
        _C("end_date", "End date", "date"),
        _C("social_worker", "Social worker"),
        _C("social_worker_phone", "Social worker phone", listed=False),
        _C("social_worker_email", "Social worker e-mail", listed=False),
        _C("personal_adviser", "Personal adviser (care leaver)",
           listed=False),
        _C("virtual_school_contact", "Virtual school contact"),
        _C("virtual_school_phone", "Virtual school phone", listed=False),
        _C("virtual_school_email", "Virtual school e-mail", listed=False),
        _C("designated_teacher", "Designated teacher"),
        _C("last_pep_on", "Last PEP", "date"),
        _C("next_pep_due", "Next PEP due", "date"),
        _C("bursary_eligible", "16-19 bursary (vulnerable group)", "bool"),
        _C("bursary_notes", "Bursary notes", "multiline", listed=False),
        _C("notes", "Notes", "multiline", listed=False),
    ))

PEP_SPEC = _records.TableSpec(
    table="vg_pep_reviews", id_col="review_id", row_type=PEPReview,
    label="PEP review", order_by="review_date DESC, review_id DESC",
    cols=(
        _C("record_id", "Care record #", "int", required=True, fixed=True),
        _C("student_id", "Student", "student", fixed=True, hidden=True),
        _C("review_date", "Review date", "date", required=True,
           default=_records.today),
        _C("attendees", "Attendees"),
        _C("progress_summary", "Progress", "multiline", listed=False),
        _C("targets", "Targets", "multiline"),
        _C("support_agreed", "Support / PP+ agreed", "multiline",
           listed=False),
        _C("pupil_voice", "Student voice", "multiline", listed=False),
        _C("next_review_due", "Next review due", "date"),
        _C("recorded_by", "Recorded by"),
        _C("notes", "Notes", "multiline", listed=False),
    ))

YOUNG_CARER_SPEC = _records.TableSpec(
    table="vg_young_carers", id_col="carer_id", row_type=YoungCarer,
    label="Young carer record", order_by="end_date IS NOT NULL, student_id",
    cols=(
        _C("student_id", "Student", "student", required=True, fixed=True),
        _C("cares_for", "Cares for", required=True),
        _C("relationship", "Relationship"),
        _C("care_tasks", "Caring tasks", "multiline", listed=False),
        _C("hours_per_week", "Hours / week", "int", min_value=0,
           max_value=168),
        _C("identified_on", "Identified on", "date", listed=False),
        _C("assessment_date", "Young carer's needs assessment", "date",
           listed=False),
        _C("support_provider", "Support provider"),
        _C("support_plan", "Support plan", "multiline", listed=False),
        _C("last_reviewed", "Last reviewed", "date"),
        _C("next_review_due", "Next review due", "date"),
        _C("end_date", "End date", "date"),
        _C("notes", "Notes", "multiline", listed=False),
    ))


def _student_ok(sid: str) -> bool:
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    return _students.get_student(sid) is not None


def _vg_guard(action: str, student_id: str | None = None,
              ref: str | None = None) -> Any:
    return _records.guard("PASTORAL", "vulnerable_groups", action,
                          student_id=student_id, record_ref=ref)


# ── Care records (LAC / PLAC / care leavers) ──────────────────────

def _care_rules(p: dict[str, Any]) -> None:
    if p["start_date"] and p["end_date"] and p["end_date"] < p["start_date"]:
        raise ValidationError("End date cannot be before start date")
    if p["care_status"] in BURSARY_VULNERABLE_STATUSES \
            and not p.get("bursary_eligible"):
        # Defined vulnerable groups are always bursary-eligible.
        p["bursary_eligible"] = 1


def create_care_record(data: dict[str, Any]) -> CareRecord:
    init_db()
    p = _records.validate(CARE_SPEC, data, error=ValidationError,
                          student_exists=_student_ok)
    _care_rules(p)
    _vg_guard("create care record", p["student_id"])
    with _connect() as conn:
        new_id = _records.insert(conn, CARE_SPEC, p)
        conn.commit()
    logger.info("Created care record #%d for %s (%s, %s)", new_id,
                p["student_id"], p["care_status"], p["local_authority"])
    sync_vulnerable_flags(p["student_id"])
    return get_care_record(new_id)


def get_care_record(record_id: int) -> CareRecord | None:
    init_db()
    with _connect() as conn:
        rec = _records.fetch(conn, CARE_SPEC, record_id)
    if rec is not None:
        _vg_guard("view care record", rec.student_id, f"vg_care:{record_id}")
    return rec


def list_care_records(*, student_id: str | None = None,
                      care_status: str | None = None,
                      active_only: bool = False,
                      pep_overdue_only: bool = False) -> list[CareRecord]:
    init_db()
    _vg_guard("list care records", student_id)
    where, args = [], []
    if active_only or pep_overdue_only:
        where.append("(end_date IS NULL OR end_date >= ?)")
        args.append(_records.today())
    if pep_overdue_only:
        where.append("next_pep_due IS NOT NULL AND next_pep_due < ?")
        args.append(_records.today())
    with _connect() as conn:
        rows = _records.select(
            conn, CARE_SPEC,
            equals={"student_id": student_id, "care_status": care_status},
            where=where, args=args)
    return _records.visible_filter("PASTORAL", rows)


def update_care_record(record_id: int, data: dict[str, Any]) -> CareRecord:
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, CARE_SPEC, record_id)
    if existing is None:
        raise ValidationError(f"No care record #{record_id}")
    p = _records.validate(CARE_SPEC, data, error=ValidationError,
                          existing=existing, student_exists=_student_ok)
    _care_rules(p)
    _vg_guard("update care record", existing.student_id,
              f"vg_care:{record_id}")
    with _connect() as conn:
        _records.update(conn, CARE_SPEC, record_id, p)
        conn.commit()
    sync_vulnerable_flags(existing.student_id)
    return get_care_record(record_id)


def delete_care_record(record_id: int) -> bool:
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, CARE_SPEC, record_id)
        if existing is None:
            return False
        _vg_guard("delete care record", existing.student_id,
                  f"vg_care:{record_id}")
        try:
            ok = _records.delete(conn, CARE_SPEC, record_id)
        except sqlite3.IntegrityError:
            # PEP actions / care-leaver plans (looked_after) restrict the
            # delete so that history is never lost by cascade.
            raise ValidationError(
                f"Care record #{record_id} has PEP actions or a care-leaver "
                "plan; set an end date instead of deleting") from None
        conn.commit()
    sync_vulnerable_flags(existing.student_id)
    return ok


# ── PEP reviews ───────────────────────────────────────────────────

def record_pep_review(data: dict[str, Any]) -> PEPReview:
    """Log a Personal Education Plan review and roll the care record's
    last/next PEP dates forward."""
    init_db()
    p = _records.validate(PEP_SPEC, data, error=ValidationError)
    with _connect() as conn:
        rec = _records.fetch(conn, CARE_SPEC, p["record_id"])
    if rec is None:
        raise ValidationError(f"No care record #{p['record_id']}")
    if p["next_review_due"] and p["next_review_due"] <= p["review_date"]:
        raise ValidationError("Next review must be after the review date")
    actor = _vg_guard("record PEP review", rec.student_id,
                      f"vg_care:{rec.record_id}")
    p["student_id"] = rec.student_id
    p["recorded_by"] = p["recorded_by"] or actor.staff_name or actor.username
    with _connect() as conn:
        new_id = _records.insert(conn, PEP_SPEC, p)
        latest = conn.execute(
            "SELECT MAX(review_date) FROM vg_pep_reviews WHERE record_id = ?",
            (rec.record_id,)).fetchone()[0]
        if latest == p["review_date"]:
            conn.execute(
                "UPDATE vg_care_records SET last_pep_on = ?, "
                "next_pep_due = COALESCE(?, next_pep_due), "
                "updated_at = datetime('now') WHERE record_id = ?",
                (p["review_date"], p["next_review_due"], rec.record_id))
        conn.commit()
        out = _records.fetch(conn, PEP_SPEC, new_id)
    logger.info("Recorded PEP review #%d for care record #%d",
                new_id, rec.record_id)
    return out


def list_pep_reviews(record_id: int) -> list[PEPReview]:
    init_db()
    rec = get_care_record(record_id)
    if rec is None:
        return []
    with _connect() as conn:
        return _records.select(conn, PEP_SPEC,
                               equals={"record_id": record_id})


def update_pep_review(review_id: int, data: dict[str, Any]) -> PEPReview:
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, PEP_SPEC, review_id)
    if existing is None:
        raise ValidationError(f"No PEP review #{review_id}")
    p = _records.validate(PEP_SPEC, data, error=ValidationError,
                          existing=existing)
    _vg_guard("update PEP review", existing.student_id, f"vg_pep:{review_id}")
    with _connect() as conn:
        _records.update(conn, PEP_SPEC, review_id, p)
        conn.commit()
        return _records.fetch(conn, PEP_SPEC, review_id)


def delete_pep_review(review_id: int) -> bool:
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, PEP_SPEC, review_id)
        if existing is None:
            return False
        _vg_guard("delete PEP review", existing.student_id,
                  f"vg_pep:{review_id}")
        ok = _records.delete(conn, PEP_SPEC, review_id)
        conn.commit()
        return ok


# ── Young carers ──────────────────────────────────────────────────

def create_young_carer(data: dict[str, Any]) -> YoungCarer:
    init_db()
    p = _records.validate(YOUNG_CARER_SPEC, data, error=ValidationError,
                          student_exists=_student_ok)
    _vg_guard("create young carer record", p["student_id"])
    with _connect() as conn:
        new_id = _records.insert(conn, YOUNG_CARER_SPEC, p)
        conn.commit()
    logger.info("Created young carer record #%d for %s", new_id,
                p["student_id"])
    sync_vulnerable_flags(p["student_id"])
    return get_young_carer(new_id)


def get_young_carer(carer_id: int) -> YoungCarer | None:
    init_db()
    with _connect() as conn:
        rec = _records.fetch(conn, YOUNG_CARER_SPEC, carer_id)
    if rec is not None:
        _vg_guard("view young carer record", rec.student_id,
                  f"vg_carer:{carer_id}")
    return rec


def list_young_carers(*, student_id: str | None = None,
                      active_only: bool = False,
                      review_overdue_only: bool = False) -> list[YoungCarer]:
    init_db()
    _vg_guard("list young carers", student_id)
    where, args = [], []
    if active_only or review_overdue_only:
        where.append("(end_date IS NULL OR end_date >= ?)")
        args.append(_records.today())
    if review_overdue_only:
        where.append("next_review_due IS NOT NULL AND next_review_due < ?")
        args.append(_records.today())
    with _connect() as conn:
        rows = _records.select(conn, YOUNG_CARER_SPEC,
                               equals={"student_id": student_id},
                               where=where, args=args)
    return _records.visible_filter("PASTORAL", rows)


def update_young_carer(carer_id: int, data: dict[str, Any]) -> YoungCarer:
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, YOUNG_CARER_SPEC, carer_id)
    if existing is None:
        raise ValidationError(f"No young carer record #{carer_id}")
    p = _records.validate(YOUNG_CARER_SPEC, data, error=ValidationError,
                          existing=existing, student_exists=_student_ok)
    _vg_guard("update young carer record", existing.student_id,
              f"vg_carer:{carer_id}")
    with _connect() as conn:
        _records.update(conn, YOUNG_CARER_SPEC, carer_id, p)
        conn.commit()
    sync_vulnerable_flags(existing.student_id)
    return get_young_carer(carer_id)


def review_young_carer(carer_id: int, *, reviewed_on: str | None = None,
                       next_review_due: str | None = None,
                       notes: str | None = None) -> YoungCarer:
    """Record a support-plan review: stamps last_reviewed, sets the next
    review date, and appends a dated line to the notes."""
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, YOUNG_CARER_SPEC, carer_id)
    if existing is None:
        raise ValidationError(f"No young carer record #{carer_id}")
    on = _records.check_date(reviewed_on, "Reviewed on",
                             ValidationError) or _records.today()
    nxt = _records.check_date(next_review_due, "Next review due",
                              ValidationError)
    if nxt and nxt <= on:
        raise ValidationError("Next review must be after the review date")
    payload: dict[str, Any] = {"last_reviewed": on}
    if nxt:
        payload["next_review_due"] = nxt
    if notes and notes.strip():
        line = f"[{on} review] {notes.strip()}"
        payload["notes"] = (f"{existing.notes}\n{line}"
                            if existing.notes else line)
    return update_young_carer(carer_id, payload)


def delete_young_carer(carer_id: int) -> bool:
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, YOUNG_CARER_SPEC, carer_id)
        if existing is None:
            return False
        _vg_guard("delete young carer record", existing.student_id,
                  f"vg_carer:{carer_id}")
        ok = _records.delete(conn, YOUNG_CARER_SPEC, carer_id)
        conn.commit()
    sync_vulnerable_flags(existing.student_id)
    return ok


# ── Flag derivation ───────────────────────────────────────────────

def sync_vulnerable_flags(student_id: str | None = None) -> int:
    """Make the wellbeing flags match the structured records.

    Each active care / young-carer record owns one flag (``source_ref``
    'vg_care:<id>' / 'vg_carer:<id>'). Ended or deleted records close
    their flag. A hand-made open flag of the same type is adopted
    instead of duplicated. Returns the number of flags changed.
    """
    init_db()
    today = _records.today()
    changed = 0
    with _connect() as conn:
        sql_s = " WHERE student_id = ?" if student_id else ""
        args = (student_id,) if student_id else ()
        wanted: dict[str, tuple[str, str, str | None]] = {}
        for r in conn.execute(
                "SELECT record_id, student_id, care_status, start_date, "
                "end_date FROM vg_care_records" + sql_s, args):
            if r["end_date"] and r["end_date"] < today:
                continue
            wanted[f"vg_care:{r['record_id']}"] = (
                r["student_id"], _CARE_FLAG[r["care_status"]], r["start_date"])
        for r in conn.execute(
                "SELECT carer_id, student_id, identified_on, end_date "
                "FROM vg_young_carers" + sql_s, args):
            if r["end_date"] and r["end_date"] < today:
                continue
            wanted[f"vg_carer:{r['carer_id']}"] = (
                r["student_id"], "Young Carer", r["identified_on"])

        existing = {r["source_ref"]: r for r in conn.execute(
            "SELECT * FROM wellbeing_flags WHERE source_ref IS NOT NULL"
            + (" AND student_id = ?" if student_id else ""), args)}

        for ref, (sid, ftype, start) in wanted.items():
            row = existing.get(ref)
            if row is not None:
                if row["end_date"] is not None or row["flag_type"] != ftype:
                    conn.execute(
                        "UPDATE wellbeing_flags SET end_date = NULL, "
                        "flag_type = ?, updated_at = datetime('now') "
                        "WHERE flag_id = ?", (ftype, row["flag_id"]))
                    changed += 1
                continue
            manual = conn.execute(
                "SELECT flag_id FROM wellbeing_flags WHERE student_id = ? "
                "AND flag_type = ? AND end_date IS NULL "
                "AND source_ref IS NULL", (sid, ftype)).fetchone()
            if manual is not None:
                conn.execute(
                    "UPDATE wellbeing_flags SET source_ref = ?, "
                    "updated_at = datetime('now') WHERE flag_id = ?",
                    (ref, manual["flag_id"]))
            else:
                conn.execute(
                    "INSERT INTO wellbeing_flags (student_id, flag_type, "
                    "start_date, notes, source_ref, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, datetime('now'), "
                    "datetime('now'))",
                    (sid, ftype, start or today,
                     "Derived from the vulnerable groups register", ref))
            changed += 1

        for ref, row in existing.items():
            if ref.startswith("vg_") and ref not in wanted \
                    and row["end_date"] is None:
                conn.execute(
                    "UPDATE wellbeing_flags SET end_date = ?, "
                    "updated_at = datetime('now') WHERE flag_id = ?",
                    (today, row["flag_id"]))
                changed += 1
        conn.commit()
    if changed:
        logger.info("Vulnerable-group flags synced (%d change(s))%s",
                    changed, f" for {student_id}" if student_id else "")
    return changed


# ── Register view ─────────────────────────────────────────────────

#: Hand-made flag types that put a student on the register even with
#: no structured record behind them.
REGISTER_FLAG_TYPES: tuple[str, ...] = (
    "Young Carer", "Looked-After Child", "Previously Looked-After",
    "Care Leaver", "Free School Meals", "Pupil Premium / Bursary",
    "SEND", "Mental Health",
)


@dataclass
class VulnerableRow:
    student_id: str
    student_name: str
    groups: list[str]
    care_status: str | None = None
    local_authority: str | None = None
    social_worker: str | None = None
    virtual_school_contact: str | None = None
    designated_teacher: str | None = None
    next_pep_due: str | None = None
    pep_overdue: bool = False
    cares_for: str | None = None
    young_carer_review_due: str | None = None
    young_carer_review_overdue: bool = False
    send_status: str | None = None
    bursary_eligible: bool = False
    flags_without_record: list[str] = field(default_factory=list)


def vulnerable_groups_register(*, group: str | None = None
                               ) -> list[VulnerableRow]:
    """One row per student in any vulnerable group: care records,
    young carers, the SEND register, and open register-type flags."""
    init_db()
    _vg_guard("view vulnerable groups register")
    rows: dict[str, VulnerableRow] = {}

    def _get(sid: str) -> VulnerableRow:
        if sid not in rows:
            rows[sid] = VulnerableRow(student_id=sid, student_name="",
                                      groups=[])
        return rows[sid]

    def _add_group(row: VulnerableRow, g: str) -> None:
        if g not in row.groups:
            row.groups.append(g)

    today = _records.today()
    with _connect() as conn:
        care = _records.select(
            conn, CARE_SPEC, where=["(end_date IS NULL OR end_date >= ?)"],
            args=[today])
        carers = _records.select(
            conn, YOUNG_CARER_SPEC,
            where=["(end_date IS NULL OR end_date >= ?)"], args=[today])
        flags = conn.execute(
            "SELECT student_id, flag_type, source_ref FROM wellbeing_flags "
            "WHERE end_date IS NULL").fetchall()
        send_rows = []
        if _records.table_exists(conn, "send_register"):
            send_rows = conn.execute(
                "SELECT student_id, register_status FROM send_register "
                "WHERE status NOT IN ('Exited','Archived')").fetchall()

    for c in care:
        r = _get(c.student_id)
        _add_group(r, _CARE_FLAG[c.care_status])
        r.care_status = c.care_status
        r.local_authority = c.local_authority
        r.social_worker = c.social_worker
        r.virtual_school_contact = c.virtual_school_contact
        r.designated_teacher = c.designated_teacher
        r.next_pep_due = c.next_pep_due
        r.pep_overdue = r.pep_overdue or c.pep_overdue
        r.bursary_eligible = r.bursary_eligible or c.bursary_eligible
    for y in carers:
        r = _get(y.student_id)
        _add_group(r, "Young Carer")
        r.cares_for = (f"{r.cares_for}; {y.cares_for}"
                       if r.cares_for else y.cares_for)
        if y.next_review_due and (not r.young_carer_review_due
                                  or y.next_review_due
                                  < r.young_carer_review_due):
            r.young_carer_review_due = y.next_review_due
        r.young_carer_review_overdue = (r.young_carer_review_overdue
                                        or y.review_overdue)
    for s in send_rows:
        r = _get(s["student_id"])
        _add_group(r, "SEND")
        r.send_status = s["register_status"]
    for f in flags:
        if f["flag_type"] not in REGISTER_FLAG_TYPES:
            continue
        r = _get(f["student_id"])
        if f["flag_type"] not in r.groups:
            _add_group(r, f["flag_type"])
            if not f["source_ref"] and f["flag_type"] in (
                    "Young Carer", "Looked-After Child",
                    "Previously Looked-After", "Care Leaver"):
                r.flags_without_record.append(f["flag_type"])

    from education_system.systems.sixth_form.domain.learners.students import students as _students
    names = {s.student_id: s.full_name for s in _students.list_students()}
    out = []
    for r in rows.values():
        r.student_name = names.get(r.student_id, "(unknown)")
        if group and group not in r.groups:
            continue
        out.append(r)
    out.sort(key=lambda r: (not r.pep_overdue, r.student_name))
    return _records.visible_filter("PASTORAL", out)
