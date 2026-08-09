"""Lesson-plan data layer for the Primary School System.

One row per planned lesson. Pairs a subject + year/form with a date and
period, plus the pedagogical fields a teacher wants to capture
(objectives, activities, resources, differentiation, assessment,
homework, notes). Status moves through Draft → Ready → Delivered →
Reviewed.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.primary.domain.learners.pupils.pupils import (
    ValidationError, YEAR_GROUPS, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

STATUSES: tuple[str, ...] = ("Draft", "Ready", "Delivered", "Reviewed")
DEFAULT_STATUS: str = "Draft"

MIN_PERIOD = 1
MAX_PERIOD = 8

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS lesson_plans (
    plan_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title            TEXT NOT NULL,
    subject_id       INTEGER NOT NULL,
    year_group       TEXT NOT NULL,
    form_group       TEXT,
    planned_date     TEXT NOT NULL,
    period           INTEGER,
    duration_min     INTEGER,
    teacher          TEXT,
    status           TEXT NOT NULL DEFAULT 'Draft',
    objectives       TEXT,
    activities       TEXT,
    resources        TEXT,
    differentiation  TEXT,
    assessment       TEXT,
    homework         TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id)
);

CREATE INDEX IF NOT EXISTS idx_lp_date
    ON lesson_plans(planned_date);
CREATE INDEX IF NOT EXISTS idx_lp_subject
    ON lesson_plans(subject_id);
CREATE INDEX IF NOT EXISTS idx_lp_teacher
    ON lesson_plans(teacher);
"""


@dataclass
class LessonPlan:
    plan_id: int
    title: str
    subject_id: int
    year_group: str
    form_group: str | None
    planned_date: str
    period: int | None
    duration_min: int | None
    teacher: str | None
    status: str
    objectives: str | None
    activities: str | None
    resources: str | None
    differentiation: str | None
    assessment: str | None
    homework: str | None
    notes: str | None
    subject_code: str | None = None
    subject_name: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.systems.primary.domain.academics.subjects import (
        subjects as subjects_data,
    )
    subjects_data.init_db()
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise lesson_plans table")
        raise
    logger.info("Secondary lesson_plans table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> LessonPlan:
    keys = r.keys()
    return LessonPlan(
        plan_id=r["plan_id"], title=r["title"],
        subject_id=r["subject_id"], year_group=r["year_group"],
        form_group=r["form_group"],
        planned_date=r["planned_date"], period=r["period"],
        duration_min=r["duration_min"], teacher=r["teacher"],
        status=r["status"],
        objectives=r["objectives"], activities=r["activities"],
        resources=r["resources"],
        differentiation=r["differentiation"],
        assessment=r["assessment"], homework=r["homework"],
        notes=r["notes"],
        subject_code=r["subject_code"] if "subject_code" in keys else None,
        subject_name=r["subject_name"] if "subject_name" in keys else None,
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _validate_date(value: Any, label: str = "Planned date") -> str:
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


def _validate_int(value: Any, label: str, *,
                  minimum: int, maximum: int,
                  optional: bool = False) -> int | None:
    if value in (None, "") or (isinstance(value, str)
                                and not str(value).strip()):
        if optional:
            return None
        raise ValidationError(f"{label} is required")
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a whole number") from None
    if n < minimum or n > maximum:
        raise ValidationError(
            f"{label} must be between {minimum} and {maximum}")
    return n


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    title = (data.get("title") or "").strip()
    if not title:
        raise ValidationError("Title is required")
    if len(title) > 120:
        raise ValidationError("Title must be 120 characters or fewer")
    out["title"] = title

    sid = data.get("subject_id")
    if sid in (None, ""):
        raise ValidationError("Subject is required")
    try:
        out["subject_id"] = int(sid)
    except (TypeError, ValueError):
        raise ValidationError("Subject ID must be a number") from None
    from education_system.systems.primary.domain.academics.subjects import (
        subjects as subjects_data,
    )
    subj = subjects_data.get(out["subject_id"])
    if subj is None:
        raise ValidationError(f"No subject #{out['subject_id']}")

    yg = (data.get("year_group") or "").strip()
    if not yg:
        raise ValidationError("Year group is required")
    if yg not in YEAR_GROUPS:
        raise ValidationError(
            f"Year group must be one of {', '.join(YEAR_GROUPS)}")
    out["year_group"] = yg
    out["form_group"] = (data.get("form_group") or "").strip() or None

    out["planned_date"] = _validate_date(data.get("planned_date"))
    out["period"] = _validate_int(
        data.get("period"), "Period",
        minimum=MIN_PERIOD, maximum=MAX_PERIOD, optional=True)
    out["duration_min"] = _validate_int(
        data.get("duration_min"), "Duration (minutes)",
        minimum=5, maximum=240, optional=True)

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(STATUSES)}")
    out["status"] = status

    out["teacher"]         = (data.get("teacher") or "").strip() or None
    out["objectives"]      = (data.get("objectives") or "").strip() or None
    out["activities"]      = (data.get("activities") or "").strip() or None
    out["resources"]       = (data.get("resources") or "").strip() or None
    out["differentiation"] = (data.get("differentiation") or "").strip() or None
    out["assessment"]      = (data.get("assessment") or "").strip() or None
    out["homework"]        = (data.get("homework") or "").strip() or None
    out["notes"]           = (data.get("notes") or "").strip() or None
    return out


def create(data: dict[str, Any]) -> LessonPlan:
    init_db()
    payload = _validate(data)
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO lesson_plans
                       (title, subject_id, year_group, form_group,
                        planned_date, period, duration_min, teacher,
                        status, objectives, activities, resources,
                        differentiation, assessment, homework, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["title"], payload["subject_id"],
                 payload["year_group"], payload["form_group"],
                 payload["planned_date"], payload["period"],
                 payload["duration_min"], payload["teacher"],
                 payload["status"], payload["objectives"],
                 payload["activities"], payload["resources"],
                 payload["differentiation"], payload["assessment"],
                 payload["homework"], payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create lesson plan")
        raise
    rec = get(new_id)
    assert rec is not None
    logger.info("Created lesson plan #%d '%s' (Yr%s %s P%s status=%s)",
                rec.plan_id, rec.title, rec.year_group,
                rec.planned_date, rec.period, rec.status)
    return rec


def get(plan_id: int) -> LessonPlan | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT lp.*, s.code AS subject_code, s.name AS subject_name
                   FROM lesson_plans lp
                   LEFT JOIN subjects s ON s.subject_id = lp.subject_id
                   WHERE lp.plan_id = ?""",
                (plan_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get(%s) failed", plan_id)
        raise
    return _row(r) if r else None


def list_plans(*, year_group: str | None = None,
               subject_id: int | None = None,
               teacher: str | None = None,
               status: str | None = None,
               date_from: str | None = None,
               date_to: str | None = None) -> list[LessonPlan]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
        where.append("lp.year_group = ?")
        params.append(year_group)
    if subject_id is not None:
        where.append("lp.subject_id = ?")
        params.append(int(subject_id))
    if teacher:
        where.append("lp.teacher = ?")
        params.append(teacher.strip())
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status filter must be one of {', '.join(STATUSES)}")
        where.append("lp.status = ?")
        params.append(status)
    if date_from:
        where.append("lp.planned_date >= ?")
        params.append(_validate_date(date_from, "From date"))
    if date_to:
        where.append("lp.planned_date <= ?")
        params.append(_validate_date(date_to, "To date"))
    sql = ("""SELECT lp.*, s.code AS subject_code, s.name AS subject_name
              FROM lesson_plans lp
              LEFT JOIN subjects s ON s.subject_id = lp.subject_id""")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY lp.planned_date DESC, lp.period, lp.plan_id DESC"
    try:
        with _connect() as conn:
            return [_row(r) for r in conn.execute(sql,
                                                    tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_plans failed")
        raise


def update(plan_id: int, data: dict[str, Any]) -> LessonPlan:
    init_db()
    existing = get(plan_id)
    if existing is None:
        raise ValidationError(f"No lesson plan #{plan_id}")
    merged = {
        "title":           data.get("title", existing.title),
        "subject_id":      data.get("subject_id", existing.subject_id),
        "year_group":      data.get("year_group", existing.year_group),
        "form_group":      data.get("form_group", existing.form_group),
        "planned_date":    data.get("planned_date", existing.planned_date),
        "period":          data.get("period", existing.period),
        "duration_min":    data.get("duration_min", existing.duration_min),
        "teacher":         data.get("teacher", existing.teacher),
        "status":          data.get("status", existing.status),
        "objectives":      data.get("objectives", existing.objectives),
        "activities":      data.get("activities", existing.activities),
        "resources":       data.get("resources", existing.resources),
        "differentiation": data.get("differentiation",
                                     existing.differentiation),
        "assessment":      data.get("assessment", existing.assessment),
        "homework":        data.get("homework", existing.homework),
        "notes":           data.get("notes", existing.notes),
    }
    payload = _validate(merged)
    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE lesson_plans SET
                       title = ?, subject_id = ?, year_group = ?,
                       form_group = ?, planned_date = ?, period = ?,
                       duration_min = ?, teacher = ?, status = ?,
                       objectives = ?, activities = ?, resources = ?,
                       differentiation = ?, assessment = ?, homework = ?,
                       notes = ?, updated_at = datetime('now')
                   WHERE plan_id = ?""",
                (payload["title"], payload["subject_id"],
                 payload["year_group"], payload["form_group"],
                 payload["planned_date"], payload["period"],
                 payload["duration_min"], payload["teacher"],
                 payload["status"], payload["objectives"],
                 payload["activities"], payload["resources"],
                 payload["differentiation"], payload["assessment"],
                 payload["homework"], payload["notes"], plan_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update lesson plan #%d", plan_id)
        raise
    rec = get(plan_id)
    assert rec is not None
    logger.info("Updated lesson plan #%d (status %s)",
                rec.plan_id, rec.status)
    return rec


def set_status(plan_id: int, new_status: str) -> LessonPlan:
    return update(plan_id, {"status": new_status})


def delete(plan_id: int) -> bool:
    init_db()
    existing = get(plan_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM lesson_plans WHERE plan_id = ?", (plan_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete lesson plan #%d", plan_id)
        raise
    if deleted:
        logger.info("Deleted lesson plan #%d '%s'", plan_id, existing.title)
    return deleted


def status_counts() -> dict[str, int]:
    init_db()
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS n FROM lesson_plans "
                "GROUP BY status").fetchall()
    except sqlite3.Error:
        logger.exception("status_counts failed")
        raise
    counts = {s: 0 for s in STATUSES}
    for r in rows:
        counts[r["status"]] = r["n"]
    return counts
