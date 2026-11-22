"""Attendance letters for the Sixth Form System.

Sibling to :mod:`attendance`. When a learner's attendance falls, a
college writes home. The letters are always the same three, they always
say roughly the same thing, and they are always written by hand at half
term by somebody working from a spreadsheet.

This module holds the templates, decides who has earned which letter,
and keeps the record of what was actually sent to whom.

**A letter is issued once per stage per year.** That rule does more work
than it looks. Without it, a learner sitting at 87% receives letter 2
every time anybody runs the report, which is how families learn that the
letters mean nothing. :func:`due` only returns learners who have crossed
a threshold they have not already been written to about — and a learner
whose attendance recovers and dips again does not get letter 2 twice,
they get letter 3, because the ladder only goes one way within a year.

Templates are plain text with ``{placeholders}``, editable per college.
The shipped set is deliberately plain: no threats, a specific figure, a
named person to reply to, and what happens next.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_thresholds as thresholds,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_DB

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

DRAFT: str = "Draft"
ISSUED: str = "Issued"
CANCELLED: str = "Cancelled"
STATES: tuple[str, ...] = (DRAFT, ISSUED, CANCELLED)

# Stage keys line up with the threshold keys, so a college that moves a
# threshold moves the letter with it and nothing has to agree twice.
STAGE_KEYS: tuple[str, ...] = (
    thresholds.LETTER_1, thresholds.LETTER_2, thresholds.LETTER_3,
)
_STAGE_RANK: dict[str, int] = {k: i for i, k in enumerate(STAGE_KEYS)}

# The window a learner's attendance is measured over for letters.
DEFAULT_WINDOW_DAYS: int = 42

# Shipped templates: (stage_key, name, subject, body).
SHIPPED_TEMPLATES: tuple[tuple[str, str, str, str], ...] = (
    (thresholds.LETTER_1, "First attendance letter",
     "Attendance for {student_name}",
     "Dear {guardian_name},\n\n"
     "I am writing about {student_name}'s attendance, which is currently "
     "{percentage}% over the last {window_days} days. The college asks "
     "learners to maintain {target}%.\n\n"
     "In that time {first_name} has missed {missed_sessions} lesson(s), "
     "of which {unauthorised} were unexplained.\n\n"
     "This is not a formal warning. It is a note so that you have the same "
     "information we do, early enough for it to be easy to put right. If "
     "there is something going on that we should know about, please tell "
     "us — it is much easier to help while the figure is still recoverable."
     "\n\n"
     "If you would like to talk it through, you can reach me at "
     "{sender_contact}.\n\n"
     "Yours sincerely,\n{sender_name}\n{sender_role}"),

    (thresholds.LETTER_2, "Second attendance letter",
     "Attendance for {student_name} — we would like to meet",
     "Dear {guardian_name},\n\n"
     "We wrote to you on {previous_letter_date} about {student_name}'s "
     "attendance. It is now {percentage}% over the last {window_days} days, "
     "against the {target}% we ask for.\n\n"
     "{first_name} has missed {missed_sessions} lesson(s) in that period, "
     "{unauthorised} of them unexplained.\n\n"
     "At this level attendance starts to affect grades — learners below "
     "{threshold}% typically finish a grade lower than their target. I would "
     "like to meet you and {first_name} to agree what would help.\n\n"
     "Please contact {sender_contact} to arrange a time in the next two "
     "weeks.\n\n"
     "Yours sincerely,\n{sender_name}\n{sender_role}"),

    (thresholds.LETTER_3, "Third attendance letter",
     "Attendance for {student_name} — formal review",
     "Dear {guardian_name},\n\n"
     "Despite our previous letters, {student_name}'s attendance is now "
     "{percentage}% over the last {window_days} days. {first_name} has "
     "missed {missed_sessions} lesson(s), {unauthorised} of them "
     "unexplained.\n\n"
     "We are required to review whether the college can continue to meet "
     "{first_name}'s needs on their current programme, and attendance at "
     "this level puts examination entries and any bursary payments at "
     "risk.\n\n"
     "I am asking you to attend a formal review meeting. Please contact "
     "{sender_contact} within five working days to arrange it. If there are "
     "circumstances we do not know about, this meeting is the place to tell "
     "us, and we would much rather hear them than act without them.\n\n"
     "Yours sincerely,\n{sender_name}\n{sender_role}"),
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_letter_templates (
    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stage_key   TEXT NOT NULL,
    name        TEXT NOT NULL,
    subject     TEXT NOT NULL,
    body        TEXT NOT NULL,
    active      INTEGER NOT NULL DEFAULT 1,
    updated_at  TEXT DEFAULT (datetime('now')),
    updated_by  TEXT,
    UNIQUE(stage_key)
);

CREATE TABLE IF NOT EXISTS attendance_letters (
    letter_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL,
    stage_key    TEXT NOT NULL,
    academic_year TEXT NOT NULL,
    percentage   REAL,
    window_from  TEXT,
    window_to    TEXT,
    subject      TEXT,
    body         TEXT NOT NULL,
    recipient    TEXT,
    recipient_name TEXT,
    state        TEXT NOT NULL DEFAULT 'Draft',
    created_at   TEXT DEFAULT (datetime('now')),
    issued_at    TEXT,
    issued_by    TEXT,
    note         TEXT,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_att_letters_student
    ON attendance_letters(student_id, academic_year);
CREATE INDEX IF NOT EXISTS idx_att_letters_state
    ON attendance_letters(state);
"""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Template:
    """One editable letter."""

    template_id: int
    stage_key: str
    name: str
    subject: str
    body: str
    active: bool
    updated_at: str | None
    updated_by: str | None

    @property
    def placeholders(self) -> set[str]:
        import re
        return set(re.findall(r"\{(\w+)\}", self.subject + self.body))


@dataclass
class Letter:
    """One letter, drafted or sent."""

    letter_id: int
    student_id: str
    stage_key: str
    academic_year: str
    percentage: float | None
    window_from: str | None
    window_to: str | None
    subject: str | None
    body: str
    recipient: str | None
    recipient_name: str | None
    state: str
    created_at: str | None
    issued_at: str | None
    issued_by: str | None
    note: str | None

    @property
    def stage_number(self) -> int:
        return _STAGE_RANK.get(self.stage_key, 0) + 1

    @property
    def label(self) -> str:
        return (f"Letter {self.stage_number} · {self.student_id} · "
                f"{self.percentage:.1f}%" if self.percentage is not None
                else f"Letter {self.stage_number} · {self.student_id}")


@dataclass
class Candidate:
    """A learner who has earned a letter they have not had."""

    student_id: str
    student_name: str | None
    stage_key: str
    percentage: float
    missed_sessions: int
    unauthorised: int
    highest_sent: str | None

    @property
    def stage_number(self) -> int:
        return _STAGE_RANK.get(self.stage_key, 0) + 1


@dataclass
class RunResult:
    """What a letter run produced."""

    drafted: int = 0
    skipped_already_sent: int = 0
    no_recipient: list[str] = field(default_factory=list)
    letters: list[Letter] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return (f"{self.drafted} letter(s) drafted, "
                f"{self.skipped_already_sent} already sent this year, "
                f"{len(self.no_recipient)} with nobody to write to")


# ── DB plumbing ─────────────────────────────────────────────────────

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
    thresholds.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    _DB_READY = True
    seed_templates()
    logger.debug("Letter schema ready at %s", DB_PATH)


def seed_templates() -> int:
    """Install the shipped templates, leaving edited ones alone."""
    with _connect() as conn:
        before = conn.execute(
            "SELECT COUNT(*) AS n FROM attendance_letter_templates"
        ).fetchone()["n"]
        conn.executemany(
            """INSERT OR IGNORE INTO attendance_letter_templates
                   (stage_key, name, subject, body) VALUES (?, ?, ?, ?)""",
            SHIPPED_TEMPLATES)
        conn.commit()
        after = conn.execute(
            "SELECT COUNT(*) AS n FROM attendance_letter_templates"
        ).fetchone()["n"]
    return after - before


def _template_row(r: sqlite3.Row) -> Template:
    return Template(template_id=r["template_id"], stage_key=r["stage_key"],
                    name=r["name"], subject=r["subject"], body=r["body"],
                    active=bool(r["active"]), updated_at=r["updated_at"],
                    updated_by=r["updated_by"])


def _letter_row(r: sqlite3.Row) -> Letter:
    return Letter(
        letter_id=r["letter_id"], student_id=r["student_id"],
        stage_key=r["stage_key"], academic_year=r["academic_year"],
        percentage=r["percentage"], window_from=r["window_from"],
        window_to=r["window_to"], subject=r["subject"], body=r["body"],
        recipient=r["recipient"], recipient_name=r["recipient_name"],
        state=r["state"], created_at=r["created_at"],
        issued_at=r["issued_at"], issued_by=r["issued_by"], note=r["note"])


def validate_stage(value: Any) -> str:
    s = (value or "").strip().lower() if isinstance(value, str) else ""
    if s in STAGE_KEYS:
        return s
    # Accept "1"/"letter 1" as a convenience for a CLI.
    for index, key in enumerate(STAGE_KEYS, 1):
        if s in (str(index), f"letter {index}", f"letter_{index}"):
            return key
    raise ValidationError(f"Stage must be one of: {', '.join(STAGE_KEYS)}")


# ── Templates ───────────────────────────────────────────────────────

def get_template(stage_key: str) -> Template | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_letter_templates WHERE stage_key = ?",
            (validate_stage(stage_key),)).fetchone()
    return _template_row(r) if r else None


def list_templates() -> list[Template]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM attendance_letter_templates ORDER BY stage_key"
        ).fetchall()
    return sorted([_template_row(r) for r in rows],
                  key=lambda t: _STAGE_RANK.get(t.stage_key, 99))


def set_template(stage_key: str, *, name: str | None = None,
                 subject: str | None = None, body: str | None = None,
                 actor: str | None = None) -> Template:
    """Edit a template. Unknown placeholders are rejected, not discovered
    at three hundred letters."""
    init_db()
    stage_key = validate_stage(stage_key)
    existing = get_template(stage_key)
    if existing is None:
        raise ValidationError(f"No template for {stage_key}")
    new_subject = subject if subject is not None else existing.subject
    new_body = body if body is not None else existing.body

    import re
    known = set(_sample_context())
    used = set(re.findall(r"\{(\w+)\}", new_subject + new_body))
    unknown = used - known
    if unknown:
        raise ValidationError(
            "Unknown placeholder(s): " + ", ".join(sorted(unknown))
            + ". Available: " + ", ".join(sorted(known)))

    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_letter_templates
                  SET name = ?, subject = ?, body = ?,
                      updated_at = datetime('now'), updated_by = ?
                WHERE stage_key = ?""",
            (name or existing.name, new_subject, new_body,
             (actor or "").strip() or None, stage_key))
        conn.commit()
    out = get_template(stage_key)
    assert out is not None
    return out


def _sample_context() -> dict[str, Any]:
    """Every placeholder a template may use."""
    return {
        "student_name": "", "first_name": "", "student_id": "",
        "guardian_name": "", "percentage": "", "target": "",
        "threshold": "", "window_days": "", "window_from": "",
        "window_to": "", "missed_sessions": "", "unauthorised": "",
        "authorised": "", "late": "", "total_sessions": "",
        "previous_letter_date": "", "date": "", "academic_year": "",
        "sender_name": "", "sender_role": "", "sender_contact": "",
        "college_name": "",
    }


# ── Deciding who gets one ───────────────────────────────────────────

def _academic_year(date: str) -> str:
    target = _dt.date.fromisoformat(core._validate_date(date))
    start = target.year if target.month >= 9 else target.year - 1
    return f"{start}/{str(start + 1)[-2:]}"


def highest_sent(student_id: str, *, academic_year: str | None = None
                 ) -> str | None:
    """The most serious letter this learner has had this year."""
    year = academic_year or _academic_year(_dt.date.today().isoformat())
    sent = [letter.stage_key
            for letter in list_letters(student_id=student_id,
                                       academic_year=year, state=ISSUED)]
    if not sent:
        return None
    return max(sent, key=lambda k: _STAGE_RANK.get(k, -1))


def due(
    *,
    date: str | None = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
    group_id: int | None = None,
    year_group: int | None = None,
) -> list[Candidate]:
    """Learners who have earned a letter they have not already had.

    The ladder only climbs. A learner who had letter 2 in October and is
    still at 87% in January does not get letter 2 again — they get
    nothing until they fall to letter 3, because repeating a stage is
    how a college teaches families that its letters are automatic and
    meaningless.
    """
    init_db()
    date = core._validate_date(date or _dt.date.today().isoformat())
    date_from = (_dt.date.fromisoformat(date)
                 - _dt.timedelta(days=max(1, window_days))).isoformat()
    year = _academic_year(date)

    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    wanted: set[str] | None = None
    if group_id is not None:
        from education_system.systems.sixth_form.domain.academics.class_groups import (  # noqa: E501
            class_groups as _cg,
        )
        wanted = set(_cg.list_members(group_id))

    out: list[Candidate] = []
    for student in _students.list_students():
        if wanted is not None and student.student_id not in wanted:
            continue
        if getattr(student, "status", "Active") not in ("Active", None):
            continue
        summary = core.summary_for_student(student.student_id,
                                           date_from=date_from, date_to=date)
        if summary.total == 0 or summary.percentage is None:
            continue
        earned = thresholds.worst_letter(summary.percentage,
                                         year_group=year_group)
        if earned is None:
            continue
        already = highest_sent(student.student_id, academic_year=year)
        if already is not None and \
                _STAGE_RANK.get(earned, 0) <= _STAGE_RANK.get(already, -1):
            continue
        out.append(Candidate(
            student_id=student.student_id, student_name=student.full_name,
            stage_key=earned, percentage=summary.percentage,
            missed_sessions=summary.absent + summary.authorised,
            unauthorised=summary.absent, highest_sent=already))
    out.sort(key=lambda c: (-_STAGE_RANK.get(c.stage_key, 0), c.percentage))
    return out


# ── Drafting ────────────────────────────────────────────────────────

def _context_for(student_id: str, *, stage_key: str, date: str,
                 window_days: int, sender_name: str | None,
                 sender_role: str | None, sender_contact: str | None,
                 guardian_name: str | None) -> dict[str, Any]:
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    student = _students.get_student(student_id)
    date_from = (_dt.date.fromisoformat(date)
                 - _dt.timedelta(days=window_days)).isoformat()
    summary = core.summary_for_student(student_id, date_from=date_from,
                                       date_to=date)
    previous = [letter for letter in list_letters(student_id=student_id,
                                                  state=ISSUED)]
    previous_date = (previous[-1].issued_at or "")[:10] if previous else ""

    return {
        "student_name": student.full_name if student else student_id,
        "first_name": (student.full_name.split(" ")[0]
                       if student else student_id),
        "student_id": student_id,
        "guardian_name": guardian_name or "Parent or carer",
        "percentage": (f"{summary.percentage:.1f}"
                       if summary.percentage is not None else "—"),
        "target": f"{thresholds.value_of(thresholds.TARGET_ATTENDANCE, default=95.0):g}",
        "threshold": f"{thresholds.value_of(stage_key, default=90.0):g}",
        "window_days": str(window_days),
        "window_from": date_from,
        "window_to": date,
        "missed_sessions": str(summary.absent + summary.authorised),
        "unauthorised": str(summary.absent),
        "authorised": str(summary.authorised),
        "late": str(summary.late),
        "total_sessions": str(summary.total),
        "previous_letter_date": previous_date or "an earlier date",
        "date": date,
        "academic_year": _academic_year(date),
        "sender_name": sender_name or "The Attendance Team",
        "sender_role": sender_role or "Attendance",
        "sender_contact": sender_contact or "the college office",
        "college_name": "the college",
    }


def draft(
    student_id: str,
    stage_key: str,
    *,
    date: str | None = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
    sender_name: str | None = None,
    sender_role: str | None = None,
    sender_contact: str | None = None,
) -> Letter:
    """Render one letter. Nothing is sent."""
    init_db()
    stage_key = validate_stage(stage_key)
    template = get_template(stage_key)
    if template is None:
        raise ValidationError(f"No template for {stage_key}")
    date = core._validate_date(date or _dt.date.today().isoformat())

    recipient_name = recipient_address = None
    try:
        from education_system.systems.sixth_form.domains.communications.domain.parent_contacts import (  # noqa: E501
            parent_contacts as _contacts,
        )
        contact = _contacts.primary_for_student(student_id)
        if contact is not None:
            recipient_name = contact.full_name
            recipient_address = contact.email
    except Exception:                       # pragma: no cover - optional dep
        logger.debug("Parent-contact lookup unavailable", exc_info=True)

    context = _context_for(student_id, stage_key=stage_key, date=date,
                           window_days=window_days, sender_name=sender_name,
                           sender_role=sender_role,
                           sender_contact=sender_contact,
                           guardian_name=recipient_name)
    try:
        subject = template.subject.format(**context)
        body = template.body.format(**context)
    except KeyError as e:
        raise ValidationError(
            f"Template for {stage_key} uses unknown placeholder {e}") from None

    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO attendance_letters
                   (student_id, stage_key, academic_year, percentage,
                    window_from, window_to, subject, body, recipient,
                    recipient_name, state)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (student_id.strip(), stage_key, _academic_year(date),
             float(context["percentage"])
             if context["percentage"] != "—" else None,
             context["window_from"], context["window_to"], subject, body,
             recipient_address, recipient_name, DRAFT))
        conn.commit()
        letter_id = int(cur.lastrowid or 0)
    out = get_letter(letter_id)
    assert out is not None
    return out


def run(
    *,
    date: str | None = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
    group_id: int | None = None,
    year_group: int | None = None,
    sender_name: str | None = None,
    sender_role: str | None = None,
    sender_contact: str | None = None,
) -> RunResult:
    """Draft every letter currently due. Issues nothing.

    Two steps on purpose: somebody should read a batch of letters about
    real families before they go out.
    """
    init_db()
    result = RunResult()
    for candidate in due(date=date, window_days=window_days,
                         group_id=group_id, year_group=year_group):
        letter = draft(candidate.student_id, candidate.stage_key, date=date,
                       window_days=window_days, sender_name=sender_name,
                       sender_role=sender_role,
                       sender_contact=sender_contact)
        result.drafted += 1
        result.letters.append(letter)
        if not letter.recipient:
            result.no_recipient.append(candidate.student_id)
    logger.info("Letter run: %s", result.summary)
    return result


# ── Issuing ─────────────────────────────────────────────────────────

def issue(letter_id: int, *, issued_by: str | None = None,
          send: bool = False, sender=None) -> Letter:
    """Mark a letter as sent, and optionally actually send it.

    Issuing is what stops the same stage being drafted again, so it is
    recorded even when the letter is printed and posted rather than
    emailed.
    """
    init_db()
    letter = get_letter(letter_id)
    if letter is None:
        raise ValidationError(f"No letter with id {letter_id}")
    if letter.state == ISSUED:
        raise ValidationError(f"Letter #{letter_id} has already been issued")

    if send:
        if not letter.recipient:
            raise ValidationError(
                "That letter has no email address — print it, then issue it")
        if sender is not None:
            sender(letter)
        else:
            from education_system.platform.integrations.email.email_service import (  # noqa: E501
                EmailService,
            )
            service = EmailService()
            if not service.is_configured():
                raise ValidationError("Email is not configured")
            service.send_email(to=letter.recipient,
                               subject=letter.subject or "Attendance",
                               body=letter.body)

    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_letters
                  SET state = ?, issued_at = datetime('now'), issued_by = ?
                WHERE letter_id = ?""",
            (ISSUED, (issued_by or "").strip() or None, letter_id))
        conn.commit()
    logger.info("Letter #%d issued (%s, %s)", letter_id, letter.student_id,
                letter.stage_key)
    out = get_letter(letter_id)
    assert out is not None
    return out


def issue_all(*, issued_by: str | None = None, send: bool = False) -> int:
    """Issue every draft. Used after somebody has read the batch."""
    issued = 0
    for letter in list_letters(state=DRAFT, limit=1000):
        try:
            issue(letter.letter_id, issued_by=issued_by, send=send)
            issued += 1
        except ValidationError as e:
            logger.warning("Could not issue letter #%d: %s",
                           letter.letter_id, e)
    return issued


def cancel(letter_id: int, *, reason: str) -> Letter:
    """Bin a draft — the figure was wrong, or circumstances are known."""
    init_db()
    letter = get_letter(letter_id)
    if letter is None:
        raise ValidationError(f"No letter with id {letter_id}")
    if letter.state == ISSUED:
        raise ValidationError("That letter has already gone")
    note = (reason or "").strip()
    if not note:
        raise ValidationError("A reason is required to cancel a letter")
    with _connect() as conn:
        conn.execute(
            "UPDATE attendance_letters SET state = ?, note = ? "
            "WHERE letter_id = ?", (CANCELLED, note, letter_id))
        conn.commit()
    out = get_letter(letter_id)
    assert out is not None
    return out


# ── Reads ───────────────────────────────────────────────────────────

def get_letter(letter_id: int) -> Letter | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_letters WHERE letter_id = ?",
            (letter_id,)).fetchone()
    return _letter_row(r) if r else None


def list_letters(*, student_id: str | None = None, state: str | None = None,
                 stage_key: str | None = None,
                 academic_year: str | None = None,
                 limit: int = 200) -> list[Letter]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if state:
        if state not in STATES:
            raise ValidationError(f"State must be one of: {', '.join(STATES)}")
        clauses.append("state = ?")
        args.append(state)
    if stage_key:
        clauses.append("stage_key = ?")
        args.append(validate_stage(stage_key))
    if academic_year:
        clauses.append("academic_year = ?")
        args.append(academic_year)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(max(1, int(limit)))
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_letters {where} "
            "ORDER BY letter_id LIMIT ?", args).fetchall()
    return [_letter_row(r) for r in rows]


def history_for(student_id: str) -> list[Letter]:
    """Every letter this family has had — read before writing another."""
    return list_letters(student_id=student_id, limit=100)


def stage_counts(*, academic_year: str | None = None) -> dict[str, int]:
    """How many letters of each stage have gone out this year."""
    year = academic_year or _academic_year(_dt.date.today().isoformat())
    out = {key: 0 for key in STAGE_KEYS}
    for letter in list_letters(state=ISSUED, academic_year=year, limit=5000):
        out[letter.stage_key] = out.get(letter.stage_key, 0) + 1
    return out


def preview(stage_key: str, student_id: str, *,
            window_days: int = DEFAULT_WINDOW_DAYS) -> str:
    """Render a letter without storing it — for a template editor."""
    init_db()
    stage_key = validate_stage(stage_key)
    template = get_template(stage_key)
    if template is None:
        raise ValidationError(f"No template for {stage_key}")
    context = _context_for(student_id, stage_key=stage_key,
                           date=_dt.date.today().isoformat(),
                           window_days=window_days, sender_name=None,
                           sender_role=None, sender_contact=None,
                           guardian_name=None)
    return template.body.format(**context)
