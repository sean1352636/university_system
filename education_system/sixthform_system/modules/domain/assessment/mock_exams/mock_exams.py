"""Mock exam data layer for the Sixth Form System.

Mocks are subject-scoped practice papers — distinct from homework
(which is group-scoped) because the same paper is typically sat by all
students taking the subject regardless of which teaching set they're in.

Two tables:

* ``mock_exams``: title, subject, exam_board, paper_number, date_sat,
  duration_minutes, max_marks, notes.
* ``mock_results``: one row per (mock, student) with marks + optional
  letter-grade override + notes.

Letter grades default to the gradebook's percentage cutoffs; staff can
override per-result if they want to record a specific board grade
boundary outcome.

Cascade rules: deleting a mock drops its results; deleting a student
drops their results.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.sixthform_system.core import paths
from education_system.sixthform_system.modules.domain.assessment.gradebook.gradebook import (
    LETTER_GRADES, pct_to_letter,
)
from education_system.sixthform_system.modules.domain.academics.subjects.subjects import EXAM_BOARDS
from education_system.sixthform_system.modules.domain.assessment.mock_exams import mock_exams as data

logger = logging.getLogger(__name__)

DB_PATH = paths.MOCK_EXAMS_DB

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS mock_exams (
    mock_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title            TEXT NOT NULL,
    subject          TEXT NOT NULL,
    exam_board       TEXT,
    paper_number     INTEGER,
    date_sat         TEXT NOT NULL,
    duration_minutes INTEGER,
    max_marks        INTEGER NOT NULL,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS mock_results (
    result_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    mock_id      INTEGER NOT NULL,
    student_id   TEXT NOT NULL,
    marks        INTEGER,
    grade        TEXT,
    notes        TEXT,
    recorded_at  TEXT DEFAULT (datetime('now')),
    UNIQUE(mock_id, student_id),
    FOREIGN KEY (mock_id)    REFERENCES mock_exams(mock_id)    ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id)   ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_mocks_subject  ON mock_exams(subject);
CREATE INDEX IF NOT EXISTS idx_mocks_date     ON mock_exams(date_sat);
CREATE INDEX IF NOT EXISTS idx_mock_results_m ON mock_results(mock_id);
CREATE INDEX IF NOT EXISTS idx_mock_results_s ON mock_results(student_id);
"""


@dataclass
class MockExam:
    mock_id: int
    title: str
    subject: str
    exam_board: str | None
    paper_number: int | None
    date_sat: str
    duration_minutes: int | None
    max_marks: int
    notes: str | None
    created_at: str


@dataclass
class MockResult:
    result_id: int
    mock_id: int
    student_id: str
    marks: int | None
    grade: str | None        # override; None means use derived from marks
    notes: str | None
    recorded_at: str


@dataclass
class ResultView:
    """One row of a mock's result sheet — student + any existing result."""
    student_id: str
    full_name: str
    result: MockResult | None


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
    from education_system.sixthform_system.modules.domain.students.students import students as _students
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Mock-exams schema ready at %s", DB_PATH)

    _DB_READY = True


def _row_mock(r: sqlite3.Row) -> MockExam:
    return MockExam(
        mock_id=r["mock_id"], title=r["title"], subject=r["subject"],
        exam_board=r["exam_board"], paper_number=r["paper_number"],
        date_sat=r["date_sat"], duration_minutes=r["duration_minutes"],
        max_marks=r["max_marks"], notes=r["notes"],
        created_at=r["created_at"],
    )


def _row_result(r: sqlite3.Row) -> MockResult:
    return MockResult(
        result_id=r["result_id"], mock_id=r["mock_id"],
        student_id=r["student_id"], marks=r["marks"],
        grade=r["grade"], notes=r["notes"],
        recorded_at=r["recorded_at"],
    )


# ── Display helpers ───────────────────────────────────────────────

def derived_pct(marks: int | None, max_marks: int | None) -> float | None:
    if marks is None or max_marks in (None, 0):
        return None
    return round(100.0 * marks / max_marks, 1)


def effective_grade(result: MockResult, max_marks: int | None) -> str | None:
    """Override wins over derived; otherwise compute from percentage."""
    if result.grade:
        return result.grade
    return pct_to_letter(derived_pct(result.marks, max_marks))


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for any invalid mock-exam / result input."""


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_date(s: str, label: str) -> str:
    s = (s or "").strip()
    if not s:
        raise ValidationError(f"{label} is required")
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return s


def _validate_mock_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["title"] = _require(data.get("title"), "Title").strip()

    subject = _require(data.get("subject"), "Subject").strip()
    try:
        from education_system.sixthform_system.modules.domain.academics.subjects import subjects as _subjects
        if not _subjects.is_valid_subject(subject):
            raise ValidationError(f"Unknown subject: {subject}")
    except ImportError:
        pass
    out["subject"] = subject

    board = (data.get("exam_board") or "").strip()
    if board and board not in EXAM_BOARDS:
        raise ValidationError(
            f"Exam board must be blank or one of: {', '.join(EXAM_BOARDS)}")
    out["exam_board"] = board or None

    paper = data.get("paper_number")
    if paper in (None, ""):
        out["paper_number"] = None
    else:
        try:
            p = int(paper)
        except (TypeError, ValueError):
            raise ValidationError("Paper number must be a whole number") from None
        if p < 1 or p > 100:
            raise ValidationError("Paper number must be between 1 and 100")
        out["paper_number"] = p

    out["date_sat"] = _validate_date(data.get("date_sat"), "Date sat")

    dur = data.get("duration_minutes")
    if dur in (None, ""):
        out["duration_minutes"] = None
    else:
        try:
            d = int(dur)
        except (TypeError, ValueError):
            raise ValidationError(
                "Duration must be a whole number of minutes") from None
        if d <= 0 or d > 600:
            raise ValidationError("Duration must be between 1 and 600 minutes")
        out["duration_minutes"] = d

    mx = data.get("max_marks")
    try:
        mx_i = int(_require(mx, "Max marks"))
    except (TypeError, ValueError):
        raise ValidationError("Max marks must be a whole number") from None
    if mx_i <= 0 or mx_i > 1000:
        raise ValidationError("Max marks must be between 1 and 1000")
    out["max_marks"] = mx_i

    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def _validate_result_payload(
    data: dict[str, Any], *, max_marks: int,
) -> dict[str, Any]:
    out: dict[str, Any] = {}

    mk = data.get("marks")
    if mk in (None, ""):
        out["marks"] = None
    else:
        try:
            mk_i = int(mk)
        except (TypeError, ValueError):
            raise ValidationError("Marks must be a whole number") from None
        if mk_i < 0:
            raise ValidationError("Marks must be ≥ 0")
        if mk_i > max_marks:
            raise ValidationError(
                f"Marks ({mk_i}) exceed max for this mock ({max_marks})")
        out["marks"] = mk_i

    grade = (data.get("grade") or "").strip()
    if grade:
        if grade not in LETTER_GRADES:
            raise ValidationError(
                f"Grade override must be one of: {', '.join(LETTER_GRADES)}")
        out["grade"] = grade
    else:
        out["grade"] = None

    out["notes"] = (data.get("notes") or "").strip() or None
    return out


# ── Mock CRUD ─────────────────────────────────────────────────────

def create_mock(data: dict[str, Any]) -> MockExam:
    init_db()
    try:
        p = _validate_mock_payload(data)
    except ValidationError as e:
        logger.warning("create_mock validation failed: %s", e)
        raise
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO mock_exams
                  (title, subject, exam_board, paper_number, date_sat,
                   duration_minutes, max_marks, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (p["title"], p["subject"], p["exam_board"], p["paper_number"],
             p["date_sat"], p["duration_minutes"], p["max_marks"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_mock(new_id)
    assert out is not None
    logger.info(
        "Created mock exam #%d (%s — %s, %s, max %d)",
        new_id, out.title, out.subject, out.date_sat, out.max_marks,
    )
    return out


def get_mock(mock_id: int) -> MockExam | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM mock_exams WHERE mock_id = ?", (mock_id,),
        ).fetchone()
        return _row_mock(r) if r else None


def list_mocks(
    *,
    subject: str | None = None,
    exam_board: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    search: str | None = None,
) -> list[MockExam]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if subject:
        clauses.append("subject = ?")
        args.append(subject)
    if exam_board:
        if exam_board not in EXAM_BOARDS:
            raise ValidationError(
                f"Exam board must be one of: {', '.join(EXAM_BOARDS)}")
        clauses.append("exam_board = ?")
        args.append(exam_board)
    if date_from:
        clauses.append("date_sat >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("date_sat <= ?")
        args.append(_validate_date(date_to, "date_to"))
    if search:
        q = f"%{search.strip()}%"
        clauses.append("(title LIKE ? OR notes LIKE ?)")
        args.extend([q, q])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM mock_exams {where} "
           "ORDER BY date_sat DESC, mock_id DESC")
    with _connect() as conn:
        return [_row_mock(r) for r in conn.execute(sql, args).fetchall()]


def update_mock(mock_id: int, data: dict[str, Any]) -> MockExam:
    init_db()
    existing = get_mock(mock_id)
    if existing is None:
        logger.warning("update_mock: unknown id %d", mock_id)
        raise ValidationError(f"No mock exam with id {mock_id}")
    try:
        p = _validate_mock_payload(data)
    except ValidationError as e:
        logger.warning("update_mock(%d) validation failed: %s", mock_id, e)
        raise

    # Lowering max_marks below an existing result's marks would silently
    # invalidate that row — refuse instead.
    with _connect() as conn:
        row = conn.execute(
            "SELECT MAX(marks) AS m FROM mock_results "
            "WHERE mock_id = ? AND marks IS NOT NULL",
            (mock_id,),
        ).fetchone()
    if row and row["m"] is not None and row["m"] > p["max_marks"]:
        raise ValidationError(
            f"Cannot set max to {p['max_marks']}: at least one result "
            f"already has {row['m']} marks"
        )

    with _connect() as conn:
        conn.execute(
            """UPDATE mock_exams SET
                   title = ?, subject = ?, exam_board = ?, paper_number = ?,
                   date_sat = ?, duration_minutes = ?, max_marks = ?, notes = ?
               WHERE mock_id = ?""",
            (p["title"], p["subject"], p["exam_board"], p["paper_number"],
             p["date_sat"], p["duration_minutes"], p["max_marks"],
             p["notes"], mock_id),
        )
        conn.commit()
    out = get_mock(mock_id)
    assert out is not None
    logger.info("Updated mock exam #%d (%s)", mock_id, out.title)
    return out


def delete_mock(mock_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM mock_exams WHERE mock_id = ?", (mock_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted mock exam #%d", mock_id)
            return True
        logger.warning("delete_mock: unknown id %d", mock_id)
        return False


# ── Result roster & bulk save ─────────────────────────────────────

def _roster_for_subject(subject: str) -> list:
    """Students taking the subject as any of their 3 A-Levels."""
    from education_system.sixthform_system.modules.domain.students.students import students as _students
    return [
        s for s in _students.list_students()
        if subject in (s.subjects if hasattr(s, "subjects") else
                       [s.subject_1, s.subject_2, s.subject_3])
    ]


def result_view(mock_id: int) -> list[ResultView]:
    """Roster + existing results for a mock's subject."""
    init_db()
    mock = get_mock(mock_id)
    if mock is None:
        raise ValidationError(f"No mock exam with id {mock_id}")

    students = _roster_for_subject(mock.subject)
    with _connect() as conn:
        rows = {
            r["student_id"]: _row_result(r)
            for r in conn.execute(
                "SELECT * FROM mock_results WHERE mock_id = ?",
                (mock_id,),
            ).fetchall()
        }

    # Include any "extra" students who already have a recorded result
    # but aren't on the auto-roster (e.g. mid-year subject change).
    extra_ids = set(rows) - {s.student_id for s in students}
    if extra_ids:
        from education_system.sixthform_system.modules.domain.students.students import students as _students
        for sid in extra_ids:
            s = _students.get_student(sid)
            if s is not None:
                students.append(s)

    return [
        ResultView(s.student_id, s.full_name, rows.get(s.student_id))
        for s in students
    ]


def save_results(
    mock_id: int, entries: dict[str, dict[str, Any]],
) -> int:
    """Upsert result rows in one transaction. Missing students are
    untouched. Returns number of rows written. Skips entries where both
    marks and grade are blank."""
    init_db()
    mock = get_mock(mock_id)
    if mock is None:
        raise ValidationError(f"No mock exam with id {mock_id}")

    cleaned: list[tuple[str, dict[str, Any]]] = []
    for sid, payload in entries.items():
        # Skip rows with nothing to record
        if not any(payload.get(k) not in (None, "")
                   for k in ("marks", "grade", "notes")):
            continue
        cleaned.append((sid, _validate_result_payload(
            payload, max_marks=mock.max_marks)))

    written = 0
    try:
        with _connect() as conn:
            for sid, p in cleaned:
                conn.execute(
                    """INSERT INTO mock_results
                          (mock_id, student_id, marks, grade, notes,
                           recorded_at)
                       VALUES (?, ?, ?, ?, ?, datetime('now'))
                       ON CONFLICT(mock_id, student_id) DO UPDATE SET
                          marks       = excluded.marks,
                          grade       = excluded.grade,
                          notes       = excluded.notes,
                          recorded_at = datetime('now')""",
                    (mock_id, sid, p["marks"], p["grade"], p["notes"]),
                )
                written += 1
            conn.commit()
    except sqlite3.Error as e:
        logger.exception("save_results DB error")
        raise ValidationError(f"Database error: {e}") from e

    logger.info(
        "Saved %d result(s) for mock exam #%d", written, mock_id)
    return written


def get_result(result_id: int) -> MockResult | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM mock_results WHERE result_id = ?", (result_id,),
        ).fetchone()
        return _row_result(r) if r else None


def list_results(
    *,
    mock_id: int | None = None,
    student_id: str | None = None,
    subject: str | None = None,
) -> list[MockResult]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if mock_id is not None:
        clauses.append("mr.mock_id = ?")
        args.append(mock_id)
    if student_id:
        clauses.append("mr.student_id = ?")
        args.append(student_id)
    if subject:
        clauses.append(
            "mr.mock_id IN (SELECT mock_id FROM mock_exams WHERE subject = ?)"
        )
        args.append(subject)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        f"SELECT mr.* FROM mock_results mr {where} "
        "ORDER BY mr.mock_id DESC, mr.student_id"
    )
    with _connect() as conn:
        return [_row_result(r) for r in conn.execute(sql, args).fetchall()]


def update_result(result_id: int, data: dict[str, Any]) -> MockResult:
    init_db()
    existing = get_result(result_id)
    if existing is None:
        logger.warning("update_result: unknown id %d", result_id)
        raise ValidationError(f"No result with id {result_id}")
    mock = get_mock(existing.mock_id)
    p = _validate_result_payload(
        {
            "marks": data.get("marks", existing.marks),
            "grade": data.get("grade", existing.grade),
            "notes": data.get("notes", existing.notes),
        },
        max_marks=mock.max_marks if mock else 1000,
    )
    with _connect() as conn:
        conn.execute(
            """UPDATE mock_results SET
                   marks = ?, grade = ?, notes = ?,
                   recorded_at = datetime('now')
               WHERE result_id = ?""",
            (p["marks"], p["grade"], p["notes"], result_id),
        )
        conn.commit()
    logger.info(
        "Updated mock result #%d (student=%s, marks=%s)",
        result_id, existing.student_id, p["marks"],
    )
    out = get_result(result_id)
    assert out is not None
    return out


def delete_result(result_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM mock_results WHERE result_id = ?", (result_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted mock result #%d", result_id)
            return True
        logger.warning("delete_result: unknown id %d", result_id)
        return False


# ── Summaries ─────────────────────────────────────────────────────

@dataclass
class StudentMockSummary:
    student_id: str
    mocks_sat: int           # how many of the relevant mocks have a marks row
    mocks_total: int         # how many mocks exist in the scope
    avg_pct: float | None
    best_letter: str | None
    worst_letter: str | None


def per_student_summary_for_subject(
    subject: str,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, StudentMockSummary]:
    init_db()
    mocks = list_mocks(subject=subject, date_from=date_from, date_to=date_to)
    if not mocks:
        return {}
    mock_ids = [m.mock_id for m in mocks]
    placeholders = ",".join("?" * len(mock_ids))
    mock_max = {m.mock_id: m.max_marks for m in mocks}

    roster = _roster_for_subject(subject)
    by_student: dict[str, dict[str, Any]] = {
        s.student_id: {"sat": 0, "total": len(mocks),
                       "weighted_total": 0.0, "marked": 0,
                       "letters": []}
        for s in roster
    }

    with _connect() as conn:
        rows = conn.execute(
            f"""SELECT mr.student_id, mr.marks, mr.grade, mr.mock_id
                FROM mock_results mr
                WHERE mr.mock_id IN ({placeholders})""",
            mock_ids,
        ).fetchall()

    for r in rows:
        sid = r["student_id"]
        if sid not in by_student:
            by_student[sid] = {"sat": 0, "total": len(mocks),
                               "weighted_total": 0.0, "marked": 0,
                               "letters": []}
        d = by_student[sid]
        max_marks = mock_max.get(r["mock_id"])
        if r["marks"] is not None:
            d["sat"] += 1
            if max_marks:
                d["weighted_total"] += r["marks"] / max_marks
                d["marked"] += 1
        # Compute effective letter (override or derived)
        pct = derived_pct(r["marks"], max_marks)
        letter = r["grade"] or pct_to_letter(pct)
        if letter:
            d["letters"].append(letter)

    out: dict[str, StudentMockSummary] = {}
    for sid, d in by_student.items():
        avg = (round(100.0 * d["weighted_total"] / d["marked"], 1)
               if d["marked"] else None)
        if d["letters"]:
            sorted_letters = sorted(
                set(d["letters"]),
                key=lambda lg: LETTER_GRADES.index(lg) if lg in LETTER_GRADES else 99,
            )
            best, worst = sorted_letters[0], sorted_letters[-1]
        else:
            best, worst = None, None
        out[sid] = StudentMockSummary(
            student_id=sid, mocks_sat=d["sat"], mocks_total=d["total"],
            avg_pct=avg, best_letter=best, worst_letter=worst,
        )
    return out
