"""Sixth Form coursework assignments — constants, schema text, dataclasses and
``ValidationError`` (attachment / word-limit / similarity configuration included).

Split out of ``assignments.py``, which re-exports every name defined here."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
import datetime as _dt
import re
from education_system import paths
import logging

# Same logger object as before the split (named after the original module).
logger = logging.getLogger("education_system.systems.sixth_form.domain.academics.assignments.assignments")

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


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass
