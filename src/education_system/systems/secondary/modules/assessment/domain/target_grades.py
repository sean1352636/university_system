"""Target grades: one target per pupil per subject.

Kept from the old system: each target has a headline **target grade**, a
**minimum** ("must achieve") and an **aspirational** (stretch) grade, the
**source** it came from (CAT4, MidYIS, YELLIS, KS2, Baseline, Teacher, FFT,
Other), who set it, the date and notes. The old screens could set / update,
list (by year, pupil, subject, source), view one, show the grade distribution
and delete.

New:

* **Grades are checked against a scale.** GCSE 9-1 for every year (targets
  are usually GCSE flight paths from Year 7); Years 7-9 may use the KS3 steps
  instead; BTEC subjects use Distinction* / Distinction / Merit / Pass. The
  minimum can't be above the target, nor the aspirational below it.
* **Who.** The data manager (:data:`TARGET_GRADE_EDITORS`) sets any target,
  lowers targets (with a reason), deletes them and imports them. A teacher
  sets or raises targets for pupils in the groups they teach in that subject,
  but can't lower one. Every change is kept in ``target_grade_history``.
* **Class sheet**: set a whole teaching group's targets at once.
* **Missing targets**: pupils taught a subject this year with no target.
* **Progress against target**: the pupil's latest assessment-point grade (or
  their latest gradebook grade) against the target: above, on track, below,
  well below (two or more grades below).
* CSV export / import, and the pupil profile shows targets.
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import TARGET_GRADE_EDITORS, Principal
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

GRADE_SOURCES: tuple[str, ...] = ("CAT4", "MidYIS", "YELLIS", "KS2", "Baseline", "Teacher",
                                  "FFT", "Other")
DEFAULT_SOURCE = "Teacher"
#: Scales, best first.
SCALES: dict[str, tuple[str, ...]] = {
    "GCSE 9-1": ("9", "8", "7", "6", "5", "4", "3", "2", "1"),
    "KS3 steps": ("Mastering", "Secure", "Developing", "Emerging"),
    "BTEC": ("D*", "D", "M", "P"),
}
STATUSES: tuple[str, ...] = ("Above", "On track", "Below", "Well below", "No data",
                             "Different scale")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS target_grades (
    target_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id           INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    subject_id         INTEGER NOT NULL REFERENCES subjects (subject_id),
    target_grade       TEXT NOT NULL,
    minimum_grade      TEXT,
    aspirational_grade TEXT,
    source             TEXT NOT NULL DEFAULT 'Teacher',
    set_by             TEXT,
    set_date           TEXT NOT NULL DEFAULT (date('now')),
    notes              TEXT,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    created_by         TEXT,
    updated_at         TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by         TEXT,
    UNIQUE (pupil_id, subject_id)
);
CREATE INDEX IF NOT EXISTS ix_tg_target_subject ON target_grades (subject_id);
CREATE TABLE IF NOT EXISTS target_grade_history (
    history_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id    INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    subject_id  INTEGER NOT NULL,
    action      TEXT NOT NULL CHECK (action IN ('set', 'change', 'delete', 'import')),
    old_target  TEXT,
    new_target  TEXT,
    detail      TEXT,
    reason      TEXT,
    actor       TEXT NOT NULL,
    at          TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_tgh_pupil ON target_grade_history (pupil_id, subject_id);
"""

database.register_schema("target_grades", _SCHEMA)

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound


@dataclass(frozen=True)
class TargetGrade:
    target_id: int
    pupil_id: int
    subject_id: int
    target_grade: str
    minimum_grade: str | None
    aspirational_grade: str | None
    source: str
    set_by: str | None
    set_date: str
    notes: str | None
    created_at: str
    created_by: str | None
    updated_at: str
    updated_by: str | None
    subject_code: str = ""
    subject_name: str = ""
    pupil_name: str = ""
    admission_no: str = ""
    pupil_year: int = 0
    form_group: str | None = None


_SELECT = """
SELECT t.*, s.code AS subject_code, s.name AS subject_name, p.legal_last_name,
       p.legal_first_name, p.preferred_name, p.admission_no, p.year_group AS pupil_year,
       p.form_group
FROM target_grades t JOIN subjects s USING (subject_id) JOIN pupils p USING (pupil_id)
"""
_BASE = ("target_id", "pupil_id", "subject_id", "target_grade", "minimum_grade",
         "aspirational_grade", "source", "set_by", "set_date", "notes", "created_at",
         "created_by", "updated_at", "updated_by")
FIELDS = ("target_grade", "minimum_grade", "aspirational_grade", "source", "set_by",
          "set_date", "notes")


def _row(r) -> TargetGrade:
    return TargetGrade(**{k: r[k] for k in _BASE}, subject_code=r["subject_code"],
                       subject_name=r["subject_name"],
                       pupil_name=f"{r['legal_last_name']}, "
                                  f"{r['preferred_name'] or r['legal_first_name']}",
                       admission_no=r["admission_no"], pupil_year=r["pupil_year"],
                       form_group=r["form_group"])


# ── Helpers ──────────────────────────────────────────────────────────

def _same(a: str | None, b: str | None) -> bool:
    return bool(a) and bool(b) and a.strip().lower() == b.strip().lower()  # type: ignore[union-attr]


def is_editor(actor: Principal) -> bool:
    return actor.role in TARGET_GRADE_EDITORS


def scales_for(year_group: int, subject: S.Subject) -> tuple[str, ...]:
    """Scale names allowed for a pupil in *year_group* taking *subject*."""
    if subject.qualification == "BTEC":
        return ("BTEC",)
    return ("GCSE 9-1", "KS3 steps") if year_group <= 9 else ("GCSE 9-1",)


def scale_of(grade: str | None) -> str | None:
    for name, scale in SCALES.items():
        if grade in scale:
            return name
    return None


def rank(grade: str | None) -> int | None:
    """Higher = better within the grade's own scale."""
    name = scale_of(grade)
    if name is None:
        return None
    scale = SCALES[name]
    return len(scale) - scale.index(grade)  # type: ignore[arg-type]


def _match(value: str, scales: tuple[str, ...]) -> str | None:
    """The grade on one of *scales* that *value* names (any case; a unique
    start such as "Sec" for Secure also counts)."""
    v = value.strip().lower()
    if not v:
        return None
    every = [g for name in scales for g in SCALES[name]]
    exact = [g for g in every if g.lower() == v]
    if exact:
        return exact[0]
    starts = [g for g in every if not g[0].isdigit() and g.lower().startswith(v)]
    return starts[0] if len(starts) == 1 else None


def teaches(actor: Principal, pupil_id: int, subject_id: int) -> bool:
    """True if *actor* teaches the pupil the subject this year."""
    return any(i.group.subject_id == subject_id and _same(i.group.teacher_username,
                                                          actor.username)
               for i in TG.groups_for_pupil(pupil_id))


def can_set(actor: Principal, pupil_id: int, subject_id: int) -> bool:
    return is_editor(actor) or (actor.is_staff and teaches(actor, pupil_id, subject_id))


def _pupil(ref: Any) -> P.Pupil:
    if isinstance(ref, P.Pupil):
        return ref
    p = P.get_pupil(int(ref)) if str(ref).strip().isdigit() else None
    p = p or P.find_by_reference(str(ref or "").strip())
    if p is None:
        raise ValidationError([f"No pupil {ref}" if ref else "Choose a pupil"])
    return p


def _subject(ref: Any) -> S.Subject:
    if isinstance(ref, S.Subject):
        return ref
    s = None
    if str(ref).strip().isdigit():
        try:
            s = S.get(int(ref))
        except NotFound:
            s = None
    s = s or S.get_by_code(str(ref or "").strip())
    if s is None:
        raise ValidationError([f"No subject {ref}" if ref else "Choose a subject"])
    return s


# ── Reading ──────────────────────────────────────────────────────────

def get(target_id: int) -> TargetGrade:
    with database.connect() as conn:
        r = conn.execute(_SELECT + " WHERE t.target_id = ?", (int(target_id),)).fetchone()
    if r is None:
        raise NotFound(f"No target #{target_id}")
    return _row(r)


def get_for(pupil_id: int, subject_id: int) -> TargetGrade | None:
    with database.connect() as conn:
        r = conn.execute(_SELECT + " WHERE t.pupil_id = ? AND t.subject_id = ?",
                         (int(pupil_id), int(subject_id))).fetchone()
    return _row(r) if r else None


def list_targets(*, year_group: int | str | None = None, subject_id: int | None = None,
                 pupil: str | None = None, pupil_id: int | None = None,
                 source: str | None = None, group_id: int | None = None,
                 form_group: str | None = None) -> list[TargetGrade]:
    """The old list with its filters (year, subject, pupil, source); *pupil*
    matches a name or admission number. Pupils on roll only."""
    where, params = ["p.roll_status = 'on_roll'"], []
    if year_group not in (None, ""):
        where.append("p.year_group = ?")
        params.append(int(year_group))  # type: ignore[arg-type]
    if subject_id:
        where.append("t.subject_id = ?")
        params.append(int(subject_id))
    if pupil_id:
        where.append("t.pupil_id = ?")
        params.append(int(pupil_id))
    if source:
        if source not in GRADE_SOURCES:
            raise ValidationError([f"Source must be one of {', '.join(GRADE_SOURCES)}"])
        where.append("t.source = ?")
        params.append(source)
    if form_group:
        where.append("upper(p.form_group) = upper(?)")
        params.append(form_group.strip())
    if group_id:
        where.append("t.pupil_id IN (SELECT pupil_id FROM teaching_group_members WHERE "
                     "group_id = ?) AND t.subject_id = (SELECT subject_id FROM teaching_groups "
                     "WHERE group_id = ?)")
        params += [int(group_id), int(group_id)]
    for term in (pupil or "").split():
        where.append("(p.legal_first_name LIKE ? OR p.legal_last_name LIKE ? OR "
                     "p.preferred_name LIKE ? OR p.admission_no LIKE ? OR p.upn LIKE ?)")
        params += [f"%{term}%"] * 5
    with database.connect() as conn:
        return [_row(r) for r in conn.execute(
            _SELECT + " WHERE " + " AND ".join(where)  # nosec B608 - fixed clauses
            + " ORDER BY p.year_group, p.legal_last_name COLLATE NOCASE, "
              "p.legal_first_name COLLATE NOCASE, s.name COLLATE NOCASE", params)]


def for_pupil(pupil_id: int) -> list[TargetGrade]:
    with database.connect() as conn:
        return [_row(r) for r in conn.execute(
            _SELECT + " WHERE t.pupil_id = ? ORDER BY s.name COLLATE NOCASE",
            (int(pupil_id),))]


def history(pupil_id: int, subject_id: int | None = None) -> list[dict[str, Any]]:
    sql = ("SELECT h.*, s.code AS subject_code FROM target_grade_history h LEFT JOIN subjects s "
           "USING (subject_id) WHERE h.pupil_id = ?")
    params: list[Any] = [int(pupil_id)]
    if subject_id:
        sql += " AND h.subject_id = ?"
        params.append(int(subject_id))
    with database.connect() as conn:
        return [{"at": r["at"], "actor": r["actor"], "action": r["action"],
                 "subject_code": r["subject_code"], "old": r["old_target"],
                 "new": r["new_target"], "reason": r["reason"],
                 "detail": json.loads(r["detail"] or "{}")}
                for r in conn.execute(sql + " ORDER BY h.history_id DESC", params)]


def distribution(*, year_group: int | str | None = None, subject_id: int | None = None
                 ) -> dict[str, int]:
    """The old distribution: how many targets of each grade, best first."""
    counts = Counter(t.target_grade for t in list_targets(year_group=year_group,
                                                          subject_id=subject_id))
    return dict(sorted(counts.items(), key=lambda kv: (scale_of(kv[0]) or "~",
                                                       -(rank(kv[0]) or 0), kv[0])))


# ── Setting ──────────────────────────────────────────────────────────

def _clean(data: dict[str, Any], pupil: P.Pupil, subject: S.Subject,
           current: TargetGrade | None) -> dict[str, Any]:
    problems: list[str] = []
    merged = {k: getattr(current, k) for k in FIELDS} if current else {}
    merged.update({k: v for k, v in data.items() if k in FIELDS})
    scales = scales_for(pupil.year_group, subject)
    allowed = " / ".join(", ".join(SCALES[n]) for n in scales)
    out: dict[str, Any] = {}
    for key, label, required in (("target_grade", "Target grade", True),
                                 ("minimum_grade", "Minimum grade", False),
                                 ("aspirational_grade", "Aspirational grade", False)):
        raw = P._clean_text(merged.get(key), 20)
        if not raw:
            if required:
                problems.append(f"{label} is required")
            out[key] = None
            continue
        out[key] = _match(raw, scales)
        if out[key] is None:
            problems.append(f"{label} '{raw}' isn't a {subject.code} grade for Year "
                            f"{pupil.year_group} ({allowed})")
    t, lo, hi = out["target_grade"], out["minimum_grade"], out["aspirational_grade"]
    for other, label, bad in ((lo, "minimum", lambda a, b: a > b),
                              (hi, "aspirational", lambda a, b: a < b)):
        if t and other:
            if scale_of(t) != scale_of(other):
                problems.append(f"The {label} grade must be on the same scale as the target")
            elif bad(rank(other), rank(t)):
                problems.append(f"The {label} grade can't be "
                                + ("above" if label == "minimum" else "below") + " the target")
    src = P._clean_text(merged.get("source"), 20) or DEFAULT_SOURCE
    match = next((s for s in GRADE_SOURCES if s.lower() == src.lower()), None)
    if match is None:
        problems.append(f"Source must be one of {', '.join(GRADE_SOURCES)}")
    out["source"] = match
    out["set_by"] = P._clean_text(merged.get("set_by"), 80)
    d = merged.get("set_date")
    if d in (None, ""):
        out["set_date"] = _today().isoformat()
    else:
        try:
            when = d if isinstance(d, _dt.date) else _dt.date.fromisoformat(str(d).strip())
            if when > _today():
                problems.append("The set date can't be in the future")
            out["set_date"] = when.isoformat()
        except ValueError:
            problems.append("Set date must be a date (YYYY-MM-DD)")
    out["notes"] = P._clean_text(merged.get("notes"), 1000)
    if problems:
        raise ValidationError(problems)
    return out


def _lowered(old: TargetGrade | None, new_target: str) -> bool:
    if old is None or scale_of(old.target_grade) != scale_of(new_target):
        return False
    return (rank(new_target) or 0) < (rank(old.target_grade) or 0)


def _check(actor: Principal, pupil: P.Pupil, subject: S.Subject, old: TargetGrade | None,
           clean: dict[str, Any], reason: str | None) -> None:
    if not can_set(actor, pupil.pupil_id, subject.subject_id):
        activity_log.record("targets.set", target=f"pupil:{pupil.pupil_id}", outcome="denied",
                            principal=actor)
        raise PermissionDenied(f"Only {pupil.display_name}'s {subject.code} teacher (or the "
                               "data manager) can set this target.")
    if _lowered(old, clean["target_grade"]):
        if not is_editor(actor):
            activity_log.record("targets.lower", target=f"pupil:{pupil.pupil_id}",
                                outcome="denied", principal=actor)
            raise PermissionDenied(f"{pupil.display_name}'s {subject.code} target is "
                                   f"{old.target_grade} - only the data manager can lower "  # type: ignore[union-attr]
                                   "a target.")
        if not reason:
            raise ValidationError([f"{pupil.display_name} {subject.code}: give a reason for "
                                   f"lowering the target from {old.target_grade}"])  # type: ignore[union-attr]


def _write(conn, actor: Principal, pupil: P.Pupil, subject: S.Subject,
           old: TargetGrade | None, clean: dict[str, Any], reason: str | None,
           action: str | None = None) -> bool:
    """Insert or update one row in an open transaction. False if nothing changed."""
    if old is not None and all(getattr(old, k) == clean[k] for k in FIELDS):
        return False
    if old is None:
        cols = list(clean)
        conn.execute(
            f"INSERT INTO target_grades (pupil_id, subject_id, {', '.join(cols)}, created_by, "  # nosec B608 - columns from FIELDS
            f"updated_by) VALUES (?, ?, {', '.join('?' * len(cols))}, ?, ?)",
            (pupil.pupil_id, subject.subject_id, *clean.values(), actor.username,
             actor.username))
    else:
        conn.execute(
            "UPDATE target_grades SET " + ", ".join(f"{k} = ?" for k in clean)  # nosec B608 - FIELDS
            + ", updated_at = datetime('now'), updated_by = ? WHERE target_id = ?",
            (*clean.values(), actor.username, old.target_id))
    changed = sorted(k for k in FIELDS if old is None or getattr(old, k) != clean[k])
    conn.execute(
        "INSERT INTO target_grade_history (pupil_id, subject_id, action, old_target, "
        "new_target, detail, reason, actor) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (pupil.pupil_id, subject.subject_id, action or ("set" if old is None else "change"),
         old.target_grade if old else None, clean["target_grade"],
         json.dumps({"fields": changed, "minimum": clean["minimum_grade"],
                     "aspirational": clean["aspirational_grade"],
                     "source": clean["source"]}), reason, actor.username or "unknown"))
    return True


def upsert(data: dict[str, Any], *, actor: Principal, reason: str | None = None
           ) -> TargetGrade:
    """Set or update the (pupil, subject) target - the old "Set / update".
    *data* has ``pupil`` (id or admission number) or ``pupil_id``, ``subject_id``
    (or a code) and the target fields. A blank ``set_by`` is the signed-in user."""
    pupil = _pupil(data.get("pupil_id") or data.get("pupil"))
    subject = _subject(data.get("subject_id") or data.get("subject"))
    old = get_for(pupil.pupil_id, subject.subject_id)
    data = dict(data)
    if not P._clean_text(data.get("set_by"), 80) and old is None:
        data["set_by"] = actor.username
    clean = _clean(data, pupil, subject, old)
    reason = P._clean_text(reason, 500)
    _check(actor, pupil, subject, old, clean, reason)
    with database.connect() as conn:
        changed = _write(conn, actor, pupil, subject, old, clean, reason)
    if changed:
        activity_log.record("targets.set", target=f"pupil:{pupil.pupil_id}", principal=actor)
    rec = get_for(pupil.pupil_id, subject.subject_id)
    assert rec is not None
    return rec


def delete(target_id: int, *, actor: Principal, reason: str | None = None) -> TargetGrade:
    t = get(target_id)
    if not is_editor(actor):
        activity_log.record("targets.delete", target=f"target:{t.target_id}", outcome="denied",
                            principal=actor)
        raise PermissionDenied("Only the data manager can delete targets.")
    with database.connect() as conn:
        conn.execute("DELETE FROM target_grades WHERE target_id = ?", (t.target_id,))
        conn.execute("INSERT INTO target_grade_history (pupil_id, subject_id, action, "
                     "old_target, reason, actor) VALUES (?, ?, 'delete', ?, ?, ?)",
                     (t.pupil_id, t.subject_id, t.target_grade, P._clean_text(reason, 500),
                      actor.username or "unknown"))
    activity_log.record("targets.delete", target=f"target:{t.target_id}", principal=actor)
    return t


# ── Class sheet ──────────────────────────────────────────────────────

def class_sheet(group_id: int) -> list[tuple[P.Pupil, TargetGrade | None]]:
    g = TG.get(group_id)
    have = {t.pupil_id: t for t in list_targets(subject_id=g.subject_id)}
    return [(p, have.get(p.pupil_id)) for p in TG.members(g.group_id)]


def save_class(group_id: int, rows: dict[int, dict[str, Any]], *, actor: Principal,
               reason: str | None = None) -> int:
    """Set a group's targets at once: {pupil_id: {target_grade, minimum_grade,
    aspirational_grade, source, notes}}. Rows with no target grade are skipped
    (use Delete to remove one). All or nothing. Returns rows changed."""
    g = TG.get(group_id)
    subject = S.get(g.subject_id)
    members = {p.pupil_id: (p, t) for p, t in class_sheet(g.group_id)}
    problems: list[str] = []
    todo = []
    reason = P._clean_text(reason, 500)
    for pid, data in rows.items():
        if int(pid) not in members:
            problems.append(f"Pupil #{pid} isn't in {g.code}")
            continue
        if not P._clean_text(data.get("target_grade"), 20):
            continue
        p, old = members[int(pid)]
        data = dict(data)
        if old is None and not data.get("set_by"):
            data["set_by"] = actor.username
        try:
            clean = _clean(data, p, subject, old)
            _check(actor, p, subject, old, clean, reason)
        except ValidationError as e:
            problems += [f"{p.display_name}: {x}" if not x.startswith(p.display_name) else x
                         for x in e.problems]
            continue
        todo.append((p, old, clean))
    if problems:
        raise ValidationError(problems)
    n = 0
    with database.connect() as conn:
        for p, old, clean in todo:
            n += _write(conn, actor, p, subject, old, clean, reason)
    if n:
        activity_log.record("targets.class", target=f"group:{g.group_id}", principal=actor,
                            rows=n)
    return n


# ── Reports ──────────────────────────────────────────────────────────

def missing(*, year_group: int | None = None, subject_id: int | None = None,
            teacher: str | None = None) -> list[tuple[TG.TeachingGroup, list[P.Pupil]]]:
    """This year's teaching groups with pupils who have no target in the subject."""
    have = {(t.pupil_id, t.subject_id) for t in list_targets(year_group=year_group,
                                                             subject_id=subject_id)}
    out = []
    for g in TG.list_groups(academic_year=TG.current_year(_today()), year_group=year_group,
                            subject_id=subject_id, teacher=teacher):
        if not g.is_active:
            continue
        gaps = [p for p in TG.members(g.group_id) if (p.pupil_id, g.subject_id) not in have]
        if gaps:
            out.append((g, gaps))
    return out


def _current_grades(pupil_id: int | None = None) -> dict[tuple[int, int], tuple[str, str]]:
    """(pupil, subject) -> (grade, where from): the newest assessment-point
    working-at grade, else the latest gradebook grade this year."""
    out: dict[tuple[int, int], tuple[str, str]] = {}
    year = TG.current_year(_today())
    one = "" if pupil_id is None else " AND m.pupil_id = ?"
    who: tuple = () if pupil_id is None else (int(pupil_id),)
    with database.connect() as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = "
                                             "'table'")}
        if "gradebook_marks" in tables:
            for r in conn.execute(
                    "SELECT m.pupil_id, a.subject_id, m.grade FROM gradebook_marks m JOIN "
                    "gradebook_assessments a USING (assessment_id) WHERE a.academic_year = ? "
                    "AND m.status = 'Marked' AND m.grade IS NOT NULL AND m.grade != ''"
                    + one + " ORDER BY a.assessment_date, m.mark_id", (year, *who)):
                out[(r[0], r[1])] = (r[2], "gradebook")
        ap_dates: dict[tuple[int, int], str] = {}
        if "assessment_point_grades" in tables:
            for r in conn.execute(
                    "SELECT g.pupil_id, g.subject_id, g.working_at, a.name, "
                    "COALESCE(a.deadline, a.opens_on, a.created_at) FROM "
                    "assessment_point_grades g JOIN assessment_points a USING (point_id) "
                    "WHERE g.working_at IS NOT NULL" + one.replace("m.", "g.")
                    + " ORDER BY a.academic_year, COALESCE(a.deadline, a.opens_on, "
                      "a.created_at), a.point_id", who):
                out[(r[0], r[1])] = (r[2], r[3])
                ap_dates[(r[0], r[1])] = str(r[4] or "")[:10]
        has_mocks = "mock_results" in tables
    if has_mocks:
        # A completed mock series is newer evidence than an earlier assessment point.
        from education_system.systems.secondary.modules.examinations.domain import mock_exams as MX
        for key, (grade, name, ended) in MX.latest_grades(pupil_id).items():
            if key not in ap_dates or ended >= ap_dates[key]:
                out[key] = (grade, name)
    return out


def progress_status(target: str, current: str | None) -> str:
    if not current:
        return "No data"
    if re.fullmatch(r"[1-9]-[1-9]", current.strip()) and scale_of(target) == "GCSE 9-1":
        # A combined-science mock grade ("6-5") counts as the mean of its two.
        from education_system.systems.secondary.modules.examinations.domain import mock_exams as MX
        return MX.compare(current, target)
    cur = _match(current, tuple(SCALES))
    if cur is None or scale_of(cur) != scale_of(target):
        return "Different scale"
    gap = (rank(cur) or 0) - (rank(target) or 0)
    return "Above" if gap > 0 else "On track" if gap == 0 else \
        "Below" if gap == -1 else "Well below"


def progress(*, year_group: int | None = None, subject_id: int | None = None,
             group_id: int | None = None, pupil_id: int | None = None,
             status: str | None = None) -> list[dict[str, Any]]:
    """Each target against the pupil's current grade."""
    now = _current_grades(pupil_id)
    out = []
    for t in list_targets(year_group=year_group, subject_id=subject_id, group_id=group_id,
                          pupil_id=pupil_id):
        cur, src = now.get((t.pupil_id, t.subject_id), (None, None))
        st = progress_status(t.target_grade, cur)
        if status and st != status:
            continue
        out.append({"target": t, "current": cur, "from": src, "status": st})
    return out


def progress_summary(**filters: Any) -> dict[str, int]:
    c = Counter(r["status"] for r in progress(**filters))
    return {s: c.get(s, 0) for s in STATUSES}


# ── Import / export ──────────────────────────────────────────────────

CSV_HEADINGS = ("Admission no", "Pupil", "Year", "Form", "Subject", "Target", "Minimum",
                "Aspirational", "Source", "Set by", "Set date", "Notes")


def export_csv(path: str | Path, *, actor: Principal, **filters: Any) -> int:
    if not actor.is_staff:
        raise PermissionDenied("Only school staff can export targets.")
    rows = list_targets(**filters)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(CSV_HEADINGS)
        for t in rows:
            w.writerow([_safe(v) for v in (t.admission_no, t.pupil_name, t.pupil_year,
                                           t.form_group, t.subject_code, t.target_grade,
                                           t.minimum_grade, t.aspirational_grade, t.source,
                                           t.set_by, t.set_date, t.notes)])
    activity_log.record("targets.export", principal=actor, rows=len(rows))
    return len(rows)


def import_csv(path: str | Path, *, actor: Principal, source: str | None = None,
               reason: str | None = None) -> dict[str, int]:
    """Bulk targets (e.g. from FFT): Admission no, Subject (code), Target, and
    optionally Minimum, Aspirational, Source, Set date, Notes. Data manager
    only; all or nothing. Returns {'set': n, 'changed': n, 'unchanged': n}."""
    if not is_editor(actor):
        activity_log.record("targets.import", outcome="denied", principal=actor)
        raise PermissionDenied("Only the data manager can import targets.")
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        heads = {h.strip().lower(): h for h in (reader.fieldnames or [])}
        need = [h for h in ("admission no", "subject", "target") if h not in heads]
        if need:
            raise ValidationError(["The file needs 'Admission no', 'Subject' and 'Target' "
                                   "columns"])
        lines = list(reader)
    keys = {"target": "target_grade", "minimum": "minimum_grade",
            "aspirational": "aspirational_grade", "source": "source", "set date": "set_date",
            "notes": "notes", "set by": "set_by"}
    problems: list[str] = []
    todo = []
    seen: set[tuple[int, int]] = set()
    reason = P._clean_text(reason, 500)
    for i, r in enumerate(lines, 2):
        adm = (r.get(heads["admission no"]) or "").strip()
        if not adm:
            continue
        try:
            p = _pupil(adm)
            s = _subject((r.get(heads["subject"]) or "").strip())
        except ValidationError as e:
            problems += [f"Row {i}: {x}" for x in e.problems]
            continue
        if (p.pupil_id, s.subject_id) in seen:
            problems.append(f"Row {i}: {p.admission_no} {s.code} appears twice")
            continue
        seen.add((p.pupil_id, s.subject_id))
        data = {k: (r.get(heads[h]) or "").strip() for h, k in keys.items() if h in heads}
        if source and not data.get("source"):
            data["source"] = source
        old = get_for(p.pupil_id, s.subject_id)
        if old is None and not data.get("set_by"):
            data["set_by"] = actor.username
        try:
            clean = _clean(data, p, s, old)
            _check(actor, p, s, old, clean, reason or "Imported")
        except (ValidationError, PermissionDenied) as e:
            msgs = e.problems if isinstance(e, ValidationError) else [str(e)]
            problems += [f"Row {i}: {x}" for x in msgs]
            continue
        todo.append((p, s, old, clean))
    if problems:
        raise ValidationError(problems)
    counts = {"set": 0, "changed": 0, "unchanged": 0}
    with database.connect() as conn:
        for p, s, old, clean in todo:
            if _write(conn, actor, p, s, old, clean, reason or "Imported", "import"):
                counts["set" if old is None else "changed"] += 1
            else:
                counts["unchanged"] += 1
    activity_log.record("targets.import", principal=actor, rows=counts["set"] + counts["changed"])
    return counts


S.register_usage("target_grades", "subject_id", "target grade(s)")
