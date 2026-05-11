"""Careers-guidance data layer for the Sixth Form System.

Two tables:

* ``career_sessions`` — one row per session (1-to-1 interview,
  workshop, employer encounter…), each optionally tagged to a Gatsby
  benchmark (1-8) so the school can report on its careers programme.
* ``career_aspirations`` — one row per student capturing their
  intended pathway after sixth form (university / apprenticeship /
  employment / gap year / undecided), target career, employer, course.

Cascade: deleting a student wipes their sessions and aspirations.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.sixthform_system.core import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.CAREERS_DB

SESSION_TYPES: tuple[str, ...] = (
    "1-to-1 Interview", "Group Session", "Workshop",
    "Employer Encounter", "University Visit",
    "Mock Interview", "CV Review", "Drop-In", "Other",
)
DEFAULT_SESSION_TYPE: str = "1-to-1 Interview"

SESSION_STATUSES: tuple[str, ...] = (
    "Scheduled", "Completed", "Cancelled", "No-Show",
)
DEFAULT_SESSION_STATUS: str = "Completed"

# Gatsby benchmarks — the eight standards English schools are measured
# against for careers provision.
GATSBY_BENCHMARKS: dict[int, str] = {
    1: "A stable careers programme",
    2: "Learning from career and labour market information",
    3: "Addressing the needs of each pupil",
    4: "Linking curriculum learning to careers",
    5: "Encounters with employers and employees",
    6: "Experiences of workplaces",
    7: "Encounters with further and higher education",
    8: "Personal guidance",
}

PATHWAYS: tuple[str, ...] = (
    "University", "Apprenticeship", "Employment",
    "Gap Year", "Undecided",
)
DEFAULT_PATHWAY: str = "Undecided"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS career_sessions (
    session_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id       TEXT NOT NULL,
    session_date     TEXT NOT NULL,
    advisor          TEXT,
    session_type     TEXT NOT NULL DEFAULT '1-to-1 Interview',
    duration_minutes INTEGER,
    gatsby_benchmark INTEGER,
    topics           TEXT,
    action_plan      TEXT,
    follow_up_date   TEXT,
    status           TEXT NOT NULL DEFAULT 'Completed',
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS career_aspirations (
    aspiration_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL UNIQUE,
    primary_pathway TEXT NOT NULL DEFAULT 'Undecided',
    target_career   TEXT,
    target_sector   TEXT,
    target_employer TEXT,
    target_course   TEXT,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_csessions_student ON career_sessions(student_id);
CREATE INDEX IF NOT EXISTS idx_csessions_date    ON career_sessions(session_date);
CREATE INDEX IF NOT EXISTS idx_csessions_benchmk ON career_sessions(gatsby_benchmark);
CREATE INDEX IF NOT EXISTS idx_aspir_pathway     ON career_aspirations(primary_pathway);
"""


@dataclass
class CareerSession:
    session_id: int
    student_id: str
    session_date: str
    advisor: str | None
    session_type: str
    duration_minutes: int | None
    gatsby_benchmark: int | None
    topics: str | None
    action_plan: str | None
    follow_up_date: str | None
    status: str
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class CareerAspiration:
    aspiration_id: int
    student_id: str
    primary_pathway: str
    target_career: str | None
    target_sector: str | None
    target_employer: str | None
    target_course: str | None
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class SessionRow:
    session: CareerSession
    student_name: str


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    from education_system.sixthform_system.modules.domain.students import students as _students
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Careers schema ready at %s", DB_PATH)


def _row_session(r: sqlite3.Row) -> CareerSession:
    return CareerSession(
        session_id=r["session_id"], student_id=r["student_id"],
        session_date=r["session_date"], advisor=r["advisor"],
        session_type=r["session_type"],
        duration_minutes=r["duration_minutes"],
        gatsby_benchmark=r["gatsby_benchmark"],
        topics=r["topics"], action_plan=r["action_plan"],
        follow_up_date=r["follow_up_date"],
        status=r["status"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_aspir(r: sqlite3.Row) -> CareerAspiration:
    return CareerAspiration(
        aspiration_id=r["aspiration_id"], student_id=r["student_id"],
        primary_pathway=r["primary_pathway"],
        target_career=r["target_career"],
        target_sector=r["target_sector"],
        target_employer=r["target_employer"],
        target_course=r["target_course"],
        notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for invalid careers input."""


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_date(value: Any, label: str) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return s


def _validate_session_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    sid = _require(data.get("student_id"), "Student ID").strip()
    from education_system.sixthform_system.modules.domain.students import students as _students
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    out["student_id"] = sid

    sd = _validate_date(_require(data.get("session_date"), "Session date"),
                         "Session date")
    out["session_date"] = sd

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

    bench = data.get("gatsby_benchmark")
    if bench in (None, ""):
        out["gatsby_benchmark"] = None
    else:
        try:
            b = int(bench)
        except (TypeError, ValueError):
            raise ValidationError(
                "Gatsby benchmark must be a number 1-8") from None
        if b not in GATSBY_BENCHMARKS:
            raise ValidationError(
                f"Gatsby benchmark must be one of: "
                f"{', '.join(str(k) for k in GATSBY_BENCHMARKS)}")
        out["gatsby_benchmark"] = b

    status = (data.get("status") or DEFAULT_SESSION_STATUS).strip()
    if status not in SESSION_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(SESSION_STATUSES)}")
    out["status"] = status

    out["follow_up_date"] = _validate_date(
        data.get("follow_up_date"), "Follow-up date")

    out["advisor"]     = (data.get("advisor") or "").strip() or None
    out["topics"]      = (data.get("topics") or "").strip() or None
    out["action_plan"] = (data.get("action_plan") or "").strip() or None
    out["notes"]       = (data.get("notes") or "").strip() or None
    return out


def _validate_aspiration_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    sid = _require(data.get("student_id"), "Student ID").strip()
    from education_system.sixthform_system.modules.domain.students import students as _students
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    out["student_id"] = sid

    pathway = (data.get("primary_pathway") or DEFAULT_PATHWAY).strip()
    if pathway not in PATHWAYS:
        raise ValidationError(
            f"Pathway must be one of: {', '.join(PATHWAYS)}")
    out["primary_pathway"] = pathway

    out["target_career"]   = (data.get("target_career") or "").strip() or None
    out["target_sector"]   = (data.get("target_sector") or "").strip() or None
    out["target_employer"] = (data.get("target_employer") or "").strip() or None
    out["target_course"]   = (data.get("target_course") or "").strip() or None
    out["notes"]           = (data.get("notes") or "").strip() or None
    return out


# ── Session CRUD ──────────────────────────────────────────────────

def create_session(data: dict[str, Any]) -> CareerSession:
    init_db()
    try:
        p = _validate_session_payload(data)
    except ValidationError as e:
        logger.warning("create_session validation failed: %s", e)
        raise
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO career_sessions
                   (student_id, session_date, advisor, session_type,
                    duration_minutes, gatsby_benchmark, topics,
                    action_plan, follow_up_date, status, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["student_id"], p["session_date"], p["advisor"],
             p["session_type"], p["duration_minutes"],
             p["gatsby_benchmark"], p["topics"], p["action_plan"],
             p["follow_up_date"], p["status"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_session(new_id)
    assert out is not None
    logger.info(
        "Created careers session #%d for %s (%s, %s, bm=%s)",
        new_id, p["student_id"], p["session_date"],
        p["session_type"], p["gatsby_benchmark"] or "—",
    )
    return out


def get_session(session_id: int) -> CareerSession | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM career_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return _row_session(r) if r else None


def list_sessions(
    *,
    student_id: str | None = None,
    advisor_like: str | None = None,
    session_type: str | None = None,
    benchmark: int | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[CareerSession]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if advisor_like:
        clauses.append("advisor LIKE ?")
        args.append(f"%{advisor_like.strip()}%")
    if session_type:
        if session_type not in SESSION_TYPES:
            raise ValidationError(
                f"Session type must be one of: {', '.join(SESSION_TYPES)}")
        clauses.append("session_type = ?")
        args.append(session_type)
    if benchmark is not None:
        if benchmark not in GATSBY_BENCHMARKS:
            raise ValidationError(
                f"Benchmark must be 1-8 (got {benchmark})")
        clauses.append("gatsby_benchmark = ?")
        args.append(benchmark)
    if status:
        if status not in SESSION_STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(SESSION_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if date_from:
        clauses.append("session_date >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("session_date <= ?")
        args.append(_validate_date(date_to, "date_to"))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM career_sessions {where} "
           "ORDER BY session_date DESC, session_id DESC")
    with _connect() as conn:
        return [_row_session(r) for r in conn.execute(sql, args).fetchall()]


def sessions_for_student(student_id: str) -> list[CareerSession]:
    return list_sessions(student_id=student_id)


def list_sessions_with_detail(**kwargs) -> list[SessionRow]:
    rows = list_sessions(**kwargs)
    if not rows:
        return []
        from education_system.sixthform_system.modules.domain.students import students as _students
    names = {s.student_id: s.full_name for s in _students.list_students()}
    return [SessionRow(session=s,
                        student_name=names.get(s.student_id, "(unknown)"))
            for s in rows]


def update_session(session_id: int, data: dict[str, Any]) -> CareerSession:
    init_db()
    existing = get_session(session_id)
    if existing is None:
        logger.warning("update_session: unknown id %d", session_id)
        raise ValidationError(f"No session with id {session_id}")
    p = _validate_session_payload({
        "student_id":       existing.student_id,
        "session_date":     data.get("session_date", existing.session_date),
        "advisor":          data.get("advisor", existing.advisor),
        "session_type":     data.get("session_type", existing.session_type),
        "duration_minutes": data.get("duration_minutes",
                                      existing.duration_minutes),
        "gatsby_benchmark": data.get("gatsby_benchmark",
                                      existing.gatsby_benchmark),
        "topics":           data.get("topics", existing.topics),
        "action_plan":      data.get("action_plan", existing.action_plan),
        "follow_up_date":   data.get("follow_up_date",
                                      existing.follow_up_date),
        "status":           data.get("status", existing.status),
        "notes":            data.get("notes", existing.notes),
    })
    with _connect() as conn:
        conn.execute(
            """UPDATE career_sessions SET
                   session_date = ?, advisor = ?, session_type = ?,
                   duration_minutes = ?, gatsby_benchmark = ?,
                   topics = ?, action_plan = ?, follow_up_date = ?,
                   status = ?, notes = ?, updated_at = datetime('now')
               WHERE session_id = ?""",
            (p["session_date"], p["advisor"], p["session_type"],
             p["duration_minutes"], p["gatsby_benchmark"],
             p["topics"], p["action_plan"], p["follow_up_date"],
             p["status"], p["notes"], session_id),
        )
        conn.commit()
    out = get_session(session_id)
    assert out is not None
    logger.info("Updated careers session #%d (%s, status=%s)",
                session_id, out.session_date, out.status)
    return out


def delete_session(session_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM career_sessions WHERE session_id = ?",
            (session_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted careers session #%d", session_id)
            return True
        logger.warning("delete_session: unknown id %d", session_id)
        return False


# ── Aspirations CRUD (upsert per student) ─────────────────────────

def get_aspiration_for_student(student_id: str) -> CareerAspiration | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM career_aspirations WHERE student_id = ?",
            (student_id.strip(),),
        ).fetchone()
        return _row_aspir(r) if r else None


def save_aspiration(data: dict[str, Any]) -> CareerAspiration:
    """Upsert keyed on student_id."""
    init_db()
    try:
        p = _validate_aspiration_payload(data)
    except ValidationError as e:
        logger.warning("save_aspiration validation failed: %s", e)
        raise
    with _connect() as conn:
        conn.execute(
            """INSERT INTO career_aspirations
                   (student_id, primary_pathway, target_career,
                    target_sector, target_employer, target_course, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
               ON CONFLICT(student_id) DO UPDATE SET
                   primary_pathway = excluded.primary_pathway,
                   target_career   = excluded.target_career,
                   target_sector   = excluded.target_sector,
                   target_employer = excluded.target_employer,
                   target_course   = excluded.target_course,
                   notes           = excluded.notes,
                   updated_at      = datetime('now')""",
            (p["student_id"], p["primary_pathway"],
             p["target_career"], p["target_sector"],
             p["target_employer"], p["target_course"], p["notes"]),
        )
        conn.commit()
    out = get_aspiration_for_student(p["student_id"])
    assert out is not None
    logger.info(
        "Saved careers aspiration for %s (pathway=%s, target=%s)",
        p["student_id"], p["primary_pathway"], p["target_career"] or "—",
    )
    return out


def list_aspirations(
    *,
    pathway: str | None = None,
    target_career_like: str | None = None,
) -> list[CareerAspiration]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if pathway:
        if pathway not in PATHWAYS:
            raise ValidationError(
                f"Pathway must be one of: {', '.join(PATHWAYS)}")
        clauses.append("primary_pathway = ?")
        args.append(pathway)
    if target_career_like:
        clauses.append("target_career LIKE ?")
        args.append(f"%{target_career_like.strip()}%")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM career_aspirations {where} "
           "ORDER BY student_id")
    with _connect() as conn:
        return [_row_aspir(r) for r in conn.execute(sql, args).fetchall()]


def delete_aspiration(student_id: str) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM career_aspirations WHERE student_id = ?",
            (student_id.strip(),),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted careers aspiration for %s", student_id)
            return True
        return False


# ── Summary ───────────────────────────────────────────────────────

@dataclass
class CareersSummary:
    total_sessions: int
    by_type: dict[str, int]
    by_status: dict[str, int]
    by_benchmark: dict[int, int]
    students_with_session: int
    students_no_session: int      # in the date window
    upcoming_scheduled: int        # Scheduled sessions in next N days
    upcoming_follow_ups: int       # follow_up_date within next N days
    by_pathway: dict[str, int]
    students_with_aspiration: int


def summary(
    *,
    no_session_window_days: int = 180,
    upcoming_window_days: int = 14,
) -> CareersSummary:
    """Counts + alerts. ``no_session_window_days`` counts students who
    haven't had a Completed session in the last N days (default 6 months
    — the Gatsby 8 baseline for personal guidance).
    """
    import datetime as _dt
    from education_system.sixthform_system.modules.domain.students import students as _students
    init_db()
    today = _dt.date.today()
    no_session_cutoff = (today - _dt.timedelta(days=no_session_window_days)
                         ).isoformat()
    upcoming_cutoff = (today + _dt.timedelta(days=upcoming_window_days)
                       ).isoformat()
    today_iso = today.isoformat()

    sessions = list_sessions()
    by_type = {t: 0 for t in SESSION_TYPES}
    by_status = {s: 0 for s in SESSION_STATUSES}
    by_benchmark = {b: 0 for b in GATSBY_BENCHMARKS}
    seen_students_completed_recently: set[str] = set()
    upcoming_scheduled = 0
    upcoming_followups = 0
    for s in sessions:
        by_type[s.session_type] = by_type.get(s.session_type, 0) + 1
        by_status[s.status] = by_status.get(s.status, 0) + 1
        if s.gatsby_benchmark is not None:
            by_benchmark[s.gatsby_benchmark] = by_benchmark.get(
                s.gatsby_benchmark, 0) + 1
        if (s.status == "Completed"
                and s.session_date >= no_session_cutoff):
            seen_students_completed_recently.add(s.student_id)
        if (s.status == "Scheduled"
                and today_iso <= s.session_date <= upcoming_cutoff):
            upcoming_scheduled += 1
        if (s.follow_up_date
                and today_iso <= s.follow_up_date <= upcoming_cutoff):
            upcoming_followups += 1

    all_students = _students.list_students()
    total_students = len(all_students)
    students_no_session = total_students - len(
        seen_students_completed_recently)

    aspirations = list_aspirations()
    by_pathway = {p: 0 for p in PATHWAYS}
    for a in aspirations:
        by_pathway[a.primary_pathway] = by_pathway.get(
            a.primary_pathway, 0) + 1

    return CareersSummary(
        total_sessions=len(sessions),
        by_type=by_type, by_status=by_status, by_benchmark=by_benchmark,
        students_with_session=len(seen_students_completed_recently),
        students_no_session=students_no_session,
        upcoming_scheduled=upcoming_scheduled,
        upcoming_follow_ups=upcoming_followups,
        by_pathway=by_pathway,
        students_with_aspiration=len(aspirations),
    )
