"""Gradebook data layer for the Sixth Form System.

The gradebook is a **derived view** over the homework data: every row
sits in ``submissions``, joined to ``assignments`` for max-marks and
title. The gradebook adds three things on top:

* **Letter grades** — A-Level boundaries (A*, A, B, C, D, E, U), applied
  to either a per-assignment override (table ``grade_boundaries``) or
  the standard percentage defaults.
* **Per-student summaries** — average percentage across all marked
  submissions in a group, best/worst letter, total marked vs. total set.
* **Per-group matrix** — wide view: rows = students, columns =
  assignments, cells = mark / pct / letter.

This module *does not* enter marks — that's the homework module's job.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.sixthform_system.core import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.GRADEBOOK_DB

LETTER_GRADES: tuple[str, ...] = ("A*", "A", "B", "C", "D", "E", "U")

# Default percentage thresholds for A-Level letter grades. Order matters
# (must be descending); pct >= threshold ⇒ that letter.
DEFAULT_BOUNDARIES_PCT: tuple[tuple[str, float], ...] = (
    ("A*", 90.0),
    ("A",  80.0),
    ("B",  70.0),
    ("C",  60.0),
    ("D",  50.0),
    ("E",  40.0),
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS grade_boundaries (
    assignment_id INTEGER PRIMARY KEY,
    a_star        INTEGER,
    a             INTEGER,
    b             INTEGER,
    c             INTEGER,
    d             INTEGER,
    e             INTEGER,
    updated_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (assignment_id)
        REFERENCES assignments(assignment_id) ON DELETE CASCADE
);
"""


@dataclass
class GradeBoundaries:
    """Raw mark thresholds for each letter; lower letters omitted means
    "default to percentage". Any non-None override wins over the default."""
    assignment_id: int
    a_star: int | None
    a:      int | None
    b:      int | None
    c:      int | None
    d:      int | None
    e:      int | None

    def as_dict(self) -> dict[str, int | None]:
        return {
            "A*": self.a_star, "A": self.a, "B": self.b,
            "C": self.c, "D": self.d, "E": self.e,
        }


@dataclass
class GradedSubmission:
    """One cell in the gradebook: submission joined to assignment +
    derived percentage and letter grade."""
    student_id: str
    assignment_id: int
    title: str
    type: str
    due_date: str
    status: str
    marks: int | None
    max_marks: int | None
    percentage: float | None
    letter: str | None


@dataclass
class StudentGradebookSummary:
    student_id: str
    total_assignments: int
    marked: int
    avg_pct: float | None
    best_letter: str | None
    worst_letter: str | None


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    from education_system.sixthform_system.modules.domain.homework import homework as _hw
    _hw.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Gradebook schema ready at %s", DB_PATH)


# ── Letter grade helpers ───────────────────────────────────────────

def pct_to_letter(pct: float | None) -> str | None:
    """Return the default A-Level letter for a percentage, or None if
    pct is None."""
    if pct is None:
        return None
    for letter, threshold in DEFAULT_BOUNDARIES_PCT:
        if pct >= threshold:
            return letter
    return "U"


def _resolve_letter(
    marks: int | None,
    max_marks: int | None,
    boundaries: GradeBoundaries | None,
) -> tuple[float | None, str | None]:
    """Compute (percentage, letter). Returns (None, None) if not marked.

    Per-assignment overrides (raw mark thresholds) win over the default
    percentage table. If only *some* letters have overrides, the rest
    fall back to the percentage default — staff might only pin A*/A.
    """
    if marks is None or max_marks in (None, 0):
        return None, None
    pct = round(100.0 * marks / max_marks, 1)

    if boundaries is not None:
        ordered = (
            ("A*", boundaries.a_star),
            ("A",  boundaries.a),
            ("B",  boundaries.b),
            ("C",  boundaries.c),
            ("D",  boundaries.d),
            ("E",  boundaries.e),
        )
        if any(th is not None for _, th in ordered):
            for letter, threshold in ordered:
                if threshold is not None and marks >= threshold:
                    return pct, letter
            # No override hit — fall through to percentage default for U.
    return pct, pct_to_letter(pct)


# ── Boundaries CRUD ────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for invalid gradebook input."""


def get_boundaries(assignment_id: int) -> GradeBoundaries | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM grade_boundaries WHERE assignment_id = ?",
            (assignment_id,),
        ).fetchone()
        if not r:
            return None
        return GradeBoundaries(
            assignment_id=r["assignment_id"],
            a_star=r["a_star"], a=r["a"], b=r["b"],
            c=r["c"], d=r["d"], e=r["e"],
        )


def set_boundaries(assignment_id: int, data: dict[str, Any]) -> GradeBoundaries:
    """Upsert per-assignment grade boundaries.

    ``data`` may have any subset of ``a_star / a / b / c / d / e`` keys
    (or the user-friendly "A*", "A", ... aliases). Blank/None values
    clear that letter back to "use percentage default".
    """
    init_db()
    from education_system.sixthform_system.modules.domain.homework import homework as _hw
    assn = _hw.get_assignment(assignment_id)
    if assn is None:
        raise ValidationError(f"No assignment with id {assignment_id}")
    if assn.max_marks is None:
        raise ValidationError(
            "Assignment has no max_marks — cannot set raw boundaries")

    # Coerce + validate each letter's threshold.
    def _coerce(value: Any, label: str) -> int | None:
        if value in (None, "") or (isinstance(value, str) and not value.strip()):
            return None
        try:
            n = int(value)
        except (TypeError, ValueError):
            raise ValidationError(
                f"{label} threshold must be a whole number") from None
        if n < 0 or n > assn.max_marks:
            raise ValidationError(
                f"{label} threshold must be 0–{assn.max_marks}")
        return n

    def _val(*keys: str) -> int | None:
        for k in keys:
            if k in data:
                return _coerce(data[k], keys[0])
        return None

    a_star = _val("a_star", "A*")
    a      = _val("a",      "A")
    b      = _val("b",      "B")
    c      = _val("c",      "C")
    d      = _val("d",      "D")
    e      = _val("e",      "E")

    # Sanity: boundaries should be monotonically non-increasing
    # (A* ≥ A ≥ B ≥ C ≥ D ≥ E). Allow gaps (None) — only validate the
    # ones the user set.
    set_pairs = [("A*", a_star), ("A", a), ("B", b),
                 ("C", c), ("D", d), ("E", e)]
    last: tuple[str, int] | None = None
    for label, n in set_pairs:
        if n is None:
            continue
        if last is not None and n > last[1]:
            raise ValidationError(
                f"Boundaries out of order: {label}={n} > {last[0]}={last[1]}"
            )
        last = (label, n)

    with _connect() as conn:
        conn.execute(
            """INSERT INTO grade_boundaries
                  (assignment_id, a_star, a, b, c, d, e, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(assignment_id) DO UPDATE SET
                  a_star = excluded.a_star,
                  a      = excluded.a,
                  b      = excluded.b,
                  c      = excluded.c,
                  d      = excluded.d,
                  e      = excluded.e,
                  updated_at = datetime('now')""",
            (assignment_id, a_star, a, b, c, d, e),
        )
        conn.commit()
    logger.info(
        "Set grade boundaries for assignment #%d "
        "(A*=%s A=%s B=%s C=%s D=%s E=%s)",
        assignment_id, a_star, a, b, c, d, e,
    )
    out = get_boundaries(assignment_id)
    assert out is not None
    return out


def clear_boundaries(assignment_id: int) -> bool:
    """Revert to defaults (percentage thresholds)."""
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM grade_boundaries WHERE assignment_id = ?",
            (assignment_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info(
                "Cleared grade boundaries for assignment #%d", assignment_id)
            return True
        return False


# ── Gradebook views ────────────────────────────────────────────────

def graded_submissions_for_student(student_id: str) -> list[GradedSubmission]:
    """Every submission this student has, joined to assignment + boundary."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT s.student_id, s.marks, s.status,
                      a.assignment_id, a.title, a.type, a.due_date,
                      a.max_marks
               FROM submissions s
               JOIN assignments a ON a.assignment_id = s.assignment_id
               WHERE s.student_id = ?
               ORDER BY a.due_date DESC, a.assignment_id DESC""",
            (student_id,),
        ).fetchall()
    out: list[GradedSubmission] = []
    for r in rows:
        b = get_boundaries(r["assignment_id"])
        pct, letter = _resolve_letter(r["marks"], r["max_marks"], b)
        out.append(GradedSubmission(
            student_id=r["student_id"], assignment_id=r["assignment_id"],
            title=r["title"], type=r["type"], due_date=r["due_date"],
            status=r["status"], marks=r["marks"], max_marks=r["max_marks"],
            percentage=pct, letter=letter,
        ))
    return out


def graded_submissions_for_group(
    group_id: int,
    *,
    type: str | None = None,
    due_from: str | None = None,
    due_to: str | None = None,
) -> list[GradedSubmission]:
    """Every submission for a group's assignments, with letter grades."""
    init_db()
    clauses: list[str] = ["a.group_id = ?"]
    args: list[Any] = [group_id]
    if type:
        from education_system.sixthform_system.modules.domain.homework.homework import ASSIGNMENT_TYPES
        if type not in ASSIGNMENT_TYPES:
            raise ValidationError(
                f"Type must be one of: {', '.join(ASSIGNMENT_TYPES)}")
        clauses.append("a.type = ?")
        args.append(type)
    if due_from:
        clauses.append("a.due_date >= ?")
        args.append(due_from)
    if due_to:
        clauses.append("a.due_date <= ?")
        args.append(due_to)
    where = " AND ".join(clauses)
    sql = (
        "SELECT s.student_id, s.marks, s.status, "
        "       a.assignment_id, a.title, a.type, a.due_date, a.max_marks "
        "FROM submissions s "
        "JOIN assignments a ON a.assignment_id = s.assignment_id "
        f"WHERE {where} "
        "ORDER BY a.due_date DESC, s.student_id"
    )
    with _connect() as conn:
        rows = conn.execute(sql, args).fetchall()

    # Cache boundaries lookup so we don't reissue per-row.
    boundary_cache: dict[int, GradeBoundaries | None] = {}
    out: list[GradedSubmission] = []
    for r in rows:
        aid = r["assignment_id"]
        if aid not in boundary_cache:
            boundary_cache[aid] = get_boundaries(aid)
        pct, letter = _resolve_letter(
            r["marks"], r["max_marks"], boundary_cache[aid])
        out.append(GradedSubmission(
            student_id=r["student_id"], assignment_id=aid,
            title=r["title"], type=r["type"], due_date=r["due_date"],
            status=r["status"], marks=r["marks"], max_marks=r["max_marks"],
            percentage=pct, letter=letter,
        ))
    return out


def group_matrix(
    group_id: int,
    *,
    type: str | None = None,
    due_from: str | None = None,
    due_to: str | None = None,
) -> tuple[list[Any], list[Any], dict[tuple[str, int], GradedSubmission]]:
    """Return (assignments, students, cells) for a per-group matrix.

    ``cells`` is keyed by ``(student_id, assignment_id)``. Students
    without a submission row for some assignment are absent from the
    map (the renderer shows "—").
    """
    init_db()
    from education_system.sixthform_system.modules.domain.class_groups import class_groups
    from education_system.sixthform_system.modules.domain.homework import homework
    from education_system.sixthform_system.modules.domain.students import students as _cg
    from education_system.sixthform_system.modules.domain.homework import homework as _hw
    from education_system.sixthform_system.modules.domain.students import students as _students
    assns = _hw.list_assignments(
        group_id=group_id, type=type, due_from=due_from, due_to=due_to)
    members = _cg.list_members(group_id)
    student_index = {s.student_id: s for s in _students.list_students()
                     if s.student_id in members}
    student_objs = [student_index[m] for m in members if m in student_index]

    cells: dict[tuple[str, int], GradedSubmission] = {}
    for gs in graded_submissions_for_group(
            group_id, type=type, due_from=due_from, due_to=due_to):
        cells[(gs.student_id, gs.assignment_id)] = gs
    return assns, student_objs, cells


def student_summary(
    student_id: str,
    *,
    group_id: int | None = None,
) -> StudentGradebookSummary:
    """Per-student summary across all (or one group's) assignments."""
    init_db()
    from education_system.sixthform_system.modules.domain.homework import homework as _hw

    if group_id is not None:
        assns = _hw.list_assignments(group_id=group_id)
    else:
        assns = _hw.list_assignments()

    if not assns:
        return StudentGradebookSummary(
            student_id=student_id, total_assignments=0, marked=0,
            avg_pct=None, best_letter=None, worst_letter=None,
        )

    aid_index = {a.assignment_id: a for a in assns}
    grade_rows: list[GradedSubmission] = []
    for gs in graded_submissions_for_student(student_id):
        if gs.assignment_id in aid_index:
            grade_rows.append(gs)

    marked = [g for g in grade_rows
              if g.percentage is not None and g.letter is not None]
    if not marked:
        return StudentGradebookSummary(
            student_id=student_id, total_assignments=len(assns),
            marked=0, avg_pct=None,
            best_letter=None, worst_letter=None,
        )

    avg_pct = round(sum(g.percentage for g in marked) / len(marked), 1)
    # Best = highest letter (lowest index in LETTER_GRADES).
    ordered_letters = sorted(
        {g.letter for g in marked if g.letter},
        key=lambda lg: LETTER_GRADES.index(lg) if lg in LETTER_GRADES else 99,
    )
    best = ordered_letters[0] if ordered_letters else None
    worst = ordered_letters[-1] if ordered_letters else None

    return StudentGradebookSummary(
        student_id=student_id, total_assignments=len(assns),
        marked=len(marked), avg_pct=avg_pct,
        best_letter=best, worst_letter=worst,
    )
