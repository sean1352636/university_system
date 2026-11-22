"""Lesson plans and schemes of work.

**Plans.** A lesson plan is for a teaching group on a date (and usually a
period), which gives it its subject, year group and teacher. A plan with no
group is a *shared plan* for a subject and year group - a resource others can
copy - and needs no date. When a group, date and period match a timetabled
lesson, the plan is linked to that lesson.

The old fields are kept (objectives, activities, resources, differentiation,
assessment, homework, notes) with success criteria and an evaluation added.
Status moves Draft -> Ready -> Delivered -> Reviewed:

* Ready needs objectives and activities;
* Delivered only on or after the lesson's date;
* Reviewed needs an evaluation (what went well, next steps).

**Schemes of work.** Units (subject + year group, a term, an order and a number
of lessons) group plans into a sequence; a unit shows how many of its lessons
are planned and delivered for each group.

**Who.** All staff can view every plan and write their own. A plan can be
changed by its teacher or whoever wrote it, or by :data:`LESSON_PLAN_EDITORS`.
Delivered and reviewed plans are a record: only editors delete them. Units are
managed by editors.
"""

from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.curriculum.domain import timetable as TT
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import LESSON_PLAN_EDITORS, Principal
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

STATUSES: tuple[str, ...] = ("Draft", "Ready", "Delivered", "Reviewed")
TERMS: tuple[str, ...] = ("Autumn", "Spring", "Summer", "Any")

#: The plan's writing fields, in the order a form shows them.
TEXT_FIELDS: tuple[tuple[str, str], ...] = (
    ("objectives", "Learning objectives"),
    ("success_criteria", "Success criteria"),
    ("activities", "Activities"),
    ("resources", "Resources"),
    ("differentiation", "Differentiation / SEND"),
    ("assessment", "Assessment"),
    ("homework", "Homework"),
    ("notes", "Notes"),
    ("evaluation", "Evaluation (after the lesson)"),
)
_TEXT_LIMIT = 4000
MAX_PLAN_DAYS = 120   # plan-from-timetable range

_SCHEMA = """
CREATE TABLE IF NOT EXISTS lesson_plan_units (
    unit_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id  INTEGER NOT NULL REFERENCES subjects (subject_id),
    year_group  INTEGER NOT NULL CHECK (year_group BETWEEN 7 AND 11),
    title       TEXT NOT NULL COLLATE NOCASE,
    term        TEXT NOT NULL DEFAULT 'Any',
    sequence    INTEGER NOT NULL DEFAULT 1,
    lessons     INTEGER,
    overview    TEXT,
    status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    created_by  TEXT,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by  TEXT,
    UNIQUE (subject_id, year_group, title)
);
CREATE TABLE IF NOT EXISTS lesson_plans (
    plan_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title            TEXT NOT NULL,
    subject_id       INTEGER NOT NULL REFERENCES subjects (subject_id),
    year_group       INTEGER NOT NULL CHECK (year_group BETWEEN 7 AND 11),
    group_id         INTEGER REFERENCES teaching_groups (group_id) ON DELETE SET NULL,
    unit_id          INTEGER REFERENCES lesson_plan_units (unit_id) ON DELETE SET NULL,
    lesson_id        INTEGER REFERENCES timetable_lessons (lesson_id) ON DELETE SET NULL,
    planned_date     TEXT,
    period           INTEGER,
    duration_min     INTEGER,
    teacher_name     TEXT,
    teacher_username TEXT,
    status           TEXT NOT NULL DEFAULT 'Draft'
                     CHECK (status IN ('Draft', 'Ready', 'Delivered', 'Reviewed')),
    objectives       TEXT,
    success_criteria TEXT,
    activities       TEXT,
    resources        TEXT,
    differentiation  TEXT,
    assessment       TEXT,
    homework         TEXT,
    notes            TEXT,
    evaluation       TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    created_by       TEXT,
    updated_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by       TEXT
);
CREATE INDEX IF NOT EXISTS ix_lesson_plans_date ON lesson_plans (planned_date);
CREATE INDEX IF NOT EXISTS ix_lesson_plans_group ON lesson_plans (group_id, planned_date);
CREATE UNIQUE INDEX IF NOT EXISTS ux_lesson_plans_slot
    ON lesson_plans (group_id, planned_date, period)
    WHERE group_id IS NOT NULL AND planned_date IS NOT NULL AND period IS NOT NULL;
CREATE TABLE IF NOT EXISTS lesson_plan_audit (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id  INTEGER,
    unit_id  INTEGER,
    action   TEXT NOT NULL CHECK (action IN ('create', 'update', 'status', 'copy', 'delete',
                                             'unit_create', 'unit_update', 'unit_archive',
                                             'unit_restore', 'unit_delete')),
    actor    TEXT NOT NULL,
    detail   TEXT,
    at       TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

database.register_schema("lesson_plans", _SCHEMA)

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound


# ── Records ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Unit:
    unit_id: int
    subject_id: int
    year_group: int
    title: str
    term: str = "Any"
    sequence: int = 1
    lessons: int | None = None
    overview: str | None = None
    status: str = "active"
    created_at: str | None = None
    created_by: str | None = None
    updated_at: str | None = None
    updated_by: str | None = None

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def label(self) -> str:
        return f"{self.sequence}. {self.title}"


@dataclass(frozen=True)
class Plan:
    plan_id: int
    title: str
    subject_id: int
    year_group: int
    group_id: int | None
    unit_id: int | None
    lesson_id: int | None
    planned_date: str | None
    period: int | None
    duration_min: int | None
    teacher_name: str | None
    teacher_username: str | None
    status: str
    objectives: str | None
    success_criteria: str | None
    activities: str | None
    resources: str | None
    differentiation: str | None
    assessment: str | None
    homework: str | None
    notes: str | None
    evaluation: str | None
    created_at: str
    created_by: str | None
    updated_at: str
    updated_by: str | None
    # Joined for lists:
    subject_code: str = ""
    subject_name: str = ""
    group_code: str | None = None
    unit_title: str | None = None

    @property
    def is_shared(self) -> bool:
        """A plan for a subject and year with no group: for others to copy."""
        return self.group_id is None

    @property
    def when(self) -> str:
        if not self.planned_date:
            return "Shared plan"
        d = _dt.date.fromisoformat(self.planned_date)
        return f"{d:%a %d %b %Y}" + (f" P{self.period}" if self.period else "")

    @property
    def for_label(self) -> str:
        return self.group_code or f"Year {self.year_group}"


@dataclass(frozen=True)
class UnitProgress:
    unit: Unit
    group_code: str | None   # None = every group together
    planned: int
    delivered: int           # Delivered or Reviewed


_SELECT = """
SELECT lp.*, s.code AS subject_code, s.name AS subject_name, g.code AS group_code,
       u.title AS unit_title
FROM lesson_plans lp
JOIN subjects s ON s.subject_id = lp.subject_id
LEFT JOIN teaching_groups g ON g.group_id = lp.group_id
LEFT JOIN lesson_plan_units u ON u.unit_id = lp.unit_id
"""


def _plan(r) -> Plan:
    return Plan(**{k: r[k] for k in Plan.__dataclass_fields__})


def _unit(r) -> Unit:
    return Unit(**{k: r[k] for k in Unit.__dataclass_fields__})


# ── Helpers ──────────────────────────────────────────────────────────

def is_editor(actor: Principal) -> bool:
    return actor.role in LESSON_PLAN_EDITORS


def can_change(actor: Principal, plan: Plan) -> bool:
    """The plan's teacher, whoever wrote it, or an editor."""
    if is_editor(actor):
        return True
    me = (actor.username or "").lower()
    return bool(me) and me in {(plan.created_by or "").lower(),
                               (plan.teacher_username or "").lower()}


def _require_staff(actor: Principal, action: str, target: Any = None) -> None:
    if not actor.is_staff:
        activity_log.record(action, target=target, outcome="denied", principal=actor)
        raise PermissionDenied("Only school staff can write lesson plans.")


def _require_owner(actor: Principal, plan: Plan, action: str) -> None:
    _require_staff(actor, action, f"plan:{plan.plan_id}")
    if not can_change(actor, plan):
        activity_log.record(action, target=f"plan:{plan.plan_id}", outcome="denied",
                            principal=actor)
        raise PermissionDenied("Only the plan's teacher (or whoever wrote it) can change it.")


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        activity_log.record(action, target=target, outcome="denied", principal=actor)
        raise PermissionDenied("Your account can view schemes of work but not change them.")


def _audit(conn, action: str, actor: Principal, *, plan_id: int | None = None,
           unit_id: int | None = None, detail: dict | None = None) -> None:
    conn.execute("INSERT INTO lesson_plan_audit (plan_id, unit_id, action, actor, detail) "
                 "VALUES (?, ?, ?, ?, ?)",
                 (plan_id, unit_id, action, actor.username or "unknown",
                  json.dumps(detail, default=str, sort_keys=True) if detail else None))


def _int(value: Any, label: str, lo: int, hi: int, problems: list[str]) -> int | None:
    if value in (None, ""):
        return None
    try:
        n = int(str(value).strip())
    except ValueError:
        n = lo - 1
    if not lo <= n <= hi:
        problems.append(f"{label} must be from {lo} to {hi}")
        return None
    return n


def _minutes_between(a: str, b: str) -> int:
    return (int(b[:2]) * 60 + int(b[3:])) - (int(a[:2]) * 60 + int(a[3:]))


# ── Units (schemes of work) ──────────────────────────────────────────

def get_unit(unit_id: int) -> Unit:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM lesson_plan_units WHERE unit_id = ?",
                         (int(unit_id),)).fetchone()
    if r is None:
        raise NotFound(f"No unit #{unit_id}")
    return _unit(r)


def list_units(*, subject_id: int | None = None, year_group: int | None = None,
               include_archived: bool = False) -> list[Unit]:
    sql, params = "SELECT u.* FROM lesson_plan_units u JOIN subjects s USING (subject_id)", []
    where = []
    if subject_id is not None:
        where.append("u.subject_id = ?")
        params.append(int(subject_id))
    if year_group is not None:
        where.append("u.year_group = ?")
        params.append(int(year_group))
    if not include_archived:
        where.append("u.status = 'active'")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += (" ORDER BY s.name COLLATE NOCASE, u.year_group, CASE u.term WHEN 'Autumn' THEN 1 "
            "WHEN 'Spring' THEN 2 WHEN 'Summer' THEN 3 ELSE 4 END, u.sequence, u.title")
    with database.connect() as conn:
        return [_unit(r) for r in conn.execute(sql, params)]


def _clean_unit(data: dict[str, Any], current: Unit | None) -> dict[str, Any]:
    problems: list[str] = []
    allowed = {"subject_id", "year_group", "title", "term", "sequence", "lessons", "overview"}
    unknown = set(data) - allowed
    if unknown:
        problems.append(f"Unknown field(s): {', '.join(sorted(unknown))}")
    merged = {k: getattr(current, k) for k in allowed} if current else {}
    merged.update(data)
    out: dict[str, Any] = {}
    subject = None
    try:
        subject = S.get(int(merged.get("subject_id")))  # type: ignore[arg-type]
        out["subject_id"] = subject.subject_id
    except (TypeError, ValueError, S.NotFound):
        problems.append("Choose a subject")
    year = _int(merged.get("year_group"), "Year group", 7, 11, problems)
    if year is None and not any("Year group" in p for p in problems):
        problems.append("Choose a year group")
    if subject and year and year not in subject.years:
        problems.append(f"{subject.name} isn't taught in Year {year} ({subject.key_stage})")
    out["year_group"] = year
    out["title"] = P._clean_text(merged.get("title"), 120)
    if not out["title"]:
        problems.append("Give the unit a title")
    term = str(merged.get("term") or "Any").strip().title()
    if term not in TERMS:
        problems.append("Term must be Autumn, Spring, Summer or Any")
    out["term"] = term
    out["sequence"] = _int(merged.get("sequence"), "Order", 1, 99, problems) or 1
    out["lessons"] = _int(merged.get("lessons"), "Number of lessons", 1, 200, problems)
    out["overview"] = P._clean_text(merged.get("overview"), _TEXT_LIMIT)
    if problems:
        raise ValidationError(problems)
    return out


def _unit_taken(conn, clean: dict[str, Any], not_id: int | None) -> bool:
    return conn.execute(
        "SELECT 1 FROM lesson_plan_units WHERE subject_id = ? AND year_group = ? AND "
        "title = ? AND unit_id IS NOT ?",
        (clean["subject_id"], clean["year_group"], clean["title"], not_id)).fetchone() is not None


def create_unit(data: dict[str, Any], *, actor: Principal) -> Unit:
    _require_editor(actor, "lesson_plans.unit_create")
    clean = _clean_unit(data, None)
    with database.connect() as conn:
        if _unit_taken(conn, clean, None):
            raise ValidationError([f"Year {clean['year_group']} already has a unit called "
                                   f"'{clean['title']}' for that subject"])
        cols = list(clean)
        uid = conn.execute(
            f"INSERT INTO lesson_plan_units ({', '.join(cols)}, created_by, updated_by) "  # nosec B608 - fixed columns
            f"VALUES ({', '.join('?' * len(cols))}, ?, ?)",
            (*clean.values(), actor.username, actor.username)).lastrowid
        _audit(conn, "unit_create", actor, unit_id=uid)
    activity_log.record("lesson_plans.unit_create", target=f"unit:{uid}", principal=actor)
    return get_unit(uid)


def update_unit(unit_id: int, changes: dict[str, Any], *, actor: Principal) -> Unit:
    _require_editor(actor, "lesson_plans.unit_update", f"unit:{unit_id}")
    u = get_unit(unit_id)
    clean = _clean_unit(changes, u)
    diff = {k: v for k, v in clean.items() if getattr(u, k) != v}
    if not diff:
        return u
    with database.connect() as conn:
        if ("subject_id" in diff or "year_group" in diff) and conn.execute(
                "SELECT 1 FROM lesson_plans WHERE unit_id = ?", (u.unit_id,)).fetchone():
            raise ValidationError(["This unit has lesson plans - its subject and year "
                                   "can't change"])
        if _unit_taken(conn, clean, u.unit_id):
            raise ValidationError([f"Year {clean['year_group']} already has a unit called "
                                   f"'{clean['title']}' for that subject"])
        sets = ", ".join(f"{k} = ?" for k in diff)
        conn.execute(f"UPDATE lesson_plan_units SET {sets}, updated_at = datetime('now'), "  # nosec B608 - keys from _clean_unit
                     "updated_by = ? WHERE unit_id = ?",
                     (*diff.values(), actor.username, u.unit_id))
        _audit(conn, "unit_update", actor, unit_id=u.unit_id, detail={"fields": sorted(diff)})
    activity_log.record("lesson_plans.unit_update", target=f"unit:{u.unit_id}",
                        principal=actor, fields=sorted(diff))
    return get_unit(u.unit_id)


def _set_unit_status(unit_id: int, status: str, actor: Principal) -> Unit:
    action = "unit_archive" if status == "archived" else "unit_restore"
    _require_editor(actor, f"lesson_plans.{action}", f"unit:{unit_id}")
    u = get_unit(unit_id)
    with database.connect() as conn:
        conn.execute("UPDATE lesson_plan_units SET status = ?, updated_at = datetime('now'), "
                     "updated_by = ? WHERE unit_id = ?", (status, actor.username, u.unit_id))
        _audit(conn, action, actor, unit_id=u.unit_id)
    activity_log.record(f"lesson_plans.{action}", target=f"unit:{u.unit_id}", principal=actor)
    return get_unit(u.unit_id)


def archive_unit(unit_id: int, *, actor: Principal) -> Unit:
    """Hide a unit from new plans (its plans keep the link)."""
    return _set_unit_status(unit_id, "archived", actor)


def restore_unit(unit_id: int, *, actor: Principal) -> Unit:
    return _set_unit_status(unit_id, "active", actor)


def delete_unit(unit_id: int, *, actor: Principal) -> None:
    """Delete a unit no plan uses (archive it otherwise)."""
    _require_editor(actor, "lesson_plans.unit_delete", f"unit:{unit_id}")
    u = get_unit(unit_id)
    with database.connect() as conn:
        n = conn.execute("SELECT COUNT(*) FROM lesson_plans WHERE unit_id = ?",
                         (u.unit_id,)).fetchone()[0]
        if n:
            raise ValidationError([f"{n} lesson plan(s) use this unit - archive it instead"])
        conn.execute("DELETE FROM lesson_plan_units WHERE unit_id = ?", (u.unit_id,))
        _audit(conn, "unit_delete", actor, unit_id=u.unit_id, detail={"title": u.title})
    activity_log.record("lesson_plans.unit_delete", target=f"unit:{u.unit_id}", principal=actor)


def unit_progress(unit_id: int) -> list[UnitProgress]:
    """For each group with plans in the unit: lessons planned and delivered."""
    u = get_unit(unit_id)
    with database.connect() as conn:
        rows = conn.execute(
            "SELECT g.code, COUNT(*) AS n, SUM(lp.status IN ('Delivered', 'Reviewed')) AS done "
            "FROM lesson_plans lp LEFT JOIN teaching_groups g ON g.group_id = lp.group_id "
            "WHERE lp.unit_id = ? GROUP BY lp.group_id ORDER BY g.code", (u.unit_id,)).fetchall()
    return [UnitProgress(u, r["code"], r["n"], r["done"] or 0) for r in rows]


# ── Reading plans ────────────────────────────────────────────────────

def get(plan_id: int) -> Plan:
    with database.connect() as conn:
        r = conn.execute(_SELECT + " WHERE lp.plan_id = ?", (int(plan_id),)).fetchone()
    if r is None:
        raise NotFound(f"No lesson plan #{plan_id}")
    return _plan(r)


def list_plans(*, year_group: int | None = None, subject_id: int | None = None,
               group_id: int | None = None, unit_id: int | None = None,
               teacher: str | None = None, status: str | None = None,
               date_from: Any = None, date_to: Any = None, search: str | None = None,
               shared: bool | None = None) -> list[Plan]:
    """Plans, newest date first (shared plans last). *teacher* matches the
    teacher's login or name, or who wrote the plan."""
    where, params = [], []
    problems: list[str] = []
    if year_group not in (None, ""):
        where.append("lp.year_group = ?")
        params.append(int(year_group))
    if subject_id is not None:
        where.append("lp.subject_id = ?")
        params.append(int(subject_id))
    if group_id is not None:
        where.append("lp.group_id = ?")
        params.append(int(group_id))
    if unit_id is not None:
        where.append("lp.unit_id = ?")
        params.append(int(unit_id))
    if teacher:
        where.append("(lower(lp.teacher_username) = lower(?) OR lower(lp.teacher_name) = "
                     "lower(?) OR lower(lp.created_by) = lower(?))")
        params.extend([teacher.strip()] * 3)
    if status:
        if status not in STATUSES:
            problems.append(f"Status must be one of {', '.join(STATUSES)}")
        where.append("lp.status = ?")
        params.append(status)
    for value, op, label in ((date_from, ">=", "From"), (date_to, "<=", "To")):
        if value:
            try:
                d = value if isinstance(value, _dt.date) else _dt.date.fromisoformat(
                    str(value).strip())
                where.append(f"lp.planned_date {op} ?")
                params.append(d.isoformat())
            except ValueError:
                problems.append(f"{label} date must be YYYY-MM-DD")
    for word in (search or "").split():
        where.append("(lp.title LIKE ? OR lp.objectives LIKE ? OR u.title LIKE ?)")
        params.extend([f"%{word}%"] * 3)
    if shared is not None:
        where.append("lp.group_id IS NULL" if shared else "lp.group_id IS NOT NULL")
    if problems:
        raise ValidationError(problems)
    sql = _SELECT + (" WHERE " + " AND ".join(where) if where else "")
    sql += (" ORDER BY lp.planned_date IS NULL, lp.planned_date DESC, lp.period, "
            "lp.plan_id DESC")
    with database.connect() as conn:
        return [_plan(r) for r in conn.execute(sql, params)]


def status_counts(**filters: Any) -> dict[str, int]:
    out = {s: 0 for s in STATUSES}
    for p in list_plans(**filters):
        out[p.status] += 1
    return out


def for_lesson(group_id: int, day: Any, period: int) -> Plan | None:
    d = _dt.date.fromisoformat(str(day)) if not isinstance(day, _dt.date) else day
    with database.connect() as conn:
        r = conn.execute(_SELECT + " WHERE lp.group_id = ? AND lp.planned_date = ? AND "
                         "lp.period = ?", (int(group_id), d.isoformat(), int(period))
                         ).fetchone()
    return _plan(r) if r else None


def coverage(start: Any, end: Any, *, teacher: str | None = None
             ) -> list[tuple[_dt.date, TT.Lesson, Plan | None]]:
    """Every timetabled lesson from *start* to *end* with its plan (or None)."""
    s, e = _range(start, end)
    plans = {(p.group_id, p.planned_date, p.period): p
             for p in list_plans(date_from=s, date_to=e, shared=False)}
    out = []
    d = s
    while d <= e:
        lessons, _label = TT.lessons_on(d, **({"teacher": teacher} if teacher else {}))
        for x in lessons:
            out.append((d, x, plans.get((x.group_id, d.isoformat(), x.period))))
        d += _dt.timedelta(days=1)
    return out


def history(plan_id: int | None = None, *, unit_id: int | None = None,
            limit: int = 100) -> list[dict[str, Any]]:
    sql, params = "SELECT * FROM lesson_plan_audit", []
    if plan_id is not None:
        sql += " WHERE plan_id = ?"
        params.append(int(plan_id))
    elif unit_id is not None:
        sql += " WHERE unit_id = ?"
        params.append(int(unit_id))
    with database.connect() as conn:
        rows = conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?", (*params, limit))
        return [{"at": r["at"], "actor": r["actor"], "action": r["action"],
                 "plan_id": r["plan_id"], "unit_id": r["unit_id"],
                 "detail": json.loads(r["detail"]) if r["detail"] else {}} for r in rows]


def _range(start: Any, end: Any) -> tuple[_dt.date, _dt.date]:
    try:
        s = start if isinstance(start, _dt.date) else _dt.date.fromisoformat(str(start).strip())
        e = end if isinstance(end, _dt.date) else _dt.date.fromisoformat(str(end).strip())
    except ValueError:
        raise ValidationError(["Dates must be YYYY-MM-DD"]) from None
    if e < s:
        raise ValidationError(["The end date is before the start date"])
    if (e - s).days > MAX_PLAN_DAYS:
        raise ValidationError([f"At most {MAX_PLAN_DAYS} days at a time"])
    return s, e


# ── Writing plans ────────────────────────────────────────────────────

_EDITABLE = ("title", "subject_id", "year_group", "group_id", "unit_id", "planned_date",
             "period", "duration_min", "teacher_name", "teacher_username",
             *(k for k, _l in TEXT_FIELDS))


def _clean(data: dict[str, Any], current: Plan | None) -> tuple[dict[str, Any], list[str]]:
    """Validated columns and warnings (e.g. 'not on the timetable')."""
    problems: list[str] = []
    warnings: list[str] = []
    unknown = set(data) - set(_EDITABLE)
    if unknown:
        problems.append(f"Unknown field(s): {', '.join(sorted(unknown))}")
    merged = {k: getattr(current, k) for k in _EDITABLE} if current else {}
    merged.update(data)
    out: dict[str, Any] = {}

    out["title"] = P._clean_text(merged.get("title"), 120)
    if not out["title"]:
        problems.append("Give the plan a title")

    group = None
    gid = merged.get("group_id")
    if gid not in (None, ""):
        try:
            group = TG.get(int(gid))
        except (TypeError, ValueError, TG.NotFound):
            problems.append("Choose a teaching group")
    if group is not None:
        changed = current is None or current.group_id != group.group_id
        if changed and not (group.is_current and group.is_active):
            problems.append(f"{group.code} isn't one of this year's open groups")
        out["group_id"] = group.group_id
        out["subject_id"] = group.subject_id
        out["year_group"] = group.year_group
    else:
        out["group_id"] = None
        try:
            subject = S.get(int(merged.get("subject_id")))  # type: ignore[arg-type]
            out["subject_id"] = subject.subject_id
        except (TypeError, ValueError, S.NotFound):
            subject = None
            problems.append("Choose a teaching group, or a subject and year for a shared plan")
        year = _int(merged.get("year_group"), "Year group", 7, 11, problems)
        if subject is not None and year is None and not any("Year" in p for p in problems):
            problems.append("Choose a year group")
        if subject is not None and year is not None and year not in subject.years:
            problems.append(f"{subject.name} isn't taught in Year {year}")
        out["year_group"] = year

    uid = merged.get("unit_id")
    out["unit_id"] = None
    if uid not in (None, ""):
        try:
            u = get_unit(int(uid))
        except (TypeError, ValueError, NotFound):
            problems.append("Choose a unit from the scheme of work")
        else:
            if (u.subject_id, u.year_group) != (out.get("subject_id"), out.get("year_group")):
                problems.append(f"Unit '{u.title}' is for another subject or year")
            elif not u.is_active and (current is None or current.unit_id != u.unit_id):
                problems.append(f"Unit '{u.title}' is archived")
            out["unit_id"] = u.unit_id

    day = None
    raw = merged.get("planned_date")
    if raw not in (None, ""):
        try:
            day = raw if isinstance(raw, _dt.date) else _dt.date.fromisoformat(str(raw).strip())
        except ValueError:
            problems.append("Date must be YYYY-MM-DD")
    elif group is not None:
        problems.append("A plan for a group needs the lesson's date")
    out["planned_date"] = day.isoformat() if day else None
    plist = TT.periods()
    out["period"] = _int(merged.get("period"), "Period", 1, len(plist), problems)
    out["duration_min"] = _int(merged.get("duration_min"), "Length (minutes)", 5, 300,
                               problems)
    if out["duration_min"] is None and out["period"]:
        p = next((x for x in plist if x.period == out["period"]), None)
        if p:
            out["duration_min"] = _minutes_between(p.start_time, p.end_time)

    # The timetabled lesson it is for, if any.
    out["lesson_id"] = None
    if group is not None and day is not None and out["period"]:
        lessons, label = TT.lessons_on(day, group_id=group.group_id)
        hit = next((x for x in lessons if x.period == out["period"]), None)
        if hit:
            out["lesson_id"] = hit.lesson_id
        else:
            warnings.append(f"{group.code} has no timetabled lesson then ({label}) - "
                            "saved as an extra lesson")

    out["teacher_name"] = P._clean_text(merged.get("teacher_name"), 100)
    out["teacher_username"] = P._clean_text(merged.get("teacher_username"), 100)
    if group is not None and current is None:
        out["teacher_name"] = out["teacher_name"] or group.teacher_name
        out["teacher_username"] = out["teacher_username"] or group.teacher_username
    if out["teacher_username"]:
        login = next((t for t in TG.teacher_choices()
                      if t["username"].lower() == out["teacher_username"].lower()), None)
        if login is None:
            if current is None or out["teacher_username"] != current.teacher_username:
                problems.append(f"'{out['teacher_username']}' isn't a secondary staff login")
        else:
            out["teacher_username"] = login["username"]
            out["teacher_name"] = out["teacher_name"] or login["display_name"]
    for key, _label in TEXT_FIELDS:
        out[key] = P._clean_text(merged.get(key), _TEXT_LIMIT)
    if problems:
        raise ValidationError(problems)
    return out, warnings


def _slot_taken(conn, clean: dict[str, Any], not_id: int | None) -> Plan | None:
    if not (clean["group_id"] and clean["planned_date"] and clean["period"]):
        return None
    r = conn.execute(_SELECT + " WHERE lp.group_id = ? AND lp.planned_date = ? AND "
                     "lp.period = ? AND lp.plan_id IS NOT ?",
                     (clean["group_id"], clean["planned_date"], clean["period"], not_id)
                     ).fetchone()
    return _plan(r) if r else None


def create(data: dict[str, Any], *, actor: Principal) -> tuple[Plan, list[str]]:
    """New Draft plan. Returns (plan, warnings)."""
    _require_staff(actor, "lesson_plans.create")
    clean, warnings = _clean(data, None)
    with database.connect() as conn:
        clash = _slot_taken(conn, clean, None)
        if clash:
            raise ValidationError([f"{clash.group_code} already has a plan for that lesson: "
                                   f"'{clash.title}'"])
        cols = list(clean)
        pid = conn.execute(
            f"INSERT INTO lesson_plans ({', '.join(cols)}, created_by, updated_by) "  # nosec B608 - columns from _clean
            f"VALUES ({', '.join('?' * len(cols))}, ?, ?)",
            (*clean.values(), actor.username, actor.username)).lastrowid
        _audit(conn, "create", actor, plan_id=pid,
               detail={"group_id": clean["group_id"], "unit_id": clean["unit_id"]})
    activity_log.record("lesson_plans.create", target=f"plan:{pid}", principal=actor)
    return get(pid), warnings


def update(plan_id: int, changes: dict[str, Any], *, actor: Principal
           ) -> tuple[Plan, list[str]]:
    p = get(plan_id)
    _require_owner(actor, p, "lesson_plans.update")
    clean, warnings = _clean(changes, p)
    diff = {k: v for k, v in clean.items() if getattr(p, k) != v}
    if not diff:
        return p, warnings
    if p.status == "Reviewed" and set(diff) - {"evaluation", "notes"} and not is_editor(actor):
        raise ValidationError(["A reviewed plan is a record - only its evaluation and notes "
                               "can change"])
    with database.connect() as conn:
        clash = _slot_taken(conn, clean, p.plan_id)
        if clash:
            raise ValidationError([f"{clash.group_code} already has a plan for that lesson: "
                                   f"'{clash.title}'"])
        sets = ", ".join(f"{k} = ?" for k in diff)
        conn.execute(f"UPDATE lesson_plans SET {sets}, updated_at = datetime('now'), "  # nosec B608 - keys from _clean
                     "updated_by = ? WHERE plan_id = ?",
                     (*diff.values(), actor.username, p.plan_id))
        _audit(conn, "update", actor, plan_id=p.plan_id, detail={"fields": sorted(diff)})
    activity_log.record("lesson_plans.update", target=f"plan:{p.plan_id}", principal=actor,
                        fields=sorted(diff))
    return get(p.plan_id), warnings


def status_problems(p: Plan, status: str, *, evaluation: str | None = None) -> list[str]:
    """Why *p* can't move to *status* (empty if it can)."""
    if status not in STATUSES:
        return [f"Status must be one of {', '.join(STATUSES)}"]
    out = []
    target = STATUSES.index(status)
    if target >= 1 and not (p.objectives and p.activities):
        out.append("Add learning objectives and activities before marking it Ready")
    if target >= 2:
        if p.is_shared:
            out.append("A shared plan isn't delivered - copy it to a group first")
        elif p.planned_date and p.planned_date > _today().isoformat():
            out.append(f"The lesson isn't until {p.planned_date}")
    if target == 3 and not ((evaluation or "").strip() or p.evaluation):
        out.append("Write an evaluation (what went well, next steps) to mark it Reviewed")
    return out


def set_status(plan_id: int, status: str, *, actor: Principal,
               evaluation: str | None = None) -> Plan:
    p = get(plan_id)
    _require_owner(actor, p, "lesson_plans.status")
    status = str(status or "").strip().title()
    problems = status_problems(p, status, evaluation=evaluation)
    if p.status == "Reviewed" and status != "Reviewed" and not is_editor(actor):
        problems.append("A reviewed plan is a record - only an editor can reopen it")
    if problems:
        raise ValidationError(problems)
    ev = P._clean_text(evaluation, _TEXT_LIMIT)
    with database.connect() as conn:
        conn.execute("UPDATE lesson_plans SET status = ?, evaluation = COALESCE(?, evaluation), "
                     "updated_at = datetime('now'), updated_by = ? WHERE plan_id = ?",
                     (status, ev, actor.username, p.plan_id))
        _audit(conn, "status", actor, plan_id=p.plan_id, detail={"from": p.status,
                                                                 "to": status})
    activity_log.record("lesson_plans.status", target=f"plan:{p.plan_id}", principal=actor,
                        status=status)
    return get(p.plan_id)


def delete(plan_id: int, *, actor: Principal) -> Plan:
    p = get(plan_id)
    _require_owner(actor, p, "lesson_plans.delete")
    if p.status in ("Delivered", "Reviewed") and not is_editor(actor):
        raise ValidationError([f"A {p.status.lower()} plan is a record - ask an editor to "
                               "remove it"])
    with database.connect() as conn:
        conn.execute("DELETE FROM lesson_plans WHERE plan_id = ?", (p.plan_id,))
        _audit(conn, "delete", actor, plan_id=p.plan_id,
               detail={"title": p.title, "status": p.status})
    activity_log.record("lesson_plans.delete", target=f"plan:{p.plan_id}", principal=actor)
    return p


def copy(plan_id: int, *, actor: Principal, group_id: Any = None, planned_date: Any = None,
         period: Any = None, title: str | None = None, shared: bool = False
         ) -> tuple[Plan, list[str]]:
    """A new Draft with the plan's content (not its evaluation) - for another group or
    date, or as a shared plan (*shared*)."""
    p = get(plan_id)
    data: dict[str, Any] = {k: getattr(p, k) for k, _l in TEXT_FIELDS if k != "evaluation"}
    data.update(title=title or p.title, unit_id=p.unit_id)
    if shared:
        data.update(group_id=None, subject_id=p.subject_id, year_group=p.year_group)
    else:
        data.update(group_id=group_id if group_id not in (None, "") else p.group_id,
                    subject_id=p.subject_id, year_group=p.year_group,
                    planned_date=planned_date, period=period)
        if data["group_id"] is None:
            raise ValidationError(["Choose the group to copy the plan to"])
    if data.get("group_id") and data["group_id"] != p.group_id:
        g = TG.get(int(data["group_id"]))
        if g.subject_id != p.subject_id:
            raise ValidationError([f"{g.code} is a different subject"])
        if g.year_group != p.year_group:
            data["unit_id"] = None
    new, warnings = create(data, actor=actor)
    with database.connect() as conn:
        _audit(conn, "copy", actor, plan_id=new.plan_id, detail={"from": p.plan_id})
    return new, warnings


def plan_from_timetable(group_id: int, start: Any, end: Any, *, actor: Principal,
                        unit_id: Any = None) -> tuple[list[Plan], int]:
    """Draft plans for each timetabled lesson of the group from *start* to *end*
    (lessons that already have a plan are skipped). Returns (created, skipped)."""
    _require_staff(actor, "lesson_plans.from_timetable")
    g = TG.get(int(group_id))
    if not is_editor(actor) and (actor.username or "").lower() not in {
            (g.teacher_username or "").lower()}:
        raise PermissionDenied(f"Only {g.code}'s teacher can plan its lessons in bulk.")
    s, e = _range(start, end)
    unit = get_unit(int(unit_id)) if unit_id not in (None, "") else None
    subject = S.get(g.subject_id)
    n = len(list_plans(group_id=g.group_id, unit_id=unit.unit_id)) if unit else 0
    created, skipped = [], 0
    d = s
    while d <= e:
        lessons, _label = TT.lessons_on(d, group_id=g.group_id)
        for x in lessons:
            if for_lesson(g.group_id, d, x.period):
                skipped += 1
                continue
            n += 1
            title = (f"{unit.title} - lesson {n}" if unit
                     else f"{subject.name} - {d:%a %d %b} P{x.period}")
            plan, _w = create({"title": title, "group_id": g.group_id, "planned_date": d,
                               "period": x.period,
                               "unit_id": unit.unit_id if unit else None}, actor=actor)
            created.append(plan)
        d += _dt.timedelta(days=1)
    return created, skipped


# ── Export ───────────────────────────────────────────────────────────

def as_text(plan_id: int) -> str:
    """The plan as plain text, for printing or e-mailing."""
    p = get(plan_id)
    lines = [p.title, "=" * min(len(p.title), 70),
             f"{p.subject_name} · {p.for_label} · {p.when}"
             + (f" · {p.duration_min} min" if p.duration_min else ""),
             f"Teacher: {p.teacher_name or '-'}    Status: {p.status}"]
    if p.unit_title:
        lines.append(f"Unit: {p.unit_title}")
    for key, label in TEXT_FIELDS:
        value = getattr(p, key)
        if value:
            lines += ["", label, "-" * len(label), value]
    return "\n".join(lines) + "\n"


def export_text(plan_id: int, path: str | Path, *, actor: Principal) -> None:
    _require_staff(actor, "lesson_plans.export", f"plan:{plan_id}")
    Path(path).write_text(as_text(plan_id), encoding="utf-8")
    activity_log.record("lesson_plans.export", target=f"plan:{plan_id}", principal=actor)


S.register_usage("lesson_plans", "subject_id", "lesson plan(s)")
S.register_usage("lesson_plan_units", "subject_id", "scheme of work unit(s)")
