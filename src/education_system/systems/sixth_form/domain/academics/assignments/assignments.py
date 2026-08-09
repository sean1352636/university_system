"""Assignments — coursework-style assignments with per-student submissions.

Distinct from the daily ``homework`` module: an assignment is a
substantial piece of work (essay, project, practical, controlled
assessment, coursework component) with its own brief, rubric, grade
weight, and a row per student tracking submission + marks + feedback.

Schema is four related tables:

* ``coursework_assignments``          — one row per assignment.
* ``coursework_submissions``          — one row per (assignment,
                                          student), created when a
                                          student is added to the
                                          cohort and updated as they
                                          submit. Holds the *current*
                                          state: latest attempt, marks,
                                          extension, similarity score.
* ``coursework_submission_versions``  — one row per submission attempt,
                                          so a draft → feedback →
                                          final-piece cycle keeps every
                                          version rather than
                                          overwriting.
* ``coursework_attachments``          — file metadata, hung off either
                                          an assignment (brief, mark
                                          scheme, resources) or a
                                          submission version (the work
                                          itself). Bytes live on disk
                                          under
                                          ``paths.COURSEWORK_FILES_DIR``.

Cascade: deleting an assignment removes all its submissions, their
versions and every attachment row; deleting a student removes their
submission rows. Files on disk are unlinked by the delete helpers here
— SQLite cascades cannot reach the filesystem.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import logging
import mimetypes
import re
import shutil
import sqlite3
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from education_system import paths
from education_system.systems.sixth_form.domain.academics.assignments import (
    assignments as data,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ASSIGNMENTS_DB


ASSIGNMENT_TYPES: tuple[str, ...] = (
    "Essay",
    "Project",
    "Practical",
    "Presentation",
    "Coursework",
    "NEA",
    "Controlled Assessment",
    "Lab Report",
    "Portfolio",
    "Group Task",
    "Other",
)
DEFAULT_ASSIGNMENT_TYPE: str = "Essay"

ASSIGNMENT_STATUSES: tuple[str, ...] = (
    "Draft", "Set", "Closed", "Graded", "Archived",
)
DEFAULT_ASSIGNMENT_STATUS: str = "Draft"

SUBMISSION_STATUSES: tuple[str, ...] = (
    "Not Started", "In Progress", "Submitted",
    "Late", "Excused", "Missing", "Returned",
)
DEFAULT_SUBMISSION_STATUS: str = "Not Started"
DONE_SUBMISSION_STATUSES: tuple[str, ...] = (
    "Submitted", "Late", "Excused", "Returned",
)

YEAR_GROUPS: tuple[str, ...] = ("Year 12", "Year 13", "Mixed")

# Statuses that mean "the student still owes us this work". The late
# sweep only ever touches rows in one of these.
PENDING_SUBMISSION_STATUSES: tuple[str, ...] = ("Not Started", "In Progress")

# When a marked piece becomes visible to the student.
#   Immediate — the moment it is marked (the historical behaviour)
#   On date   — held until ``release_on``, so a class sees results together
#   Manual    — held until someone explicitly releases it
RELEASE_POLICIES: tuple[str, ...] = ("Immediate", "On date", "Manual")
DEFAULT_RELEASE_POLICY: str = "Immediate"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ── Attachments ───────────────────────────────────────────────────
# An attachment belongs to exactly one of: an assignment (material the
# teacher hands out) or a submission version (the work handed back).
ASSIGNMENT_ATTACHMENT_KINDS: tuple[str, ...] = (
    "Brief", "Mark Scheme", "Resource", "Exemplar", "Other",
)
SUBMISSION_ATTACHMENT_KINDS: tuple[str, ...] = (
    "Work", "Feedback", "Receipt", "Other",
)
ATTACHMENT_KINDS: tuple[str, ...] = tuple(
    dict.fromkeys(ASSIGNMENT_ATTACHMENT_KINDS + SUBMISSION_ATTACHMENT_KINDS))
DEFAULT_ASSIGNMENT_ATTACHMENT_KIND: str = "Resource"
DEFAULT_SUBMISSION_ATTACHMENT_KIND: str = "Work"

# 25 MB is generous for an essay and small enough that a mis-picked
# video doesn't fill the data volume.
MAX_ATTACHMENT_BYTES: int = 25 * 1024 * 1024

# Executable / scriptable types are refused outright: this store is
# handed back to staff to open, so it must never carry something that
# runs on double-click.
BLOCKED_ATTACHMENT_SUFFIXES: frozenset[str] = frozenset({
    ".exe", ".com", ".bat", ".cmd", ".scr", ".pif", ".msi", ".msp",
    ".dll", ".sys", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh",
    ".ps1", ".psm1", ".jar", ".app", ".sh", ".bash", ".reg", ".lnk",
})

_UNSAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")

# ── Word limits ───────────────────────────────────────────────────
# Boards typically allow a little headroom before a penalty applies;
# inside the tolerance band we warn, beyond it we call it a breach.
WORD_LIMIT_TOLERANCE: float = 0.10

# ── Similarity ────────────────────────────────────────────────────
# Percentage at or above which a submission is flagged for a human to
# look at. Per-assignment ``similarity_threshold`` overrides this.
DEFAULT_SIMILARITY_THRESHOLD: float = 30.0


_SCHEMA = """
CREATE TABLE IF NOT EXISTS coursework_assignments (
    assignment_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    title             TEXT NOT NULL,
    subject_name      TEXT NOT NULL,
    course_id         INTEGER,
    class_group_id    INTEGER,
    year_group        TEXT,
    assignment_type   TEXT NOT NULL DEFAULT 'Essay',
    teacher           TEXT,
    set_date          TEXT,
    due_date          TEXT,
    max_marks         REAL,
    weight_percent    REAL,
    brief             TEXT,
    rubric            TEXT,
    resources         TEXT,
    submission_method TEXT,
    status            TEXT NOT NULL DEFAULT 'Draft',
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS coursework_submissions (
    submission_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id     INTEGER NOT NULL,
    student_id        TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'Not Started',
    submitted_on      TEXT,
    marks             REAL,
    grade             TEXT,
    feedback          TEXT,
    marked_by         TEXT,
    marked_on         TEXT,
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (assignment_id) REFERENCES coursework_assignments(assignment_id)
        ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE,
    UNIQUE (assignment_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_cw_subject   ON coursework_assignments(subject_name);
CREATE INDEX IF NOT EXISTS idx_cw_status    ON coursework_assignments(status);
CREATE INDEX IF NOT EXISTS idx_cw_due       ON coursework_assignments(due_date);
CREATE INDEX IF NOT EXISTS idx_cw_teacher   ON coursework_assignments(teacher);
CREATE TABLE IF NOT EXISTS coursework_submission_versions (
    version_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id     INTEGER NOT NULL,
    attempt_no        INTEGER NOT NULL,
    is_draft          INTEGER NOT NULL DEFAULT 0,
    status            TEXT NOT NULL,
    submitted_on      TEXT NOT NULL,
    submitted_at      TEXT NOT NULL DEFAULT (datetime('now')),
    submitted_by      TEXT,
    word_count        INTEGER,
    similarity_score  REAL,
    receipt_ref       TEXT,
    receipt_hash      TEXT,
    receipt_path      TEXT,
    note              TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (submission_id) REFERENCES coursework_submissions(submission_id)
        ON DELETE CASCADE,
    UNIQUE (submission_id, attempt_no)
);

CREATE TABLE IF NOT EXISTS coursework_attachments (
    attachment_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id     INTEGER,
    submission_id     INTEGER,
    version_id        INTEGER,
    kind              TEXT NOT NULL DEFAULT 'Resource',
    filename          TEXT NOT NULL,
    stored_path       TEXT NOT NULL,
    byte_size         INTEGER NOT NULL DEFAULT 0,
    sha256            TEXT,
    content_type      TEXT,
    uploaded_by       TEXT,
    uploaded_at       TEXT DEFAULT (datetime('now')),
    notes             TEXT,
    FOREIGN KEY (assignment_id) REFERENCES coursework_assignments(assignment_id)
        ON DELETE CASCADE,
    FOREIGN KEY (submission_id) REFERENCES coursework_submissions(submission_id)
        ON DELETE CASCADE,
    FOREIGN KEY (version_id) REFERENCES coursework_submission_versions(version_id)
        ON DELETE CASCADE,
    CHECK ((assignment_id IS NOT NULL) + (submission_id IS NOT NULL) = 1)
);

CREATE INDEX IF NOT EXISTS idx_cwsub_assign  ON coursework_submissions(assignment_id);
CREATE INDEX IF NOT EXISTS idx_cwsub_student ON coursework_submissions(student_id);
CREATE INDEX IF NOT EXISTS idx_cwsub_status  ON coursework_submissions(status);
CREATE INDEX IF NOT EXISTS idx_cwver_sub     ON coursework_submission_versions(submission_id);
CREATE INDEX IF NOT EXISTS idx_cwatt_assign  ON coursework_attachments(assignment_id);
CREATE INDEX IF NOT EXISTS idx_cwatt_sub     ON coursework_attachments(submission_id);
CREATE INDEX IF NOT EXISTS idx_cwatt_version ON coursework_attachments(version_id);
"""


# Columns added to the two original tables after they shipped. Applied
# as ALTER TABLE at init_db() so an existing sixthform.db upgrades in
# place — see the same idiom in advanced_search.py.
_ASSIGNMENT_EXTRA_COLS: tuple[tuple[str, str], ...] = (
    ("word_limit",           "INTEGER"),
    ("allow_resubmission",   "INTEGER NOT NULL DEFAULT 1"),
    ("similarity_threshold", "REAL"),
    # Marking policy. The mechanics live in ``assignments_marking``;
    # the settings live here because they belong to the assignment.
    ("late_penalty_percent_per_day", "REAL"),
    ("late_penalty_cap_percent",     "REAL"),
    ("late_penalty_grace_days",      "INTEGER NOT NULL DEFAULT 0"),
    ("moderation_tolerance",         "REAL"),
    ("honour_access_arrangements",   "INTEGER NOT NULL DEFAULT 1"),
    # Feedback workflow. Mechanics live in ``assignments_feedback``.
    ("marking_sla_days",             "INTEGER"),
    ("anonymous_marking",            "INTEGER NOT NULL DEFAULT 0"),
    ("release_policy",               "TEXT NOT NULL DEFAULT 'Immediate'"),
    ("release_on",                   "TEXT"),
    ("released_at",                  "TEXT"),
    ("appeal_window_days",           "INTEGER"),
    # Assessment instruments. Mechanics live in
    # ``assignments_assessment``.
    ("is_group_assignment",          "INTEGER NOT NULL DEFAULT 0"),
    ("peer_assessment_weight",       "REAL"),
    ("self_assessment_required",     "INTEGER NOT NULL DEFAULT 0"),
    # Multi-part composition: a child names its parent and carries the
    # share of the parent's mark it is worth.
    ("parent_assignment_id",         "INTEGER"),
    ("component_weight",             "REAL"),
    # Awarding-body metadata. Mechanics live in
    # ``assignments_catalogue``.
    ("qualification",                "TEXT"),
    ("exam_board",                   "TEXT"),
    ("spec_code",                    "TEXT"),
    ("unit_code",                    "TEXT"),
    ("component_code",               "TEXT"),
    ("assessment_objectives",        "TEXT"),
    # Templates and the shared department library.
    ("is_template",                  "INTEGER NOT NULL DEFAULT 0"),
    ("template_name",                "TEXT"),
    ("shared_with_department",       "INTEGER NOT NULL DEFAULT 0"),
    ("source_assignment_id",         "INTEGER"),
    ("times_reused",                 "INTEGER NOT NULL DEFAULT 0"),
    ("estimated_hours",              "REAL"),
    # Scheduling and outward notification. Mechanics live in
    # ``assignments_scheduling``.
    ("auto_publish",                 "INTEGER NOT NULL DEFAULT 0"),
    ("published_on",                 "TEXT"),
    ("reminder_days",                "TEXT"),
    ("chase_enabled",                "INTEGER NOT NULL DEFAULT 1"),
    ("parent_visible",               "INTEGER NOT NULL DEFAULT 1"),
    ("calendar_event_id",            "INTEGER"),
    # Cover and handover. ``teacher`` stays the substantive owner; a
    # cover marker is recorded alongside so the original is never lost.
    ("cover_marker",                 "TEXT"),
    ("cover_from",                   "TEXT"),
    ("cover_until",                  "TEXT"),
    ("cover_reason",                 "TEXT"),
)

_SUBMISSION_EXTRA_COLS: tuple[tuple[str, str], ...] = (
    ("attempt_no",            "INTEGER NOT NULL DEFAULT 0"),
    ("is_draft",              "INTEGER NOT NULL DEFAULT 0"),
    ("word_count",            "INTEGER"),
    ("extended_due_date",     "TEXT"),
    ("extension_reason",      "TEXT"),
    ("extension_by",          "TEXT"),
    ("extension_on",          "TEXT"),
    ("similarity_score",      "REAL"),
    ("similarity_provider",   "TEXT"),
    ("similarity_report",     "TEXT"),
    ("similarity_checked_on", "TEXT"),
    ("receipt_ref",           "TEXT"),
    ("auto_status_on",        "TEXT"),
    # Marking. ``raw_marks`` is what the marker awarded; ``marks`` is
    # what counts after any late penalty, so the original is never lost.
    ("raw_marks",             "REAL"),
    ("penalty_percent",       "REAL"),
    ("penalty_days",          "INTEGER"),
    ("penalty_waived",        "INTEGER NOT NULL DEFAULT 0"),
    ("penalty_waived_reason", "TEXT"),
    ("sample_band",           "TEXT"),
    ("sample_note",           "TEXT"),
    ("sample_by",             "TEXT"),
    ("sample_on",             "TEXT"),
    ("access_arrangements",   "TEXT"),
    # Feedback workflow: a mark can exist without the student seeing it.
    ("feedback_released",     "INTEGER NOT NULL DEFAULT 0"),
    ("feedback_released_on",  "TEXT"),
    ("feedback_released_by",  "TEXT"),
    ("acknowledged_on",       "TEXT"),
    ("student_response",      "TEXT"),
    # Assessment instruments.
    ("group_id",              "INTEGER"),
    ("group_adjustment",      "REAL"),
    ("peer_score",            "REAL"),
    ("self_predicted_marks",  "REAL"),
    ("self_assessment_note",  "TEXT"),
    ("self_assessed_on",      "TEXT"),
    ("objective_marks",       "REAL"),
    ("objective_marked_on",   "TEXT"),
    # Differentiated variants and outward chasing.
    ("variant_id",            "INTEGER"),
    ("reminders_sent",        "TEXT"),
    ("chase_level",           "INTEGER NOT NULL DEFAULT 0"),
    ("last_chased_on",        "TEXT"),
)


@dataclass
class Assignment:
    assignment_id: int
    title: str
    subject_name: str
    course_id: int | None
    class_group_id: int | None
    year_group: str | None
    assignment_type: str
    teacher: str | None
    set_date: str | None
    due_date: str | None
    max_marks: float | None
    weight_percent: float | None
    brief: str | None
    rubric: str | None
    resources: str | None
    submission_method: str | None
    status: str
    notes: str | None
    created_at: str
    updated_at: str
    word_limit: int | None = None
    allow_resubmission: bool = True
    similarity_threshold: float | None = None
    late_penalty_percent_per_day: float | None = None
    late_penalty_cap_percent: float | None = None
    late_penalty_grace_days: int = 0
    moderation_tolerance: float | None = None
    honour_access_arrangements: bool = True
    marking_sla_days: int | None = None
    anonymous_marking: bool = False
    release_policy: str = "Immediate"
    release_on: str | None = None
    released_at: str | None = None
    appeal_window_days: int | None = None
    is_group_assignment: bool = False
    peer_assessment_weight: float | None = None
    self_assessment_required: bool = False
    parent_assignment_id: int | None = None
    component_weight: float | None = None
    qualification: str | None = None
    exam_board: str | None = None
    spec_code: str | None = None
    unit_code: str | None = None
    component_code: str | None = None
    assessment_objectives: str | None = None
    is_template: bool = False
    template_name: str | None = None
    shared_with_department: bool = False
    source_assignment_id: int | None = None
    times_reused: int = 0
    estimated_hours: float | None = None
    auto_publish: bool = False
    published_on: str | None = None
    reminder_days: str | None = None
    chase_enabled: bool = True
    parent_visible: bool = True
    calendar_event_id: int | None = None
    cover_marker: str | None = None
    cover_from: str | None = None
    cover_until: str | None = None
    cover_reason: str | None = None

    def marker_on(self, day: str | None = None) -> str | None:
        """Who is marking this today — the cover marker if one is in
        force, otherwise the substantive teacher."""
        if not self.cover_marker:
            return self.teacher
        today = day or _dt.date.today().isoformat()
        if self.cover_from and today < self.cover_from:
            return self.teacher
        if self.cover_until and today > self.cover_until:
            return self.teacher
        return self.cover_marker

    @property
    def is_covered(self) -> bool:
        return bool(self.cover_marker) and \
            self.marker_on() == self.cover_marker

    @property
    def is_component(self) -> bool:
        return self.parent_assignment_id is not None

    @property
    def objective_list(self) -> list[str]:
        return [o.strip() for o in (self.assessment_objectives or "").split(",")
                if o.strip()]

    @property
    def spec_reference(self) -> str:
        """Human-readable awarding-body reference, or an empty string."""
        parts = [p for p in (self.exam_board, self.spec_code,
                              self.unit_code, self.component_code) if p]
        return " · ".join(parts)

    @property
    def is_open(self) -> bool:
        return self.status in ("Draft", "Set")

    @property
    def is_overdue(self) -> bool:
        if not self.due_date or self.status not in ("Set", "Draft"):
            return False
        return self.due_date < _dt.date.today().isoformat()

    @property
    def effective_similarity_threshold(self) -> float:
        if self.similarity_threshold is None:
            return DEFAULT_SIMILARITY_THRESHOLD
        return self.similarity_threshold


@dataclass
class Submission:
    submission_id: int
    assignment_id: int
    student_id: str
    status: str
    submitted_on: str | None
    marks: float | None
    grade: str | None
    feedback: str | None
    marked_by: str | None
    marked_on: str | None
    notes: str | None
    created_at: str
    updated_at: str
    attempt_no: int = 0
    is_draft: bool = False
    word_count: int | None = None
    extended_due_date: str | None = None
    extension_reason: str | None = None
    extension_by: str | None = None
    extension_on: str | None = None
    similarity_score: float | None = None
    similarity_provider: str | None = None
    similarity_report: str | None = None
    similarity_checked_on: str | None = None
    receipt_ref: str | None = None
    auto_status_on: str | None = None
    raw_marks: float | None = None
    penalty_percent: float | None = None
    penalty_days: int | None = None
    penalty_waived: bool = False
    penalty_waived_reason: str | None = None
    sample_band: str | None = None
    sample_note: str | None = None
    sample_by: str | None = None
    sample_on: str | None = None
    access_arrangements: str | None = None
    feedback_released: bool = False
    feedback_released_on: str | None = None
    feedback_released_by: str | None = None
    acknowledged_on: str | None = None
    student_response: str | None = None
    group_id: int | None = None
    group_adjustment: float | None = None
    peer_score: float | None = None
    self_predicted_marks: float | None = None
    self_assessment_note: str | None = None
    self_assessed_on: str | None = None
    objective_marks: float | None = None
    objective_marked_on: str | None = None
    variant_id: int | None = None
    reminders_sent: str | None = None
    chase_level: int = 0
    last_chased_on: str | None = None

    @property
    def reminders_sent_list(self) -> list[int]:
        out = []
        for part in (self.reminders_sent or "").split(","):
            part = part.strip()
            if part.lstrip("-").isdigit():
                out.append(int(part))
        return out

    @property
    def is_acknowledged(self) -> bool:
        return bool(self.acknowledged_on)

    @property
    def is_sample(self) -> bool:
        return bool(self.sample_band)

    @property
    def penalty_applied(self) -> bool:
        return bool(self.penalty_percent)

    @property
    def is_done(self) -> bool:
        return self.status in DONE_SUBMISSION_STATUSES

    @property
    def has_extension(self) -> bool:
        return bool(self.extended_due_date)

    @property
    def percent(self) -> float | None:
        return None    # overlay with assignment.max_marks at the row layer


@dataclass
class SubmissionVersion:
    """One attempt at a submission — a draft or the final piece.

    Immutable once written: a resubmission adds a new row rather than
    editing this one, so the earlier attempt and its files survive.
    """

    version_id: int
    submission_id: int
    attempt_no: int
    is_draft: bool
    status: str
    submitted_on: str
    submitted_at: str
    submitted_by: str | None
    word_count: int | None
    similarity_score: float | None
    receipt_ref: str | None
    receipt_hash: str | None
    receipt_path: str | None
    note: str | None
    created_at: str

    @property
    def label(self) -> str:
        kind = "Draft" if self.is_draft else "Final"
        return f"Attempt {self.attempt_no} ({kind})"


@dataclass
class Attachment:
    """File metadata. The bytes live at ``path``, outside the DB."""

    attachment_id: int
    assignment_id: int | None
    submission_id: int | None
    version_id: int | None
    kind: str
    filename: str
    stored_path: str
    byte_size: int
    sha256: str | None
    content_type: str | None
    uploaded_by: str | None
    uploaded_at: str
    notes: str | None

    @property
    def path(self) -> Path:
        return paths.SIXTH_FORM_COURSEWORK_FILES_DIR / self.stored_path

    @property
    def exists(self) -> bool:
        return self.path.is_file()

    @property
    def size_label(self) -> str:
        n = float(self.byte_size)
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024 or unit == "GB":
                return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
            n /= 1024
        return f"{self.byte_size} B"


@dataclass
class WordLimitCheck:
    """Outcome of comparing a word count against the brief's limit."""

    limit: int | None
    word_count: int | None
    over_by: int = 0
    within_tolerance: bool = True

    @property
    def applicable(self) -> bool:
        return self.limit is not None and self.word_count is not None

    @property
    def breached(self) -> bool:
        return self.applicable and not self.within_tolerance

    @property
    def message(self) -> str:
        if not self.applicable:
            return ""
        if self.over_by <= 0:
            return (f"{self.word_count} words "
                    f"(limit {self.limit}) — within limit")
        band = "within tolerance" if self.within_tolerance else "OVER LIMIT"
        return (f"{self.word_count} words (limit {self.limit}) — "
                f"{self.over_by} over, {band}")


@dataclass
class SimilarityResult:
    """What a plagiarism provider reported back for one attempt."""

    score: float
    provider: str | None = None
    report_ref: str | None = None
    checked_on: str | None = None


@dataclass
class AssignmentDetail:
    assignment: Assignment
    submissions: list[Submission] = field(default_factory=list)

    @property
    def total_submissions(self) -> int:
        return len(self.submissions)

    @property
    def submitted_count(self) -> int:
        return sum(1 for s in self.submissions if s.is_done)

    @property
    def marked_count(self) -> int:
        return sum(1 for s in self.submissions if s.marks is not None)

    @property
    def average_mark(self) -> float | None:
        marks = [s.marks for s in self.submissions
                  if s.marks is not None]
        if not marks:
            return None
        return round(sum(marks) / len(marks), 2)

    @property
    def percent_submitted(self) -> float:
        if not self.submissions:
            return 0.0
        return round(100.0 * self.submitted_count
                      / len(self.submissions), 1)


@dataclass
class AssignmentRow:
    assignment: Assignment
    total_submissions: int = 0
    submitted_count: int = 0
    marked_count: int = 0
    average_mark: float | None = None


@dataclass
class SubmissionRow:
    submission: Submission
    student_name: str


@dataclass
class Summary:
    total_assignments: int
    by_status: dict[str, int]
    by_type: dict[str, int]
    by_subject: dict[str, int]
    open_count: int
    overdue: int
    upcoming_due: int
    total_submissions: int
    submitted_total: int
    marked_total: int
    overdue_submissions: int = 0
    active_extensions: int = 0
    flagged_similarity: int = 0
    attachment_count: int = 0
    attachment_bytes: int = 0


# ── DB plumbing ────────────────────────────────────────────────────

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
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        for table, cols in (
            ("coursework_assignments", _ASSIGNMENT_EXTRA_COLS),
            ("coursework_submissions", _SUBMISSION_EXTRA_COLS),
        ):
            have = {r["name"] for r in conn.execute(
                f"PRAGMA table_info({table})").fetchall()}
            for col, ddl in cols:
                if col not in have:
                    conn.execute(
                        f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
        conn.commit()
    paths.SIXTH_FORM_COURSEWORK_FILES_DIR.mkdir(parents=True, exist_ok=True)
    logger.debug("Assignments schema ready at %s", DB_PATH)

    _DB_READY = True


def _row_assignment(r: sqlite3.Row) -> Assignment:
    return Assignment(
        assignment_id=r["assignment_id"], title=r["title"],
        subject_name=r["subject_name"],
        course_id=r["course_id"],
        class_group_id=r["class_group_id"],
        year_group=r["year_group"],
        assignment_type=r["assignment_type"],
        teacher=r["teacher"], set_date=r["set_date"],
        due_date=r["due_date"], max_marks=r["max_marks"],
        weight_percent=r["weight_percent"],
        brief=r["brief"], rubric=r["rubric"],
        resources=r["resources"],
        submission_method=r["submission_method"],
        status=r["status"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
        word_limit=r["word_limit"],
        allow_resubmission=bool(r["allow_resubmission"]),
        similarity_threshold=r["similarity_threshold"],
        late_penalty_percent_per_day=r["late_penalty_percent_per_day"],
        late_penalty_cap_percent=r["late_penalty_cap_percent"],
        late_penalty_grace_days=r["late_penalty_grace_days"] or 0,
        moderation_tolerance=r["moderation_tolerance"],
        honour_access_arrangements=bool(r["honour_access_arrangements"]),
        marking_sla_days=r["marking_sla_days"],
        anonymous_marking=bool(r["anonymous_marking"]),
        release_policy=r["release_policy"] or "Immediate",
        release_on=r["release_on"],
        released_at=r["released_at"],
        appeal_window_days=r["appeal_window_days"],
        is_group_assignment=bool(r["is_group_assignment"]),
        peer_assessment_weight=r["peer_assessment_weight"],
        self_assessment_required=bool(r["self_assessment_required"]),
        parent_assignment_id=r["parent_assignment_id"],
        component_weight=r["component_weight"],
        qualification=r["qualification"],
        exam_board=r["exam_board"], spec_code=r["spec_code"],
        unit_code=r["unit_code"], component_code=r["component_code"],
        assessment_objectives=r["assessment_objectives"],
        is_template=bool(r["is_template"]),
        template_name=r["template_name"],
        shared_with_department=bool(r["shared_with_department"]),
        source_assignment_id=r["source_assignment_id"],
        times_reused=r["times_reused"] or 0,
        estimated_hours=r["estimated_hours"],
        auto_publish=bool(r["auto_publish"]),
        published_on=r["published_on"],
        reminder_days=r["reminder_days"],
        chase_enabled=bool(r["chase_enabled"]),
        parent_visible=bool(r["parent_visible"]),
        calendar_event_id=r["calendar_event_id"],
        cover_marker=r["cover_marker"], cover_from=r["cover_from"],
        cover_until=r["cover_until"],
        cover_reason=r["cover_reason"],
    )


def _row_submission(r: sqlite3.Row) -> Submission:
    return Submission(
        submission_id=r["submission_id"],
        assignment_id=r["assignment_id"],
        student_id=r["student_id"], status=r["status"],
        submitted_on=r["submitted_on"], marks=r["marks"],
        grade=r["grade"], feedback=r["feedback"],
        marked_by=r["marked_by"], marked_on=r["marked_on"],
        notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
        attempt_no=r["attempt_no"] or 0,
        is_draft=bool(r["is_draft"]),
        word_count=r["word_count"],
        extended_due_date=r["extended_due_date"],
        extension_reason=r["extension_reason"],
        extension_by=r["extension_by"],
        extension_on=r["extension_on"],
        similarity_score=r["similarity_score"],
        similarity_provider=r["similarity_provider"],
        similarity_report=r["similarity_report"],
        similarity_checked_on=r["similarity_checked_on"],
        receipt_ref=r["receipt_ref"],
        auto_status_on=r["auto_status_on"],
        raw_marks=r["raw_marks"],
        penalty_percent=r["penalty_percent"],
        penalty_days=r["penalty_days"],
        penalty_waived=bool(r["penalty_waived"]),
        penalty_waived_reason=r["penalty_waived_reason"],
        sample_band=r["sample_band"],
        sample_note=r["sample_note"],
        sample_by=r["sample_by"],
        sample_on=r["sample_on"],
        access_arrangements=r["access_arrangements"],
        feedback_released=bool(r["feedback_released"]),
        feedback_released_on=r["feedback_released_on"],
        feedback_released_by=r["feedback_released_by"],
        acknowledged_on=r["acknowledged_on"],
        student_response=r["student_response"],
        group_id=r["group_id"],
        group_adjustment=r["group_adjustment"],
        peer_score=r["peer_score"],
        self_predicted_marks=r["self_predicted_marks"],
        self_assessment_note=r["self_assessment_note"],
        self_assessed_on=r["self_assessed_on"],
        objective_marks=r["objective_marks"],
        objective_marked_on=r["objective_marked_on"],
        variant_id=r["variant_id"],
        reminders_sent=r["reminders_sent"],
        chase_level=r["chase_level"] or 0,
        last_chased_on=r["last_chased_on"],
    )


def _row_version(r: sqlite3.Row) -> SubmissionVersion:
    return SubmissionVersion(
        version_id=r["version_id"],
        submission_id=r["submission_id"],
        attempt_no=r["attempt_no"],
        is_draft=bool(r["is_draft"]),
        status=r["status"],
        submitted_on=r["submitted_on"],
        submitted_at=r["submitted_at"],
        submitted_by=r["submitted_by"],
        word_count=r["word_count"],
        similarity_score=r["similarity_score"],
        receipt_ref=r["receipt_ref"],
        receipt_hash=r["receipt_hash"],
        receipt_path=r["receipt_path"],
        note=r["note"],
        created_at=r["created_at"],
    )


def _row_attachment(r: sqlite3.Row) -> Attachment:
    return Attachment(
        attachment_id=r["attachment_id"],
        assignment_id=r["assignment_id"],
        submission_id=r["submission_id"],
        version_id=r["version_id"],
        kind=r["kind"], filename=r["filename"],
        stored_path=r["stored_path"],
        byte_size=r["byte_size"] or 0,
        sha256=r["sha256"], content_type=r["content_type"],
        uploaded_by=r["uploaded_by"], uploaded_at=r["uploaded_at"],
        notes=r["notes"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_date(value: Any, label: str, *,
                    required: bool = False) -> str | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _validate_number(value: Any, label: str, *,
                      min_val: float | None = None,
                      max_val: float | None = None) -> float | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a number") from None
    if min_val is not None and f < min_val:
        raise ValidationError(f"{label} must be at least {min_val}")
    if max_val is not None and f > max_val:
        raise ValidationError(f"{label} must be at most {max_val}")
    return f


def _validate_subject(value: Any) -> str:
    name = _require(value, "Subject").strip()
    try:
        from education_system.systems.sixth_form.domain.academics.subjects import (
            subjects as _subjects,
        )
        names = {x.name for x in _subjects.list_subjects()}
        if names and name not in names:
            raise ValidationError(
                f"Subject {name!r} not in catalogue")
    except ValidationError:
        raise
    except Exception:
        pass
    return name


def _validate_assignment_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["title"] = _require(payload.get("title"), "Title").strip()
    out["subject_name"] = _validate_subject(payload.get("subject_name"))

    atype = (payload.get("assignment_type")
              or DEFAULT_ASSIGNMENT_TYPE).strip()
    if atype not in ASSIGNMENT_TYPES:
        raise ValidationError(
            f"Type must be one of: {', '.join(ASSIGNMENT_TYPES)}")
    out["assignment_type"] = atype

    status = (payload.get("status")
                or DEFAULT_ASSIGNMENT_STATUS).strip()
    if status not in ASSIGNMENT_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(ASSIGNMENT_STATUSES)}")
    out["status"] = status

    year = (payload.get("year_group") or "").strip()
    if year and year not in YEAR_GROUPS:
        raise ValidationError(
            f"Year group must be one of: {', '.join(YEAR_GROUPS)}")
    out["year_group"] = year or None

    out["teacher"] = (payload.get("teacher") or "").strip() or None
    out["set_date"] = _validate_date(payload.get("set_date"),
                                          "Set date")
    out["due_date"] = _validate_date(payload.get("due_date"),
                                          "Due date")
    if (out["set_date"] and out["due_date"]
            and out["due_date"] < out["set_date"]):
        raise ValidationError(
            "Due date cannot be before set date")

    out["max_marks"] = _validate_number(payload.get("max_marks"),
                                            "Max marks", min_val=0)
    out["weight_percent"] = _validate_number(
        payload.get("weight_percent"), "Weight %",
        min_val=0, max_val=100)

    limit = _validate_number(payload.get("word_limit"), "Word limit",
                              min_val=1)
    out["word_limit"] = int(limit) if limit is not None else None
    out["similarity_threshold"] = _validate_number(
        payload.get("similarity_threshold"), "Similarity threshold %",
        min_val=0, max_val=100)
    allow = payload.get("allow_resubmission", True)
    out["allow_resubmission"] = 0 if allow in (False, 0, "0", "No",
                                                "no", "false") else 1

    out["late_penalty_percent_per_day"] = _validate_number(
        payload.get("late_penalty_percent_per_day"),
        "Late penalty % per day", min_val=0, max_val=100)
    out["late_penalty_cap_percent"] = _validate_number(
        payload.get("late_penalty_cap_percent"),
        "Late penalty cap %", min_val=0, max_val=100)
    grace = _validate_number(payload.get("late_penalty_grace_days"),
                              "Late penalty grace days", min_val=0)
    out["late_penalty_grace_days"] = int(grace) if grace else 0
    out["moderation_tolerance"] = _validate_number(
        payload.get("moderation_tolerance"),
        "Moderation tolerance", min_val=0)
    honour = payload.get("honour_access_arrangements", True)
    out["honour_access_arrangements"] = 0 if honour in (
        False, 0, "0", "No", "no", "false") else 1

    def _flag(key: str, default: Any = False) -> int:
        value = payload.get(key, default)
        return 0 if value in (False, 0, "0", "No", "no", "false",
                               "", None) else 1

    sla = _validate_number(payload.get("marking_sla_days"),
                            "Marking SLA days", min_val=0)
    out["marking_sla_days"] = int(sla) if sla is not None else None
    out["anonymous_marking"] = _flag("anonymous_marking")

    policy = (payload.get("release_policy")
               or DEFAULT_RELEASE_POLICY).strip()
    if policy not in RELEASE_POLICIES:
        raise ValidationError(
            f"Release policy must be one of: "
            f"{', '.join(RELEASE_POLICIES)}")
    out["release_policy"] = policy
    out["release_on"] = _validate_date(payload.get("release_on"),
                                        "Release date")
    if policy == "On date" and not out["release_on"]:
        raise ValidationError(
            "A release date is required when the policy is 'On date'")
    out["released_at"] = (payload.get("released_at") or "").strip() or None

    window = _validate_number(payload.get("appeal_window_days"),
                               "Appeal window days", min_val=0)
    out["appeal_window_days"] = int(window) if window is not None else None

    out["is_group_assignment"] = _flag("is_group_assignment")
    out["peer_assessment_weight"] = _validate_number(
        payload.get("peer_assessment_weight"),
        "Peer assessment weight %", min_val=0, max_val=100)
    out["self_assessment_required"] = _flag("self_assessment_required")

    out["parent_assignment_id"] = None
    if payload.get("parent_assignment_id") not in (None, ""):
        try:
            out["parent_assignment_id"] = int(
                payload["parent_assignment_id"])
        except (TypeError, ValueError):
            raise ValidationError(
                "parent_assignment_id must be a number") from None
    out["component_weight"] = _validate_number(
        payload.get("component_weight"), "Component weight %",
        min_val=0, max_val=100)

    def _text(key: str) -> str | None:
        return (str(payload.get(key) or "").strip() or None)

    out["qualification"]         = _text("qualification")
    out["exam_board"]            = _text("exam_board")
    out["spec_code"]             = _text("spec_code")
    out["unit_code"]             = _text("unit_code")
    out["component_code"]        = _text("component_code")
    out["assessment_objectives"] = _text("assessment_objectives")
    out["template_name"]         = _text("template_name")
    out["cover_marker"]          = _text("cover_marker")
    out["cover_reason"]          = _text("cover_reason")
    out["published_on"]          = _validate_date(
        payload.get("published_on"), "Published on")
    out["cover_from"]            = _validate_date(
        payload.get("cover_from"), "Cover from")
    out["cover_until"]           = _validate_date(
        payload.get("cover_until"), "Cover until")
    if (out["cover_from"] and out["cover_until"]
            and out["cover_until"] < out["cover_from"]):
        raise ValidationError(
            "Cover cannot end before it starts")

    out["is_template"]            = _flag("is_template")
    out["shared_with_department"] = _flag("shared_with_department")
    out["auto_publish"]           = _flag("auto_publish")
    out["chase_enabled"]          = _flag("chase_enabled", True)
    out["parent_visible"]         = _flag("parent_visible", True)

    hours = _validate_number(payload.get("estimated_hours"),
                              "Estimated hours", min_val=0)
    out["estimated_hours"] = hours
    reused = _validate_number(payload.get("times_reused"),
                               "Times reused", min_val=0)
    out["times_reused"] = int(reused) if reused else 0

    for key in ("source_assignment_id", "calendar_event_id"):
        out[key] = None
        if payload.get(key) not in (None, ""):
            try:
                out[key] = int(payload[key])
            except (TypeError, ValueError):
                raise ValidationError(
                    f"{key} must be a number") from None

    # Reminder offsets are stored as a sorted, de-duplicated CSV of
    # days-before-due, so "7, 3, 3, 1" and "1,3,7" mean the same thing.
    raw_days = payload.get("reminder_days")
    if raw_days in (None, ""):
        out["reminder_days"] = None
    else:
        if isinstance(raw_days, (list, tuple, set)):
            candidates = list(raw_days)
        else:
            candidates = [p for p in str(raw_days).split(",")]
        days: set[int] = set()
        for candidate in candidates:
            text = str(candidate).strip()
            if not text:
                continue
            try:
                value = int(text)
            except ValueError:
                raise ValidationError(
                    f"Reminder days must be whole numbers, "
                    f"got {text!r}") from None
            if value < 0:
                raise ValidationError(
                    "Reminder days count backwards from the due date, "
                    "so they cannot be negative")
            days.add(value)
        out["reminder_days"] = (",".join(str(d) for d in
                                          sorted(days, reverse=True))
                                 or None)

    out["course_id"] = None
    if payload.get("course_id") not in (None, ""):
        try:
            out["course_id"] = int(payload.get("course_id"))
        except (TypeError, ValueError):
            raise ValidationError(
                "course_id must be a number") from None
    out["class_group_id"] = None
    if payload.get("class_group_id") not in (None, ""):
        try:
            out["class_group_id"] = int(payload.get("class_group_id"))
        except (TypeError, ValueError):
            raise ValidationError(
                "class_group_id must be a number") from None

    out["brief"]             = (payload.get("brief")
                                  or "").strip() or None
    out["rubric"]            = (payload.get("rubric")
                                  or "").strip() or None
    out["resources"]         = (payload.get("resources")
                                  or "").strip() or None
    out["submission_method"] = (payload.get("submission_method")
                                  or "").strip() or None
    out["notes"]             = (payload.get("notes")
                                  or "").strip() or None
    return out


def _validate_submission_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    aid = payload.get("assignment_id")
    if aid in (None, ""):
        raise ValidationError("Assignment id is required")
    try:
        out["assignment_id"] = int(aid)
    except (TypeError, ValueError):
        raise ValidationError(
            "Assignment id must be a number") from None
    if get_assignment(out["assignment_id"]) is None:
        raise ValidationError(
            f"No assignment #{out['assignment_id']}")

    sid = _require(payload.get("student_id"), "Student").strip()
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    out["student_id"] = sid

    status = (payload.get("status") or DEFAULT_SUBMISSION_STATUS).strip()
    if status not in SUBMISSION_STATUSES:
        raise ValidationError(
            f"Submission status must be one of: "
            f"{', '.join(SUBMISSION_STATUSES)}")
    out["status"] = status

    out["submitted_on"] = _validate_date(
        payload.get("submitted_on"), "Submitted on")
    out["marks"] = _validate_number(payload.get("marks"),
                                        "Marks", min_val=0)

    assignment = get_assignment(out["assignment_id"])
    if (assignment and assignment.max_marks is not None
            and out["marks"] is not None
            and out["marks"] > assignment.max_marks):
        raise ValidationError(
            f"Marks ({out['marks']}) exceed max_marks "
            f"({assignment.max_marks})")

    wc = _validate_number(payload.get("word_count"), "Word count",
                            min_val=0)
    out["word_count"] = int(wc) if wc is not None else None
    draft = payload.get("is_draft", False)
    out["is_draft"] = 1 if draft in (True, 1, "1", "Yes", "yes",
                                       "true") else 0

    out["grade"]      = (payload.get("grade") or "").strip() or None
    out["feedback"]   = (payload.get("feedback") or "").strip() or None
    out["marked_by"]  = (payload.get("marked_by") or "").strip() or None
    out["marked_on"]  = _validate_date(payload.get("marked_on"),
                                            "Marked on")
    out["notes"]      = (payload.get("notes") or "").strip() or None

    if (out["status"] in DONE_SUBMISSION_STATUSES
            and not out["submitted_on"]
            and out["status"] in ("Submitted", "Late", "Returned")):
        out["submitted_on"] = _dt.date.today().isoformat()
    if out["marks"] is not None and not out["marked_on"]:
        out["marked_on"] = _dt.date.today().isoformat()
    return out


# ── Assignment CRUD ───────────────────────────────────────────────

def create_assignment(payload: dict[str, Any]) -> Assignment:
    init_db()
    p = _validate_assignment_payload(payload)
    _validate_parent_link(None, p["parent_assignment_id"])
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO coursework_assignments
                   (title, subject_name, course_id, class_group_id,
                    year_group, assignment_type, teacher,
                    set_date, due_date, max_marks, weight_percent,
                    brief, rubric, resources, submission_method,
                    status, notes, word_limit, allow_resubmission,
                    similarity_threshold,
                    late_penalty_percent_per_day,
                    late_penalty_cap_percent, late_penalty_grace_days,
                    moderation_tolerance, honour_access_arrangements,
                    marking_sla_days, anonymous_marking,
                    release_policy, release_on, appeal_window_days,
                    is_group_assignment, peer_assessment_weight,
                    self_assessment_required, parent_assignment_id,
                    component_weight,
                    qualification, exam_board, spec_code, unit_code,
                    component_code, assessment_objectives,
                    is_template, template_name,
                    shared_with_department, source_assignment_id,
                    times_reused, estimated_hours,
                    auto_publish, published_on, reminder_days,
                    chase_enabled, parent_visible, calendar_event_id,
                    cover_marker, cover_from, cover_until,
                    cover_reason,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["title"], p["subject_name"], p["course_id"],
             p["class_group_id"], p["year_group"],
             p["assignment_type"], p["teacher"],
             p["set_date"], p["due_date"], p["max_marks"],
             p["weight_percent"], p["brief"], p["rubric"],
             p["resources"], p["submission_method"],
             p["status"], p["notes"], p["word_limit"],
             p["allow_resubmission"], p["similarity_threshold"],
             p["late_penalty_percent_per_day"],
             p["late_penalty_cap_percent"],
             p["late_penalty_grace_days"],
             p["moderation_tolerance"],
             p["honour_access_arrangements"],
             p["marking_sla_days"], p["anonymous_marking"],
             p["release_policy"], p["release_on"],
             p["appeal_window_days"], p["is_group_assignment"],
             p["peer_assessment_weight"],
             p["self_assessment_required"],
             p["parent_assignment_id"], p["component_weight"],
             p["qualification"], p["exam_board"], p["spec_code"],
             p["unit_code"], p["component_code"],
             p["assessment_objectives"], p["is_template"],
             p["template_name"], p["shared_with_department"],
             p["source_assignment_id"], p["times_reused"],
             p["estimated_hours"], p["auto_publish"],
             p["published_on"], p["reminder_days"],
             p["chase_enabled"], p["parent_visible"],
             p["calendar_event_id"], p["cover_marker"],
             p["cover_from"], p["cover_until"], p["cover_reason"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_assignment(new_id)
    assert out is not None
    logger.info(
        "Created assignment #%d %r (%s, due %s, status %s)",
        new_id, p["title"], p["subject_name"], p["due_date"],
        p["status"])
    _notify_students_assignment_created(out)
    return out


def _students_on_course(course_id: int) -> list[str]:
    """Return distinct student_ids enrolled in any class group of a course."""
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    seen: set[str] = set()
    ordered: list[str] = []
    for g in _cg.list_groups(course_id=course_id):
        for sid in _cg.list_members(g.group_id):
            if sid not in seen:
                seen.add(sid)
                ordered.append(sid)
    return ordered


def _notify_students_assignment_created(a: Assignment) -> None:
    """Email every student on the assignment's course. Best-effort."""
    if a.course_id is None:
        return
    try:
        from education_system.systems.sixth_form import SYSTEM_NAME
        from education_system.systems.sixth_form.domain.academics.courses import (
            courses as _courses,
        )
        from education_system.systems.sixth_form.domain.operations.communications.messages import (
            email_templates,
        )
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        course = _courses.get_course(a.course_id)
        student_ids = _students_on_course(a.course_id)
        if not student_ids:
            logger.info(
                "Assignment #%d: no students on course #%d to notify",
                a.assignment_id, a.course_id)
            return
        sent = 0
        for sid in student_ids:
            student = _students.get_student(sid)
            if student is None:
                continue
            try:
                email_templates.send_from_template(
                    "assignment_set",
                    {
                        "system_name":       SYSTEM_NAME,
                        "first_name":        student.first_name,
                        "full_name":         student.full_name,
                        "student_id":        student.student_id,
                        "title":             a.title,
                        "subject_name":      a.subject_name,
                        "assignment_type":   a.assignment_type,
                        "teacher":           a.teacher or "your teacher",
                        "set_date":          a.set_date or "—",
                        "due_date":          a.due_date or "—",
                        "max_marks":         (str(a.max_marks)
                                                if a.max_marks is not None
                                                else "—"),
                        "submission_method": (a.submission_method
                                                or "see the portal"),
                        "brief":             (a.brief
                                                or "(See the portal for full details.)"),
                        "course_code":       (course.course_code
                                                if course else "—"),
                        "course_title":      (course.title
                                                if course else "—"),
                    },
                    to_name=student.full_name,
                    to_address=student.email,
                    student_id=student.student_id,
                )
                sent += 1
            except Exception:
                logger.exception(
                    "assignment_set email failed for student %s "
                    "(assignment #%d)",
                    sid, a.assignment_id)
        logger.info(
            "Assignment #%d: notified %d/%d student(s) on course #%d",
            a.assignment_id, sent, len(student_ids), a.course_id)
    except Exception:
        logger.exception(
            "Could not notify students for assignment #%d",
            a.assignment_id)


def get_assignment(assignment_id: int) -> Assignment | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM coursework_assignments WHERE assignment_id = ?",
            (assignment_id,)).fetchone()
        return _row_assignment(r) if r else None


def list_assignments(
    *,
    subject_name: str | None = None,
    teacher_like: str | None = None,
    status: str | None = None,
    assignment_type: str | None = None,
    year_group: str | None = None,
    course_id: int | None = None,
    class_group_id: int | None = None,
    open_only: bool = False,
    overdue_only: bool = False,
    title_like: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[Assignment]:
    init_db()
    clauses, args = [], []
    if subject_name:
        clauses.append("subject_name = ?")
        args.append(subject_name.strip())
    if teacher_like:
        clauses.append("teacher LIKE ?")
        args.append(f"%{teacher_like.strip()}%")
    if status:
        if status not in ASSIGNMENT_STATUSES:
            raise ValidationError(
                f"Status must be one of: "
                f"{', '.join(ASSIGNMENT_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if assignment_type:
        if assignment_type not in ASSIGNMENT_TYPES:
            raise ValidationError(
                f"Type must be one of: "
                f"{', '.join(ASSIGNMENT_TYPES)}")
        clauses.append("assignment_type = ?")
        args.append(assignment_type)
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year group must be one of: "
                f"{', '.join(YEAR_GROUPS)}")
        clauses.append("year_group = ?")
        args.append(year_group)
    if course_id is not None:
        clauses.append("course_id = ?")
        args.append(int(course_id))
    if class_group_id is not None:
        clauses.append("class_group_id = ?")
        args.append(int(class_group_id))
    if open_only:
        clauses.append("status IN ('Draft', 'Set')")
    if overdue_only:
        today = _dt.date.today().isoformat()
        clauses.append("due_date IS NOT NULL AND due_date < ? "
                       "AND status IN ('Draft', 'Set')")
        args.append(today)
    if title_like:
        clauses.append("title LIKE ?")
        args.append(f"%{title_like.strip()}%")
    if date_from:
        clauses.append("due_date >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("due_date <= ?")
        args.append(_validate_date(date_to, "date_to"))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM coursework_assignments {where} "
           "ORDER BY CASE WHEN due_date IS NULL THEN 1 ELSE 0 END, "
           "due_date ASC, assignment_id ASC")
    with _connect() as conn:
        return [_row_assignment(r)
                for r in conn.execute(sql, args).fetchall()]


def list_assignments_with_detail(**kwargs) -> list[AssignmentRow]:
    rows = list_assignments(**kwargs)
    if not rows:
        return []
    with _connect() as conn:
        out: list[AssignmentRow] = []
        for a in rows:
            stats = conn.execute(
                f"SELECT COUNT(*) total, "
                f"  SUM(CASE WHEN status IN "
                f"    ({','.join('?' * len(DONE_SUBMISSION_STATUSES))}) "
                f"    THEN 1 ELSE 0 END) AS done, "
                f"  SUM(CASE WHEN marks IS NOT NULL "
                f"    THEN 1 ELSE 0 END) AS marked, "
                f"  AVG(marks) AS avg_marks "
                f"FROM coursework_submissions "
                f"WHERE assignment_id = ?",
                (*DONE_SUBMISSION_STATUSES, a.assignment_id)).fetchone()
            out.append(AssignmentRow(
                assignment=a,
                total_submissions=stats["total"] or 0,
                submitted_count=stats["done"] or 0,
                marked_count=stats["marked"] or 0,
                average_mark=(round(stats["avg_marks"], 2)
                                if stats["avg_marks"] is not None
                                else None),
            ))
    return out


def get_assignment_detail(assignment_id: int) -> AssignmentDetail | None:
    init_db()
    a = get_assignment(assignment_id)
    if a is None:
        return None
    subs = list_submissions(assignment_id=assignment_id)
    return AssignmentDetail(assignment=a, submissions=subs)


def update_assignment(assignment_id: int,
                       payload: dict[str, Any]) -> Assignment:
    init_db()
    existing = get_assignment(assignment_id)
    if existing is None:
        raise ValidationError(f"No assignment #{assignment_id}")
    merged = {
        "title":             payload.get("title", existing.title),
        "subject_name":      payload.get("subject_name",
                                          existing.subject_name),
        "course_id":         payload.get("course_id",
                                          existing.course_id),
        "class_group_id":    payload.get("class_group_id",
                                          existing.class_group_id),
        "year_group":        payload.get("year_group",
                                          existing.year_group),
        "assignment_type":   payload.get("assignment_type",
                                          existing.assignment_type),
        "teacher":           payload.get("teacher", existing.teacher),
        "set_date":          payload.get("set_date",
                                          existing.set_date),
        "due_date":          payload.get("due_date",
                                          existing.due_date),
        "max_marks":         payload.get("max_marks",
                                          existing.max_marks),
        "weight_percent":    payload.get("weight_percent",
                                          existing.weight_percent),
        "brief":             payload.get("brief", existing.brief),
        "rubric":            payload.get("rubric", existing.rubric),
        "resources":         payload.get("resources",
                                          existing.resources),
        "submission_method": payload.get("submission_method",
                                          existing.submission_method),
        "status":            payload.get("status", existing.status),
        "notes":             payload.get("notes", existing.notes),
        "word_limit":        payload.get("word_limit",
                                          existing.word_limit),
        "allow_resubmission": payload.get("allow_resubmission",
                                            existing.allow_resubmission),
        "similarity_threshold": payload.get(
            "similarity_threshold", existing.similarity_threshold),
        "late_penalty_percent_per_day": payload.get(
            "late_penalty_percent_per_day",
            existing.late_penalty_percent_per_day),
        "late_penalty_cap_percent": payload.get(
            "late_penalty_cap_percent",
            existing.late_penalty_cap_percent),
        "late_penalty_grace_days": payload.get(
            "late_penalty_grace_days", existing.late_penalty_grace_days),
        "moderation_tolerance": payload.get(
            "moderation_tolerance", existing.moderation_tolerance),
        "honour_access_arrangements": payload.get(
            "honour_access_arrangements",
            existing.honour_access_arrangements),
        "marking_sla_days": payload.get("marking_sla_days",
                                          existing.marking_sla_days),
        "anonymous_marking": payload.get("anonymous_marking",
                                           existing.anonymous_marking),
        "release_policy": payload.get("release_policy",
                                        existing.release_policy),
        "release_on": payload.get("release_on", existing.release_on),
        "appeal_window_days": payload.get("appeal_window_days",
                                            existing.appeal_window_days),
        "is_group_assignment": payload.get(
            "is_group_assignment", existing.is_group_assignment),
        "peer_assessment_weight": payload.get(
            "peer_assessment_weight", existing.peer_assessment_weight),
        "self_assessment_required": payload.get(
            "self_assessment_required",
            existing.self_assessment_required),
        "parent_assignment_id": payload.get(
            "parent_assignment_id", existing.parent_assignment_id),
        "component_weight": payload.get("component_weight",
                                          existing.component_weight),
    }
    for key in ("qualification", "exam_board", "spec_code",
                 "unit_code", "component_code",
                 "assessment_objectives", "is_template",
                 "template_name", "shared_with_department",
                 "source_assignment_id", "times_reused",
                 "estimated_hours", "auto_publish", "published_on",
                 "reminder_days", "chase_enabled", "parent_visible",
                 "calendar_event_id", "cover_marker", "cover_from",
                 "cover_until", "cover_reason"):
        merged[key] = payload.get(key, getattr(existing, key))
    p = _validate_assignment_payload(merged)
    _validate_parent_link(assignment_id, p["parent_assignment_id"])
    with _connect() as conn:
        conn.execute(
            """UPDATE coursework_assignments SET
                   title = ?, subject_name = ?, course_id = ?,
                   class_group_id = ?, year_group = ?,
                   assignment_type = ?, teacher = ?, set_date = ?,
                   due_date = ?, max_marks = ?, weight_percent = ?,
                   brief = ?, rubric = ?, resources = ?,
                   submission_method = ?, status = ?, notes = ?,
                   word_limit = ?, allow_resubmission = ?,
                   similarity_threshold = ?,
                   late_penalty_percent_per_day = ?,
                   late_penalty_cap_percent = ?,
                   late_penalty_grace_days = ?,
                   moderation_tolerance = ?,
                   honour_access_arrangements = ?,
                   marking_sla_days = ?, anonymous_marking = ?,
                   release_policy = ?, release_on = ?,
                   appeal_window_days = ?, is_group_assignment = ?,
                   peer_assessment_weight = ?,
                   self_assessment_required = ?,
                   parent_assignment_id = ?, component_weight = ?,
                   qualification = ?, exam_board = ?, spec_code = ?,
                   unit_code = ?, component_code = ?,
                   assessment_objectives = ?, is_template = ?,
                   template_name = ?, shared_with_department = ?,
                   source_assignment_id = ?, times_reused = ?,
                   estimated_hours = ?, auto_publish = ?,
                   published_on = ?, reminder_days = ?,
                   chase_enabled = ?, parent_visible = ?,
                   calendar_event_id = ?, cover_marker = ?,
                   cover_from = ?, cover_until = ?, cover_reason = ?,
                   updated_at = datetime('now')
               WHERE assignment_id = ?""",
            (p["title"], p["subject_name"], p["course_id"],
             p["class_group_id"], p["year_group"],
             p["assignment_type"], p["teacher"],
             p["set_date"], p["due_date"], p["max_marks"],
             p["weight_percent"], p["brief"], p["rubric"],
             p["resources"], p["submission_method"],
             p["status"], p["notes"], p["word_limit"],
             p["allow_resubmission"], p["similarity_threshold"],
             p["late_penalty_percent_per_day"],
             p["late_penalty_cap_percent"],
             p["late_penalty_grace_days"],
             p["moderation_tolerance"],
             p["honour_access_arrangements"],
             p["marking_sla_days"], p["anonymous_marking"],
             p["release_policy"], p["release_on"],
             p["appeal_window_days"], p["is_group_assignment"],
             p["peer_assessment_weight"],
             p["self_assessment_required"],
             p["parent_assignment_id"], p["component_weight"],
             p["qualification"], p["exam_board"], p["spec_code"],
             p["unit_code"], p["component_code"],
             p["assessment_objectives"], p["is_template"],
             p["template_name"], p["shared_with_department"],
             p["source_assignment_id"], p["times_reused"],
             p["estimated_hours"], p["auto_publish"],
             p["published_on"], p["reminder_days"],
             p["chase_enabled"], p["parent_visible"],
             p["calendar_event_id"], p["cover_marker"],
             p["cover_from"], p["cover_until"], p["cover_reason"],
             assignment_id),
        )
        conn.commit()
    out = get_assignment(assignment_id)
    assert out is not None
    logger.info("Updated assignment #%d (status=%s)",
                assignment_id, out.status)
    return out


def set_assignment_status(assignment_id: int,
                          status: str) -> Assignment:
    if status not in ASSIGNMENT_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(ASSIGNMENT_STATUSES)}")
    return update_assignment(assignment_id, {"status": status})


def delete_assignment(assignment_id: int) -> bool:
    init_db()
    with _connect() as conn:
        # Collect file paths before the cascade removes the rows that
        # point at them — SQLite cannot delete from disk.
        stored = _stored_paths_for_assignment(conn, assignment_id)
        receipts = [r["receipt_path"] for r in conn.execute(
            """SELECT receipt_path FROM coursework_submission_versions
               WHERE receipt_path IS NOT NULL
                 AND submission_id IN (SELECT submission_id
                                         FROM coursework_submissions
                                        WHERE assignment_id = ?)""",
            (assignment_id,)).fetchall()]
        cur = conn.execute(
            "DELETE FROM coursework_assignments WHERE assignment_id = ?",
            (assignment_id,))
        conn.commit()
        deleted = bool(cur.rowcount)
    if deleted:
        _unlink_stored(stored + receipts)
        logger.info(
            "Deleted assignment #%d (cascade: submissions, versions, "
            "%d file(s))", assignment_id, len(stored) + len(receipts))
    return deleted


# ── Submission CRUD ───────────────────────────────────────────────

def add_student(assignment_id: int, student_id: str, *,
                 status: str = DEFAULT_SUBMISSION_STATUS,
                 apply_access_arrangements: bool = True) -> Submission:
    """Put a student on an assignment.

    Their exam-access arrangements are honoured on the way in, so a
    student with extra time gets their deadline uplift without anyone
    having to remember. Set ``apply_access_arrangements=False`` to skip
    that (bulk imports that will sweep afterwards).
    """
    sub = create_submission({
        "assignment_id": assignment_id,
        "student_id": student_id,
        "status": status,
    })
    if not apply_access_arrangements:
        return sub
    try:
        from education_system.systems.sixth_form.domain.academics.assignments import (
            assignments_marking as _marking,
        )
        _marking.apply_access_arrangements_to(sub.submission_id)
    except Exception:
        # SEND data is optional; never block adding a student over it.
        logger.exception(
            "Could not apply access arrangements to submission #%d",
            sub.submission_id)
    out = get_submission(sub.submission_id)
    return out if out is not None else sub


def add_class_group(assignment_id: int, group_id: int) -> int:
    """Bulk-add every member of a class group as a submission row.
    Returns the number of new rows created."""
    init_db()
    if get_assignment(assignment_id) is None:
        raise ValidationError(f"No assignment #{assignment_id}")
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    if _cg.get_group(group_id) is None:
        raise ValidationError(f"No class group #{group_id}")
    members = _cg.list_members(group_id)
    n = 0
    for sid in members:
        try:
            add_student(assignment_id, sid)
            n += 1
        except ValidationError as e:
            if "already exists" in str(e).lower():
                continue
            # Likely UNIQUE constraint at the DB level
            logger.debug("Skipping %s: %s", sid, e)
    return n


def create_submission(payload: dict[str, Any]) -> Submission:
    init_db()
    p = _validate_submission_payload(payload)
    with _connect() as conn:
        if conn.execute(
                "SELECT 1 FROM coursework_submissions "
                "WHERE assignment_id = ? AND student_id = ?",
                (p["assignment_id"], p["student_id"])).fetchone():
            raise ValidationError(
                f"Student {p['student_id']} already has a "
                f"submission row for assignment "
                f"#{p['assignment_id']}")
        cur = conn.execute(
            """INSERT INTO coursework_submissions
                   (assignment_id, student_id, status, submitted_on,
                    marks, grade, feedback, marked_by, marked_on,
                    notes, word_count, is_draft,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["assignment_id"], p["student_id"], p["status"],
             p["submitted_on"], p["marks"], p["grade"],
             p["feedback"], p["marked_by"], p["marked_on"],
             p["notes"], p["word_count"], p["is_draft"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_submission(new_id)
    assert out is not None
    logger.info("Created submission #%d for student %s on assignment #%d",
                new_id, p["student_id"], p["assignment_id"])
    return out


def get_submission(submission_id: int) -> Submission | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM coursework_submissions "
            "WHERE submission_id = ?",
            (submission_id,)).fetchone()
        return _row_submission(r) if r else None


def list_submissions(
    *,
    assignment_id: int | None = None,
    student_id: str | None = None,
    status: str | None = None,
    done_only: bool = False,
    marked_only: bool = False,
    unmarked_only: bool = False,
) -> list[Submission]:
    init_db()
    clauses, args = [], []
    if assignment_id is not None:
        clauses.append("assignment_id = ?")
        args.append(int(assignment_id))
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if status:
        if status not in SUBMISSION_STATUSES:
            raise ValidationError(
                f"Status must be one of: "
                f"{', '.join(SUBMISSION_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if done_only:
        ph = ",".join("?" * len(DONE_SUBMISSION_STATUSES))
        clauses.append(f"status IN ({ph})")
        args.extend(DONE_SUBMISSION_STATUSES)
    if marked_only:
        clauses.append("marks IS NOT NULL")
    if unmarked_only:
        clauses.append("marks IS NULL")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM coursework_submissions {where} "
           "ORDER BY assignment_id ASC, student_id ASC")
    with _connect() as conn:
        return [_row_submission(r)
                for r in conn.execute(sql, args).fetchall()]


def list_submissions_with_detail(**kwargs) -> list[SubmissionRow]:
    rows = list_submissions(**kwargs)
    if not rows:
        return []
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    names = {s.student_id: s.full_name for s in _students.list_students()}
    return [SubmissionRow(submission=s,
                          student_name=names.get(s.student_id,
                                                   "(unknown)"))
            for s in rows]


def update_submission(submission_id: int,
                       payload: dict[str, Any]) -> Submission:
    init_db()
    existing = get_submission(submission_id)
    if existing is None:
        raise ValidationError(f"No submission #{submission_id}")
    merged = {
        "assignment_id": existing.assignment_id,
        "student_id":    existing.student_id,
        "status":        payload.get("status", existing.status),
        "submitted_on":  payload.get("submitted_on",
                                      existing.submitted_on),
        "marks":         payload.get("marks", existing.marks),
        "grade":         payload.get("grade", existing.grade),
        "feedback":      payload.get("feedback", existing.feedback),
        "marked_by":     payload.get("marked_by", existing.marked_by),
        "marked_on":     payload.get("marked_on", existing.marked_on),
        "notes":         payload.get("notes", existing.notes),
        "word_count":    payload.get("word_count", existing.word_count),
        "is_draft":      payload.get("is_draft", existing.is_draft),
    }
    p = _validate_submission_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE coursework_submissions SET
                   status = ?, submitted_on = ?, marks = ?,
                   grade = ?, feedback = ?, marked_by = ?,
                   marked_on = ?, notes = ?, word_count = ?,
                   is_draft = ?,
                   updated_at = datetime('now')
               WHERE submission_id = ?""",
            (p["status"], p["submitted_on"], p["marks"],
             p["grade"], p["feedback"], p["marked_by"],
             p["marked_on"], p["notes"], p["word_count"],
             p["is_draft"], submission_id),
        )
        conn.commit()
    out = get_submission(submission_id)
    assert out is not None
    _audit_mark_edit(submission_id, existing, out)
    return out


def _audit_mark_edit(submission_id: int, before: Submission,
                      after: Submission) -> None:
    """Log a mark or grade edit made through the generic update path.

    ``marking.apply_marks`` writes its own audit rows, so this only
    catches edits that bypass the pipeline — a hand-corrected mark in
    the GUI, for instance. Best-effort: an audit failure must never
    lose the edit the user just made.
    """
    changes = [(f, getattr(before, f), getattr(after, f))
               for f in ("marks", "grade")
               if getattr(before, f) != getattr(after, f)]
    if not changes:
        return
    try:
        from education_system.systems.sixth_form.domain.academics.assignments import (
            assignments_marking as _marking,
        )
        for field_name, old, new in changes:
            _marking.record_mark_change(
                submission_id, field=field_name,
                old_value=None if old is None else str(old),
                new_value=None if new is None else str(new),
                source="manual", reason="Edited directly",
                changed_by=after.marked_by)
    except Exception:
        logger.exception("Could not audit mark edit on submission #%d",
                          submission_id)


def mark_submission(submission_id: int, *,
                     marks: float | None = None,
                     grade: str | None = None,
                     feedback: str | None = None,
                     marked_by: str | None = None) -> Submission:
    """Award a mark, running the full marking pipeline.

    ``marks`` is the raw mark the marker awarded. The pipeline in
    ``assignments_marking`` applies any late penalty, derives the grade
    from the assignment's boundaries when one isn't given, and records
    the change in the audit trail. See :func:`marking.apply_marks`.
    """
    from education_system.systems.sixth_form.domain.academics.assignments import (
        assignments_marking as _marking,
    )
    return _marking.apply_marks(
        submission_id, raw_marks=marks, grade=grade,
        feedback=feedback, marked_by=marked_by, source="manual")


def submit(submission_id: int, *,
            late: bool | None = None,
            submitted_on: str | None = None,
            files: Sequence[str | Path] | None = None,
            word_count: int | None = None,
            is_draft: bool = False,
            submitted_by: str | None = None) -> Submission:
    """Record a hand-in. Thin wrapper over :func:`submit_work`.

    ``late`` now defaults to ``None`` meaning "work it out from the
    deadline" — pass ``True``/``False`` to override that judgement.
    """
    submit_work(submission_id, files=files, word_count=word_count,
                 is_draft=is_draft, submitted_on=submitted_on,
                 submitted_by=submitted_by, late=late)
    out = get_submission(submission_id)
    assert out is not None
    return out


def set_submission_status(submission_id: int,
                          status: str) -> Submission:
    return update_submission(submission_id, {"status": status})


def delete_submission(submission_id: int) -> bool:
    init_db()
    with _connect() as conn:
        stored = _stored_paths_for_submission(conn, submission_id)
        cur = conn.execute(
            "DELETE FROM coursework_submissions "
            "WHERE submission_id = ?",
            (submission_id,))
        conn.commit()
        deleted = bool(cur.rowcount)
    if deleted:
        _unlink_stored(stored)
        logger.info("Deleted submission #%d (%d file(s))",
                    submission_id, len(stored))
    return deleted


# ── Multi-part assignments ────────────────────────────────────────

def _validate_parent_link(assignment_id: int | None,
                           parent_id: int | None) -> None:
    """Refuse a parent link that would create a cycle or a deep tree.

    Composition is deliberately one level: an NEA has components, but a
    component cannot itself have components. Two levels would make the
    weighted rollup ambiguous without buying anything a flat list of
    components doesn't already give you.
    """
    if parent_id is None:
        return
    if assignment_id is not None and parent_id == assignment_id:
        raise ValidationError("An assignment cannot be its own parent")
    parent = get_assignment(parent_id)
    if parent is None:
        raise ValidationError(f"No assignment #{parent_id} to be a parent")
    if parent.parent_assignment_id is not None:
        raise ValidationError(
            f"Assignment #{parent_id} is itself a component — "
            f"components cannot be nested")
    if assignment_id is not None and list_components(assignment_id):
        raise ValidationError(
            f"Assignment #{assignment_id} already has components of its "
            f"own, so it cannot become a component")


def list_components(assignment_id: int) -> list[Assignment]:
    """Child assignments that make up this one, in due-date order."""
    init_db()
    with _connect() as conn:
        return [_row_assignment(r) for r in conn.execute(
            "SELECT * FROM coursework_assignments "
            "WHERE parent_assignment_id = ? "
            "ORDER BY CASE WHEN due_date IS NULL THEN 1 ELSE 0 END, "
            "due_date ASC, assignment_id ASC",
            (int(assignment_id),)).fetchall()]


@dataclass
class ComponentMark:
    """One component's contribution to a student's overall mark."""

    assignment: Assignment
    submission: Submission | None
    weight: float
    percent: float | None = None

    @property
    def contribution(self) -> float | None:
        """Weighted percentage points this component contributes."""
        if self.percent is None:
            return None
        return round(self.percent * self.weight / 100.0, 2)


@dataclass
class ComponentRollup:
    """A student's overall mark across a multi-part assignment."""

    assignment_id: int
    student_id: str
    components: list[ComponentMark] = field(default_factory=list)
    total_weight: float = 0.0
    weighted_percent: float | None = None
    overall_marks: float | None = None
    grade: str | None = None

    @property
    def complete(self) -> bool:
        return bool(self.components) and all(
            c.percent is not None for c in self.components)

    @property
    def message(self) -> str:
        if not self.components:
            return "No components"
        marked = sum(1 for c in self.components if c.percent is not None)
        head = f"{marked}/{len(self.components)} components marked"
        if abs(self.total_weight - 100.0) > 0.001:
            head += f"; weights total {self.total_weight:g}% (not 100%)"
        if self.weighted_percent is not None:
            head += f"; {self.weighted_percent:g}% overall"
        return head


def component_weights(assignment_id: int) -> dict[int, float]:
    """Each component's share, defaulting to an even split.

    A department that hasn't set weights almost always means "these
    count equally", so that is what an unweighted rubric produces
    rather than a zero.
    """
    components = list_components(assignment_id)
    if not components:
        return {}
    stated = {c.assignment_id: c.component_weight for c in components}
    if all(w is None for w in stated.values()):
        even = round(100.0 / len(components), 4)
        return {cid: even for cid in stated}
    # Partly weighted: unstated components share whatever is left.
    used = sum(w for w in stated.values() if w is not None)
    blanks = [cid for cid, w in stated.items() if w is None]
    share = round(max(0.0, 100.0 - used) / len(blanks), 4) if blanks else 0.0
    return {cid: (w if w is not None else share)
            for cid, w in stated.items()}


def component_rollup(assignment_id: int,
                      student_id: str) -> ComponentRollup:
    """Combine a student's component marks into one overall result.

    Percentages are combined rather than raw marks, so components with
    different maximums weigh correctly against each other.
    """
    init_db()
    parent = get_assignment(assignment_id)
    if parent is None:
        raise ValidationError(f"No assignment #{assignment_id}")
    weights = component_weights(assignment_id)
    out = ComponentRollup(assignment_id=assignment_id,
                           student_id=str(student_id).strip())
    for component in list_components(assignment_id):
        subs = list_submissions(assignment_id=component.assignment_id,
                                 student_id=out.student_id)
        sub = subs[0] if subs else None
        percent = None
        if (sub is not None and sub.marks is not None
                and component.max_marks):
            percent = round(100.0 * sub.marks / component.max_marks, 2)
        out.components.append(ComponentMark(
            assignment=component, submission=sub,
            weight=weights.get(component.assignment_id, 0.0),
            percent=percent))
    out.total_weight = round(sum(c.weight for c in out.components), 4)

    scored = [c for c in out.components if c.percent is not None]
    if scored:
        # Rescale by the weight actually marked so a part-marked NEA
        # reports the student's standing so far rather than a figure
        # dragged down by components that haven't been marked yet.
        weight_marked = sum(c.weight for c in scored)
        if weight_marked > 0:
            out.weighted_percent = round(
                sum((c.contribution or 0) for c in scored)
                / weight_marked * 100.0, 2)
            if parent.max_marks:
                out.overall_marks = round(
                    parent.max_marks * out.weighted_percent / 100.0, 2)
    if out.weighted_percent is not None:
        try:
            from education_system.systems.sixth_form.domain.academics.assignments import (
                assignments_marking as _marking,
            )
            out.grade = _marking.pct_to_letter(out.weighted_percent)
        except Exception:
            logger.debug("Could not resolve a rollup grade",
                          exc_info=True)
    return out


def apply_component_rollup(assignment_id: int, student_id: str, *,
                            marked_by: str | None = None
                            ) -> Submission | None:
    """Write a student's rolled-up component mark onto the parent.

    The student needs a submission row on the parent for the overall
    mark to land on; without one there is nothing to write to and this
    returns ``None``.
    """
    rollup = component_rollup(assignment_id, student_id)
    if rollup.overall_marks is None:
        return None
    subs = list_submissions(assignment_id=assignment_id,
                             student_id=rollup.student_id)
    if not subs:
        return None
    from education_system.systems.sixth_form.domain.academics.assignments import (
        assignments_marking as _marking,
    )
    return _marking.apply_marks(
        subs[0].submission_id, raw_marks=rollup.overall_marks,
        marked_by=marked_by, source="manual",
        reason=(f"Rolled up from {len(rollup.components)} component(s): "
                f"{rollup.weighted_percent:g}% weighted"))


def rollup_all(assignment_id: int, *,
                marked_by: str | None = None) -> dict[str, int]:
    """Roll every student's components up onto the parent assignment."""
    init_db()
    done = skipped = 0
    for sub in list_submissions(assignment_id=assignment_id):
        if apply_component_rollup(assignment_id, sub.student_id,
                                   marked_by=marked_by) is not None:
            done += 1
        else:
            skipped += 1
    logger.info("Component rollup on assignment #%d: %d applied, "
                "%d incomplete", assignment_id, done, skipped)
    return {"applied": done, "skipped": skipped}


# ── Attachments ───────────────────────────────────────────────────

def _files_root() -> Path:
    root = paths.SIXTH_FORM_COURSEWORK_FILES_DIR
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_filename(name: Any) -> str:
    """Reduce a user-supplied name to something safe to write to disk.

    Strips any directory component first — a browser upload can carry
    ``../../etc/passwd`` as its filename — then collapses everything
    outside ``[A-Za-z0-9._-]``.
    """
    stem = Path(str(name or "")).name.strip()
    cleaned = _UNSAFE_FILENAME_RE.sub("_", stem).strip("._-")
    return cleaned[:120] or "file"


def _check_attachment_name(filename: str) -> None:
    suffix = Path(filename).suffix.lower()
    if suffix in BLOCKED_ATTACHMENT_SUFFIXES:
        raise ValidationError(
            f"{suffix} files are not accepted as coursework attachments")


def _attachment_dir(*, assignment_id: int,
                     submission_id: int | None = None,
                     attempt_no: int | None = None) -> Path:
    """Relative directory (under the file root) for a new attachment."""
    if submission_id is None:
        return Path(f"assignment_{assignment_id}") / "material"
    leaf = ("attempt_%d" % attempt_no) if attempt_no else "loose"
    return (Path(f"assignment_{assignment_id}")
            / f"submission_{submission_id}" / leaf)


def _validate_attachment_kind(kind: Any, *, for_assignment: bool) -> str:
    allowed = (ASSIGNMENT_ATTACHMENT_KINDS if for_assignment
                else SUBMISSION_ATTACHMENT_KINDS)
    default = (DEFAULT_ASSIGNMENT_ATTACHMENT_KIND if for_assignment
                else DEFAULT_SUBMISSION_ATTACHMENT_KIND)
    value = (str(kind).strip() if kind not in (None, "") else default)
    if value not in allowed:
        raise ValidationError(
            f"Attachment kind must be one of: {', '.join(allowed)}")
    return value


def attach_file(*,
                 source_path: str | Path | None = None,
                 data: bytes | None = None,
                 filename: str | None = None,
                 assignment_id: int | None = None,
                 submission_id: int | None = None,
                 version_id: int | None = None,
                 kind: str | None = None,
                 uploaded_by: str | None = None,
                 notes: str | None = None) -> Attachment:
    """Copy a file into the coursework store and record its metadata.

    Give either ``source_path`` (a file on disk) or ``data`` (bytes,
    for an upload that never touched the filesystem) plus ``filename``.
    Exactly one of ``assignment_id`` / ``submission_id`` identifies the
    owner; ``version_id`` optionally pins the file to one attempt.

    The stored copy is content-hashed so a submission receipt can prove
    later that the file has not been swapped.
    """
    init_db()
    if (assignment_id is None) == (submission_id is None):
        raise ValidationError(
            "Attach to exactly one of an assignment or a submission")
    if (source_path is None) == (data is None):
        raise ValidationError(
            "Provide exactly one of source_path or data")

    if source_path is not None:
        src = Path(source_path).expanduser()
        if not src.is_file():
            raise ValidationError(f"No such file: {src}")
        size = src.stat().st_size
        name = filename or src.name
    else:
        assert data is not None
        size = len(data)
        if not filename:
            raise ValidationError("filename is required with data=")
        name = filename

    if size == 0:
        raise ValidationError("File is empty")
    if size > MAX_ATTACHMENT_BYTES:
        raise ValidationError(
            f"File is {size / 1048576:.1f} MB — the limit is "
            f"{MAX_ATTACHMENT_BYTES // 1048576} MB")

    safe = _safe_filename(name)
    _check_attachment_name(safe)

    # Resolve the owning assignment (and attempt) so the file lands in
    # a directory that mirrors the record structure.
    attempt_no: int | None = None
    if assignment_id is not None:
        if get_assignment(assignment_id) is None:
            raise ValidationError(f"No assignment #{assignment_id}")
        owning_assignment = assignment_id
        for_assignment = True
    else:
        sub = get_submission(int(submission_id))  # type: ignore[arg-type]
        if sub is None:
            raise ValidationError(f"No submission #{submission_id}")
        owning_assignment = sub.assignment_id
        for_assignment = False
        if version_id is not None:
            version = get_version(version_id)
            if version is None or version.submission_id != sub.submission_id:
                raise ValidationError(
                    f"Version #{version_id} does not belong to "
                    f"submission #{sub.submission_id}")
            attempt_no = version.attempt_no

    kind_value = _validate_attachment_kind(kind,
                                            for_assignment=for_assignment)

    rel_dir = _attachment_dir(assignment_id=owning_assignment,
                               submission_id=submission_id,
                               attempt_no=attempt_no)
    abs_dir = _files_root() / rel_dir
    abs_dir.mkdir(parents=True, exist_ok=True)
    # A uuid prefix keeps two students' "essay.docx" apart without
    # mangling the name staff see in the UI.
    stored_name = f"{uuid.uuid4().hex[:12]}_{safe}"
    dest = abs_dir / stored_name

    digest = hashlib.sha256()
    if source_path is not None:
        shutil.copyfile(Path(source_path).expanduser(), dest)
        with dest.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
    else:
        assert data is not None
        dest.write_bytes(data)
        digest.update(data)

    content_type = mimetypes.guess_type(safe)[0]
    rel_path = str(rel_dir / stored_name)

    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO coursework_attachments
                       (assignment_id, submission_id, version_id, kind,
                        filename, stored_path, byte_size, sha256,
                        content_type, uploaded_by, uploaded_at, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           datetime('now'), ?)""",
                (assignment_id, submission_id, version_id, kind_value,
                 safe, rel_path, size, digest.hexdigest(),
                 content_type, (uploaded_by or "").strip() or None,
                 (notes or "").strip() or None),
            )
            conn.commit()
            new_id = int(cur.lastrowid or 0)
    except Exception:
        # Never leave bytes on disk with no row pointing at them.
        dest.unlink(missing_ok=True)
        raise

    out = get_attachment(new_id)
    assert out is not None
    logger.info("Attached %r (%d bytes, %s) to %s #%s",
                safe, size, kind_value,
                "assignment" if for_assignment else "submission",
                assignment_id if for_assignment else submission_id)
    return out


def get_attachment(attachment_id: int) -> Attachment | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM coursework_attachments WHERE attachment_id = ?",
            (attachment_id,)).fetchone()
        return _row_attachment(r) if r else None


def list_attachments(*,
                      assignment_id: int | None = None,
                      submission_id: int | None = None,
                      version_id: int | None = None,
                      kind: str | None = None) -> list[Attachment]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if assignment_id is not None:
        clauses.append("assignment_id = ?")
        args.append(int(assignment_id))
    if submission_id is not None:
        clauses.append("submission_id = ?")
        args.append(int(submission_id))
    if version_id is not None:
        clauses.append("version_id = ?")
        args.append(int(version_id))
    if kind:
        clauses.append("kind = ?")
        args.append(str(kind).strip())
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        return [_row_attachment(r) for r in conn.execute(
            f"SELECT * FROM coursework_attachments {where} "
            "ORDER BY attachment_id ASC", args).fetchall()]


def delete_attachment(attachment_id: int) -> bool:
    """Remove the metadata row and unlink the stored file."""
    init_db()
    existing = get_attachment(attachment_id)
    if existing is None:
        return False
    with _connect() as conn:
        conn.execute(
            "DELETE FROM coursework_attachments WHERE attachment_id = ?",
            (attachment_id,))
        conn.commit()
    _unlink_stored([existing.stored_path])
    logger.info("Deleted attachment #%d (%s)",
                attachment_id, existing.filename)
    return True


def _unlink_stored(rel_paths: list[str]) -> None:
    """Best-effort removal of stored files and any dirs left empty."""
    root = paths.SIXTH_FORM_COURSEWORK_FILES_DIR
    parents: set[Path] = set()
    for rel in rel_paths:
        if not rel:
            continue
        target = root / rel
        try:
            target.unlink(missing_ok=True)
            parents.add(target.parent)
        except OSError:
            logger.warning("Could not remove coursework file %s", target)
    # Walk upwards removing directories that are now empty, stopping at
    # the store root.
    for parent in sorted(parents, key=lambda p: len(p.parts), reverse=True):
        node = parent
        while node != root and root in node.parents:
            try:
                node.rmdir()
            except OSError:
                break
            node = node.parent


def _stored_paths_for_assignment(conn: sqlite3.Connection,
                                  assignment_id: int) -> list[str]:
    rows = conn.execute(
        """SELECT stored_path FROM coursework_attachments
           WHERE assignment_id = ?
              OR submission_id IN (SELECT submission_id
                                     FROM coursework_submissions
                                    WHERE assignment_id = ?)""",
        (assignment_id, assignment_id)).fetchall()
    return [r["stored_path"] for r in rows]


def _stored_paths_for_submission(conn: sqlite3.Connection,
                                  submission_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT stored_path FROM coursework_attachments "
        "WHERE submission_id = ?", (submission_id,)).fetchall()
    paths_out = [r["stored_path"] for r in rows]
    receipts = conn.execute(
        "SELECT receipt_path FROM coursework_submission_versions "
        "WHERE submission_id = ? AND receipt_path IS NOT NULL",
        (submission_id,)).fetchall()
    paths_out.extend(r["receipt_path"] for r in receipts)
    return paths_out


# ── Word limits ───────────────────────────────────────────────────

def check_word_limit(assignment: Assignment,
                      word_count: int | None) -> WordLimitCheck:
    """Compare a word count against the brief's limit.

    Over-limit never blocks a submission — boards expect the marker to
    apply the penalty — so this returns a report rather than raising.
    """
    limit = assignment.word_limit
    if limit is None or word_count is None:
        return WordLimitCheck(limit=limit, word_count=word_count)
    over = max(0, int(word_count) - int(limit))
    within = int(word_count) <= int(limit) * (1 + WORD_LIMIT_TOLERANCE)
    return WordLimitCheck(limit=int(limit), word_count=int(word_count),
                           over_by=over, within_tolerance=within)


def count_words(text: str) -> int:
    """Whitespace word count — the same rule most boards apply."""
    return len(str(text or "").split())


# ── Extensions ────────────────────────────────────────────────────

def effective_due_date(submission: Submission,
                        assignment: Assignment | None = None) -> str | None:
    """The date this student is actually held to.

    An approved extension replaces the assignment's due date for that
    student alone; everything downstream (lateness at submit time, the
    late sweep, the overdue report) reads through here.
    """
    if submission.extended_due_date:
        return submission.extended_due_date
    if assignment is None:
        assignment = get_assignment(submission.assignment_id)
    return assignment.due_date if assignment else None


def grant_extension(submission_id: int, new_due_date: str, *,
                     reason: str,
                     authorised_by: str | None = None) -> Submission:
    """Give one student a later deadline, with an audit trail.

    If the sweep had already written the student off as ``Missing``,
    a future extension puts them back in play.
    """
    init_db()
    sub = get_submission(submission_id)
    if sub is None:
        raise ValidationError(f"No submission #{submission_id}")
    new_date = _validate_date(new_due_date, "Extended due date",
                               required=True)
    assert new_date is not None    # required=True guarantees it
    reason_text = _require(reason, "Extension reason").strip()

    assignment = get_assignment(sub.assignment_id)
    if (assignment and assignment.due_date
            and new_date <= assignment.due_date):
        raise ValidationError(
            f"Extension ({new_date}) must be after the original due "
            f"date ({assignment.due_date})")

    today = _dt.date.today().isoformat()
    restore = (sub.status == "Missing" and new_date >= today)
    with _connect() as conn:
        conn.execute(
            """UPDATE coursework_submissions SET
                   extended_due_date = ?, extension_reason = ?,
                   extension_by = ?, extension_on = ?,
                   status = CASE WHEN ? THEN 'Not Started' ELSE status END,
                   updated_at = datetime('now')
               WHERE submission_id = ?""",
            (new_date, reason_text,
             (authorised_by or "").strip() or None, today,
             1 if restore else 0, submission_id))
        conn.commit()
    out = get_submission(submission_id)
    assert out is not None
    logger.info(
        "Extension granted on submission #%d (student %s) to %s by %s: %s",
        submission_id, out.student_id, new_date,
        authorised_by or "(unrecorded)", reason_text)
    return out


def revoke_extension(submission_id: int) -> Submission:
    """Withdraw an extension, restoring the assignment's own due date."""
    init_db()
    if get_submission(submission_id) is None:
        raise ValidationError(f"No submission #{submission_id}")
    with _connect() as conn:
        conn.execute(
            """UPDATE coursework_submissions SET
                   extended_due_date = NULL, extension_reason = NULL,
                   extension_by = NULL, extension_on = NULL,
                   updated_at = datetime('now')
               WHERE submission_id = ?""", (submission_id,))
        conn.commit()
    out = get_submission(submission_id)
    assert out is not None
    logger.info("Extension revoked on submission #%d", submission_id)
    return out


def list_extensions(*, assignment_id: int | None = None) -> list[Submission]:
    init_db()
    clauses = ["extended_due_date IS NOT NULL"]
    args: list[Any] = []
    if assignment_id is not None:
        clauses.append("assignment_id = ?")
        args.append(int(assignment_id))
    with _connect() as conn:
        return [_row_submission(r) for r in conn.execute(
            "SELECT * FROM coursework_submissions WHERE "
            + " AND ".join(clauses)
            + " ORDER BY extended_due_date ASC", args).fetchall()]


# ── Submission versions (drafts + resubmission) ───────────────────

def get_version(version_id: int) -> SubmissionVersion | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM coursework_submission_versions "
            "WHERE version_id = ?", (version_id,)).fetchone()
        return _row_version(r) if r else None


def list_versions(submission_id: int) -> list[SubmissionVersion]:
    init_db()
    with _connect() as conn:
        return [_row_version(r) for r in conn.execute(
            "SELECT * FROM coursework_submission_versions "
            "WHERE submission_id = ? ORDER BY attempt_no ASC",
            (int(submission_id),)).fetchall()]


def latest_version(submission_id: int) -> SubmissionVersion | None:
    versions = list_versions(submission_id)
    return versions[-1] if versions else None


def submit_work(submission_id: int, *,
                 files: Sequence[str | Path] | None = None,
                 word_count: int | None = None,
                 is_draft: bool = False,
                 submitted_on: str | None = None,
                 submitted_by: str | None = None,
                 note: str | None = None,
                 late: bool | None = None,
                 issue_receipt: bool = True,
                 force: bool = False) -> SubmissionVersion:
    """Record one attempt at a submission: files, word count, receipt.

    Every call appends a new version rather than overwriting the last,
    so a draft → feedback → final cycle keeps the whole trail.

    A *draft* deliberately leaves the submission ``In Progress``: the
    student still owes the final piece, and the late sweep should still
    chase them for it. A final attempt sets ``Submitted`` or ``Late``,
    decided against :func:`effective_due_date` so an approved extension
    is honoured.

    Pass ``force=True`` to override a closed assignment or a
    resubmission lock (staff acting on a student's behalf).
    """
    init_db()
    sub = get_submission(submission_id)
    if sub is None:
        raise ValidationError(f"No submission #{submission_id}")
    assignment = get_assignment(sub.assignment_id)
    if assignment is None:
        raise ValidationError(f"No assignment #{sub.assignment_id}")

    if not force and assignment.status in ("Closed", "Graded", "Archived"):
        raise ValidationError(
            f"Assignment #{assignment.assignment_id} is {assignment.status}"
            f" — it is closed to submissions")

    existing = list_versions(submission_id)
    if (not force and not is_draft and not assignment.allow_resubmission
            and any(not v.is_draft for v in existing)):
        raise ValidationError(
            "This assignment does not allow resubmission — a final "
            "attempt has already been recorded")

    when = _validate_date(submitted_on, "Submitted on") \
        or _dt.date.today().isoformat()
    wc = _validate_number(word_count, "Word count", min_val=0)
    wc_int = int(wc) if wc is not None else None

    due = effective_due_date(sub, assignment)
    if late is None:
        late = bool(due and when > due)
    if is_draft:
        # A draft is progress, not a hand-in.
        status = "In Progress"
    else:
        status = "Late" if late else "Submitted"

    attempt_no = (existing[-1].attempt_no + 1) if existing else 1

    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO coursework_submission_versions
                   (submission_id, attempt_no, is_draft, status,
                    submitted_on, submitted_at, submitted_by,
                    word_count, note, created_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'), ?, ?, ?,
                       datetime('now'))""",
            (submission_id, attempt_no, 1 if is_draft else 0, status,
             when, (submitted_by or "").strip() or None, wc_int,
             (note or "").strip() or None))
        conn.commit()
        version_id = int(cur.lastrowid or 0)

    for f in (files or []):
        attach_file(source_path=f, submission_id=submission_id,
                     version_id=version_id, kind="Work",
                     uploaded_by=submitted_by)

    # Roll the attempt up onto the submission row so the existing list
    # and summary views stay accurate without joining.
    with _connect() as conn:
        conn.execute(
            """UPDATE coursework_submissions SET
                   status = ?, attempt_no = ?, is_draft = ?,
                   word_count = COALESCE(?, word_count),
                   submitted_on = CASE WHEN ? THEN submitted_on ELSE ? END,
                   auto_status_on = NULL,
                   updated_at = datetime('now')
               WHERE submission_id = ?""",
            (status, attempt_no, 1 if is_draft else 0, wc_int,
             1 if is_draft else 0, when, submission_id))
        conn.commit()

    if issue_receipt:
        try:
            issue_submission_receipt(version_id)
        except Exception:
            logger.exception(
                "Receipt generation failed for version #%d "
                "(the submission itself is recorded)", version_id)

    out = get_version(version_id)
    assert out is not None
    check = check_word_limit(assignment, wc_int)
    if check.breached:
        logger.warning(
            "Submission #%d attempt %d is over the word limit: %s",
            submission_id, attempt_no, check.message)
    logger.info(
        "Recorded %s for submission #%d (student %s, attempt %d, "
        "status %s, %d file(s))",
        "draft" if is_draft else "submission", submission_id,
        sub.student_id, attempt_no, status, len(files or []))
    return out


# ── Submission receipts ───────────────────────────────────────────

def receipt_reference(assignment_id: int, submission_id: int,
                       attempt_no: int) -> str:
    return f"CW{assignment_id:04d}-{submission_id:05d}-A{attempt_no}"


def build_receipt_text(version_id: int) -> str:
    """Render the human-readable receipt for one attempt.

    Lists every file with its size and SHA-256 so the school can show
    later that what was marked is exactly what was handed in.
    """
    version = get_version(version_id)
    if version is None:
        raise ValidationError(f"No submission version #{version_id}")
    sub = get_submission(version.submission_id)
    assert sub is not None
    assignment = get_assignment(sub.assignment_id)
    assert assignment is not None

    student_name = sub.student_id
    try:
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        student = _students.get_student(sub.student_id)
        if student is not None:
            student_name = f"{student.full_name} ({sub.student_id})"
    except Exception:
        logger.debug("Could not resolve student name for receipt",
                      exc_info=True)

    files = list_attachments(version_id=version_id)
    due = effective_due_date(sub, assignment)
    check = check_word_limit(assignment, version.word_count)

    lines = [
        "SUBMISSION RECEIPT",
        "==================",
        f"Reference:    {version.receipt_ref or receipt_reference(assignment.assignment_id, sub.submission_id, version.attempt_no)}",
        f"Assignment:   #{assignment.assignment_id} {assignment.title}",
        f"Subject:      {assignment.subject_name}",
        f"Student:      {student_name}",
        f"Attempt:      {version.label}",
        f"Submitted on: {version.submitted_on} "
        f"(recorded {version.submitted_at} UTC)",
        f"Due:          {due or '—'}"
        + ("  [extension applied]" if sub.extended_due_date else ""),
        f"Status:       {version.status}",
    ]
    if check.applicable:
        lines.append(f"Word count:   {check.message}")
    elif version.word_count is not None:
        lines.append(f"Word count:   {version.word_count}")

    lines.append("")
    if files:
        lines.append(f"Files ({len(files)})")
        lines.append("-" * 40)
        for f in files:
            lines.append(f"  {f.filename}  [{f.size_label}]")
            lines.append(f"    sha256: {f.sha256 or '—'}")
    else:
        lines.append("Files: none attached "
                     "(submission recorded without an upload)")
    lines.append("")
    lines.append("Keep this receipt. If a submission is ever queried, "
                 "the reference and file hashes above")
    lines.append("identify exactly what was received and when.")
    return "\n".join(lines)


def issue_submission_receipt(version_id: int, *,
                              email: bool = True) -> SubmissionVersion:
    """Stamp a reference on an attempt, write the receipt, email it.

    The reference and hash are written back to the version row, and the
    receipt text is stored beside the submitted files.
    """
    init_db()
    version = get_version(version_id)
    if version is None:
        raise ValidationError(f"No submission version #{version_id}")
    sub = get_submission(version.submission_id)
    assert sub is not None

    ref = receipt_reference(sub.assignment_id, sub.submission_id,
                             version.attempt_no)
    files = list_attachments(version_id=version_id)
    # Hash over the content hashes: changing any file changes this.
    fingerprint = hashlib.sha256(
        "|".join([ref, version.submitted_at or "",
                  *(f.sha256 or "" for f in files)]).encode("utf-8")
    ).hexdigest()[:16]

    with _connect() as conn:
        conn.execute(
            "UPDATE coursework_submission_versions SET "
            "receipt_ref = ?, receipt_hash = ? WHERE version_id = ?",
            (ref, fingerprint, version_id))
        conn.execute(
            "UPDATE coursework_submissions SET receipt_ref = ?, "
            "updated_at = datetime('now') WHERE submission_id = ?",
            (ref, sub.submission_id))
        conn.commit()

    text = build_receipt_text(version_id)
    rel_dir = _attachment_dir(assignment_id=sub.assignment_id,
                               submission_id=sub.submission_id,
                               attempt_no=version.attempt_no)
    abs_dir = _files_root() / rel_dir
    abs_dir.mkdir(parents=True, exist_ok=True)
    rel_path = rel_dir / f"receipt_A{version.attempt_no}.txt"
    (_files_root() / rel_path).write_text(text, encoding="utf-8")

    with _connect() as conn:
        conn.execute(
            "UPDATE coursework_submission_versions SET receipt_path = ? "
            "WHERE version_id = ?", (str(rel_path), version_id))
        conn.commit()

    if email:
        _email_receipt(version_id, ref, fingerprint, text)

    out = get_version(version_id)
    assert out is not None
    logger.info("Issued receipt %s (hash %s) for version #%d",
                ref, fingerprint, version_id)
    return out


def _email_receipt(version_id: int, ref: str, fingerprint: str,
                    text: str) -> None:
    """Email the receipt to the student. Best-effort, like the
    assignment-set notification — a mail failure must never lose the
    submission that has already been recorded."""
    try:
        from education_system.systems.sixth_form import SYSTEM_NAME
        from education_system.systems.sixth_form.domain.operations.communications.messages import (
            email_templates,
        )
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        version = get_version(version_id)
        assert version is not None
        sub = get_submission(version.submission_id)
        assert sub is not None
        assignment = get_assignment(sub.assignment_id)
        assert assignment is not None
        student = _students.get_student(sub.student_id)
        if student is None:
            logger.info("No student record for %s — receipt %s not emailed",
                        sub.student_id, ref)
            return
        files = list_attachments(version_id=version_id)
        email_templates.send_from_template(
            "assignment_receipt",
            {
                "system_name":   SYSTEM_NAME,
                "first_name":    student.first_name,
                "full_name":     student.full_name,
                "student_id":    student.student_id,
                "title":         assignment.title,
                "subject_name":  assignment.subject_name,
                "reference":     ref,
                "fingerprint":   fingerprint,
                "attempt":       version.label,
                "submitted_on":  version.submitted_on,
                "submitted_at":  version.submitted_at,
                "status":        version.status,
                "due_date":      effective_due_date(sub, assignment) or "—",
                "file_count":    str(len(files)),
                "file_list":     ("\n".join(
                    f"  {f.filename} [{f.size_label}] sha256:{f.sha256}"
                    for f in files) or "  (no files attached)"),
                "receipt":       text,
            },
            to_name=student.full_name,
            to_address=student.email,
            student_id=student.student_id,
        )
        logger.info("Emailed receipt %s to %s", ref, sub.student_id)
    except Exception:
        logger.exception("Could not email receipt %s", ref)


# ── Similarity / plagiarism ───────────────────────────────────────

# Set by whatever integration the college actually buys. Called with
# (submission, attachments) and expected to return a SimilarityResult
# or None. Nothing ships wired up — the schema, threshold and flagged
# report below work whether or not a provider is registered.
_SIMILARITY_PROVIDER: Callable[
    [Submission, list[Attachment]], SimilarityResult | None] | None = None


def register_similarity_provider(
        fn: Callable[[Submission, list[Attachment]],
                      SimilarityResult | None]) -> None:
    """Install the plagiarism checker used by :func:`run_similarity_check`."""
    global _SIMILARITY_PROVIDER
    _SIMILARITY_PROVIDER = fn
    logger.info("Similarity provider registered: %s",
                getattr(fn, "__name__", fn))


def clear_similarity_provider() -> None:
    global _SIMILARITY_PROVIDER
    _SIMILARITY_PROVIDER = None


def record_similarity(submission_id: int, *,
                       score: float,
                       provider: str | None = None,
                       report_ref: str | None = None,
                       checked_on: str | None = None,
                       version_id: int | None = None) -> Submission:
    """Store a similarity score against a submission (and attempt).

    Above the assignment's threshold the result is logged as a flag for
    a human to review — this module never accuses anyone by itself.
    """
    init_db()
    sub = get_submission(submission_id)
    if sub is None:
        raise ValidationError(f"No submission #{submission_id}")
    value = _validate_number(score, "Similarity score",
                              min_val=0, max_val=100)
    if value is None:
        raise ValidationError("Similarity score is required")
    when = _validate_date(checked_on, "Checked on") \
        or _dt.date.today().isoformat()

    with _connect() as conn:
        conn.execute(
            """UPDATE coursework_submissions SET
                   similarity_score = ?, similarity_provider = ?,
                   similarity_report = ?, similarity_checked_on = ?,
                   updated_at = datetime('now')
               WHERE submission_id = ?""",
            (value, (provider or "").strip() or None,
             (report_ref or "").strip() or None, when, submission_id))
        if version_id is not None:
            conn.execute(
                "UPDATE coursework_submission_versions SET "
                "similarity_score = ? WHERE version_id = ? "
                "AND submission_id = ?",
                (value, version_id, submission_id))
        conn.commit()

    out = get_submission(submission_id)
    assert out is not None
    assignment = get_assignment(sub.assignment_id)
    threshold = (assignment.effective_similarity_threshold
                  if assignment else DEFAULT_SIMILARITY_THRESHOLD)
    if value >= threshold:
        logger.warning(
            "Similarity %.1f%% on submission #%d (student %s, "
            "assignment #%d) is at or above the %.1f%% threshold — "
            "flagged for review%s",
            value, submission_id, sub.student_id, sub.assignment_id,
            threshold,
            f" (report {report_ref})" if report_ref else "")
    return out


def run_similarity_check(submission_id: int) -> SimilarityResult | None:
    """Ask the registered provider to score a submission.

    Returns ``None`` when no provider is installed, so callers can
    offer the action without needing to know whether the college has
    an integration.
    """
    init_db()
    if _SIMILARITY_PROVIDER is None:
        logger.info("No similarity provider registered — skipping check "
                    "on submission #%d", submission_id)
        return None
    sub = get_submission(submission_id)
    if sub is None:
        raise ValidationError(f"No submission #{submission_id}")
    files = list_attachments(submission_id=submission_id, kind="Work")
    result = _SIMILARITY_PROVIDER(sub, files)
    if result is None:
        return None
    record_similarity(submission_id, score=result.score,
                       provider=result.provider,
                       report_ref=result.report_ref,
                       checked_on=result.checked_on)
    return result


def list_flagged_submissions(*, assignment_id: int | None = None
                              ) -> list[Submission]:
    """Submissions whose similarity score meets the review threshold."""
    init_db()
    clauses = ["s.similarity_score IS NOT NULL"]
    args: list[Any] = []
    if assignment_id is not None:
        clauses.append("s.assignment_id = ?")
        args.append(int(assignment_id))
    sql = ("SELECT s.* FROM coursework_submissions s "
           "JOIN coursework_assignments a "
           "  ON a.assignment_id = s.assignment_id "
           f"WHERE {' AND '.join(clauses)} "
           "  AND s.similarity_score >= "
           "      COALESCE(a.similarity_threshold, ?) "
           "ORDER BY s.similarity_score DESC")
    with _connect() as conn:
        return [_row_submission(r) for r in conn.execute(
            sql, (*args, DEFAULT_SIMILARITY_THRESHOLD)).fetchall()]


# ── Automatic late detection ──────────────────────────────────────

def list_overdue_submissions(*, today: str | None = None,
                              assignment_id: int | None = None
                              ) -> list[Submission]:
    """Open submissions past their (possibly extended) deadline."""
    init_db()
    day = _validate_date(today, "today") or _dt.date.today().isoformat()
    ph = ",".join("?" * len(PENDING_SUBMISSION_STATUSES))
    clauses = [f"s.status IN ({ph})", "a.status IN ('Draft', 'Set')"]
    args: list[Any] = list(PENDING_SUBMISSION_STATUSES)
    if assignment_id is not None:
        clauses.append("s.assignment_id = ?")
        args.append(int(assignment_id))
    sql = ("SELECT s.* FROM coursework_submissions s "
           "JOIN coursework_assignments a "
           "  ON a.assignment_id = s.assignment_id "
           f"WHERE {' AND '.join(clauses)} "
           "  AND COALESCE(s.extended_due_date, a.due_date) IS NOT NULL "
           "  AND COALESCE(s.extended_due_date, a.due_date) < ? "
           "ORDER BY COALESCE(s.extended_due_date, a.due_date) ASC")
    with _connect() as conn:
        return [_row_submission(r)
                for r in conn.execute(sql, (*args, day)).fetchall()]


def sweep_late_submissions(*, today: str | None = None,
                            assignment_id: int | None = None,
                            dry_run: bool = False) -> dict[str, int]:
    """Mark work that is past its deadline and never arrived.

    Only touches ``Not Started`` / ``In Progress`` rows on assignments
    that are still open, and reads the deadline through
    :func:`effective_due_date` so an extension protects that student.
    Idempotent: a second run over the same day changes nothing.

    Returns counts: ``overdue`` seen, ``marked_missing`` changed.
    """
    init_db()
    day = _validate_date(today, "today") or _dt.date.today().isoformat()
    overdue = list_overdue_submissions(today=day,
                                        assignment_id=assignment_id)
    if dry_run or not overdue:
        return {"overdue": len(overdue), "marked_missing": 0}

    ids = [s.submission_id for s in overdue]
    with _connect() as conn:
        conn.executemany(
            "UPDATE coursework_submissions SET status = 'Missing', "
            "auto_status_on = ?, updated_at = datetime('now') "
            "WHERE submission_id = ?",
            [(day, sid) for sid in ids])
        conn.commit()
    logger.info("Late sweep on %s: marked %d submission(s) Missing",
                day, len(ids))
    return {"overdue": len(overdue), "marked_missing": len(ids)}


# ── Summary ───────────────────────────────────────────────────────

def summary(*, upcoming_window_days: int = 14) -> Summary:
    init_db()
    today = _dt.date.today().isoformat()
    horizon = (_dt.date.today()
                + _dt.timedelta(days=upcoming_window_days)).isoformat()
    rows = list_assignments()
    by_status = {s: 0 for s in ASSIGNMENT_STATUSES}
    by_type = {t: 0 for t in ASSIGNMENT_TYPES}
    by_subject: dict[str, int] = {}
    open_count = 0
    overdue = 0
    upcoming = 0
    for a in rows:
        by_status[a.status] = by_status.get(a.status, 0) + 1
        by_type[a.assignment_type] = by_type.get(
            a.assignment_type, 0) + 1
        by_subject[a.subject_name] = by_subject.get(
            a.subject_name, 0) + 1
        if a.is_open:
            open_count += 1
            if a.is_overdue:
                overdue += 1
            elif a.due_date and today <= a.due_date <= horizon:
                upcoming += 1

    with _connect() as conn:
        tot = conn.execute(
            "SELECT COUNT(*) FROM coursework_submissions"
        ).fetchone()[0]
        done = conn.execute(
            f"SELECT COUNT(*) FROM coursework_submissions "
            f"WHERE status IN "
            f"({','.join('?' * len(DONE_SUBMISSION_STATUSES))})",
            DONE_SUBMISSION_STATUSES).fetchone()[0]
        marked = conn.execute(
            "SELECT COUNT(*) FROM coursework_submissions "
            "WHERE marks IS NOT NULL").fetchone()[0]
        extensions = conn.execute(
            "SELECT COUNT(*) FROM coursework_submissions "
            "WHERE extended_due_date IS NOT NULL").fetchone()[0]
        att = conn.execute(
            "SELECT COUNT(*) n, COALESCE(SUM(byte_size), 0) b "
            "FROM coursework_attachments").fetchone()

    return Summary(
        total_assignments=len(rows),
        by_status=by_status,
        by_type=by_type,
        by_subject=dict(sorted(by_subject.items(),
                                key=lambda kv: kv[1],
                                reverse=True)),
        open_count=open_count,
        overdue=overdue,
        upcoming_due=upcoming,
        total_submissions=tot,
        submitted_total=done,
        marked_total=marked,
        overdue_submissions=len(list_overdue_submissions(today=today)),
        active_extensions=extensions,
        flagged_similarity=len(list_flagged_submissions()),
        attachment_count=att["n"] or 0,
        attachment_bytes=att["b"] or 0,
    )
