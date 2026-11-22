"""Gradebook: assessments set to a class, each pupil's mark and grade, and
what the marks show.

**Assessments.** The old gradebook was one row per pupil mark, tagged with an
assessment name, type, term and date. Now the assessment is its own record
(subject, teaching group or year group, name, type, term, date, out-of marks,
weight) and each pupil has one mark for it, so a teacher can enter a whole
class at once and see who is still to be marked. The old single "Record /
update entry" still works: it files the mark under the matching assessment,
creating one if needed.

**Marks.** A mark can't be above the assessment's maximum; the % is worked out.
A grade can be typed, or worked out from grade boundaries (the assessment's
own, else the subject's). A pupil can be marked Absent or Excused instead.
Locking an assessment stops changes (the gradebook editor can unlock it).

**Reports.** The old pupil / subject summary and cohort assessment summary
(average, highest, lowest, grades), plus a markbook grid for a class, each
pupil's subjects, missing marks, pupils whose marks are low or falling,
and CSV export / import.

**Who.** Staff set and mark assessments for the groups they teach (and any
year-group assessment they set). :data:`GRADEBOOK_EDITORS` change anything,
unlock and set subject boundaries. All staff can view. Every change goes in
``gradebook_audit`` and the activity log.
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import re
import statistics
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import GRADEBOOK_EDITORS, Principal
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ASSESSMENT_TYPES: tuple[str, ...] = ("Test", "Quiz", "Essay", "Mock", "Coursework", "Project",
                                     "Classwork", "Homework", "Other")
TERMS: tuple[str, ...] = ("Autumn", "Spring", "Summer", "Ongoing")
MARK_STATUSES: tuple[str, ...] = ("Marked", "Absent", "Excused")
GCSE_BOUNDARIES = "9:85, 8:75, 7:65, 6:55, 5:45, 4:35, 3:25, 2:15, 1:5, U:0"
_GRADE_RE = re.compile(r"^[A-Za-z0-9*+\-]{1,3}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS gradebook_assessments (
    assessment_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id       INTEGER NOT NULL REFERENCES subjects (subject_id),
    group_id         INTEGER REFERENCES teaching_groups (group_id) ON DELETE SET NULL,
    group_code       TEXT,
    year_group       INTEGER NOT NULL CHECK (year_group BETWEEN 7 AND 11),
    academic_year    TEXT NOT NULL,
    name             TEXT NOT NULL,
    assessment_type  TEXT NOT NULL DEFAULT 'Test',
    term             TEXT NOT NULL DEFAULT 'Autumn',
    assessment_date  TEXT NOT NULL,
    max_marks        REAL,
    weight           REAL NOT NULL DEFAULT 1,
    boundaries       TEXT,
    teacher          TEXT,
    set_by           TEXT,
    status           TEXT NOT NULL DEFAULT 'Open' CHECK (status IN ('Open', 'Locked')),
    notes            TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by       TEXT
);
CREATE INDEX IF NOT EXISTS ix_gb_assess_subject ON gradebook_assessments (subject_id, year_group);
CREATE INDEX IF NOT EXISTS ix_gb_assess_group ON gradebook_assessments (group_id);
CREATE TABLE IF NOT EXISTS gradebook_marks (
    mark_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_id  INTEGER NOT NULL REFERENCES gradebook_assessments (assessment_id)
                   ON DELETE CASCADE,
    pupil_id       INTEGER NOT NULL REFERENCES pupils (pupil_id),
    status         TEXT NOT NULL DEFAULT 'Marked'
                   CHECK (status IN ('Marked', 'Absent', 'Excused')),
    marks_awarded  REAL,
    mark_pct       REAL,
    grade          TEXT,
    comments       TEXT,
    entered_by     TEXT,
    updated_at     TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (assessment_id, pupil_id)
);
CREATE INDEX IF NOT EXISTS ix_gb_marks_pupil ON gradebook_marks (pupil_id);
CREATE TABLE IF NOT EXISTS gradebook_boundaries (
    subject_id  INTEGER PRIMARY KEY REFERENCES subjects (subject_id) ON DELETE CASCADE,
    boundaries  TEXT NOT NULL,
    updated_by  TEXT,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS gradebook_audit (
    audit_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_id  INTEGER,
    pupil_id       INTEGER,
    action         TEXT NOT NULL CHECK (action IN (
        'create', 'update', 'delete', 'lock', 'unlock', 'mark', 'unmark', 'import',
        'boundaries')),
    actor          TEXT NOT NULL,
    detail         TEXT,
    at             TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

database.register_schema("gradebook", _SCHEMA)

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound


# ── Records ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Assessment:
    assessment_id: int
    subject_id: int
    group_id: int | None
    group_code: str | None
    year_group: int
    academic_year: str
    name: str
    assessment_type: str
    term: str
    assessment_date: str
    max_marks: float | None
    weight: float
    boundaries: str | None
    teacher: str | None
    set_by: str | None
    status: str
    notes: str | None
    created_at: str
    updated_at: str
    updated_by: str | None
    subject_code: str = ""
    subject_name: str = ""
    marked: int = 0

    @property
    def for_label(self) -> str:
        return self.group_code or f"Year {self.year_group}"

    @property
    def locked(self) -> bool:
        return self.status == "Locked"


@dataclass(frozen=True)
class Entry:
    """One pupil's mark (the old gradebook row)."""
    mark_id: int
    assessment_id: int
    pupil_id: int
    status: str
    marks_awarded: float | None
    mark_pct: float | None
    grade: str | None
    comments: str | None
    entered_by: str | None
    updated_at: str
    assessment_name: str = ""
    assessment_type: str = ""
    term: str = ""
    assessment_date: str = ""
    max_marks: float | None = None
    weight: float = 1.0
    subject_id: int = 0
    subject_code: str = ""
    teacher: str | None = None
    group_code: str | None = None
    pupil_name: str = ""
    admission_no: str = ""
    pupil_year: int = 0

    @property
    def marks_label(self) -> str:
        if self.status != "Marked":
            return self.status
        if self.marks_awarded is None:
            return "-"
        return (f"{self.marks_awarded:g}/{self.max_marks:g}" if self.max_marks
                else f"{self.marks_awarded:g}")


_A_SELECT = """
SELECT a.*, s.code AS subject_code, s.name AS subject_name,
       (SELECT COUNT(*) FROM gradebook_marks m WHERE m.assessment_id = a.assessment_id)
         AS marked
FROM gradebook_assessments a JOIN subjects s USING (subject_id)
"""
_E_SELECT = """
SELECT m.*, a.name AS assessment_name, a.assessment_type, a.term, a.assessment_date,
       a.max_marks, a.weight, a.subject_id, s.code AS subject_code, a.teacher, a.group_code,
       p.legal_last_name, p.legal_first_name, p.preferred_name, p.admission_no,
       p.year_group AS pupil_year
FROM gradebook_marks m JOIN gradebook_assessments a USING (assessment_id)
JOIN subjects s ON s.subject_id = a.subject_id JOIN pupils p ON p.pupil_id = m.pupil_id
"""
_E_BASE = ("mark_id", "assessment_id", "pupil_id", "status", "marks_awarded", "mark_pct",
           "grade", "comments", "entered_by", "updated_at")
_E_EXTRA = ("assessment_name", "assessment_type", "term", "assessment_date", "max_marks",
            "weight", "subject_id", "subject_code", "teacher", "group_code", "admission_no",
            "pupil_year")


def _assessment(r) -> Assessment:
    return Assessment(**{k: r[k] for k in Assessment.__dataclass_fields__})


def _entry(r) -> Entry:
    return Entry(**{k: r[k] for k in _E_BASE + _E_EXTRA},
                 pupil_name=f"{r['legal_last_name']}, "
                            f"{r['preferred_name'] or r['legal_first_name']}")


# ── Helpers ──────────────────────────────────────────────────────────

def _same(a: str | None, b: str | None) -> bool:
    return bool(a) and bool(b) and a.strip().lower() == b.strip().lower()  # type: ignore[union-attr]


def is_editor(actor: Principal) -> bool:
    return actor.role in GRADEBOOK_EDITORS


def _group_teacher(group_id: int | None) -> str | None:
    if not group_id:
        return None
    try:
        return TG.get(group_id).teacher_username
    except TG.NotFound:
        return None


def can_mark(actor: Principal, a: Assessment) -> bool:
    """The gradebook editor, whoever set it, or the group's teacher."""
    if is_editor(actor):
        return True
    if not actor.is_staff:
        return False
    return _same(actor.username, a.set_by) or _same(actor.username,
                                                    _group_teacher(a.group_id))


def _require_staff(actor: Principal, action: str) -> None:
    if not actor.is_staff:
        activity_log.record(action, outcome="denied", principal=actor)
        raise PermissionDenied("Only school staff can use the gradebook.")


def _require_marker(actor: Principal, a: Assessment, action: str) -> None:
    if not can_mark(actor, a):
        activity_log.record(action, target=f"assessment:{a.assessment_id}", outcome="denied",
                            principal=actor)
        raise PermissionDenied(f"Only the teacher who set '{a.name}', {a.for_label}'s "
                               "teacher or a head of department can change it.")


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        activity_log.record(action, target=target, outcome="denied", principal=actor)
        raise PermissionDenied("Only a head of department can do this.")


def _audit(conn, action: str, actor: Principal, *, assessment_id: int | None = None,
           pupil_id: int | None = None, detail: dict | None = None) -> None:
    conn.execute("INSERT INTO gradebook_audit (assessment_id, pupil_id, action, actor, detail) "
                 "VALUES (?, ?, ?, ?, ?)",
                 (assessment_id, pupil_id, action, actor.username or "unknown",
                  json.dumps(detail, default=str, sort_keys=True) if detail else None))


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


def _num(value: Any, label: str, problems: list[str], lo: float, hi: float) -> float | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    try:
        v = float(str(value).strip())
    except ValueError:
        problems.append(f"{label} must be a number")
        return None
    if not lo <= v <= hi:
        problems.append(f"{label} must be from {lo:g} to {hi:g}")
        return None
    return v


def term_for(day: _dt.date) -> str:
    """Autumn Sep-Dec, Spring Jan-Mar, Summer Apr-Aug (when no term is chosen)."""
    return "Autumn" if day.month >= 9 else "Spring" if day.month <= 3 else "Summer"


# ── Grade boundaries ─────────────────────────────────────────────────

def parse_boundaries(text: str | None) -> list[tuple[str, float]]:
    """'9:85, 8:75, ... U:0' -> [('9', 85.0), ...] highest first."""
    if not text or not str(text).strip():
        return []
    out, problems = [], []
    for part in re.split(r"[,;\n]+", str(text)):
        part = part.strip()
        if not part:
            continue
        grade, _sep, pct = part.partition(":")
        grade = grade.strip()
        if not _sep or not _GRADE_RE.match(grade):
            problems.append(f"'{part}' should look like 7:65 (grade:minimum %)")
            continue
        v = _num(pct, f"Boundary for {grade}", problems, 0, 100)
        if v is not None:
            out.append((grade, v))
    if len({g for g, _v in out}) != len(out):
        problems.append("A grade is listed twice in the boundaries")
    if problems:
        raise ValidationError(problems)
    return sorted(out, key=lambda t: -t[1])


def boundaries_text(pairs: list[tuple[str, float]]) -> str:
    return ", ".join(f"{g}:{v:g}" for g, v in pairs)


def grade_for(pct: float | None, pairs: list[tuple[str, float]]) -> str | None:
    if pct is None:
        return None
    return next((g for g, v in pairs if pct >= v), None)


def subject_boundaries(subject_id: int) -> str | None:
    with database.connect() as conn:
        r = conn.execute("SELECT boundaries FROM gradebook_boundaries WHERE subject_id = ?",
                         (int(subject_id),)).fetchone()
    return r[0] if r else None


def set_subject_boundaries(subject_id: int, text: str | None, *, actor: Principal) -> str | None:
    """The subject's default boundaries ('' removes them)."""
    _require_editor(actor, "gradebook.boundaries", f"subject:{subject_id}")
    subj = S.get(int(subject_id))
    pairs = parse_boundaries(text)
    with database.connect() as conn:
        if pairs:
            conn.execute("INSERT INTO gradebook_boundaries (subject_id, boundaries, updated_by) "
                         "VALUES (?, ?, ?) ON CONFLICT (subject_id) DO UPDATE SET "
                         "boundaries = excluded.boundaries, updated_by = excluded.updated_by, "
                         "updated_at = datetime('now')",
                         (subj.subject_id, boundaries_text(pairs), actor.username))
        else:
            conn.execute("DELETE FROM gradebook_boundaries WHERE subject_id = ?",
                         (subj.subject_id,))
        _audit(conn, "boundaries", actor, detail={"subject": subj.code, "set": bool(pairs)})
    activity_log.record("gradebook.boundaries", target=f"subject:{subj.subject_id}",
                        principal=actor)
    return subject_boundaries(subj.subject_id)


def boundaries_for(a: Assessment) -> list[tuple[str, float]]:
    return parse_boundaries(a.boundaries or subject_boundaries(a.subject_id))


# ── Assessments ──────────────────────────────────────────────────────

def get(assessment_id: int) -> Assessment:
    with database.connect() as conn:
        r = conn.execute(_A_SELECT + " WHERE a.assessment_id = ?", (int(assessment_id),)
                         ).fetchone()
    if r is None:
        raise NotFound(f"No assessment #{assessment_id}")
    return _assessment(r)


def list_assessments(*, subject_id: int | None = None, year_group: int | None = None,
                     group_id: int | None = None, term: str | None = None,
                     assessment_type: str | None = None, academic_year: str | None = None,
                     teacher: str | None = None, search: str | None = None
                     ) -> list[Assessment]:
    sql, where, params = _A_SELECT, [], []
    for col, val in (("a.subject_id", subject_id), ("a.year_group", year_group),
                     ("a.group_id", group_id), ("a.term", term),
                     ("a.assessment_type", assessment_type),
                     ("a.academic_year", academic_year)):
        if val not in (None, ""):
            where.append(f"{col} = ?")
            params.append(val)
    if teacher:
        where.append("(lower(a.set_by) = lower(?) OR a.group_id IN (SELECT group_id FROM "
                     "teaching_groups WHERE lower(teacher_username) = lower(?)))")
        params += [teacher, teacher]
    for word in (search or "").split():
        where.append("(a.name LIKE ? OR a.group_code LIKE ?)")
        params += [f"%{word}%"] * 2
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY a.assessment_date DESC, a.assessment_id DESC"
    with database.connect() as conn:
        return [_assessment(r) for r in conn.execute(sql, params)]


EDITABLE_FIELDS = ("subject_id", "group_id", "year_group", "name", "assessment_type", "term",
                   "assessment_date", "max_marks", "weight", "boundaries", "teacher", "notes")


def _clean(data: dict[str, Any], current: Assessment | None) -> dict[str, Any]:
    problems: list[str] = []
    unknown = set(data) - set(EDITABLE_FIELDS)
    if unknown:
        problems.append(f"Unknown field(s): {', '.join(sorted(unknown))}")
    merged = {k: getattr(current, k) for k in EDITABLE_FIELDS} if current else {}
    merged.update(data)
    out: dict[str, Any] = {}
    group = None
    gid = merged.get("group_id")
    if gid not in (None, ""):
        try:
            group = TG.get(int(gid))
        except (ValueError, TG.NotFound):
            problems.append("Choose a teaching group from the list")
    out["group_id"] = group.group_id if group else None
    out["group_code"] = group.code if group else None
    sid = merged.get("subject_id") or (group.subject_id if group else None)
    subj = None
    if sid in (None, ""):
        problems.append("Choose the subject")
    else:
        try:
            subj = S.get(int(sid))
        except (ValueError, S.NotFound):
            problems.append("Choose a subject from the list")
    if group and subj and group.subject_id != subj.subject_id:
        problems.append(f"{group.code} is a {S.get(group.subject_id).code} group, not "
                        f"{subj.code}")
    out["subject_id"] = subj.subject_id if subj else None
    year = group.year_group if group else merged.get("year_group")
    try:
        out["year_group"] = int(year)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        out["year_group"] = 0
    if out["year_group"] not in P.YEAR_GROUPS:
        problems.append("Choose a teaching group or a year group (7-11)")
    out["name"] = P._clean_text(merged.get("name"), 80)
    if not out["name"]:
        problems.append("Assessment name is required")
    atype = (P._clean_text(merged.get("assessment_type"), 20) or "Test").title()
    if atype not in ASSESSMENT_TYPES:
        problems.append(f"Type must be one of {', '.join(ASSESSMENT_TYPES)}")
    out["assessment_type"] = atype
    day = _date(merged.get("assessment_date"), "Date", problems) or _today()
    if day > _today() + _dt.timedelta(days=366):
        problems.append("The date is more than a year away")
    out["assessment_date"] = day.isoformat()
    term = (P._clean_text(merged.get("term"), 10) or term_for(day)).title()
    if term not in TERMS:
        problems.append(f"Term must be one of {', '.join(TERMS)}")
    out["term"] = term
    out["academic_year"] = TG.current_year(day)
    if group and group.academic_year != out["academic_year"]:
        problems.append(f"{group.code} is a {group.academic_year} group - the date is in "
                        f"{out['academic_year']}")
    out["max_marks"] = _num(merged.get("max_marks"), "Max marks", problems, 1, 10000)
    w = _num(merged.get("weight"), "Weight", problems, 0, 100)
    out["weight"] = 1.0 if w is None else w
    try:
        pairs = parse_boundaries(merged.get("boundaries"))
        out["boundaries"] = boundaries_text(pairs) or None
    except ValidationError as e:
        problems += e.problems
        out["boundaries"] = None
    out["teacher"] = P._clean_text(merged.get("teacher"), 100) or (
        group.teacher_name if group else None)
    out["notes"] = P._clean_text(merged.get("notes"), 2000)
    if problems:
        raise ValidationError(problems)
    return out


def create(data: dict[str, Any], *, actor: Principal) -> Assessment:
    _require_staff(actor, "gradebook.create")
    clean = _clean(data, None)
    if clean["group_id"] and not is_editor(actor) and not _same(
            actor.username, _group_teacher(clean["group_id"])):
        activity_log.record("gradebook.create", outcome="denied", principal=actor)
        raise PermissionDenied(f"You don't teach {clean['group_code']} - ask its teacher or a "
                               "head of department.")
    with database.connect() as conn:
        cols = list(clean)
        aid = conn.execute(
            f"INSERT INTO gradebook_assessments ({', '.join(cols)}, set_by, updated_by) "  # nosec B608 - columns from _clean
            f"VALUES ({', '.join('?' * len(cols))}, ?, ?)",
            (*clean.values(), actor.username, actor.username)).lastrowid
        _audit(conn, "create", actor, assessment_id=aid)
    activity_log.record("gradebook.create", target=f"assessment:{aid}", principal=actor)
    return get(aid)


def update(assessment_id: int, changes: dict[str, Any], *, actor: Principal) -> Assessment:
    """Change an assessment. A new maximum or boundaries re-work every mark's %
    and grade (grades typed by hand are kept)."""
    a = get(assessment_id)
    _require_marker(actor, a, "gradebook.update")
    if a.locked:
        raise ValidationError([f"'{a.name}' is locked - unlock it first"])
    clean = _clean(changes, a)
    diff = {k: v for k, v in clean.items() if getattr(a, k) != v}
    if not diff:
        return a
    if a.marked and ("subject_id" in diff or "group_id" in diff and clean["group_id"]):
        raise ValidationError(["Marks are already entered - the subject or group can't "
                               "change"])
    if "max_marks" in diff:
        top = max((e.marks_awarded or 0 for e in entries(a.assessment_id)), default=0)
        if clean["max_marks"] is None and a.marked:
            raise ValidationError(["Marks are already entered - keep a maximum"])
        if clean["max_marks"] is not None and top > clean["max_marks"]:
            raise ValidationError([f"A pupil already has {top:g} - the maximum can't be lower"])
    with database.connect() as conn:
        sets = ", ".join(f"{k} = ?" for k in diff)
        conn.execute(f"UPDATE gradebook_assessments SET {sets}, updated_at = datetime('now'), "  # nosec B608 - keys from _clean
                     "updated_by = ? WHERE assessment_id = ?",
                     (*diff.values(), actor.username, a.assessment_id))
        _audit(conn, "update", actor, assessment_id=a.assessment_id,
               detail={"fields": sorted(diff)})
    activity_log.record("gradebook.update", target=f"assessment:{a.assessment_id}",
                        principal=actor, fields=sorted(diff))
    if {"max_marks", "boundaries"} & set(diff):
        _rework(get(a.assessment_id), old_pairs=boundaries_for(a))
    return get(a.assessment_id)


def _rework(a: Assessment, *, old_pairs: list[tuple[str, float]]) -> None:
    """Recompute % (and grades that were worked out, not typed)."""
    pairs = boundaries_for(a)
    rows = entries(a.assessment_id)
    with database.connect() as conn:
        for e in rows:
            if e.status != "Marked" or e.marks_awarded is None:
                continue
            pct = round(100 * e.marks_awarded / a.max_marks, 2) if a.max_marks else None
            was_auto = e.grade is None or e.grade == grade_for(e.mark_pct, old_pairs)
            grade = grade_for(pct, pairs) if was_auto else e.grade
            conn.execute("UPDATE gradebook_marks SET mark_pct = ?, grade = ? WHERE mark_id = ?",
                         (pct, grade, e.mark_id))


def set_locked(assessment_id: int, locked: bool, *, actor: Principal) -> Assessment:
    a = get(assessment_id)
    if locked:
        _require_marker(actor, a, "gradebook.lock")
    else:
        _require_editor(actor, "gradebook.unlock", f"assessment:{a.assessment_id}")
    if a.locked == locked:
        return a
    with database.connect() as conn:
        conn.execute("UPDATE gradebook_assessments SET status = ?, updated_at = datetime('now'), "
                     "updated_by = ? WHERE assessment_id = ?",
                     ("Locked" if locked else "Open", actor.username, a.assessment_id))
        _audit(conn, "lock" if locked else "unlock", actor, assessment_id=a.assessment_id)
    activity_log.record("gradebook.lock" if locked else "gradebook.unlock",
                        target=f"assessment:{a.assessment_id}", principal=actor)
    return get(a.assessment_id)


def delete(assessment_id: int, *, actor: Principal) -> Assessment:
    """With no marks: whoever can mark it. With marks: a head of department."""
    a = get(assessment_id)
    _require_marker(actor, a, "gradebook.delete")
    if a.marked and not is_editor(actor):
        raise PermissionDenied(f"'{a.name}' has {a.marked} mark(s) - ask a head of department "
                               "to delete it")
    if a.locked:
        raise ValidationError([f"'{a.name}' is locked - unlock it first"])
    with database.connect() as conn:
        conn.execute("DELETE FROM gradebook_assessments WHERE assessment_id = ?",
                     (a.assessment_id,))
        _audit(conn, "delete", actor, assessment_id=a.assessment_id,
               detail={"name": a.name, "marks": a.marked})
    activity_log.record("gradebook.delete", target=f"assessment:{a.assessment_id}",
                        principal=actor)
    return a


def history(assessment_id: int, *, limit: int = 300) -> list[dict[str, Any]]:
    with database.connect() as conn:
        return [{"at": r["at"], "actor": r["actor"], "action": r["action"],
                 "pupil_id": r["pupil_id"], "detail": json.loads(r["detail"] or "{}")}
                for r in conn.execute("SELECT * FROM gradebook_audit WHERE assessment_id = ? "
                                      "ORDER BY audit_id DESC LIMIT ?",
                                      (int(assessment_id), int(limit)))]


# ── Marks ────────────────────────────────────────────────────────────

def entries(assessment_id: int) -> list[Entry]:
    with database.connect() as conn:
        return [_entry(r) for r in conn.execute(
            _E_SELECT + " WHERE m.assessment_id = ? ORDER BY p.legal_last_name COLLATE NOCASE, "
            "p.legal_first_name COLLATE NOCASE", (int(assessment_id),))]


def get_entry(mark_id: int) -> Entry:
    with database.connect() as conn:
        r = conn.execute(_E_SELECT + " WHERE m.mark_id = ?", (int(mark_id),)).fetchone()
    if r is None:
        raise NotFound(f"No gradebook entry #{mark_id}")
    return _entry(r)


def list_entries(*, pupil_id: int | None = None, subject_id: int | None = None,
                 year_group: int | None = None, term: str | None = None,
                 assessment_type: str | None = None, date_from: Any = None,
                 date_to: Any = None, academic_year: str | None = None) -> list[Entry]:
    """The old gradebook list: every pupil mark, newest first."""
    problems: list[str] = []
    df, dt_ = _date(date_from, "From date", problems), _date(date_to, "To date", problems)
    if term and term not in TERMS:
        problems.append(f"Term must be one of {', '.join(TERMS)}")
    if assessment_type and assessment_type not in ASSESSMENT_TYPES:
        problems.append(f"Type must be one of {', '.join(ASSESSMENT_TYPES)}")
    if problems:
        raise ValidationError(problems)
    sql, where, params = _E_SELECT, [], []
    for col, val in (("m.pupil_id", pupil_id), ("a.subject_id", subject_id),
                     ("p.year_group", year_group), ("a.term", term),
                     ("a.assessment_type", assessment_type),
                     ("a.academic_year", academic_year)):
        if val not in (None, ""):
            where.append(f"{col} = ?")
            params.append(val)
    if df:
        where.append("a.assessment_date >= ?")
        params.append(df.isoformat())
    if dt_:
        where.append("a.assessment_date <= ?")
        params.append(dt_.isoformat())
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY a.assessment_date DESC, m.mark_id DESC"
    with database.connect() as conn:
        return [_entry(r) for r in conn.execute(sql, params)]


def pupils_for(a: Assessment) -> list[P.Pupil]:
    """Who should have a mark: the group's pupils (or, for a year-group
    assessment, those already marked), plus anyone already marked."""
    marked = {e.pupil_id for e in entries(a.assessment_id)}
    pupils = TG.members(a.group_id) if a.group_id else []
    ids = {p.pupil_id for p in pupils}
    extra = [P.get_pupil(pid) for pid in marked - ids]
    out = pupils + [p for p in extra if p is not None]
    return sorted(out, key=lambda p: (p.legal_last_name.lower(), p.legal_first_name.lower()))


def _clean_mark(a: Assessment, pupil: P.Pupil, data: dict[str, Any],
                pairs: list[tuple[str, float]], problems: list[str]) -> dict[str, Any] | None:
    who = pupil.display_name
    status = (P._clean_text(data.get("status"), 10) or "Marked").title()
    if status not in MARK_STATUSES:
        problems.append(f"{who}: status must be Marked, Absent or Excused")
        return None
    out: dict[str, Any] = {"status": status, "comments": P._clean_text(data.get("comments"),
                                                                     1000)}
    if status != "Marked":
        out.update(marks_awarded=None, mark_pct=None, grade=None)
        return out
    n = len(problems)
    marks = _num(data.get("marks_awarded"), f"{who}: mark", problems, 0, 10000)
    if marks is not None and a.max_marks is None:
        problems.append(f"{who}: '{a.name}' has no maximum - give a grade instead")
    if marks is not None and a.max_marks is not None and marks > a.max_marks:
        problems.append(f"{who}: {marks:g} is more than the maximum ({a.max_marks:g})")
    grade = P._clean_text(data.get("grade"), 3)
    if grade and not _GRADE_RE.match(grade):
        problems.append(f"{who}: grade must be 1-3 letters, digits or * + -")
    if marks is None and not grade and len(problems) == n:
        problems.append(f"{who}: give a mark or a grade (or mark them Absent)")
    if len(problems) > n:
        return None
    pct = round(100 * marks / a.max_marks, 2) if marks is not None and a.max_marks else None
    out.update(marks_awarded=marks, mark_pct=pct, grade=grade or grade_for(pct, pairs))
    return out


def record_marks(assessment_id: int, marks: dict[int, dict[str, Any]], *,
                 actor: Principal) -> int:
    """Enter or change several pupils' marks at once: {pupil_id: {marks_awarded,
    grade, status, comments}}. All or nothing. Returns how many were saved."""
    a = get(assessment_id)
    _require_marker(actor, a, "gradebook.mark")
    if a.locked:
        raise ValidationError([f"'{a.name}' is locked - unlock it first"])
    pairs = boundaries_for(a)
    problems: list[str] = []
    rows = []
    already = {e.pupil_id for e in entries(a.assessment_id)}
    for pid, data in marks.items():
        p = P.get_pupil(int(pid))
        if p is None:
            problems.append(f"No pupil #{pid}")
            continue
        if p.year_group != a.year_group and p.pupil_id not in already:
            problems.append(f"{p.display_name} is in Year {p.year_group}, not Year "
                            f"{a.year_group}")
            continue
        clean = _clean_mark(a, p, data, pairs, problems)
        if clean:
            rows.append((p.pupil_id, clean))
    if problems:
        raise ValidationError(problems)
    if not rows:
        return 0
    with database.connect() as conn:
        for pid, c in rows:
            conn.execute(
                "INSERT INTO gradebook_marks (assessment_id, pupil_id, status, marks_awarded, "
                "mark_pct, grade, comments, entered_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (assessment_id, pupil_id) DO UPDATE SET status = excluded.status, "
                "marks_awarded = excluded.marks_awarded, mark_pct = excluded.mark_pct, "
                "grade = excluded.grade, comments = excluded.comments, "
                "entered_by = excluded.entered_by, updated_at = datetime('now')",
                (a.assessment_id, pid, c["status"], c["marks_awarded"], c["mark_pct"],
                 c["grade"], c["comments"], actor.username))
        _audit(conn, "mark", actor, assessment_id=a.assessment_id,
               pupil_id=rows[0][0] if len(rows) == 1 else None, detail={"pupils": len(rows)})
    activity_log.record("gradebook.mark", target=f"assessment:{a.assessment_id}",
                        principal=actor, pupils=len(rows))
    return len(rows)


def _find_or_create(subject_id: int, pupil: P.Pupil, name: str, day: _dt.date,
                    defaults: dict[str, Any], actor: Principal) -> Assessment:
    """The assessment the old single-entry form means: same subject, name and
    date for the pupil's group (or their year)."""
    groups = {g.group_id for g in TG.list_groups(academic_year=TG.current_year(day),
                                                 subject_id=subject_id,
                                                 year_group=pupil.year_group)
              if pupil.pupil_id in {m.pupil_id for m in TG.members(g.group_id)}}
    for a in list_assessments(subject_id=subject_id, year_group=pupil.year_group):
        if a.assessment_date == day.isoformat() and a.name.lower() == name.lower() and (
                a.group_id is None or a.group_id in groups):
            return a
    gid = next(iter(groups), None) if len(groups) == 1 else None
    if gid and not (is_editor(actor) or _same(actor.username, _group_teacher(gid))):
        gid = None
    return create({**defaults, "subject_id": subject_id, "group_id": gid,
                   "year_group": pupil.year_group, "name": name,
                   "assessment_date": day.isoformat()}, actor=actor)


def record_entry(data: dict[str, Any], *, actor: Principal) -> Entry:
    """The old 'Record / update entry': pupil, subject, assessment name, type,
    term, date, marks, max marks, grade, teacher, comments."""
    _require_staff(actor, "gradebook.mark")
    problems: list[str] = []
    ref = str(data.get("pupil") or data.get("pupil_id") or "").strip()
    p = P.find_by_reference(ref) if ref else None
    if p is None:
        problems.append("Choose the pupil (admission number or UPN)")
    sid = data.get("subject_id")
    if sid in (None, ""):
        problems.append("Choose the subject")
    name = P._clean_text(data.get("assessment_name"), 80)
    if not name:
        problems.append("Assessment name is required")
    day = _date(data.get("assessment_date"), "Date", problems) or _today()
    if problems:
        raise ValidationError(problems)
    assert p is not None and name
    a = _find_or_create(int(sid), p, name, day,  # type: ignore[arg-type]
                        {k: data.get(k) for k in ("assessment_type", "term", "max_marks",
                                                  "teacher")}, actor)
    want_max = _num(data.get("max_marks"), "Max marks", [], 1, 10000)
    if want_max is not None and want_max != a.max_marks and not a.marked:
        a = update(a.assessment_id, {"max_marks": want_max}, actor=actor)
    elif want_max is not None and a.max_marks is not None and want_max != a.max_marks:
        raise ValidationError([f"'{a.name}' is out of {a.max_marks:g} for the other pupils"])
    record_marks(a.assessment_id, {p.pupil_id: {k: data.get(k) for k in (
        "marks_awarded", "grade", "status", "comments")}}, actor=actor)
    e = next(x for x in entries(a.assessment_id) if x.pupil_id == p.pupil_id)
    return e


def delete_entry(mark_id: int, *, actor: Principal) -> Entry:
    """The old 'Delete entry'."""
    e = get_entry(mark_id)
    a = get(e.assessment_id)
    _require_marker(actor, a, "gradebook.unmark")
    if a.locked:
        raise ValidationError([f"'{a.name}' is locked - unlock it first"])
    with database.connect() as conn:
        conn.execute("DELETE FROM gradebook_marks WHERE mark_id = ?", (e.mark_id,))
        _audit(conn, "unmark", actor, assessment_id=a.assessment_id, pupil_id=e.pupil_id)
    activity_log.record("gradebook.unmark", target=f"assessment:{a.assessment_id}",
                        principal=actor)
    return e


# ── Summaries ────────────────────────────────────────────────────────

def _weighted(rows: list[Entry]) -> float | None:
    got = [(e.mark_pct, e.weight) for e in rows if e.mark_pct is not None and e.weight]
    total = sum(w for _p, w in got)
    return round(sum(p * w for p, w in got) / total, 2) if total else None


def pupil_subject_summary(pupil_id: int, subject_id: int, *,
                          academic_year: str | None = None) -> dict[str, Any]:
    """The old pupil / subject summary: entries, average % (weighted), latest
    grade, entries by term."""
    rows = list_entries(pupil_id=pupil_id, subject_id=subject_id, academic_year=academic_year)
    marked = [e for e in rows if e.status == "Marked"]
    by_term = Counter(e.term for e in rows)
    return {"pupil_id": pupil_id, "subject_id": subject_id, "count": len(rows),
            "avg_pct": _weighted(marked),
            "latest_grade": next((e.grade for e in marked if e.grade), None),
            "by_term": {t: by_term.get(t, 0) for t in TERMS},
            "absent": sum(1 for e in rows if e.status == "Absent"), "entries": rows}


def assessment_summary(assessment_id: int) -> dict[str, Any]:
    """The old cohort summary: count, average, highest, lowest, grades; plus the
    median, absences and who is still to be marked."""
    a = get(assessment_id)
    rows = entries(a.assessment_id)
    pcts = sorted(e.mark_pct for e in rows if e.mark_pct is not None)
    done = {e.pupil_id for e in rows}
    return {"assessment": a, "count": len(rows),
            "marked": sum(1 for e in rows if e.status == "Marked"),
            "absent": sum(1 for e in rows if e.status == "Absent"),
            "excused": sum(1 for e in rows if e.status == "Excused"),
            "avg_pct": round(sum(pcts) / len(pcts), 2) if pcts else None,
            "median_pct": round(statistics.median(pcts), 2) if pcts else None,
            "max_pct": pcts[-1] if pcts else None, "min_pct": pcts[0] if pcts else None,
            "grades": dict(sorted(Counter(e.grade for e in rows if e.grade).items())),
            "missing": [p for p in pupils_for(a) if p.pupil_id not in done],
            "entries": sorted(rows, key=lambda e: (-(e.mark_pct or -1), e.pupil_name))}


def markbook(*, group_id: int | None = None, subject_id: int | None = None,
             year_group: int | None = None, term: str | None = None,
             academic_year: str | None = None) -> dict[str, Any]:
    """A class grid: assessments (oldest first) x pupils, with each pupil's
    weighted average. Either a teaching group, or a subject + year."""
    if not group_id and not (subject_id and year_group):
        raise ValidationError(["Choose a teaching group, or a subject and year"])
    if group_id:
        g = TG.get(group_id)
        found = list_assessments(group_id=g.group_id, term=term,
                                 academic_year=academic_year or g.academic_year)
        pupils = TG.members(g.group_id)
    else:
        found = list_assessments(subject_id=subject_id, year_group=year_group, term=term,
                                 academic_year=academic_year or TG.current_year(_today()))
        pupils = []
    found.sort(key=lambda a: (a.assessment_date, a.assessment_id))
    cells: dict[int, dict[int, Entry]] = {}
    for a in found:
        for e in entries(a.assessment_id):
            cells.setdefault(e.pupil_id, {})[a.assessment_id] = e
    known = {p.pupil_id for p in pupils}
    pupils += [p for p in (P.get_pupil(pid) for pid in cells if pid not in known) if p]
    pupils.sort(key=lambda p: (p.legal_last_name.lower(), p.legal_first_name.lower()))
    rows = []
    for p in pupils:
        mine = cells.get(p.pupil_id, {})
        marked = [e for e in mine.values() if e.status == "Marked"]
        rows.append({"pupil": p, "cells": mine, "avg_pct": _weighted(marked),
                     "latest_grade": next((mine[a.assessment_id].grade for a in reversed(found)
                                           if a.assessment_id in mine
                                           and mine[a.assessment_id].grade), None)})
    return {"assessments": found, "rows": rows}


def pupil_overview(pupil_id: int, *, academic_year: str | None = None
                   ) -> list[dict[str, Any]]:
    """Each subject the pupil has marks in this year: average, latest grade, count."""
    year = academic_year or TG.current_year(_today())
    rows = list_entries(pupil_id=pupil_id, academic_year=year)
    out = []
    for sid in sorted({e.subject_id for e in rows}):
        mine = [e for e in rows if e.subject_id == sid]
        marked = [e for e in mine if e.status == "Marked"]
        out.append({"subject_id": sid, "subject_code": mine[0].subject_code,
                    "count": len(mine), "avg_pct": _weighted(marked),
                    "latest_grade": next((e.grade for e in marked if e.grade), None),
                    "latest": mine[0]})
    return out


def missing_marks(actor: Principal, *, everyone: bool = False) -> list[tuple[Assessment, int]]:
    """Group assessments that have happened with pupils still to be marked
    (mine, or everyone's): (assessment, how many), oldest first."""
    out = []
    for a in list_assessments(academic_year=TG.current_year(_today()),
                              teacher=None if everyone else actor.username):
        if not a.group_id or a.assessment_date > _today().isoformat() or a.locked:
            continue
        done = {e.pupil_id for e in entries(a.assessment_id)}
        n = sum(1 for p in TG.members(a.group_id) if p.pupil_id not in done)
        if n:
            out.append((a, n))
    return sorted(out, key=lambda t: (t[0].assessment_date, t[0].assessment_id))


def concerns(*, below: float = 40.0, drop: float = 15.0, year_group: int | None = None,
             subject_id: int | None = None) -> list[dict[str, Any]]:
    """Pupils whose average in a subject is below *below* %, or whose latest mark
    is *drop* points under their average before it."""
    rows = [e for e in list_entries(academic_year=TG.current_year(_today()),
                                    year_group=year_group, subject_id=subject_id)
            if e.status == "Marked" and e.mark_pct is not None]
    by: dict[tuple[int, int], list[Entry]] = {}
    for e in rows:
        by.setdefault((e.pupil_id, e.subject_id), []).append(e)
    out = []
    for (_pid, _sid), mine in by.items():
        mine.sort(key=lambda e: (e.assessment_date, e.mark_id))
        avg = _weighted(mine)
        why = []
        if avg is not None and avg < below:
            why.append(f"average {avg:g}% (below {below:g}%)")
        if len(mine) >= 2:
            before = _weighted(mine[:-1])
            last = mine[-1].mark_pct
            if before is not None and last is not None and before - last >= drop:
                why.append(f"latest {last:g}% vs {before:g}% before")
        if why:
            out.append({"pupil_name": mine[0].pupil_name, "pupil_id": mine[0].pupil_id,
                        "admission_no": mine[0].admission_no, "year": mine[0].pupil_year,
                        "subject_code": mine[0].subject_code, "avg_pct": avg,
                        "why": "; ".join(why)})
    return sorted(out, key=lambda d: (d["avg_pct"] if d["avg_pct"] is not None else 999,
                                      d["pupil_name"]))


# ── Import / export ──────────────────────────────────────────────────

def export_markbook(path: str | Path, *, actor: Principal, group_id: int | None = None,
                    subject_id: int | None = None, year_group: int | None = None,
                    term: str | None = None) -> int:
    _require_staff(actor, "gradebook.export")
    mb = markbook(group_id=group_id, subject_id=subject_id, year_group=year_group, term=term)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Admission no", "Pupil", "Form",
                    *[f"{a.name} ({a.assessment_date})" for a in mb["assessments"]],
                    "Average %", "Latest grade"])
        for r in mb["rows"]:
            p = r["pupil"]
            cells = [r["cells"].get(a.assessment_id) for a in mb["assessments"]]
            w.writerow([_safe(x) for x in (
                p.admission_no, f"{p.legal_last_name}, {p.preferred_name or p.legal_first_name}",
                p.form_group, *[(c.marks_label + (f" ({c.grade})" if c.grade else "")) if c
                                else "" for c in cells], r["avg_pct"], r["latest_grade"])])
    activity_log.record("gradebook.export", principal=actor, rows=len(mb["rows"]))
    return len(mb["rows"])


def import_marks(assessment_id: int, path: str | Path, *, actor: Principal
                 ) -> tuple[int, list[str]]:
    """CSV with Admission no, and Mark and/or Grade (optional Status, Comments).
    All or nothing. Returns (saved, notes about skipped blank rows)."""
    a = get(assessment_id)
    _require_marker(actor, a, "gradebook.import")
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        heads = {h.strip().lower(): h for h in (reader.fieldnames or [])}
        if "admission no" not in heads or not ({"mark", "grade", "status"} & set(heads)):
            raise ValidationError(["The file needs an 'Admission no' column and a 'Mark' or "
                                   "'Grade' column"])
        rows = list(reader)
    marks: dict[int, dict[str, Any]] = {}
    problems, notes = [], []

    def col(r, name):
        return (r.get(heads[name]) or "").strip() if name in heads else ""
    for i, r in enumerate(rows, 2):
        adm = col(r, "admission no")
        if not adm:
            continue
        p = P.find_by_reference(adm)
        if p is None:
            problems.append(f"Row {i}: no pupil {adm}")
            continue
        data = {"marks_awarded": col(r, "mark"), "grade": col(r, "grade"),
                "status": col(r, "status") or None, "comments": col(r, "comments") or None}
        if not (data["marks_awarded"] or data["grade"] or data["status"]):
            notes.append(f"Row {i}: {adm} left blank - skipped")
            continue
        if p.pupil_id in marks:
            problems.append(f"Row {i}: {adm} is in the file twice")
        marks[p.pupil_id] = data
    if problems:
        raise ValidationError(problems)
    n = record_marks(a.assessment_id, marks, actor=actor)
    with database.connect() as conn:
        _audit(conn, "import", actor, assessment_id=a.assessment_id, detail={"rows": n})
    return n, notes


S.register_usage("gradebook_assessments", "subject_id", "gradebook assessment(s)")
