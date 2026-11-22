"""Exam results: results day, reviews of marking and results analysis.

Results
    One result per Final exam entry (:mod:`modules.examinations.domain.exam_entries`): the grade,
    marks and UMS from the board, the result date, a status and notes. The
    statuses are the old ones:

    * **Pending** - no result yet;
    * **Final** - the grade the board sent;
    * **Remarked** - a review of marking (or clerical re-check) is open;
    * **Adjusted** - the grade changed after a review;
    * **Withheld** - the board is holding the result back.

    Final and Adjusted need a grade. GCSE-type grades are 9-1, U, X (absent)
    or a combined-science double grade ("6-5"); other qualifications take
    their own short grades (Pass, Merit, L2, E3...). Results come in one at a
    time or from the board's results file (all or nothing, problems listed
    by row).

The embargo
    Boards give centres the results before results day. Until the exams
    officer **releases** a series, only the exams officer
    (:data:`EXAM_RESULT_EDITORS`) can see its results; once released, all
    staff see them, and pupils and parents see them in the portal and can be
    e-mailed their results slip.

The sixth form
    Results go on with a pupil who has been sent to the sixth form
    (:mod:`modules.progression.domain.sixth_form_progression`): only once the series is
    released. Releasing a series, and any later change to a released result
    (a late result, a review outcome), updates the pupil's open sixth form
    application through the platform. Until then the handover holds back the
    embargoed grades and lists those subjects as awaited.

The GCSE record
    A Final or Adjusted 9-1/U grade on a GCSE, GCSE short course or IGCSE is
    written through to :mod:`modules.examinations.domain.gcse_results` (the record that moves on
    with the pupil to the sixth form), and taken back out again if the result
    is deleted, withheld or set back to pending.

Reviews of marking
    Post-results services: clerical re-check, review of marking, priority
    review, access to scripts. A review needs the candidate's consent (the
    grade can go down as well as up), has a fee and the board's deadline,
    and marks the result Remarked while open. Its outcome (unchanged, grade
    raised, grade lowered, marks changed) updates the result - Adjusted with
    the original grade kept - and the fee is refunded when the grade changes.

Analysis
    Per subject: entries, graded, average grade, % at 7+, 5+ and 4+, against
    the mocks and against target grades; the year's English and maths at 4+
    and 5+; each pupil's grades against target.
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

from education_system.systems.secondary.modules.examinations.domain import exam_entries as EE
from education_system.systems.secondary.modules.examinations.domain import gcse_results as G
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import EXAM_RESULT_EDITORS, Principal
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

MENU_LABEL = "Exam Results"
RESULT_STATUSES: tuple[str, ...] = ("Pending", "Final", "Remarked", "Adjusted", "Withheld")
DEFAULT_STATUS = "Pending"
PASS_GRADES_9_1: tuple[str, ...] = ("9", "8", "7", "6", "5", "4")
STRONG_PASS_GRADES: tuple[str, ...] = ("9", "8", "7", "6", "5")
GCSE_QUALS = frozenset({"GCSE", "GCSE short course", "IGCSE"})
GCSE_GRADES: tuple[str, ...] = ("9", "8", "7", "6", "5", "4", "3", "2", "1", "U", "X")
REVIEW_SERVICES: tuple[str, ...] = ("Clerical re-check", "Review of marking",
                                    "Priority review of marking", "Access to scripts")
REVIEW_STATUSES: tuple[str, ...] = ("Requested", "Submitted", "Completed", "Cancelled")
REVIEW_OUTCOMES: tuple[str, ...] = ("Unchanged", "Grade raised", "Grade lowered",
                                    "Marks changed", "Script returned")
#: Services that can change a grade (access to scripts only sends the script).
GRADE_SERVICES = frozenset(REVIEW_SERVICES[:3])

_COMBINED_RE = re.compile(r"^[1-9]-[1-9]$")
_OTHER_GRADE_RE = re.compile(r"^[A-Za-z0-9*+\-]{1,8}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS exam_results (
    result_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id        INTEGER NOT NULL UNIQUE REFERENCES exam_entries (entry_id) ON DELETE CASCADE,
    final_grade     TEXT,
    original_grade  TEXT,
    marks_awarded   REAL,
    max_marks       REAL,
    ums             REAL,
    result_date     TEXT NOT NULL DEFAULT (date('now')),
    status          TEXT NOT NULL DEFAULT 'Pending'
                    CHECK (status IN ('Pending', 'Final', 'Remarked', 'Adjusted', 'Withheld')),
    remark_outcome  TEXT,
    notes           TEXT,
    entered_by      TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS exam_results_release (
    series_id    INTEGER PRIMARY KEY REFERENCES exam_series (series_id) ON DELETE CASCADE,
    released_at  TEXT NOT NULL DEFAULT (datetime('now')),
    released_by  TEXT
);
CREATE TABLE IF NOT EXISTS exam_reviews (
    review_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    result_id     INTEGER NOT NULL REFERENCES exam_results (result_id) ON DELETE CASCADE,
    service       TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'Requested',
    consent_by    TEXT NOT NULL,
    consent_on    TEXT NOT NULL,
    requested_on  TEXT NOT NULL DEFAULT (date('now')),
    deadline      TEXT,
    fee           REAL,
    fee_payer     TEXT NOT NULL DEFAULT 'School',
    outcome       TEXT,
    grade_before  TEXT,
    grade_after   TEXT,
    marks_before  REAL,
    marks_after   REAL,
    refunded      INTEGER NOT NULL DEFAULT 0,
    completed_on  TEXT,
    notes         TEXT,
    created_by    TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_exam_reviews_result ON exam_reviews (result_id);
CREATE TABLE IF NOT EXISTS exam_results_audit (
    audit_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    series_id  INTEGER,
    result_id  INTEGER,
    pupil_id   INTEGER,
    action     TEXT NOT NULL,
    detail     TEXT,
    actor      TEXT NOT NULL,
    at         TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

database.register_schema("exam_results", _SCHEMA)

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound


# ── Records ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ExamResult:
    result_id: int
    entry_id: int
    pupil_id: int
    subject_id: int
    final_grade: str | None
    marks_awarded: float | None
    ums: float | None
    result_date: str
    status: str
    remark_outcome: str | None
    notes: str | None
    subject_code: str | None = None
    subject_name: str | None = None
    pupil_name: str | None = None
    pupil_year: int | None = None
    exam_board: str | None = None
    tier: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    original_grade: str | None = None
    max_marks: float | None = None
    series_id: int = 0
    series_name: str = ""
    qualification: str = ""
    spec_code: str = ""
    entry_code: str = ""
    admission_no: str = ""
    candidate_number: str | None = None
    entered_by: str | None = None

    @property
    def is_pass(self) -> bool | None:
        if self.final_grade is None:
            return None
        return grade_value(self.final_grade) is not None and (grade_value(self.final_grade)
                                                              or 0) >= 4

    @property
    def is_strong_pass(self) -> bool | None:
        if self.final_grade is None:
            return None
        return (grade_value(self.final_grade) or 0) >= 5

    @property
    def graded(self) -> bool:
        return self.status in ("Final", "Adjusted", "Remarked") and bool(self.final_grade)


@dataclass(frozen=True)
class Review:
    review_id: int
    result_id: int
    service: str
    status: str
    consent_by: str
    consent_on: str
    requested_on: str
    deadline: str | None
    fee: float | None
    fee_payer: str
    outcome: str | None
    grade_before: str | None
    grade_after: str | None
    marks_before: float | None
    marks_after: float | None
    refunded: bool
    completed_on: str | None
    notes: str | None
    created_by: str | None
    created_at: str

    @property
    def is_open(self) -> bool:
        return self.status in ("Requested", "Submitted")


_SELECT = (
    "SELECT r.*, e.pupil_id, e.series_id, e.tier, x.subject_id, x.exam_board, x.spec_code, "
    "x.qualification, x.tiered, x.entry_code AS code1, x.foundation_code, x.higher_code, "
    "s.code AS subject_code, s.name AS subject_name, sr.name AS series_name, "
    "p.legal_last_name, p.legal_first_name, p.preferred_name, p.year_group AS pupil_year, "
    "p.admission_no, c.candidate_number "
    "FROM exam_results r JOIN exam_entries e USING (entry_id) "
    "JOIN exam_specs x ON x.spec_id = e.spec_id JOIN subjects s ON s.subject_id = x.subject_id "
    "JOIN exam_series sr ON sr.series_id = e.series_id JOIN pupils p ON p.pupil_id = e.pupil_id "
    "LEFT JOIN exam_candidates c ON c.pupil_id = e.pupil_id")


def _code(r) -> str:
    if r["tiered"] and r["tier"] == "Foundation" and r["foundation_code"]:
        return r["foundation_code"]
    if r["tiered"] and r["tier"] == "Higher" and r["higher_code"]:
        return r["higher_code"]
    return r["code1"] or r["spec_code"]


def _row(r) -> ExamResult:
    return ExamResult(
        result_id=r["result_id"], entry_id=r["entry_id"], pupil_id=r["pupil_id"],
        subject_id=r["subject_id"], final_grade=r["final_grade"],
        marks_awarded=r["marks_awarded"], ums=r["ums"], result_date=r["result_date"],
        status=r["status"], remark_outcome=r["remark_outcome"], notes=r["notes"],
        subject_code=r["subject_code"], subject_name=r["subject_name"],
        pupil_name=f"{r['preferred_name'] or r['legal_first_name']} {r['legal_last_name']}",
        pupil_year=r["pupil_year"], exam_board=r["exam_board"], tier=r["tier"],
        created_at=r["created_at"], updated_at=r["updated_at"],
        original_grade=r["original_grade"], max_marks=r["max_marks"],
        series_id=r["series_id"], series_name=r["series_name"],
        qualification=r["qualification"], spec_code=r["spec_code"], entry_code=_code(r),
        admission_no=r["admission_no"], candidate_number=r["candidate_number"],
        entered_by=r["entered_by"])


def _review_row(r) -> Review:
    d = {k: r[k] for k in Review.__dataclass_fields__}
    d["refunded"] = bool(d["refunded"])
    return Review(**d)


# ── Access and audit ─────────────────────────────────────────────────

def is_editor(actor: Principal) -> bool:
    return actor.role in EXAM_RESULT_EDITORS


def _require(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        activity_log.record(action, target=target, outcome="denied", principal=actor)
        raise PermissionDenied("Only the exams officer can do that.")


def _audit(conn, action: str, actor: Principal, detail: dict, *, series_id: int | None = None,
           result_id: int | None = None, pupil_id: int | None = None) -> None:
    conn.execute("INSERT INTO exam_results_audit (series_id, result_id, pupil_id, action, "
                 "detail, actor) VALUES (?, ?, ?, ?, ?, ?)",
                 (series_id, result_id, pupil_id, action,
                  json.dumps(detail, sort_keys=True, default=str), actor.username or "unknown"))


def history(*, series_id: int | None = None, result_id: int | None = None,
            limit: int = 500) -> list[dict[str, Any]]:
    sql, params = "SELECT * FROM exam_results_audit WHERE 1=1", []
    if series_id is not None:
        sql += " AND series_id = ?"
        params.append(int(series_id))
    if result_id is not None:
        sql += " AND result_id = ?"
        params.append(int(result_id))
    with database.connect() as conn:
        return [{"at": r["at"], "actor": r["actor"], "action": r["action"],
                 "result_id": r["result_id"], "pupil_id": r["pupil_id"],
                 "detail": json.loads(r["detail"] or "{}")}
                for r in conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?",
                                      [*params, int(limit)])]


# ── Grades ───────────────────────────────────────────────────────────

def grade_value(grade: str | None) -> float | None:
    """9-1 as a number (a combined grade is the mean of its two; U is 0)."""
    if not grade:
        return None
    g = grade.strip().upper()
    if g == "U":
        return 0.0
    if g.isdigit() and 1 <= int(g) <= 9:
        return float(g)
    if _COMBINED_RE.match(g):
        a, b = g.split("-")
        return (int(a) + int(b)) / 2
    return None


def clean_grade(grade: Any, qualification: str, problems: list[str], label: str = ""
                ) -> str | None:
    g = str(grade or "").strip().upper()
    if not g:
        return None
    if qualification in GCSE_QUALS:
        if g in GCSE_GRADES or _COMBINED_RE.match(g):
            if _COMBINED_RE.match(g) and int(g[0]) < int(g[2]):
                problems.append(f"{label}a double grade is written higher first (e.g. 6-5)")
                return None
            return g
        problems.append(f"{label}grade must be 9-1, U, X (absent) or a double grade like 6-5")
        return None
    if not _OTHER_GRADE_RE.match(g):
        problems.append(f"{label}grade must be 1-8 letters or digits")
        return None
    return g.title() if g.isalpha() and len(g) > 2 else g


# ── The embargo ──────────────────────────────────────────────────────

def released(series_id: int) -> dict[str, Any] | None:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM exam_results_release WHERE series_id = ?",
                         (int(series_id),)).fetchone()
    return {"at": r["released_at"], "by": r["released_by"]} if r else None


def can_see(actor: Principal, series_id: int) -> bool:
    """Staff see a series' results once released; the exams officer always."""
    return is_editor(actor) or (actor.is_staff and released(series_id) is not None)


def release(series_id: int, *, actor: Principal, on: bool = True) -> dict[str, Any] | None:
    """Lift (or put back) the embargo on a series' results."""
    s = EE.get_series(series_id)
    _require(actor, "exam.results.release", f"series:{s.series_id}")
    with database.connect() as conn:
        if on:
            n = conn.execute("SELECT count(*) FROM exam_results r JOIN exam_entries e "
                             "USING (entry_id) WHERE e.series_id = ?", (s.series_id,)
                             ).fetchone()[0]
            if not n:
                raise ValidationError(["There are no results for this series yet"])
            conn.execute("INSERT INTO exam_results_release (series_id, released_by) VALUES "
                         "(?, ?) ON CONFLICT (series_id) DO NOTHING",
                         (s.series_id, actor.username))
        else:
            conn.execute("DELETE FROM exam_results_release WHERE series_id = ?",
                         (s.series_id,))
        _audit(conn, "release" if on else "embargo", actor, {}, series_id=s.series_id)
    activity_log.record("exam.results.release", target=f"series:{s.series_id}",
                        principal=actor, released=on)
    out = released(s.series_id)
    if on and out is not None:
        out["sixth_form"] = _pass_on(s.series_id, None, actor)
    return out


def _visible(rows: list[ExamResult], actor: Principal | None) -> list[ExamResult]:
    if actor is None or is_editor(actor):
        return rows
    ok = {sid for sid in {r.series_id for r in rows} if can_see(actor, sid)}
    return [r for r in rows if r.series_id in ok]


# ── Reading ──────────────────────────────────────────────────────────

def get(result_id: int) -> ExamResult | None:
    with database.connect() as conn:
        r = conn.execute(_SELECT + " WHERE r.result_id = ?", (int(result_id),)).fetchone()
    return _row(r) if r else None


def get_result(result_id: int) -> ExamResult:
    r = get(result_id)
    if r is None:
        raise NotFound(f"No exam result #{result_id}")
    return r


def get_for_entry(entry_id: int) -> ExamResult | None:
    with database.connect() as conn:
        r = conn.execute(_SELECT + " WHERE r.entry_id = ?", (int(entry_id),)).fetchone()
    return _row(r) if r else None


def list_results(*, series_id: int | None = None, year_group: int | str | None = None,
                 subject_id: int | None = None, status: str | None = None,
                 pupil_id: int | None = None, actor: Principal | None = None
                 ) -> list[ExamResult]:
    """Results with the old filters. With *actor*, embargoed series are left
    out for anyone but the exams officer."""
    where, params = [], []
    for cond, val in (("e.series_id = ?", series_id), ("p.year_group = ?", year_group),
                      ("x.subject_id = ?", subject_id), ("r.status = ?", status),
                      ("e.pupil_id = ?", pupil_id)):
        if val not in (None, ""):
            where.append(cond)
            params.append(val)
    sql = _SELECT + (" WHERE " + " AND ".join(where) if where else "")
    sql += (" ORDER BY sr.exam_year DESC, p.year_group, p.legal_last_name COLLATE NOCASE, "
            "p.legal_first_name COLLATE NOCASE, s.name COLLATE NOCASE")
    with database.connect() as conn:
        rows = [_row(r) for r in conn.execute(sql, params)]
    return _visible(rows, actor)


def list_pending_for_entries(year_group: int | str | None = None, *,
                             series_id: int | None = None) -> list[EE.ExamEntry]:
    """Final entries with no result yet (or only a Pending one)."""
    entries = EE.list_entries(series_id=series_id, year_group=year_group,
                              entry_status="Final")
    with database.connect() as conn:
        done = {r[0] for r in conn.execute(
            "SELECT entry_id FROM exam_results WHERE status <> 'Pending'")}
    return [e for e in entries if e.entry_id not in done]


def pupil_results(pupil_id: int, *, actor: Principal | None = None,
                  series_id: int | None = None) -> dict[str, Any]:
    rows = list_results(pupil_id=int(pupil_id), series_id=series_id, actor=actor)
    graded = [r for r in rows if r.graded]
    return {"pupil_id": int(pupil_id), "results": rows, "graded": len(graded),
            "passes": sum(1 for r in graded if r.is_pass),
            "strong_passes": sum(1 for r in graded if r.is_strong_pass)}


# ── Recording ────────────────────────────────────────────────────────

def _float(value: Any, label: str, lo: float, hi: float, problems: list[str]) -> float | None:
    v = str(value if value is not None else "").strip()
    if not v:
        return None
    try:
        f = float(v)
    except ValueError:
        problems.append(f"{label} must be a number")
        return None
    if not lo <= f <= hi:
        problems.append(f"{label} must be between {lo:g} and {hi:g}")
        return None
    return f


def _clean(data: dict[str, Any], entry: EE.ExamEntry, current: ExamResult | None,
           label: str = "") -> tuple[dict[str, Any], list[str]]:
    keys = ("final_grade", "marks_awarded", "max_marks", "ums", "result_date", "status",
            "remark_outcome", "notes")
    merged = {k: getattr(current, k) for k in keys} if current else {}
    merged.update({k: v for k, v in data.items() if k in keys and v is not None})
    problems: list[str] = []
    grade = clean_grade(merged.get("final_grade"), entry.qualification, problems, label)
    marks = _float(merged.get("marks_awarded"), f"{label}Marks awarded", 0, 10000, problems)
    mx = _float(merged.get("max_marks"), f"{label}Maximum marks", 1, 10000, problems)
    if marks is not None and mx is not None and marks > mx:
        problems.append(f"{label}marks can't be more than the maximum")
    ums = _float(merged.get("ums"), f"{label}UMS", 0, 600, problems)
    date = str(merged.get("result_date") or "").strip() or _today().isoformat()
    try:
        date = _dt.date.fromisoformat(date).isoformat()
    except ValueError:
        problems.append(f"{label}result date must be YYYY-MM-DD")
    status = str(data.get("status") or "").strip()
    if not status:  # not given: follow the grade
        cur = current.status if current else None
        if grade:
            status = cur if cur in ("Final", "Adjusted", "Remarked") else "Final"
        else:
            status = "Withheld" if cur == "Withheld" else DEFAULT_STATUS
    status = next((s for s in RESULT_STATUSES if s.lower() == status.lower()), status)
    if status not in RESULT_STATUSES:
        problems.append(f"{label}status must be one of {', '.join(RESULT_STATUSES)}")
    if status in ("Final", "Adjusted", "Remarked") and not grade:
        problems.append(f"{label}a grade is needed when the status is {status}")
    if status == "Pending" and grade:
        problems.append(f"{label}a pending result has no grade yet - make it Final")
    if status == "Withheld":
        grade = None
    if entry.entry_status != "Final":
        problems.append(f"{label}{entry.pupil_name} {entry.subject_code}: the entry is "
                        f"{entry.entry_status.lower()}, not Final")
    return ({"final_grade": grade, "marks_awarded": marks, "max_marks": mx, "ums": ums,
             "result_date": date, "status": status,
             "remark_outcome": P._clean_text(merged.get("remark_outcome"), 200),
             "notes": P._clean_text(merged.get("notes"), 1000)}, problems)


def _gcse_sync(conn, entry: EE.ExamEntry, before: dict[str, Any] | None,
               after: dict[str, Any] | None, actor: Principal) -> None:
    """Keep gcse_results in step with a GCSE-type result."""
    if entry.qualification not in GCSE_QUALS:
        return
    s = EE.get_series(entry.series_id)
    key = (entry.pupil_id, entry.subject_id, entry.qualification)

    def counts(c):
        return bool(c) and c["status"] in ("Final", "Adjusted", "Remarked") and \
            (c["final_grade"] or "") in G.GRADES

    if after is not None and counts(after):
        G._write(conn, entry.pupil_id, {
            "subject_id": entry.subject_id, "qualification": entry.qualification,
            "grade": after["final_grade"], "exam_board": entry.exam_board,
            "exam_year": s.exam_year, "series": s.season}, actor)
        return
    if before is not None and counts(before):
        old = conn.execute("SELECT * FROM gcse_results WHERE pupil_id = ? AND subject_id = ? "
                           "AND qualification = ?", key).fetchone()
        if old and old["grade"] == before["final_grade"] and old["exam_year"] == s.exam_year \
                and old["series"] == s.season:
            conn.execute("DELETE FROM gcse_results WHERE result_id = ?", (old["result_id"],))
            G._audit(conn, entry.pupil_id, "delete", actor,
                     {"subject_id": entry.subject_id, "qualification": entry.qualification,
                      "from": old["grade"], "why": "exam result removed"})


def _write(conn, entry: EE.ExamEntry, c: dict[str, Any], current: ExamResult | None,
           actor: Principal, action: str) -> int:
    before = ({"status": current.status, "final_grade": current.final_grade}
              if current else None)
    if current is None:
        rid = conn.execute(
            "INSERT INTO exam_results (entry_id, final_grade, marks_awarded, max_marks, ums, "
            "result_date, status, remark_outcome, notes, entered_by) VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (entry.entry_id, c["final_grade"], c["marks_awarded"], c["max_marks"], c["ums"],
             c["result_date"], c["status"], c["remark_outcome"], c["notes"],
             actor.username)).lastrowid
    else:
        rid = current.result_id
        conn.execute(
            "UPDATE exam_results SET final_grade = ?, marks_awarded = ?, max_marks = ?, "
            "ums = ?, result_date = ?, status = ?, remark_outcome = ?, notes = ?, "
            "entered_by = ?, updated_at = datetime('now') WHERE result_id = ?",
            (c["final_grade"], c["marks_awarded"], c["max_marks"], c["ums"], c["result_date"],
             c["status"], c["remark_outcome"], c["notes"], actor.username, rid))
    _gcse_sync(conn, entry, before, c, actor)
    _audit(conn, action, actor, {"from": before, "to": {"status": c["status"],
                                                        "grade": c["final_grade"]}},
           series_id=entry.series_id, result_id=rid, pupil_id=entry.pupil_id)
    return int(rid)  # type: ignore[arg-type]


def upsert(data: dict[str, Any], *, actor: Principal) -> ExamResult:
    """Record or update the result for an entry (``entry_id``): final_grade,
    marks_awarded, max_marks, ums, result_date, status, remark_outcome,
    notes. The status defaults to Final when a grade is given."""
    _require(actor, "exam.result.record")
    try:
        entry = EE.get_entry(int(str(data.get("entry_id") or "").strip()))
    except ValueError:
        raise ValidationError(["Entry ID is required"]) from None
    current = get_for_entry(entry.entry_id)
    if current and current.status == "Remarked" and open_review(current.result_id):
        if data.get("final_grade") not in (None, current.final_grade) or \
                data.get("status") not in (None, "Remarked"):
            raise ValidationError(["A review is open - record its outcome instead"])
    c, problems = _clean(data, entry, current)
    if c["status"] == "Adjusted" and not (current and current.original_grade) and not \
            (current and current.final_grade and current.final_grade != c["final_grade"]):
        problems.append("Adjusted is for a grade changed after a review - record the review")
    if problems:
        raise ValidationError([p[:1].upper() + p[1:] for p in problems])
    if current and all(getattr(current, k) == v for k, v in c.items()):
        return current
    with database.connect() as conn:
        if c["status"] == "Adjusted" and current and not current.original_grade:
            conn.execute("UPDATE exam_results SET original_grade = ? WHERE result_id = ?",
                         (current.final_grade, current.result_id))
        rid = _write(conn, entry, c, current, actor, "record" if current is None else "change")
    activity_log.record("exam.result.record", target=f"entry:{entry.entry_id}",
                        principal=actor, status=c["status"])
    _pass_on(entry.series_id, [entry.pupil_id], actor)
    return get_result(rid)


def record_for_entry(entry_id: int, grade: str | None, *, actor: Principal,
                     **more: Any) -> ExamResult:
    return upsert({"entry_id": entry_id, "final_grade": grade, **more}, actor=actor)


def save_sheet(series_id: int, rows: dict[int, dict[str, Any]], *, actor: Principal) -> int:
    """Grades for many entries at once ({entry_id: {...}}), all or nothing.
    A row with nothing in it is skipped. Returns rows changed."""
    s = EE.get_series(series_id)
    _require(actor, "exam.result.record", f"series:{s.series_id}")
    plan, problems = [], []
    for eid, data in rows.items():
        if not any(str(v or "").strip() for v in data.values()):
            continue
        e = EE.get(int(eid))
        if e is None or e.series_id != s.series_id:
            problems.append(f"Entry {eid} isn't in {s.name}")
            continue
        cur = get_for_entry(e.entry_id)
        if cur and cur.status == "Remarked" and open_review(cur.result_id):
            continue  # under review - leave it
        c, probs = _clean(data, e, cur, f"{e.pupil_name} {e.subject_code}: ")
        problems += probs
        if not probs and not (cur and all(getattr(cur, k) == v for k, v in c.items())):
            plan.append((e, c, cur))
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        for e, c, cur in plan:
            _write(conn, e, c, cur, actor, "record" if cur is None else "change")
    activity_log.record("exam.result.sheet", target=f"series:{s.series_id}", principal=actor,
                        rows=len(plan))
    if plan:
        _pass_on(s.series_id, sorted({e.pupil_id for e, _c, _cur in plan}), actor)
    return len(plan)


def delete(result_id: int, *, actor: Principal) -> bool:
    r = get(result_id)
    if r is None:
        return False
    _require(actor, "exam.result.delete", f"result:{r.result_id}")
    if reviews(r.result_id):
        raise ValidationError(["The result has reviews of marking - it can't be deleted"])
    entry = EE.get_entry(r.entry_id)
    with database.connect() as conn:
        _gcse_sync(conn, entry, {"status": r.status, "final_grade": r.final_grade}, None, actor)
        conn.execute("DELETE FROM exam_results WHERE result_id = ?", (r.result_id,))
        _audit(conn, "delete", actor, {"grade": r.final_grade, "status": r.status},
               series_id=r.series_id, result_id=r.result_id, pupil_id=r.pupil_id)
    activity_log.record("exam.result.delete", target=f"result:{r.result_id}", principal=actor)
    _pass_on(r.series_id, [r.pupil_id], actor)
    return True


# ── Results file ─────────────────────────────────────────────────────

def import_results(series_id: int, path: str | Path, *, actor: Principal) -> dict[str, int]:
    """The board's results file: Candidate number (or Admission no), Entry
    code (or Spec code) and Grade, optionally Marks, Max marks, UMS, Status
    (e.g. Withheld). All or nothing; problems are listed by row. Returns
    {'record': n, 'change': n, 'unchanged': n}."""
    s = EE.get_series(series_id)
    _require(actor, "exam.result.import", f"series:{s.series_id}")
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        heads = {h.strip().lower(): h for h in (reader.fieldnames or [])}
        who = next((h for h in ("candidate number", "admission no") if h in heads), None)
        code = next((h for h in ("entry code", "spec code") if h in heads), None)
        if who is None or code is None or not ({"grade", "status"} & set(heads)):
            raise ValidationError(["The file needs 'Candidate number' (or 'Admission no'), "
                                   "'Entry code' (or 'Spec code') and 'Grade' columns"])
        lines = list(reader)

    def col(r, name):
        return (r.get(heads[name]) or "").strip() if name in heads else ""

    entries = [e for e in EE.list_entries(series_id=s.series_id) if e.entry_status == "Final"]
    by_cand = {}
    for e in entries:
        for k in (e.candidate_number, e.admission_no):
            if k:
                by_cand.setdefault((k.lstrip("0") or "0").lower() if k.isdigit()
                                   else k.lower(), []).append(e)
    problems: list[str] = []
    plan: list[tuple[EE.ExamEntry, dict, ExamResult | None]] = []
    seen: set[int] = set()
    counts = {"record": 0, "change": 0, "unchanged": 0}
    for i, r in enumerate(lines, 2):
        ref, c_ = col(r, who), col(r, code).upper()
        if not ref and not c_:
            continue
        key = (ref.lstrip("0") or "0").lower() if ref.isdigit() else ref.lower()
        mine = by_cand.get(key, [])
        if not mine:
            problems.append(f"Row {i}: no candidate {ref or '(blank)'} with Final entries in "
                            f"{s.name}")
            continue
        hit = [e for e in mine if c_ in {(e.entry_code or "").upper(), (e.spec_code or "")
                                         .upper()}]
        if len(hit) != 1:
            problems.append(f"Row {i}: {ref} isn't entered for {c_ or '(blank)'}")
            continue
        e = hit[0]
        if e.entry_id in seen:
            problems.append(f"Row {i}: {ref} {c_} appears twice")
            continue
        seen.add(e.entry_id)
        cur = get_for_entry(e.entry_id)
        if cur and cur.status == "Remarked" and open_review(cur.result_id):
            problems.append(f"Row {i}: {ref} {c_} is under review - record the review outcome")
            continue
        data = {"final_grade": col(r, "grade"), "marks_awarded": col(r, "marks") or None,
                "max_marks": col(r, "max marks") or None, "ums": col(r, "ums") or None,
                "status": col(r, "status") or None}
        cl, probs = _clean(data, e, cur, f"Row {i}: ")
        problems += probs
        if probs:
            continue
        if cur and all(getattr(cur, k) == v for k, v in cl.items()):
            counts["unchanged"] += 1
            continue
        plan.append((e, cl, cur))
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        for e, cl, cur in plan:
            _write(conn, e, cl, cur, actor, "import")
            counts["record" if cur is None else "change"] += 1
    if counts.get("record") or counts.get("change"):
        _pass_on(s.series_id, None, actor)
    activity_log.record("exam.result.import", target=f"series:{s.series_id}", principal=actor,
                        rows=counts["record"] + counts["change"])
    return counts


def export_results(series_id: int, path: str | Path, *, actor: Principal) -> int:
    if not can_see(actor, series_id):
        raise PermissionDenied("These results are still under embargo.")
    rows = list_results(series_id=series_id, actor=actor)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Admission no", "Candidate number", "Pupil", "Year", "Subject", "Board",
                    "Entry code", "Tier", "Grade", "Marks", "UMS", "Status", "Original grade"])
        for r in rows:
            w.writerow([_safe(v) for v in (
                r.admission_no, r.candidate_number, r.pupil_name, r.pupil_year,
                r.subject_name, r.exam_board, r.entry_code, r.tier, r.final_grade,
                EE._num(r.marks_awarded), EE._num(r.ums), r.status, r.original_grade)])
    activity_log.record("exam.result.export", target=f"series:{series_id}", principal=actor,
                        rows=len(rows))
    return len(rows)


# ── Reviews of marking ───────────────────────────────────────────────

def reviews(result_id: int | None = None, *, series_id: int | None = None,
            open_only: bool = False) -> list[Review]:
    sql, params = ("SELECT v.* FROM exam_reviews v JOIN exam_results r USING (result_id) "
                   "JOIN exam_entries e USING (entry_id) WHERE 1=1"), []
    if result_id is not None:
        sql += " AND v.result_id = ?"
        params.append(int(result_id))
    if series_id is not None:
        sql += " AND e.series_id = ?"
        params.append(int(series_id))
    if open_only:
        sql += " AND v.status IN ('Requested', 'Submitted')"
    with database.connect() as conn:
        return [_review_row(r) for r in conn.execute(sql + " ORDER BY v.review_id", params)]


def open_review(result_id: int) -> Review | None:
    rows = reviews(result_id, open_only=True)
    return rows[0] if rows else None


def get_review(review_id: int) -> Review:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM exam_reviews WHERE review_id = ?",
                         (int(review_id),)).fetchone()
    if r is None:
        raise NotFound(f"No review #{review_id}")
    return _review_row(r)


def request_review(result_id: int, data: dict[str, Any], *, actor: Principal) -> Review:
    """Open a post-results service. ``consent_by`` (who gave the candidate's
    written consent) is required; optional deadline, fee, fee_payer, notes."""
    r = get_result(result_id)
    _require(actor, "exam.review.request", f"result:{r.result_id}")
    problems = []
    service = next((x for x in REVIEW_SERVICES if x.lower() == str(data.get("service") or "")
                    .strip().lower()), None)
    if service is None:
        problems.append(f"Service must be one of {', '.join(REVIEW_SERVICES)}")
    if r.status not in ("Final", "Adjusted") or not r.final_grade:
        problems.append("Only a Final or Adjusted result can be reviewed")
    if open_review(r.result_id):
        problems.append("A review is already open for this result")
    consent = P._clean_text(data.get("consent_by"), 100)
    if not consent:
        problems.append("Record who gave the candidate's consent (the grade can go down as "
                        "well as up)")
    consent_on = P._parse_date(data.get("consent_on") or _today().isoformat(), "Consent date",
                               problems)
    deadline = P._parse_date(data.get("deadline"), "Deadline", problems)
    if deadline and deadline < _today().isoformat():
        problems.append("The board's deadline for this service has passed")
    fee = EE._fee(data.get("fee"), "Fee", problems)
    payer = EE._choice(data.get("fee_payer"), EE.FEE_PAYERS, "Fee payer", problems, "School")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        vid = conn.execute(
            "INSERT INTO exam_reviews (result_id, service, consent_by, consent_on, deadline, "
            "fee, fee_payer, grade_before, marks_before, notes, created_by) VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (r.result_id, service, consent, consent_on, deadline, fee, payer, r.final_grade,
             r.marks_awarded, P._clean_text(data.get("notes"), 1000), actor.username)
        ).lastrowid
        if service in GRADE_SERVICES:
            conn.execute("UPDATE exam_results SET status = 'Remarked', updated_at = "
                         "datetime('now') WHERE result_id = ?", (r.result_id,))
        _audit(conn, "review.request", actor, {"service": service, "review_id": vid},
               series_id=r.series_id, result_id=r.result_id, pupil_id=r.pupil_id)
    activity_log.record("exam.review.request", target=f"result:{r.result_id}", principal=actor)
    _pass_on(r.series_id, [r.pupil_id], actor)
    return get_review(vid)  # type: ignore[arg-type]


def mark_submitted(review_id: int, *, actor: Principal) -> Review:
    v = get_review(review_id)
    r = get_result(v.result_id)
    _require(actor, "exam.review.submit", f"result:{r.result_id}")
    if v.status != "Requested":
        raise ValidationError([f"The review is {v.status.lower()}"])
    with database.connect() as conn:
        conn.execute("UPDATE exam_reviews SET status = 'Submitted' WHERE review_id = ?",
                     (v.review_id,))
        _audit(conn, "review.submit", actor, {"review_id": v.review_id},
               series_id=r.series_id, result_id=r.result_id, pupil_id=r.pupil_id)
    return get_review(v.review_id)


def record_outcome(review_id: int, outcome: str, *, actor: Principal,
                   new_grade: str | None = None, new_marks: Any = None,
                   notes: str | None = None) -> Review:
    """Close a review. A changed grade makes the result Adjusted (the grade
    before the first review is kept) and the fee is refunded."""
    v = get_review(review_id)
    r = get_result(v.result_id)
    _require(actor, "exam.review.outcome", f"result:{r.result_id}")
    entry = EE.get_entry(r.entry_id)
    problems: list[str] = []
    if not v.is_open:
        problems.append(f"The review is already {v.status.lower()}")
    out = next((o for o in REVIEW_OUTCOMES if o.lower() == (outcome or "").strip().lower()),
               None)
    if out is None:
        problems.append(f"Outcome must be one of {', '.join(REVIEW_OUTCOMES)}")
    grade = clean_grade(new_grade, entry.qualification, problems) if new_grade else None
    marks = _float(new_marks, "New marks", 0, 10000, problems)
    if out in ("Grade raised", "Grade lowered"):
        if v.service not in GRADE_SERVICES:
            problems.append("Access to scripts doesn't change grades")
        if not grade:
            problems.append("Give the new grade")
        elif grade == r.final_grade:
            problems.append("The new grade is the same as the old one - use Unchanged or "
                            "Marks changed")
        else:
            a, b = grade_value(grade), grade_value(r.final_grade)
            if a is not None and b is not None and (a > b) != (out == "Grade raised"):
                problems.append(f"{grade} isn't {'higher' if out == 'Grade raised' else 'lower'}"
                                f" than {r.final_grade}")
    elif grade and grade != r.final_grade:
        problems.append("A changed grade is 'Grade raised' or 'Grade lowered'")
    if problems:
        raise ValidationError(problems)
    changed = out in ("Grade raised", "Grade lowered")
    with database.connect() as conn:
        conn.execute(
            "UPDATE exam_reviews SET status = 'Completed', outcome = ?, grade_after = ?, "
            "marks_after = ?, refunded = ?, completed_on = ?, notes = coalesce(?, notes) WHERE "
            "review_id = ?", (out, grade or r.final_grade, marks if marks is not None
                              else r.marks_awarded, int(changed), _today().isoformat(),
                              P._clean_text(notes, 1000), v.review_id))
        if changed:
            c = {"final_grade": grade, "marks_awarded": marks if marks is not None
                 else r.marks_awarded, "max_marks": r.max_marks, "ums": r.ums,
                 "result_date": _today().isoformat(), "status": "Adjusted",
                 "remark_outcome": f"{v.service}: {out} ({r.final_grade} -> {grade})",
                 "notes": r.notes}
            conn.execute("UPDATE exam_results SET original_grade = coalesce(original_grade, ?) "
                         "WHERE result_id = ?", (r.final_grade, r.result_id))
            _write(conn, entry, c, r, actor, "review.outcome")
        else:
            back = "Adjusted" if r.original_grade else "Final"
            conn.execute("UPDATE exam_results SET status = ?, marks_awarded = coalesce(?, "
                         "marks_awarded), remark_outcome = ?, updated_at = datetime('now') "
                         "WHERE result_id = ?",
                         (back, marks, f"{v.service}: {out}", r.result_id))
            _audit(conn, "review.outcome", actor, {"outcome": out, "review_id": v.review_id},
                   series_id=r.series_id, result_id=r.result_id, pupil_id=r.pupil_id)
    activity_log.record("exam.review.outcome", target=f"result:{r.result_id}",
                        principal=actor, outcome=out)
    _pass_on(r.series_id, [r.pupil_id], actor)
    return get_review(v.review_id)


def cancel_review(review_id: int, *, actor: Principal, reason: str | None = None) -> Review:
    v = get_review(review_id)
    r = get_result(v.result_id)
    _require(actor, "exam.review.cancel", f"result:{r.result_id}")
    if not v.is_open:
        raise ValidationError([f"The review is already {v.status.lower()}"])
    with database.connect() as conn:
        conn.execute("UPDATE exam_reviews SET status = 'Cancelled', completed_on = ?, notes = "
                     "coalesce(?, notes) WHERE review_id = ?",
                     (_today().isoformat(), P._clean_text(reason, 500), v.review_id))
        if r.status == "Remarked":
            conn.execute("UPDATE exam_results SET status = ? WHERE result_id = ?",
                         ("Adjusted" if r.original_grade else "Final", r.result_id))
        _audit(conn, "review.cancel", actor, {"review_id": v.review_id},
               series_id=r.series_id, result_id=r.result_id, pupil_id=r.pupil_id)
    _pass_on(r.series_id, [r.pupil_id], actor)
    return get_review(v.review_id)


# ── Summaries and analysis ───────────────────────────────────────────

def _pct(n: int, d: int) -> float | None:
    return round(100.0 * n / d, 1) if d else None


def cohort_summary(*, year_group: int | str | None = None, subject_id: int | None = None,
                   series_id: int | None = None, actor: Principal | None = None
                   ) -> dict[str, Any]:
    rows = list_results(year_group=year_group, subject_id=subject_id, series_id=series_id,
                        actor=actor)
    graded = [r for r in rows if r.graded]
    return {
        "total": len(rows),
        "graded": len(graded),
        "by_status": dict(Counter(r.status for r in rows)),
        "by_grade": dict(Counter(r.final_grade for r in graded)),
        "pass_rate_pct": _pct(sum(1 for r in graded if r.is_pass), len(graded)),
        "strong_pass_pct": _pct(sum(1 for r in graded if r.is_strong_pass), len(graded)),
        "pending": len(list_pending_for_entries(year_group, series_id=series_id)),
        "reviews_open": len(reviews(series_id=series_id, open_only=True)) if series_id else 0,
    }


def _mock_grades() -> dict[tuple[int, int], str]:
    try:
        from education_system.systems.secondary.modules.examinations.domain import mock_exams as MX
        return {k: v[0] for k, v in MX.latest_grades().items()}
    except Exception:  # noqa: BLE001 - no mocks yet
        return {}


def _targets() -> dict[tuple[int, int], str]:
    from education_system.systems.secondary.modules.assessment.domain import target_grades as TGR
    return {(t.pupil_id, t.subject_id): t.target_grade for t in TGR.list_targets()}


def subject_analysis(series_id: int, *, actor: Principal) -> list[dict[str, Any]]:
    """Per subject: entries, graded, average, % 7+/5+/4+, average gap to the
    latest mock and to target (positive = better than)."""
    if not can_see(actor, series_id):
        raise PermissionDenied("These results are still under embargo.")
    rows = [r for r in list_results(series_id=series_id) if r.graded]
    mocks, targets = _mock_grades(), _targets()
    out: dict[int, dict[str, Any]] = {}
    for r in rows:
        v = grade_value(r.final_grade)
        d = out.setdefault(r.subject_id, {"subject": r.subject_name, "code": r.subject_code,
                                          "graded": 0, "values": [], "vs_mock": [],
                                          "vs_target": [], "grades": Counter()})
        d["graded"] += 1
        d["grades"][r.final_grade] += 1
        if v is None:
            continue
        d["values"].append(v)
        k = (r.pupil_id, r.subject_id)
        for src, key in ((mocks, "vs_mock"), (targets, "vs_target")):
            other = grade_value(src.get(k))
            if other is not None:
                d[key].append(v - other)
    res = []
    for d in out.values():
        vals = d["values"]
        n = len(vals)
        res.append({"subject": d["subject"], "code": d["code"], "graded": d["graded"],
                    "average": round(sum(vals) / n, 2) if n else None,
                    "pct_7": _pct(sum(1 for x in vals if x >= 7), n),
                    "pct_5": _pct(sum(1 for x in vals if x >= 5), n),
                    "pct_4": _pct(sum(1 for x in vals if x >= 4), n),
                    "vs_mock": round(sum(d["vs_mock"]) / len(d["vs_mock"]), 2)
                    if d["vs_mock"] else None,
                    "vs_target": round(sum(d["vs_target"]) / len(d["vs_target"]), 2)
                    if d["vs_target"] else None,
                    "grades": dict(d["grades"])})
    return sorted(res, key=lambda x: x["subject"].lower())


def headlines(series_id: int, *, actor: Principal) -> dict[str, Any]:
    """Candidates, English and maths at 4+ and 5+, average grade, results at
    7+ and how many pupils beat / met / missed their targets."""
    if not can_see(actor, series_id):
        raise PermissionDenied("These results are still under embargo.")
    rows = [r for r in list_results(series_id=series_id) if r.graded]
    pupils = sorted({r.pupil_id for r in rows})

    def best(pid: int, word: str) -> float | None:
        vals = [grade_value(r.final_grade) for r in rows if r.pupil_id == pid
                and word in (r.subject_name or "").lower()]
        vals = [v for v in vals if v is not None]
        return max(vals) if vals else None
    eng = {p: best(p, "english") for p in pupils}
    mat = {p: best(p, "math") for p in pupils}
    both4 = sum(1 for p in pupils if (eng[p] or 0) >= 4 and (mat[p] or 0) >= 4)
    both5 = sum(1 for p in pupils if (eng[p] or 0) >= 5 and (mat[p] or 0) >= 5)
    vals = [v for v in (grade_value(r.final_grade) for r in rows) if v is not None]
    targets = _targets()
    gap = Counter()
    for r in rows:
        t, v = grade_value(targets.get((r.pupil_id, r.subject_id))), grade_value(r.final_grade)
        if t is not None and v is not None:
            gap["above" if v > t else "met" if v == t else "below"] += 1
    return {"candidates": len(pupils), "results": len(rows),
            "english_maths_4": both4, "english_maths_4_pct": _pct(both4, len(pupils)),
            "english_maths_5": both5, "english_maths_5_pct": _pct(both5, len(pupils)),
            "average": round(sum(vals) / len(vals), 2) if vals else None,
            "pct_7": _pct(sum(1 for v in vals if v >= 7), len(vals)),
            "vs_target": dict(gap)}


def pupils_vs_target(series_id: int, *, actor: Principal) -> list[dict[str, Any]]:
    """Each pupil's average gap to target, worst first."""
    if not can_see(actor, series_id):
        raise PermissionDenied("These results are still under embargo.")
    targets = _targets()
    by: dict[int, dict[str, Any]] = {}
    for r in list_results(series_id=series_id):
        if not r.graded:
            continue
        d = by.setdefault(r.pupil_id, {"pupil_id": r.pupil_id, "name": r.pupil_name,
                                       "admission_no": r.admission_no, "gaps": [],
                                       "grades": []})
        d["grades"].append(f"{r.subject_code} {r.final_grade}")
        t, v = grade_value(targets.get((r.pupil_id, r.subject_id))), grade_value(r.final_grade)
        if t is not None and v is not None:
            d["gaps"].append(v - t)
    out = [{**d, "average_gap": round(sum(d["gaps"]) / len(d["gaps"]), 2) if d["gaps"]
            else None} for d in by.values()]
    return sorted(out, key=lambda d: (d["average_gap"] is None, d["average_gap"] or 0,
                                      d["name"]))


# ── The sixth form handover ──────────────────────────────────────────

_GRADED = ("Final", "Adjusted", "Remarked")


def embargoed_gcse_keys(pupil_id: int | None = None) -> set[tuple[int, int, str, int, str]]:
    """(pupil, subject, qualification, exam year, season) of GCSE-record rows
    written by a result whose series is still under embargo - the handover
    leaves these out until release."""
    sql = ("SELECT e.pupil_id, x.subject_id, x.qualification, sr.exam_year, sr.season "
           "FROM exam_results r JOIN exam_entries e USING (entry_id) "
           "JOIN exam_specs x ON x.spec_id = e.spec_id "
           "JOIN exam_series sr ON sr.series_id = e.series_id "
           "WHERE r.status IN ('Final', 'Adjusted', 'Remarked') "
           "AND e.series_id NOT IN (SELECT series_id FROM exam_results_release)")
    params: list[Any] = []
    if pupil_id is not None:
        sql += " AND e.pupil_id = ?"
        params.append(int(pupil_id))
    with database.connect() as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = "
                            "'exam_results'").fetchone():
            return set()
        return {(r[0], r[1], r[2], r[3], r[4]) for r in conn.execute(sql, params)}


def entries_for_handover(pupil_id: int) -> list[dict[str, Any]]:
    """The pupil's Final entries in series not yet fully resulted, with where
    each stands for the sixth form: ``awaited`` (no result, or the series is
    still under embargo), ``under review``, ``withheld`` or ``issued``."""
    out = []
    for e in EE.entries_for_pupil(int(pupil_id)):
        if e.entry_status != "Final":
            continue
        s = EE.get_series(e.series_id)
        r = get_for_entry(e.entry_id)
        if released(e.series_id) is None or r is None or r.status == "Pending":
            state = "awaited"
        elif r.status == "Remarked":
            state = "under review"
        elif r.status == "Withheld":
            state = "withheld"
        else:
            state = "issued"
        out.append({"subject": e.subject_name, "subject_code": e.subject_code,
                    "qualification": e.qualification, "exam_board": e.exam_board,
                    "entry_code": e.entry_code, "tier": None if e.tier == "N/A" else e.tier,
                    "series": s.name, "year": s.exam_year, "result": state,
                    "grade": r.final_grade if state in ("issued", "under review") else None})
    return out


def result_states() -> dict[int, Counter]:
    """For every pupil with Final entries: how many are issued, awaited,
    under review or withheld (one query, for lists such as Year 11)."""
    sql = ("SELECT e.pupil_id, r.status, (SELECT 1 FROM exam_results_release rl WHERE "
           "rl.series_id = e.series_id) AS rel FROM exam_entries e LEFT JOIN exam_results r "
           "USING (entry_id) WHERE e.entry_status = 'Final'")
    out: dict[int, Counter] = {}
    with database.connect() as conn:
        for pid, status, rel in conn.execute(sql):
            if not rel or status in (None, "Pending"):
                state = "awaited"
            else:
                state = {"Remarked": "under review", "Withheld": "withheld"}.get(status,
                                                                                 "issued")
            out.setdefault(pid, Counter())[state] += 1
    return out


def _pass_on(series_id: int, pupil_ids: list[int] | None, actor: Principal
             ) -> dict[str, Any] | None:
    """After a released series' results change, update the open sixth form
    applications of the pupils concerned. Best effort: a failure is logged
    and never undoes the result."""
    if released(series_id) is None:
        return None
    if pupil_ids is None:
        pupil_ids = sorted({e.pupil_id for e in EE.list_entries(series_id=series_id,
                                                                entry_status="Final")})
    try:
        from education_system.systems.secondary.modules.progression.domain import (
            sixth_form_progression as SFP,
        )
        return SFP.send_results(pupil_ids, actor=actor, quiet=True)
    except Exception:  # noqa: BLE001 - the board may be unreachable
        import logging
        logging.getLogger(__name__).exception("Could not pass results on to the sixth form")
        return {"sent": [], "skipped": {}, "failed": True}


# ── Results slips ────────────────────────────────────────────────────

def slip(pupil_id: int, series_id: int) -> dict[str, Any]:
    p = P.get_pupil(int(pupil_id))
    if p is None:
        raise NotFound(f"No pupil #{pupil_id}")
    s = EE.get_series(series_id)
    rows = list_results(series_id=s.series_id, pupil_id=p.pupil_id)
    have = {r.entry_id for r in rows}
    awaited = [e for e in EE.list_entries(series_id=s.series_id, pupil_id=p.pupil_id)
               if e.entry_status == "Final" and e.entry_id not in have]
    return {"pupil": p, "series": s, "results": rows, "awaited": awaited,
            "candidate": EE.candidate(p.pupil_id), "centre": EE.get_centre()}


def slip_text(sl: dict[str, Any]) -> str:
    p, s, c = sl["pupil"], sl["series"], sl["candidate"]
    lines = [f"Results - {s.name}", f"Candidate: {p.legal_first_name} {p.legal_last_name}",
             f"Candidate number: {c.candidate_number if c else '-'}"
             + (f"    Centre: {sl['centre'].centre_number}" if sl["centre"].centre_number
                else ""), ""]
    for r in sl["results"]:
        grade = {"Pending": "awaited", "Withheld": "withheld by the board"}.get(
            r.status, r.final_grade or "-")
        lines.append(f"  {(r.subject_name or '')[:30]:<30} {r.qualification:<10} "
                     f"{r.exam_board or '':<14} {grade}"
                     + (" (under review)" if r.status == "Remarked" else "")
                     + (f" (changed from {r.original_grade} after review)"
                        if r.status == "Adjusted" and r.original_grade else ""))
    for e in sl.get("awaited", []):
        lines.append(f"  {(e.subject_name or '')[:30]:<30} {e.qualification:<10} "
                     f"{e.exam_board or '':<14} awaited")
    if not sl["results"] and not sl.get("awaited"):
        lines.append("  No results yet.")
    return "\n".join(lines)


SLIP_TEMPLATE = "exam_results"


def send_slips(series_id: int, *, actor: Principal) -> dict[str, Any]:
    """E-mail each candidate's results to their school address and contacts.
    Only after the series is released."""
    s = EE.get_series(series_id)
    _require(actor, "exam.results.slips", f"series:{s.series_id}")
    if released(s.series_id) is None:
        raise ValidationError(["Release the results first - they are still under embargo"])
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    from education_system.systems.secondary.modules.communication.domain import email_templates
    from education_system.systems.secondary.modules.pupils.domain import pupil_accounts as PAC
    from education_system.systems.secondary.modules.pupils.domain import contacts as C
    ids = sorted({r.pupil_id for r in list_results(series_id=s.series_id)})
    if not ids:
        raise ValidationError(["There are no results for this series"])
    template = email_templates.load_template(SLIP_TEMPLATE)
    officer = EE.get_centre().officer_name or "the exams officer"
    contacts = C.emailable_for_pupils(ids)
    recipients, nobody = [], []
    for pid in ids:
        sl = slip(pid, s.series_id)
        p = sl["pupil"]
        to = []
        acct = PAC.get_for_pupil(pid)
        if acct and acct.status == "active":
            to.append((acct.school_email, p.display_name))
        to += [(c.email, c.full_name) for c in contacts.get(pid, []) if c.email]
        if not to:
            nobody.append(p)
            continue
        for address, name in to:
            subject, body = template.render({
                "recipient_name": name, "pupil_name": p.display_name,
                "pupil_first_name": p.preferred_name or p.legal_first_name,
                "series_name": s.name, "results": slip_text(sl), "officer_name": officer})
            recipients.append((address, name, subject, body))
    if not recipients:
        raise ValidationError(["None of the candidates has an e-mail address to send to"])
    mid = E.save_prepared("exam_results", f"Exam results - {s.name}",
                          f"Exam results - {s.name}", "(one results slip per candidate)",
                          recipients, actor=actor)
    with database.connect() as conn:
        _audit(conn, "slips", actor, {"emails": len(recipients), "message_id": mid},
               series_id=s.series_id)
    activity_log.record("exam.results.slips", target=f"series:{s.series_id}", principal=actor,
                        recipients=len(recipients))
    return {"message_id": mid, "emails": len(recipients), "nobody": nobody}


def released_for_pupil(pupil_id: int) -> list[dict[str, Any]]:
    """Results slips for the portal: released series only."""
    out = []
    for s in EE.list_series():
        if released(s.series_id) is None:
            continue
        sl = slip(pupil_id, s.series_id)
        if sl["results"]:
            out.append(sl)
    return out
