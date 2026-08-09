"""Running a coursework operation: clashes, digests, cover, paperwork.

Sibling to :mod:`assignments`. Everything here serves the staff who
have to keep coursework moving:

* **Clash detection** — deadlines stacking up on one class in one week,
  seen before the students feel it.
* **Teacher digest** — a daily or weekly summary of what is due, what
  is unmarked and who has not handed in.
* **Cover handover** — reassign marking when a teacher is out, without
  editing the ``teacher`` field and losing who actually owns the work.
* **CSV import and export** — bulk mark entry from a spreadsheet, and
  an export shaped for an awarding body.
* **Coversheets** — a printable sheet per submission carrying the
  rubric, marks and feedback, for physical folders and moderation.

Exports are written through :func:`export_marks` and always contain
the raw mark, the final mark and the penalty separately: a
spreadsheet showing only the final figure cannot be reconciled later.
"""

from __future__ import annotations

import csv
import datetime as _dt
import io
import logging
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from education_system.systems.sixth_form.domain.academics.assignments import (
    assignments as core,
    assignments_marking as marking,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ASSIGNMENTS_DB

ValidationError = core.ValidationError


# ── Vocabularies ──────────────────────────────────────────────────

DIGEST_PERIODS: tuple[str, ...] = ("Daily", "Weekly")
DEFAULT_DIGEST_PERIOD: str = "Weekly"

# How far ahead a digest looks for upcoming deadlines.
DIGEST_HORIZON_DAYS: dict[str, int] = {"Daily": 3, "Weekly": 10}

# A week carrying more than this many deadlines for one year group is
# flagged. Two is common and fine; three starts to bite.
CLASH_THRESHOLD: int = 3

# Columns an import will accept for each field, so a spreadsheet
# exported from anywhere stands a chance of loading.
_IMPORT_ALIASES: dict[str, tuple[str, ...]] = {
    "student_id": ("student_id", "student", "candidate", "id",
                    "candidate_number"),
    "submission_id": ("submission_id", "submission"),
    "marks": ("marks", "mark", "score", "raw_marks", "raw"),
    "grade": ("grade", "letter"),
    "feedback": ("feedback", "comment", "comments"),
}

# Header written by :func:`export_marks`.
EXPORT_COLUMNS: tuple[str, ...] = (
    "assignment_id", "assignment_title", "subject_name", "exam_board",
    "spec_code", "unit_code", "student_id", "student_name",
    "status", "submitted_on", "raw_marks", "penalty_percent",
    "marks", "max_marks", "percent", "grade", "marked_by",
    "marked_on", "released",
)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS coursework_digest_log (
    digest_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher           TEXT NOT NULL,
    period            TEXT NOT NULL,
    sent_on           TEXT NOT NULL,
    assignments       INTEGER NOT NULL DEFAULT 0,
    unmarked          INTEGER NOT NULL DEFAULT 0,
    missing           INTEGER NOT NULL DEFAULT 0,
    delivered         INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_cwdigest_teacher
    ON coursework_digest_log(teacher);
"""


# ── Dataclasses ───────────────────────────────────────────────────

@dataclass
class Clash:
    """A week where one year group faces several deadlines."""

    week_start: str
    year_group: str | None
    assignments: list[core.Assignment] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.assignments)

    @property
    def subjects(self) -> list[str]:
        return sorted({a.subject_name for a in self.assignments})

    @property
    def estimated_hours(self) -> float:
        return round(sum(a.estimated_hours or 0
                          for a in self.assignments), 2)

    @property
    def is_severe(self) -> bool:
        return self.count >= CLASH_THRESHOLD

    @property
    def message(self) -> str:
        head = (f"week of {self.week_start}: {self.count} deadline(s) "
                f"across {', '.join(self.subjects)}")
        if self.estimated_hours:
            head += f", ~{self.estimated_hours:g}h of work"
        return head + ("  ⚠" if self.is_severe else "")


@dataclass
class DigestLine:
    """One assignment's line in a teacher's digest."""

    assignment: core.Assignment
    due_date: str | None
    cohort: int = 0
    submitted: int = 0
    unmarked: int = 0
    missing: int = 0

    @property
    def needs_marking(self) -> bool:
        return self.unmarked > 0

    @property
    def message(self) -> str:
        bits = [f"{self.assignment.title} "
                f"({self.assignment.subject_name})"]
        if self.due_date:
            bits.append(f"due {self.due_date}")
        bits.append(f"{self.submitted}/{self.cohort} in")
        if self.unmarked:
            bits.append(f"{self.unmarked} to mark")
        if self.missing:
            bits.append(f"{self.missing} missing")
        return " · ".join(bits)


@dataclass
class Digest:
    """What one teacher needs to know this morning."""

    teacher: str
    period: str
    generated_on: str
    upcoming: list[DigestLine] = field(default_factory=list)
    to_mark: list[DigestLine] = field(default_factory=list)
    missing: list[DigestLine] = field(default_factory=list)
    covering_for: list[core.Assignment] = field(default_factory=list)

    @property
    def total_unmarked(self) -> int:
        return sum(line.unmarked for line in self.to_mark)

    @property
    def total_missing(self) -> int:
        return sum(line.missing for line in self.missing)

    @property
    def is_empty(self) -> bool:
        return not (self.upcoming or self.to_mark or self.missing)

    @property
    def message(self) -> str:
        if self.is_empty:
            return "Nothing outstanding"
        bits = []
        if self.upcoming:
            bits.append(f"{len(self.upcoming)} deadline(s) coming")
        if self.total_unmarked:
            bits.append(f"{self.total_unmarked} piece(s) to mark")
        if self.total_missing:
            bits.append(f"{self.total_missing} not handed in")
        return "; ".join(bits)

    def as_text(self) -> str:
        """The digest as a plain-text email body."""
        lines = [f"Coursework digest — {self.teacher}",
                 f"{self.period}, {self.generated_on}", ""]
        if self.is_empty:
            lines.append("Nothing outstanding. ")
            return "\n".join(lines)
        if self.to_mark:
            lines.append(f"To mark ({self.total_unmarked} piece(s))")
            lines.append("-" * 40)
            for line in self.to_mark:
                lines.append(f"  {line.message}")
            lines.append("")
        if self.upcoming:
            lines.append("Deadlines coming up")
            lines.append("-" * 40)
            for line in self.upcoming:
                lines.append(f"  {line.message}")
            lines.append("")
        if self.missing:
            lines.append(f"Not handed in ({self.total_missing})")
            lines.append("-" * 40)
            for line in self.missing:
                lines.append(f"  {line.message}")
            lines.append("")
        if self.covering_for:
            lines.append("You are covering marking for")
            lines.append("-" * 40)
            for a in self.covering_for:
                lines.append(f"  #{a.assignment_id} {a.title} "
                             f"(for {a.teacher or '—'})")
            lines.append("")
        return "\n".join(lines)


@dataclass
class ImportRow:
    """One line of a marks import, and what happened to it."""

    line: int
    student_id: str | None = None
    submission_id: int | None = None
    marks: float | None = None
    grade: str | None = None
    feedback: str | None = None
    ok: bool = True
    message: str = ""


@dataclass
class ImportResult:
    rows: list[ImportRow] = field(default_factory=list)
    applied: int = 0

    @property
    def errors(self) -> list[ImportRow]:
        return [r for r in self.rows if not r.ok]

    @property
    def is_valid(self) -> bool:
        return not self.errors

    @property
    def message(self) -> str:
        return (f"{len(self.rows)} row(s), {self.applied} applied, "
                f"{len(self.errors)} rejected")


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
    logger.debug("Admin schema ready at %s", DB_PATH)
    _DB_READY = True


def _today() -> str:
    return _dt.date.today().isoformat()


def _week_start(day: str) -> str:
    d = _dt.date.fromisoformat(day)
    return (d - _dt.timedelta(days=d.weekday())).isoformat()


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


# ── Deadline clashes (item 40) ────────────────────────────────────

def clashes(*, year_group: str | None = None,
             threshold: int = 2,
             date_from: str | None = None,
             date_to: str | None = None) -> list[Clash]:
    """Weeks carrying several deadlines for the same year group.

    Grouped by year group rather than the whole college, because a
    Year 12 clash is invisible in a college-wide count.
    """
    core.init_db()
    buckets: dict[tuple[str, str | None], Clash] = {}
    for a in core.list_assignments(year_group=year_group,
                                    open_only=True):
        if not a.due_date:
            continue
        if date_from and a.due_date < date_from:
            continue
        if date_to and a.due_date > date_to:
            continue
        try:
            week = _week_start(a.due_date)
        except ValueError:
            continue
        key = (week, a.year_group)
        clash = buckets.setdefault(key, Clash(week_start=week,
                                                year_group=a.year_group))
        clash.assignments.append(a)
    out = [c for c in buckets.values() if c.count >= threshold]
    return sorted(out, key=lambda c: (c.week_start, c.year_group or ""))


def student_clashes(student_id: str, *,
                     threshold: int = 2) -> list[Clash]:
    """Weeks where one student personally faces several deadlines.

    More useful than the year-group view for a tutor: a student taking
    an unusual combination can hit a clash their year group does not.
    """
    core.init_db()
    buckets: dict[str, Clash] = {}
    for sub in core.list_submissions(student_id=str(student_id).strip()):
        if sub.is_done or sub.status == "Excused":
            continue
        a = core.get_assignment(sub.assignment_id)
        if a is None:
            continue
        due = core.effective_due_date(sub, a)
        if not due:
            continue
        try:
            week = _week_start(due)
        except ValueError:
            continue
        clash = buckets.setdefault(week, Clash(week_start=week,
                                                year_group=a.year_group))
        clash.assignments.append(a)
    return sorted((c for c in buckets.values() if c.count >= threshold),
                   key=lambda c: c.week_start)


def suggest_reschedule(clash: Clash) -> list[tuple[int, str, str]]:
    """Which piece to move, and where to.

    Suggests moving the assignment with the fewest students affected —
    the least disruptive fix — one week later.
    """
    if clash.count < 2:
        return []
    scored = []
    for a in clash.assignments:
        cohort = len(core.list_submissions(
            assignment_id=a.assignment_id))
        scored.append((cohort, a))
    scored.sort(key=lambda pair: pair[0])
    out = []
    for _cohort, a in scored[:max(1, clash.count - 1)]:
        if not a.due_date:
            continue
        moved = (_dt.date.fromisoformat(a.due_date)
                 + _dt.timedelta(days=7)).isoformat()
        out.append((a.assignment_id, a.title, moved))
    return out


# ── Teacher digest (item 41) ──────────────────────────────────────

def build_digest(teacher: str, *,
                  period: str = DEFAULT_DIGEST_PERIOD,
                  today: str | None = None) -> Digest:
    """Assemble one teacher's digest.

    Reads assignments they own *and* any they are currently covering,
    so a colleague standing in for a fortnight sees the work.
    """
    init_db()
    if period not in DIGEST_PERIODS:
        raise ValidationError(
            f"Digest period must be one of: {', '.join(DIGEST_PERIODS)}")
    day = core._validate_date(today, "today") or _today()
    who = core._require(teacher, "Teacher").strip()
    horizon = (_dt.date.fromisoformat(day)
               + _dt.timedelta(
                   days=DIGEST_HORIZON_DAYS[period])).isoformat()

    digest = Digest(teacher=who, period=period, generated_on=day)
    for a in core.list_assignments():
        marker = a.marker_on(day)
        if marker != who:
            continue
        if a.teacher != who:
            digest.covering_for.append(a)
        subs = core.list_submissions(assignment_id=a.assignment_id)
        line = DigestLine(assignment=a, due_date=a.due_date,
                           cohort=len(subs))
        for sub in subs:
            if sub.is_done:
                line.submitted += 1
                if sub.marks is None:
                    line.unmarked += 1
            if sub.status == "Missing":
                line.missing += 1
        if line.unmarked:
            digest.to_mark.append(line)
        if line.missing:
            digest.missing.append(line)
        if (a.due_date and a.status in ("Draft", "Set")
                and day <= a.due_date <= horizon):
            digest.upcoming.append(line)

    digest.upcoming.sort(key=lambda x: x.due_date or "")
    digest.to_mark.sort(key=lambda x: -x.unmarked)
    digest.missing.sort(key=lambda x: -x.missing)
    return digest


def send_digest(teacher: str, *,
                 period: str = DEFAULT_DIGEST_PERIOD,
                 today: str | None = None,
                 notify: bool = True,
                 skip_if_empty: bool = True) -> Digest | None:
    """Build and email one digest.

    Returns ``None`` when there was nothing worth sending — an empty
    digest every morning trains people to ignore the useful ones.
    """
    digest = build_digest(teacher, period=period, today=today)
    if skip_if_empty and digest.is_empty:
        return None
    delivered = True
    if notify:
        delivered = _email_digest(digest)
    with _connect() as conn:
        conn.execute(
            """INSERT INTO coursework_digest_log
                   (teacher, period, sent_on, assignments, unmarked,
                    missing, delivered, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (digest.teacher, digest.period, digest.generated_on,
             len(digest.upcoming), digest.total_unmarked,
             digest.total_missing, 1 if delivered else 0))
        conn.commit()
    logger.info("Digest for %s (%s): %s",
                digest.teacher, digest.period, digest.message)
    return digest


def send_all_digests(*, period: str = DEFAULT_DIGEST_PERIOD,
                      today: str | None = None,
                      notify: bool = True) -> dict[str, Digest]:
    """One digest per teacher who has something outstanding."""
    init_db()
    day = core._validate_date(today, "today") or _today()
    teachers: set[str] = set()
    for a in core.list_assignments():
        marker = a.marker_on(day)
        if marker:
            teachers.add(marker)
    out: dict[str, Digest] = {}
    for who in sorted(teachers):
        digest = send_digest(who, period=period, today=day,
                              notify=notify)
        if digest is not None:
            out[who] = digest
    logger.info("Sent %d digest(s) for %s", len(out), day)
    return out


def digest_log(*, teacher: str | None = None,
                limit: int = 50) -> list[dict[str, Any]]:
    init_db()
    clauses, args = [], []
    if teacher:
        clauses.append("teacher = ?")
        args.append(teacher.strip())
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        return [dict(r) for r in conn.execute(
            f"SELECT * FROM coursework_digest_log {where} "
            f"ORDER BY digest_id DESC LIMIT {int(limit)}",
            args).fetchall()]


def _email_digest(digest: Digest) -> bool:
    """Best-effort digest email. A failure must not lose the log row."""
    try:
        from education_system.systems.sixth_form import SYSTEM_NAME
        from education_system.systems.sixth_form.domain.operations.communications.messages import (
            email_templates,
        )
        from education_system.systems.sixth_form.domain.staff import (
            staff as _staff,
        )
        address = None
        for member in _staff.list_staff():
            if member.full_name == digest.teacher and member.email:
                address = member.email
                break
        if not address:
            logger.info("No email address for %s — digest not sent",
                        digest.teacher)
            return False
        email_templates.send_from_template(
            "assignment_teacher_digest",
            {
                "system_name": SYSTEM_NAME,
                "teacher":     digest.teacher,
                "period":      digest.period,
                "date":        digest.generated_on,
                "summary":     digest.message,
                "to_mark":     str(digest.total_unmarked),
                "missing":     str(digest.total_missing),
                "upcoming":    str(len(digest.upcoming)),
                "body":        digest.as_text(),
            },
            to_name=digest.teacher,
            to_address=address,
        )
        return True
    except Exception:
        logger.exception("Digest email failed for %s", digest.teacher)
        return False


# ── Cover handover (item 42) ──────────────────────────────────────

def assign_cover(assignment_id: int, *,
                  cover_marker: str,
                  cover_from: str | None = None,
                  cover_until: str | None = None,
                  reason: str | None = None) -> core.Assignment:
    """Hand marking to a colleague for a period.

    The substantive teacher stays on the assignment. Editing
    ``teacher`` instead would lose who owns the work, and next term
    nobody would remember it was ever covered.
    """
    init_db()
    a = core.get_assignment(assignment_id)
    if a is None:
        raise ValidationError(f"No assignment #{assignment_id}")
    who = core._require(cover_marker, "Cover marker").strip()
    if a.teacher and who == a.teacher:
        raise ValidationError(
            f"{who} already owns this assignment — cover is for "
            f"somebody else standing in")
    out = core.update_assignment(assignment_id, {
        "cover_marker": who,
        "cover_from": cover_from or _today(),
        "cover_until": cover_until,
        "cover_reason": reason,
    })
    logger.info("Assignment #%d covered by %s from %s to %s (%s)",
                assignment_id, who, out.cover_from,
                out.cover_until or "further notice", reason or "—")
    return out


def end_cover(assignment_id: int) -> core.Assignment:
    """Return marking to the substantive teacher."""
    init_db()
    if core.get_assignment(assignment_id) is None:
        raise ValidationError(f"No assignment #{assignment_id}")
    return core.update_assignment(assignment_id, {
        "cover_marker": None, "cover_from": None,
        "cover_until": None, "cover_reason": None})


def cover_for_teacher(teacher: str, *,
                       today: str | None = None,
                       absent: bool = False,
                       cover_marker: str | None = None,
                       cover_until: str | None = None,
                       reason: str | None = None) -> list[core.Assignment]:
    """Cover every open assignment a teacher owns, in one action.

    What an office actually needs when somebody phones in sick: one
    instruction, not one per assignment.
    """
    init_db()
    day = core._validate_date(today, "today") or _today()
    out: list[core.Assignment] = []
    for a in core.list_assignments(teacher_like=teacher,
                                    open_only=True):
        if a.teacher != teacher:
            continue
        if absent:
            out.append(end_cover(a.assignment_id))
            continue
        if not cover_marker:
            raise ValidationError(
                "A cover marker is required unless ending cover")
        out.append(assign_cover(a.assignment_id,
                                 cover_marker=cover_marker,
                                 cover_from=day,
                                 cover_until=cover_until,
                                 reason=reason))
    return out


def list_covered(*, today: str | None = None) -> list[core.Assignment]:
    """Assignments currently being marked by somebody else."""
    init_db()
    day = core._validate_date(today, "today") or _today()
    return [a for a in core.list_assignments()
            if a.cover_marker and a.marker_on(day) == a.cover_marker]


def expired_cover(*, today: str | None = None
                   ) -> list[core.Assignment]:
    """Cover arrangements whose end date has passed but not been cleared.

    Harmless — :meth:`Assignment.marker_on` already ignores them — but
    worth tidying so the record reflects reality.
    """
    init_db()
    day = core._validate_date(today, "today") or _today()
    return [a for a in core.list_assignments()
            if a.cover_marker and a.cover_until
            and a.cover_until < day]


# ── CSV import and export (item 48) ───────────────────────────────

def export_marks(assignment_id: int | None = None, *,
                  subject_name: str | None = None,
                  path: str | Path | None = None,
                  released_only: bool = False) -> str:
    """Marks as CSV, for a spreadsheet or an awarding body.

    Always writes the raw mark, the penalty and the final mark in
    separate columns: an export showing only the final figure cannot be
    reconciled against the mark sheet later.
    """
    core.init_db()
    names = _student_names()
    assignments = ([core.get_assignment(assignment_id)]
                   if assignment_id is not None
                   else core.list_assignments(subject_name=subject_name))

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(EXPORT_COLUMNS)
    rows = 0
    for a in assignments:
        if a is None:
            continue
        for sub in core.list_submissions(assignment_id=a.assignment_id):
            if released_only and not sub.feedback_released:
                continue
            percent = (round(100.0 * sub.marks / a.max_marks, 1)
                       if sub.marks is not None and a.max_marks
                       else None)
            writer.writerow([
                a.assignment_id, a.title, a.subject_name,
                a.exam_board or "", a.spec_code or "",
                a.unit_code or "", sub.student_id,
                names.get(sub.student_id, ""), sub.status,
                sub.submitted_on or "",
                "" if sub.raw_marks is None else sub.raw_marks,
                "" if sub.penalty_percent is None
                else sub.penalty_percent,
                "" if sub.marks is None else sub.marks,
                "" if a.max_marks is None else a.max_marks,
                "" if percent is None else percent,
                sub.grade or "", sub.marked_by or "",
                sub.marked_on or "",
                "yes" if sub.feedback_released else "no",
            ])
            rows += 1
    text = buffer.getvalue()
    if path is not None:
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        logger.info("Exported %d mark row(s) to %s", rows, target)
    return text


def export_template(assignment_id: int, *,
                     path: str | Path | None = None) -> str:
    """A blank mark sheet for one assignment, ready to fill in.

    Pre-filled with the cohort so a teacher marking on paper can type
    marks in and import them back without matching names by hand.
    """
    core.init_db()
    a = core.get_assignment(assignment_id)
    if a is None:
        raise ValidationError(f"No assignment #{assignment_id}")
    names = _student_names()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["submission_id", "student_id", "student_name",
                      "marks", "grade", "feedback"])
    for sub in core.list_submissions(assignment_id=assignment_id):
        writer.writerow([sub.submission_id, sub.student_id,
                          names.get(sub.student_id, ""),
                          "" if sub.raw_marks is None else sub.raw_marks,
                          sub.grade or "", ""])
    text = buffer.getvalue()
    if path is not None:
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return text


def _map_headers(fieldnames: Sequence[str] | None) -> dict[str, str]:
    """Map a spreadsheet's headers onto the fields we understand."""
    out: dict[str, str] = {}
    for raw in (fieldnames or []):
        key = str(raw or "").strip().lower().replace(" ", "_")
        for field_name, aliases in _IMPORT_ALIASES.items():
            if key in aliases:
                out[field_name] = raw
                break
    return out


def parse_marks_csv(text: str, assignment_id: int) -> ImportResult:
    """Validate a marks CSV without writing anything.

    Always run before :func:`import_marks`: a spreadsheet with one bad
    row should be fixed and re-imported, not half-applied.
    """
    core.init_db()
    a = core.get_assignment(assignment_id)
    if a is None:
        raise ValidationError(f"No assignment #{assignment_id}")
    by_student = {s.student_id: s for s in
                  core.list_submissions(assignment_id=assignment_id)}
    by_id = {s.submission_id: s for s in by_student.values()}

    reader = csv.DictReader(io.StringIO(text))
    headers = _map_headers(reader.fieldnames)
    result = ImportResult()
    if "marks" not in headers:
        raise ValidationError(
            "The file needs a marks column (accepted names: "
            + ", ".join(_IMPORT_ALIASES["marks"]) + ")")
    if not ({"student_id", "submission_id"} & set(headers)):
        raise ValidationError(
            "The file needs a student_id or submission_id column")

    for number, raw in enumerate(reader, start=2):
        row = ImportRow(line=number)
        sub = None
        if "submission_id" in headers:
            value = (raw.get(headers["submission_id"]) or "").strip()
            if value:
                try:
                    row.submission_id = int(value)
                    sub = by_id.get(row.submission_id)
                except ValueError:
                    row.ok = False
                    row.message = f"{value!r} is not a submission id"
        if sub is None and "student_id" in headers:
            row.student_id = (raw.get(headers["student_id"])
                               or "").strip() or None
            if row.student_id:
                sub = by_student.get(row.student_id)
        if row.ok and sub is None:
            row.ok = False
            row.message = "No submission on this assignment"
        if sub is not None:
            row.submission_id = sub.submission_id
            row.student_id = sub.student_id

        marks_text = (raw.get(headers["marks"]) or "").strip()
        if row.ok and marks_text:
            try:
                row.marks = float(marks_text)
            except ValueError:
                row.ok = False
                row.message = f"{marks_text!r} is not a number"
            else:
                if row.marks < 0:
                    row.ok = False
                    row.message = "Marks cannot be negative"
                elif a.max_marks is not None and row.marks > a.max_marks:
                    row.ok = False
                    row.message = (f"{row.marks:g} exceeds max_marks "
                                   f"({a.max_marks:g})")
        elif row.ok:
            row.message = "No mark given — row skipped"

        if "grade" in headers:
            row.grade = (raw.get(headers["grade"]) or "").strip() or None
        if "feedback" in headers:
            row.feedback = ((raw.get(headers["feedback"]) or "").strip()
                             or None)
        result.rows.append(row)
    return result


def import_marks(text_or_path: str | Path, assignment_id: int, *,
                  marked_by: str | None = None,
                  dry_run: bool = False,
                  allow_partial: bool = False) -> ImportResult:
    """Load marks from a CSV through the marking pipeline.

    Refuses a file with any bad row unless ``allow_partial``: applying
    28 of 30 rows and reporting two errors leaves a spreadsheet nobody
    can safely re-import.
    """
    core.init_db()
    text = str(text_or_path)
    candidate = Path(text).expanduser() if len(text) < 4096 else None
    if candidate is not None and candidate.is_file():
        text = candidate.read_text(encoding="utf-8")

    result = parse_marks_csv(text, assignment_id)
    if result.errors and not allow_partial:
        logger.info("Marks import refused: %d bad row(s)",
                     len(result.errors))
        return result
    if dry_run:
        return result

    for row in result.rows:
        if not row.ok or row.marks is None or row.submission_id is None:
            continue
        try:
            marking.record_mark(row.submission_id, role="First",
                                 marks=row.marks, grade=row.grade,
                                 feedback=row.feedback,
                                 marked_by=marked_by)
            marking.apply_marks(row.submission_id, raw_marks=row.marks,
                                 grade=row.grade, feedback=row.feedback,
                                 marked_by=marked_by, source="import",
                                 reason="Imported from spreadsheet")
            result.applied += 1
            row.message = f"Marked {row.marks:g}"
        except Exception as e:                      # pragma: no cover
            logger.exception("Import failed on line %d", row.line)
            row.ok = False
            row.message = str(e)
    logger.info("Marks import on assignment #%d: %s",
                assignment_id, result.message)
    return result


def export_history(student_id: str, *,
                    path: str | Path | None = None) -> str:
    """One student's coursework record as CSV, for a reference or file."""
    from education_system.systems.sixth_form.domain.academics.assignments import (
        assignments_analytics as _analytics,
    )
    history = _analytics.student_history(str(student_id).strip())
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["due_date", "subject_name", "title",
                      "assignment_type", "status", "marks",
                      "max_marks", "percent", "grade"])
    for entry in history.entries:
        writer.writerow([
            entry.due_date or "", entry.assignment.subject_name,
            entry.assignment.title, entry.assignment.assignment_type,
            entry.state,
            "" if entry.submission.marks is None
            else entry.submission.marks,
            "" if entry.assignment.max_marks is None
            else entry.assignment.max_marks,
            "" if entry.percent is None else entry.percent,
            entry.submission.grade or "",
        ])
    text = buffer.getvalue()
    if path is not None:
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return text


# ── Coversheets (item 49) ─────────────────────────────────────────

def build_coversheet(submission_id: int, *,
                      include_feedback: bool = True) -> str:
    """A printable sheet for one submission.

    Plain text rather than PDF: it prints, it pastes into a document,
    and it does not need a rendering library on a school desktop. The
    rubric breakdown is the part a moderator actually reads.
    """
    core.init_db()
    sub = core.get_submission(submission_id)
    if sub is None:
        raise ValidationError(f"No submission #{submission_id}")
    a = core.get_assignment(sub.assignment_id)
    if a is None:
        raise ValidationError(f"No assignment #{sub.assignment_id}")
    names = _student_names()

    width = 66
    lines = ["=" * width, "COURSEWORK COVERSHEET".center(width),
             "=" * width, ""]
    lines.append(f"Student      : {names.get(sub.student_id, '')} "
                 f"({sub.student_id})")
    lines.append(f"Assignment   : {a.title}")
    lines.append(f"Subject      : {a.subject_name}  ·  "
                 f"{a.assignment_type}")
    if a.spec_reference:
        lines.append(f"Specification: {a.spec_reference}")
    if a.objective_list:
        lines.append(f"Objectives   : {', '.join(a.objective_list)}")
    lines.append(f"Teacher      : {a.teacher or '—'}")
    if a.is_covered:
        lines.append(f"Marked by    : {a.cover_marker} (cover)")
    lines.append(f"Due          : "
                 f"{core.effective_due_date(sub, a) or '—'}"
                 + ("  [extension]" if sub.extended_due_date else ""))
    lines.append(f"Submitted    : {sub.submitted_on or 'not submitted'}"
                 f"  ({sub.status})")
    if sub.word_count is not None:
        check = core.check_word_limit(a, sub.word_count)
        lines.append(f"Word count   : "
                     f"{check.message or sub.word_count}")
    lines.append("")

    criteria = marking.list_criteria(a.assignment_id)
    if criteria:
        lines.append("-" * width)
        lines.append(f"{'Criterion':<38}{'Mark':>10}{'Max':>8}")
        lines.append("-" * width)
        scores = {m.criterion_id: m for m in
                  marking.list_criterion_marks(submission_id)}
        for criterion in criteria:
            mark = scores.get(criterion.criterion_id)
            value = ("—" if mark is None or mark.marks is None
                     else f"{mark.marks:g}")
            lines.append(f"{criterion.label[:38]:<38}{value:>10}"
                         f"{criterion.max_marks:>8g}")
            if mark is not None and mark.comment:
                lines.append(f"    {mark.comment[:60]}")
        lines.append("-" * width)

    lines.append("")
    lines.append(f"{'Raw mark':<20}: "
                 f"{'—' if sub.raw_marks is None else f'{sub.raw_marks:g}'}")
    if sub.penalty_percent:
        lines.append(f"{'Late penalty':<20}: "
                     f"{sub.penalty_percent:g}% "
                     f"({sub.penalty_days} day(s) late)")
    lines.append(f"{'Final mark':<20}: "
                 f"{'—' if sub.marks is None else f'{sub.marks:g}'}"
                 f" / {a.max_marks or '?'}")
    lines.append(f"{'Grade':<20}: {sub.grade or '—'}")
    lines.append(f"{'Marked by':<20}: {sub.marked_by or '—'}"
                 f"  on {sub.marked_on or '—'}")

    moderation = marking.moderation_state(submission_id)
    if moderation.is_double_marked:
        lines.append(f"{'Moderation':<20}: {moderation.message}")
    if sub.sample_band:
        lines.append(f"{'Sample':<20}: {sub.sample_band}"
                     + (f" — {sub.sample_note}"
                         if sub.sample_note else ""))
    if sub.similarity_score is not None:
        lines.append(f"{'Similarity':<20}: "
                     f"{sub.similarity_score:g}%"
                     + (f" ({sub.similarity_provider})"
                         if sub.similarity_provider else ""))

    if include_feedback and sub.feedback:
        lines.append("")
        lines.append("-" * width)
        lines.append("Feedback")
        lines.append("-" * width)
        for line in sub.feedback.splitlines():
            lines.append(f"  {line}")

    lines.append("")
    lines.append("-" * width)
    lines.append("Student declaration: this is my own work.")
    lines.append("")
    lines.append("Signed: ______________________   "
                 "Date: ______________")
    lines.append("")
    return "\n".join(lines)


def write_coversheets(assignment_id: int, *,
                       directory: str | Path | None = None,
                       include_feedback: bool = True) -> list[Path]:
    """Write one coversheet per student to disk, ready to print."""
    core.init_db()
    a = core.get_assignment(assignment_id)
    if a is None:
        raise ValidationError(f"No assignment #{assignment_id}")
    target = (Path(directory).expanduser() if directory
              else paths.SIXTH_FORM_COURSEWORK_FILES_DIR
              / f"assignment_{assignment_id}" / "coversheets")
    target.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for sub in core.list_submissions(assignment_id=assignment_id):
        path = target / f"coversheet_{sub.student_id}.txt"
        path.write_text(
            build_coversheet(sub.submission_id,
                              include_feedback=include_feedback),
            encoding="utf-8")
        written.append(path)
    logger.info("Wrote %d coversheet(s) for assignment #%d to %s",
                len(written), assignment_id, target)
    return written


def build_sample_pack(assignment_id: int) -> str:
    """Every sampled script's coversheet in one document.

    What actually goes to a moderator: the standardisation sample with
    its marks and rubric breakdown, in one file rather than twelve.
    """
    core.init_db()
    a = core.get_assignment(assignment_id)
    if a is None:
        raise ValidationError(f"No assignment #{assignment_id}")
    samples = marking.list_samples(assignment_id=assignment_id)
    if not samples:
        raise ValidationError(
            "Nothing is flagged as a standardisation sample")
    header = [
        "=" * 66,
        f"STANDARDISATION SAMPLE — {a.title}".center(66),
        f"{a.subject_name} · {a.spec_reference or 'no spec recorded'}"
        .center(66),
        "=" * 66, "",
        f"{len(samples)} script(s), "
        f"{', '.join(sorted({s.sample_band or '?' for s in samples}))}",
        "",
    ]
    parts = ["\n".join(header)]
    for sub in samples:
        parts.append(build_coversheet(sub.submission_id))
        parts.append("\f")        # page break for printing
    return "\n".join(parts)
