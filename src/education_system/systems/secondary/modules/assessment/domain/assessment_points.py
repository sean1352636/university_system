"""Assessment points: the school's termly data drops.

There was no assessment-points screen in the old system (only the menu entry),
so this is new.

**A point** ("Autumn data drop") covers some year groups in one school year. It
says which grade scale each key stage uses (KS3 steps or GCSE 9-1), what
teachers record (working-at grade always; predicted grade, attitude to
learning, homework and a comment if switched on), when it opens and the
deadline. It goes Draft -> Open -> Closed -> Published.

**Grades.** While a point is open, each teacher fills in a sheet for each
teaching group they teach in those years: one row per pupil. The grades must
be on the point's scale for that year. A sheet can be pre-filled from the
pupil's latest gradebook grade. The data manager
(:data:`ASSESSMENT_POINT_EDITORS`) can enter or correct any sheet until the
point is published; published grades are fixed (it can be unpublished).

**Reports.** Completion by group and teacher (and e-mailing teachers who
haven't finished), grade spread by subject, progress against an earlier point
(up / same / down), pupils with poor attitude in several subjects, one pupil's
grades across subjects, and CSV export / import.

Every change goes in ``assessment_point_audit`` and the activity log.
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import ASSESSMENT_POINT_EDITORS, Principal
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

#: Grade scales, best first.
SCALES: dict[str, tuple[str, ...]] = {
    "GCSE 9-1": ("9", "8", "7", "6", "5", "4", "3", "2", "1", "U"),
    "KS3 steps": ("Mastering", "Secure", "Developing", "Emerging"),
}
ATTITUDE = {1: "Excellent", 2: "Good", 3: "Requires improvement", 4: "Cause for concern"}
STATUSES: tuple[str, ...] = ("Draft", "Open", "Closed", "Published")
_MOVES = {("Draft", "Open"), ("Open", "Closed"), ("Closed", "Open"), ("Closed", "Published"),
          ("Published", "Closed"), ("Open", "Draft")}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS assessment_points (
    point_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    academic_year      TEXT NOT NULL,
    name               TEXT NOT NULL,
    year_groups        TEXT NOT NULL,
    ks3_scale          TEXT NOT NULL DEFAULT 'KS3 steps',
    ks4_scale          TEXT NOT NULL DEFAULT 'GCSE 9-1',
    collect_predicted  INTEGER NOT NULL DEFAULT 1,
    collect_attitude   INTEGER NOT NULL DEFAULT 1,
    collect_homework   INTEGER NOT NULL DEFAULT 0,
    collect_comment    INTEGER NOT NULL DEFAULT 0,
    opens_on           TEXT,
    deadline           TEXT,
    status             TEXT NOT NULL DEFAULT 'Draft'
                       CHECK (status IN ('Draft', 'Open', 'Closed', 'Published')),
    notes              TEXT,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    created_by         TEXT,
    updated_at         TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by         TEXT,
    UNIQUE (academic_year, name)
);
CREATE TABLE IF NOT EXISTS assessment_point_grades (
    grade_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    point_id    INTEGER NOT NULL REFERENCES assessment_points (point_id) ON DELETE CASCADE,
    pupil_id    INTEGER NOT NULL REFERENCES pupils (pupil_id),
    subject_id  INTEGER NOT NULL REFERENCES subjects (subject_id),
    group_id    INTEGER REFERENCES teaching_groups (group_id) ON DELETE SET NULL,
    group_code  TEXT,
    working_at  TEXT,
    predicted   TEXT,
    attitude    INTEGER CHECK (attitude BETWEEN 1 AND 4),
    homework    INTEGER CHECK (homework BETWEEN 1 AND 4),
    comment     TEXT,
    entered_by  TEXT,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (point_id, pupil_id, subject_id)
);
CREATE INDEX IF NOT EXISTS ix_apg_pupil ON assessment_point_grades (pupil_id);
CREATE TABLE IF NOT EXISTS assessment_point_audit (
    audit_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    point_id  INTEGER,
    action    TEXT NOT NULL CHECK (action IN ('create', 'update', 'status', 'delete', 'grades',
                                              'import', 'chase')),
    actor     TEXT NOT NULL,
    detail    TEXT,
    at        TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

database.register_schema("assessment_points", _SCHEMA)

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound


# ── Records ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Point:
    point_id: int
    academic_year: str
    name: str
    year_groups: str
    ks3_scale: str
    ks4_scale: str
    collect_predicted: bool
    collect_attitude: bool
    collect_homework: bool
    collect_comment: bool
    opens_on: str | None
    deadline: str | None
    status: str
    notes: str | None
    created_at: str
    created_by: str | None
    updated_at: str
    updated_by: str | None

    @property
    def years(self) -> tuple[int, ...]:
        return tuple(int(y) for y in self.year_groups.split(",") if y)

    @property
    def years_label(self) -> str:
        return ", ".join(map(str, self.years))

    def scale_for(self, year_group: int) -> tuple[str, ...]:
        return SCALES[self.ks4_scale if year_group >= 10 else self.ks3_scale]

    @property
    def overdue(self) -> bool:
        return self.status == "Open" and bool(self.deadline) and \
            self.deadline < _today().isoformat()  # type: ignore[operator]


@dataclass(frozen=True)
class Grade:
    grade_id: int
    point_id: int
    pupil_id: int
    subject_id: int
    group_id: int | None
    group_code: str | None
    working_at: str | None
    predicted: str | None
    attitude: int | None
    homework: int | None
    comment: str | None
    entered_by: str | None
    updated_at: str
    subject_code: str = ""
    pupil_name: str = ""
    admission_no: str = ""
    year_group: int = 0
    form_group: str | None = None


_G_SELECT = """
SELECT g.*, s.code AS subject_code, p.legal_last_name, p.legal_first_name, p.preferred_name,
       p.admission_no, p.year_group, p.form_group
FROM assessment_point_grades g JOIN subjects s USING (subject_id) JOIN pupils p USING (pupil_id)
"""
_G_BASE = ("grade_id", "point_id", "pupil_id", "subject_id", "group_id", "group_code",
           "working_at", "predicted", "attitude", "homework", "comment", "entered_by",
           "updated_at")
_FLAGS = ("collect_predicted", "collect_attitude", "collect_homework", "collect_comment")


def _point(r) -> Point:
    d = {k: r[k] for k in Point.__dataclass_fields__}
    for k in _FLAGS:
        d[k] = bool(d[k])
    return Point(**d)


def _grade(r) -> Grade:
    return Grade(**{k: r[k] for k in _G_BASE}, subject_code=r["subject_code"],
                 pupil_name=f"{r['legal_last_name']}, "
                            f"{r['preferred_name'] or r['legal_first_name']}",
                 admission_no=r["admission_no"], year_group=r["year_group"],
                 form_group=r["form_group"])


# ── Helpers ──────────────────────────────────────────────────────────

def _same(a: str | None, b: str | None) -> bool:
    return bool(a) and bool(b) and a.strip().lower() == b.strip().lower()  # type: ignore[union-attr]


def is_editor(actor: Principal) -> bool:
    return actor.role in ASSESSMENT_POINT_EDITORS


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        activity_log.record(action, target=target, outcome="denied", principal=actor)
        raise PermissionDenied("Only the data manager can set up or change assessment points.")


def _audit(conn, action: str, actor: Principal, point_id: int | None,
           detail: dict | None = None) -> None:
    conn.execute("INSERT INTO assessment_point_audit (point_id, action, actor, detail) VALUES "
                 "(?, ?, ?, ?)", (point_id, action, actor.username or "unknown",
                                  json.dumps(detail, default=str, sort_keys=True)
                                  if detail else None))


def _date(value: Any, label: str, problems: list[str]) -> _dt.date | None:
    if value in (None, ""):
        return None
    if isinstance(value, _dt.date):
        return value
    try:
        return _dt.date.fromisoformat(str(value).strip())
    except ValueError:
        problems.append(f"{label} must be a date (YYYY-MM-DD)")
        return None


def _flag(v: Any) -> int:
    if isinstance(v, bool):
        return int(v)
    return int(str(v or "").strip().lower() in {"1", "true", "yes", "y"})


def rank(scale: tuple[str, ...], grade: str | None) -> int | None:
    """Higher = better; None if not on the scale."""
    if grade is None or grade not in scale:
        return None
    return len(scale) - scale.index(grade)


# ── Points ───────────────────────────────────────────────────────────

def get_point(point_id: int) -> Point:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM assessment_points WHERE point_id = ?",
                         (int(point_id),)).fetchone()
    if r is None:
        raise NotFound(f"No assessment point #{point_id}")
    return _point(r)


def list_points(*, academic_year: str | None = None, status: str | None = None
                ) -> list[Point]:
    sql, where, params = "SELECT * FROM assessment_points", [], []
    if academic_year:
        where.append("academic_year = ?")
        params.append(academic_year)
    if status:
        where.append("status = ?")
        params.append(status)
    if where:
        sql += " WHERE " + " AND ".join(where)
    with database.connect() as conn:
        return [_point(r) for r in conn.execute(
            sql + " ORDER BY academic_year DESC, COALESCE(deadline, opens_on, created_at) DESC, "
                  "point_id DESC", params)]


EDITABLE_FIELDS = ("name", "year_groups", "ks3_scale", "ks4_scale", *_FLAGS, "opens_on",
                   "deadline", "notes")


def _clean(data: dict[str, Any], current: Point | None) -> dict[str, Any]:
    problems: list[str] = []
    unknown = set(data) - set(EDITABLE_FIELDS) - {"academic_year"}
    if unknown:
        problems.append(f"Unknown field(s): {', '.join(sorted(unknown))}")
    merged = {k: getattr(current, k) for k in EDITABLE_FIELDS} if current else {}
    merged.update(data)
    out: dict[str, Any] = {}
    out["name"] = P._clean_text(merged.get("name"), 60)
    if not out["name"]:
        problems.append("Give the point a name (e.g. Autumn data drop)")
    years = merged.get("year_groups")
    if isinstance(years, (list, tuple, set)):
        years = ",".join(str(y) for y in years)
    ys: list[int] = []
    for part in str(years or "").replace(" ", ",").split(","):
        if not part:
            continue
        if not part.isdigit() or int(part) not in P.YEAR_GROUPS:
            problems.append("Year groups must be from 7 to 11")
            break
        if int(part) not in ys:
            ys.append(int(part))
    if not ys:
        problems.append("Choose at least one year group")
    out["year_groups"] = ",".join(map(str, sorted(ys)))
    for key, label in (("ks3_scale", "KS3 scale"), ("ks4_scale", "KS4 scale")):
        v = merged.get(key) or ("KS3 steps" if key == "ks3_scale" else "GCSE 9-1")
        if v not in SCALES:
            problems.append(f"{label} must be one of {', '.join(SCALES)}")
        out[key] = v
    for k in _FLAGS:
        out[k] = _flag(merged.get(k, 1 if k in ("collect_predicted", "collect_attitude")
                                  else 0))
    o = _date(merged.get("opens_on"), "Opens on", problems)
    d = _date(merged.get("deadline"), "Deadline", problems)
    if o and d and d < o:
        problems.append("The deadline can't be before it opens")
    out["opens_on"], out["deadline"] = (o.isoformat() if o else None,
                                        d.isoformat() if d else None)
    out["notes"] = P._clean_text(merged.get("notes"), 2000)
    if problems:
        raise ValidationError(problems)
    return out


def create_point(data: dict[str, Any], *, actor: Principal) -> Point:
    _require_editor(actor, "points.create")
    clean = _clean(data, None)
    year = P._clean_text(data.get("academic_year"), 7) or TG.current_year(_today())
    with database.connect() as conn:
        if conn.execute("SELECT 1 FROM assessment_points WHERE academic_year = ? AND name = ? "
                        "COLLATE NOCASE", (year, clean["name"])).fetchone():
            raise ValidationError([f"{year} already has a point called '{clean['name']}'"])
        cols = list(clean)
        pid = conn.execute(
            f"INSERT INTO assessment_points (academic_year, {', '.join(cols)}, created_by, "  # nosec B608 - columns from _clean
            f"updated_by) VALUES (?, {', '.join('?' * len(cols))}, ?, ?)",
            (year, *clean.values(), actor.username, actor.username)).lastrowid
        _audit(conn, "create", actor, pid)
    activity_log.record("points.create", target=f"point:{pid}", principal=actor)
    return get_point(pid)


def update_point(point_id: int, changes: dict[str, Any], *, actor: Principal) -> Point:
    pt = get_point(point_id)
    _require_editor(actor, "points.update", f"point:{pt.point_id}")
    if pt.status == "Published":
        raise ValidationError([f"'{pt.name}' is published - unpublish it first"])
    clean = _clean(changes, pt)
    diff = {k: v for k, v in clean.items()
            if getattr(pt, k) != (bool(v) if k in _FLAGS else v)}
    if not diff:
        return pt
    with database.connect() as conn:
        n = conn.execute("SELECT COUNT(*) FROM assessment_point_grades WHERE point_id = ?",
                         (pt.point_id,)).fetchone()[0]
        if n and ({"ks3_scale", "ks4_scale"} & set(diff)):
            raise ValidationError([f"{n} grade(s) are already in - the scales can't change"])
        if n and "year_groups" in diff:
            dropped = set(pt.years) - {int(y) for y in clean["year_groups"].split(",")}
            used = {r[0] for r in conn.execute(
                "SELECT DISTINCT p.year_group FROM assessment_point_grades g JOIN pupils p "
                "USING (pupil_id) WHERE g.point_id = ?", (pt.point_id,))}
            if dropped & used:
                raise ValidationError([f"Year {', '.join(map(str, sorted(dropped & used)))} "
                                       "already has grades - it can't be removed"])
        if "name" in diff and conn.execute(
                "SELECT 1 FROM assessment_points WHERE academic_year = ? AND name = ? COLLATE "
                "NOCASE AND point_id != ?", (pt.academic_year, clean["name"], pt.point_id)
        ).fetchone():
            raise ValidationError([f"{pt.academic_year} already has a point called "
                                   f"'{clean['name']}'"])
        sets = ", ".join(f"{k} = ?" for k in diff)
        conn.execute(f"UPDATE assessment_points SET {sets}, updated_at = datetime('now'), "  # nosec B608 - keys from _clean
                     "updated_by = ? WHERE point_id = ?",
                     (*diff.values(), actor.username, pt.point_id))
        _audit(conn, "update", actor, pt.point_id, {"fields": sorted(diff)})
    activity_log.record("points.update", target=f"point:{pt.point_id}", principal=actor)
    return get_point(pt.point_id)


def set_status(point_id: int, status: str, *, actor: Principal) -> Point:
    pt = get_point(point_id)
    _require_editor(actor, "points.status", f"point:{pt.point_id}")
    status = str(status or "").strip().title()
    if status == pt.status:
        return pt
    if (pt.status, status) not in _MOVES:
        raise ValidationError([f"A {pt.status.lower()} point can't go to {status}"])
    if pt.status == "Open" and status == "Draft" and grades(pt.point_id):
        raise ValidationError(["Grades are already in - close it instead"])
    if status == "Open" and pt.academic_year != TG.current_year(_today()):
        raise ValidationError([f"'{pt.name}' is for {pt.academic_year} - only this year's "
                               "points can open"])
    with database.connect() as conn:
        conn.execute("UPDATE assessment_points SET status = ?, updated_at = datetime('now'), "
                     "updated_by = ? WHERE point_id = ?", (status, actor.username, pt.point_id))
        _audit(conn, "status", actor, pt.point_id, {"from": pt.status, "to": status})
    activity_log.record("points.status", target=f"point:{pt.point_id}", principal=actor,
                        status=status)
    return get_point(pt.point_id)


def delete_point(point_id: int, *, actor: Principal) -> Point:
    pt = get_point(point_id)
    _require_editor(actor, "points.delete", f"point:{pt.point_id}")
    if pt.status == "Published":
        raise ValidationError([f"'{pt.name}' is published - unpublish it first"])
    with database.connect() as conn:
        conn.execute("DELETE FROM assessment_points WHERE point_id = ?", (pt.point_id,))
        _audit(conn, "delete", actor, pt.point_id, {"name": pt.name})
    activity_log.record("points.delete", target=f"point:{pt.point_id}", principal=actor)
    return pt


def history(point_id: int, *, limit: int = 300) -> list[dict[str, Any]]:
    with database.connect() as conn:
        return [{"at": r["at"], "actor": r["actor"], "action": r["action"],
                 "detail": json.loads(r["detail"] or "{}")}
                for r in conn.execute("SELECT * FROM assessment_point_audit WHERE point_id = ? "
                                      "ORDER BY audit_id DESC LIMIT ?",
                                      (int(point_id), int(limit)))]


# ── Who enters what ──────────────────────────────────────────────────

def groups_for(pt: Point, *, teacher: str | None = None) -> list[TG.TeachingGroup]:
    """Teaching groups the point covers (this point's year, its year groups)."""
    out = []
    for y in pt.years:
        out += [g for g in TG.list_groups(academic_year=pt.academic_year, year_group=y,
                                          teacher=teacher) if g.is_active]
    return sorted(out, key=lambda g: (g.year_group, g.code.lower()))


def can_enter(actor: Principal, pt: Point, group: TG.TeachingGroup) -> bool:
    if is_editor(actor):
        return pt.status in ("Open", "Closed")
    return pt.status == "Open" and actor.is_staff and _same(actor.username,
                                                            group.teacher_username)


def grades(point_id: int, *, group_id: int | None = None, subject_id: int | None = None,
           pupil_id: int | None = None, year_group: int | None = None) -> list[Grade]:
    sql, where, params = _G_SELECT + " WHERE g.point_id = ?", [], [int(point_id)]
    for col, val in (("g.group_id", group_id), ("g.subject_id", subject_id),
                     ("g.pupil_id", pupil_id), ("p.year_group", year_group)):
        if val not in (None, ""):
            where.append(f"{col} = ?")
            params.append(val)
    if where:
        sql += " AND " + " AND ".join(where)
    with database.connect() as conn:
        return [_grade(r) for r in conn.execute(
            sql + " ORDER BY s.code, p.legal_last_name COLLATE NOCASE, p.legal_first_name "
                  "COLLATE NOCASE", params)]


def sheet(point_id: int, group_id: int) -> list[tuple[P.Pupil, Grade | None]]:
    """The group's pupils with their grade so far."""
    pt = get_point(point_id)
    g = TG.get(group_id)
    if g.year_group not in pt.years or g.academic_year != pt.academic_year:
        raise ValidationError([f"{g.code} isn't covered by '{pt.name}'"])
    have = {x.pupil_id: x for x in grades(pt.point_id, subject_id=g.subject_id)}
    return [(p, have.get(p.pupil_id)) for p in TG.members(g.group_id)]


def _clean_row(pt: Point, pupil: P.Pupil, data: dict[str, Any], problems: list[str]
               ) -> dict[str, Any] | None:
    scale = pt.scale_for(pupil.year_group)
    who = pupil.display_name
    n = len(problems)
    out: dict[str, Any] = {}

    def grade(key: str, label: str) -> str | None:
        v = P._clean_text(data.get(key), 20)
        if not v:
            return None
        match = next((s for s in scale if s.lower() == v.lower()), None)
        if match is None:
            problems.append(f"{who}: {label} '{v}' isn't on the {', '.join(scale)} scale")
        return match
    out["working_at"] = grade("working_at", "working-at grade")
    out["predicted"] = grade("predicted", "predicted grade") if pt.collect_predicted else None
    for key, on, label in (("attitude", pt.collect_attitude, "attitude"),
                           ("homework", pt.collect_homework, "homework")):
        v = data.get(key)
        out[key] = None
        if on and v not in (None, ""):
            try:
                out[key] = int(str(v).strip())
            except ValueError:
                out[key] = 0
            if out[key] not in ATTITUDE:
                problems.append(f"{who}: {label} must be 1 (excellent) to 4 (cause for concern)")
    out["comment"] = P._clean_text(data.get("comment"), 600) if pt.collect_comment else None
    return out if len(problems) == n else None


def save_sheet(point_id: int, group_id: int, rows: dict[int, dict[str, Any]], *,
               actor: Principal) -> int:
    """Save a group's grades: {pupil_id: {working_at, predicted, attitude,
    homework, comment}}. A row left completely blank removes that pupil's grade.
    All or nothing. Returns how many rows were saved or cleared."""
    pt = get_point(point_id)
    g = TG.get(group_id)
    if not can_enter(actor, pt, g):
        activity_log.record("points.grades", target=f"point:{pt.point_id}", outcome="denied",
                            principal=actor)
        if pt.status in ("Draft", "Published") or (pt.status == "Closed"
                                                   and not is_editor(actor)):
            raise PermissionDenied(f"'{pt.name}' is {pt.status.lower()} - grades can only be "
                                   "entered while it's open")
        raise PermissionDenied(f"Only {g.code}'s teacher (or the data manager) can enter its "
                               "grades")
    members = {p.pupil_id: p for p, _g in sheet(pt.point_id, g.group_id)}
    problems: list[str] = []
    clean: list[tuple[int, dict[str, Any] | None]] = []
    for pid, data in rows.items():
        p = members.get(int(pid))
        if p is None:
            problems.append(f"Pupil #{pid} isn't in {g.code}")
            continue
        c = _clean_row(pt, p, data, problems)
        if c is None:
            continue
        clean.append((p.pupil_id, c if any(v not in (None, "") for v in c.values()) else None))
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        for pid, c in clean:
            if c is None:
                conn.execute("DELETE FROM assessment_point_grades WHERE point_id = ? AND "
                             "pupil_id = ? AND subject_id = ?",
                             (pt.point_id, pid, g.subject_id))
                continue
            conn.execute(
                "INSERT INTO assessment_point_grades (point_id, pupil_id, subject_id, group_id, "
                "group_code, working_at, predicted, attitude, homework, comment, entered_by) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (point_id, pupil_id, "
                "subject_id) DO UPDATE SET group_id = excluded.group_id, group_code = "
                "excluded.group_code, working_at = excluded.working_at, predicted = "
                "excluded.predicted, attitude = excluded.attitude, homework = excluded.homework, "
                "comment = excluded.comment, entered_by = excluded.entered_by, "
                "updated_at = datetime('now')",
                (pt.point_id, pid, g.subject_id, g.group_id, g.code, c["working_at"],
                 c["predicted"], c["attitude"], c["homework"], c["comment"], actor.username))
        _audit(conn, "grades", actor, pt.point_id, {"group": g.code, "rows": len(clean)})
    activity_log.record("points.grades", target=f"point:{pt.point_id}", principal=actor,
                        rows=len(clean))
    return len(clean)


def from_gradebook(point_id: int, group_id: int) -> dict[int, str]:
    """Suggested working-at grades: each pupil's latest gradebook grade in the
    subject this year, where it's on the point's scale (or the start of one
    grade on it, as the gradebook keeps short grades)."""
    from education_system.systems.secondary.modules.assessment.domain import gradebook as GB
    pt = get_point(point_id)
    g = TG.get(group_id)
    scale = pt.scale_for(g.year_group)
    out = {}
    for p, _x in sheet(pt.point_id, g.group_id):
        s = GB.pupil_subject_summary(p.pupil_id, g.subject_id,
                                     academic_year=pt.academic_year)
        got = (s["latest_grade"] or "").strip().lower()
        # Gradebook grades are short ("Sec" for Secure): a unique prefix counts.
        hits = [x for x in scale if x.lower() == got] or \
            [x for x in scale if got and x.lower().startswith(got)]
        if len(hits) == 1:
            out[p.pupil_id] = hits[0]
    return out


# ── Reports ──────────────────────────────────────────────────────────

def completion(point_id: int, *, teacher: str | None = None) -> list[dict[str, Any]]:
    """Per group: pupils, how many have a working-at grade, %."""
    pt = get_point(point_id)
    done = Counter((x.subject_id, x.pupil_id) for x in grades(pt.point_id) if x.working_at)
    out = []
    for g in groups_for(pt, teacher=teacher):
        pupils = TG.members(g.group_id)
        n = sum(1 for p in pupils if done[(g.subject_id, p.pupil_id)])
        out.append({"group": g, "subject_code": S.get(g.subject_id).code,
                    "pupils": len(pupils), "done": n,
                    "pct": round(n * 100 / len(pupils)) if pupils else 100})
    return out


def summary(point_id: int) -> dict[str, Any]:
    rows = completion(point_id)
    total = sum(r["pupils"] for r in rows)
    done = sum(r["done"] for r in rows)
    return {"groups": len(rows), "complete": sum(1 for r in rows if r["done"] >= r["pupils"]),
            "pupils": total, "done": done,
            "pct": round(done * 100 / total) if total else None}


def chase(point_id: int, *, actor: Principal) -> dict[str, Any]:
    """E-mail each teacher with unfinished groups. Returns {'sent': [ids],
    'no_email': [teacher names]}."""
    pt = get_point(point_id)
    _require_editor(actor, "points.chase", f"point:{pt.point_id}")
    if pt.status != "Open":
        raise ValidationError([f"'{pt.name}' isn't open"])
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    todo: dict[tuple[str, str], list[str]] = {}
    for r in completion(pt.point_id):
        if r["done"] < r["pupils"]:
            g = r["group"]
            key = (g.teacher_email or "", g.teacher_name or g.code)
            todo.setdefault(key, []).append(f"{g.code} ({r['done']}/{r['pupils']})")
    if not todo:
        raise ValidationError(["Every group is complete"])
    sent, no_email = [], []
    for (email, name), groups_ in todo.items():
        if not email:
            no_email.append(name)
            continue
        body = (f"Dear {name},\n\nThe {pt.name} grades are still needed for: "
                + ", ".join(groups_)
                + (f".\n\nThe deadline is {pt.deadline}." if pt.deadline else ".")
                + "\n\nPlease enter them under Assessment Points.\n\nThank you")
        sent.append(E.send_to_address(email, name, f"{pt.name}: grades needed", body,
                                      actor=actor, kind="assessment_point_chase",
                                      label=pt.name))
    with database.connect() as conn:
        _audit(conn, "chase", actor, pt.point_id, {"sent": len(sent)})
    return {"sent": sent, "no_email": no_email}


def distribution(point_id: int, *, year_group: int | None = None) -> dict[str, Any]:
    """Working-at grades by subject: {subject_code: {grade: n}} in scale order,
    plus attitude counts."""
    pt = get_point(point_id)
    rows = grades(pt.point_id, year_group=year_group)
    out: dict[str, dict[str, int]] = {}
    for x in rows:
        if x.working_at:
            out.setdefault(x.subject_code, Counter())[x.working_at] += 1  # type: ignore[index]
    order = {g: i for scale in SCALES.values() for i, g in enumerate(scale)}
    return {"subjects": {s: dict(sorted(c.items(), key=lambda kv: order.get(kv[0], 99)))
                         for s, c in sorted(out.items())},
            "attitude": {ATTITUDE[k]: v for k, v in sorted(Counter(
                x.attitude for x in rows if x.attitude).items())}}


def progress(point_id: int, earlier_id: int, *, year_group: int | None = None
             ) -> dict[str, Any]:
    """Working-at now vs an earlier point, per pupil and subject (same scale only)."""
    pt, before = get_point(point_id), get_point(earlier_id)
    old = {(x.pupil_id, x.subject_id): x for x in grades(before.point_id) if x.working_at}
    counts = Counter()
    down = []
    for x in grades(pt.point_id, year_group=year_group):
        o = old.get((x.pupil_id, x.subject_id))
        if not x.working_at or o is None:
            continue
        scale_now = pt.scale_for(x.year_group)
        a, b = rank(scale_now, o.working_at), rank(scale_now, x.working_at)
        if a is None or b is None:
            counts["different scale"] += 1
            continue
        move = "up" if b > a else "down" if b < a else "same"
        counts[move] += 1
        if move == "down":
            down.append({"pupil_name": x.pupil_name, "pupil_id": x.pupil_id,
                         "subject_code": x.subject_code, "before": o.working_at,
                         "now": x.working_at, "year": x.year_group})
    return {"up": counts["up"], "same": counts["same"], "down": counts["down"],
            "different_scale": counts["different scale"], "declines": down}


def attitude_concerns(point_id: int, *, min_subjects: int = 2, worst: int = 3
                      ) -> list[dict[str, Any]]:
    """Pupils with attitude *worst* or below (3 or 4) in at least *min_subjects*."""
    by: dict[int, list[Grade]] = {}
    for x in grades(point_id):
        if x.attitude and x.attitude >= worst:
            by.setdefault(x.pupil_id, []).append(x)
    out = [{"pupil_id": pid, "pupil_name": xs[0].pupil_name, "admission_no": xs[0].admission_no,
            "year": xs[0].year_group, "form": xs[0].form_group,
            "subjects": ", ".join(f"{x.subject_code} ({x.attitude})" for x in xs),
            "count": len(xs)} for pid, xs in by.items() if len(xs) >= min_subjects]
    return sorted(out, key=lambda d: (-d["count"], d["pupil_name"]))


def pupil_report(point_id: int, pupil_id: int) -> list[Grade]:
    return grades(point_id, pupil_id=pupil_id)


def for_pupil(pupil_id: int) -> tuple[Point, list[Grade]] | None:
    """The newest point with grades for the pupil (published first), for the
    profile."""
    with database.connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT a.point_id FROM assessment_point_grades g JOIN assessment_points a "
            "USING (point_id) WHERE g.pupil_id = ? ORDER BY a.status = 'Published' DESC, "
            "a.academic_year DESC, a.point_id DESC LIMIT 1", (int(pupil_id),)).fetchall()
    if not rows:
        return None
    pt = get_point(rows[0][0])
    return pt, pupil_report(pt.point_id, pupil_id)


# ── Import / export ──────────────────────────────────────────────────

def export_point(point_id: int, path: str | Path, *, actor: Principal) -> int:
    if not actor.is_staff:
        raise PermissionDenied("Only school staff can export grades.")
    pt = get_point(point_id)
    rows = grades(pt.point_id)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Admission no", "Pupil", "Year", "Form", "Subject", "Group", "Working at",
                    "Predicted", "Attitude", "Homework", "Comment"])
        for x in rows:
            w.writerow([_safe(v) for v in (x.admission_no, x.pupil_name, x.year_group,
                                           x.form_group, x.subject_code, x.group_code,
                                           x.working_at, x.predicted, x.attitude, x.homework,
                                           x.comment)])
    activity_log.record("points.export", target=f"point:{pt.point_id}", principal=actor,
                        rows=len(rows))
    return len(rows)


def import_grades(point_id: int, group_id: int, path: str | Path, *, actor: Principal
                  ) -> int:
    """CSV for one group: Admission no, Working at, and optionally Predicted,
    Attitude, Homework, Comment. All or nothing."""
    pt = get_point(point_id)
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        heads = {h.strip().lower(): h for h in (reader.fieldnames or [])}
        if "admission no" not in heads or "working at" not in heads:
            raise ValidationError(["The file needs 'Admission no' and 'Working at' columns"])
        lines = list(reader)
    keys = {"working at": "working_at", "predicted": "predicted", "attitude": "attitude",
            "homework": "homework", "comment": "comment"}
    rows: dict[int, dict[str, Any]] = {}
    problems = []
    for i, r in enumerate(lines, 2):
        adm = (r.get(heads["admission no"]) or "").strip()
        if not adm:
            continue
        p = P.find_by_reference(adm)
        if p is None:
            problems.append(f"Row {i}: no pupil {adm}")
            continue
        rows[p.pupil_id] = {k: (r.get(heads[h]) or "").strip() for h, k in keys.items()
                            if h in heads}
    if problems:
        raise ValidationError(problems)
    # Columns the file leaves out keep what's already there.
    have = {p.pupil_id: x for p, x in sheet(pt.point_id, group_id) if x}
    for pid, row in rows.items():
        x = have.get(pid)
        for k in keys.values():
            if k not in row and x is not None:
                row[k] = getattr(x, k)
    n = save_sheet(pt.point_id, group_id, rows, actor=actor)
    with database.connect() as conn:
        _audit(conn, "import", actor, pt.point_id, {"rows": n})
    return n


S.register_usage("assessment_point_grades", "subject_id", "assessment point grade(s)")
