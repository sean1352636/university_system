"""Homework: tasks set to a class, and each pupil's hand-in, mark and feedback.

**Tasks.** Homework is set to a teaching group, which gives it its subject,
year group, class list and teacher. As in the old screen, it can instead be
set to a whole year group (optionally one form) for a subject. The old fields
are kept (title, set by, set date, due date, points, instructions, notes)
with an expected time in minutes and resources added. Status moves
Draft -> Set -> Closed:

* Set needs instructions and a due date that hasn't passed. Setting it adds
  every pupil in the class as Pending (the old "Seed", which can also be run
  again to add pupils who joined since);
* Closed is from the due date on; anyone still Pending becomes Missing
  (a pupil can be marked Missing from the due date too);
* back to Draft only while nobody has handed anything in.

**Pupils' work.** Each pupil has one row: Pending, Submitted, Late, Missing,
Graded or Excused. Work handed in after the due date is Late; Missing only
once the due date has passed; Excused needs a reason; Graded needs a mark or a
grade, and a mark can't be above the task's points.

**Load.** A pupil shouldn't get more than the daily limit (default 2) of
homework due on one day; setting more gives a warning, as does a due date
that isn't a school day.

**Who.** All staff can view all homework and set their own. A task and its
marks can be changed by the person who set it, whoever wrote it, or the
group's teacher, or by :data:`HOMEWORK_EDITORS`, who also set the daily limit.
Homework with work handed in is a record: only editors delete it.
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.curriculum.domain import academic_year as _AY  # noqa: F401 - schema first
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import HOMEWORK_EDITORS, Principal
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

STATUSES: tuple[str, ...] = ("Draft", "Set", "Closed")
WORK_STATUSES: tuple[str, ...] = ("Pending", "Submitted", "Late", "Missing", "Graded",
                                  "Excused")
HANDED_IN = frozenset({"Submitted", "Late", "Graded"})
_TEXT_LIMIT = 4000
DEFAULT_DAILY_LIMIT = 2

_SCHEMA = """
CREATE TABLE IF NOT EXISTS homework_tasks (
    task_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title            TEXT NOT NULL,
    subject_id       INTEGER NOT NULL REFERENCES subjects (subject_id),
    year_group       INTEGER NOT NULL CHECK (year_group BETWEEN 7 AND 11),
    group_id         INTEGER REFERENCES teaching_groups (group_id) ON DELETE SET NULL,
    group_code       TEXT,
    form_group       TEXT,
    set_by_name      TEXT,
    set_by_username  TEXT,
    set_date         TEXT NOT NULL,
    due_date         TEXT NOT NULL,
    est_minutes      INTEGER,
    points           INTEGER,
    status           TEXT NOT NULL DEFAULT 'Draft' CHECK (status IN ('Draft', 'Set', 'Closed')),
    instructions     TEXT,
    resources        TEXT,
    notes            TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    created_by       TEXT,
    updated_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by       TEXT
);
CREATE INDEX IF NOT EXISTS ix_homework_due ON homework_tasks (due_date);
CREATE INDEX IF NOT EXISTS ix_homework_group ON homework_tasks (group_id);
CREATE TABLE IF NOT EXISTS homework_work (
    work_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id        INTEGER NOT NULL REFERENCES homework_tasks (task_id) ON DELETE CASCADE,
    pupil_id       INTEGER NOT NULL REFERENCES pupils (pupil_id),
    status         TEXT NOT NULL DEFAULT 'Pending'
                   CHECK (status IN ('Pending', 'Submitted', 'Late', 'Missing', 'Graded',
                                     'Excused')),
    handed_in      TEXT,
    mark           REAL,
    grade          TEXT,
    feedback       TEXT,
    excuse_reason  TEXT,
    updated_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by     TEXT,
    UNIQUE (task_id, pupil_id)
);
CREATE INDEX IF NOT EXISTS ix_homework_work_pupil ON homework_work (pupil_id, status);
CREATE TABLE IF NOT EXISTS homework_settings (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS homework_audit (
    audit_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id   INTEGER,
    pupil_id  INTEGER,
    action    TEXT NOT NULL CHECK (action IN ('create', 'update', 'status', 'seed', 'work',
                                              'work_delete', 'copy', 'delete', 'notify',
                                              'settings')),
    actor     TEXT NOT NULL,
    detail    TEXT,
    at        TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

database.register_schema("homework", _SCHEMA)

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound


# ── Records ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Task:
    task_id: int
    title: str
    subject_id: int
    year_group: int
    group_id: int | None
    group_code: str | None
    form_group: str | None
    set_by_name: str | None
    set_by_username: str | None
    set_date: str
    due_date: str
    est_minutes: int | None
    points: int | None
    status: str
    instructions: str | None
    resources: str | None
    notes: str | None
    created_at: str
    created_by: str | None
    updated_at: str
    updated_by: str | None
    # Joined for lists:
    subject_code: str = ""
    subject_name: str = ""
    teacher_username: str | None = None   # the group's teacher

    @property
    def for_label(self) -> str:
        """Who it's set to: the group, or the year (and form)."""
        if self.group_code:
            return self.group_code
        return f"Year {self.year_group}" + (f" {self.form_group}" if self.form_group else "")

    @property
    def overdue(self) -> bool:
        return self.status == "Set" and self.due_date < _today().isoformat()


@dataclass(frozen=True)
class Work:
    """One pupil's row for a task."""

    work_id: int
    task_id: int
    pupil_id: int
    status: str
    handed_in: str | None
    mark: float | None
    grade: str | None
    feedback: str | None
    excuse_reason: str | None
    updated_at: str
    updated_by: str | None
    # Joined:
    pupil_name: str = ""
    admission_no: str = ""
    form_group: str | None = None
    due_date: str = ""
    points: int | None = None
    title: str = ""
    subject_code: str = ""

    @property
    def late(self) -> bool:
        return bool(self.handed_in and self.due_date and self.handed_in > self.due_date)

    @property
    def mark_pct(self) -> float | None:
        if self.mark is None:
            return None
        if self.points:
            return round(self.mark * 100 / self.points, 1)
        return round(self.mark, 1)

    @property
    def mark_label(self) -> str:
        if self.mark is None:
            return self.grade or ""
        m = f"{self.mark:g}" + (f"/{self.points}" if self.points else "%")
        return m + (f" ({self.grade})" if self.grade else "")


@dataclass(frozen=True)
class PupilSummary:
    pupil_id: int
    set: int            # homework due so far
    handed_in: int      # Submitted / Late / Graded
    late: int
    missing: int
    excused: int
    average_pct: float | None

    @property
    def completion_pct(self) -> float | None:
        counted = self.set - self.excused
        return round(self.handed_in * 100 / counted, 1) if counted > 0 else None


_SELECT = """
SELECT t.*, s.code AS subject_code, s.name AS subject_name, g.teacher_username
FROM homework_tasks t
JOIN subjects s ON s.subject_id = t.subject_id
LEFT JOIN teaching_groups g ON g.group_id = t.group_id
"""

_WORK_SELECT = """
SELECT w.*, p.legal_last_name, p.legal_first_name, p.preferred_name, p.admission_no,
       p.form_group AS pupil_form, t.due_date, t.points, t.title, s.code AS subject_code
FROM homework_work w
JOIN pupils p ON p.pupil_id = w.pupil_id
JOIN homework_tasks t ON t.task_id = w.task_id
JOIN subjects s ON s.subject_id = t.subject_id
"""

_TASK_FIELDS = tuple(f for f in Task.__dataclass_fields__)
_WORK_BASE = ("work_id", "task_id", "pupil_id", "status", "handed_in", "mark", "grade",
              "feedback", "excuse_reason", "updated_at", "updated_by")


def _task(r) -> Task:
    return Task(**{k: r[k] for k in _TASK_FIELDS})


def _work(r) -> Work:
    first = r["preferred_name"] or r["legal_first_name"]
    return Work(**{k: r[k] for k in _WORK_BASE},
                pupil_name=f"{r['legal_last_name']}, {first}",
                admission_no=r["admission_no"], form_group=r["pupil_form"],
                due_date=r["due_date"], points=r["points"], title=r["title"],
                subject_code=r["subject_code"])


# ── Helpers ──────────────────────────────────────────────────────────

def _same(a: str | None, b: str | None) -> bool:
    return bool(a) and bool(b) and a.strip().lower() == b.strip().lower()  # type: ignore[union-attr]


def is_editor(actor: Principal) -> bool:
    return actor.role in HOMEWORK_EDITORS


def can_change(actor: Principal, task: Task) -> bool:
    """Whoever set it or wrote it, the group's teacher, or an editor."""
    if is_editor(actor):
        return True
    return any(_same(actor.username, u) for u in
               (task.set_by_username, task.created_by, task.teacher_username))


def _require_staff(actor: Principal, action: str, target: Any = None) -> None:
    if not actor.is_staff:
        activity_log.record(action, target=target, outcome="denied", principal=actor)
        raise PermissionDenied("Only school staff can set and mark homework.")


def _require_owner(actor: Principal, task: Task, action: str) -> None:
    _require_staff(actor, action, f"homework:{task.task_id}")
    if not can_change(actor, task):
        activity_log.record(action, target=f"homework:{task.task_id}", outcome="denied",
                            principal=actor)
        raise PermissionDenied("Only the teacher who set this homework (or the group's "
                               "teacher) can change it or mark it.")


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        activity_log.record(action, target=target, outcome="denied", principal=actor)
        raise PermissionDenied("Your account can't change homework settings.")


def _audit(conn, action: str, actor: Principal, *, task_id: int | None = None,
           pupil_id: int | None = None, detail: dict | None = None) -> None:
    conn.execute("INSERT INTO homework_audit (task_id, pupil_id, action, actor, detail) "
                 "VALUES (?, ?, ?, ?, ?)",
                 (task_id, pupil_id, action, actor.username or "unknown",
                  json.dumps(detail, default=str, sort_keys=True) if detail else None))


def _date(value: Any, label: str, problems: list[str]) -> _dt.date | None:
    if value in (None, ""):
        return None
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value
    try:
        return _dt.date.fromisoformat(str(value).strip())
    except ValueError:
        problems.append(f"{label} must be a date (YYYY-MM-DD)")
        return None


def _int(value: Any, label: str, lo: int, hi: int, problems: list[str]) -> int | None:
    if value in (None, ""):
        return None
    try:
        n = int(str(value).strip())
    except ValueError:
        n = lo - 1
    if not lo <= n <= hi:
        problems.append(f"{label} must be a whole number from {lo} to {hi}")
        return None
    return n


def _school_day(day: _dt.date) -> tuple[bool, str]:
    from education_system.systems.secondary.modules.attendance.domain import attendance as AT
    return AT.school_day(day)


# ── Settings ─────────────────────────────────────────────────────────

def daily_limit() -> int:
    with database.connect() as conn:
        r = conn.execute("SELECT value FROM homework_settings WHERE key = 'daily_limit'"
                         ).fetchone()
    return int(r[0]) if r else DEFAULT_DAILY_LIMIT


def set_daily_limit(value: Any, *, actor: Principal) -> int:
    _require_editor(actor, "homework.settings")
    problems: list[str] = []
    n = _int(value, "Daily limit", 1, 10, problems)
    if n is None:
        raise ValidationError(problems or ["Daily limit must be a whole number from 1 to 10"])
    with database.connect() as conn:
        conn.execute("INSERT INTO homework_settings (key, value) VALUES ('daily_limit', ?) "
                     "ON CONFLICT (key) DO UPDATE SET value = excluded.value", (str(n),))
        _audit(conn, "settings", actor, detail={"daily_limit": n})
    activity_log.record("homework.settings", principal=actor)
    return n


# ── Reading tasks ────────────────────────────────────────────────────

def get(task_id: int) -> Task:
    with database.connect() as conn:
        r = conn.execute(_SELECT + " WHERE t.task_id = ?", (int(task_id),)).fetchone()
    if r is None:
        raise NotFound(f"No homework #{task_id}")
    return _task(r)


def list_tasks(*, year_group: int | None = None, subject_id: int | None = None,
               group_id: int | None = None, status: str | None = None,
               teacher: str | None = None, due_from: Any = None, due_to: Any = None,
               search: str | None = None) -> list[Task]:
    """Homework, latest due first. *teacher* matches the setter or group teacher
    (username or name)."""
    where, params = [], []
    if year_group:
        where.append("t.year_group = ?")
        params.append(int(year_group))
    if subject_id is not None:
        where.append("t.subject_id = ?")
        params.append(int(subject_id))
    if group_id is not None:
        where.append("t.group_id = ?")
        params.append(int(group_id))
    if status:
        if status not in STATUSES:
            raise ValidationError([f"Status must be one of {', '.join(STATUSES)}"])
        where.append("t.status = ?")
        params.append(status)
    if teacher:
        where.append("(lower(t.set_by_username) = lower(?) OR lower(t.set_by_name) = lower(?) "
                     "OR lower(g.teacher_username) = lower(?) OR lower(t.created_by) = lower(?))")
        params += [teacher.strip()] * 4
    problems: list[str] = []
    for value, op, label in ((due_from, ">=", "From"), (due_to, "<=", "To")):
        d = _date(value, f"{label} date", problems)
        if d:
            where.append(f"t.due_date {op} ?")
            params.append(d.isoformat())
    if problems:
        raise ValidationError(problems)
    for term in (search or "").split():
        where.append("(t.title LIKE ? OR t.group_code LIKE ? OR s.code LIKE ?)")
        params += [f"%{term}%"] * 3
    sql = _SELECT + (" WHERE " + " AND ".join(where) if where else "")
    sql += " ORDER BY t.due_date DESC, t.task_id DESC"
    with database.connect() as conn:
        return [_task(r) for r in conn.execute(sql, params)]


def status_counts() -> dict[str, int]:
    out = {s: 0 for s in STATUSES}
    with database.connect() as conn:
        for r in conn.execute("SELECT status, COUNT(*) FROM homework_tasks GROUP BY status"):
            out[r[0]] = r[1]
    return out


def history(*, task_id: int | None = None, pupil_id: int | None = None,
            limit: int = 200) -> list[dict[str, Any]]:
    sql, params = "SELECT * FROM homework_audit", []
    if task_id is not None:
        sql += " WHERE task_id = ?"
        params.append(int(task_id))
    elif pupil_id is not None:
        sql += " WHERE pupil_id = ?"
        params.append(int(pupil_id))
    params.append(int(limit))
    with database.connect() as conn:
        return [{"at": r["at"], "actor": r["actor"], "action": r["action"],
                 "pupil_id": r["pupil_id"], "detail": json.loads(r["detail"] or "{}")}
                for r in conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?", params)]


# ── Class lists ──────────────────────────────────────────────────────

def pupils_for(task: Task) -> list[P.Pupil]:
    """Who the homework is for: the group's members, else the year (and form)."""
    if task.group_id is not None:
        return TG.members(task.group_id)
    return P.list_pupils(year_group=task.year_group, form_group=task.form_group or None)


def _due_counts(pupil_ids: list[int], due: str, not_task: int | None) -> Counter:
    """How many other Set homeworks each pupil has due on *due*."""
    out: Counter = Counter()
    if not pupil_ids:
        return out
    with database.connect() as conn:
        for start in range(0, len(pupil_ids), 500):
            chunk = pupil_ids[start:start + 500]
            rows = conn.execute(
                "SELECT w.pupil_id, COUNT(*) FROM homework_work w JOIN homework_tasks t "
                "USING (task_id) WHERE t.due_date = ? AND t.status = 'Set' AND "
                f"t.task_id IS NOT ? AND w.pupil_id IN ({', '.join('?' * len(chunk))}) "  # nosec B608 - placeholders only
                "GROUP BY w.pupil_id", (due, not_task, *chunk)).fetchall()
            out.update({r[0]: r[1] for r in rows})
    return out


def load_warnings(task: Task, pupils: list[P.Pupil] | None = None) -> list[str]:
    """Too much homework due that day, or a due date that isn't a school day."""
    out = []
    due = _dt.date.fromisoformat(task.due_date)
    ok, label = _school_day(due)
    if not ok:
        out.append(f"{due:%a %d %b} isn't a school day ({label})")
    pupils = pupils if pupils is not None else pupils_for(task)
    counts = _due_counts([p.pupil_id for p in pupils], task.due_date, task.task_id)
    limit = daily_limit()
    over = sum(1 for n in counts.values() if n >= limit)
    if over:
        out.append(f"{over} pupil(s) already have {limit} or more homework(s) due on "
                   f"{due:%a %d %b}")
    return out


# ── Changing tasks ───────────────────────────────────────────────────

EDITABLE_FIELDS: tuple[str, ...] = (
    "title", "group_id", "subject_id", "year_group", "form_group", "set_by_name",
    "set_by_username", "set_date", "due_date", "est_minutes", "points", "instructions",
    "resources", "notes")


def _clean(data: dict[str, Any], current: Task | None) -> dict[str, Any]:
    problems: list[str] = []
    unknown = set(data) - set(EDITABLE_FIELDS) - {"status"}
    if unknown:
        problems.append(f"Unknown field(s): {', '.join(sorted(unknown))}")
    merged: dict[str, Any] = ({k: getattr(current, k) for k in EDITABLE_FIELDS}
                              if current else {})
    merged.update(data)
    out: dict[str, Any] = {}
    out["title"] = P._clean_text(merged.get("title"), 120)
    if not out["title"]:
        problems.append("Give the homework a title")

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
        out.update(group_id=group.group_id, group_code=group.code,
                   subject_id=group.subject_id, year_group=group.year_group, form_group=None)
    else:
        out["group_id"] = None
        # A group that was deleted later keeps its code on the homework.
        out["group_code"] = (current.group_code if current is not None
                             and current.group_id is None else None)
        subject = None
        try:
            subject = S.get(int(merged.get("subject_id")))  # type: ignore[arg-type]
            out["subject_id"] = subject.subject_id
        except (TypeError, ValueError, S.NotFound):
            problems.append("Choose a teaching group, or a subject and year group")
        year = _int(merged.get("year_group"), "Year group", 7, 11, problems)
        if subject is not None and year is None and not any("Year" in p for p in problems):
            problems.append("Choose a year group")
        if subject is not None and year is not None and year not in subject.years:
            problems.append(f"{subject.name} isn't taught in Year {year}")
        out["year_group"] = year
        form = P._clean_text(merged.get("form_group"), 20)
        if form and year is not None:
            from education_system.systems.secondary.modules.curriculum.domain import (
                form_groups as FG,
            )
            names = FG.names_for_year(year)
            hit = next((n for n in names if n.lower() == form.lower()), None)
            if names and hit is None:
                problems.append(f"Form must be one of Year {year}'s forms: {', '.join(names)}")
            form = hit or form
        out["form_group"] = form

    set_date = _date(merged.get("set_date"), "Set date", problems) or _today()
    due = _date(merged.get("due_date"), "Due date", problems)
    if due is None and not any("Due date" in p for p in problems):
        problems.append("Due date is required")
    if due is not None and due < set_date:
        problems.append("The due date can't be before the set date")
    out["set_date"] = set_date.isoformat()
    out["due_date"] = due.isoformat() if due else None
    out["est_minutes"] = _int(merged.get("est_minutes"), "Expected time (minutes)", 5, 300,
                              problems)
    out["points"] = _int(merged.get("points"), "Points", 1, 1000, problems)

    out["set_by_username"] = P._clean_text(merged.get("set_by_username"), 100)
    out["set_by_name"] = P._clean_text(merged.get("set_by_name"), 100)
    if out["set_by_username"]:
        login = next((t for t in TG.teacher_choices()
                      if _same(t["username"], out["set_by_username"])), None)
        if login is None:
            if current is None or out["set_by_username"] != current.set_by_username:
                problems.append(f"'{out['set_by_username']}' isn't a secondary staff login")
        else:
            out["set_by_username"] = login["username"]
            out["set_by_name"] = out["set_by_name"] or login["display_name"]
    for key in ("instructions", "resources", "notes"):
        out[key] = P._clean_text(merged.get(key), _TEXT_LIMIT)
    if problems:
        raise ValidationError(problems)
    return out


def _setter_defaults(clean: dict[str, Any], actor: Principal) -> None:
    """New homework: set by the signed-in teacher (else the group's teacher)."""
    if clean["set_by_username"] or clean["set_by_name"]:
        return
    me = next((t for t in TG.teacher_choices() if _same(t["username"], actor.username)), None)
    if me is not None:
        clean["set_by_username"], clean["set_by_name"] = me["username"], me["display_name"]
    elif clean["group_id"] is not None:
        g = TG.get(clean["group_id"])
        clean["set_by_username"], clean["set_by_name"] = g.teacher_username, g.teacher_name
    else:
        clean["set_by_name"] = actor.username


def create(data: dict[str, Any], *, actor: Principal) -> tuple[Task, list[str]]:
    """New homework as a Draft; ``status="Set"`` sets it straight away.
    Returns (task, warnings)."""
    _require_staff(actor, "homework.create")
    status = str(data.get("status") or "Draft").strip().title()
    if status not in ("Draft", "Set"):
        raise ValidationError(["New homework is a Draft or Set"])
    clean = _clean({k: v for k, v in data.items() if k != "status"}, None)
    if status == "Set":
        problems = []
        if not clean["instructions"]:
            problems.append("Write the instructions before setting the homework")
        if clean["due_date"] < _today().isoformat():
            problems.append(f"The due date ({clean['due_date']}) has passed")
        if problems:
            raise ValidationError(problems)
    _setter_defaults(clean, actor)
    with database.connect() as conn:
        cols = list(clean)
        tid = conn.execute(
            f"INSERT INTO homework_tasks ({', '.join(cols)}, created_by, updated_by) "  # nosec B608 - columns from _clean
            f"VALUES ({', '.join('?' * len(cols))}, ?, ?)",
            (*clean.values(), actor.username, actor.username)).lastrowid
        _audit(conn, "create", actor, task_id=tid, detail={"group_id": clean["group_id"]})
    activity_log.record("homework.create", target=f"homework:{tid}", principal=actor)
    if status == "Set":
        return set_task(tid, actor=actor)
    return get(tid), []


def update(task_id: int, changes: dict[str, Any], *, actor: Principal
           ) -> tuple[Task, list[str]]:
    """Change the details. Returns (task, warnings)."""
    t = get(task_id)
    _require_owner(actor, t, "homework.update")
    if "status" in changes:
        raise ValidationError(["Use Set status to change the status"])
    clean = _clean(changes, t)
    diff = {k: v for k, v in clean.items() if getattr(t, k) != v}
    if not diff:
        return t, []
    if t.status != "Draft" and set(diff) & {"group_id", "subject_id", "year_group",
                                            "form_group"}:
        raise ValidationError(["Homework that has been set can't move to another class - "
                               "copy it instead"])
    if t.status != "Draft" and "points" in diff and clean["points"] is not None:
        with database.connect() as conn:
            top = conn.execute("SELECT MAX(mark) FROM homework_work WHERE task_id = ?",
                               (t.task_id,)).fetchone()[0]
        if top is not None and top > clean["points"]:
            raise ValidationError([f"A pupil already has {top:g} - points can't be lower"])
    with database.connect() as conn:
        sets = ", ".join(f"{k} = ?" for k in diff)
        conn.execute(f"UPDATE homework_tasks SET {sets}, updated_at = datetime('now'), "  # nosec B608 - keys from _clean
                     "updated_by = ? WHERE task_id = ?",
                     (*diff.values(), actor.username, t.task_id))
        _audit(conn, "update", actor, task_id=t.task_id, detail={"fields": sorted(diff)})
    activity_log.record("homework.update", target=f"homework:{t.task_id}", principal=actor,
                        fields=sorted(diff))
    new = get(t.task_id)
    warnings = load_warnings(new) if new.status == "Set" and "due_date" in diff else []
    return new, warnings


def seed(task_id: int, *, actor: Principal) -> int:
    """Add a Pending row for each pupil in the class who hasn't got one (the old
    "Seed"). Returns how many were added."""
    t = get(task_id)
    _require_owner(actor, t, "homework.seed")
    if t.status == "Draft":
        raise ValidationError(["Set the homework first - pupils are added when it's set"])
    pupils = pupils_for(t)
    with database.connect() as conn:
        have = {r[0] for r in conn.execute("SELECT pupil_id FROM homework_work WHERE "
                                           "task_id = ?", (t.task_id,))}
        new = [p.pupil_id for p in pupils if p.pupil_id not in have]
        conn.executemany("INSERT INTO homework_work (task_id, pupil_id, updated_by) "
                         "VALUES (?, ?, ?)", [(t.task_id, pid, actor.username) for pid in new])
        if new:
            _audit(conn, "seed", actor, task_id=t.task_id, detail={"added": len(new)})
    activity_log.record("homework.seed", target=f"homework:{t.task_id}", principal=actor,
                        added=len(new))
    return len(new)


def set_task(task_id: int, *, actor: Principal) -> tuple[Task, list[str]]:
    """Draft (or Closed) -> Set: adds the class as Pending. Returns (task, warnings)."""
    t = get(task_id)
    _require_owner(actor, t, "homework.status")
    problems = []
    if not t.instructions:
        problems.append("Write the instructions before setting the homework")
    if t.status == "Draft" and t.due_date < _today().isoformat():
        problems.append(f"The due date ({t.due_date}) has passed")
    if problems:
        raise ValidationError(problems)
    pupils = pupils_for(t)
    if not pupils:
        raise ValidationError([f"Nobody is in {t.for_label} to set it to"])
    warnings = load_warnings(t, pupils) if t.status == "Draft" else []
    with database.connect() as conn:
        conn.execute("UPDATE homework_tasks SET status = 'Set', updated_at = datetime('now'), "
                     "updated_by = ? WHERE task_id = ?", (actor.username, t.task_id))
        _audit(conn, "status", actor, task_id=t.task_id, detail={"from": t.status, "to": "Set"})
    activity_log.record("homework.status", target=f"homework:{t.task_id}", principal=actor,
                        status="Set")
    seed(t.task_id, actor=actor)
    return get(t.task_id), warnings


def close(task_id: int, *, actor: Principal) -> tuple[Task, int]:
    """Set -> Closed: anyone still Pending is Missing. Returns (task, missing)."""
    t = get(task_id)
    _require_owner(actor, t, "homework.status")
    if t.status != "Set":
        raise ValidationError([f"Only set homework can be closed (this is {t.status})"])
    if t.due_date > _today().isoformat():
        raise ValidationError([f"It isn't due until {t.due_date}"])
    with database.connect() as conn:
        n = conn.execute("UPDATE homework_work SET status = 'Missing', "
                         "updated_at = datetime('now'), updated_by = ? WHERE task_id = ? AND "
                         "status = 'Pending'", (actor.username, t.task_id)).rowcount
        conn.execute("UPDATE homework_tasks SET status = 'Closed', "
                     "updated_at = datetime('now'), updated_by = ? WHERE task_id = ?",
                     (actor.username, t.task_id))
        _audit(conn, "status", actor, task_id=t.task_id,
               detail={"from": "Set", "to": "Closed", "missing": n})
    activity_log.record("homework.status", target=f"homework:{t.task_id}", principal=actor,
                        status="Closed")
    return get(t.task_id), n


def to_draft(task_id: int, *, actor: Principal) -> Task:
    """Set -> Draft while nobody has handed anything in (Pending rows go)."""
    t = get(task_id)
    _require_owner(actor, t, "homework.status")
    if t.status == "Draft":
        return t
    with database.connect() as conn:
        n = conn.execute("SELECT COUNT(*) FROM homework_work WHERE task_id = ? AND "
                         "status != 'Pending'", (t.task_id,)).fetchone()[0]
        if n:
            raise ValidationError([f"{n} pupil(s) already have work recorded - it can't go "
                                   "back to Draft"])
        conn.execute("DELETE FROM homework_work WHERE task_id = ?", (t.task_id,))
        conn.execute("UPDATE homework_tasks SET status = 'Draft', "
                     "updated_at = datetime('now'), updated_by = ? WHERE task_id = ?",
                     (actor.username, t.task_id))
        _audit(conn, "status", actor, task_id=t.task_id, detail={"from": t.status,
                                                                 "to": "Draft"})
    activity_log.record("homework.status", target=f"homework:{t.task_id}", principal=actor,
                        status="Draft")
    return get(t.task_id)


def set_status(task_id: int, status: str, *, actor: Principal) -> tuple[Task, list[str]]:
    """The old "Set status": Draft / Set / Closed, each with its rules."""
    status = str(status or "").strip().title()
    if status == "Set":
        return set_task(task_id, actor=actor)
    if status == "Closed":
        t, n = close(task_id, actor=actor)
        return t, ([f"{n} pupil(s) hadn't handed it in - now Missing"] if n else [])
    if status == "Draft":
        return to_draft(task_id, actor=actor), []
    raise ValidationError([f"Status must be one of {', '.join(STATUSES)}"])


def delete(task_id: int, *, actor: Principal) -> Task:
    t = get(task_id)
    _require_owner(actor, t, "homework.delete")
    with database.connect() as conn:
        n = conn.execute("SELECT COUNT(*) FROM homework_work WHERE task_id = ? AND status IN "
                         "('Submitted', 'Late', 'Graded')", (t.task_id,)).fetchone()[0]
        if n and not is_editor(actor):
            raise ValidationError([f"{n} pupil(s) have handed this in - it's a record now; "
                                   "close it, or ask an administrator to remove it"])
        conn.execute("DELETE FROM homework_tasks WHERE task_id = ?", (t.task_id,))
        _audit(conn, "delete", actor, task_id=t.task_id,
               detail={"title": t.title, "status": t.status, "handed_in": n})
    activity_log.record("homework.delete", target=f"homework:{t.task_id}", principal=actor)
    return t


def copy(task_id: int, *, actor: Principal, group_id: Any = None, set_date: Any = None,
         due_date: Any = None, title: str | None = None) -> tuple[Task, list[str]]:
    """The same homework as a new Draft - for another group, or new dates."""
    t = get(task_id)
    data: dict[str, Any] = {k: getattr(t, k) for k in ("title", "est_minutes", "points",
                                                       "instructions", "resources", "notes")}
    if title:
        data["title"] = title
    if group_id not in (None, ""):
        g = TG.get(int(group_id))
        if g.subject_id != t.subject_id:
            raise ValidationError([f"{g.code} is a different subject"])
        data["group_id"] = g.group_id
    elif t.group_id is not None:
        data["group_id"] = t.group_id
    else:
        data.update(subject_id=t.subject_id, year_group=t.year_group, form_group=t.form_group)
    data["set_date"] = set_date or _today()
    data["due_date"] = due_date
    if data["due_date"] in (None, ""):
        raise ValidationError(["Give the copy a due date"])
    new, warnings = create(data, actor=actor)
    with database.connect() as conn:
        _audit(conn, "copy", actor, task_id=new.task_id, detail={"from": t.task_id})
    return new, warnings


# ── Pupils' work ─────────────────────────────────────────────────────

def list_work(task_id: int) -> list[Work]:
    with database.connect() as conn:
        return [_work(r) for r in conn.execute(
            _WORK_SELECT + " WHERE w.task_id = ? ORDER BY p.legal_last_name COLLATE NOCASE, "
            "p.legal_first_name COLLATE NOCASE", (int(task_id),))]


def get_work(task_id: int, pupil_id: int) -> Work | None:
    with database.connect() as conn:
        r = conn.execute(_WORK_SELECT + " WHERE w.task_id = ? AND w.pupil_id = ?",
                         (int(task_id), int(pupil_id))).fetchone()
    return _work(r) if r else None


def record(task_id: int, pupil_id: int, data: dict[str, Any], *, actor: Principal
           ) -> Work:
    """Record a pupil's work: ``status`` (Submitted / Late / Missing / Graded /
    Excused / Pending), ``handed_in``, ``mark``, ``grade``, ``feedback``,
    ``excuse_reason``. Keys left out keep what's there."""
    t = get(task_id)
    _require_owner(actor, t, "homework.work")
    if t.status == "Draft":
        raise ValidationError(["Set the homework first"])
    current = get_work(t.task_id, pupil_id)
    if current is None:
        if int(pupil_id) not in {p.pupil_id for p in pupils_for(t)}:
            raise ValidationError([f"That pupil isn't in {t.for_label}"])
    unknown = set(data) - {"status", "handed_in", "mark", "grade", "feedback",
                           "excuse_reason"}
    if unknown:
        raise ValidationError([f"Unknown field(s): {', '.join(sorted(unknown))}"])
    problems: list[str] = []
    old = {k: getattr(current, k) if current else None for k in
           ("status", "handed_in", "mark", "grade", "feedback", "excuse_reason")}
    status = str(data.get("status") or old["status"] or "Pending").strip().title()
    if status not in WORK_STATUSES:
        problems.append(f"Status must be one of {', '.join(WORK_STATUSES)}")
    today = _today()
    handed = _date(data["handed_in"], "Handed in", problems) if "handed_in" in data else (
        _dt.date.fromisoformat(old["handed_in"]) if old["handed_in"] else None)
    mark: float | None = old["mark"]
    if "mark" in data:
        mark = None
        if data["mark"] not in (None, ""):
            top = t.points or 100
            try:
                mark = float(str(data["mark"]).strip().rstrip("%"))
            except ValueError:
                mark = -1.0
            if not 0 <= mark <= top:
                problems.append(f"Mark must be from 0 to {top}" + ("" if t.points else " (%)"))
    grade = P._clean_text(data["grade"], 10) if "grade" in data else old["grade"]
    feedback = (P._clean_text(data["feedback"], _TEXT_LIMIT) if "feedback" in data
                else old["feedback"])
    reason = (P._clean_text(data["excuse_reason"], 200) if "excuse_reason" in data
              else old["excuse_reason"])
    if status in HANDED_IN:
        handed = handed or today
        if handed > today:
            problems.append("Work can't be handed in on a future date")
        if handed.isoformat() < t.set_date:
            problems.append(f"It wasn't set until {t.set_date}")
        if status in ("Submitted", "Late"):
            status = "Late" if handed.isoformat() > t.due_date else "Submitted"
            if "status" not in data and (mark is not None or grade):
                status = "Graded"   # a mark on handed-in work grades it
        if status == "Graded" and mark is None and not grade:
            problems.append("Give a mark or a grade to mark it Graded")
        reason = None
    else:
        handed = None
        if (data.get("mark") not in (None, "")) or (data.get("grade") not in (None, "")):
            problems.append("Only work that's been handed in can have a mark")
        mark, grade = None, None
        if status == "Missing" and t.due_date > today.isoformat():
            problems.append(f"It isn't missing yet - it's due {t.due_date}")
        if status == "Excused" and not reason:
            problems.append("Say why the pupil is excused")
        if status != "Excused":
            reason = None
    if problems:
        raise ValidationError(problems)
    new = {"status": status, "handed_in": handed.isoformat() if handed else None,
           "mark": mark, "grade": grade, "feedback": feedback, "excuse_reason": reason}
    changed = sorted(k for k in new if new[k] != old[k])
    with database.connect() as conn:
        conn.execute(
            "INSERT INTO homework_work (task_id, pupil_id, status, handed_in, mark, grade, "
            "feedback, excuse_reason, updated_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (task_id, pupil_id) DO UPDATE SET status = excluded.status, "
            "handed_in = excluded.handed_in, mark = excluded.mark, grade = excluded.grade, "
            "feedback = excluded.feedback, excuse_reason = excluded.excuse_reason, "
            "updated_at = datetime('now'), updated_by = excluded.updated_by",
            (t.task_id, int(pupil_id), *new.values(), actor.username))
        if changed:
            _audit(conn, "work", actor, task_id=t.task_id, pupil_id=int(pupil_id),
                   detail={"from": old["status"], "to": status, "fields": changed})
    activity_log.record("homework.work", target=f"homework:{t.task_id}", principal=actor,
                        status=status)
    out = get_work(t.task_id, pupil_id)
    assert out is not None
    return out


def hand_in(task_id: int, *, actor: Principal, pupil_id: int | None = None,
            note: str | None = None) -> Work:
    """A pupil marks their own homework as handed in (from the pupil portal):
    Submitted, or Late after the due date. Only while the homework is Set, and
    only once - the teacher marks it from there. *note* is kept as the pupil's
    comment in the feedback box only if the teacher hasn't written any."""
    from education_system.systems.secondary.modules.portals.domain import portal_accounts
    if not actor.is_student:
        activity_log.record("homework.hand_in", target=f"homework:{task_id}",
                            outcome="denied", principal=actor)
        raise PermissionDenied("Only the pupil can hand in their own homework.")
    mine = portal_accounts.pupils_for(actor, "pupil")
    pupil = next((p for p in mine if pupil_id is None or p.pupil_id == int(pupil_id)), None)
    if pupil is None:
        activity_log.record("homework.hand_in", target=f"homework:{task_id}",
                            outcome="denied", principal=actor)
        raise PermissionDenied("You can only hand in your own homework.")
    t = get(task_id)
    w = get_work(t.task_id, pupil.pupil_id)
    if w is None and pupil.pupil_id not in {p.pupil_id for p in pupils_for(t)}:
        raise PermissionDenied("That homework wasn't set to you.")
    if t.status != "Set":
        raise ValidationError(["That homework isn't open for handing in"])
    if w is not None and w.status not in ("Pending", "Missing"):
        raise ValidationError([f"You've already handed it in ({w.status.lower()})"
                               if w.status in HANDED_IN else
                               f"It's marked {w.status.lower()} - speak to your teacher"])
    today = _today()
    status = "Late" if today.isoformat() > t.due_date else "Submitted"
    comment = P._clean_text(note, 500)
    with database.connect() as conn:
        conn.execute(
            "INSERT INTO homework_work (task_id, pupil_id, status, handed_in, feedback, "
            "updated_by) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (task_id, pupil_id) DO UPDATE "
            "SET status = excluded.status, handed_in = excluded.handed_in, "
            "feedback = COALESCE(homework_work.feedback, excluded.feedback), "
            "updated_at = datetime('now'), updated_by = excluded.updated_by",
            (t.task_id, pupil.pupil_id, status, today.isoformat(),
             f"Pupil: {comment}" if comment else None, actor.username))
        _audit(conn, "work", actor, task_id=t.task_id, pupil_id=pupil.pupil_id,
               detail={"from": w.status if w else None, "to": status, "by": "pupil"})
    activity_log.record("homework.hand_in", target=f"homework:{t.task_id}", principal=actor,
                        status=status)
    out = get_work(t.task_id, pupil.pupil_id)
    assert out is not None
    return out


def record_many(task_id: int, pupil_ids: list[int], status: str, *, actor: Principal,
                handed_in: Any = None, excuse_reason: str | None = None
                ) -> tuple[int, list[str]]:
    """Give several pupils the same status (e.g. tick off who handed it in).
    Returns (how many changed, problems for the ones that couldn't)."""
    done, problems = 0, []
    for pid in pupil_ids:
        data: dict[str, Any] = {"status": status}
        if handed_in not in (None, ""):
            data["handed_in"] = handed_in
        if excuse_reason:
            data["excuse_reason"] = excuse_reason
        try:
            record(task_id, pid, data, actor=actor)
            done += 1
        except ValidationError as e:
            p = P.get_pupil(pid)
            problems.append(f"{p.display_name if p else pid}: {'; '.join(e.problems)}")
    return done, problems


def delete_work(task_id: int, pupil_id: int, *, actor: Principal) -> Work:
    """Remove a pupil's row (e.g. added by mistake). Marked work: editors only."""
    t = get(task_id)
    _require_owner(actor, t, "homework.work_delete")
    w = get_work(task_id, pupil_id)
    if w is None:
        raise NotFound("That pupil has no row for this homework")
    if w.status in HANDED_IN and not is_editor(actor):
        raise ValidationError(["This pupil handed work in - set them Excused instead"])
    with database.connect() as conn:
        conn.execute("DELETE FROM homework_work WHERE work_id = ?", (w.work_id,))
        _audit(conn, "work_delete", actor, task_id=t.task_id, pupil_id=w.pupil_id,
               detail={"status": w.status})
    activity_log.record("homework.work_delete", target=f"homework:{t.task_id}",
                        principal=actor)
    return w


# ── Reports ──────────────────────────────────────────────────────────

def summary(task_id: int) -> dict[str, Any]:
    """The old Summary: counts by status, average mark and completion."""
    t = get(task_id)
    rows = list_work(t.task_id)
    counts = Counter(w.status for w in rows)
    marks = [w.mark_pct for w in rows if w.mark_pct is not None]
    counted = len(rows) - counts["Excused"]
    handed = sum(counts[s] for s in HANDED_IN)
    return {"task": t, "total": len(rows),
            "by_status": {s: counts.get(s, 0) for s in WORK_STATUSES},
            "handed_in": handed, "late": sum(1 for w in rows if w.late),
            "completion_pct": round(handed * 100 / counted, 1) if counted else None,
            "marked": len(marks),
            "average_pct": round(sum(marks) / len(marks), 1) if marks else None,
            "to_mark": counts["Submitted"] + counts["Late"]}


def for_pupil(pupil_id: int, *, status: str | None = None, since: Any = None) -> list[Work]:
    """The old 'Pupil submission history': newest due first."""
    sql, params = _WORK_SELECT + " WHERE w.pupil_id = ? AND t.status != 'Draft'", [int(pupil_id)]
    if status:
        if status not in WORK_STATUSES:
            raise ValidationError([f"Status must be one of {', '.join(WORK_STATUSES)}"])
        sql += " AND w.status = ?"
        params.append(status)
    if since:
        sql += " AND t.due_date >= ?"
        params.append(_dt.date.fromisoformat(str(since)).isoformat())
    with database.connect() as conn:
        return [_work(r) for r in conn.execute(sql + " ORDER BY t.due_date DESC", params)]


def pupil_summary(pupil_id: int, *, since: Any = None) -> PupilSummary:
    """This academic year's homework (due so far) for the pupil profile."""
    start = since or P.academic_year_start(_today())
    today = _today().isoformat()
    rows = [w for w in for_pupil(pupil_id, since=start) if w.due_date <= today]
    marks = [w.mark_pct for w in rows if w.mark_pct is not None]
    return PupilSummary(pupil_id, len(rows), sum(1 for w in rows if w.status in HANDED_IN),
                        sum(1 for w in rows if w.late),
                        sum(1 for w in rows if w.status == "Missing"),
                        sum(1 for w in rows if w.status == "Excused"),
                        round(sum(marks) / len(marks), 1) if marks else None)


def _mine(actor: Principal, t: Task) -> bool:
    return any(_same(actor.username, u) for u in
               (t.set_by_username, t.created_by, t.teacher_username))


def to_mark(actor: Principal, *, everyone: bool = False) -> list[tuple[Task, int]]:
    """Homework of mine (or, with *everyone*, all homework) with work handed in but
    not graded: (task, how many), oldest due first."""
    with database.connect() as conn:
        rows = conn.execute(
            "SELECT task_id, COUNT(*) FROM homework_work WHERE status IN ('Submitted', 'Late') "
            "GROUP BY task_id").fetchall()
    out = [(t, n) for t, n in ((get(tid), n) for tid, n in rows)
           if everyone or _mine(actor, t)]
    return sorted(out, key=lambda x: (x[0].due_date, x[0].task_id))


def my_homework(actor: Principal, *, status: str | None = None) -> list[Task]:
    """Homework I set, or for groups I teach."""
    return list_tasks(teacher=actor.username, status=status)


def missing_report(*, start: Any = None, end: Any = None, year_group: int | None = None,
                   group_id: int | None = None) -> list[dict[str, Any]]:
    """Pupils with homework Missing (or handed in late) between the due dates,
    most missing first."""
    problems: list[str] = []
    s = _date(start, "From date", problems) or P.academic_year_start(_today())
    e = _date(end, "To date", problems) or _today()
    if problems:
        raise ValidationError(problems)
    sql = (_WORK_SELECT + " WHERE t.due_date BETWEEN ? AND ? AND t.status != 'Draft' "
           "AND p.roll_status = 'on_roll'")
    params: list[Any] = [s.isoformat(), e.isoformat()]
    if year_group:
        sql += " AND t.year_group = ?"
        params.append(int(year_group))
    if group_id is not None:
        sql += " AND t.group_id = ?"
        params.append(int(group_id))
    by: dict[int, dict[str, Any]] = {}
    with database.connect() as conn:
        for r in conn.execute(sql, params):
            w = _work(r)
            row = by.setdefault(w.pupil_id, {"pupil_id": w.pupil_id, "name": w.pupil_name,
                                             "admission_no": w.admission_no,
                                             "form_group": w.form_group, "set": 0,
                                             "missing": 0, "late": 0, "titles": []})
            row["set"] += 1
            if w.status == "Missing":
                row["missing"] += 1
                row["titles"].append(f"{w.subject_code} {w.title} ({w.due_date})")
            if w.late:
                row["late"] += 1
    rows = [r for r in by.values() if r["missing"] or r["late"]]
    return sorted(rows, key=lambda r: (-r["missing"], -r["late"], r["name"].lower()))


def due_calendar(start: Any, end: Any, *, year_group: int | None = None
                 ) -> dict[str, list[Task]]:
    """Set homework by due date, for the homework timetable."""
    rows = list_tasks(year_group=year_group, due_from=start, due_to=end)
    out: dict[str, list[Task]] = {}
    for t in sorted(rows, key=lambda x: (x.due_date, x.for_label)):
        if t.status != "Draft":
            out.setdefault(t.due_date, []).append(t)
    return out


def completion_by_group(*, year_group: int | None = None) -> list[dict[str, Any]]:
    """Per class: homeworks set, completion and average mark this year."""
    since = P.academic_year_start(_today()).isoformat()
    today = _today().isoformat()
    by: dict[str, dict[str, Any]] = {}
    for t in list_tasks(year_group=year_group, due_from=since, due_to=today):
        if t.status == "Draft":
            continue
        s = summary(t.task_id)
        key = t.for_label
        row = by.setdefault(key, {"for": key, "subject": t.subject_code, "tasks": 0,
                                  "pupil_tasks": 0, "handed_in": 0, "excused": 0,
                                  "marks": []})
        row["tasks"] += 1
        row["pupil_tasks"] += s["total"]
        row["handed_in"] += s["handed_in"]
        row["excused"] += s["by_status"]["Excused"]
        if s["average_pct"] is not None:
            row["marks"].append(s["average_pct"])
    out = []
    for row in sorted(by.values(), key=lambda r: r["for"].lower()):
        counted = row["pupil_tasks"] - row["excused"]
        marks = row.pop("marks")
        row["completion_pct"] = round(row["handed_in"] * 100 / counted, 1) if counted else None
        row["average_pct"] = round(sum(marks) / len(marks), 1) if marks else None
        out.append(row)
    return out


# ── Telling parents and exporting ────────────────────────────────────

def email_body(task: Task) -> str:
    return ("Dear {contact_name},\n\n"
            f"{{pupil_first_name}} hasn't handed in their {task.subject_name} homework "
            f"\"{task.title}\", which was due on "
            f"{_dt.date.fromisoformat(task.due_date):%A %d %B}.\n\n"
            "Please could you encourage them to complete it and hand it in as soon as "
            "possible.\n\nThank you,\n" + (task.set_by_name or "The school"))


def notify_parents(task_id: int, *, actor: Principal, pupil_ids: list[int] | None = None,
                   body: str | None = None):
    """E-mail the contacts of pupils whose homework is Missing (or *pupil_ids*).
    Returns the email_outbox ``SendResult`` (run delivery next)."""
    t = get(task_id)
    _require_owner(actor, t, "homework.notify")
    missing = [w.pupil_id for w in list_work(t.task_id) if w.status == "Missing"]
    ids = [int(p) for p in pupil_ids] if pupil_ids is not None else missing
    if not ids:
        raise ValidationError(["Nobody's homework is missing"])
    not_missing = set(ids) - set(missing)
    if not_missing:
        raise ValidationError([f"{len(not_missing)} of the chosen pupil(s) aren't marked "
                               "Missing"])
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    result = E.send_message(f"Homework not handed in: {t.subject_name} - {t.title}",
                            body or email_body(t), E.Audience(kind="pupils", pupil_ids=ids),
                            actor=actor)
    with database.connect() as conn:
        _audit(conn, "notify", actor, task_id=t.task_id,
               detail={"pupils": len(ids), "message_id": result.message_id})
    return result


def export_marks(task_id: int, path: str | Path, *, actor: Principal) -> int:
    """The class's marks as CSV. Returns the number of pupils."""
    t = get(task_id)
    _require_staff(actor, "homework.export", f"homework:{t.task_id}")
    rows = list_work(t.task_id)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Admission no", "Pupil", "Form", "Status", "Handed in", "Late", "Mark",
                    "Out of", "%", "Grade", "Feedback"])
        for r in rows:
            w.writerow([_safe(x) for x in (
                r.admission_no, r.pupil_name, r.form_group, r.status, r.handed_in,
                "Yes" if r.late else "", r.mark, t.points, r.mark_pct, r.grade, r.feedback)])
    activity_log.record("homework.export", target=f"homework:{t.task_id}", principal=actor,
                        rows=len(rows))
    return len(rows)


def as_text(task_id: int) -> str:
    t = get(task_id)
    lines = [t.title, "=" * min(len(t.title), 70),
             f"{t.subject_name} · {t.for_label} · set {t.set_date} · due {t.due_date}",
             f"Set by: {t.set_by_name or '-'}    Status: {t.status}"
             + (f"    Points: {t.points}" if t.points else "")
             + (f"    About {t.est_minutes} min" if t.est_minutes else "")]
    for label, value in (("Instructions", t.instructions), ("Resources", t.resources),
                         ("Notes", t.notes)):
        if value:
            lines += ["", label, "-" * len(label), value]
    return "\n".join(lines) + "\n"


S.register_usage("homework_tasks", "subject_id", "homework task(s)")
