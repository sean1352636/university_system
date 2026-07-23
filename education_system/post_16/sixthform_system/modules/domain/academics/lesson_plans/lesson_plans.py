"""Lesson Plans — per-lesson teacher notes for the Sixth Form System.

One row per planned lesson: a single class, on a specific date, with
the teacher's objectives, activities, resources, homework, and
differentiation notes.

Each plan is anchored to a **subject** (required) and optionally a
**course** and **class group**, with a back-reference to the
``teacher`` (free-text name; could become a staff_id later).

Workflow: ``Draft → Ready → Delivered → Archived``. ``Delivered``
auto-stamps ``delivered_on`` to today if no explicit date is set.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.post_16.sixthform_system.core import paths
from education_system.post_16.sixthform_system.modules.domain.academics.lesson_plans import (
    lesson_plans as data,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.LESSON_PLANS_DB

STATUSES: tuple[str, ...] = (
    "Draft", "Ready", "Delivered", "Archived", "Cancelled",
)
DEFAULT_STATUS: str = "Draft"
OPEN_STATUSES: tuple[str, ...] = ("Draft", "Ready")

LEVELS: tuple[str, ...] = (
    "A-Level", "AS-Level", "BTEC", "T-Level", "GCSE Resit",
    "Functional Skills", "EPQ", "Other",
)
DEFAULT_LEVEL: str = "A-Level"

YEAR_GROUPS: tuple[str, ...] = (
    "Year 12", "Year 13", "Mixed",
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS lesson_plans (
    plan_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title             TEXT NOT NULL,
    subject_id        INTEGER,
    subject_name      TEXT NOT NULL,
    level             TEXT,
    year_group        TEXT,
    course_id         INTEGER,
    class_group_id    INTEGER,
    teacher           TEXT,
    sequence_number   INTEGER,
    week_number       INTEGER,
    planned_date      TEXT,
    delivered_on      TEXT,
    duration_minutes  INTEGER,
    topic             TEXT,
    objectives        TEXT,
    success_criteria  TEXT,
    activities        TEXT,
    resources         TEXT,
    homework          TEXT,
    assessment        TEXT,
    differentiation   TEXT,
    keywords          TEXT,
    status            TEXT NOT NULL DEFAULT 'Draft',
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_lp_subject     ON lesson_plans(subject_name);
CREATE INDEX IF NOT EXISTS idx_lp_status      ON lesson_plans(status);
CREATE INDEX IF NOT EXISTS idx_lp_teacher     ON lesson_plans(teacher);
CREATE INDEX IF NOT EXISTS idx_lp_date        ON lesson_plans(planned_date);
CREATE INDEX IF NOT EXISTS idx_lp_class_group ON lesson_plans(class_group_id);
CREATE INDEX IF NOT EXISTS idx_lp_course      ON lesson_plans(course_id);
"""


@dataclass
class LessonPlan:
    plan_id: int
    title: str
    subject_id: int | None
    subject_name: str
    level: str | None
    year_group: str | None
    course_id: int | None
    class_group_id: int | None
    teacher: str | None
    sequence_number: int | None
    week_number: int | None
    planned_date: str | None
    delivered_on: str | None
    duration_minutes: int | None
    topic: str | None
    objectives: str | None
    success_criteria: str | None
    activities: str | None
    resources: str | None
    homework: str | None
    assessment: str | None
    differentiation: str | None
    keywords: str | None
    status: str
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def is_draft(self) -> bool:
        return self.status == "Draft"

    @property
    def is_delivered(self) -> bool:
        return self.status == "Delivered"


@dataclass
class Summary:
    total: int
    by_status: dict[str, int]
    by_subject: dict[str, int]
    by_teacher: dict[str, int]
    drafts: int
    ready: int
    delivered: int
    upcoming: int           # status in Draft/Ready, planned_date in [today, +window]


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Lesson-plans schema ready at %s", DB_PATH)

    _DB_READY = True


def _row(r: sqlite3.Row) -> LessonPlan:
    return LessonPlan(
        plan_id=r["plan_id"], title=r["title"],
        subject_id=r["subject_id"], subject_name=r["subject_name"],
        level=r["level"], year_group=r["year_group"],
        course_id=r["course_id"],
        class_group_id=r["class_group_id"],
        teacher=r["teacher"],
        sequence_number=r["sequence_number"],
        week_number=r["week_number"],
        planned_date=r["planned_date"],
        delivered_on=r["delivered_on"],
        duration_minutes=r["duration_minutes"],
        topic=r["topic"],
        objectives=r["objectives"],
        success_criteria=r["success_criteria"],
        activities=r["activities"],
        resources=r["resources"],
        homework=r["homework"],
        assessment=r["assessment"],
        differentiation=r["differentiation"],
        keywords=r["keywords"],
        status=r["status"], notes=r["notes"],
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


def _resolve_subject(payload: dict[str, Any]) -> tuple[int | None, str]:
    """Return (subject_id, subject_name) — name is the source of
    truth; id is best-effort."""
    name = (payload.get("subject_name") or "").strip()
    sid = payload.get("subject_id")
    try:
        from education_system.post_16.sixthform_system.modules.domain.academics.subjects import (
            subjects as _subjects,
        )
        if sid not in (None, ""):
            try:
                sid_int = int(sid)
            except (TypeError, ValueError):
                raise ValidationError(
                    "subject_id must be a number") from None
            row = _subjects.get_subject(sid_int)
            if row is None:
                raise ValidationError(
                    f"No subject with id {sid_int}")
            return row.subject_id, row.name
        if not name:
            raise ValidationError("Subject is required")
        row = _subjects.get_subject_by_name(name)
        if row is None:
            # Allow free-text subject if it doesn't match the
            # catalogue — schools sometimes plan around non-formal
            # qualifications.
            return None, name
        return row.subject_id, row.name
    except ValidationError:
        raise
    except Exception:
        if not name:
            raise ValidationError("Subject is required")
        return None, name


def _validate_course(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        cid = int(value)
    except (TypeError, ValueError):
        raise ValidationError("course_id must be a number") from None
    try:
        from education_system.post_16.sixthform_system.modules.domain.academics.courses import (
            courses as _courses,
        )
        if _courses.get_course(cid) is None:
            raise ValidationError(f"No course with id {cid}")
    except ValidationError:
        raise
    except Exception:
        pass
    return cid


def _validate_class_group(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        gid = int(value)
    except (TypeError, ValueError):
        raise ValidationError(
            "class_group_id must be a number") from None
    try:
        from education_system.post_16.sixthform_system.modules.domain.academics.class_groups import (
            class_groups as _cg,
        )
        if _cg.get_group(gid) is None:
            raise ValidationError(f"No class group with id {gid}")
    except ValidationError:
        raise
    except Exception:
        pass
    return gid


def _validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["title"] = _require(payload.get("title"), "Title").strip()

    sid, sname = _resolve_subject(payload)
    out["subject_id"] = sid
    out["subject_name"] = sname

    level = (payload.get("level") or "").strip()
    if level and level not in LEVELS:
        raise ValidationError(
            f"Level must be one of: {', '.join(LEVELS)}")
    out["level"] = level or None

    year = (payload.get("year_group") or "").strip()
    if year and year not in YEAR_GROUPS:
        raise ValidationError(
            f"Year group must be one of: {', '.join(YEAR_GROUPS)}")
    out["year_group"] = year or None

    out["course_id"]      = _validate_course(payload.get("course_id"))
    out["class_group_id"] = _validate_class_group(
        payload.get("class_group_id"))
    out["teacher"]        = (payload.get("teacher") or "").strip() or None
    out["sequence_number"] = _validate_int(
        payload.get("sequence_number"), "Sequence number",
        min_val=0, max_val=10000)
    out["week_number"] = _validate_int(
        payload.get("week_number"), "Week number",
        min_val=0, max_val=200)
    out["planned_date"]  = _validate_date(
        payload.get("planned_date"), "Planned date")
    out["delivered_on"]  = _validate_date(
        payload.get("delivered_on"), "Delivered on")
    out["duration_minutes"] = _validate_int(
        payload.get("duration_minutes"), "Duration (minutes)",
        min_val=0, max_val=1440)

    status = (payload.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    out["topic"]            = (payload.get("topic") or "").strip() or None
    out["objectives"]       = (payload.get("objectives")
                                or "").strip() or None
    out["success_criteria"] = (payload.get("success_criteria")
                                or "").strip() or None
    out["activities"]       = (payload.get("activities")
                                or "").strip() or None
    out["resources"]        = (payload.get("resources")
                                or "").strip() or None
    out["homework"]         = (payload.get("homework")
                                or "").strip() or None
    out["assessment"]       = (payload.get("assessment")
                                or "").strip() or None
    out["differentiation"]  = (payload.get("differentiation")
                                or "").strip() or None
    out["keywords"]         = (payload.get("keywords")
                                or "").strip() or None
    out["notes"]            = (payload.get("notes") or "").strip() or None

    if status == "Delivered" and not out["delivered_on"]:
        out["delivered_on"] = _dt.date.today().isoformat()
    return out


# ── CRUD ──────────────────────────────────────────────────────────

def create_plan(payload: dict[str, Any]) -> LessonPlan:
    init_db()
    p = _validate_payload(payload)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO lesson_plans
                   (title, subject_id, subject_name, level, year_group,
                    course_id, class_group_id, teacher,
                    sequence_number, week_number, planned_date,
                    delivered_on, duration_minutes, topic, objectives,
                    success_criteria, activities, resources, homework,
                    assessment, differentiation, keywords, status,
                    notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["title"], p["subject_id"], p["subject_name"],
             p["level"], p["year_group"], p["course_id"],
             p["class_group_id"], p["teacher"],
             p["sequence_number"], p["week_number"],
             p["planned_date"], p["delivered_on"],
             p["duration_minutes"], p["topic"], p["objectives"],
             p["success_criteria"], p["activities"], p["resources"],
             p["homework"], p["assessment"], p["differentiation"],
             p["keywords"], p["status"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_plan(new_id)
    assert out is not None
    logger.info("Created lesson plan #%d %r (subject=%s, status=%s)",
                new_id, p["title"], p["subject_name"], p["status"])
    return out


def get_plan(plan_id: int) -> LessonPlan | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM lesson_plans WHERE plan_id = ?",
            (plan_id,)).fetchone()
        return _row(r) if r else None


def list_plans(
    *,
    subject_name: str | None = None,
    subject_id: int | None = None,
    teacher_like: str | None = None,
    status: str | None = None,
    open_only: bool = False,
    course_id: int | None = None,
    class_group_id: int | None = None,
    year_group: str | None = None,
    level: str | None = None,
    week_number: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    title_like: str | None = None,
) -> list[LessonPlan]:
    init_db()
    clauses, args = [], []
    if subject_name:
        clauses.append("subject_name = ?")
        args.append(subject_name.strip())
    if subject_id is not None:
        clauses.append("subject_id = ?")
        args.append(subject_id)
    if teacher_like:
        clauses.append("teacher LIKE ?")
        args.append(f"%{teacher_like.strip()}%")
    if title_like:
        clauses.append("title LIKE ?")
        args.append(f"%{title_like.strip()}%")
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if open_only:
        ph = ",".join("?" * len(OPEN_STATUSES))
        clauses.append(f"status IN ({ph})")
        args.extend(OPEN_STATUSES)
    if course_id is not None:
        clauses.append("course_id = ?")
        args.append(course_id)
    if class_group_id is not None:
        clauses.append("class_group_id = ?")
        args.append(class_group_id)
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year group must be one of: {', '.join(YEAR_GROUPS)}")
        clauses.append("year_group = ?")
        args.append(year_group)
    if level:
        if level not in LEVELS:
            raise ValidationError(
                f"Level must be one of: {', '.join(LEVELS)}")
        clauses.append("level = ?")
        args.append(level)
    if week_number is not None:
        clauses.append("week_number = ?")
        args.append(int(week_number))
    if date_from:
        clauses.append("planned_date >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("planned_date <= ?")
        args.append(_validate_date(date_to, "date_to"))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM lesson_plans {where} "
           "ORDER BY "
           "  CASE WHEN planned_date IS NULL THEN 1 ELSE 0 END, "
           "  planned_date ASC, "
           "  CASE WHEN sequence_number IS NULL THEN 1 ELSE 0 END, "
           "  sequence_number ASC, "
           "  plan_id ASC")
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def update_plan(plan_id: int, payload: dict[str, Any]) -> LessonPlan:
    init_db()
    existing = get_plan(plan_id)
    if existing is None:
        raise ValidationError(f"No lesson plan #{plan_id}")
    merged = {
        "title":            payload.get("title", existing.title),
        "subject_name":     payload.get("subject_name",
                                        existing.subject_name),
        "subject_id":       payload.get("subject_id",
                                        existing.subject_id),
        "level":            payload.get("level", existing.level),
        "year_group":       payload.get("year_group",
                                        existing.year_group),
        "course_id":        payload.get("course_id",
                                        existing.course_id),
        "class_group_id":   payload.get("class_group_id",
                                        existing.class_group_id),
        "teacher":          payload.get("teacher", existing.teacher),
        "sequence_number":  payload.get("sequence_number",
                                        existing.sequence_number),
        "week_number":      payload.get("week_number",
                                        existing.week_number),
        "planned_date":     payload.get("planned_date",
                                        existing.planned_date),
        "delivered_on":     payload.get("delivered_on",
                                        existing.delivered_on),
        "duration_minutes": payload.get("duration_minutes",
                                        existing.duration_minutes),
        "topic":            payload.get("topic", existing.topic),
        "objectives":       payload.get("objectives",
                                        existing.objectives),
        "success_criteria": payload.get("success_criteria",
                                        existing.success_criteria),
        "activities":       payload.get("activities",
                                        existing.activities),
        "resources":        payload.get("resources",
                                        existing.resources),
        "homework":         payload.get("homework", existing.homework),
        "assessment":       payload.get("assessment",
                                        existing.assessment),
        "differentiation":  payload.get("differentiation",
                                        existing.differentiation),
        "keywords":         payload.get("keywords", existing.keywords),
        "status":           payload.get("status", existing.status),
        "notes":            payload.get("notes", existing.notes),
    }
    p = _validate_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE lesson_plans SET
                   title = ?, subject_id = ?, subject_name = ?,
                   level = ?, year_group = ?, course_id = ?,
                   class_group_id = ?, teacher = ?, sequence_number = ?,
                   week_number = ?, planned_date = ?, delivered_on = ?,
                   duration_minutes = ?, topic = ?, objectives = ?,
                   success_criteria = ?, activities = ?, resources = ?,
                   homework = ?, assessment = ?, differentiation = ?,
                   keywords = ?, status = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE plan_id = ?""",
            (p["title"], p["subject_id"], p["subject_name"],
             p["level"], p["year_group"], p["course_id"],
             p["class_group_id"], p["teacher"], p["sequence_number"],
             p["week_number"], p["planned_date"], p["delivered_on"],
             p["duration_minutes"], p["topic"], p["objectives"],
             p["success_criteria"], p["activities"], p["resources"],
             p["homework"], p["assessment"], p["differentiation"],
             p["keywords"], p["status"], p["notes"], plan_id),
        )
        conn.commit()
    out = get_plan(plan_id)
    assert out is not None
    logger.info("Updated lesson plan #%d (status=%s)",
                plan_id, out.status)
    return out


def set_status(plan_id: int, status: str) -> LessonPlan:
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    return update_plan(plan_id, {"status": status})


def mark_delivered(plan_id: int, *,
                    delivered_on: str | None = None) -> LessonPlan:
    return update_plan(plan_id, {
        "status": "Delivered",
        "delivered_on": delivered_on or _dt.date.today().isoformat(),
    })


def duplicate_plan(plan_id: int, *,
                    new_title: str | None = None,
                    new_date: str | None = None) -> LessonPlan:
    """Clone an existing plan as a new Draft. Resets delivery fields."""
    existing = get_plan(plan_id)
    if existing is None:
        raise ValidationError(f"No lesson plan #{plan_id}")
    payload = {
        "title":            new_title or f"{existing.title} (copy)",
        "subject_name":     existing.subject_name,
        "subject_id":       existing.subject_id,
        "level":            existing.level,
        "year_group":       existing.year_group,
        "course_id":        existing.course_id,
        "class_group_id":   existing.class_group_id,
        "teacher":          existing.teacher,
        "sequence_number":  existing.sequence_number,
        "week_number":      existing.week_number,
        "planned_date":     new_date,
        "delivered_on":     None,
        "duration_minutes": existing.duration_minutes,
        "topic":            existing.topic,
        "objectives":       existing.objectives,
        "success_criteria": existing.success_criteria,
        "activities":       existing.activities,
        "resources":        existing.resources,
        "homework":         existing.homework,
        "assessment":       existing.assessment,
        "differentiation":  existing.differentiation,
        "keywords":         existing.keywords,
        "status":           "Draft",
        "notes":            existing.notes,
    }
    return create_plan(payload)


def delete_plan(plan_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM lesson_plans WHERE plan_id = ?",
            (plan_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted lesson plan #%d", plan_id)
            return True
        return False


# ── Summary ───────────────────────────────────────────────────────

def summary(*, upcoming_window_days: int = 14) -> Summary:
    init_db()
    today = _dt.date.today().isoformat()
    horizon = (_dt.date.today()
                + _dt.timedelta(days=upcoming_window_days)).isoformat()
    rows = list_plans()
    by_status: dict[str, int] = {s: 0 for s in STATUSES}
    by_subject: dict[str, int] = {}
    by_teacher: dict[str, int] = {}
    upcoming = 0
    for p in rows:
        by_status[p.status] = by_status.get(p.status, 0) + 1
        by_subject[p.subject_name] = by_subject.get(
            p.subject_name, 0) + 1
        if p.teacher:
            by_teacher[p.teacher] = by_teacher.get(p.teacher, 0) + 1
        if (p.status in OPEN_STATUSES and p.planned_date
                and today <= p.planned_date <= horizon):
            upcoming += 1
    return Summary(
        total=len(rows),
        by_status=by_status,
        by_subject=dict(sorted(by_subject.items(),
                                key=lambda kv: kv[1],
                                reverse=True)),
        by_teacher=dict(sorted(by_teacher.items(),
                                key=lambda kv: kv[1],
                                reverse=True)),
        drafts=by_status.get("Draft", 0),
        ready=by_status.get("Ready", 0),
        delivered=by_status.get("Delivered", 0),
        upcoming=upcoming,
    )
