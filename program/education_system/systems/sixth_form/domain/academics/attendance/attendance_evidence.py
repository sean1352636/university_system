"""Absence evidence for the Sixth Form System.

Sibling to :mod:`attendance`. An authorised absence is a claim somebody
accepted. Sometimes the college accepts it on trust; sometimes it asks
for a sick note, an appointment card, a letter. What it has never had is
anywhere to put the note when it arrives.

Two halves, and the second is the one that actually changes behaviour:

* **Evidence** — a document (or a description of one, for a card
  somebody looked at over the counter) attached to a mark, with what it
  is, who received it, and when it expires. Some evidence covers a span:
  a fit note for a fortnight should not need re-supplying daily.
* **Requirements** — the promise. When a mark is coded with a reason
  that :mod:`attendance_codes` flags ``requires_evidence``, a
  requirement is raised with a deadline. If the evidence never arrives,
  :func:`enforce_overdue` recodes the mark to unauthorised.

That last step is the point. A college that asks for evidence and never
checks has an authorisation policy in name only, and every learner
learns within a term that "I'll bring a note" is a complete sentence.
The reversion is not punitive — it is what the mark meant all along
once the evidence did not come.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_codes as codes,
    attendance_thresholds as thresholds,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_DB

# Where evidence documents are kept. Runtime learner data — never
# committed, and under the system's own data directory.
EVIDENCE_DIR: Path = paths.SIXTH_FORM_DATA_DIR / "attendance_evidence"

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

FIT_NOTE: str = "Fit note"
APPOINTMENT_CARD: str = "Appointment card"
HOSPITAL_LETTER: str = "Hospital letter"
PARENT_LETTER: str = "Letter from home"
EMAIL: str = "Email"
DEATH_CERTIFICATE: str = "Death certificate"
COURT_LETTER: str = "Court or official letter"
OTHER: str = "Other"
EVIDENCE_KINDS: tuple[str, ...] = (
    FIT_NOTE, APPOINTMENT_CARD, HOSPITAL_LETTER, PARENT_LETTER, EMAIL,
    DEATH_CERTIFICATE, COURT_LETTER, OTHER,
)

# Whether the college holds the document or merely saw it. "Sighted" is
# honest about the appointment card handed over the counter and given
# straight back, which is most of them.
HELD: str = "Held"
SIGHTED: str = "Sighted"
CUSTODY: tuple[str, ...] = (HELD, SIGHTED)

# Requirement lifecycle.
AWAITING: str = "Awaiting"
RECEIVED: str = "Received"
WAIVED: str = "Waived"
EXPIRED: str = "Expired"
REQUIREMENT_STATES: tuple[str, ...] = (AWAITING, RECEIVED, WAIVED, EXPIRED)

# What an unmet requirement recodes the mark to. `O` — the reason given
# was not substantiated, which is exactly what unauthorised means.
UNMET_CODE: str = "O"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_evidence (
    evidence_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL,
    record_id    INTEGER,
    kind         TEXT NOT NULL DEFAULT 'Other',
    custody      TEXT NOT NULL DEFAULT 'Sighted',
    covers_from  TEXT,
    covers_to    TEXT,
    description  TEXT,
    file_name    TEXT,
    file_path    TEXT,
    received_by  TEXT,
    received_at  TEXT DEFAULT (datetime('now')),
    expires_on   TEXT,
    withdrawn    INTEGER NOT NULL DEFAULT 0,
    withdrawn_at TEXT,
    notes        TEXT,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS attendance_evidence_requirements (
    requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id    INTEGER NOT NULL,
    student_id   TEXT NOT NULL,
    date         TEXT NOT NULL,
    original_code TEXT,
    reason_id    INTEGER,
    due_on       TEXT NOT NULL,
    state        TEXT NOT NULL DEFAULT 'Awaiting',
    evidence_id  INTEGER,
    raised_by    TEXT,
    raised_at    TEXT DEFAULT (datetime('now')),
    settled_at   TEXT,
    settled_by   TEXT,
    note         TEXT,
    UNIQUE(record_id)
);

CREATE INDEX IF NOT EXISTS idx_att_evid_student
    ON attendance_evidence(student_id);
CREATE INDEX IF NOT EXISTS idx_att_evid_record
    ON attendance_evidence(record_id);
CREATE INDEX IF NOT EXISTS idx_att_evreq_state
    ON attendance_evidence_requirements(state);
CREATE INDEX IF NOT EXISTS idx_att_evreq_due
    ON attendance_evidence_requirements(due_on);
"""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Evidence:
    """One piece of evidence."""

    evidence_id: int
    student_id: str
    record_id: int | None
    kind: str
    custody: str
    covers_from: str | None
    covers_to: str | None
    description: str | None
    file_name: str | None
    file_path: str | None
    received_by: str | None
    received_at: str | None
    expires_on: str | None
    withdrawn: bool
    withdrawn_at: str | None
    notes: str | None

    @property
    def has_file(self) -> bool:
        return bool(self.file_path)

    def covers(self, date: str) -> bool:
        """Whether this evidence speaks to a given date."""
        if self.withdrawn:
            return False
        if self.covers_from and date < self.covers_from:
            return False
        if self.covers_to and date > self.covers_to:
            return False
        return True

    @property
    def is_expired(self) -> bool:
        return bool(self.expires_on
                    and self.expires_on < _dt.date.today().isoformat())

    @property
    def label(self) -> str:
        span = ""
        if self.covers_from:
            span = (f" covering {self.covers_from}"
                    + (f" → {self.covers_to}"
                       if self.covers_to and self.covers_to != self.covers_from
                       else ""))
        return f"{self.kind} ({self.custody.lower()}){span}"


@dataclass
class Requirement:
    """A promise of evidence, with a deadline."""

    requirement_id: int
    record_id: int
    student_id: str
    date: str
    original_code: str | None
    reason_id: int | None
    due_on: str
    state: str
    evidence_id: int | None
    raised_by: str | None
    raised_at: str | None
    settled_at: str | None
    settled_by: str | None
    note: str | None
    student_name: str | None = None

    @property
    def is_open(self) -> bool:
        return self.state == AWAITING

    def is_overdue(self, *, on: str | None = None) -> bool:
        today = on or _dt.date.today().isoformat()
        return self.state == AWAITING and self.due_on < today

    def days_left(self, *, on: str | None = None) -> int:
        today = _dt.date.fromisoformat(on or _dt.date.today().isoformat())
        return (_dt.date.fromisoformat(self.due_on) - today).days

    @property
    def label(self) -> str:
        who = self.student_name or self.student_id
        return (f"{who} · absence {self.date} · evidence due {self.due_on} "
                f"({self.state})")


@dataclass
class EnforcementResult:
    """What an overdue sweep did."""

    checked: int = 0
    recoded: int = 0
    failed: list[str] = field(default_factory=list)
    requirements: list[Requirement] = field(default_factory=list)


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
    codes.init_db()
    thresholds.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    logger.debug("Evidence schema ready at %s", DB_PATH)
    _DB_READY = True


def _evidence_row(r: sqlite3.Row) -> Evidence:
    return Evidence(
        evidence_id=r["evidence_id"], student_id=r["student_id"],
        record_id=r["record_id"], kind=r["kind"], custody=r["custody"],
        covers_from=r["covers_from"], covers_to=r["covers_to"],
        description=r["description"], file_name=r["file_name"],
        file_path=r["file_path"], received_by=r["received_by"],
        received_at=r["received_at"], expires_on=r["expires_on"],
        withdrawn=bool(r["withdrawn"]), withdrawn_at=r["withdrawn_at"],
        notes=r["notes"])


def _requirement_row(r: sqlite3.Row) -> Requirement:
    return Requirement(
        requirement_id=r["requirement_id"], record_id=r["record_id"],
        student_id=r["student_id"], date=r["date"],
        original_code=r["original_code"], reason_id=r["reason_id"],
        due_on=r["due_on"], state=r["state"], evidence_id=r["evidence_id"],
        raised_by=r["raised_by"], raised_at=r["raised_at"],
        settled_at=r["settled_at"], settled_by=r["settled_by"],
        note=r["note"])


# ── Validation ──────────────────────────────────────────────────────

def validate_kind(value: Any) -> str:
    s = (value or "").strip() if isinstance(value, str) else ""
    if not s:
        return OTHER
    for kind in EVIDENCE_KINDS:
        if s.lower() == kind.lower():
            return kind
    raise ValidationError(f"Kind must be one of: {', '.join(EVIDENCE_KINDS)}")


def validate_custody(value: Any) -> str:
    s = (value or "").strip() if isinstance(value, str) else ""
    if not s:
        return SIGHTED
    for custody in CUSTODY:
        if s.lower() == custody.lower():
            return custody
    raise ValidationError(f"Custody must be one of: {', '.join(CUSTODY)}")


# ── Recording evidence ──────────────────────────────────────────────

def record_evidence(
    student_id: str,
    *,
    kind: str = OTHER,
    custody: str = SIGHTED,
    record_id: int | None = None,
    covers_from: str | None = None,
    covers_to: str | None = None,
    description: str | None = None,
    file_name: str | None = None,
    file_bytes: bytes | None = None,
    received_by: str | None = None,
    expires_on: str | None = None,
    notes: str | None = None,
) -> Evidence:
    """Log evidence, optionally storing the document itself.

    ``file_bytes`` writes the document under the system data directory
    and keeps only the path in the row — learner medical information
    does not belong in a database column that gets exported by accident.
    Pass no bytes and it is a record of having seen something, which is
    what happens at a counter.
    """
    init_db()
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    student = _students.get_student((student_id or "").strip())
    if student is None:
        raise ValidationError(f"No student with id {student_id}")
    kind = validate_kind(kind)
    custody = validate_custody(custody)
    covers_from = core._validate_date(covers_from) if covers_from else None
    covers_to = core._validate_date(covers_to) if covers_to else None
    if covers_from and covers_to and covers_to < covers_from:
        raise ValidationError("Evidence cannot stop covering before it starts")
    if expires_on:
        expires_on = core._validate_date(expires_on)

    if record_id is not None:
        record = core.get_record(record_id)
        if record is None:
            raise ValidationError(f"No attendance record with id {record_id}")
        covers_from = covers_from or record.date
        covers_to = covers_to or record.date

    stored_path: str | None = None
    if file_bytes is not None:
        if not file_name:
            raise ValidationError("A stored document needs a file name")
        if len(file_bytes) > 20 * 1024 * 1024:
            raise ValidationError("Evidence files are limited to 20 MB")
        target_dir = EVIDENCE_DIR / student.student_id
        target_dir.mkdir(parents=True, exist_ok=True)
        stamp = _dt.datetime.now().strftime("%Y%m%d%H%M%S")
        safe = Path(file_name).name.replace(" ", "_")
        target = target_dir / f"{stamp}_{safe}"
        target.write_bytes(file_bytes)
        stored_path = str(target)
        custody = HELD

    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO attendance_evidence
                   (student_id, record_id, kind, custody, covers_from,
                    covers_to, description, file_name, file_path,
                    received_by, expires_on, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (student.student_id, record_id, kind, custody, covers_from,
             covers_to, (description or "").strip() or None,
             (file_name or "").strip() or None, stored_path,
             (received_by or "").strip() or None, expires_on,
             (notes or "").strip() or None))
        conn.commit()
        evidence_id = int(cur.lastrowid or 0)
    logger.info("Evidence recorded for %s: %s", student.student_id, kind)
    out = get_evidence(evidence_id)
    assert out is not None
    return out


def get_evidence(evidence_id: int) -> Evidence | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_evidence WHERE evidence_id = ?",
            (evidence_id,)).fetchone()
    return _evidence_row(r) if r else None


def list_evidence(*, student_id: str | None = None,
                  record_id: int | None = None, kind: str | None = None,
                  include_withdrawn: bool = False) -> list[Evidence]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if not include_withdrawn:
        clauses.append("withdrawn = 0")
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if record_id is not None:
        clauses.append("record_id = ?")
        args.append(record_id)
    if kind:
        clauses.append("kind = ?")
        args.append(validate_kind(kind))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_evidence {where} "
            "ORDER BY received_at DESC", args).fetchall()
    return [_evidence_row(r) for r in rows]


def evidence_for_date(student_id: str, date: str) -> list[Evidence]:
    """Anything on file that speaks to one learner on one date."""
    date = core._validate_date(date)
    return [e for e in list_evidence(student_id=student_id)
            if e.covers(date)]


def withdraw_evidence(evidence_id: int, *, reason: str,
                      actor: str | None = None) -> Evidence:
    """Retract evidence — a note that turned out not to be genuine."""
    init_db()
    if get_evidence(evidence_id) is None:
        raise ValidationError(f"No evidence with id {evidence_id}")
    note = (reason or "").strip()
    if not note:
        raise ValidationError("A reason is required to withdraw evidence")
    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_evidence
                  SET withdrawn = 1, withdrawn_at = datetime('now'),
                      notes = COALESCE(notes || '; ', '') || ?
                WHERE evidence_id = ?""",
            (f"Withdrawn by {actor or '?'}: {note}", evidence_id))
        conn.commit()
    out = get_evidence(evidence_id)
    assert out is not None
    return out


def delete_evidence(evidence_id: int, *, remove_file: bool = True) -> bool:
    """Delete evidence outright, including the stored document.

    For a retention purge or a subject-access erasure — not for an
    ordinary correction, which is :func:`withdraw_evidence`.
    """
    init_db()
    existing = get_evidence(evidence_id)
    if existing is None:
        return False
    if remove_file and existing.file_path:
        try:
            Path(existing.file_path).unlink(missing_ok=True)
        except OSError:                     # pragma: no cover - defensive
            logger.warning("Could not delete evidence file %s",
                           existing.file_path)
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM attendance_evidence WHERE evidence_id = ?",
            (evidence_id,))
        conn.commit()
    return bool(cur.rowcount)


# ── Requirements ────────────────────────────────────────────────────

def _default_due(date: str) -> str:
    days = int(thresholds.value_of(thresholds.EVIDENCE_DAYS, default=5.0) or 5)
    return (_dt.date.fromisoformat(date)
            + _dt.timedelta(days=days)).isoformat()


def require_evidence(
    record_id: int,
    *,
    due_on: str | None = None,
    raised_by: str | None = None,
    note: str | None = None,
) -> Requirement:
    """Raise a requirement against a mark.

    Idempotent per record: asking twice does not create two deadlines.
    """
    init_db()
    record = core.get_record(record_id)
    if record is None:
        raise ValidationError(f"No attendance record with id {record_id}")
    due = core._validate_date(due_on) if due_on else _default_due(record.date)

    with _connect() as conn:
        conn.execute(
            """INSERT INTO attendance_evidence_requirements
                   (record_id, student_id, date, original_code, reason_id,
                    due_on, state, raised_by, note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(record_id) DO UPDATE SET
                   due_on = excluded.due_on,
                   note = COALESCE(excluded.note,
                                   attendance_evidence_requirements.note)""",
            (record_id, record.student_id, record.date, record.code,
             record.reason_id, due, AWAITING,
             (raised_by or "").strip() or None,
             (note or "").strip() or None))
        conn.commit()
    out = requirement_for(record_id)
    assert out is not None
    return out


def raise_for_reason(record_id: int, *,
                     raised_by: str | None = None) -> Requirement | None:
    """Raise a requirement only if the mark's reason asks for one.

    The hook a coding flow calls without having to know the policy: a
    reason flagged ``requires_evidence`` gets a deadline, everything
    else gets nothing.
    """
    init_db()
    record = core.get_record(record_id)
    if record is None or record.reason_id is None:
        return None
    reason = codes.get_reason(record.reason_id)
    if reason is None or not reason.requires_evidence:
        return None
    return require_evidence(record_id, raised_by=raised_by,
                            note=f"{reason.name} requires evidence")


def requirement_for(record_id: int) -> Requirement | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_evidence_requirements "
            "WHERE record_id = ?", (record_id,)).fetchone()
    return _requirement_row(r) if r else None


def get_requirement(requirement_id: int) -> Requirement | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_evidence_requirements "
            "WHERE requirement_id = ?", (requirement_id,)).fetchone()
    return _requirement_row(r) if r else None


def list_requirements(*, student_id: str | None = None,
                      state: str | None = None,
                      due_before: str | None = None,
                      limit: int = 500) -> list[Requirement]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if state:
        if state not in REQUIREMENT_STATES:
            raise ValidationError(
                f"State must be one of: {', '.join(REQUIREMENT_STATES)}")
        clauses.append("state = ?")
        args.append(state)
    if due_before:
        clauses.append("due_on < ?")
        args.append(core._validate_date(due_before))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(max(1, int(limit)))
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_evidence_requirements {where} "
            "ORDER BY due_on, requirement_id LIMIT ?", args).fetchall()
    return [_requirement_row(r) for r in rows]


def outstanding(*, with_names: bool = True) -> list[Requirement]:
    """Evidence the college is still waiting for, soonest deadline first."""
    out = list_requirements(state=AWAITING)
    if with_names and out:
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        index = {s.student_id: s.full_name for s in _students.list_students()}
        for requirement in out:
            requirement.student_name = index.get(requirement.student_id)
    return out


def overdue(*, on: str | None = None) -> list[Requirement]:
    """Requirements whose deadline has passed with nothing received."""
    today = core._validate_date(on or _dt.date.today().isoformat())
    return list_requirements(state=AWAITING, due_before=today)


def satisfy(requirement_id: int, *, evidence_id: int,
            settled_by: str | None = None) -> Requirement:
    """The evidence arrived. The mark stands as it is."""
    init_db()
    requirement = get_requirement(requirement_id)
    if requirement is None:
        raise ValidationError(f"No requirement with id {requirement_id}")
    if get_evidence(evidence_id) is None:
        raise ValidationError(f"No evidence with id {evidence_id}")
    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_evidence_requirements
                  SET state = ?, evidence_id = ?, settled_at = datetime('now'),
                      settled_by = ?
                WHERE requirement_id = ?""",
            (RECEIVED, evidence_id, (settled_by or "").strip() or None,
             requirement_id))
        conn.commit()
    logger.info("Evidence requirement #%d satisfied", requirement_id)
    out = get_requirement(requirement_id)
    assert out is not None
    return out


def waive(requirement_id: int, *, reason: str,
          settled_by: str | None = None) -> Requirement:
    """Decide the evidence is not needed after all.

    Used more than anyone expects, and worth recording: a learner whose
    circumstances are known does not need to produce a note every time.
    """
    init_db()
    if get_requirement(requirement_id) is None:
        raise ValidationError(f"No requirement with id {requirement_id}")
    note = (reason or "").strip()
    if not note:
        raise ValidationError("A reason is required to waive evidence")
    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_evidence_requirements
                  SET state = ?, settled_at = datetime('now'),
                      settled_by = ?, note = ?
                WHERE requirement_id = ?""",
            (WAIVED, (settled_by or "").strip() or None, note,
             requirement_id))
        conn.commit()
    out = get_requirement(requirement_id)
    assert out is not None
    return out


def enforce_overdue(
    *,
    on: str | None = None,
    dry_run: bool = False,
    actor: str | None = None,
) -> EnforcementResult:
    """Recode marks whose promised evidence never arrived.

    The step that makes the policy real. Run nightly, or from the CLI on
    a Friday. ``dry_run`` reports what would change without touching a
    mark — worth using the first time, because the list is usually
    longer than anyone expects.
    """
    init_db()
    result = EnforcementResult()
    for requirement in overdue(on=on):
        result.checked += 1
        result.requirements.append(requirement)

        # A late-but-arrived piece of evidence covering the date counts,
        # even if nobody linked it to the requirement.
        if evidence_for_date(requirement.student_id, requirement.date):
            if not dry_run:
                with _connect() as conn:
                    conn.execute(
                        "UPDATE attendance_evidence_requirements "
                        "SET state = ?, settled_at = datetime('now'), "
                        "note = COALESCE(note || '; ', '') || ? "
                        "WHERE requirement_id = ?",
                        (RECEIVED, "Matched to evidence on file",
                         requirement.requirement_id))
                    conn.commit()
            continue

        if dry_run:
            continue
        try:
            codes.set_code(
                requirement.record_id, UNMET_CODE, actor=actor,
                note=f"Evidence for {requirement.date} was due "
                     f"{requirement.due_on} and did not arrive")
            with _connect() as conn:
                conn.execute(
                    """UPDATE attendance_evidence_requirements
                          SET state = ?, settled_at = datetime('now'),
                              settled_by = ?
                        WHERE requirement_id = ?""",
                    (EXPIRED, (actor or "").strip() or None,
                     requirement.requirement_id))
                conn.commit()
            result.recoded += 1
        except ValidationError as e:
            # A submitted register or a deleted record: report it rather
            # than failing the whole sweep.
            result.failed.append(f"{requirement.label}: {e}")
    logger.info("Evidence sweep: %d checked, %d recoded, %d could not be",
                result.checked, result.recoded, len(result.failed))
    return result


def chase_list(*, days_ahead: int = 2) -> list[Requirement]:
    """Requirements about to fall due — worth a text before they do."""
    cutoff = (_dt.date.today()
              + _dt.timedelta(days=max(0, days_ahead))).isoformat()
    return [r for r in outstanding() if r.due_on <= cutoff]
