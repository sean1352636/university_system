"""Learner agreements and parent/guardian acknowledgements.

Each enrolment year a learner signs the learner agreement and — while
they are under 18 on the enrolment's start date — a parent or guardian
acknowledges it. One row per signature in ``enrolment_agreements``:

* **kind** — :data:`LEARNER` or :data:`PARENT`;
* who signed (name as signed), and for a parent their relationship and,
  when they are on file, the parent-contacts record they came from;
* the date signed, the method (:data:`METHODS`) and who recorded it.

A signature is never edited or deleted. :func:`withdraw` marks it
Withdrawn with a reason; :func:`correct` marks it Corrected and records
the replacement, linked through ``replaces_id``. Every action is in
``enrolment_agreement_history``.

Recording needs ``admissions`` or ``students.manage``; reads are open.
"""

from __future__ import annotations

import contextlib
import datetime as _dt
import logging
from dataclasses import dataclass
from typing import Any, Iterator

from education_system.systems.sixth_form.domain.admissions.enrolments import (
    enrolments as _enrolments,
)

logger = logging.getLogger(__name__)

ValidationError = _enrolments.ValidationError

LEARNER = "Learner"
PARENT = "Parent/guardian"
KINDS: tuple[str, ...] = (LEARNER, PARENT)
METHODS: tuple[str, ...] = ("Paper", "Online")
CURRENT, WITHDRAWN, CORRECTED = "Current", "Withdrawn", "Corrected"
STATUSES: tuple[str, ...] = (CURRENT, WITHDRAWN, CORRECTED)
#: A parent acknowledgement is needed while the learner is under this age
#: on the enrolment start date.
ADULT_AGE = 18

_SCHEMA = """
CREATE TABLE IF NOT EXISTS enrolment_agreements (
    agreement_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    enrolment_id   INTEGER NOT NULL,
    student_id     TEXT NOT NULL,
    kind           TEXT NOT NULL,
    signed_name    TEXT NOT NULL,
    relationship   TEXT,
    contact_id     INTEGER,
    signed_on      TEXT NOT NULL,
    method         TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'Current',
    replaces_id    INTEGER,
    notes          TEXT,
    recorded_by    TEXT,
    recorded_at    TEXT NOT NULL DEFAULT (datetime('now')),
    ended_by       TEXT,
    ended_at       TEXT,
    ended_reason   TEXT,
    FOREIGN KEY (enrolment_id) REFERENCES enrolments(enrolment_id)
        ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_enrol_agree_enrolment
    ON enrolment_agreements(enrolment_id);

CREATE TABLE IF NOT EXISTS enrolment_agreement_history (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    agreement_id   INTEGER NOT NULL,
    enrolment_id   INTEGER NOT NULL,
    action         TEXT NOT NULL,
    detail         TEXT,
    changed_by     TEXT,
    changed_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_enrol_agree_hist
    ON enrolment_agreement_history(enrolment_id);
"""

_READY_PATHS: set[str] = set()


def _init() -> None:
    key = str(_enrolments.DB_PATH)
    if key in _READY_PATHS:
        return
    _enrolments.init_db()
    conn = _enrolments._connect()
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()
    _READY_PATHS.add(key)


@contextlib.contextmanager
def _db() -> Iterator[Any]:
    _init()
    conn = _enrolments._connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


@dataclass
class Agreement:
    agreement_id: int
    enrolment_id: int
    student_id: str
    kind: str
    signed_name: str
    relationship: str | None
    contact_id: int | None
    signed_on: str
    method: str
    status: str
    replaces_id: int | None
    notes: str | None
    recorded_by: str | None
    recorded_at: str
    ended_by: str | None
    ended_at: str | None
    ended_reason: str | None

    @property
    def is_current(self) -> bool:
        return self.status == CURRENT


def _row(r: Any) -> Agreement:
    return Agreement(**{k: r[k] for k in r.keys()})


def _history(conn: Any, a: Agreement | dict, action: str,
             detail: str | None = None) -> None:
    aid = a["agreement_id"] if isinstance(a, dict) else a.agreement_id
    eid = a["enrolment_id"] if isinstance(a, dict) else a.enrolment_id
    conn.execute(
        "INSERT INTO enrolment_agreement_history (agreement_id, "
        "enrolment_id, action, detail, changed_by) VALUES (?, ?, ?, ?, ?)",
        (aid, eid, action, detail, _enrolments._actor()))


# ── Reads ───────────────────────────────────────────────────────────

def get(agreement_id: int) -> Agreement | None:
    with _db() as conn:
        r = conn.execute("SELECT * FROM enrolment_agreements WHERE "
                         "agreement_id = ?", (int(agreement_id),)).fetchone()
    return _row(r) if r else None


def for_enrolment(enrolment_id: int, *, current_only: bool = False
                  ) -> list[Agreement]:
    sql = "SELECT * FROM enrolment_agreements WHERE enrolment_id = ?"
    if current_only:
        sql += " AND status = 'Current'"
    with _db() as conn:
        return [_row(r) for r in conn.execute(
            sql + " ORDER BY agreement_id", (int(enrolment_id),)).fetchall()]


def current(enrolment_id: int, kind: str) -> Agreement | None:
    rows = [a for a in for_enrolment(enrolment_id, current_only=True)
            if a.kind == kind]
    return rows[-1] if rows else None


def history(enrolment_id: int) -> list[dict[str, Any]]:
    with _db() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM enrolment_agreement_history WHERE enrolment_id = ? "
            "ORDER BY id DESC", (int(enrolment_id),)).fetchall()]


def _age_on(dob: str | None, day: str) -> int | None:
    if not dob:
        return None
    try:
        b = _dt.date.fromisoformat(dob)
        d = _dt.date.fromisoformat(day)
    except ValueError:
        return None
    return d.year - b.year - ((d.month, d.day) < (b.month, b.day))


def parent_needed(e: _enrolments.Enrolment) -> bool:
    """A parent/guardian acknowledgement is needed when the learner is
    under 18 on the enrolment start date (or their age is unknown)."""
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    s = _students.get_student(e.student_id)
    day = e.start_date or _enrolments.academic_year_dates(e.academic_year)[0]
    age = _age_on(getattr(s, "date_of_birth", None), day)
    return age is None or age < ADULT_AGE


@dataclass
class AgreementState:
    enrolment_id: int
    learner: Agreement | None
    parent: Agreement | None
    parent_needed: bool

    @property
    def complete(self) -> bool:
        return self.learner is not None and (
            self.parent is not None or not self.parent_needed)

    @property
    def missing(self) -> list[str]:
        out = []
        if self.learner is None:
            out.append("learner agreement not signed")
        if self.parent_needed and self.parent is None:
            out.append("parent/guardian acknowledgement missing")
        return out


def state(enrolment_id: int) -> AgreementState:
    e = _enrolments.get_enrolment(int(enrolment_id))
    if e is None:
        raise ValidationError(f"No enrolment #{enrolment_id}")
    return AgreementState(e.enrolment_id, current(e.enrolment_id, LEARNER),
                          current(e.enrolment_id, PARENT), parent_needed(e))


@dataclass
class OutstandingRow:
    enrolment_id: int
    student_id: str
    year_group: int
    missing: list[str]


def outstanding(academic_year: str | None = None) -> list[OutstandingRow]:
    """Live enrolments in the year (default: the current one) still
    missing a learner agreement or a needed parent acknowledgement."""
    year = academic_year or _enrolments.current_academic_year()
    out = []
    for e in _enrolments.list_enrolments(academic_year=year):
        if not e.is_live:
            continue
        st = state(e.enrolment_id)
        if not st.complete:
            out.append(OutstandingRow(e.enrolment_id, e.student_id,
                                      e.year_group, st.missing))
    return out


# ── Parent contacts ─────────────────────────────────────────────────

def parent_contacts(student_id: str) -> list[Any]:
    """The learner's parent/carer contacts, those with parental
    responsibility first (for the "who acknowledged" picker)."""
    from education_system.systems.sixth_form.domains.communications.domain.parent_contacts import (
        parent_contacts as _pc,
    )
    return sorted(_pc.contacts_for_student(student_id),
                  key=lambda c: (not c.has_parental_responsibility,
                                 not c.is_primary, c.last_name))


# ── Writes ──────────────────────────────────────────────────────────

def _validate(e: _enrolments.Enrolment, kind: str, signed_name: str | None,
              signed_on: str | None, method: str,
              relationship: str | None, contact_id: int | None
              ) -> dict[str, Any]:
    if kind not in KINDS:
        raise ValidationError("Kind must be one of: " + ", ".join(KINDS))
    if method not in METHODS:
        raise ValidationError("Method must be one of: " + ", ".join(METHODS))
    day = (signed_on or "").strip() or _dt.date.today().isoformat()
    try:
        d = _dt.date.fromisoformat(day)
    except ValueError:
        raise ValidationError("Signed date must be YYYY-MM-DD") from None
    if d > _dt.date.today():
        raise ValidationError("Signed date cannot be in the future")
    name = (signed_name or "").strip()
    rel = (relationship or "").strip() or None
    contact = None
    if kind == PARENT:
        if contact_id is not None:
            contact = next((c for c in parent_contacts(e.student_id)
                            if c.contact_id == int(contact_id)), None)
            if contact is None:
                raise ValidationError(
                    f"Contact #{contact_id} is not one of {e.student_id}'s "
                    "parent contacts")
            name = name or contact.full_name
            rel = rel or contact.relationship
        if not rel:
            raise ValidationError("Give the parent/guardian's relationship "
                                  "to the learner")
    else:
        if contact_id is not None:
            raise ValidationError("A learner agreement has no parent contact")
        if not name:
            from education_system.systems.sixth_form.domain.learners.students import (
                students as _students,
            )
            s = _students.get_student(e.student_id)
            name = s.full_name if s else ""
        rel = None
    if not name:
        raise ValidationError("Give the name as signed")
    return {"signed_name": name, "relationship": rel,
            "contact_id": int(contact_id) if contact else None,
            "signed_on": day}


def record(enrolment_id: int, kind: str, *, method: str,
           signed_name: str | None = None, signed_on: str | None = None,
           relationship: str | None = None, contact_id: int | None = None,
           notes: str | None = None) -> Agreement:
    """Record a signature. Refused when a current one of that kind is
    already on file — :func:`correct` it instead."""
    _enrolments._require_writer("recording learner agreements")
    e = _enrolments.get_enrolment(int(enrolment_id))
    if e is None:
        raise ValidationError(f"No enrolment #{enrolment_id}")
    if e.is_archived:
        raise ValidationError(f"Enrolment #{enrolment_id} is archived")
    if current(e.enrolment_id, kind) is not None:
        raise ValidationError(
            f"A {kind.lower()} signature is already on file for this "
            "enrolment — correct or withdraw it instead")
    return _insert(e, kind, method, notes, None,
                   _validate(e, kind, signed_name, signed_on, method,
                             relationship, contact_id))


def _insert(e: _enrolments.Enrolment, kind: str, method: str,
            notes: str | None, replaces: int | None,
            v: dict[str, Any], conn: Any = None) -> Agreement:
    own = conn is None
    ctx = _db() if own else contextlib.nullcontext(conn)
    with ctx as c:
        cur = c.execute(
            "INSERT INTO enrolment_agreements (enrolment_id, student_id, "
            "kind, signed_name, relationship, contact_id, signed_on, method, "
            "replaces_id, notes, recorded_by) VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (e.enrolment_id, e.student_id, kind, v["signed_name"],
             v["relationship"], v["contact_id"], v["signed_on"], method,
             replaces, (notes or "").strip() or None, _enrolments._actor()))
        aid = cur.lastrowid
        _history(c, {"agreement_id": aid, "enrolment_id": e.enrolment_id},
                 "recorded" if replaces is None else "recorded (correction)",
                 f"{kind}: {v['signed_name']}"
                 + (f" ({v['relationship']})" if v["relationship"] else "")
                 + f", {method}, {v['signed_on']}")
        r = c.execute("SELECT * FROM enrolment_agreements WHERE "
                      "agreement_id = ?", (aid,)).fetchone()
    logger.info("%s agreement #%d recorded for enrolment #%d", kind, aid,
                e.enrolment_id)
    return _row(r)


def _end(agreement_id: int, reason: str) -> Agreement:
    """The current agreement about to be withdrawn / corrected."""
    a = get(agreement_id)
    if a is None:
        raise ValidationError(f"No agreement #{agreement_id}")
    if not a.is_current:
        raise ValidationError(f"Agreement #{agreement_id} is already "
                              f"{a.status}")
    why = (reason or "").strip()
    if not why:
        raise ValidationError("Give a reason")
    return a


def withdraw(agreement_id: int, *, reason: str) -> Agreement:
    """Mark a signature Withdrawn (e.g. signed by the wrong person)."""
    _enrolments._require_writer("withdrawing learner agreements")
    a = _end(agreement_id, reason)
    with _db() as conn:
        conn.execute(
            "UPDATE enrolment_agreements SET status = 'Withdrawn', "
            "ended_by = ?, ended_at = datetime('now'), ended_reason = ? "
            "WHERE agreement_id = ?",
            (_enrolments._actor(), reason.strip(), a.agreement_id))
        _history(conn, a, "withdrawn", reason.strip())
    out = get(a.agreement_id)
    assert out is not None
    return out


def correct(agreement_id: int, *, reason: str, method: str | None = None,
            signed_name: str | None = None, signed_on: str | None = None,
            relationship: str | None = None, contact_id: int | None = None,
            notes: str | None = None) -> Agreement:
    """Replace a signature's details: the old row becomes Corrected and a
    new current row (``replaces_id`` = the old one) is returned. Fields
    left out keep the old values."""
    _enrolments._require_writer("correcting learner agreements")
    old = _end(agreement_id, reason)
    e = _enrolments.get_enrolment(old.enrolment_id)
    if e is None:
        raise ValidationError(f"No enrolment #{old.enrolment_id}")
    m = method or old.method
    v = _validate(e, old.kind, signed_name or old.signed_name,
                  signed_on or old.signed_on, m,
                  relationship if relationship is not None
                  else old.relationship,
                  contact_id if contact_id is not None else old.contact_id)
    with _db() as conn:
        conn.execute(
            "UPDATE enrolment_agreements SET status = 'Corrected', "
            "ended_by = ?, ended_at = datetime('now'), ended_reason = ? "
            "WHERE agreement_id = ?",
            (_enrolments._actor(), reason.strip(), old.agreement_id))
        _history(conn, old, "corrected", reason.strip())
        return _insert(e, old.kind, m, notes if notes is not None
                       else old.notes, old.agreement_id, v, conn=conn)
