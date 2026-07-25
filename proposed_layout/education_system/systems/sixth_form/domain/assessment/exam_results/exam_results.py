"""Results-day data layer for the Sixth Form System.

One ``exam_results`` row per ``exam_entries`` row (UNIQUE link), holding
the marks, UMS (uniform mark scale), final letter grade, and release
date. The exam entry's ``status`` is auto-bumped to ``Sat`` whenever a
result is saved, so the entries directory stays consistent.

Cascade: deleting an exam entry (or, via that, the student) drops the
result.

Distinct from:

* **Predicted grades**  — teacher's forecast, before exams sit.
* **Mock exams**        — practice papers run internally.
* **Exam entries**      — formal board registrations.

"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any
from education_system.systems.sixth_form.infrastructure import paths
from education_system.systems.sixth_form.domain.assessment.gradebook.gradebook import LETTER_GRADES

logger = logging.getLogger(__name__)

DB_PATH = paths.EXAM_RESULTS_DB

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS exam_results (
    result_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id     INTEGER NOT NULL UNIQUE,
    marks        INTEGER,
    ums          INTEGER,
    grade        TEXT NOT NULL,
    released_at  TEXT,
    notes        TEXT,
    recorded_at  TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (entry_id)
        REFERENCES exam_entries(entry_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_results_grade ON exam_results(grade);
CREATE INDEX IF NOT EXISTS idx_results_date  ON exam_results(released_at);
"""


@dataclass
class ExamResult:
    result_id: int
    entry_id: int
    marks: int | None
    ums: int | None
    grade: str
    released_at: str | None
    notes: str | None
    recorded_at: str
    updated_at: str


@dataclass
class ResultRow:
    """Result joined to its exam entry + student name for display."""
    result: ExamResult
    student_id: str
    student_name: str
    subject: str
    exam_board: str
    paper_code: str
    paper_title: str | None
    season: str
    year: int


@dataclass
class ResultEntryView:
    """One row of a bulk result sheet: the (entered) student + existing result."""
    entry_id: int
    student_id: str
    full_name: str
    candidate_no: str | None
    status: str  # entry status: Entered / Withdrawn / Absent / Sat
    result: ExamResult | None


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
    # FKs reference exam_entries which references students — make sure
    # both are in place.
    from education_system.systems.sixth_form.domain.assessment.exam_entries import exam_entries as _entries
    _entries.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Exam-results schema ready at %s", DB_PATH)

    _DB_READY = True


def _row(r: sqlite3.Row) -> ExamResult:
    return ExamResult(
        result_id=r["result_id"], entry_id=r["entry_id"],
        marks=r["marks"], ums=r["ums"], grade=r["grade"],
        released_at=r["released_at"], notes=r["notes"],
        recorded_at=r["recorded_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for invalid result input."""


def _validate_date_opt(value: Any, label: str) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return s


def _validate_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    eid = data.get("entry_id")
    if eid in (None, ""):
        raise ValidationError("Entry ID is required")
    try:
        eid_i = int(eid)
    except (TypeError, ValueError):
        raise ValidationError("Entry ID must be a whole number") from None
    from education_system.systems.sixth_form.domain.assessment.exam_entries import (
        exam_entries as _entries,
    )
    if _entries.get_entry(eid_i) is None:
        raise ValidationError(f"No exam entry with id {eid_i}")
    out["entry_id"] = eid_i

    grade = (data.get("grade") or "").strip()
    if not grade:
        raise ValidationError("Grade is required")
    if grade not in LETTER_GRADES:
        raise ValidationError(
            f"Grade must be one of: {', '.join(LETTER_GRADES)}")
    out["grade"] = grade

    for key, lo, hi in (("marks", 0, 1000), ("ums", 0, 1000)):
        v = data.get(key)
        if v in (None, ""):
            out[key] = None
            continue
        try:
            n = int(v)
        except (TypeError, ValueError):
            raise ValidationError(
                f"{key.upper() if key=='ums' else key.title()} must be a "
                "whole number"
            ) from None
        if n < lo or n > hi:
            raise ValidationError(
                f"{key.upper() if key=='ums' else key.title()} "
                f"must be between {lo} and {hi}"
            )
        out[key] = n

    out["released_at"] = _validate_date_opt(
        data.get("released_at"), "Released at")
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


# ── CRUD ───────────────────────────────────────────────────────────

def save_result(data: dict[str, Any]) -> ExamResult:
    """Upsert a result keyed by ``entry_id`` and bump the entry's status
    to ``Sat`` so the entries directory stays consistent."""
    init_db()
    try:
        p = _validate_payload(data)
    except ValidationError as e:
        logger.warning("save_result validation failed: %s", e)
        raise

    with _connect() as conn:
        conn.execute(
            """INSERT INTO exam_results
                   (entry_id, marks, ums, grade, released_at, notes,
                    recorded_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
               ON CONFLICT(entry_id) DO UPDATE SET
                   marks       = excluded.marks,
                   ums         = excluded.ums,
                   grade       = excluded.grade,
                   released_at = excluded.released_at,
                   notes       = excluded.notes,
                   updated_at  = datetime('now')""",
            (p["entry_id"], p["marks"], p["ums"], p["grade"],
             p["released_at"], p["notes"]),
        )
        conn.commit()

    # Bump the entry to 'Sat' so the directory reflects reality.
        from education_system.systems.sixth_form.domain.assessment.exam_entries import exam_entries as _entries
    try:
        entry = _entries.get_entry(p["entry_id"])
        if entry and entry.status != "Sat":
            _entries.update_entry(p["entry_id"], {"status": "Sat"})
    except Exception:
        logger.exception(
            "Failed to bump entry #%d status to Sat", p["entry_id"])

    out = get_for_entry(p["entry_id"])
    assert out is not None
    logger.info(
        "Saved result for entry #%d: grade=%s, marks=%s, ums=%s",
        p["entry_id"], out.grade, out.marks, out.ums,
    )
    return out


def get_result(result_id: int) -> ExamResult | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM exam_results WHERE result_id = ?", (result_id,),
        ).fetchone()
        return _row(r) if r else None


def get_for_entry(entry_id: int) -> ExamResult | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM exam_results WHERE entry_id = ?", (entry_id,),
        ).fetchone()
        return _row(r) if r else None


def update_result(result_id: int, data: dict[str, Any]) -> ExamResult:
    """Update grade / marks / UMS / released_at / notes for an existing
    result. ``entry_id`` is immutable through this entry point."""
    init_db()
    existing = get_result(result_id)
    if existing is None:
        logger.warning("update_result: unknown id %d", result_id)
        raise ValidationError(f"No result with id {result_id}")

    p = _validate_payload({
        "entry_id":    existing.entry_id,
        "grade":       data.get("grade", existing.grade),
        "marks":       data.get("marks", existing.marks),
        "ums":         data.get("ums", existing.ums),
        "released_at": data.get("released_at", existing.released_at),
        "notes":       data.get("notes", existing.notes),
    })

    with _connect() as conn:
        conn.execute(
            """UPDATE exam_results SET
                   marks = ?, ums = ?, grade = ?,
                   released_at = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE result_id = ?""",
            (p["marks"], p["ums"], p["grade"], p["released_at"],
             p["notes"], result_id),
        )
        conn.commit()
    logger.info(
        "Updated result #%d (entry=%d, grade=%s)",
        result_id, existing.entry_id, p["grade"],
    )
    out = get_result(result_id)
    assert out is not None
    return out


def delete_result(result_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM exam_results WHERE result_id = ?", (result_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted result #%d", result_id)
            return True
        logger.warning("delete_result: unknown id %d", result_id)
        return False


# ── Joined queries ─────────────────────────────────────────────────

def _join_query(extra_where: str = "", args: tuple = ()) -> list[ResultRow]:
    init_db()
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    name_index = {s.student_id: s.full_name for s in _students.list_students()}
    sql = f"""
        SELECT r.*,
               e.student_id, e.subject, e.exam_board, e.paper_code,
               e.paper_title, e.season, e.year
        FROM exam_results r
        JOIN exam_entries e ON e.entry_id = r.entry_id
        {extra_where}
        ORDER BY e.year DESC, e.season, e.subject, e.student_id
    """
    with _connect() as conn:
        rows = conn.execute(sql, args).fetchall()
    out: list[ResultRow] = []
    for r in rows:
        result = ExamResult(
            result_id=r["result_id"], entry_id=r["entry_id"],
            marks=r["marks"], ums=r["ums"], grade=r["grade"],
            released_at=r["released_at"], notes=r["notes"],
            recorded_at=r["recorded_at"], updated_at=r["updated_at"],
        )
        out.append(ResultRow(
            result=result,
            student_id=r["student_id"],
            student_name=name_index.get(r["student_id"], "(unknown)"),
            subject=r["subject"], exam_board=r["exam_board"],
            paper_code=r["paper_code"], paper_title=r["paper_title"],
            season=r["season"], year=r["year"],
        ))
    return out


def list_results(
    *,
    student_id: str | None = None,
    subject: str | None = None,
    exam_board: str | None = None,
    season: str | None = None,
    year: int | None = None,
    paper_code: str | None = None,
    grade: str | None = None,
) -> list[ResultRow]:
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("e.student_id = ?")
        args.append(student_id.strip())
    if subject:
        clauses.append("e.subject = ?")
        args.append(subject)
    if exam_board:
        clauses.append("e.exam_board = ?")
        args.append(exam_board)
    if season:
        clauses.append("e.season = ?")
        args.append(season)
    if year is not None:
        clauses.append("e.year = ?")
        args.append(year)
    if paper_code:
        clauses.append("e.paper_code = ?")
        args.append(paper_code.strip().upper())
    if grade:
        if grade not in LETTER_GRADES:
            raise ValidationError(
                f"Grade must be one of: {', '.join(LETTER_GRADES)}")
        clauses.append("r.grade = ?")
        args.append(grade)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return _join_query(where, tuple(args))


def results_for_student(
    student_id: str, *, year: int | None = None,
) -> list[ResultRow]:
    return list_results(student_id=student_id, year=year)


# ── Bulk-by-paper view ─────────────────────────────────────────────

def bulk_view(
    paper_code: str, season: str, year: int,
) -> list[ResultEntryView]:
    """Roster of exam entries for this paper/season/year + any saved
    result. Excludes Withdrawn entries by default — they don't sit.
    """
    init_db()
    from education_system.systems.sixth_form.domain.assessment.exam_entries import exam_entries
    from education_system.systems.sixth_form.domain.learners.students import students as _entries
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    entries = _entries.list_entries(
        paper_code=paper_code, season=season, year=year)
    if not entries:
        return []
    name_index = {s.student_id: s.full_name for s in _students.list_students()}

    with _connect() as conn:
        placeholders = ",".join("?" * len(entries))
        results = {
            r["entry_id"]: _row(r)
            for r in conn.execute(
                f"SELECT * FROM exam_results WHERE entry_id IN ({placeholders})",
                [e.entry_id for e in entries],
            ).fetchall()
        }

    out: list[ResultEntryView] = []
    for e in entries:
        out.append(ResultEntryView(
            entry_id=e.entry_id,
            student_id=e.student_id,
            full_name=name_index.get(e.student_id, "(unknown)"),
            candidate_no=e.candidate_no,
            status=e.status,
            result=results.get(e.entry_id),
        ))
    return out


def save_bulk(
    *,
    paper_code: str,
    season: str,
    year: int,
    released_at: str | None,
    entries: dict[int, dict[str, Any]],
) -> int:
    """Upsert results for a batch of exam entries on a single paper.

    ``entries`` maps ``entry_id`` → ``{"grade", "marks", "ums", "notes"}``.
    Rows missing a grade are skipped so partial saves are fine. Returns
    the number of rows written.
    """
    init_db()
    released_at = _validate_date_opt(released_at, "Released at")
    written = 0
    for entry_id, payload in entries.items():
        grade = (payload.get("grade") or "").strip()
        if not grade:
            continue
        try:
            save_result({
                "entry_id":   entry_id,
                "grade":      grade,
                "marks":      payload.get("marks"),
                "ums":        payload.get("ums"),
                "released_at": released_at,
                "notes":      payload.get("notes"),
            })
        except ValidationError as e:
            logger.warning(
                "save_bulk skipped entry %d: %s", entry_id, e)
            raise
        written += 1
    logger.info(
        "Bulk-saved %d result(s) for %s (%s %d)",
        written, paper_code, season, year,
    )
    return written


# ── Summaries / grade distribution ─────────────────────────────────

@dataclass
class GradeDistribution:
    counts: dict[str, int] = field(default_factory=dict)
    total: int = 0

    @property
    def pass_count(self) -> int:
        """A*-E counted; U is a fail."""
        return sum(self.counts.get(g, 0) for g in LETTER_GRADES if g != "U")

    @property
    def pass_rate(self) -> float | None:
        if self.total == 0:
            return None
        return round(100.0 * self.pass_count / self.total, 1)

    @property
    def top_rate(self) -> float | None:
        """A*-A as a percentage of the total."""
        if self.total == 0:
            return None
        top = self.counts.get("A*", 0) + self.counts.get("A", 0)
        return round(100.0 * top / self.total, 1)


def grade_distribution(
    *,
    subject: str | None = None,
    exam_board: str | None = None,
    season: str | None = None,
    year: int | None = None,
) -> GradeDistribution:
    """Tally results by letter grade for the given series filter."""
    rows = list_results(
        subject=subject, exam_board=exam_board,
        season=season, year=year,
    )
    counts: dict[str, int] = {g: 0 for g in LETTER_GRADES}
    for r in rows:
        counts[r.result.grade] = counts.get(r.result.grade, 0) + 1
    return GradeDistribution(counts=counts, total=len(rows))


@dataclass
class StudentResultsSummary:
    student_id: str
    total: int          # papers with a recorded result
    by_grade: dict[str, int]
    best: str | None
    worst: str | None


def per_student_summary(
    student_id: str, *, year: int | None = None,
) -> StudentResultsSummary:
    rows = results_for_student(student_id, year=year)
    counts: dict[str, int] = {g: 0 for g in LETTER_GRADES}
    for r in rows:
        counts[r.result.grade] = counts.get(r.result.grade, 0) + 1
    if rows:
        sorted_letters = sorted(
            {r.result.grade for r in rows},
            key=lambda lg: LETTER_GRADES.index(lg) if lg in LETTER_GRADES else 99,
        )
        best, worst = sorted_letters[0], sorted_letters[-1]
    else:
        best, worst = None, None
    return StudentResultsSummary(
        student_id=student_id, total=len(rows),
        by_grade=counts, best=best, worst=worst,
    )
