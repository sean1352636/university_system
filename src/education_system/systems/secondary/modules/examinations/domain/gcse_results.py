"""GCSE results: the grades pupils actually achieved.

One row per pupil per subject per qualification (GCSE, GCSE short course,
IGCSE): grade 9-1 or U, the exam board, the year sat and the series. A
resit replaces the row (the change is audited). Entered one pupil at a time
or imported from the results-day file; the exams officer
(:data:`EXAM_RESULT_EDITORS`) changes them, all staff read them.

The results move on with the pupil to the sixth form (see
:mod:`modules.progression.domain.sixth_form_progression`).

The embargo
    A grade recorded in Exam Results (:mod:`modules.examinations.domain.exam_results`) is written
    here at once, but while its series is still under embargo it is left
    out of everything read from here - the profile, the GCSE results list,
    exports, the summary and the sixth form handover - for everyone,
    and it can't be overwritten by hand. It appears when the exams officer
    releases the series.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import EXAM_RESULT_EDITORS, Principal
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

GRADES: tuple[str, ...] = ("9", "8", "7", "6", "5", "4", "3", "2", "1", "U")
QUALIFICATIONS: tuple[str, ...] = ("GCSE", "GCSE short course", "IGCSE")
SERIES: tuple[str, ...] = ("June", "November")
BOARDS = S.EXAM_BOARDS

_SCHEMA = """
CREATE TABLE IF NOT EXISTS gcse_results (
    result_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id       INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    subject_id     INTEGER NOT NULL REFERENCES subjects (subject_id),
    qualification  TEXT NOT NULL DEFAULT 'GCSE',
    grade          TEXT NOT NULL,
    exam_board     TEXT,
    exam_year      INTEGER NOT NULL,
    series         TEXT NOT NULL DEFAULT 'June',
    entered_by     TEXT,
    entered_at     TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (pupil_id, subject_id, qualification)
);
CREATE INDEX IF NOT EXISTS ix_gcse_results_pupil ON gcse_results (pupil_id);
CREATE TABLE IF NOT EXISTS gcse_results_audit (
    audit_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id  INTEGER NOT NULL,
    action    TEXT NOT NULL CHECK (action IN ('record', 'change', 'delete', 'import')),
    detail    TEXT,
    actor     TEXT NOT NULL,
    at        TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

database.register_schema("gcse_results", _SCHEMA)

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound


@dataclass(frozen=True)
class Result:
    result_id: int
    pupil_id: int
    subject_id: int
    qualification: str
    grade: str
    exam_board: str | None
    exam_year: int
    series: str
    entered_by: str | None
    entered_at: str
    subject_code: str = ""
    subject_name: str = ""
    ebacc_category: str | None = None
    pupil_name: str = ""
    admission_no: str = ""
    year_group: int = 0

    @property
    def passed(self) -> bool:
        """Grade 4 or above (a "standard pass")."""
        return self.grade.isdigit() and int(self.grade) >= 4


_SELECT = """
SELECT r.*, s.code AS subject_code, s.name AS subject_name, s.ebacc_category,
       p.legal_last_name, p.legal_first_name, p.preferred_name, p.admission_no, p.year_group
FROM gcse_results r JOIN subjects s USING (subject_id) JOIN pupils p USING (pupil_id)
"""
_BASE = ("result_id", "pupil_id", "subject_id", "qualification", "grade", "exam_board",
         "exam_year", "series", "entered_by", "entered_at")


def _row(r) -> Result:
    return Result(**{k: r[k] for k in _BASE}, subject_code=r["subject_code"],
                  subject_name=r["subject_name"], ebacc_category=r["ebacc_category"],
                  pupil_name=f"{r['legal_last_name']}, "
                             f"{r['preferred_name'] or r['legal_first_name']}",
                  admission_no=r["admission_no"], year_group=r["year_group"])


def is_editor(actor: Principal) -> bool:
    return actor.role in EXAM_RESULT_EDITORS


def _require(actor: Principal, action: str, target: str | None = None) -> None:
    if not is_editor(actor):
        activity_log.record(action, target=target, outcome="denied", principal=actor)
        raise PermissionDenied("Only the exams officer can change GCSE results.")


def _audit(conn, pupil_id: int, action: str, actor: Principal, detail: dict) -> None:
    conn.execute("INSERT INTO gcse_results_audit (pupil_id, action, detail, actor) VALUES "
                 "(?, ?, ?, ?)", (pupil_id, action, json.dumps(detail, sort_keys=True),
                                  actor.username or "unknown"))


# ── Reading ──────────────────────────────────────────────────────────

def _held(pupil_id: int | None = None) -> set[tuple]:
    """(pupil, subject, qualification, exam year, season) of rows from an
    exam series still under embargo."""
    from education_system.systems.secondary.modules.examinations.domain import exam_results as ER
    return ER.embargoed_gcse_keys(pupil_id)


def _key(r: Result) -> tuple:
    return (r.pupil_id, r.subject_id, r.qualification, r.exam_year, r.series)


def _visible(rows: list[Result], pupil_id: int | None = None) -> list[Result]:
    held = _held(pupil_id)
    return [r for r in rows if _key(r) not in held] if held else rows


def _refuse_held(pupil_id: int, c: dict[str, Any], label: str, problems: list[str],
                 held: set[tuple] | None = None) -> None:
    held = _held(pupil_id) if held is None else held
    if any(k[:3] == (pupil_id, c["subject_id"], c["qualification"]) for k in held):
        problems.append(f"{label}that result is under embargo in Exam Results - change it "
                        "there")


def get(result_id: int) -> Result:
    with database.connect() as conn:
        r = conn.execute(_SELECT + " WHERE r.result_id = ?", (int(result_id),)).fetchone()
    if r is None or not _visible([_row(r)], r["pupil_id"]):
        raise NotFound(f"No GCSE result #{result_id}")
    return _row(r)


def for_pupil(pupil_id: int) -> list[Result]:
    """The pupil's results, leaving out grades still under embargo."""
    with database.connect() as conn:
        rows = [_row(r) for r in conn.execute(
            _SELECT + " WHERE r.pupil_id = ? ORDER BY s.name COLLATE NOCASE, r.qualification",
            (int(pupil_id),))]
    return _visible(rows, int(pupil_id))


def list_results(*, year_group: int | None = None, subject_id: int | None = None,
                 exam_year: int | None = None, pupil: str | None = None) -> list[Result]:
    where, params = ["1=1"], []
    for col, val in (("p.year_group", year_group), ("r.subject_id", subject_id),
                     ("r.exam_year", exam_year)):
        if val not in (None, ""):
            where.append(f"{col} = ?")
            params.append(int(val))  # type: ignore[arg-type]
    for term in (pupil or "").split():
        where.append("(p.legal_first_name LIKE ? OR p.legal_last_name LIKE ? OR "
                     "p.preferred_name LIKE ? OR p.admission_no LIKE ?)")
        params += [f"%{term}%"] * 4
    with database.connect() as conn:
        rows = [_row(r) for r in conn.execute(
            _SELECT + " WHERE " + " AND ".join(where)  # nosec B608 - fixed clauses
            + " ORDER BY p.legal_last_name COLLATE NOCASE, p.legal_first_name COLLATE NOCASE, "
              "s.name COLLATE NOCASE", params)]
    return _visible(rows)


def summary(pupil_id: int) -> dict[str, Any]:
    """Count, passes (4+), strong passes (5+), best English and maths."""
    rows = for_pupil(pupil_id)

    def best(cat: str) -> str | None:
        got = [r.grade for r in rows if (r.ebacc_category == cat
                                         or r.subject_name.lower().startswith(cat.lower()))
               and r.grade.isdigit()]
        return max(got, key=int) if got else None
    return {"count": len(rows), "passes": sum(r.passed for r in rows),
            "strong": sum(1 for r in rows if r.grade.isdigit() and int(r.grade) >= 5),
            "english": best("English"), "maths": best("Maths")}


def summary_line(pupil_id: int) -> str | None:
    rows = for_pupil(pupil_id)
    if not rows:
        return None
    return ", ".join(f"{r.subject_code} {r.grade}" for r in rows)


def history(pupil_id: int) -> list[dict[str, Any]]:
    with database.connect() as conn:
        return [{"at": r["at"], "actor": r["actor"], "action": r["action"],
                 "detail": json.loads(r["detail"] or "{}")}
                for r in conn.execute("SELECT * FROM gcse_results_audit WHERE pupil_id = ? "
                                      "ORDER BY audit_id DESC", (int(pupil_id),))]


# ── Recording ────────────────────────────────────────────────────────

def _subject(ref: Any) -> S.Subject | None:
    if isinstance(ref, S.Subject):
        return ref
    v = str(ref or "").strip()
    if not v:
        return None
    if v.isdigit():
        try:
            return S.get(int(v))
        except NotFound:
            return None
    s = S.get_by_code(v)
    if s is None:
        s = next((x for x in S.list_subjects(active_only=False)
                  if x.name.lower() == v.lower()), None)
    return s


def _clean(data: dict[str, Any], label: str, problems: list[str]) -> dict[str, Any] | None:
    n = len(problems)
    s = _subject(data.get("subject_id") or data.get("subject"))
    if s is None:
        problems.append(f"{label}no subject {data.get('subject') or data.get('subject_id') or ''}"
                        .strip())
    grade = (P._clean_text(data.get("grade"), 3) or "").upper()
    if grade not in GRADES:
        problems.append(f"{label}grade must be 9-1 or U")
    qual = P._clean_text(data.get("qualification"), 30) or "GCSE"
    qual = next((q for q in QUALIFICATIONS if q.lower() == qual.lower()), qual)
    if qual not in QUALIFICATIONS:
        problems.append(f"{label}qualification must be one of {', '.join(QUALIFICATIONS)}")
    board = P._clean_text(data.get("exam_board"), 40)
    if board:
        board = next((b for b in BOARDS if b.lower() == board.lower()), board)
    if board and board not in BOARDS:
        problems.append(f"{label}exam board must be one of {', '.join(BOARDS)}")
    if not board and s is not None and s.exam_board:
        board = s.exam_board
    year_raw = data.get("exam_year")
    year = _today().year if year_raw in (None, "") else None
    if year is None:
        try:
            year = int(str(year_raw).strip())
        except ValueError:
            year = 0
        if not 2015 <= year <= _today().year:
            problems.append(f"{label}exam year must be between 2015 and {_today().year}")
    series = P._clean_text(data.get("series"), 10) or "June"
    series = next((x for x in SERIES if x.lower() == series.lower()), series)
    if series not in SERIES:
        problems.append(f"{label}series must be June or November")
    if len(problems) != n:
        return None
    return {"subject_id": s.subject_id, "qualification": qual, "grade": grade,  # type: ignore[union-attr]
            "exam_board": board, "exam_year": year, "series": series}


def _write(conn, pupil_id: int, c: dict[str, Any], actor: Principal, action: str | None = None
           ) -> str:
    """Upsert one result in an open transaction. Returns 'record', 'change' or ''."""
    old = conn.execute("SELECT * FROM gcse_results WHERE pupil_id = ? AND subject_id = ? AND "
                       "qualification = ?", (pupil_id, c["subject_id"], c["qualification"])
                       ).fetchone()
    if old is not None and all(old[k] == c[k] for k in ("grade", "exam_board", "exam_year",
                                                         "series")):
        return ""
    conn.execute(
        "INSERT INTO gcse_results (pupil_id, subject_id, qualification, grade, exam_board, "
        "exam_year, series, entered_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT "
        "(pupil_id, subject_id, qualification) DO UPDATE SET grade = excluded.grade, "
        "exam_board = excluded.exam_board, exam_year = excluded.exam_year, series = "
        "excluded.series, entered_by = excluded.entered_by, entered_at = datetime('now')",
        (pupil_id, c["subject_id"], c["qualification"], c["grade"], c["exam_board"],
         c["exam_year"], c["series"], actor.username))
    kind = "record" if old is None else "change"
    _audit(conn, pupil_id, action or kind, actor,
           {"subject_id": c["subject_id"], "qualification": c["qualification"],
            "from": old["grade"] if old else None, "to": c["grade"]})
    return kind


def record(pupil_id: int, data: dict[str, Any], *, actor: Principal) -> Result:
    """Record or replace one result: subject (id/code/name), grade, and
    optionally qualification, exam_board, exam_year (default this year),
    series."""
    p = P.get_pupil(int(pupil_id))
    if p is None:
        raise NotFound(f"No pupil with id {pupil_id}")
    _require(actor, "gcse.record", p.admission_no)
    problems: list[str] = []
    c = _clean(data, "", problems)
    if c is not None:
        _refuse_held(p.pupil_id, c, "", problems)
    if problems:
        raise ValidationError([x[:1].upper() + x[1:] for x in problems])
    with database.connect() as conn:
        _write(conn, p.pupil_id, c, actor)  # type: ignore[arg-type]
        rid = conn.execute("SELECT result_id FROM gcse_results WHERE pupil_id = ? AND "
                           "subject_id = ? AND qualification = ?",
                           (p.pupil_id, c["subject_id"], c["qualification"])  # type: ignore[index]
                           ).fetchone()[0]
    activity_log.record("gcse.record", target=p.admission_no, principal=actor)
    return get(rid)


def record_many(pupil_id: int, rows: list[dict[str, Any]], *, actor: Principal) -> int:
    """Several results for one pupil, all or nothing. Returns rows changed."""
    p = P.get_pupil(int(pupil_id))
    if p is None:
        raise NotFound(f"No pupil with id {pupil_id}")
    _require(actor, "gcse.record", p.admission_no)
    problems: list[str] = []
    clean = []
    seen = set()
    for i, data in enumerate(rows, 1):
        c = _clean(data, f"Row {i}: ", problems)
        if c is None:
            continue
        key = (c["subject_id"], c["qualification"])
        if key in seen:
            problems.append(f"Row {i}: that subject appears twice")
            continue
        seen.add(key)
        _refuse_held(p.pupil_id, c, f"Row {i}: ", problems)
        clean.append(c)
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        n = sum(1 for c in clean if _write(conn, p.pupil_id, c, actor))
    activity_log.record("gcse.record", target=p.admission_no, principal=actor, rows=n)
    return n


def delete(result_id: int, *, actor: Principal) -> Result:
    r = get(result_id)
    _require(actor, "gcse.delete", r.admission_no)
    with database.connect() as conn:
        conn.execute("DELETE FROM gcse_results WHERE result_id = ?", (r.result_id,))
        _audit(conn, r.pupil_id, "delete", actor,
               {"subject_id": r.subject_id, "qualification": r.qualification,
                "from": r.grade})
    activity_log.record("gcse.delete", target=r.admission_no, principal=actor)
    return r


# ── CSV ──────────────────────────────────────────────────────────────

def export_csv(path: str | Path, *, actor: Principal, **filters: Any) -> int:
    if not actor.is_staff:
        raise PermissionDenied("Only school staff can export results.")
    rows = list_results(**filters)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Admission no", "Pupil", "Year", "Subject", "Qualification", "Grade",
                    "Board", "Exam year", "Series"])
        for r in rows:
            w.writerow([_safe(v) for v in (r.admission_no, r.pupil_name, r.year_group,
                                           r.subject_code, r.qualification, r.grade,
                                           r.exam_board, r.exam_year, r.series)])
    activity_log.record("gcse.export", principal=actor, rows=len(rows))
    return len(rows)


def import_csv(path: str | Path, *, actor: Principal) -> dict[str, int]:
    """Results-day file: Admission no (or UPN), Subject (code or name),
    Grade, and optionally Qualification, Board, Exam year, Series. All or
    nothing. Returns {'record': n, 'change': n, 'unchanged': n}."""
    _require(actor, "gcse.import")
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        heads = {h.strip().lower(): h for h in (reader.fieldnames or [])}
        if not {"admission no", "subject", "grade"} <= set(heads):
            raise ValidationError(["The file needs 'Admission no', 'Subject' and 'Grade' "
                                   "columns"])
        lines = list(reader)
    keys = {"subject": "subject", "grade": "grade", "qualification": "qualification",
            "board": "exam_board", "exam year": "exam_year", "series": "series"}
    problems: list[str] = []
    todo: list[tuple[int, dict[str, Any]]] = []
    seen: set[tuple] = set()
    held = _held()
    for i, r in enumerate(lines, 2):
        ref = (r.get(heads["admission no"]) or "").strip()
        if not ref:
            continue
        p = P.find_by_reference(ref)
        if p is None:
            problems.append(f"Row {i}: no pupil {ref}")
            continue
        data = {k: (r.get(heads[h]) or "").strip() for h, k in keys.items() if h in heads}
        c = _clean(data, f"Row {i}: ", problems)
        if c is None:
            continue
        key = (p.pupil_id, c["subject_id"], c["qualification"])
        if key in seen:
            problems.append(f"Row {i}: {p.admission_no} has that subject twice")
            continue
        seen.add(key)
        _refuse_held(p.pupil_id, c, f"Row {i}: ", problems, held)
        todo.append((p.pupil_id, c))
    if problems:
        raise ValidationError(problems)
    counts = {"record": 0, "change": 0, "unchanged": 0}
    with database.connect() as conn:
        for pid, c in todo:
            counts[_write(conn, pid, c, actor) or "unchanged"] += 1
    activity_log.record("gcse.import", principal=actor, rows=counts["record"] + counts["change"])
    return counts


def handover_list(pupil_id: int) -> list[dict[str, Any]]:
    """The results as plain data for the sixth form. Grades that came from an
    exam series still under embargo (:mod:`modules.examinations.domain.exam_results`) are held
    back until the exams officer releases it."""
    return [{"subject": r.subject_name, "subject_code": r.subject_code,
             "qualification": r.qualification, "grade": r.grade,
             "exam_board": r.exam_board, "year": r.exam_year, "series": r.series}
            for r in for_pupil(pupil_id)]


S.register_usage("gcse_results", "subject_id", "GCSE result(s)")
