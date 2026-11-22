"""Exam access arrangements as the exams officer applies them.

The arrangements themselves are recorded by the SEN/pastoral team in
:mod:`accessibility` (category "Exam Access") and are only read here,
through its public functions. This module adds what the exams office
must keep for a JCQ inspection: the Form 8 evidence reference, the
approval date and the expiry (an approval lasts
:data:`APPROVAL_VALID_MONTHS` months), and turns the free-text
arrangement names into the flags a sitting needs (extra time %, reader,
scribe, word processor, separate room, rest breaks).

An expired arrangement is flagged and not applied to a sitting: JCQ
does not allow an arrangement to be used once its approval has lapsed.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.assessment.exams_office import store
from education_system.systems.sixth_form.domain.assessment.exams_office.store import (
    ValidationError,
)

logger = logging.getLogger(__name__)

# JCQ: an access arrangement approved through Access Arrangements
# Online (Form 8 evidence) is valid for 26 months from approval.
APPROVAL_VALID_MONTHS: int = 26

# Arrangements that need a Form 8 assessment before approval. Word
# processors, rest breaks and separate rooms are centre-delegated.
FORM8_REQUIRED: tuple[str, ...] = ("extra_time", "reader", "scribe")

# Days before expiry an arrangement is reported as "expiring soon".
EXPIRY_WARNING_DAYS: int = 60

_PCT_RE = re.compile(r"(\d{1,3})\s*%")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS exams_access_evidence (
    evidence_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    accommodation_id INTEGER NOT NULL UNIQUE,
    student_id       TEXT NOT NULL,
    form8_reference  TEXT,
    approval_date    TEXT,
    expiry_date      TEXT,
    approved_by      TEXT,
    notes            TEXT,
    updated_by       TEXT,
    updated_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_exams_access_ev_student
    ON exams_access_evidence(student_id);
"""


def init_db() -> None:
    store.ensure("access_evidence", _SCHEMA)


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Arrangement:
    """One "Exam Access" accommodation with its exams-office evidence."""
    accommodation_id: int
    student_id: str
    name: str
    description: str | None
    status: str
    kind: str                     # extra_time / reader / scribe / ...
    extra_time_pct: int
    form8_reference: str | None
    approval_date: str | None
    expiry_date: str | None
    approved_by: str | None
    evidence_notes: str | None

    @property
    def needs_form8(self) -> bool:
        return self.kind in FORM8_REQUIRED

    @property
    def expired(self) -> bool:
        return bool(self.expiry_date and self.expiry_date < store.today())

    @property
    def expiring_soon(self) -> bool:
        if not self.expiry_date or self.expired:
            return False
        import datetime as _dt
        left = (_dt.date.fromisoformat(self.expiry_date)
                - _dt.date.fromisoformat(store.today())).days
        return left <= EXPIRY_WARNING_DAYS

    @property
    def usable(self) -> bool:
        return self.status == "Active" and not self.expired

    @property
    def problem(self) -> str | None:
        if self.status != "Active":
            return f"Status {self.status}"
        if self.expired:
            return f"Expired {self.expiry_date}"
        if self.needs_form8 and not self.form8_reference:
            return "No Form 8 reference"
        if self.needs_form8 and not self.approval_date:
            return "No approval date"
        if self.expiring_soon:
            return f"Expires {self.expiry_date}"
        return None


@dataclass
class CandidateArrangements:
    """The flags a sitting needs for one candidate."""
    student_id: str
    extra_time_pct: int = 0
    reader: bool = False
    scribe: bool = False
    word_processor: bool = False
    separate_room: bool = False
    rest_breaks: bool = False
    other: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)   # problems found
    arrangements: list[Arrangement] = field(default_factory=list)

    @property
    def any(self) -> bool:
        return bool(self.extra_time_pct or self.reader or self.scribe
                    or self.word_processor or self.separate_room
                    or self.rest_breaks or self.other)

    def summary(self) -> str:
        parts: list[str] = []
        if self.extra_time_pct:
            parts.append(f"{self.extra_time_pct}% extra time")
        for on, label in ((self.reader, "Reader"), (self.scribe, "Scribe"),
                          (self.word_processor, "Word processor"),
                          (self.separate_room, "Separate room"),
                          (self.rest_breaks, "Rest breaks")):
            if on:
                parts.append(label)
        parts.extend(self.other)
        text = ", ".join(parts)
        if self.flags:
            text += (" | " if text else "") + "FLAGS: " + "; ".join(self.flags)
        return text


def classify(name: str, description: str | None = None) -> tuple[str, int]:
    """Work out what an arrangement is from its free-text name.

    Returns ``(kind, extra_time_pct)``.
    """
    text = f"{name or ''} {description or ''}".lower()
    if "extra time" in text or "additional time" in text:
        m = _PCT_RE.search(text)
        pct = int(m.group(1)) if m else 25
        return "extra_time", max(0, min(pct, 100))
    if "scribe" in text or "speech-to-text" in text or "speech to text" in text:
        return "scribe", 0
    if "reader" in text or "screen reader" in text or "computer reader" in text:
        return "reader", 0
    if "word processor" in text or "laptop" in text:
        return "word_processor", 0
    if "separate room" in text or "small group" in text or "separate invigilation" in text:
        return "separate_room", 0
    if "rest break" in text or "supervised rest" in text:
        return "rest_breaks", 0
    return "other", 0


# ── Evidence ────────────────────────────────────────────────────────

def _evidence_rows(student_id: str | None = None) -> dict[int, dict]:
    init_db()
    sql = "SELECT * FROM exams_access_evidence"
    args: list[Any] = []
    if student_id:
        sql += " WHERE student_id = ?"
        args.append(student_id)
    with store.connect() as conn:
        return {r["accommodation_id"]: dict(r) for r in conn.execute(sql, args)}


def record_evidence(accommodation_id: int, data: dict[str, Any]) -> Arrangement:
    """Record the Form 8 reference and approval for one arrangement.

    The expiry defaults to approval + :data:`APPROVAL_VALID_MONTHS`.
    """
    init_db()
    from education_system.systems.sixth_form.domain.pastoral.accessibility import (
        accessibility as _acc,
    )
    acc = _acc.get_accommodation(int(accommodation_id))
    if acc is None:
        raise ValidationError(f"No accommodation #{accommodation_id}")
    if acc.category != "Exam Access":
        raise ValidationError("Only 'Exam Access' arrangements carry Form 8 evidence")
    approval = store.date(data.get("approval_date"), "Approval date")
    expiry = store.date(data.get("expiry_date"), "Expiry date")
    if approval and not expiry:
        expiry = store.add_months(approval, APPROVAL_VALID_MONTHS)
    if approval and expiry and expiry < approval:
        raise ValidationError("Expiry cannot be before approval")
    vals = (int(accommodation_id), acc.student_id,
            store.text(data.get("form8_reference"), "Form 8 reference", limit=60),
            approval, expiry,
            store.text(data.get("approved_by"), "Approved by", limit=120),
            store.text(data.get("notes"), "Notes", limit=1000), store.actor())
    with store.connect() as conn:
        conn.execute(
            """INSERT INTO exams_access_evidence
                   (accommodation_id, student_id, form8_reference, approval_date,
                    expiry_date, approved_by, notes, updated_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(accommodation_id) DO UPDATE SET
                   form8_reference = excluded.form8_reference,
                   approval_date = excluded.approval_date,
                   expiry_date = excluded.expiry_date,
                   approved_by = excluded.approved_by,
                   notes = excluded.notes,
                   updated_by = excluded.updated_by,
                   updated_at = datetime('now')""", vals)
        conn.commit()
    logger.info("Recorded Form 8 evidence for accommodation #%s", accommodation_id)
    return next(a for a in list_arrangements(student_id=acc.student_id, active_only=False)
                if a.accommodation_id == int(accommodation_id))


def list_arrangements(*, student_id: str | None = None,
                      active_only: bool = True) -> list[Arrangement]:
    """Every "Exam Access" arrangement joined to its evidence."""
    from education_system.systems.sixth_form.domain.pastoral.accessibility import (
        accessibility as _acc,
    )
    accs = _acc.list_accommodations(student_id=student_id, category="Exam Access",
                                    active_only=active_only)
    ev = _evidence_rows(student_id)
    out: list[Arrangement] = []
    for a in accs:
        kind, pct = classify(a.name, a.description)
        e = ev.get(a.accommodation_id, {})
        # Fall back to what the SEN record holds when no evidence row yet.
        approval = e.get("approval_date") or a.approved_date
        expiry = e.get("expiry_date") or (
            store.add_months(approval, APPROVAL_VALID_MONTHS) if approval else None)
        if not e and a.end_date and (expiry is None or a.end_date < expiry):
            expiry = a.end_date
        out.append(Arrangement(
            accommodation_id=a.accommodation_id, student_id=a.student_id,
            name=a.name, description=a.description, status=a.status,
            kind=kind, extra_time_pct=pct,
            form8_reference=e.get("form8_reference") or (a.evidence if kind in FORM8_REQUIRED else None),
            approval_date=approval, expiry_date=expiry,
            approved_by=e.get("approved_by") or a.approved_by,
            evidence_notes=e.get("notes")))
    return out


def for_student(student_id: str) -> CandidateArrangements:
    """The flags to copy onto a sitting for one candidate."""
    out = CandidateArrangements(student_id=student_id)
    for a in list_arrangements(student_id=student_id, active_only=True):
        out.arrangements.append(a)
        if a.problem:
            out.flags.append(f"{a.name}: {a.problem}")
        if not a.usable:
            continue          # expired arrangements are never applied
        if a.kind == "extra_time":
            out.extra_time_pct = max(out.extra_time_pct, a.extra_time_pct)
        elif a.kind == "other":
            out.other.append(a.name)
        else:
            setattr(out, a.kind, True)
    return out


def expired_or_flagged(*, include_expiring: bool = True) -> list[Arrangement]:
    """Arrangements an exams officer has to act on before the next series."""
    out = []
    for a in list_arrangements(active_only=True):
        p = a.problem
        if p and (include_expiring or not a.expiring_soon):
            out.append(a)
    return out
