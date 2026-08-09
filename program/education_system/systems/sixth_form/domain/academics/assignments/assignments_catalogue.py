"""Authoring a coursework assignment: specs, templates, variants, load.

Sibling to :mod:`assignments`. Where that module runs an assignment,
this one is about *writing* it well and reusing it:

* **Awarding-body metadata** — exam board, specification, unit and
  component codes, and assessment-objective mapping, so a piece of
  coursework can be traced to the thing it is evidence for.
* **Templates** — save an assignment as a template, then clone it into
  a new year with its rubric, questions and resources intact.
* **Department library** — the shared bank of assignments a department
  reuses rather than rewrites, ranked by how often they are taken up.
* **Differentiated variants** — foundation/higher tiers or scaffolded
  versions of one brief, issued per student without splitting the
  assignment in two.
* **Estimated hours** — the teacher's expected workload, aggregated per
  student across subjects so nobody's week quietly becomes 30 hours.

Cloning is the load-bearing operation here: it copies the *design* of
an assignment (brief, rubric, questions, variants, resources) and never
the *run* of it (students, submissions, marks, files).
"""

from __future__ import annotations

import datetime as _dt
import logging
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

QUALIFICATIONS: tuple[str, ...] = (
    "A-Level", "AS-Level", "BTEC", "Cambridge Technical",
    "EPQ", "Core Maths", "GCSE Resit", "Other",
)

EXAM_BOARDS: tuple[str, ...] = (
    "AQA", "Edexcel (Pearson)", "OCR", "WJEC/Eduqas",
    "Cambridge International", "Other",
)

# The common assessment objectives across A-Level specs. Free text is
# accepted too — boards differ and this is a convenience, not a rule.
COMMON_OBJECTIVES: tuple[str, ...] = (
    "AO1", "AO2", "AO3", "AO4", "AO5", "AO6",
)

# Tiers a differentiated variant can sit at.
VARIANT_TIERS: tuple[str, ...] = (
    "Foundation", "Core", "Higher", "Scaffolded", "Extension",
)
DEFAULT_VARIANT_TIER: str = "Core"

# A week carrying more coursework hours than this is worth a look. Not
# a rule — a study week legitimately runs hot.
WEEKLY_HOURS_WARNING: float = 12.0


_SCHEMA = """
CREATE TABLE IF NOT EXISTS coursework_variants (
    variant_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id     INTEGER NOT NULL,
    name              TEXT NOT NULL,
    tier              TEXT NOT NULL DEFAULT 'Core',
    brief             TEXT,
    resources         TEXT,
    max_marks         REAL,
    estimated_hours   REAL,
    notes             TEXT,
    is_default        INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (assignment_id) REFERENCES coursework_assignments(assignment_id)
        ON DELETE CASCADE,
    UNIQUE (assignment_id, name)
);

CREATE INDEX IF NOT EXISTS idx_cwvar_assign
    ON coursework_variants(assignment_id);
"""


# ── Dataclasses ───────────────────────────────────────────────────

@dataclass
class Variant:
    """A differentiated version of one brief."""

    variant_id: int
    assignment_id: int
    name: str
    tier: str
    brief: str | None
    resources: str | None
    max_marks: float | None
    estimated_hours: float | None
    notes: str | None
    is_default: bool
    created_at: str
    updated_at: str

    @property
    def label(self) -> str:
        return f"{self.name} ({self.tier})"


@dataclass
class CloneResult:
    """What a clone actually copied."""

    assignment: core.Assignment
    source_id: int
    criteria: int = 0
    questions: int = 0
    variants: int = 0
    attachments: int = 0

    @property
    def message(self) -> str:
        bits = [f"#{self.assignment.assignment_id} "
                f"{self.assignment.title!r}"]
        copied = [f"{self.criteria} criteria" if self.criteria else "",
                  f"{self.questions} questions" if self.questions else "",
                  f"{self.variants} variants" if self.variants else "",
                  f"{self.attachments} files" if self.attachments else ""]
        copied = [c for c in copied if c]
        if copied:
            bits.append("with " + ", ".join(copied))
        return " ".join(bits)


@dataclass
class LibraryEntry:
    """One reusable assignment in the department bank."""

    assignment: core.Assignment
    criteria: int = 0
    questions: int = 0
    variants: int = 0

    @property
    def is_template(self) -> bool:
        return self.assignment.is_template

    @property
    def label(self) -> str:
        a = self.assignment
        name = a.template_name or a.title
        suffix = " [template]" if a.is_template else ""
        return f"{name}{suffix}"

    @property
    def message(self) -> str:
        a = self.assignment
        bits = [a.subject_name, a.assignment_type]
        if a.spec_reference:
            bits.append(a.spec_reference)
        if self.criteria:
            bits.append(f"{self.criteria} criteria")
        if a.times_reused:
            bits.append(f"reused {a.times_reused}×")
        return " · ".join(bits)


@dataclass
class WorkloadWeek:
    """Coursework hours falling in one week for one student."""

    week_start: str
    hours: float = 0.0
    assignments: list[tuple[int, str, float]] = field(
        default_factory=list)

    @property
    def is_heavy(self) -> bool:
        return self.hours > WEEKLY_HOURS_WARNING

    @property
    def message(self) -> str:
        head = (f"week of {self.week_start}: {self.hours:g}h across "
                f"{len(self.assignments)} assignment(s)")
        return head + ("  ⚠ heavy" if self.is_heavy else "")


@dataclass
class WorkloadReport:
    student_id: str
    weeks: list[WorkloadWeek] = field(default_factory=list)

    @property
    def total_hours(self) -> float:
        return round(sum(w.hours for w in self.weeks), 2)

    @property
    def heaviest(self) -> WorkloadWeek | None:
        return max(self.weeks, key=lambda w: w.hours, default=None)

    @property
    def heavy_weeks(self) -> list[WorkloadWeek]:
        return [w for w in self.weeks if w.is_heavy]

    @property
    def message(self) -> str:
        if not self.weeks:
            return "No estimated hours on this student's assignments"
        head = (f"{self.total_hours:g}h over {len(self.weeks)} week(s)")
        if self.heavy_weeks:
            head += f"; {len(self.heavy_weeks)} over "
            head += f"{WEEKLY_HOURS_WARNING:g}h"
        return head


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
    core.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    logger.debug("Catalogue schema ready at %s", DB_PATH)
    _DB_READY = True


def _row_variant(r: sqlite3.Row) -> Variant:
    return Variant(
        variant_id=r["variant_id"],
        assignment_id=r["assignment_id"], name=r["name"],
        tier=r["tier"], brief=r["brief"], resources=r["resources"],
        max_marks=r["max_marks"],
        estimated_hours=r["estimated_hours"], notes=r["notes"],
        is_default=bool(r["is_default"]),
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _today() -> str:
    return _dt.date.today().isoformat()


def _require_assignment(assignment_id: int) -> core.Assignment:
    a = core.get_assignment(assignment_id)
    if a is None:
        raise ValidationError(f"No assignment #{assignment_id}")
    return a


# ── Awarding-body metadata (item 30) ──────────────────────────────

def set_specification(assignment_id: int, *,
                       qualification: str | None = None,
                       exam_board: str | None = None,
                       spec_code: str | None = None,
                       unit_code: str | None = None,
                       component_code: str | None = None,
                       objectives: str | list[str] | None = None
                       ) -> core.Assignment:
    """Record what awarding-body requirement this work evidences."""
    init_db()
    _require_assignment(assignment_id)
    payload: dict[str, Any] = {}
    if qualification is not None:
        payload["qualification"] = qualification
    if exam_board is not None:
        payload["exam_board"] = exam_board
    if spec_code is not None:
        payload["spec_code"] = spec_code
    if unit_code is not None:
        payload["unit_code"] = unit_code
    if component_code is not None:
        payload["component_code"] = component_code
    if objectives is not None:
        if isinstance(objectives, (list, tuple, set)):
            joined = ",".join(str(o).strip() for o in objectives
                               if str(o).strip())
        else:
            joined = ",".join(o.strip() for o in str(objectives).split(",")
                               if o.strip())
        payload["assessment_objectives"] = joined or None
    return core.update_assignment(assignment_id, payload)


def objective_coverage(*, subject_name: str | None = None,
                        qualification: str | None = None
                        ) -> dict[str, int]:
    """How many assignments evidence each assessment objective.

    The gap in this table is the point: an AO with no coursework behind
    it is one the cohort has never been assessed on.
    """
    init_db()
    counts: dict[str, int] = {}
    for a in core.list_assignments(subject_name=subject_name):
        if qualification and a.qualification != qualification:
            continue
        for objective in a.objective_list:
            counts[objective] = counts.get(objective, 0) + 1
    return dict(sorted(counts.items()))


def list_by_specification(*, exam_board: str | None = None,
                           spec_code: str | None = None,
                           unit_code: str | None = None,
                           objective: str | None = None
                           ) -> list[core.Assignment]:
    """Every assignment matching an awarding-body reference."""
    init_db()
    out = []
    for a in core.list_assignments():
        if exam_board and a.exam_board != exam_board:
            continue
        if spec_code and a.spec_code != spec_code:
            continue
        if unit_code and a.unit_code != unit_code:
            continue
        if objective and objective not in a.objective_list:
            continue
        out.append(a)
    return out


def specification_gaps(subject_name: str,
                        required: list[str] | None = None
                        ) -> list[str]:
    """Assessment objectives with no coursework evidencing them."""
    expected = list(required or COMMON_OBJECTIVES)
    covered = objective_coverage(subject_name=subject_name)
    return [o for o in expected if not covered.get(o)]


# ── Templates and the department library (items 31 and 32) ────────

def save_as_template(assignment_id: int, *,
                      template_name: str | None = None,
                      share: bool = True) -> core.Assignment:
    """Mark an assignment as a reusable template.

    The original keeps its students and marks — flagging it a template
    only says "this design is worth using again".
    """
    init_db()
    a = _require_assignment(assignment_id)
    return core.update_assignment(assignment_id, {
        "is_template": True,
        "template_name": (template_name or a.title).strip(),
        "shared_with_department": share,
    })


def unset_template(assignment_id: int) -> core.Assignment:
    init_db()
    _require_assignment(assignment_id)
    return core.update_assignment(assignment_id,
                                   {"is_template": False,
                                    "template_name": None})


def share_with_department(assignment_id: int, *,
                           shared: bool = True) -> core.Assignment:
    init_db()
    _require_assignment(assignment_id)
    return core.update_assignment(assignment_id,
                                   {"shared_with_department": shared})


def list_library(*, subject_name: str | None = None,
                  qualification: str | None = None,
                  templates_only: bool = False,
                  query: str | None = None) -> list[LibraryEntry]:
    """The department bank, most-reused first.

    Ranking by reuse puts the assignment colleagues actually pick at
    the top, which is a better signal than the date someone wrote it.
    """
    init_db()
    from education_system.systems.sixth_form.domain.academics.assignments import (
        assignments_assessment as _assess,
        assignments_marking as _marking,
    )
    out: list[LibraryEntry] = []
    for a in core.list_assignments(subject_name=subject_name):
        if not (a.is_template or a.shared_with_department):
            continue
        if templates_only and not a.is_template:
            continue
        if qualification and a.qualification != qualification:
            continue
        if query:
            haystack = " ".join(filter(None, [
                a.title, a.template_name, a.subject_name, a.brief,
                a.spec_reference])).lower()
            if query.strip().lower() not in haystack:
                continue
        try:
            criteria = len(_marking.list_criteria(a.assignment_id))
            questions = len(_assess.list_questions(a.assignment_id))
        except Exception:
            criteria = questions = 0
        out.append(LibraryEntry(
            assignment=a, criteria=criteria, questions=questions,
            variants=len(list_variants(a.assignment_id))))
    return sorted(out,
                   key=lambda e: (-e.assignment.times_reused,
                                   e.assignment.title.lower()))


def clone_assignment(assignment_id: int, *,
                      title: str | None = None,
                      set_date: str | None = None,
                      due_date: str | None = None,
                      teacher: str | None = None,
                      course_id: int | None = None,
                      status: str = "Draft",
                      copy_rubric: bool = True,
                      copy_questions: bool = True,
                      copy_variants: bool = True,
                      copy_attachments: bool = True,
                      created_by: str | None = None) -> CloneResult:
    """Copy an assignment's design into a fresh one.

    Copies the brief, rubric, objective questions, variants and
    teaching material. Deliberately does *not* copy students,
    submissions, marks, groups or the mark audit — a new run of an
    assignment starts empty, and silently inheriting last year's marks
    would be a data-protection incident waiting to happen.
    """
    init_db()
    source = _require_assignment(assignment_id)

    payload: dict[str, Any] = {
        "title": (title or source.title).strip(),
        "subject_name": source.subject_name,
        "assignment_type": source.assignment_type,
        "year_group": source.year_group,
        "teacher": teacher if teacher is not None else source.teacher,
        "course_id": (course_id if course_id is not None
                       else source.course_id),
        "class_group_id": None,
        "set_date": set_date or _today(),
        "due_date": due_date,
        "max_marks": source.max_marks,
        "weight_percent": source.weight_percent,
        "brief": source.brief,
        "rubric": source.rubric,
        "resources": source.resources,
        "submission_method": source.submission_method,
        "notes": source.notes,
        "status": status,
        "word_limit": source.word_limit,
        "allow_resubmission": source.allow_resubmission,
        "similarity_threshold": source.similarity_threshold,
        "late_penalty_percent_per_day":
            source.late_penalty_percent_per_day,
        "late_penalty_cap_percent": source.late_penalty_cap_percent,
        "late_penalty_grace_days": source.late_penalty_grace_days,
        "moderation_tolerance": source.moderation_tolerance,
        "honour_access_arrangements": source.honour_access_arrangements,
        "marking_sla_days": source.marking_sla_days,
        "anonymous_marking": source.anonymous_marking,
        "release_policy": source.release_policy,
        "release_on": None,
        "appeal_window_days": source.appeal_window_days,
        "is_group_assignment": source.is_group_assignment,
        "peer_assessment_weight": source.peer_assessment_weight,
        "self_assessment_required": source.self_assessment_required,
        "qualification": source.qualification,
        "exam_board": source.exam_board,
        "spec_code": source.spec_code,
        "unit_code": source.unit_code,
        "component_code": source.component_code,
        "assessment_objectives": source.assessment_objectives,
        "estimated_hours": source.estimated_hours,
        "reminder_days": source.reminder_days,
        "chase_enabled": source.chase_enabled,
        "parent_visible": source.parent_visible,
        "auto_publish": source.auto_publish,
        "source_assignment_id": source.assignment_id,
        # A clone is a working assignment, not another template, until
        # someone says otherwise.
        "is_template": False,
        "shared_with_department": False,
    }
    if payload["set_date"] and payload["due_date"] \
            and payload["due_date"] < payload["set_date"]:
        raise ValidationError(
            "Due date cannot be before set date")

    new_assignment = core.create_assignment(payload)
    result = CloneResult(assignment=new_assignment,
                          source_id=source.assignment_id)

    if copy_rubric:
        result.criteria = _clone_rubric(source.assignment_id,
                                         new_assignment.assignment_id)
    if copy_questions:
        result.questions = _clone_questions(
            source.assignment_id, new_assignment.assignment_id)
    if copy_variants:
        result.variants = _clone_variants(
            source.assignment_id, new_assignment.assignment_id)
    if copy_attachments:
        result.attachments = _clone_attachments(
            source.assignment_id, new_assignment.assignment_id,
            uploaded_by=created_by)

    with _connect() as conn:
        conn.execute(
            "UPDATE coursework_assignments SET "
            "times_reused = times_reused + 1, "
            "updated_at = datetime('now') WHERE assignment_id = ?",
            (source.assignment_id,))
        conn.commit()

    logger.info("Cloned assignment #%d into %s",
                source.assignment_id, result.message)
    return result


def _clone_rubric(source_id: int, target_id: int) -> int:
    try:
        from education_system.systems.sixth_form.domain.academics.assignments import (
            assignments_marking as _marking,
        )
        n = 0
        for c in _marking.list_criteria(source_id):
            _marking.add_criterion(target_id, {
                "code": c.code, "title": c.title,
                "descriptor": c.descriptor, "max_marks": c.max_marks,
                "weight_percent": c.weight_percent,
                "assessment_objective": c.assessment_objective,
                "position": c.position})
            n += 1
        boundaries = _marking.get_grade_boundaries(source_id)
        if boundaries is not None and boundaries.is_set:
            _marking.set_grade_boundaries(target_id, {
                letter: value
                for letter, value in boundaries.as_pairs()
                if value is not None})
        return n
    except Exception:
        logger.exception("Could not clone the rubric from #%d",
                          source_id)
        return 0


def _clone_questions(source_id: int, target_id: int) -> int:
    try:
        from education_system.systems.sixth_form.domain.academics.assignments import (
            assignments_assessment as _assess,
        )
        n = 0
        for q in _assess.list_questions(source_id):
            _assess.add_question(target_id, {
                "question_type": q.question_type, "prompt": q.prompt,
                "options": q.options, "answer_key": q.answer_key,
                "marks": q.marks, "tolerance": q.tolerance,
                "case_sensitive": q.case_sensitive,
                "accept_any_of": q.accept_any_of,
                "feedback_correct": q.feedback_correct,
                "feedback_wrong": q.feedback_wrong,
                "position": q.position})
            n += 1
        return n
    except Exception:
        logger.exception("Could not clone questions from #%d", source_id)
        return 0


def _clone_variants(source_id: int, target_id: int) -> int:
    n = 0
    for v in list_variants(source_id):
        add_variant(target_id, {
            "name": v.name, "tier": v.tier, "brief": v.brief,
            "resources": v.resources, "max_marks": v.max_marks,
            "estimated_hours": v.estimated_hours, "notes": v.notes,
            "is_default": v.is_default})
        n += 1
    return n


def _clone_attachments(source_id: int, target_id: int, *,
                        uploaded_by: str | None) -> int:
    """Copy teaching material, re-reading the bytes into a new file."""
    n = 0
    for att in core.list_attachments(assignment_id=source_id):
        if not att.exists:
            logger.warning(
                "Skipping missing attachment %r while cloning #%d",
                att.filename, source_id)
            continue
        try:
            core.attach_file(source_path=att.path,
                              assignment_id=target_id,
                              filename=att.filename, kind=att.kind,
                              uploaded_by=uploaded_by or att.uploaded_by,
                              notes=att.notes)
            n += 1
        except Exception:
            logger.exception("Could not copy attachment %r",
                              att.filename)
    return n


def clone_lineage(assignment_id: int) -> list[core.Assignment]:
    """Walk back through the chain of assignments this was cloned from."""
    init_db()
    out: list[core.Assignment] = []
    seen: set[int] = set()
    current = core.get_assignment(assignment_id)
    while current is not None and current.source_assignment_id:
        if current.source_assignment_id in seen:
            break        # defensive: a cycle should be impossible
        seen.add(current.source_assignment_id)
        parent = core.get_assignment(current.source_assignment_id)
        if parent is None:
            break
        out.append(parent)
        current = parent
    return out


# ── Differentiated variants (item 33) ─────────────────────────────

def add_variant(assignment_id: int,
                 payload: dict[str, Any]) -> Variant:
    """Add a tiered or scaffolded version of the brief."""
    init_db()
    _require_assignment(assignment_id)
    name = core._require(payload.get("name"), "Variant name").strip()
    tier = (payload.get("tier") or DEFAULT_VARIANT_TIER).strip()
    if tier not in VARIANT_TIERS:
        raise ValidationError(
            f"Variant tier must be one of: {', '.join(VARIANT_TIERS)}")
    max_marks = core._validate_number(payload.get("max_marks"),
                                       "Variant max marks", min_val=0)
    hours = core._validate_number(payload.get("estimated_hours"),
                                   "Estimated hours", min_val=0)
    default = payload.get("is_default", False)
    is_default = 0 if default in (False, 0, "0", "No", "no",
                                    "false", None, "") else 1

    with _connect() as conn:
        if conn.execute(
                "SELECT 1 FROM coursework_variants "
                "WHERE assignment_id = ? AND name = ?",
                (assignment_id, name)).fetchone():
            raise ValidationError(
                f"Assignment #{assignment_id} already has a variant "
                f"named {name!r}")
        if is_default:
            conn.execute(
                "UPDATE coursework_variants SET is_default = 0 "
                "WHERE assignment_id = ?", (assignment_id,))
        cur = conn.execute(
            """INSERT INTO coursework_variants
                   (assignment_id, name, tier, brief, resources,
                    max_marks, estimated_hours, notes, is_default,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (assignment_id, name, tier,
             (payload.get("brief") or "").strip() or None,
             (payload.get("resources") or "").strip() or None,
             max_marks, hours,
             (payload.get("notes") or "").strip() or None,
             is_default))
        conn.commit()
        new_id = int(cur.lastrowid or 0)
    out = get_variant(new_id)
    assert out is not None
    return out


def get_variant(variant_id: int) -> Variant | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM coursework_variants WHERE variant_id = ?",
            (variant_id,)).fetchone()
        return _row_variant(r) if r else None


def list_variants(assignment_id: int) -> list[Variant]:
    init_db()
    with _connect() as conn:
        return [_row_variant(r) for r in conn.execute(
            "SELECT * FROM coursework_variants WHERE assignment_id = ? "
            "ORDER BY variant_id ASC",
            (int(assignment_id),)).fetchall()]


def update_variant(variant_id: int,
                    payload: dict[str, Any]) -> Variant:
    init_db()
    existing = get_variant(variant_id)
    if existing is None:
        raise ValidationError(f"No variant #{variant_id}")
    name = core._require(payload.get("name", existing.name),
                          "Variant name").strip()
    tier = str(payload.get("tier", existing.tier)).strip()
    if tier not in VARIANT_TIERS:
        raise ValidationError(
            f"Variant tier must be one of: {', '.join(VARIANT_TIERS)}")

    def _text(key: str) -> str | None:
        value = payload.get(key, getattr(existing, key))
        return (str(value).strip() or None) if value else None

    with _connect() as conn:
        conn.execute(
            """UPDATE coursework_variants SET
                   name = ?, tier = ?, brief = ?, resources = ?,
                   max_marks = ?, estimated_hours = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE variant_id = ?""",
            (name, tier, _text("brief"), _text("resources"),
             core._validate_number(
                 payload.get("max_marks", existing.max_marks),
                 "Variant max marks", min_val=0),
             core._validate_number(
                 payload.get("estimated_hours",
                              existing.estimated_hours),
                 "Estimated hours", min_val=0),
             _text("notes"), variant_id))
        conn.commit()
    out = get_variant(variant_id)
    assert out is not None
    return out


def delete_variant(variant_id: int) -> bool:
    """Remove a variant. Students on it fall back to the base brief."""
    init_db()
    existing = get_variant(variant_id)
    if existing is None:
        return False
    with _connect() as conn:
        conn.execute(
            "UPDATE coursework_submissions SET variant_id = NULL, "
            "updated_at = datetime('now') WHERE variant_id = ?",
            (variant_id,))
        cur = conn.execute(
            "DELETE FROM coursework_variants WHERE variant_id = ?",
            (variant_id,))
        conn.commit()
        return bool(cur.rowcount)


def assign_variant(submission_id: int,
                    variant_id: int | None) -> core.Submission:
    """Issue one student a particular version of the brief."""
    init_db()
    sub = core.get_submission(submission_id)
    if sub is None:
        raise ValidationError(f"No submission #{submission_id}")
    if variant_id is not None:
        variant = get_variant(variant_id)
        if variant is None:
            raise ValidationError(f"No variant #{variant_id}")
        if variant.assignment_id != sub.assignment_id:
            raise ValidationError(
                f"Variant #{variant_id} belongs to assignment "
                f"#{variant.assignment_id}, not #{sub.assignment_id}")
    with _connect() as conn:
        conn.execute(
            "UPDATE coursework_submissions SET variant_id = ?, "
            "updated_at = datetime('now') WHERE submission_id = ?",
            (variant_id, submission_id))
        conn.commit()
    out = core.get_submission(submission_id)
    assert out is not None
    return out


def assign_default_variants(assignment_id: int) -> int:
    """Put everyone without a variant onto the default one."""
    init_db()
    default = next((v for v in list_variants(assignment_id)
                     if v.is_default), None)
    if default is None:
        return 0
    n = 0
    for sub in core.list_submissions(assignment_id=assignment_id):
        if sub.variant_id is None:
            assign_variant(sub.submission_id, default.variant_id)
            n += 1
    return n


def variant_brief(submission_id: int) -> str | None:
    """The brief this student should actually see.

    Falls back to the assignment's own brief when the student is on no
    variant, or the variant carries no brief of its own.
    """
    init_db()
    sub = core.get_submission(submission_id)
    if sub is None:
        raise ValidationError(f"No submission #{submission_id}")
    a = core.get_assignment(sub.assignment_id)
    if sub.variant_id is None:
        return a.brief if a else None
    variant = get_variant(sub.variant_id)
    if variant is None or not variant.brief:
        return a.brief if a else None
    return variant.brief


def variant_spread(assignment_id: int) -> dict[str, int]:
    """How many students sit on each variant."""
    init_db()
    names = {v.variant_id: v.label
             for v in list_variants(assignment_id)}
    out: dict[str, int] = {label: 0 for label in names.values()}
    out["(base brief)"] = 0
    for sub in core.list_submissions(assignment_id=assignment_id):
        key = names.get(sub.variant_id or -1, "(base brief)")
        out[key] = out.get(key, 0) + 1
    return out


# ── Estimated hours and workload (item 34) ────────────────────────

def _week_start(day: str) -> str:
    """Monday of the week a date falls in."""
    d = _dt.date.fromisoformat(day)
    return (d - _dt.timedelta(days=d.weekday())).isoformat()


def submission_hours(submission: core.Submission,
                     assignment: core.Assignment) -> float | None:
    """Expected hours for this student — variant overrides the base."""
    if submission.variant_id is not None:
        variant = get_variant(submission.variant_id)
        if variant is not None and variant.estimated_hours is not None:
            return variant.estimated_hours
    return assignment.estimated_hours


def student_workload(student_id: str, *,
                      date_from: str | None = None,
                      date_to: str | None = None) -> WorkloadReport:
    """Coursework hours per week for one student, across subjects.

    Hours land in the week the work is *due*, which is where students
    actually feel them, rather than spread evenly from the set date.
    """
    init_db()
    report = WorkloadReport(student_id=str(student_id).strip())
    buckets: dict[str, WorkloadWeek] = {}
    for sub in core.list_submissions(student_id=report.student_id):
        a = core.get_assignment(sub.assignment_id)
        if a is None or not a.due_date:
            continue
        if date_from and a.due_date < date_from:
            continue
        if date_to and a.due_date > date_to:
            continue
        hours = submission_hours(sub, a)
        if not hours:
            continue
        due = core.effective_due_date(sub, a) or a.due_date
        try:
            key = _week_start(due)
        except ValueError:
            continue
        week = buckets.setdefault(key, WorkloadWeek(week_start=key))
        week.hours = round(week.hours + hours, 2)
        week.assignments.append((a.assignment_id, a.title, hours))
    report.weeks = [buckets[k] for k in sorted(buckets)]
    return report


def cohort_workload(*, year_group: str | None = None,
                     date_from: str | None = None,
                     date_to: str | None = None
                     ) -> dict[str, WorkloadReport]:
    """Workload per student, heaviest first.

    The point of aggregating across subjects: no single department can
    see that its 6-hour essay landed in the same week as two others.
    """
    init_db()
    students: set[str] = set()
    for a in core.list_assignments(year_group=year_group):
        for sub in core.list_submissions(assignment_id=a.assignment_id):
            students.add(sub.student_id)
    reports = {sid: student_workload(sid, date_from=date_from,
                                      date_to=date_to)
               for sid in sorted(students)}
    return dict(sorted(reports.items(),
                        key=lambda kv: -kv[1].total_hours))


def heavy_weeks(*, year_group: str | None = None,
                 threshold: float | None = None
                 ) -> list[tuple[str, WorkloadWeek]]:
    """(student_id, week) pairs above the workload warning line."""
    limit = (threshold if threshold is not None
             else WEEKLY_HOURS_WARNING)
    out: list[tuple[str, WorkloadWeek]] = []
    for student_id, report in cohort_workload(
            year_group=year_group).items():
        for week in report.weeks:
            if week.hours > limit:
                out.append((student_id, week))
    return sorted(out, key=lambda pair: -pair[1].hours)


def assignment_hours_summary(assignment_id: int) -> dict[str, Any]:
    """What this assignment is expected to cost the cohort."""
    init_db()
    a = _require_assignment(assignment_id)
    subs = core.list_submissions(assignment_id=assignment_id)
    per_student = [submission_hours(s, a) for s in subs]
    known = [h for h in per_student if h]
    return {
        "assignment_id": assignment_id,
        "base_hours": a.estimated_hours,
        "students": len(subs),
        "with_estimate": len(known),
        "total_hours": round(sum(known), 2) if known else 0.0,
        "average_hours": (round(sum(known) / len(known), 2)
                           if known else None),
    }
