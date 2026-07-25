"""Study Planner — per-student revision tasks and study sessions.

One row per planned study task: ``revision``, ``past paper``,
``reading``, ``coursework``, etc. Anchored to a student + subject
with a planned date, planned duration, and a status workflow
``Planned → In Progress → Completed`` (or ``Skipped`` / ``Rescheduled``).

When a task is marked Completed, ``completed_on`` and
``actual_duration_minutes`` can be recorded for retrospective review.

Cascade: deleting a student wipes their study tasks.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.systems.sixth_form.infrastructure import paths
from education_system.systems.sixth_form.domain.academics.study_planner import (
    study_planner as data,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.STUDY_PLANNER_DB


TASK_TYPES: tuple[str, ...] = (
    "Revision",
    "Past Paper",
    "Notes",
    "Reading",
    "Coursework",
    "Practice Questions",
    "Flashcards",
    "Mind Map",
    "Video / Tutorial",
    "Group Study",
    "Other",
)
DEFAULT_TASK_TYPE: str = "Revision"

STATUSES: tuple[str, ...] = (
    "Planned", "In Progress", "Completed", "Skipped",
    "Rescheduled", "Cancelled",
)
DEFAULT_STATUS: str = "Planned"
OPEN_STATUSES: tuple[str, ...] = ("Planned", "In Progress")

PRIORITIES: tuple[str, ...] = ("Low", "Medium", "High", "Urgent")
DEFAULT_PRIORITY: str = "Medium"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}(:\d{2})?$")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS study_tasks (
    task_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id        TEXT NOT NULL,
    subject_name      TEXT,
    topic             TEXT,
    title             TEXT NOT NULL,
    description       TEXT,
    task_type         TEXT NOT NULL DEFAULT 'Revision',
    priority          TEXT NOT NULL DEFAULT 'Medium',
    planned_date      TEXT,
    planned_start     TEXT,
    planned_duration  INTEGER,
    actual_duration   INTEGER,
    completed_on      TEXT,
    status            TEXT NOT NULL DEFAULT 'Planned',
    reflection        TEXT,
    resources         TEXT,
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sp_student  ON study_tasks(student_id);
CREATE INDEX IF NOT EXISTS idx_sp_subject  ON study_tasks(subject_name);
CREATE INDEX IF NOT EXISTS idx_sp_status   ON study_tasks(status);
CREATE INDEX IF NOT EXISTS idx_sp_date     ON study_tasks(planned_date);
CREATE INDEX IF NOT EXISTS idx_sp_priority ON study_tasks(priority);
"""


@dataclass
class StudyTask:
    task_id: int
    student_id: str
    subject_name: str | None
    topic: str | None
    title: str
    description: str | None
    task_type: str
    priority: str
    planned_date: str | None
    planned_start: str | None
    planned_duration: int | None
    actual_duration: int | None
    completed_on: str | None
    status: str
    reflection: str | None
    resources: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES

    @property
    def is_done(self) -> bool:
        return self.status == "Completed"

    @property
    def is_overdue(self) -> bool:
        if not (self.is_open and self.planned_date):
            return False
        return self.planned_date < _dt.date.today().isoformat()

    @property
    def time_label(self) -> str:
        if self.planned_start:
            return self.planned_start[:5]
        return "—"


@dataclass
class TaskRow:
    task: StudyTask
    student_name: str


@dataclass
class StudentSummary:
    student_id: str
    total: int
    completed: int
    open_count: int
    overdue: int
    minutes_planned: int
    minutes_actual: int
    by_subject: dict[str, int]
    by_status: dict[str, int]


@dataclass
class Summary:
    total_tasks: int
    by_status: dict[str, int]
    by_type: dict[str, int]
    by_priority: dict[str, int]
    by_subject: dict[str, int]
    open_count: int
    completed_count: int
    overdue: int
    today_count: int
    this_week_count: int
    upcoming: int
    minutes_planned: int
    minutes_actual: int
    distinct_students: int


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
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Study-planner schema ready at %s", DB_PATH)

    _DB_READY = True


def _row(r: sqlite3.Row) -> StudyTask:
    return StudyTask(
        task_id=r["task_id"], student_id=r["student_id"],
        subject_name=r["subject_name"], topic=r["topic"],
        title=r["title"], description=r["description"],
        task_type=r["task_type"], priority=r["priority"],
        planned_date=r["planned_date"],
        planned_start=r["planned_start"],
        planned_duration=r["planned_duration"],
        actual_duration=r["actual_duration"],
        completed_on=r["completed_on"], status=r["status"],
        reflection=r["reflection"],
        resources=r["resources"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_date(value: Any, label: str, *,
                    required: bool = False) -> str | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _validate_time(value: Any, label: str) -> str | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        return None
    s = str(value).strip()
    if not _TIME_RE.match(s):
        raise ValidationError(f"{label} must be HH:MM")
    if len(s) == 5:
        s = s + ":00"
    try:
        _dt.time.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real time") from None
    return s


def _validate_int(value: Any, label: str, *,
                   min_val: int | None = None,
                   max_val: int | None = None) -> int | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a whole number") from None
    if min_val is not None and n < min_val:
        raise ValidationError(f"{label} must be at least {min_val}")
    if max_val is not None and n > max_val:
        raise ValidationError(f"{label} must be at most {max_val}")
    return n


def _validate_student(value: Any) -> str:
    sid = _require(value, "Student").strip()
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    return sid


def _validate_subject(value: Any) -> str | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        return None
    name = str(value).strip()
    try:
        from education_system.systems.sixth_form.domain.academics.subjects import (
            subjects as _subjects,
        )
        names = {x.name for x in _subjects.list_subjects()}
        if names and name not in names:
            # Tolerate non-catalogue subjects (e.g. EPQ, a generic
            # study skill) — return as-is.
            return name
    except Exception:
        pass
    return name


def _validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["student_id"] = _validate_student(payload.get("student_id"))
    out["title"] = _require(payload.get("title"), "Title").strip()
    out["subject_name"] = _validate_subject(payload.get("subject_name"))
    out["topic"] = (payload.get("topic") or "").strip() or None

    ttype = (payload.get("task_type") or DEFAULT_TASK_TYPE).strip()
    if ttype not in TASK_TYPES:
        raise ValidationError(
            f"Task type must be one of: {', '.join(TASK_TYPES)}")
    out["task_type"] = ttype

    priority = (payload.get("priority") or DEFAULT_PRIORITY).strip()
    if priority not in PRIORITIES:
        raise ValidationError(
            f"Priority must be one of: {', '.join(PRIORITIES)}")
    out["priority"] = priority

    status = (payload.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    out["planned_date"] = _validate_date(
        payload.get("planned_date"), "Planned date")
    out["planned_start"] = _validate_time(
        payload.get("planned_start"), "Planned start")
    out["planned_duration"] = _validate_int(
        payload.get("planned_duration"),
        "Planned duration (mins)",
        min_val=0, max_val=24 * 60)
    out["actual_duration"]  = _validate_int(
        payload.get("actual_duration"),
        "Actual duration (mins)",
        min_val=0, max_val=24 * 60)
    out["completed_on"] = _validate_date(
        payload.get("completed_on"), "Completed on")

    out["description"] = (payload.get("description")
                            or "").strip() or None
    out["reflection"]  = (payload.get("reflection")
                            or "").strip() or None
    out["resources"]   = (payload.get("resources")
                            or "").strip() or None
    out["notes"]       = (payload.get("notes") or "").strip() or None

    if status == "Completed" and not out["completed_on"]:
        out["completed_on"] = _dt.date.today().isoformat()
    return out


# ── CRUD ──────────────────────────────────────────────────────────

def create_task(payload: dict[str, Any]) -> StudyTask:
    init_db()
    p = _validate_payload(payload)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO study_tasks
                   (student_id, subject_name, topic, title,
                    description, task_type, priority, planned_date,
                    planned_start, planned_duration, actual_duration,
                    completed_on, status, reflection, resources,
                    notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, datetime('now'), datetime('now'))""",
            (p["student_id"], p["subject_name"], p["topic"],
             p["title"], p["description"], p["task_type"],
             p["priority"], p["planned_date"], p["planned_start"],
             p["planned_duration"], p["actual_duration"],
             p["completed_on"], p["status"], p["reflection"],
             p["resources"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_task(new_id)
    assert out is not None
    logger.info("Created study task #%d for %s (%s, due %s, %s)",
                new_id, p["student_id"], p["subject_name"] or "—",
                p["planned_date"], p["status"])
    return out


def get_task(task_id: int) -> StudyTask | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM study_tasks WHERE task_id = ?",
            (task_id,)).fetchone()
        return _row(r) if r else None


def list_tasks(
    *,
    student_id: str | None = None,
    subject_name: str | None = None,
    task_type: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    open_only: bool = False,
    overdue_only: bool = False,
    today_only: bool = False,
    date_from: str | None = None,
    date_to: str | None = None,
    title_like: str | None = None,
) -> list[StudyTask]:
    init_db()
    clauses, args = [], []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if subject_name:
        clauses.append("subject_name = ?")
        args.append(subject_name.strip())
    if task_type:
        if task_type not in TASK_TYPES:
            raise ValidationError(
                f"Task type must be one of: {', '.join(TASK_TYPES)}")
        clauses.append("task_type = ?")
        args.append(task_type)
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if priority:
        if priority not in PRIORITIES:
            raise ValidationError(
                f"Priority must be one of: {', '.join(PRIORITIES)}")
        clauses.append("priority = ?")
        args.append(priority)
    if open_only:
        ph = ",".join("?" * len(OPEN_STATUSES))
        clauses.append(f"status IN ({ph})")
        args.extend(OPEN_STATUSES)
    if overdue_only:
        today = _dt.date.today().isoformat()
        ph = ",".join("?" * len(OPEN_STATUSES))
        clauses.append(
            f"planned_date IS NOT NULL AND planned_date < ? "
            f"AND status IN ({ph})")
        args.append(today)
        args.extend(OPEN_STATUSES)
    if today_only:
        clauses.append("planned_date = ?")
        args.append(_dt.date.today().isoformat())
    if date_from:
        clauses.append("planned_date >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("planned_date <= ?")
        args.append(_validate_date(date_to, "date_to"))
    if title_like:
        clauses.append("(title LIKE ? OR topic LIKE ?)")
        args.extend([f"%{title_like.strip()}%",
                      f"%{title_like.strip()}%"])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM study_tasks {where} "
           "ORDER BY "
           "  CASE WHEN planned_date IS NULL THEN 1 ELSE 0 END, "
           "  planned_date ASC, "
           "  CASE priority "
           "    WHEN 'Urgent' THEN 0 "
           "    WHEN 'High'   THEN 1 "
           "    WHEN 'Medium' THEN 2 "
           "    ELSE 3 END, "
           "  CASE WHEN planned_start IS NULL THEN 1 ELSE 0 END, "
           "  planned_start ASC, task_id ASC")
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def list_tasks_with_detail(**kwargs) -> list[TaskRow]:
    rows = list_tasks(**kwargs)
    if not rows:
        return []
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    names = {s.student_id: s.full_name
              for s in _students.list_students()}
    return [TaskRow(task=t,
                     student_name=names.get(t.student_id,
                                              "(unknown)"))
            for t in rows]


def update_task(task_id: int, payload: dict[str, Any]) -> StudyTask:
    init_db()
    existing = get_task(task_id)
    if existing is None:
        raise ValidationError(f"No study task #{task_id}")
    merged = {
        "student_id":       existing.student_id,
        "subject_name":     payload.get("subject_name",
                                         existing.subject_name),
        "topic":            payload.get("topic", existing.topic),
        "title":            payload.get("title", existing.title),
        "description":      payload.get("description",
                                         existing.description),
        "task_type":        payload.get("task_type",
                                         existing.task_type),
        "priority":         payload.get("priority",
                                         existing.priority),
        "planned_date":     payload.get("planned_date",
                                         existing.planned_date),
        "planned_start":    payload.get("planned_start",
                                         existing.planned_start),
        "planned_duration": payload.get("planned_duration",
                                         existing.planned_duration),
        "actual_duration":  payload.get("actual_duration",
                                         existing.actual_duration),
        "completed_on":     payload.get("completed_on",
                                         existing.completed_on),
        "status":           payload.get("status", existing.status),
        "reflection":       payload.get("reflection",
                                         existing.reflection),
        "resources":        payload.get("resources",
                                         existing.resources),
        "notes":            payload.get("notes", existing.notes),
    }
    p = _validate_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE study_tasks SET
                   subject_name = ?, topic = ?, title = ?,
                   description = ?, task_type = ?, priority = ?,
                   planned_date = ?, planned_start = ?,
                   planned_duration = ?, actual_duration = ?,
                   completed_on = ?, status = ?, reflection = ?,
                   resources = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE task_id = ?""",
            (p["subject_name"], p["topic"], p["title"],
             p["description"], p["task_type"], p["priority"],
             p["planned_date"], p["planned_start"],
             p["planned_duration"], p["actual_duration"],
             p["completed_on"], p["status"], p["reflection"],
             p["resources"], p["notes"], task_id),
        )
        conn.commit()
    out = get_task(task_id)
    assert out is not None
    return out


def set_status(task_id: int, status: str) -> StudyTask:
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    return update_task(task_id, {"status": status})


def start_task(task_id: int) -> StudyTask:
    return set_status(task_id, "In Progress")


def complete_task(task_id: int, *,
                   actual_duration: int | None = None,
                   reflection: str | None = None) -> StudyTask:
    payload: dict[str, Any] = {
        "status": "Completed",
        "completed_on": _dt.date.today().isoformat(),
    }
    if actual_duration is not None:
        payload["actual_duration"] = actual_duration
    if reflection is not None:
        payload["reflection"] = reflection
    return update_task(task_id, payload)


def skip_task(task_id: int) -> StudyTask:
    return set_status(task_id, "Skipped")


def reschedule(task_id: int, *, new_date: str,
                new_start: str | None = None) -> StudyTask:
    payload: dict[str, Any] = {
        "planned_date": new_date,
        "status": "Planned",
    }
    if new_start is not None:
        payload["planned_start"] = new_start
    return update_task(task_id, payload)


def duplicate_task(task_id: int, *,
                    new_date: str | None = None) -> StudyTask:
    existing = get_task(task_id)
    if existing is None:
        raise ValidationError(f"No study task #{task_id}")
    payload = {
        "student_id":       existing.student_id,
        "subject_name":     existing.subject_name,
        "topic":            existing.topic,
        "title":            existing.title,
        "description":      existing.description,
        "task_type":        existing.task_type,
        "priority":         existing.priority,
        "planned_date":     new_date,
        "planned_start":    existing.planned_start,
        "planned_duration": existing.planned_duration,
        "status":           "Planned",
        "resources":        existing.resources,
        "notes":            existing.notes,
    }
    return create_task(payload)


def delete_task(task_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM study_tasks WHERE task_id = ?",
            (task_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted study task #%d", task_id)
            return True
        return False


# ── Bulk planner ──────────────────────────────────────────────────

def plan_revision_block(
    student_id: str, *,
    subject_name: str,
    topics: list[str],
    start_date: str,
    daily_minutes: int = 45,
    task_type: str = "Revision",
    priority: str = "Medium",
) -> list[StudyTask]:
    """Create one Planned task per topic on consecutive days from
    ``start_date``. Handy for kicking off a revision schedule."""
    init_db()
    if not topics:
        raise ValidationError("Provide at least one topic")
    df = _validate_date(start_date, "start_date", required=True)
    base = _dt.date.fromisoformat(df)
    created: list[StudyTask] = []
    for i, topic in enumerate(topics):
        topic = (topic or "").strip()
        if not topic:
            continue
        day = (base + _dt.timedelta(days=i)).isoformat()
        t = create_task({
            "student_id":       student_id,
            "subject_name":     subject_name,
            "topic":            topic,
            "title":            f"{subject_name}: {topic}",
            "task_type":        task_type,
            "priority":         priority,
            "planned_date":     day,
            "planned_duration": daily_minutes,
            "status":           "Planned",
        })
        created.append(t)
    return created


# ── Summary ───────────────────────────────────────────────────────

def student_summary(student_id: str) -> StudentSummary:
    init_db()
    today = _dt.date.today().isoformat()
    rows = list_tasks(student_id=student_id)
    by_subject: dict[str, int] = {}
    by_status: dict[str, int] = {s: 0 for s in STATUSES}
    planned_minutes = 0
    actual_minutes = 0
    completed = 0
    open_count = 0
    overdue = 0
    for t in rows:
        by_status[t.status] = by_status.get(t.status, 0) + 1
        key = t.subject_name or "(none)"
        by_subject[key] = by_subject.get(key, 0) + 1
        if t.planned_duration:
            planned_minutes += t.planned_duration
        if t.actual_duration:
            actual_minutes += t.actual_duration
        if t.is_done:
            completed += 1
        if t.is_open:
            open_count += 1
            if (t.planned_date and t.planned_date < today):
                overdue += 1
    return StudentSummary(
        student_id=student_id,
        total=len(rows),
        completed=completed,
        open_count=open_count,
        overdue=overdue,
        minutes_planned=planned_minutes,
        minutes_actual=actual_minutes,
        by_subject=dict(sorted(by_subject.items(),
                                key=lambda kv: kv[1],
                                reverse=True)),
        by_status=by_status,
    )


def summary(*, upcoming_window_days: int = 7) -> Summary:
    init_db()
    today_date = _dt.date.today()
    today = today_date.isoformat()
    horizon = (today_date
                + _dt.timedelta(days=upcoming_window_days)).isoformat()
    monday = today_date - _dt.timedelta(days=today_date.weekday())
    sunday = monday + _dt.timedelta(days=6)

    rows = list_tasks()
    by_status = {s: 0 for s in STATUSES}
    by_type = {t: 0 for t in TASK_TYPES}
    by_priority = {p: 0 for p in PRIORITIES}
    by_subject: dict[str, int] = {}
    planned_minutes = 0
    actual_minutes = 0
    open_count = 0
    completed = 0
    overdue = 0
    today_count = 0
    week_count = 0
    upcoming = 0
    students: set[str] = set()
    for t in rows:
        by_status[t.status] = by_status.get(t.status, 0) + 1
        by_type[t.task_type] = by_type.get(t.task_type, 0) + 1
        by_priority[t.priority] = by_priority.get(t.priority, 0) + 1
        key = t.subject_name or "(none)"
        by_subject[key] = by_subject.get(key, 0) + 1
        if t.planned_duration:
            planned_minutes += t.planned_duration
        if t.actual_duration:
            actual_minutes += t.actual_duration
        if t.is_done:
            completed += 1
        if t.is_open:
            open_count += 1
            if t.is_overdue:
                overdue += 1
            elif t.planned_date and today <= t.planned_date <= horizon:
                upcoming += 1
        if t.planned_date == today:
            today_count += 1
        if (t.planned_date
                and monday.isoformat() <= t.planned_date
                <= sunday.isoformat()):
            week_count += 1
        students.add(t.student_id)

    return Summary(
        total_tasks=len(rows),
        by_status=by_status,
        by_type=by_type,
        by_priority=by_priority,
        by_subject=dict(sorted(by_subject.items(),
                                key=lambda kv: kv[1],
                                reverse=True)),
        open_count=open_count,
        completed_count=completed,
        overdue=overdue,
        today_count=today_count,
        this_week_count=week_count,
        upcoming=upcoming,
        minutes_planned=planned_minutes,
        minutes_actual=actual_minutes,
        distinct_students=len(students),
    )
