"""Marking, moderation and rubrics for coursework assignments.

Sibling to :mod:`assignments`, which owns assignments, submissions and
files. This module owns everything that happens *to a mark*:

* **Rubric criteria** — the brief's mark scheme as rows rather than a
  text blob, so marking can be per-criterion and analysed afterwards.
* **Per-criterion marks** — one score per (submission, criterion,
  marker), summing to the marker's total.
* **Grade boundaries** — per-assignment raw-mark thresholds, falling
  back to the college's standard A-Level percentages.
* **Second marking and moderation** — independent marks per role, a
  discrepancy check against the assignment's tolerance, and a recorded
  resolution.
* **Standardisation samples** — the top/middle/bottom spread a
  department sends to a moderator.
* **Late penalties** — a policy applied to the awarded mark, with the
  raw mark preserved so the deduction is always reversible.
* **Access arrangements** — exam-access entitlements from the pastoral
  ``accessibility`` module, turned into deadline uplifts.
* **Mark audit trail** — every change to a mark or grade, with who,
  when and why.
* **Comment bank** — reusable department feedback.
* **Bulk marking** — validate-then-apply a whole class in one pass.

The marking pipeline
--------------------
:func:`apply_marks` is the single place a mark is written::

    raw mark  →  late penalty  →  final mark  →  grade boundary  →  audit

Everything else (per-criterion totals, moderation resolution, bulk
marking, :func:`assignments.mark_submission`) funnels through it, so a
mark can never reach the database having skipped the penalty, the
boundary table or the audit row.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.academics.assignments import (
    assignments as core,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ASSIGNMENTS_DB

ValidationError = core.ValidationError


# ── Vocabularies ──────────────────────────────────────────────────

# Who awarded a mark. 'First' is the class teacher; 'Second' is the
# independent second marker; 'Moderator' is the person who resolves a
# disagreement between them.
MARKER_ROLES: tuple[str, ...] = ("First", "Second", "Moderator")
DEFAULT_MARKER_ROLE: str = "First"

# Where a sampled script sits in the cohort — a moderator expects a
# spread, not five scripts from the middle.
SAMPLE_BANDS: tuple[str, ...] = ("Top", "Middle", "Bottom", "Borderline")

COMMENT_CATEGORIES: tuple[str, ...] = (
    "Strength", "Development", "Target", "Technique",
    "Referencing", "Presentation", "Effort", "General",
)
DEFAULT_COMMENT_CATEGORY: str = "General"

# What caused a mark to change. Recorded on every audit row so a later
# reader can tell a marker's decision from a policy's arithmetic.
AUDIT_SOURCES: tuple[str, ...] = (
    "manual", "criterion", "penalty", "moderation", "bulk", "import",
)

# Letter grades and the college's default percentage thresholds are
# owned by the gradebook — import them so an A* means one thing.
LETTER_GRADES: tuple[str, ...] = ("A*", "A", "B", "C", "D", "E", "U")
DEFAULT_BOUNDARIES_PCT: tuple[tuple[str, float], ...] = (
    ("A*", 90.0), ("A", 80.0), ("B", 70.0),
    ("C", 60.0), ("D", 50.0), ("E", 40.0),
)

# Boundary columns, in descending order. Used for both storage and
# resolution, so the two can never drift apart.
_BOUNDARY_COLUMNS: tuple[tuple[str, str], ...] = (
    ("a_star", "A*"), ("a", "A"), ("b", "B"),
    ("c", "C"), ("d", "D"), ("e", "E"),
)

# "25% extra time" → 25.0. Anything else in the arrangement name is
# ignored; free-text arrangements that carry no percentage simply
# contribute no uplift.
_EXTRA_TIME_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%\s*extra\s*time",
                             re.IGNORECASE)

# A coursework deadline is a window, not a timed paper, so extra time
# is converted into extra days across that window.
MIN_ACCESS_EXTENSION_DAYS: int = 1


_SCHEMA = """
CREATE TABLE IF NOT EXISTS coursework_rubric_criteria (
    criterion_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id     INTEGER NOT NULL,
    position          INTEGER NOT NULL DEFAULT 0,
    code              TEXT,
    title             TEXT NOT NULL,
    descriptor        TEXT,
    max_marks         REAL NOT NULL,
    weight_percent    REAL,
    assessment_objective TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (assignment_id) REFERENCES coursework_assignments(assignment_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS coursework_criterion_marks (
    criterion_mark_id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id     INTEGER NOT NULL,
    criterion_id      INTEGER NOT NULL,
    role              TEXT NOT NULL DEFAULT 'First',
    marks             REAL,
    comment           TEXT,
    marked_by         TEXT,
    marked_on         TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (submission_id) REFERENCES coursework_submissions(submission_id)
        ON DELETE CASCADE,
    FOREIGN KEY (criterion_id) REFERENCES coursework_rubric_criteria(criterion_id)
        ON DELETE CASCADE,
    UNIQUE (submission_id, criterion_id, role)
);

CREATE TABLE IF NOT EXISTS coursework_grade_boundaries (
    assignment_id     INTEGER PRIMARY KEY,
    a_star            REAL,
    a                 REAL,
    b                 REAL,
    c                 REAL,
    d                 REAL,
    e                 REAL,
    notes             TEXT,
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (assignment_id) REFERENCES coursework_assignments(assignment_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS coursework_marks (
    mark_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id     INTEGER NOT NULL,
    role              TEXT NOT NULL,
    marks             REAL,
    grade             TEXT,
    feedback          TEXT,
    marked_by         TEXT,
    marked_on         TEXT,
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (submission_id) REFERENCES coursework_submissions(submission_id)
        ON DELETE CASCADE,
    UNIQUE (submission_id, role)
);

CREATE TABLE IF NOT EXISTS coursework_mark_audit (
    audit_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id     INTEGER NOT NULL,
    field             TEXT NOT NULL,
    old_value         TEXT,
    new_value         TEXT,
    source            TEXT NOT NULL DEFAULT 'manual',
    reason            TEXT,
    changed_by        TEXT,
    changed_at        TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (submission_id) REFERENCES coursework_submissions(submission_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS coursework_comment_bank (
    comment_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_name      TEXT,
    category          TEXT NOT NULL DEFAULT 'General',
    code              TEXT,
    body              TEXT NOT NULL,
    is_active         INTEGER NOT NULL DEFAULT 1,
    use_count         INTEGER NOT NULL DEFAULT 0,
    created_by        TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_cwcrit_assign
    ON coursework_rubric_criteria(assignment_id);
CREATE INDEX IF NOT EXISTS idx_cwcritmark_sub
    ON coursework_criterion_marks(submission_id);
CREATE INDEX IF NOT EXISTS idx_cwcritmark_crit
    ON coursework_criterion_marks(criterion_id);
CREATE INDEX IF NOT EXISTS idx_cwmarks_sub
    ON coursework_marks(submission_id);
CREATE INDEX IF NOT EXISTS idx_cwaudit_sub
    ON coursework_mark_audit(submission_id);
CREATE INDEX IF NOT EXISTS idx_cwbank_subject
    ON coursework_comment_bank(subject_name);
CREATE INDEX IF NOT EXISTS idx_cwbank_category
    ON coursework_comment_bank(category);
"""


# ── Dataclasses ───────────────────────────────────────────────────

@dataclass
class Criterion:
    criterion_id: int
    assignment_id: int
    position: int
    code: str | None
    title: str
    descriptor: str | None
    max_marks: float
    weight_percent: float | None
    assessment_objective: str | None
    created_at: str
    updated_at: str

    @property
    def label(self) -> str:
        return f"{self.code} {self.title}" if self.code else self.title


@dataclass
class CriterionMark:
    criterion_mark_id: int
    submission_id: int
    criterion_id: int
    role: str
    marks: float | None
    comment: str | None
    marked_by: str | None
    marked_on: str | None
    created_at: str
    updated_at: str


@dataclass
class GradeBoundaries:
    assignment_id: int
    a_star: float | None
    a: float | None
    b: float | None
    c: float | None
    d: float | None
    e: float | None
    notes: str | None
    updated_at: str

    @property
    def is_set(self) -> bool:
        return any(getattr(self, col) is not None
                    for col, _ in _BOUNDARY_COLUMNS)

    def as_pairs(self) -> list[tuple[str, float | None]]:
        return [(letter, getattr(self, col))
                for col, letter in _BOUNDARY_COLUMNS]


@dataclass
class Mark:
    """One marker's independent judgement on a submission."""

    mark_id: int
    submission_id: int
    role: str
    marks: float | None
    grade: str | None
    feedback: str | None
    marked_by: str | None
    marked_on: str | None
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class MarkAudit:
    audit_id: int
    submission_id: int
    field: str
    old_value: str | None
    new_value: str | None
    source: str
    reason: str | None
    changed_by: str | None
    changed_at: str


@dataclass
class BankComment:
    comment_id: int
    subject_name: str | None
    category: str
    code: str | None
    body: str
    is_active: bool
    use_count: int
    created_by: str | None
    created_at: str
    updated_at: str

    @property
    def label(self) -> str:
        head = self.body.splitlines()[0] if self.body else ""
        if len(head) > 60:
            head = head[:57] + "..."
        return f"[{self.category}] {head}"


@dataclass
class LatePenalty:
    """What the assignment's late policy costs this submission."""

    days_late: int = 0
    percent: float = 0.0
    waived: bool = False
    waived_reason: str | None = None
    capped: bool = False

    @property
    def applies(self) -> bool:
        return self.percent > 0 and not self.waived

    def apply_to(self, raw: float | None) -> float | None:
        if raw is None or not self.applies:
            return raw
        return round(raw * (1.0 - self.percent / 100.0), 2)

    @property
    def message(self) -> str:
        if self.waived:
            return (f"{self.days_late} day(s) late — penalty waived"
                    + (f" ({self.waived_reason})"
                        if self.waived_reason else ""))
        if not self.days_late:
            return "On time"
        if not self.percent:
            return f"{self.days_late} day(s) late — no penalty policy set"
        cap = " (capped)" if self.capped else ""
        return (f"{self.days_late} day(s) late — "
                f"{self.percent:.0f}% deducted{cap}")


@dataclass
class RubricTotal:
    """How the rubric's criteria add up against the assignment's max."""

    criterion_count: int
    total_max: float
    assignment_max: float | None

    @property
    def matches(self) -> bool:
        if self.assignment_max is None or not self.criterion_count:
            return True
        return abs(self.total_max - self.assignment_max) < 0.001

    @property
    def message(self) -> str:
        if not self.criterion_count:
            return "No rubric criteria defined"
        if self.assignment_max is None:
            return (f"{self.criterion_count} criteria totalling "
                    f"{self.total_max:g} (assignment has no max marks)")
        if self.matches:
            return (f"{self.criterion_count} criteria totalling "
                    f"{self.total_max:g} — matches the assignment max")
        return (f"{self.criterion_count} criteria total {self.total_max:g} "
                f"but the assignment max is {self.assignment_max:g}")


@dataclass
class Moderation:
    """First vs second mark on one submission."""

    submission_id: int
    first: float | None = None
    second: float | None = None
    moderator: float | None = None
    tolerance: float | None = None

    @property
    def discrepancy(self) -> float | None:
        if self.first is None or self.second is None:
            return None
        return round(abs(self.first - self.second), 2)

    @property
    def is_double_marked(self) -> bool:
        return self.first is not None and self.second is not None

    @property
    def needs_moderation(self) -> bool:
        gap = self.discrepancy
        if gap is None or self.tolerance is None:
            return False
        return gap > self.tolerance and self.moderator is None

    @property
    def message(self) -> str:
        if not self.is_double_marked:
            return "Not double marked"
        gap = self.discrepancy or 0.0
        if self.moderator is not None:
            return f"Gap {gap:g} — moderated to {self.moderator:g}"
        if self.tolerance is None:
            return f"Gap {gap:g} — no tolerance set"
        if gap > self.tolerance:
            return f"Gap {gap:g} exceeds tolerance {self.tolerance:g}"
        return f"Gap {gap:g} within tolerance {self.tolerance:g}"


@dataclass
class GridRow:
    """One student's line in the bulk-marking grid."""

    submission: core.Submission
    student_name: str
    criterion_marks: dict[int, float | None] = field(default_factory=dict)
    penalty: LatePenalty = field(default_factory=LatePenalty)
    moderation: Moderation | None = None
    access_arrangements: list[str] = field(default_factory=list)


@dataclass
class BulkOutcome:
    submission_id: int
    student_id: str
    ok: bool
    message: str


@dataclass
class BulkResult:
    applied: int
    failed: int
    outcomes: list[BulkOutcome] = field(default_factory=list)

    @property
    def all_ok(self) -> bool:
        return self.failed == 0


# ── DB plumbing ───────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    # The core tables are the FK targets for everything here, so they
    # must exist first.
    core.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    logger.debug("Marking schema ready at %s", DB_PATH)
    _DB_READY = True


def _row_criterion(r: sqlite3.Row) -> Criterion:
    return Criterion(
        criterion_id=r["criterion_id"],
        assignment_id=r["assignment_id"],
        position=r["position"], code=r["code"], title=r["title"],
        descriptor=r["descriptor"], max_marks=r["max_marks"],
        weight_percent=r["weight_percent"],
        assessment_objective=r["assessment_objective"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_criterion_mark(r: sqlite3.Row) -> CriterionMark:
    return CriterionMark(
        criterion_mark_id=r["criterion_mark_id"],
        submission_id=r["submission_id"],
        criterion_id=r["criterion_id"], role=r["role"],
        marks=r["marks"], comment=r["comment"],
        marked_by=r["marked_by"], marked_on=r["marked_on"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_boundaries(r: sqlite3.Row) -> GradeBoundaries:
    return GradeBoundaries(
        assignment_id=r["assignment_id"], a_star=r["a_star"],
        a=r["a"], b=r["b"], c=r["c"], d=r["d"], e=r["e"],
        notes=r["notes"], updated_at=r["updated_at"],
    )


def _row_mark(r: sqlite3.Row) -> Mark:
    return Mark(
        mark_id=r["mark_id"], submission_id=r["submission_id"],
        role=r["role"], marks=r["marks"], grade=r["grade"],
        feedback=r["feedback"], marked_by=r["marked_by"],
        marked_on=r["marked_on"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_audit(r: sqlite3.Row) -> MarkAudit:
    return MarkAudit(
        audit_id=r["audit_id"], submission_id=r["submission_id"],
        field=r["field"], old_value=r["old_value"],
        new_value=r["new_value"], source=r["source"],
        reason=r["reason"], changed_by=r["changed_by"],
        changed_at=r["changed_at"],
    )


def _row_comment(r: sqlite3.Row) -> BankComment:
    return BankComment(
        comment_id=r["comment_id"], subject_name=r["subject_name"],
        category=r["category"], code=r["code"], body=r["body"],
        is_active=bool(r["is_active"]), use_count=r["use_count"],
        created_by=r["created_by"], created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def _today() -> str:
    return _dt.date.today().isoformat()


def _require_submission(submission_id: int) -> core.Submission:
    sub = core.get_submission(submission_id)
    if sub is None:
        raise ValidationError(f"No submission #{submission_id}")
    return sub


def _require_assignment(assignment_id: int) -> core.Assignment:
    a = core.get_assignment(assignment_id)
    if a is None:
        raise ValidationError(f"No assignment #{assignment_id}")
    return a


def _validate_role(role: Any) -> str:
    value = (str(role).strip() if role not in (None, "")
              else DEFAULT_MARKER_ROLE)
    if value not in MARKER_ROLES:
        raise ValidationError(
            f"Marker role must be one of: {', '.join(MARKER_ROLES)}")
    return value


# ── Rubric criteria (item 12) ─────────────────────────────────────

def add_criterion(assignment_id: int, payload: dict[str, Any]) -> Criterion:
    """Add one row to an assignment's mark scheme."""
    init_db()
    _require_assignment(assignment_id)
    title = core._require(payload.get("title"), "Criterion title").strip()
    max_marks = core._validate_number(payload.get("max_marks"),
                                       "Criterion max marks", min_val=0)
    if max_marks is None:
        raise ValidationError("Criterion max marks is required")
    weight = core._validate_number(payload.get("weight_percent"),
                                    "Weight %", min_val=0, max_val=100)
    position = core._validate_number(payload.get("position"),
                                      "Position", min_val=0)
    if position is None:
        with _connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(position), 0) + 1 AS nxt "
                "FROM coursework_rubric_criteria WHERE assignment_id = ?",
                (assignment_id,)).fetchone()
        position = row["nxt"]

    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO coursework_rubric_criteria
                   (assignment_id, position, code, title, descriptor,
                    max_marks, weight_percent, assessment_objective,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (assignment_id, int(position),
             (payload.get("code") or "").strip() or None, title,
             (payload.get("descriptor") or "").strip() or None,
             max_marks, weight,
             (payload.get("assessment_objective") or "").strip() or None))
        conn.commit()
        new_id = int(cur.lastrowid or 0)
    out = get_criterion(new_id)
    assert out is not None
    logger.info("Added rubric criterion #%d %r (%g marks) to assignment #%d",
                new_id, title, max_marks, assignment_id)
    return out


def get_criterion(criterion_id: int) -> Criterion | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM coursework_rubric_criteria "
            "WHERE criterion_id = ?", (criterion_id,)).fetchone()
        return _row_criterion(r) if r else None


def list_criteria(assignment_id: int) -> list[Criterion]:
    init_db()
    with _connect() as conn:
        return [_row_criterion(r) for r in conn.execute(
            "SELECT * FROM coursework_rubric_criteria "
            "WHERE assignment_id = ? "
            "ORDER BY position ASC, criterion_id ASC",
            (int(assignment_id),)).fetchall()]


def update_criterion(criterion_id: int,
                      payload: dict[str, Any]) -> Criterion:
    init_db()
    existing = get_criterion(criterion_id)
    if existing is None:
        raise ValidationError(f"No criterion #{criterion_id}")
    title = core._require(
        payload.get("title", existing.title), "Criterion title").strip()
    max_marks = core._validate_number(
        payload.get("max_marks", existing.max_marks),
        "Criterion max marks", min_val=0)
    if max_marks is None:
        raise ValidationError("Criterion max marks is required")
    weight = core._validate_number(
        payload.get("weight_percent", existing.weight_percent),
        "Weight %", min_val=0, max_val=100)
    position = core._validate_number(
        payload.get("position", existing.position), "Position", min_val=0)

    def _text(key: str) -> str | None:
        value = payload.get(key, getattr(existing, key))
        return (str(value).strip() or None) if value else None

    with _connect() as conn:
        conn.execute(
            """UPDATE coursework_rubric_criteria SET
                   position = ?, code = ?, title = ?, descriptor = ?,
                   max_marks = ?, weight_percent = ?,
                   assessment_objective = ?,
                   updated_at = datetime('now')
               WHERE criterion_id = ?""",
            (int(position or 0), _text("code"), title,
             _text("descriptor"), max_marks, weight,
             _text("assessment_objective"), criterion_id))
        conn.commit()
    out = get_criterion(criterion_id)
    assert out is not None
    return out


def delete_criterion(criterion_id: int) -> bool:
    """Remove a criterion. Any marks awarded against it go too."""
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM coursework_rubric_criteria "
            "WHERE criterion_id = ?", (criterion_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted rubric criterion #%d (cascade: marks)",
                        criterion_id)
            return True
        return False


def reorder_criteria(assignment_id: int,
                      criterion_ids: list[int]) -> list[Criterion]:
    """Set the display order from a full list of this rubric's ids."""
    init_db()
    current = {c.criterion_id for c in list_criteria(assignment_id)}
    given = list(dict.fromkeys(int(c) for c in criterion_ids))
    if set(given) != current:
        raise ValidationError(
            "Reorder needs every criterion of the assignment exactly once")
    with _connect() as conn:
        conn.executemany(
            "UPDATE coursework_rubric_criteria SET position = ?, "
            "updated_at = datetime('now') WHERE criterion_id = ?",
            [(i, cid) for i, cid in enumerate(given, 1)])
        conn.commit()
    return list_criteria(assignment_id)


def rubric_total(assignment_id: int) -> RubricTotal:
    """Do the criteria add up to the assignment's max marks?

    Deliberately a report rather than a hard constraint — departments
    build a rubric over several sittings and shouldn't be blocked
    halfway.
    """
    a = _require_assignment(assignment_id)
    criteria = list_criteria(assignment_id)
    return RubricTotal(criterion_count=len(criteria),
                        total_max=round(sum(c.max_marks
                                             for c in criteria), 2),
                        assignment_max=a.max_marks)


# ── Per-criterion marking (item 13) ───────────────────────────────

def set_criterion_mark(submission_id: int, criterion_id: int, *,
                        marks: float | None,
                        role: str = DEFAULT_MARKER_ROLE,
                        comment: str | None = None,
                        marked_by: str | None = None) -> CriterionMark:
    """Score one criterion for one submission. Upserts."""
    init_db()
    sub = _require_submission(submission_id)
    criterion = get_criterion(criterion_id)
    if criterion is None:
        raise ValidationError(f"No criterion #{criterion_id}")
    if criterion.assignment_id != sub.assignment_id:
        raise ValidationError(
            f"Criterion #{criterion_id} belongs to assignment "
            f"#{criterion.assignment_id}, not #{sub.assignment_id}")
    value = core._validate_number(marks, "Criterion marks", min_val=0,
                                   max_val=criterion.max_marks)
    role_value = _validate_role(role)

    with _connect() as conn:
        conn.execute(
            """INSERT INTO coursework_criterion_marks
                   (submission_id, criterion_id, role, marks, comment,
                    marked_by, marked_on, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))
               ON CONFLICT (submission_id, criterion_id, role)
               DO UPDATE SET marks = excluded.marks,
                             comment = excluded.comment,
                             marked_by = excluded.marked_by,
                             marked_on = excluded.marked_on,
                             updated_at = datetime('now')""",
            (submission_id, criterion_id, role_value, value,
             (comment or "").strip() or None,
             (marked_by or "").strip() or None, _today()))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM coursework_criterion_marks "
            "WHERE submission_id = ? AND criterion_id = ? AND role = ?",
            (submission_id, criterion_id, role_value)).fetchone()
    return _row_criterion_mark(r)


def list_criterion_marks(submission_id: int, *,
                          role: str | None = None
                          ) -> list[CriterionMark]:
    init_db()
    clauses = ["m.submission_id = ?"]
    args: list[Any] = [int(submission_id)]
    if role:
        clauses.append("m.role = ?")
        args.append(_validate_role(role))
    with _connect() as conn:
        return [_row_criterion_mark(r) for r in conn.execute(
            "SELECT m.* FROM coursework_criterion_marks m "
            "JOIN coursework_rubric_criteria c "
            "  ON c.criterion_id = m.criterion_id "
            f"WHERE {' AND '.join(clauses)} "
            "ORDER BY c.position ASC, c.criterion_id ASC",
            args).fetchall()]


def criterion_total(submission_id: int, *,
                     role: str = DEFAULT_MARKER_ROLE) -> float | None:
    """Sum a marker's criterion scores, or None if nothing scored yet."""
    rows = [m.marks for m in list_criterion_marks(submission_id, role=role)
            if m.marks is not None]
    if not rows:
        return None
    return round(sum(rows), 2)


def criterion_coverage(submission_id: int, *,
                        role: str = DEFAULT_MARKER_ROLE
                        ) -> tuple[int, int]:
    """(scored, total) criteria — how complete this marking is."""
    sub = _require_submission(submission_id)
    total = len(list_criteria(sub.assignment_id))
    scored = len([m for m in list_criterion_marks(submission_id, role=role)
                  if m.marks is not None])
    return scored, total


def apply_criterion_total(submission_id: int, *,
                           role: str = DEFAULT_MARKER_ROLE,
                           marked_by: str | None = None,
                           feedback: str | None = None,
                           require_complete: bool = True) -> core.Submission:
    """Sum the criterion scores and push them through the pipeline.

    With ``require_complete`` (the default) a partly-marked rubric is
    refused — a half-finished total looks exactly like a low mark once
    it lands on the submission.
    """
    init_db()
    scored, total = criterion_coverage(submission_id, role=role)
    if total == 0:
        raise ValidationError(
            "This assignment has no rubric criteria to total")
    if require_complete and scored < total:
        raise ValidationError(
            f"Only {scored} of {total} criteria are scored — finish the "
            f"rubric or pass require_complete=False")
    subtotal = criterion_total(submission_id, role=role)
    if subtotal is None:
        raise ValidationError("No criterion marks to total")

    role_value = _validate_role(role)
    record_mark(submission_id, role=role_value, marks=subtotal,
                 marked_by=marked_by, feedback=feedback)
    if role_value == "First":
        return apply_marks(submission_id, raw_marks=subtotal,
                            marked_by=marked_by, feedback=feedback,
                            source="criterion",
                            reason=f"Sum of {scored} rubric criteria")
    return _require_submission(submission_id)


# ── Grade boundaries (item 14) ────────────────────────────────────

def set_grade_boundaries(assignment_id: int,
                          data: dict[str, Any]) -> GradeBoundaries:
    """Upsert raw-mark thresholds for one assignment.

    Accepts either column names (``a_star``) or letters (``A*``). A
    blank value clears that letter back to the percentage default.
    """
    init_db()
    a = _require_assignment(assignment_id)

    def _coerce(value: Any, label: str) -> float | None:
        parsed = core._validate_number(value, f"{label} boundary",
                                        min_val=0)
        if parsed is None:
            return None
        if a.max_marks is not None and parsed > a.max_marks:
            raise ValidationError(
                f"{label} boundary ({parsed:g}) exceeds the assignment "
                f"max marks ({a.max_marks:g})")
        return parsed

    values: dict[str, float | None] = {}
    for col, letter in _BOUNDARY_COLUMNS:
        raw: Any = None
        for key in (col, letter):
            if key in data:
                raw = data[key]
                break
        values[col] = _coerce(raw, letter)

    # A*, A, B... must descend, or the resolver would award the wrong
    # letter without anything looking obviously broken.
    ordered = [(letter, values[col]) for col, letter in _BOUNDARY_COLUMNS]
    seen = [(letter, v) for letter, v in ordered if v is not None]
    for (hi_letter, hi), (lo_letter, lo) in zip(seen, seen[1:]):
        if lo > hi:
            raise ValidationError(
                f"{lo_letter} boundary ({lo:g}) cannot be above "
                f"{hi_letter} ({hi:g})")

    with _connect() as conn:
        conn.execute(
            """INSERT INTO coursework_grade_boundaries
                   (assignment_id, a_star, a, b, c, d, e, notes,
                    updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT (assignment_id) DO UPDATE SET
                   a_star = excluded.a_star, a = excluded.a,
                   b = excluded.b, c = excluded.c, d = excluded.d,
                   e = excluded.e, notes = excluded.notes,
                   updated_at = datetime('now')""",
            (assignment_id, values["a_star"], values["a"], values["b"],
             values["c"], values["d"], values["e"],
             (data.get("notes") or "").strip() or None))
        conn.commit()
    out = get_grade_boundaries(assignment_id)
    assert out is not None
    logger.info("Set grade boundaries for assignment #%d: %s",
                assignment_id,
                ", ".join(f"{letter}={v:g}"
                          for letter, v in out.as_pairs()
                          if v is not None) or "(cleared)")
    return out


def get_grade_boundaries(assignment_id: int) -> GradeBoundaries | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM coursework_grade_boundaries "
            "WHERE assignment_id = ?", (int(assignment_id),)).fetchone()
        return _row_boundaries(r) if r else None


def clear_grade_boundaries(assignment_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM coursework_grade_boundaries "
            "WHERE assignment_id = ?", (int(assignment_id),))
        conn.commit()
        return bool(cur.rowcount)


def pct_to_letter(pct: float | None) -> str | None:
    """The college's standard A-Level letter for a percentage."""
    if pct is None:
        return None
    for letter, threshold in DEFAULT_BOUNDARIES_PCT:
        if pct >= threshold:
            return letter
    return "U"


def resolve_grade(assignment: core.Assignment,
                   marks: float | None
                   ) -> tuple[float | None, str | None]:
    """(percentage, letter) for a mark on this assignment.

    Per-assignment raw thresholds win. If only some letters are pinned,
    the rest fall back to the percentage defaults — a department often
    pins only A*/A after a standardisation meeting.
    """
    if marks is None or not assignment.max_marks:
        return None, None
    pct = round(100.0 * marks / assignment.max_marks, 1)
    boundaries = get_grade_boundaries(assignment.assignment_id)
    if boundaries is not None and boundaries.is_set:
        for letter, threshold in boundaries.as_pairs():
            if threshold is not None and marks >= threshold:
                return pct, letter
        # Below every pinned threshold: fall through to the default so
        # a part-filled table still yields a sensible lower grade.
    return pct, pct_to_letter(pct)


# ── Late penalties (item 10) ──────────────────────────────────────

def _days_late(assignment: core.Assignment,
                submission: core.Submission) -> int:
    """Whole days between the effective deadline and the hand-in."""
    due = core.effective_due_date(submission, assignment)
    if not due or not submission.submitted_on:
        return 0
    try:
        delta = (_dt.date.fromisoformat(submission.submitted_on)
                 - _dt.date.fromisoformat(due)).days
    except ValueError:
        return 0
    return max(0, delta)


def compute_late_penalty(assignment: core.Assignment,
                          submission: core.Submission) -> LatePenalty:
    """What the assignment's policy costs this submission.

    Days are counted from the student's *effective* deadline, so an
    approved extension shifts the penalty clock rather than sitting
    awkwardly alongside it.
    """
    days = _days_late(assignment, submission)
    penalty = LatePenalty(days_late=days,
                           waived=bool(submission.penalty_waived),
                           waived_reason=submission.penalty_waived_reason)
    rate = assignment.late_penalty_percent_per_day
    if not days or not rate:
        return penalty
    chargeable = max(0, days - (assignment.late_penalty_grace_days or 0))
    if not chargeable:
        return penalty
    percent = rate * chargeable
    cap = assignment.late_penalty_cap_percent
    if cap is not None and percent > cap:
        percent = cap
        penalty.capped = True
    penalty.percent = round(min(percent, 100.0), 2)
    return penalty


def waive_penalty(submission_id: int, *, reason: str,
                   waived_by: str | None = None) -> core.Submission:
    """Set aside the late penalty for one student, and re-apply marks."""
    init_db()
    sub = _require_submission(submission_id)
    reason_text = core._require(reason, "Waiver reason").strip()
    with _connect() as conn:
        conn.execute(
            "UPDATE coursework_submissions SET penalty_waived = 1, "
            "penalty_waived_reason = ?, updated_at = datetime('now') "
            "WHERE submission_id = ?", (reason_text, submission_id))
        conn.commit()
    record_mark_change(submission_id, field="penalty_waived",
                        old_value="0", new_value="1", source="penalty",
                        reason=reason_text, changed_by=waived_by)
    logger.info("Late penalty waived on submission #%d (%s): %s",
                submission_id, sub.student_id, reason_text)
    return _recompute_marks(submission_id, changed_by=waived_by,
                             reason="Penalty waived")


def restore_penalty(submission_id: int, *,
                     restored_by: str | None = None) -> core.Submission:
    """Undo a waiver and re-apply the policy."""
    init_db()
    _require_submission(submission_id)
    with _connect() as conn:
        conn.execute(
            "UPDATE coursework_submissions SET penalty_waived = 0, "
            "penalty_waived_reason = NULL, "
            "updated_at = datetime('now') WHERE submission_id = ?",
            (submission_id,))
        conn.commit()
    record_mark_change(submission_id, field="penalty_waived",
                        old_value="1", new_value="0", source="penalty",
                        reason="Waiver withdrawn",
                        changed_by=restored_by)
    return _recompute_marks(submission_id, changed_by=restored_by,
                             reason="Penalty waiver withdrawn")


def _recompute_marks(submission_id: int, *,
                      changed_by: str | None,
                      reason: str) -> core.Submission:
    """Re-run the pipeline over the stored raw mark, if there is one."""
    sub = _require_submission(submission_id)
    if sub.raw_marks is None:
        return sub
    return apply_marks(submission_id, raw_marks=sub.raw_marks,
                        marked_by=sub.marked_by, source="penalty",
                        reason=reason, changed_by=changed_by)


# ── The marking pipeline ──────────────────────────────────────────

def apply_marks(submission_id: int, *,
                 raw_marks: float | None,
                 grade: str | None = None,
                 feedback: str | None = None,
                 marked_by: str | None = None,
                 status: str | None = "Returned",
                 source: str = "manual",
                 reason: str | None = None,
                 changed_by: str | None = None) -> core.Submission:
    """Write a mark, applying penalty, boundaries and audit in order.

    This is the only function that writes ``marks``/``grade``/
    ``raw_marks``; everything else routes through it so a mark can
    never land having skipped a step.

    ``raw_marks`` is what the marker awarded. ``marks`` is what counts
    after any late penalty — the raw figure stays on the row so the
    deduction can always be explained or undone.
    """
    init_db()
    sub = _require_submission(submission_id)
    a = _require_assignment(sub.assignment_id)

    value = core._validate_number(raw_marks, "Marks", min_val=0)
    if value is not None and a.max_marks is not None \
            and value > a.max_marks:
        raise ValidationError(
            f"Marks ({value:g}) exceed max_marks ({a.max_marks:g})")

    penalty = compute_late_penalty(a, sub)
    final = penalty.apply_to(value)
    if grade is None:
        _, grade = resolve_grade(a, final)

    old = {"raw_marks": sub.raw_marks, "marks": sub.marks,
           "grade": sub.grade}
    new = {"raw_marks": value, "marks": final, "grade": grade}

    with _connect() as conn:
        conn.execute(
            """UPDATE coursework_submissions SET
                   raw_marks = ?, marks = ?, grade = ?,
                   penalty_percent = ?, penalty_days = ?,
                   feedback = COALESCE(?, feedback),
                   marked_by = COALESCE(?, marked_by),
                   marked_on = ?,
                   status = COALESCE(?, status),
                   updated_at = datetime('now')
               WHERE submission_id = ?""",
            (value, final, grade,
             penalty.percent if penalty.applies else None,
             penalty.days_late or None,
             (feedback or "").strip() or None,
             (marked_by or "").strip() or None,
             _today() if value is not None else sub.marked_on,
             status, submission_id))
        conn.commit()

    for field_name, before in old.items():
        after = new[field_name]
        if before != after:
            record_mark_change(
                submission_id, field=field_name,
                old_value=None if before is None else f"{before:g}"
                if isinstance(before, (int, float)) else str(before),
                new_value=None if after is None else f"{after:g}"
                if isinstance(after, (int, float)) else str(after),
                source=source, reason=reason,
                changed_by=changed_by or marked_by)

    out = _require_submission(submission_id)
    if penalty.applies:
        logger.info(
            "Submission #%d marked %s raw → %s after %s",
            submission_id, value, final, penalty.message)
    else:
        logger.info("Submission #%d marked %s (grade %s)",
                     submission_id, final, grade or "—")
    return out


# ── Second marking and moderation (item 15) ───────────────────────

def record_mark(submission_id: int, *,
                 role: str = DEFAULT_MARKER_ROLE,
                 marks: float | None = None,
                 grade: str | None = None,
                 feedback: str | None = None,
                 marked_by: str | None = None,
                 notes: str | None = None) -> Mark:
    """Store one marker's independent judgement. Upserts on role.

    Recording a second mark deliberately does *not* change the
    submission's mark — that only happens when the two agree inside
    tolerance, or a moderator resolves them.
    """
    init_db()
    sub = _require_submission(submission_id)
    a = _require_assignment(sub.assignment_id)
    role_value = _validate_role(role)
    value = core._validate_number(marks, "Marks", min_val=0)
    if value is not None and a.max_marks is not None \
            and value > a.max_marks:
        raise ValidationError(
            f"Marks ({value:g}) exceed max_marks ({a.max_marks:g})")
    if grade is None:
        _, grade = resolve_grade(a, value)

    with _connect() as conn:
        conn.execute(
            """INSERT INTO coursework_marks
                   (submission_id, role, marks, grade, feedback,
                    marked_by, marked_on, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))
               ON CONFLICT (submission_id, role) DO UPDATE SET
                   marks = excluded.marks, grade = excluded.grade,
                   feedback = excluded.feedback,
                   marked_by = excluded.marked_by,
                   marked_on = excluded.marked_on,
                   notes = excluded.notes,
                   updated_at = datetime('now')""",
            (submission_id, role_value, value, grade,
             (feedback or "").strip() or None,
             (marked_by or "").strip() or None, _today(),
             (notes or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM coursework_marks "
            "WHERE submission_id = ? AND role = ?",
            (submission_id, role_value)).fetchone()
    logger.info("Recorded %s mark %s on submission #%d by %s",
                role_value, value, submission_id,
                marked_by or "(unrecorded)")
    return _row_mark(r)


def list_marks(submission_id: int) -> list[Mark]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM coursework_marks WHERE submission_id = ?",
            (int(submission_id),)).fetchall()
    order = {role: i for i, role in enumerate(MARKER_ROLES)}
    return sorted((_row_mark(r) for r in rows),
                   key=lambda m: order.get(m.role, 99))


def get_mark(submission_id: int, role: str) -> Mark | None:
    role_value = _validate_role(role)
    return next((m for m in list_marks(submission_id)
                  if m.role == role_value), None)


def moderation_state(submission_id: int) -> Moderation:
    """First vs second mark, judged against the assignment tolerance."""
    sub = _require_submission(submission_id)
    a = _require_assignment(sub.assignment_id)
    by_role = {m.role: m.marks for m in list_marks(submission_id)}
    return Moderation(submission_id=submission_id,
                       first=by_role.get("First"),
                       second=by_role.get("Second"),
                       moderator=by_role.get("Moderator"),
                       tolerance=a.moderation_tolerance)


def list_for_moderation(*, assignment_id: int | None = None
                         ) -> list[Moderation]:
    """Double-marked submissions whose markers disagree too much."""
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if assignment_id is not None:
        clauses.append("assignment_id = ?")
        args.append(int(assignment_id))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        ids = [r["submission_id"] for r in conn.execute(
            f"SELECT submission_id FROM coursework_submissions {where} "
            "ORDER BY submission_id ASC", args).fetchall()]
    out = [moderation_state(sid) for sid in ids]
    return [m for m in out if m.needs_moderation]


def resolve_moderation(submission_id: int, *,
                        marks: float,
                        resolved_by: str | None = None,
                        note: str | None = None) -> core.Submission:
    """Settle a first/second disagreement and set the final mark."""
    init_db()
    state = moderation_state(submission_id)
    if not state.is_double_marked:
        raise ValidationError(
            "This submission has no first and second mark to resolve")
    record_mark(submission_id, role="Moderator", marks=marks,
                 marked_by=resolved_by, notes=note)
    reason = note or (f"Moderated: first {state.first:g}, "
                      f"second {state.second:g}")
    return apply_marks(submission_id, raw_marks=marks,
                        marked_by=resolved_by, source="moderation",
                        reason=reason, changed_by=resolved_by)


# ── Standardisation samples (item 16) ─────────────────────────────

def flag_sample(submission_id: int, *, band: str,
                 note: str | None = None,
                 flagged_by: str | None = None) -> core.Submission:
    """Mark one submission as part of the standardisation sample."""
    init_db()
    _require_submission(submission_id)
    value = str(band or "").strip()
    if value not in SAMPLE_BANDS:
        raise ValidationError(
            f"Sample band must be one of: {', '.join(SAMPLE_BANDS)}")
    with _connect() as conn:
        conn.execute(
            "UPDATE coursework_submissions SET sample_band = ?, "
            "sample_note = ?, sample_by = ?, sample_on = ?, "
            "updated_at = datetime('now') WHERE submission_id = ?",
            (value, (note or "").strip() or None,
             (flagged_by or "").strip() or None, _today(),
             submission_id))
        conn.commit()
    return _require_submission(submission_id)


def unflag_sample(submission_id: int) -> core.Submission:
    init_db()
    _require_submission(submission_id)
    with _connect() as conn:
        conn.execute(
            "UPDATE coursework_submissions SET sample_band = NULL, "
            "sample_note = NULL, sample_by = NULL, sample_on = NULL, "
            "updated_at = datetime('now') WHERE submission_id = ?",
            (submission_id,))
        conn.commit()
    return _require_submission(submission_id)


def list_samples(*, assignment_id: int | None = None
                  ) -> list[core.Submission]:
    init_db()
    clauses = ["sample_band IS NOT NULL"]
    args: list[Any] = []
    if assignment_id is not None:
        clauses.append("assignment_id = ?")
        args.append(int(assignment_id))
    with _connect() as conn:
        return [core._row_submission(r) for r in conn.execute(
            "SELECT * FROM coursework_submissions WHERE "
            + " AND ".join(clauses)
            + " ORDER BY assignment_id ASC, marks DESC",
            args).fetchall()]


def auto_select_sample(assignment_id: int, *,
                        per_band: int = 2,
                        flagged_by: str | None = None,
                        replace: bool = True) -> list[core.Submission]:
    """Pick a top / middle / bottom spread from the marked cohort.

    Boards want the range evidenced, not the department's favourites,
    so this takes the highest, lowest and middle marks mechanically.
    """
    init_db()
    _require_assignment(assignment_id)
    if per_band < 1:
        raise ValidationError("per_band must be at least 1")
    marked = [s for s in core.list_submissions(assignment_id=assignment_id)
              if s.marks is not None]
    if not marked:
        raise ValidationError(
            "Nothing is marked yet — a sample needs marks to rank")
    ranked = sorted(marked, key=lambda s: (s.marks or 0), reverse=True)

    if replace:
        for s in list_samples(assignment_id=assignment_id):
            unflag_sample(s.submission_id)

    take = min(per_band, len(ranked))
    chosen: dict[int, str] = {}
    for s in ranked[:take]:
        chosen[s.submission_id] = "Top"
    for s in ranked[-take:]:
        chosen.setdefault(s.submission_id, "Bottom")
    middle_start = max(0, (len(ranked) - take) // 2)
    for s in ranked[middle_start:middle_start + take]:
        chosen.setdefault(s.submission_id, "Middle")

    out: list[core.Submission] = []
    for submission_id, band in chosen.items():
        out.append(flag_sample(submission_id, band=band,
                                note="Auto-selected standardisation sample",
                                flagged_by=flagged_by))
    logger.info("Auto-selected %d sample(s) for assignment #%d",
                len(out), assignment_id)
    return sorted(out, key=lambda s: -(s.marks or 0))


# ── Mark audit trail (item 17) ────────────────────────────────────

def record_mark_change(submission_id: int, *, field: str,
                        old_value: str | None,
                        new_value: str | None,
                        source: str = "manual",
                        reason: str | None = None,
                        changed_by: str | None = None) -> MarkAudit:
    """Append one row to the mark audit trail."""
    init_db()
    source_value = str(source or "manual").strip()
    if source_value not in AUDIT_SOURCES:
        raise ValidationError(
            f"Audit source must be one of: {', '.join(AUDIT_SOURCES)}")
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO coursework_mark_audit
                   (submission_id, field, old_value, new_value, source,
                    reason, changed_by, changed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (submission_id, field, old_value, new_value, source_value,
             (reason or "").strip() or None,
             (changed_by or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM coursework_mark_audit WHERE audit_id = ?",
            (cur.lastrowid,)).fetchone()
    return _row_audit(r)


def list_mark_audit(*, submission_id: int | None = None,
                     assignment_id: int | None = None,
                     field: str | None = None,
                     limit: int | None = None) -> list[MarkAudit]:
    """The change history, newest first."""
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if submission_id is not None:
        clauses.append("t.submission_id = ?")
        args.append(int(submission_id))
    if assignment_id is not None:
        clauses.append(
            "t.submission_id IN (SELECT submission_id "
            "FROM coursework_submissions WHERE assignment_id = ?)")
        args.append(int(assignment_id))
    if field:
        clauses.append("t.field = ?")
        args.append(str(field).strip())
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT t.* FROM coursework_mark_audit t {where} "
           "ORDER BY t.audit_id DESC")
    if limit:
        sql += f" LIMIT {int(limit)}"
    with _connect() as conn:
        return [_row_audit(r) for r in conn.execute(sql, args).fetchall()]


# ── Comment bank (item 18) ────────────────────────────────────────

def add_comment(payload: dict[str, Any]) -> BankComment:
    init_db()
    body = core._require(payload.get("body"), "Comment body").strip()
    category = (payload.get("category")
                 or DEFAULT_COMMENT_CATEGORY).strip()
    if category not in COMMENT_CATEGORIES:
        raise ValidationError(
            f"Category must be one of: {', '.join(COMMENT_CATEGORIES)}")
    subject = (payload.get("subject_name") or "").strip() or None
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO coursework_comment_bank
                   (subject_name, category, code, body, is_active,
                    use_count, created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, 1, 0, ?,
                       datetime('now'), datetime('now'))""",
            (subject, category,
             (payload.get("code") or "").strip() or None, body,
             (payload.get("created_by") or "").strip() or None))
        conn.commit()
        new_id = int(cur.lastrowid or 0)
    out = get_comment(new_id)
    assert out is not None
    return out


def get_comment(comment_id: int) -> BankComment | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM coursework_comment_bank WHERE comment_id = ?",
            (comment_id,)).fetchone()
        return _row_comment(r) if r else None


def list_comments(*, subject_name: str | None = None,
                   category: str | None = None,
                   query: str | None = None,
                   include_inactive: bool = False) -> list[BankComment]:
    """Comments for a subject, plus the college-wide ones.

    A subject filter is inclusive of shared comments (``subject_name``
    NULL) — a history teacher wants the department bank *and* the
    generic referencing comments.
    """
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if not include_inactive:
        clauses.append("is_active = 1")
    if subject_name:
        clauses.append("(subject_name IS NULL OR subject_name = ?)")
        args.append(subject_name.strip())
    if category:
        clauses.append("category = ?")
        args.append(category.strip())
    if query:
        clauses.append("(body LIKE ? OR code LIKE ?)")
        args.extend([f"%{query.strip()}%"] * 2)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        return [_row_comment(r) for r in conn.execute(
            f"SELECT * FROM coursework_comment_bank {where} "
            "ORDER BY use_count DESC, comment_id ASC",
            args).fetchall()]


def update_comment(comment_id: int,
                    payload: dict[str, Any]) -> BankComment:
    init_db()
    existing = get_comment(comment_id)
    if existing is None:
        raise ValidationError(f"No comment #{comment_id}")
    body = core._require(payload.get("body", existing.body),
                          "Comment body").strip()
    category = str(payload.get("category", existing.category)).strip()
    if category not in COMMENT_CATEGORIES:
        raise ValidationError(
            f"Category must be one of: {', '.join(COMMENT_CATEGORIES)}")
    subject = payload.get("subject_name", existing.subject_name)
    code = payload.get("code", existing.code)
    active = payload.get("is_active", existing.is_active)
    with _connect() as conn:
        conn.execute(
            """UPDATE coursework_comment_bank SET
                   subject_name = ?, category = ?, code = ?, body = ?,
                   is_active = ?, updated_at = datetime('now')
               WHERE comment_id = ?""",
            ((str(subject).strip() or None) if subject else None,
             category, (str(code).strip() or None) if code else None,
             body, 0 if active in (False, 0, "0", "No", "no") else 1,
             comment_id))
        conn.commit()
    out = get_comment(comment_id)
    assert out is not None
    return out


def delete_comment(comment_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM coursework_comment_bank WHERE comment_id = ?",
            (comment_id,))
        conn.commit()
        return bool(cur.rowcount)


def use_comment(comment_id: int, *,
                 submission_id: int | None = None) -> str:
    """Return a comment's body, expanded, and count the use.

    The counter is what makes the bank self-sorting: the comments a
    department actually reaches for rise to the top of the picker.
    """
    init_db()
    comment = get_comment(comment_id)
    if comment is None:
        raise ValidationError(f"No comment #{comment_id}")
    with _connect() as conn:
        conn.execute(
            "UPDATE coursework_comment_bank SET use_count = use_count + 1, "
            "updated_at = datetime('now') WHERE comment_id = ?",
            (comment_id,))
        conn.commit()
    if submission_id is None:
        return comment.body
    return expand_comment(comment.body, submission_id)


def expand_comment(body: str, submission_id: int) -> str:
    """Substitute ``{first_name}``/``{grade}``-style placeholders.

    Unknown placeholders are left alone rather than raising — a comment
    with a stray brace should still reach the student.
    """
    sub = _require_submission(submission_id)
    a = core.get_assignment(sub.assignment_id)
    values: dict[str, str] = {
        "student_id": sub.student_id,
        "first_name": sub.student_id,
        "full_name": sub.student_id,
        "marks": "" if sub.marks is None else f"{sub.marks:g}",
        "raw_marks": ("" if sub.raw_marks is None
                       else f"{sub.raw_marks:g}"),
        "grade": sub.grade or "",
        "max_marks": ("" if not a or a.max_marks is None
                       else f"{a.max_marks:g}"),
        "title": a.title if a else "",
        "subject_name": a.subject_name if a else "",
    }
    try:
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        student = _students.get_student(sub.student_id)
        if student is not None:
            values["first_name"] = student.first_name
            values["full_name"] = student.full_name
    except Exception:
        logger.debug("Could not resolve student for comment expansion",
                      exc_info=True)

    def _sub(match: re.Match[str]) -> str:
        key = match.group(1)
        return values.get(key, match.group(0))

    return re.sub(r"\{(\w+)\}", _sub, str(body or ""))


# ── Access arrangements (item 11) ─────────────────────────────────

def access_arrangements_for(student_id: str) -> list[str]:
    """Current exam-access arrangement names for a student.

    Reads the pastoral ``accessibility`` module. Best-effort: a college
    that has not populated SEND data must still be able to mark.
    """
    try:
        from education_system.systems.sixth_form.domain.pastoral.accessibility import (
            accessibility as _acc,
        )
        rows = _acc.accommodations_for_student(str(student_id).strip())
    except Exception:
        logger.debug("Accessibility data unavailable for %s",
                      student_id, exc_info=True)
        return []
    return [a.name for a in rows
            if a.category == "Exam Access" and a.is_current]


def extra_time_percent(student_id: str) -> float | None:
    """The largest extra-time entitlement a student holds, as a percent."""
    found = [float(m.group(1))
             for name in access_arrangements_for(student_id)
             if (m := _EXTRA_TIME_RE.search(name))]
    return max(found) if found else None


def access_extension_days(assignment: core.Assignment,
                           student_id: str) -> int:
    """Extra days a student's extra-time entitlement is worth.

    Coursework is a window rather than a timed paper, so extra time is
    applied to the length of that window: 25% extra time on a 14-day
    window is 3.5 days, rounded up to 4. Without a set date to measure
    from there is no window, so the minimum uplift applies.
    """
    percent = extra_time_percent(student_id)
    if not percent:
        return 0
    window = 0
    if assignment.set_date and assignment.due_date:
        try:
            window = (_dt.date.fromisoformat(assignment.due_date)
                      - _dt.date.fromisoformat(assignment.set_date)).days
        except ValueError:
            window = 0
    if window <= 0:
        return MIN_ACCESS_EXTENSION_DAYS
    import math
    return max(MIN_ACCESS_EXTENSION_DAYS,
                math.ceil(window * percent / 100.0))


def apply_access_arrangements(assignment_id: int, *,
                               applied_by: str | None = None,
                               overwrite: bool = False) -> dict[str, int]:
    """Give every entitled student on this assignment their uplift.

    Records the uplift as an ordinary extension so it shows up in the
    extensions list and the late sweep honours it automatically. An
    extension granted by a human is never overwritten unless asked.
    """
    init_db()
    a = _require_assignment(assignment_id)
    if not a.honour_access_arrangements:
        return {"eligible": 0, "granted": 0, "skipped": 0}
    if not a.due_date:
        logger.info(
            "Assignment #%d has no due date — no access uplift to apply",
            assignment_id)
        return {"eligible": 0, "granted": 0, "skipped": 0}

    eligible = granted = skipped = 0
    for sub in core.list_submissions(assignment_id=assignment_id):
        outcome = apply_access_arrangements_to(
            sub.submission_id, applied_by=applied_by,
            overwrite=overwrite, assignment=a)
        if outcome != "not-eligible":
            eligible += 1
        if outcome == "granted":
            granted += 1
        elif outcome == "already-extended":
            skipped += 1
    logger.info(
        "Access arrangements on assignment #%d: %d eligible, "
        "%d granted, %d already extended",
        assignment_id, eligible, granted, skipped)
    return {"eligible": eligible, "granted": granted, "skipped": skipped}


def apply_access_arrangements_to(submission_id: int, *,
                                  applied_by: str | None = None,
                                  overwrite: bool = False,
                                  assignment: core.Assignment | None = None
                                  ) -> str:
    """Snapshot one student's arrangements and grant their uplift.

    Returns ``"granted"``, ``"already-extended"``, ``"no-deadline"`` or
    ``"not-eligible"`` so the caller can report without re-deriving.
    """
    init_db()
    sub = _require_submission(submission_id)
    a = assignment or _require_assignment(sub.assignment_id)

    names = access_arrangements_for(sub.student_id)
    if names:
        _store_arrangements(submission_id, names)
    if not a.honour_access_arrangements:
        return "not-eligible"
    days = access_extension_days(a, sub.student_id)
    if not days:
        return "not-eligible"
    if not a.due_date:
        return "no-deadline"
    if sub.extended_due_date and not overwrite:
        return "already-extended"
    try:
        new_due = (_dt.date.fromisoformat(a.due_date)
                   + _dt.timedelta(days=days)).isoformat()
    except ValueError:
        return "no-deadline"
    percent = extra_time_percent(sub.student_id)
    core.grant_extension(
        submission_id, new_due,
        reason=(f"Access arrangement: {percent:g}% extra time "
                f"(+{days} day(s))"),
        authorised_by=applied_by or "Access arrangements")
    return "granted"


def _store_arrangements(submission_id: int, names: list[str]) -> None:
    """Snapshot the arrangements onto the submission for the marker.

    Stored rather than looked up live so a marker opening last year's
    work sees what was in force then, not what is in force now.
    """
    with _connect() as conn:
        conn.execute(
            "UPDATE coursework_submissions SET access_arrangements = ?, "
            "updated_at = datetime('now') WHERE submission_id = ?",
            ("; ".join(names) or None, submission_id))
        conn.commit()


def refresh_arrangements(submission_id: int) -> core.Submission:
    """Re-read a student's arrangements onto their submission."""
    init_db()
    sub = _require_submission(submission_id)
    _store_arrangements(submission_id,
                         access_arrangements_for(sub.student_id))
    return _require_submission(submission_id)


# ── Bulk marking (item 19) ────────────────────────────────────────

def marking_grid(assignment_id: int, *,
                  role: str = DEFAULT_MARKER_ROLE) -> list[GridRow]:
    """Everything the marker needs for a whole class, in one query set."""
    init_db()
    _require_assignment(assignment_id)
    names = {}
    try:
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        names = {s.student_id: s.full_name
                 for s in _students.list_students()}
    except Exception:
        logger.debug("Student names unavailable for the marking grid",
                      exc_info=True)
    a = _require_assignment(assignment_id)
    out: list[GridRow] = []
    for sub in core.list_submissions(assignment_id=assignment_id):
        crit = {m.criterion_id: m.marks
                for m in list_criterion_marks(sub.submission_id,
                                               role=role)}
        arrangements = ([x.strip()
                         for x in sub.access_arrangements.split(";")]
                        if sub.access_arrangements else [])
        out.append(GridRow(
            submission=sub,
            student_name=names.get(sub.student_id, "(unknown)"),
            criterion_marks=crit,
            penalty=compute_late_penalty(a, sub),
            moderation=moderation_state(sub.submission_id),
            access_arrangements=arrangements,
        ))
    return out


def bulk_mark(assignment_id: int, rows: list[dict[str, Any]], *,
               marked_by: str | None = None,
               role: str = DEFAULT_MARKER_ROLE,
               stop_on_error: bool = False) -> BulkResult:
    """Mark a whole class in one pass.

    Every row is validated before anything is written, so a typo in row
    28 doesn't leave rows 1–27 applied and the rest not. Rows may be
    keyed by ``submission_id`` or by ``student_id``.
    """
    init_db()
    _require_assignment(assignment_id)
    by_student = {s.student_id: s for s in
                  core.list_submissions(assignment_id=assignment_id)}
    by_id = {s.submission_id: s for s in by_student.values()}

    prepared: list[tuple[core.Submission, dict[str, Any]]] = []
    outcomes: list[BulkOutcome] = []

    for raw in rows:
        sub = None
        if raw.get("submission_id") not in (None, ""):
            sub = by_id.get(int(raw["submission_id"]))
        elif raw.get("student_id"):
            sub = by_student.get(str(raw["student_id"]).strip())
        if sub is None:
            outcomes.append(BulkOutcome(
                submission_id=int(raw.get("submission_id") or 0),
                student_id=str(raw.get("student_id") or "?"),
                ok=False,
                message="No submission on this assignment for that row"))
            if stop_on_error:
                return BulkResult(applied=0, failed=len(outcomes),
                                   outcomes=outcomes)
            continue
        try:
            marks = core._validate_number(raw.get("marks"), "Marks",
                                           min_val=0)
            a = _require_assignment(assignment_id)
            if (marks is not None and a.max_marks is not None
                    and marks > a.max_marks):
                raise ValidationError(
                    f"Marks ({marks:g}) exceed max_marks "
                    f"({a.max_marks:g})")
        except ValidationError as e:
            outcomes.append(BulkOutcome(
                submission_id=sub.submission_id,
                student_id=sub.student_id, ok=False, message=str(e)))
            if stop_on_error:
                return BulkResult(applied=0, failed=len(outcomes),
                                   outcomes=outcomes)
            continue
        prepared.append((sub, {
            "marks": marks,
            "grade": (raw.get("grade") or "").strip() or None,
            "feedback": (raw.get("feedback") or "").strip() or None,
        }))

    if stop_on_error and any(not o.ok for o in outcomes):
        return BulkResult(applied=0, failed=len(outcomes),
                           outcomes=outcomes)

    applied = 0
    for sub, values in prepared:
        try:
            record_mark(sub.submission_id, role=role,
                         marks=values["marks"], grade=values["grade"],
                         feedback=values["feedback"],
                         marked_by=marked_by)
            out = apply_marks(sub.submission_id,
                               raw_marks=values["marks"],
                               grade=values["grade"],
                               feedback=values["feedback"],
                               marked_by=marked_by, source="bulk",
                               reason="Bulk marking")
            applied += 1
            note = (f"{out.marks:g}" if out.marks is not None else "—")
            if out.penalty_percent:
                note += f" (after {out.penalty_percent:g}% late penalty)"
            outcomes.append(BulkOutcome(
                submission_id=sub.submission_id,
                student_id=sub.student_id, ok=True,
                message=f"Marked {note}"))
        except Exception as e:                     # pragma: no cover
            logger.exception("Bulk mark failed for submission #%d",
                              sub.submission_id)
            outcomes.append(BulkOutcome(
                submission_id=sub.submission_id,
                student_id=sub.student_id, ok=False, message=str(e)))

    failed = sum(1 for o in outcomes if not o.ok)
    logger.info("Bulk marking on assignment #%d: %d applied, %d failed",
                assignment_id, applied, failed)
    return BulkResult(applied=applied, failed=failed, outcomes=outcomes)
