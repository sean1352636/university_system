"""Assessment instruments: objective questions, groups, peer and self.

Sibling to :mod:`assignments_marking`, which covers the teacher's own
judgement. This module covers marks that come from somewhere else:

* **Objective questions** — multiple choice and short answer with a
  stored answer key, marked by the machine so the human only reads
  what needs reading.
* **Group assignments** — a group as a first-class thing, with a shared
  mark and a per-member adjustment for the member who did the work and
  the member who didn't.
* **Peer assessment** — students scoring each other against the rubric,
  contributing a configurable share of the mark.
* **Self-assessment** — the student's own prediction before submitting,
  compared to the actual mark afterwards.

None of these write the final mark directly. Objective marks and peer
scores are held on the submission for the teacher to fold in, and
:func:`apply_group_marks` routes through the marking pipeline like
everything else, so the late penalty, grade boundaries and audit trail
still apply.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.academics.assignments import (
    assignments_marking as marking,
)
from education_system.systems.sixth_form.domain.academics.assignments import (
    models as assignments_models,
    store as assignments_store,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ASSIGNMENTS_DB

ValidationError = assignments_models.ValidationError


# ── Vocabularies ──────────────────────────────────────────────────

QUESTION_TYPES: tuple[str, ...] = (
    "Multiple choice",
    "Multiple response",
    "Short answer",
    "Numeric",
    "True/False",
)
DEFAULT_QUESTION_TYPE: str = "Multiple choice"

# Types the machine can mark without a human. Anything else is stored
# for structure but left for the teacher.
AUTO_MARKABLE_TYPES: tuple[str, ...] = QUESTION_TYPES

GROUP_ROLES: tuple[str, ...] = (
    "Member", "Lead", "Scribe", "Presenter", "Researcher",
)
DEFAULT_GROUP_ROLE: str = "Member"

# How a peer score is turned into a number out of the rubric maximum.
PEER_SCORE_MODES: tuple[str, ...] = ("Average", "Median", "Trimmed mean")
DEFAULT_PEER_SCORE_MODE: str = "Average"

# Numeric answers rarely land exactly; the key can name its own
# tolerance, and this is the fallback.
DEFAULT_NUMERIC_TOLERANCE: float = 0.0

_WHITESPACE_RE = re.compile(r"\s+")
_PUNCTUATION_RE = re.compile(r"[^\w\s]")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS coursework_questions (
    question_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id     INTEGER NOT NULL,
    position          INTEGER NOT NULL DEFAULT 0,
    question_type     TEXT NOT NULL DEFAULT 'Multiple choice',
    prompt            TEXT NOT NULL,
    options           TEXT,
    answer_key        TEXT NOT NULL,
    marks             REAL NOT NULL DEFAULT 1,
    tolerance         REAL,
    case_sensitive    INTEGER NOT NULL DEFAULT 0,
    accept_any_of     INTEGER NOT NULL DEFAULT 1,
    feedback_correct  TEXT,
    feedback_wrong    TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (assignment_id) REFERENCES coursework_assignments(assignment_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS coursework_answers (
    answer_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id     INTEGER NOT NULL,
    question_id       INTEGER NOT NULL,
    response          TEXT,
    is_correct        INTEGER,
    marks_awarded     REAL,
    marked_on         TEXT,
    override_by       TEXT,
    override_reason   TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (submission_id) REFERENCES coursework_submissions(submission_id)
        ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES coursework_questions(question_id)
        ON DELETE CASCADE,
    UNIQUE (submission_id, question_id)
);

CREATE TABLE IF NOT EXISTS coursework_groups (
    group_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id     INTEGER NOT NULL,
    name              TEXT NOT NULL,
    notes             TEXT,
    group_marks       REAL,
    marked_by         TEXT,
    marked_on         TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (assignment_id) REFERENCES coursework_assignments(assignment_id)
        ON DELETE CASCADE,
    UNIQUE (assignment_id, name)
);

CREATE TABLE IF NOT EXISTS coursework_group_members (
    membership_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id          INTEGER NOT NULL,
    submission_id     INTEGER NOT NULL,
    role              TEXT NOT NULL DEFAULT 'Member',
    adjustment        REAL NOT NULL DEFAULT 0,
    adjustment_reason TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (group_id) REFERENCES coursework_groups(group_id)
        ON DELETE CASCADE,
    FOREIGN KEY (submission_id) REFERENCES coursework_submissions(submission_id)
        ON DELETE CASCADE,
    UNIQUE (submission_id)
);

CREATE TABLE IF NOT EXISTS coursework_peer_reviews (
    review_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id     INTEGER NOT NULL,
    reviewer_student  TEXT NOT NULL,
    criterion_id      INTEGER,
    marks             REAL,
    comment           TEXT,
    submitted_on      TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (submission_id) REFERENCES coursework_submissions(submission_id)
        ON DELETE CASCADE,
    FOREIGN KEY (criterion_id) REFERENCES coursework_rubric_criteria(criterion_id)
        ON DELETE CASCADE,
    UNIQUE (submission_id, reviewer_student, criterion_id)
);

CREATE INDEX IF NOT EXISTS idx_cwq_assign
    ON coursework_questions(assignment_id);
CREATE INDEX IF NOT EXISTS idx_cwans_sub
    ON coursework_answers(submission_id);
CREATE INDEX IF NOT EXISTS idx_cwgrp_assign
    ON coursework_groups(assignment_id);
CREATE INDEX IF NOT EXISTS idx_cwgrpmem_group
    ON coursework_group_members(group_id);
CREATE INDEX IF NOT EXISTS idx_cwpeer_sub
    ON coursework_peer_reviews(submission_id);
CREATE INDEX IF NOT EXISTS idx_cwpeer_reviewer
    ON coursework_peer_reviews(reviewer_student);
"""


# ── Dataclasses ───────────────────────────────────────────────────

@dataclass
class Question:
    question_id: int
    assignment_id: int
    position: int
    question_type: str
    prompt: str
    options: str | None
    answer_key: str
    marks: float
    tolerance: float | None
    case_sensitive: bool
    accept_any_of: bool
    feedback_correct: str | None
    feedback_wrong: str | None
    created_at: str
    updated_at: str

    @property
    def option_list(self) -> list[str]:
        return [o.strip() for o in (self.options or "").split("|")
                if o.strip()]

    @property
    def key_list(self) -> list[str]:
        return [k.strip() for k in (self.answer_key or "").split("|")
                if k.strip()]

    @property
    def is_auto_markable(self) -> bool:
        return self.question_type in AUTO_MARKABLE_TYPES


@dataclass
class Answer:
    answer_id: int
    submission_id: int
    question_id: int
    response: str | None
    is_correct: bool | None
    marks_awarded: float | None
    marked_on: str | None
    override_by: str | None
    override_reason: str | None
    created_at: str
    updated_at: str

    @property
    def is_overridden(self) -> bool:
        return bool(self.override_by)


@dataclass
class AutoMarkResult:
    submission_id: int
    questions: int = 0
    answered: int = 0
    correct: int = 0
    marks_awarded: float = 0.0
    marks_available: float = 0.0
    overridden: int = 0

    @property
    def percent(self) -> float | None:
        if not self.marks_available:
            return None
        return round(100.0 * self.marks_awarded
                      / self.marks_available, 1)

    @property
    def message(self) -> str:
        if not self.questions:
            return "No objective questions on this assignment"
        head = (f"{self.correct}/{self.answered} correct, "
                f"{self.marks_awarded:g}/{self.marks_available:g} marks")
        if self.answered < self.questions:
            head += f" ({self.questions - self.answered} unanswered)"
        if self.overridden:
            head += f"; {self.overridden} marked by hand"
        return head


@dataclass
class Group:
    group_id: int
    assignment_id: int
    name: str
    notes: str | None
    group_marks: float | None
    marked_by: str | None
    marked_on: str | None
    created_at: str
    updated_at: str


@dataclass
class GroupMember:
    membership_id: int
    group_id: int
    submission_id: int
    student_id: str
    student_name: str
    role: str
    adjustment: float
    adjustment_reason: str | None

    def effective_marks(self, group_marks: float | None) -> float | None:
        if group_marks is None:
            return None
        return round(max(0.0, group_marks + self.adjustment), 2)


@dataclass
class GroupDetail:
    group: Group
    members: list[GroupMember] = field(default_factory=list)

    @property
    def size(self) -> int:
        return len(self.members)

    @property
    def is_adjusted(self) -> bool:
        return any(m.adjustment for m in self.members)

    @property
    def message(self) -> str:
        head = f"{self.size} member(s)"
        if self.group.group_marks is not None:
            head += f", group mark {self.group.group_marks:g}"
        if self.is_adjusted:
            head += " (with per-member adjustments)"
        return head


@dataclass
class PeerReview:
    review_id: int
    submission_id: int
    reviewer_student: str
    criterion_id: int | None
    marks: float | None
    comment: str | None
    submitted_on: str | None
    created_at: str
    updated_at: str


@dataclass
class PeerSummary:
    submission_id: int
    reviewer_count: int = 0
    score: float | None = None
    spread: float | None = None
    per_criterion: dict[int, float] = field(default_factory=dict)

    @property
    def message(self) -> str:
        if not self.reviewer_count:
            return "No peer reviews"
        head = (f"{self.reviewer_count} reviewer(s), "
                f"score {self.score:g}" if self.score is not None
                else f"{self.reviewer_count} reviewer(s)")
        if self.spread is not None:
            head += f" (spread {self.spread:g})"
        return head


@dataclass
class SelfAssessment:
    submission_id: int
    predicted: float | None
    actual: float | None
    note: str | None
    assessed_on: str | None

    @property
    def gap(self) -> float | None:
        if self.predicted is None or self.actual is None:
            return None
        return round(self.actual - self.predicted, 2)

    @property
    def accuracy(self) -> str | None:
        """How well calibrated the student's self-belief was."""
        gap = self.gap
        if gap is None:
            return None
        if gap > 0:
            return "Underestimated"
        if gap < 0:
            return "Overestimated"
        return "Accurate"

    @property
    def message(self) -> str:
        if self.predicted is None:
            return "No self-assessment"
        if self.actual is None:
            return f"Predicted {self.predicted:g}, not yet marked"
        return (f"Predicted {self.predicted:g}, "
                f"actual {self.actual:g} — "
                f"{self.accuracy} by {abs(self.gap or 0):g}")


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
    # Peer reviews key off rubric criteria, so the marking schema has
    # to exist before ours.
    marking.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    logger.debug("Assessment schema ready at %s", DB_PATH)
    _DB_READY = True


def _today() -> str:
    return _dt.date.today().isoformat()


def _require_submission(submission_id: int) -> assignments_models.Submission:
    sub = assignments_store.get_submission(submission_id)
    if sub is None:
        raise ValidationError(f"No submission #{submission_id}")
    return sub


def _require_assignment(assignment_id: int) -> assignments_models.Assignment:
    a = assignments_store.get_assignment(assignment_id)
    if a is None:
        raise ValidationError(f"No assignment #{assignment_id}")
    return a


def _student_names() -> dict[str, str]:
    try:
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        return {s.student_id: s.full_name
                for s in _students.list_students()}
    except Exception:
        logger.debug("Student names unavailable", exc_info=True)
        return {}


def _row_question(r: sqlite3.Row) -> Question:
    return Question(
        question_id=r["question_id"],
        assignment_id=r["assignment_id"], position=r["position"],
        question_type=r["question_type"], prompt=r["prompt"],
        options=r["options"], answer_key=r["answer_key"],
        marks=r["marks"], tolerance=r["tolerance"],
        case_sensitive=bool(r["case_sensitive"]),
        accept_any_of=bool(r["accept_any_of"]),
        feedback_correct=r["feedback_correct"],
        feedback_wrong=r["feedback_wrong"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_answer(r: sqlite3.Row) -> Answer:
    return Answer(
        answer_id=r["answer_id"], submission_id=r["submission_id"],
        question_id=r["question_id"], response=r["response"],
        is_correct=(None if r["is_correct"] is None
                     else bool(r["is_correct"])),
        marks_awarded=r["marks_awarded"], marked_on=r["marked_on"],
        override_by=r["override_by"],
        override_reason=r["override_reason"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_group(r: sqlite3.Row) -> Group:
    return Group(
        group_id=r["group_id"], assignment_id=r["assignment_id"],
        name=r["name"], notes=r["notes"],
        group_marks=r["group_marks"], marked_by=r["marked_by"],
        marked_on=r["marked_on"], created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def _row_peer(r: sqlite3.Row) -> PeerReview:
    return PeerReview(
        review_id=r["review_id"], submission_id=r["submission_id"],
        reviewer_student=r["reviewer_student"],
        criterion_id=r["criterion_id"], marks=r["marks"],
        comment=r["comment"], submitted_on=r["submitted_on"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Objective questions and auto-marking (item 25) ────────────────

def add_question(assignment_id: int,
                  payload: dict[str, Any]) -> Question:
    """Add one auto-markable question with its answer key.

    ``options`` and ``answer_key`` are pipe-separated, so a multiple
    choice question is ``"A|B|C|D"`` with key ``"C"``, and a short
    answer accepting synonyms is key ``"photosynthesis|photo-synthesis"``.
    """
    init_db()
    _require_assignment(assignment_id)
    prompt = assignments_store._require(payload.get("prompt"), "Prompt").strip()
    answer_key = assignments_store._require(payload.get("answer_key"),
                                "Answer key").strip()
    kind = (payload.get("question_type")
             or DEFAULT_QUESTION_TYPE).strip()
    if kind not in QUESTION_TYPES:
        raise ValidationError(
            f"Question type must be one of: {', '.join(QUESTION_TYPES)}")
    marks = assignments_store._validate_number(payload.get("marks", 1),
                                   "Question marks", min_val=0)
    if marks is None:
        marks = 1.0
    tolerance = assignments_store._validate_number(payload.get("tolerance"),
                                       "Tolerance", min_val=0)

    options = (payload.get("options") or "").strip() or None
    if kind in ("Multiple choice", "Multiple response") and not options:
        raise ValidationError(
            f"{kind} questions need an options list "
            f"(pipe-separated, e.g. 'A|B|C|D')")
    if kind == "Numeric":
        for key in answer_key.split("|"):
            try:
                float(key.strip())
            except ValueError:
                raise ValidationError(
                    f"Numeric answer key {key.strip()!r} is not a "
                    f"number") from None

    position = assignments_store._validate_number(payload.get("position"),
                                      "Position", min_val=0)
    if position is None:
        with _connect() as conn:
            position = conn.execute(
                "SELECT COALESCE(MAX(position), 0) + 1 AS nxt "
                "FROM coursework_questions WHERE assignment_id = ?",
                (assignment_id,)).fetchone()["nxt"]

    def _flag(key: str, default: bool) -> int:
        value = payload.get(key, default)
        return 0 if value in (False, 0, "0", "No", "no", "false") else 1

    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO coursework_questions
                   (assignment_id, position, question_type, prompt,
                    options, answer_key, marks, tolerance,
                    case_sensitive, accept_any_of, feedback_correct,
                    feedback_wrong, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (assignment_id, int(position), kind, prompt, options,
             answer_key, marks, tolerance,
             _flag("case_sensitive", False),
             _flag("accept_any_of", True),
             (payload.get("feedback_correct") or "").strip() or None,
             (payload.get("feedback_wrong") or "").strip() or None))
        conn.commit()
        new_id = int(cur.lastrowid or 0)
    out = get_question(new_id)
    assert out is not None
    return out


def get_question(question_id: int) -> Question | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM coursework_questions WHERE question_id = ?",
            (question_id,)).fetchone()
        return _row_question(r) if r else None


def list_questions(assignment_id: int) -> list[Question]:
    init_db()
    with _connect() as conn:
        return [_row_question(r) for r in conn.execute(
            "SELECT * FROM coursework_questions WHERE assignment_id = ? "
            "ORDER BY position ASC, question_id ASC",
            (int(assignment_id),)).fetchall()]


def delete_question(question_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM coursework_questions WHERE question_id = ?",
            (question_id,))
        conn.commit()
        return bool(cur.rowcount)


def questions_total(assignment_id: int) -> float:
    return round(sum(q.marks for q in list_questions(assignment_id)), 2)


def _normalise(text: str, *, case_sensitive: bool) -> str:
    """Collapse the differences that shouldn't cost a student a mark."""
    value = _WHITESPACE_RE.sub(" ", str(text or "").strip())
    value = _PUNCTUATION_RE.sub("", value)
    return value if case_sensitive else value.casefold()


def check_answer(question: Question,
                  response: str | None) -> tuple[bool, float]:
    """Mark one response against the key. Returns (correct, marks).

    Short answers ignore case, surrounding whitespace and punctuation
    by default — a student who writes "Photosynthesis." has not got it
    wrong. Numeric answers honour the question's tolerance.
    """
    if response is None or not str(response).strip():
        return False, 0.0
    keys = question.key_list
    if not keys:
        return False, 0.0

    if question.question_type == "Numeric":
        try:
            given_number = float(str(response).strip())
        except ValueError:
            return False, 0.0
        tolerance = (question.tolerance
                     if question.tolerance is not None
                     else DEFAULT_NUMERIC_TOLERANCE)
        for key in keys:
            try:
                if abs(given_number - float(key)) <= tolerance:
                    return True, question.marks
            except ValueError:
                continue
        return False, 0.0

    if question.question_type == "Multiple response":
        # Order must not matter, but the set must match exactly —
        # partial credit would need a mark scheme this doesn't model.
        given_set = {_normalise(x, case_sensitive=question.case_sensitive)
                     for x in str(response).split("|") if x.strip()}
        key_set = {_normalise(k, case_sensitive=question.case_sensitive)
                   for k in keys}
        return (given_set == key_set,
                question.marks if given_set == key_set else 0.0)

    given = _normalise(response, case_sensitive=question.case_sensitive)
    for key in keys:
        if given == _normalise(key,
                                case_sensitive=question.case_sensitive):
            return True, question.marks
        if not question.accept_any_of:
            break
    return False, 0.0


def record_answer(submission_id: int, question_id: int, *,
                   response: str | None,
                   auto_mark: bool = True) -> Answer:
    """Store a student's response, marking it immediately by default."""
    init_db()
    sub = _require_submission(submission_id)
    question = get_question(question_id)
    if question is None:
        raise ValidationError(f"No question #{question_id}")
    if question.assignment_id != sub.assignment_id:
        raise ValidationError(
            f"Question #{question_id} belongs to assignment "
            f"#{question.assignment_id}, not #{sub.assignment_id}")

    correct: bool | None = None
    awarded: float | None = None
    marked_on: str | None = None
    if auto_mark and question.is_auto_markable:
        is_right, awarded = check_answer(question, response)
        correct = is_right
        marked_on = _today()

    with _connect() as conn:
        conn.execute(
            """INSERT INTO coursework_answers
                   (submission_id, question_id, response, is_correct,
                    marks_awarded, marked_on, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))
               ON CONFLICT (submission_id, question_id) DO UPDATE SET
                   response = excluded.response,
                   is_correct = excluded.is_correct,
                   marks_awarded = excluded.marks_awarded,
                   marked_on = excluded.marked_on,
                   override_by = NULL, override_reason = NULL,
                   updated_at = datetime('now')""",
            (submission_id, question_id,
             None if response is None else str(response),
             None if correct is None else int(correct),
             awarded, marked_on))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM coursework_answers "
            "WHERE submission_id = ? AND question_id = ?",
            (submission_id, question_id)).fetchone()
    return _row_answer(r)


def list_answers(submission_id: int) -> list[Answer]:
    init_db()
    with _connect() as conn:
        return [_row_answer(r) for r in conn.execute(
            "SELECT a.* FROM coursework_answers a "
            "JOIN coursework_questions q "
            "  ON q.question_id = a.question_id "
            "WHERE a.submission_id = ? "
            "ORDER BY q.position ASC, q.question_id ASC",
            (int(submission_id),)).fetchall()]


def override_answer(submission_id: int, question_id: int, *,
                     marks: float,
                     overridden_by: str,
                     reason: str | None = None) -> Answer:
    """Overrule the machine on one answer.

    Auto-marking is confidently wrong often enough — a correct answer
    phrased unusually, a key with a typo — that a human override has to
    be a first-class action rather than an edit to the answer key.
    """
    init_db()
    question = get_question(question_id)
    if question is None:
        raise ValidationError(f"No question #{question_id}")
    value = assignments_store._validate_number(marks, "Marks", min_val=0,
                                   max_val=question.marks)
    who = assignments_store._require(overridden_by, "Overridden by").strip()
    with _connect() as conn:
        cur = conn.execute(
            """UPDATE coursework_answers SET
                   marks_awarded = ?, is_correct = ?, marked_on = ?,
                   override_by = ?, override_reason = ?,
                   updated_at = datetime('now')
               WHERE submission_id = ? AND question_id = ?""",
            (value, int(bool(value and value >= question.marks)),
             _today(), who, (reason or "").strip() or None,
             submission_id, question_id))
        conn.commit()
        if not cur.rowcount:
            raise ValidationError(
                "There is no recorded answer to override")
        r = conn.execute(
            "SELECT * FROM coursework_answers "
            "WHERE submission_id = ? AND question_id = ?",
            (submission_id, question_id)).fetchone()
    logger.info("Answer to question #%d on submission #%d overridden "
                "to %s by %s", question_id, submission_id, value, who)
    return _row_answer(r)


def auto_mark(submission_id: int, *,
               store: bool = True) -> AutoMarkResult:
    """Re-mark every stored answer and total the objective section.

    The total is held in ``objective_marks`` rather than written to the
    submission's mark: on a mixed paper the teacher still has the essay
    to mark, and deciding how the two combine is their call.
    """
    init_db()
    sub = _require_submission(submission_id)
    questions = {q.question_id: q
                 for q in list_questions(sub.assignment_id)}
    result = AutoMarkResult(submission_id=submission_id,
                             questions=len(questions))
    result.marks_available = round(
        sum(q.marks for q in questions.values()), 2)

    for answer in list_answers(submission_id):
        question = questions.get(answer.question_id)
        if question is None:
            continue
        result.answered += 1
        if answer.is_overridden:
            result.overridden += 1
            awarded = answer.marks_awarded or 0.0
            if answer.is_correct:
                result.correct += 1
        else:
            is_right, awarded = check_answer(question, answer.response)
            if is_right:
                result.correct += 1
            if store:
                with _connect() as conn:
                    conn.execute(
                        "UPDATE coursework_answers SET is_correct = ?, "
                        "marks_awarded = ?, marked_on = ?, "
                        "updated_at = datetime('now') "
                        "WHERE answer_id = ?",
                        (int(is_right), awarded, _today(),
                         answer.answer_id))
                    conn.commit()
        result.marks_awarded = round(result.marks_awarded + awarded, 2)

    if store and questions:
        with _connect() as conn:
            conn.execute(
                "UPDATE coursework_submissions SET objective_marks = ?, "
                "objective_marked_on = ?, updated_at = datetime('now') "
                "WHERE submission_id = ?",
                (result.marks_awarded, _today(), submission_id))
            conn.commit()
    logger.info("Auto-marked submission #%d: %s",
                submission_id, result.message)
    return result


def auto_mark_assignment(assignment_id: int) -> dict[str, Any]:
    """Auto-mark every submission on an assignment."""
    init_db()
    _require_assignment(assignment_id)
    marked = 0
    total = 0.0
    for sub in assignments_store.list_submissions(assignment_id=assignment_id):
        result = auto_mark(sub.submission_id)
        if result.answered:
            marked += 1
            total += result.marks_awarded
    return {"submissions_marked": marked,
            "average_marks": (round(total / marked, 2)
                               if marked else None)}


def question_analysis(assignment_id: int) -> list[dict[str, Any]]:
    """Per-question facility: which questions the cohort got wrong.

    The reason to auto-mark at all — one glance shows the question
    everybody missed, which is a teaching problem, not a marking one.
    """
    init_db()
    out: list[dict[str, Any]] = []
    for question in list_questions(assignment_id):
        with _connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS answered, "
                "  SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) "
                "    AS correct "
                "FROM coursework_answers WHERE question_id = ?",
                (question.question_id,)).fetchone()
        answered = row["answered"] or 0
        correct = row["correct"] or 0
        out.append({
            "question_id": question.question_id,
            "position": question.position,
            "prompt": question.prompt,
            "answered": answered,
            "correct": correct,
            "facility": (round(100.0 * correct / answered, 1)
                          if answered else None),
        })
    return out


# ── Group assignments (item 26) ───────────────────────────────────

def create_group(assignment_id: int, name: str, *,
                  notes: str | None = None) -> Group:
    init_db()
    a = _require_assignment(assignment_id)
    if not a.is_group_assignment:
        logger.info(
            "Assignment #%d is not flagged as a group assignment — "
            "creating group %r anyway", assignment_id, name)
    group_name = assignments_store._require(name, "Group name").strip()
    with _connect() as conn:
        if conn.execute(
                "SELECT 1 FROM coursework_groups "
                "WHERE assignment_id = ? AND name = ?",
                (assignment_id, group_name)).fetchone():
            raise ValidationError(
                f"Assignment #{assignment_id} already has a group "
                f"named {group_name!r}")
        cur = conn.execute(
            """INSERT INTO coursework_groups
                   (assignment_id, name, notes, created_at, updated_at)
               VALUES (?, ?, ?, datetime('now'), datetime('now'))""",
            (assignment_id, group_name,
             (notes or "").strip() or None))
        conn.commit()
        new_id = int(cur.lastrowid or 0)
    out = get_group(new_id)
    assert out is not None
    return out


def get_group(group_id: int) -> Group | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM coursework_groups WHERE group_id = ?",
            (group_id,)).fetchone()
        return _row_group(r) if r else None


def list_groups(assignment_id: int) -> list[Group]:
    init_db()
    with _connect() as conn:
        return [_row_group(r) for r in conn.execute(
            "SELECT * FROM coursework_groups WHERE assignment_id = ? "
            "ORDER BY name ASC", (int(assignment_id),)).fetchall()]


def delete_group(group_id: int) -> bool:
    """Disband a group. Members keep their submissions and marks."""
    init_db()
    members = list_group_members(group_id)
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM coursework_groups WHERE group_id = ?",
            (group_id,))
        conn.executemany(
            "UPDATE coursework_submissions SET group_id = NULL, "
            "group_adjustment = NULL, updated_at = datetime('now') "
            "WHERE submission_id = ?",
            [(m.submission_id,) for m in members])
        conn.commit()
        return bool(cur.rowcount)


def add_group_member(group_id: int, submission_id: int, *,
                      role: str = DEFAULT_GROUP_ROLE,
                      adjustment: float = 0.0,
                      adjustment_reason: str | None = None
                      ) -> GroupMember:
    """Put a student's submission in a group. A student is in one group."""
    init_db()
    group = get_group(group_id)
    if group is None:
        raise ValidationError(f"No group #{group_id}")
    sub = _require_submission(submission_id)
    if sub.assignment_id != group.assignment_id:
        raise ValidationError(
            f"Submission #{submission_id} is on assignment "
            f"#{sub.assignment_id}, not #{group.assignment_id}")
    role_value = (role or DEFAULT_GROUP_ROLE).strip()
    if role_value not in GROUP_ROLES:
        raise ValidationError(
            f"Group role must be one of: {', '.join(GROUP_ROLES)}")
    delta = assignments_store._validate_number(adjustment, "Adjustment")
    if delta is None:
        delta = 0.0

    with _connect() as conn:
        conn.execute(
            """INSERT INTO coursework_group_members
                   (group_id, submission_id, role, adjustment,
                    adjustment_reason, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))
               ON CONFLICT (submission_id) DO UPDATE SET
                   group_id = excluded.group_id,
                   role = excluded.role,
                   adjustment = excluded.adjustment,
                   adjustment_reason = excluded.adjustment_reason,
                   updated_at = datetime('now')""",
            (group_id, submission_id, role_value, delta,
             (adjustment_reason or "").strip() or None))
        conn.execute(
            "UPDATE coursework_submissions SET group_id = ?, "
            "group_adjustment = ?, updated_at = datetime('now') "
            "WHERE submission_id = ?",
            (group_id, delta, submission_id))
        conn.commit()
    member = next((m for m in list_group_members(group_id)
                    if m.submission_id == submission_id), None)
    assert member is not None
    return member


def remove_group_member(submission_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM coursework_group_members "
            "WHERE submission_id = ?", (submission_id,))
        conn.execute(
            "UPDATE coursework_submissions SET group_id = NULL, "
            "group_adjustment = NULL, updated_at = datetime('now') "
            "WHERE submission_id = ?", (submission_id,))
        conn.commit()
        return bool(cur.rowcount)


def set_member_adjustment(submission_id: int, *,
                           adjustment: float,
                           reason: str | None = None) -> GroupMember:
    """Move one member off the group mark.

    The whole reason group work needs its own model: three students who
    did the work and one who didn't cannot all take the same mark.
    """
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT group_id FROM coursework_group_members "
            "WHERE submission_id = ?", (submission_id,)).fetchone()
    if row is None:
        raise ValidationError(
            f"Submission #{submission_id} is not in a group")
    delta = assignments_store._validate_number(adjustment, "Adjustment")
    if delta is None:
        delta = 0.0
    with _connect() as conn:
        conn.execute(
            "UPDATE coursework_group_members SET adjustment = ?, "
            "adjustment_reason = ?, updated_at = datetime('now') "
            "WHERE submission_id = ?",
            (delta, (reason or "").strip() or None, submission_id))
        conn.execute(
            "UPDATE coursework_submissions SET group_adjustment = ?, "
            "updated_at = datetime('now') WHERE submission_id = ?",
            (delta, submission_id))
        conn.commit()
    member = next((m for m in list_group_members(row["group_id"])
                    if m.submission_id == submission_id), None)
    assert member is not None
    return member


def list_group_members(group_id: int) -> list[GroupMember]:
    init_db()
    names = _student_names()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT m.*, s.student_id FROM coursework_group_members m "
            "JOIN coursework_submissions s "
            "  ON s.submission_id = m.submission_id "
            "WHERE m.group_id = ? ORDER BY s.student_id ASC",
            (int(group_id),)).fetchall()
    return [GroupMember(
        membership_id=r["membership_id"], group_id=r["group_id"],
        submission_id=r["submission_id"], student_id=r["student_id"],
        student_name=names.get(r["student_id"], r["student_id"]),
        role=r["role"], adjustment=r["adjustment"] or 0.0,
        adjustment_reason=r["adjustment_reason"]) for r in rows]


def get_group_detail(group_id: int) -> GroupDetail | None:
    group = get_group(group_id)
    if group is None:
        return None
    return GroupDetail(group=group,
                        members=list_group_members(group_id))


def set_group_marks(group_id: int, marks: float, *,
                     marked_by: str | None = None) -> Group:
    """Record the mark the group's work earned, before adjustments."""
    init_db()
    group = get_group(group_id)
    if group is None:
        raise ValidationError(f"No group #{group_id}")
    a = _require_assignment(group.assignment_id)
    value = assignments_store._validate_number(marks, "Group marks", min_val=0)
    if value is not None and a.max_marks is not None \
            and value > a.max_marks:
        raise ValidationError(
            f"Group marks ({value:g}) exceed max_marks "
            f"({a.max_marks:g})")
    with _connect() as conn:
        conn.execute(
            "UPDATE coursework_groups SET group_marks = ?, "
            "marked_by = ?, marked_on = ?, updated_at = datetime('now') "
            "WHERE group_id = ?",
            (value, (marked_by or "").strip() or None, _today(),
             group_id))
        conn.commit()
    out = get_group(group_id)
    assert out is not None
    return out


def apply_group_marks(group_id: int, *,
                       marked_by: str | None = None
                       ) -> list[assignments_models.Submission]:
    """Push the group mark plus each member's adjustment onto their row.

    Routes through the marking pipeline, so a group member who handed
    in late still takes the late penalty and everyone's change lands in
    the audit trail.
    """
    init_db()
    detail = get_group_detail(group_id)
    if detail is None:
        raise ValidationError(f"No group #{group_id}")
    if detail.group.group_marks is None:
        raise ValidationError(
            "Set the group's mark before applying it to members")
    a = _require_assignment(detail.group.assignment_id)

    out: list[assignments_models.Submission] = []
    for member in detail.members:
        value = member.effective_marks(detail.group.group_marks)
        if value is None:
            continue
        if a.max_marks is not None and value > a.max_marks:
            value = a.max_marks
        reason = f"Group {detail.group.name!r} mark"
        if member.adjustment:
            reason += (f" {detail.group.group_marks:g} "
                       f"{member.adjustment:+g}")
            if member.adjustment_reason:
                reason += f" ({member.adjustment_reason})"
        out.append(marking.apply_marks(
            member.submission_id, raw_marks=value,
            marked_by=marked_by or detail.group.marked_by,
            source="manual", reason=reason))
    logger.info("Applied group #%d marks to %d member(s)",
                group_id, len(out))
    return out


def ungrouped_submissions(assignment_id: int) -> list[assignments_models.Submission]:
    """Students on a group assignment who aren't in a group yet."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT s.* FROM coursework_submissions s "
            "LEFT JOIN coursework_group_members m "
            "  ON m.submission_id = s.submission_id "
            "WHERE s.assignment_id = ? AND m.membership_id IS NULL "
            "ORDER BY s.student_id ASC",
            (int(assignment_id),)).fetchall()
    return [assignments_store._row_submission(r) for r in rows]


# ── Peer assessment (item 27) ─────────────────────────────────────

def record_peer_review(submission_id: int, *,
                        reviewer_student: str,
                        marks: float | None = None,
                        criterion_id: int | None = None,
                        comment: str | None = None,
                        submitted_on: str | None = None) -> PeerReview:
    """One student's score for another's work.

    A criterion may be named to score against the rubric, or omitted
    for a single overall score.
    """
    init_db()
    sub = _require_submission(submission_id)
    reviewer = assignments_store._require(reviewer_student, "Reviewer").strip()
    if reviewer == sub.student_id:
        raise ValidationError(
            "A student cannot peer-review their own work — record that "
            "as a self-assessment instead")

    ceiling: float | None = None
    if criterion_id is not None:
        criterion = marking.get_criterion(criterion_id)
        if criterion is None:
            raise ValidationError(f"No criterion #{criterion_id}")
        if criterion.assignment_id != sub.assignment_id:
            raise ValidationError(
                f"Criterion #{criterion_id} belongs to a different "
                f"assignment")
        ceiling = criterion.max_marks
    else:
        a = assignments_store.get_assignment(sub.assignment_id)
        ceiling = a.max_marks if a else None

    value = assignments_store._validate_number(marks, "Peer marks", min_val=0,
                                   max_val=ceiling)
    when = assignments_store._validate_date(submitted_on, "Submitted on") or _today()

    # Upserted by hand rather than with ON CONFLICT: an overall review
    # has criterion_id NULL, and SQLite treats NULLs as distinct in a
    # UNIQUE constraint, so the conflict clause would never fire and a
    # reviewer could score the same work twice.
    with _connect() as conn:
        existing = conn.execute(
            "SELECT review_id FROM coursework_peer_reviews "
            "WHERE submission_id = ? AND reviewer_student = ? "
            "  AND criterion_id IS ?",
            (submission_id, reviewer, criterion_id)).fetchone()
        if existing is not None:
            conn.execute(
                "UPDATE coursework_peer_reviews SET marks = ?, "
                "comment = ?, submitted_on = ?, "
                "updated_at = datetime('now') WHERE review_id = ?",
                (value, (comment or "").strip() or None, when,
                 existing["review_id"]))
        else:
            conn.execute(
                """INSERT INTO coursework_peer_reviews
                       (submission_id, reviewer_student, criterion_id,
                        marks, comment, submitted_on,
                        created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?,
                           datetime('now'), datetime('now'))""",
                (submission_id, reviewer, criterion_id, value,
                 (comment or "").strip() or None, when))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM coursework_peer_reviews "
            "WHERE submission_id = ? AND reviewer_student = ? "
            "  AND criterion_id IS ?",
            (submission_id, reviewer, criterion_id)).fetchone()
    return _row_peer(r)


def list_peer_reviews(*, submission_id: int | None = None,
                       reviewer_student: str | None = None
                       ) -> list[PeerReview]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if submission_id is not None:
        clauses.append("submission_id = ?")
        args.append(int(submission_id))
    if reviewer_student:
        clauses.append("reviewer_student = ?")
        args.append(reviewer_student.strip())
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        return [_row_peer(r) for r in conn.execute(
            f"SELECT * FROM coursework_peer_reviews {where} "
            "ORDER BY review_id ASC", args).fetchall()]


def delete_peer_review(review_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM coursework_peer_reviews WHERE review_id = ?",
            (review_id,))
        conn.commit()
        return bool(cur.rowcount)


def peer_summary(submission_id: int, *,
                  mode: str = DEFAULT_PEER_SCORE_MODE,
                  store: bool = True) -> PeerSummary:
    """Combine a submission's peer scores into one number.

    'Trimmed mean' drops the highest and lowest reviewer, which is the
    usual answer to a friend marking generously and a rival marking
    harshly. It needs at least three reviewers to mean anything.
    """
    init_db()
    _require_submission(submission_id)
    if mode not in PEER_SCORE_MODES:
        raise ValidationError(
            f"Peer score mode must be one of: "
            f"{', '.join(PEER_SCORE_MODES)}")
    reviews = [r for r in list_peer_reviews(submission_id=submission_id)
               if r.marks is not None]
    summary = PeerSummary(submission_id=submission_id)
    if not reviews:
        return summary

    # One reviewer may score several criteria; their contribution is
    # the sum across the rubric, so one reviewer counts once.
    by_reviewer: dict[str, float] = {}
    for review in reviews:
        by_reviewer[review.reviewer_student] = round(
            by_reviewer.get(review.reviewer_student, 0.0)
            + (review.marks or 0.0), 2)
    scores = sorted(by_reviewer.values())
    summary.reviewer_count = len(scores)
    summary.spread = round(scores[-1] - scores[0], 2)

    if mode == "Median":
        mid = len(scores) // 2
        summary.score = (scores[mid] if len(scores) % 2
                          else round((scores[mid - 1]
                                       + scores[mid]) / 2, 2))
    elif mode == "Trimmed mean" and len(scores) >= 3:
        trimmed = scores[1:-1]
        summary.score = round(sum(trimmed) / len(trimmed), 2)
    else:
        summary.score = round(sum(scores) / len(scores), 2)

    per_criterion: dict[int, list[float]] = {}
    for review in reviews:
        if review.criterion_id is None or review.marks is None:
            continue
        per_criterion.setdefault(review.criterion_id,
                                  []).append(review.marks)
    summary.per_criterion = {cid: round(sum(v) / len(v), 2)
                             for cid, v in per_criterion.items()}

    if store:
        with _connect() as conn:
            conn.execute(
                "UPDATE coursework_submissions SET peer_score = ?, "
                "updated_at = datetime('now') WHERE submission_id = ?",
                (summary.score, submission_id))
            conn.commit()
    return summary


def blended_marks(submission_id: int, *,
                   teacher_marks: float,
                   mode: str = DEFAULT_PEER_SCORE_MODE) -> float | None:
    """Combine the teacher's mark with the peer score by the weighting.

    Returns ``None`` when the assignment sets no peer weight or nobody
    reviewed — the teacher's mark stands unchanged in both cases.
    """
    init_db()
    sub = _require_submission(submission_id)
    a = _require_assignment(sub.assignment_id)
    weight = a.peer_assessment_weight
    if not weight:
        return None
    summary = peer_summary(submission_id, mode=mode, store=False)
    if summary.score is None:
        return None
    return round(teacher_marks * (100.0 - weight) / 100.0
                  + summary.score * weight / 100.0, 2)


def apply_peer_blend(submission_id: int, *,
                      teacher_marks: float,
                      marked_by: str | None = None,
                      mode: str = DEFAULT_PEER_SCORE_MODE
                      ) -> assignments_models.Submission:
    """Write the blended teacher/peer mark through the pipeline."""
    blended = blended_marks(submission_id, teacher_marks=teacher_marks,
                             mode=mode)
    sub = _require_submission(submission_id)
    a = _require_assignment(sub.assignment_id)
    if blended is None:
        return marking.apply_marks(submission_id,
                                    raw_marks=teacher_marks,
                                    marked_by=marked_by,
                                    source="manual")
    summary = peer_summary(submission_id, mode=mode)
    return marking.apply_marks(
        submission_id, raw_marks=blended, marked_by=marked_by,
        source="manual",
        reason=(f"Teacher {teacher_marks:g} blended with peer "
                f"{summary.score:g} at {a.peer_assessment_weight:g}% "
                f"({summary.reviewer_count} reviewer(s), {mode})"))


def peer_review_coverage(assignment_id: int) -> dict[str, int]:
    """Who has reviewed and who still owes reviews."""
    init_db()
    subs = assignments_store.list_submissions(assignment_id=assignment_id)
    ids = {s.submission_id for s in subs}
    reviewed = set()
    reviewers = set()
    for review in list_peer_reviews():
        if review.submission_id in ids:
            reviewed.add(review.submission_id)
            reviewers.add(review.reviewer_student)
    return {"submissions": len(subs),
            "reviewed": len(reviewed),
            "awaiting_review": len(subs) - len(reviewed),
            "active_reviewers": len(reviewers)}


# ── Self-assessment (item 28) ─────────────────────────────────────

def record_self_assessment(submission_id: int, *,
                            predicted_marks: float,
                            note: str | None = None,
                            assessed_on: str | None = None
                            ) -> assignments_models.Submission:
    """Record the student's own prediction before it is marked.

    Refuses once the mark is visible: a prediction made after seeing
    the result measures nothing.
    """
    init_db()
    sub = _require_submission(submission_id)
    a = _require_assignment(sub.assignment_id)
    value = assignments_store._validate_number(predicted_marks, "Predicted marks",
                                   min_val=0, max_val=a.max_marks)
    if value is None:
        raise ValidationError("A predicted mark is required")

    try:
        from education_system.systems.sixth_form.domain.academics.assignments import (
            assignments_feedback as _feedback,
        )
        if _feedback.is_visible_to_student(sub, a):
            raise ValidationError(
                "The mark has already been released — a prediction "
                "made now measures nothing")
    except ValidationError:
        raise
    except Exception:
        logger.debug("Could not check release state for self-assessment",
                      exc_info=True)

    when = assignments_store._validate_date(assessed_on, "Assessed on") or _today()
    with _connect() as conn:
        conn.execute(
            "UPDATE coursework_submissions SET self_predicted_marks = ?, "
            "self_assessment_note = ?, self_assessed_on = ?, "
            "updated_at = datetime('now') WHERE submission_id = ?",
            (value, (note or "").strip() or None, when, submission_id))
        conn.commit()
    return _require_submission(submission_id)


def get_self_assessment(submission_id: int) -> SelfAssessment:
    sub = _require_submission(submission_id)
    return SelfAssessment(submission_id=submission_id,
                           predicted=sub.self_predicted_marks,
                           actual=sub.marks,
                           note=sub.self_assessment_note,
                           assessed_on=sub.self_assessed_on)


def self_assessment_report(assignment_id: int
                            ) -> list[SelfAssessment]:
    """Every student's prediction against their actual mark."""
    init_db()
    return [get_self_assessment(s.submission_id)
            for s in assignments_store.list_submissions(assignment_id=assignment_id)
            if s.self_predicted_marks is not None]


def calibration_summary(assignment_id: int) -> dict[str, Any]:
    """How well the cohort judges its own work.

    A class that consistently overestimates has not understood the mark
    scheme, which is a more useful finding than any individual gap.
    """
    rows = [r for r in self_assessment_report(assignment_id)
            if r.gap is not None]
    if not rows:
        return {"assessed": 0, "average_gap": None,
                "over": 0, "under": 0, "accurate": 0}
    gaps = [r.gap or 0.0 for r in rows]
    return {
        "assessed": len(rows),
        "average_gap": round(sum(gaps) / len(gaps), 2),
        "mean_absolute_gap": round(
            sum(abs(g) for g in gaps) / len(gaps), 2),
        "over": sum(1 for r in rows if r.accuracy == "Overestimated"),
        "under": sum(1 for r in rows if r.accuracy == "Underestimated"),
        "accurate": sum(1 for r in rows if r.accuracy == "Accurate"),
    }


def missing_self_assessments(assignment_id: int
                              ) -> list[assignments_models.Submission]:
    """Students who owe a self-assessment on an assignment requiring one."""
    init_db()
    a = _require_assignment(assignment_id)
    if not a.self_assessment_required:
        return []
    return [s for s in assignments_store.list_submissions(assignment_id=assignment_id)
            if s.self_predicted_marks is None]
