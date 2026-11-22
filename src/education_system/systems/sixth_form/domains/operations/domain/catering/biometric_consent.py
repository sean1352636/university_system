"""Biometric consent for the Sixth Form System (Protection of Freedoms
Act 2012, Chapter 2, ss. 26–28, and the DfE guidance "Protection of
children's biometric information in schools").

What the law asks of a college that uses biometrics (e.g. fingerprint
recognition at the catering till), and how this module records it:

* **Written consent before any processing.** For a learner under 18
  (a "child" in s. 28) at least one parent must consent in writing
  (s. 26(3)(a)); for an adult the consent is the learner's own (UK GDPR
  explicit consent for special-category data). :func:`record_consent`
  insists on a written form and keeps the document reference.
* **Objection beats consent.** If the learner — at any age — objects or
  refuses, processing must stop whatever a parent said (s. 26(5)); for
  an under-18, any parent's written objection or withdrawal stops it too
  (s. 26(3)(b)). :func:`record_objection` / :func:`withdraw_consent`.
* **A reasonable alternative** (s. 26(7)): the till always accepts the
  ID card number or a PIN instead (``cashless.ALTERNATIVE_ID_METHODS``).
* **Stop and delete.** When consent goes, the template held by the
  reader supplier must be deleted; :func:`templates_to_delete` is that
  to-do list and :func:`confirm_template_deleted` records it was done.

The age at which the learner's own consent is enough is a college
setting (``learner_consent_age``). It defaults to **18**, which is what
s. 26 requires of FE institutions: under 18 a parent's written consent
is needed and the learner's objection still overrides it. A college that
has taken advice otherwise can lower it to 16 or 17 — a parent's
objection still stops processing for any under-18.

The decision is :func:`status_for`; the till calls :func:`require_allowed`,
which refuses (``BiometricRefused``) and logs the refusal. Every consent
change, objection and refusal is written to ``biometric_audit``.

Permissions: OPERATIONS to record or change consent and objections; the
consent register and audit need OPERATIONS too.
"""

from __future__ import annotations

import datetime as _dt
import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from education_system import paths
from education_system.systems.sixth_form.infrastructure import database as _sql

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_STUDENTS_DB

DEFAULT_PURPOSE = "Cashless catering"
PURPOSES: tuple[str, ...] = (DEFAULT_PURPOSE, "Library", "Building access")

LEARNER = "Learner"
PARENT = "Parent/Carer"
PARTIES: tuple[str, ...] = (LEARNER, PARENT)

#: Consent must be in writing (s. 26(3)); these are the accepted forms.
CONSENT_FORMS: tuple[str, ...] = (
    "Signed paper form", "Signed electronic form", "Signed letter")

OBJECTION_HOW: tuple[str, ...] = (
    "In writing", "Told staff", "Refused at the till")

CURRENT = "Current"
WITHDRAWN = "Withdrawn"
ACTIVE = "Active"
LIFTED = "Lifted"
ENROLLED = "Enrolled"
DELETED = "Deleted"

ADULT_AGE = 18
DEFAULT_LEARNER_CONSENT_AGE = 18

_SCHEMA = """
CREATE TABLE IF NOT EXISTS biometric_consents (
    consent_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL,
    purpose         TEXT NOT NULL DEFAULT 'Cashless catering',
    given_by        TEXT NOT NULL CHECK (given_by IN ('Learner', 'Parent/Carer')),
    given_by_name   TEXT NOT NULL,
    relationship    TEXT,
    consent_form    TEXT NOT NULL,
    document_ref    TEXT,
    given_on        TEXT NOT NULL,
    learner_age     INTEGER,
    status          TEXT NOT NULL DEFAULT 'Current',
    withdrawn_on    TEXT,
    withdrawn_by    TEXT,
    withdrawn_by_name TEXT,
    withdrawal_note TEXT,
    recorded_by     TEXT,
    withdrawal_recorded_by TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_bio_one_current
    ON biometric_consents(student_id, purpose, given_by)
    WHERE status = 'Current';
CREATE INDEX IF NOT EXISTS idx_bio_cons_student ON biometric_consents(student_id);

CREATE TABLE IF NOT EXISTS biometric_objections (
    objection_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL,
    purpose         TEXT NOT NULL DEFAULT 'Cashless catering',
    raised_by       TEXT NOT NULL CHECK (raised_by IN ('Learner', 'Parent/Carer')),
    raised_by_name  TEXT NOT NULL,
    raised_on       TEXT NOT NULL,
    how             TEXT NOT NULL,
    note            TEXT,
    status          TEXT NOT NULL DEFAULT 'Active',
    lifted_on       TEXT,
    lifted_note     TEXT,
    recorded_by     TEXT,
    lifted_by       TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);
CREATE INDEX IF NOT EXISTS idx_bio_obj_student ON biometric_objections(student_id);

CREATE TABLE IF NOT EXISTS biometric_enrolments (
    enrolment_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL,
    purpose         TEXT NOT NULL DEFAULT 'Cashless catering',
    enrolled_on     TEXT NOT NULL,
    enrolled_by     TEXT,
    status          TEXT NOT NULL DEFAULT 'Enrolled',
    deleted_on      TEXT,
    deleted_by      TEXT,
    deletion_note   TEXT,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_bio_one_enrolment
    ON biometric_enrolments(student_id, purpose) WHERE status = 'Enrolled';

CREATE TABLE IF NOT EXISTS biometric_audit (
    log_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    at          TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    student_id  TEXT,
    purpose     TEXT,
    event       TEXT NOT NULL,
    detail      TEXT,
    actor       TEXT
);
CREATE INDEX IF NOT EXISTS idx_bio_audit_student ON biometric_audit(student_id);

CREATE TABLE IF NOT EXISTS biometric_settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_by  TEXT,
    updated_at  TEXT DEFAULT (datetime('now'))
);
"""


class ValidationError(ValueError):
    pass


class BiometricRefused(ValidationError):
    """No current consent (or an objection): use card or PIN instead."""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Consent:
    consent_id: int
    student_id: str
    purpose: str
    given_by: str
    given_by_name: str
    relationship: str | None
    consent_form: str
    document_ref: str | None
    given_on: str
    learner_age: int | None
    status: str
    withdrawn_on: str | None
    withdrawn_by: str | None
    withdrawn_by_name: str | None
    withdrawal_note: str | None
    recorded_by: str | None
    student_name: str | None = None


@dataclass
class Objection:
    objection_id: int
    student_id: str
    purpose: str
    raised_by: str
    raised_by_name: str
    raised_on: str
    how: str
    note: str | None
    status: str
    lifted_on: str | None
    lifted_note: str | None
    recorded_by: str | None
    student_name: str | None = None


@dataclass
class BiometricStatus:
    student_id: str
    purpose: str
    allowed: bool
    reason: str
    age: int | None
    learner_consent: Consent | None = None
    parent_consent: Consent | None = None
    objections: list[Objection] = field(default_factory=list)
    enrolled: bool = False


# ── DB plumbing ─────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[_sql.Connection]:
    paths.ensure_sixth_form_directories()
    conn = _sql.connect(str(DB_PATH))
    conn.row_factory = _sql.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


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
    _DB_READY = True


def _consent(r: _sql.Row) -> Consent:
    keys = r.keys()
    return Consent(
        consent_id=r["consent_id"], student_id=r["student_id"],
        purpose=r["purpose"], given_by=r["given_by"],
        given_by_name=r["given_by_name"], relationship=r["relationship"],
        consent_form=r["consent_form"], document_ref=r["document_ref"],
        given_on=r["given_on"], learner_age=r["learner_age"],
        status=r["status"], withdrawn_on=r["withdrawn_on"],
        withdrawn_by=r["withdrawn_by"],
        withdrawn_by_name=r["withdrawn_by_name"],
        withdrawal_note=r["withdrawal_note"], recorded_by=r["recorded_by"],
        student_name=(f"{r['s_first']} {r['s_last']}".strip()
                      if "s_first" in keys and r["s_first"] else None))


def _objection(r: _sql.Row) -> Objection:
    keys = r.keys()
    return Objection(
        objection_id=r["objection_id"], student_id=r["student_id"],
        purpose=r["purpose"], raised_by=r["raised_by"],
        raised_by_name=r["raised_by_name"], raised_on=r["raised_on"],
        how=r["how"], note=r["note"], status=r["status"],
        lifted_on=r["lifted_on"], lifted_note=r["lifted_note"],
        recorded_by=r["recorded_by"],
        student_name=(f"{r['s_first']} {r['s_last']}".strip()
                      if "s_first" in keys and r["s_first"] else None))


# ── Helpers ─────────────────────────────────────────────────────────

def _access():
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return access


def _actor() -> str:
    return _access().current().username or "system"


def _require_ops(action: str) -> None:
    a = _access()
    a.current().require(a.OPERATIONS, action)


def _text(v: Any) -> str | None:
    s = str(v).strip() if v is not None else ""
    return s or None


def _choice(v: Any, options: tuple[str, ...], label: str,
            default: str | None = None) -> str:
    s = _text(v) or default
    for o in options:
        if s and s.lower() == o.lower():
            return o
    raise ValidationError(f"{label} must be one of: {', '.join(options)}")


def _date(v: Any, label: str) -> str:
    s = _text(v) or _dt.date.today().isoformat()
    try:
        d = _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} must be YYYY-MM-DD") from None
    if d > _dt.date.today():
        raise ValidationError(f"{label} cannot be in the future")
    return d.isoformat()


def _student(sid: Any):
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    s = _text(sid)
    if not s:
        raise ValidationError("Student is required")
    st = _students.get_student(s)
    if st is None:
        raise ValidationError(f"No student with id {s}")
    return st


def age_on(dob: str | None, day: str | None = None) -> int | None:
    if not dob:
        return None
    try:
        b = _dt.date.fromisoformat(str(dob)[:10])
    except ValueError:
        return None
    d = _dt.date.fromisoformat(day) if day else _dt.date.today()
    return d.year - b.year - ((d.month, d.day) < (b.month, b.day))


def _audit(conn: _sql.Connection, student_id: str | None, purpose: str | None,
           event: str, detail: str | None = None) -> None:
    conn.execute(
        "INSERT INTO biometric_audit (student_id, purpose, event, detail, actor)"
        " VALUES (?, ?, ?, ?, ?)",
        (student_id, purpose, event, detail, _actor()))


# ── Settings ────────────────────────────────────────────────────────

def learner_consent_age() -> int:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT value FROM biometric_settings "
                         "WHERE key = 'learner_consent_age'").fetchone()
    try:
        return int(r["value"]) if r else DEFAULT_LEARNER_CONSENT_AGE
    except ValueError:
        return DEFAULT_LEARNER_CONSENT_AGE


def set_learner_consent_age(age: Any) -> int:
    """From what age the learner's own written consent is enough (16–18).

    18 (the default) follows s. 26 for under-18s at FE institutions.
    """
    _require_ops("biometric consent settings")
    try:
        v = int(age)
    except (TypeError, ValueError):
        raise ValidationError("Age must be a whole number") from None
    if v not in (16, 17, 18):
        raise ValidationError("Age must be 16, 17 or 18")
    with _connect() as conn:
        conn.execute(
            "INSERT INTO biometric_settings (key, value, updated_by) VALUES "
            "('learner_consent_age', ?, ?) ON CONFLICT(key) DO UPDATE SET "
            "value = excluded.value, updated_by = excluded.updated_by, "
            "updated_at = datetime('now')", (str(v), _actor()))
        _audit(conn, None, None, "Setting changed",
               f"learner_consent_age = {v}")
    return v


# ── Consent ─────────────────────────────────────────────────────────

def record_consent(student_id: str, *, given_by: str, given_by_name: str,
                   consent_form: str, relationship: str | None = None,
                   document_ref: str | None = None,
                   given_on: str | None = None,
                   purpose: str = DEFAULT_PURPOSE) -> Consent:
    """Record written consent from the learner or a parent/carer."""
    _require_ops("biometric consent")
    init_db()
    st = _student(student_id)
    party = _choice(given_by, PARTIES, "Given by")
    name = _text(given_by_name)
    if not name:
        raise ValidationError("Name of the person consenting is required")
    form = _choice(consent_form, CONSENT_FORMS, "Consent form")
    purp = _choice(purpose, PURPOSES, "Purpose", DEFAULT_PURPOSE)
    day = _date(given_on, "Consent date")
    age = age_on(st.date_of_birth, day)
    rel = _text(relationship)
    if party == PARENT and not rel:
        raise ValidationError("Relationship to the learner is required")
    if party == PARENT and age is not None and age >= ADULT_AGE:
        raise ValidationError(
            f"{st.full_name} was {age} on {day}: an adult gives their own "
            "consent")
    objs = [o for o in list_objections(student_id=st.student_id,
                                       purpose=purp, active_only=True)
            if o.raised_by == party]
    if objs:
        raise ValidationError(
            f"There is an active objection from the {party.lower()} "
            f"(#{objs[0].objection_id}). Lift it on their instruction first.")
    with _connect() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO biometric_consents (student_id, purpose, "
                "given_by, given_by_name, relationship, consent_form, "
                "document_ref, given_on, learner_age, recorded_by) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (st.student_id, purp, party, name, rel, form,
                 _text(document_ref), day, age, _actor()))
        except _sql.IntegrityError:
            raise ValidationError(
                f"There is already current {party.lower()} consent for "
                f"{purp.lower()}; withdraw it before recording a new one"
            ) from None
        cid = int(cur.lastrowid)
        _audit(conn, st.student_id, purp, "Consent recorded",
               f"{party} {name} ({form}) on {day}")
    logger.info("Biometric consent #%d recorded for %s (%s)", cid,
                st.student_id, party)
    out = get_consent(cid)
    assert out is not None
    return out


def withdraw_consent(consent_id: int, *, withdrawn_by: str,
                     withdrawn_by_name: str, note: str | None = None,
                     withdrawn_on: str | None = None) -> Consent:
    """Consent withdrawn — biometric use stops at once."""
    _require_ops("biometric consent")
    c = get_consent(int(consent_id))
    if c is None:
        raise ValidationError(f"No consent #{consent_id}")
    if c.status != CURRENT:
        raise ValidationError(f"Consent #{c.consent_id} is already {c.status}")
    party = _choice(withdrawn_by, PARTIES, "Withdrawn by")
    name = _text(withdrawn_by_name)
    if not name:
        raise ValidationError("Name of the person withdrawing is required")
    day = _date(withdrawn_on, "Withdrawal date")
    with _connect() as conn:
        conn.execute(
            "UPDATE biometric_consents SET status = 'Withdrawn', "
            "withdrawn_on = ?, withdrawn_by = ?, withdrawn_by_name = ?, "
            "withdrawal_note = ?, withdrawal_recorded_by = ?, "
            "updated_at = datetime('now') WHERE consent_id = ?",
            (day, party, name, _text(note), _actor(), c.consent_id))
        _audit(conn, c.student_id, c.purpose, "Consent withdrawn",
               f"#{c.consent_id} by {party} {name}")
    out = get_consent(c.consent_id)
    assert out is not None
    return out


def get_consent(consent_id: int) -> Consent | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT c.*, s.first_name AS s_first, s.last_name AS s_last "
            "FROM biometric_consents c LEFT JOIN students s "
            "ON s.student_id = c.student_id WHERE c.consent_id = ?",
            (consent_id,)).fetchone()
    return _consent(r) if r else None


def list_consents(*, student_id: str | None = None,
                  purpose: str | None = None,
                  current_only: bool = False) -> list[Consent]:
    init_db()
    clauses, args = [], []
    if student_id:
        clauses.append("c.student_id = ?")
        args.append(student_id.strip())
    if purpose:
        clauses.append("c.purpose = ?")
        args.append(purpose)
    if current_only:
        clauses.append("c.status = 'Current'")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        # db-audit: ignore[DBW001] - where joins fixed clause literals only
        rows = conn.execute(
            "SELECT c.*, s.first_name AS s_first, s.last_name AS s_last "
            f"FROM biometric_consents c LEFT JOIN students s "
            f"ON s.student_id = c.student_id {where} "
            "ORDER BY c.consent_id DESC", args).fetchall()
    return [_consent(r) for r in rows]


# ── Objections ──────────────────────────────────────────────────────

def record_objection(student_id: str, *, raised_by: str, raised_by_name: str,
                     how: str, note: str | None = None,
                     raised_on: str | None = None,
                     purpose: str = DEFAULT_PURPOSE) -> Objection:
    """The learner (any age) or a parent/carer (under-18) objects."""
    _require_ops("biometric consent")
    init_db()
    st = _student(student_id)
    party = _choice(raised_by, PARTIES, "Raised by")
    name = _text(raised_by_name)
    if not name:
        raise ValidationError("Name of the person objecting is required")
    hw = _choice(how, OBJECTION_HOW, "How")
    purp = _choice(purpose, PURPOSES, "Purpose", DEFAULT_PURPOSE)
    day = _date(raised_on, "Objection date")
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO biometric_objections (student_id, purpose, raised_by,"
            " raised_by_name, raised_on, how, note, recorded_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (st.student_id, purp, party, name, day, hw, _text(note), _actor()))
        oid = int(cur.lastrowid)
        _audit(conn, st.student_id, purp, "Objection recorded",
               f"{party} {name} ({hw})")
    out = get_objection(oid)
    assert out is not None
    return out


def lift_objection(objection_id: int, *, note: str) -> Objection:
    """Lift an objection on the instruction of the person who raised it."""
    _require_ops("biometric consent")
    o = get_objection(int(objection_id))
    if o is None:
        raise ValidationError(f"No objection #{objection_id}")
    if o.status != ACTIVE:
        raise ValidationError(f"Objection #{o.objection_id} is already lifted")
    n = _text(note)
    if not n:
        raise ValidationError(
            f"Say how {o.raised_by_name} asked for the objection to be lifted")
    with _connect() as conn:
        conn.execute(
            "UPDATE biometric_objections SET status = 'Lifted', lifted_on = "
            "date('now', 'localtime'), lifted_note = ?, lifted_by = ? "
            "WHERE objection_id = ?", (n, _actor(), o.objection_id))
        _audit(conn, o.student_id, o.purpose, "Objection lifted",
               f"#{o.objection_id}: {n}")
    out = get_objection(o.objection_id)
    assert out is not None
    return out


def get_objection(objection_id: int) -> Objection | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT o.*, s.first_name AS s_first, s.last_name AS s_last "
            "FROM biometric_objections o LEFT JOIN students s "
            "ON s.student_id = o.student_id WHERE o.objection_id = ?",
            (objection_id,)).fetchone()
    return _objection(r) if r else None


def list_objections(*, student_id: str | None = None,
                    purpose: str | None = None,
                    active_only: bool = False) -> list[Objection]:
    init_db()
    clauses, args = [], []
    if student_id:
        clauses.append("o.student_id = ?")
        args.append(student_id.strip())
    if purpose:
        clauses.append("o.purpose = ?")
        args.append(purpose)
    if active_only:
        clauses.append("o.status = 'Active'")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        # db-audit: ignore[DBW001] - where joins fixed clause literals only
        rows = conn.execute(
            "SELECT o.*, s.first_name AS s_first, s.last_name AS s_last "
            f"FROM biometric_objections o LEFT JOIN students s "
            f"ON s.student_id = o.student_id {where} "
            "ORDER BY o.objection_id DESC", args).fetchall()
    return [_objection(r) for r in rows]


# ── The decision ────────────────────────────────────────────────────

def _decide(st, purpose: str, consents: list[Consent],
            objections: list[Objection], consent_age: int,
            enrolled: bool) -> BiometricStatus:
    age = age_on(st.date_of_birth)
    learner = next((c for c in consents if c.given_by == LEARNER), None)
    parent = next((c for c in consents if c.given_by == PARENT), None)
    out = BiometricStatus(st.student_id, purpose, False, "", age, learner,
                          parent, objections, enrolled)
    if any(o.raised_by == LEARNER for o in objections):
        out.reason = "Learner objects (s. 26(5)) — use card or PIN"
        return out
    minor = age is None or age < ADULT_AGE
    if minor and any(o.raised_by == PARENT for o in objections):
        out.reason = "Parent/carer objects — use card or PIN"
        return out
    if age is None:
        # Unknown age: treat as a child and need a parent's consent.
        if parent is not None:
            out.allowed, out.reason = True, "Parent/carer consent (age unknown)"
        else:
            out.reason = "Date of birth missing — parent consent needed"
        return out
    if age >= consent_age:
        if learner is not None and (learner.learner_age is None
                                    or learner.learner_age >= consent_age):
            out.allowed, out.reason = True, "Learner's own consent"
        elif parent is not None and age >= ADULT_AGE:
            out.reason = "Now 18 — needs the learner's own consent"
        elif learner is None and parent is not None:
            # Parent consent remains valid while still a child.
            out.allowed, out.reason = True, "Parent/carer consent"
        else:
            out.reason = "No written consent"
        return out
    if parent is not None:
        out.allowed, out.reason = True, "Parent/carer consent"
    else:
        out.reason = (f"Under {consent_age}: needs a parent/carer's written "
                      "consent")
    return out


def status_for(student_id: str, purpose: str = DEFAULT_PURPOSE
               ) -> BiometricStatus:
    st = _student(student_id)
    purp = _choice(purpose, PURPOSES, "Purpose", DEFAULT_PURPOSE)
    consents = list_consents(student_id=st.student_id, purpose=purp,
                             current_only=True)
    objs = list_objections(student_id=st.student_id, purpose=purp,
                           active_only=True)
    with _connect() as conn:
        enrolled = conn.execute(
            "SELECT 1 FROM biometric_enrolments WHERE student_id = ? AND "
            "purpose = ? AND status = 'Enrolled'",
            (st.student_id, purp)).fetchone() is not None
    return _decide(st, purp, consents, objs, learner_consent_age(), enrolled)


def require_allowed(student_id: str, purpose: str = DEFAULT_PURPOSE, *,
                    context: str = "") -> BiometricStatus:
    """Raise :class:`BiometricRefused` (and log it) unless allowed now."""
    s = status_for(student_id, purpose)
    if not s.allowed:
        with _connect() as conn:
            _audit(conn, s.student_id, s.purpose, "Biometric refused",
                   f"{context}: {s.reason}".strip(": "))
        raise BiometricRefused(
            f"Biometric identification refused: {s.reason}. Use the "
            "learner's ID card or PIN instead.")
    return s


def allowed_map(purpose: str = DEFAULT_PURPOSE) -> dict[str, str]:
    """student_id → "Allowed" or the reason it is not, for students with
    any consent/objection record (others have no consent)."""
    init_db()
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    consents: dict[str, list[Consent]] = {}
    for c in list_consents(purpose=purpose, current_only=True):
        consents.setdefault(c.student_id, []).append(c)
    objs: dict[str, list[Objection]] = {}
    for o in list_objections(purpose=purpose, active_only=True):
        objs.setdefault(o.student_id, []).append(o)
    ids = set(consents) | set(objs)
    if not ids:
        return {}
    age = learner_consent_age()
    out: dict[str, str] = {}
    for s in _students.list_students():
        if s.student_id not in ids:
            continue
        d = _decide(s, purpose, consents.get(s.student_id, []),
                    objs.get(s.student_id, []), age, False)
        out[s.student_id] = "Allowed" if d.allowed else d.reason
    return out


def register(purpose: str = DEFAULT_PURPOSE, *,
             include_left: bool = False) -> list[BiometricStatus]:
    """Consent register: every learner's biometric position (OPERATIONS)."""
    _require_ops("the biometric consent register")
    init_db()
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    purp = _choice(purpose, PURPOSES, "Purpose", DEFAULT_PURPOSE)
    consents: dict[str, list[Consent]] = {}
    for c in list_consents(purpose=purp, current_only=True):
        consents.setdefault(c.student_id, []).append(c)
    objs: dict[str, list[Objection]] = {}
    for o in list_objections(purpose=purp, active_only=True):
        objs.setdefault(o.student_id, []).append(o)
    with _connect() as conn:
        enrolled = {r[0] for r in conn.execute(
            "SELECT student_id FROM biometric_enrolments WHERE purpose = ? "
            "AND status = 'Enrolled'", (purp,))}
    age = learner_consent_age()
    out = []
    for s in sorted(_students.list_students(),
                    key=lambda s: (s.last_name, s.first_name)):
        if s.status == "Left" and not include_left \
                and s.student_id not in enrolled:
            continue
        out.append(_decide(s, purp, consents.get(s.student_id, []),
                           objs.get(s.student_id, []), age,
                           s.student_id in enrolled))
    return out


# ── Templates held by the reader ────────────────────────────────────

def enrol_template(student_id: str, purpose: str = DEFAULT_PURPOSE) -> None:
    """Record that the learner's template was taken by the reader —
    only allowed with current consent."""
    _require_ops("biometric enrolment")
    s = require_allowed(student_id, purpose, context="enrolment")
    with _connect() as conn:
        try:
            conn.execute(
                "INSERT INTO biometric_enrolments (student_id, purpose, "
                "enrolled_on, enrolled_by) VALUES (?, ?, date('now', "
                "'localtime'), ?)", (s.student_id, s.purpose, _actor()))
        except _sql.IntegrityError:
            raise ValidationError("Already enrolled") from None
        _audit(conn, s.student_id, s.purpose, "Template enrolled")


def templates_to_delete(purpose: str | None = None) -> list[BiometricStatus]:
    """Enrolled templates whose consent has gone (or learner has left):
    the reader supplier must delete them."""
    _require_ops("biometric enrolment")
    init_db()
    out = []
    purposes = (purpose,) if purpose else PURPOSES
    for purp in purposes:
        with _connect() as conn:
            ids = [r[0] for r in conn.execute(
                "SELECT student_id FROM biometric_enrolments WHERE purpose = ? "
                "AND status = 'Enrolled'", (purp,))]
        for sid in ids:
            try:
                s = status_for(sid, purp)
            except ValidationError:
                continue
            st = _student(sid)
            if not s.allowed or st.status == "Left":
                if s.allowed:
                    s.reason = "Learner has left"
                out.append(s)
    return out


def confirm_template_deleted(student_id: str, *, note: str | None = None,
                             purpose: str = DEFAULT_PURPOSE) -> None:
    _require_ops("biometric enrolment")
    st = _student(student_id)
    purp = _choice(purpose, PURPOSES, "Purpose", DEFAULT_PURPOSE)
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE biometric_enrolments SET status = 'Deleted', deleted_on = "
            "date('now', 'localtime'), deleted_by = ?, deletion_note = ? "
            "WHERE student_id = ? AND purpose = ? AND status = 'Enrolled'",
            (_actor(), _text(note), st.student_id, purp))
        if not cur.rowcount:
            raise ValidationError(f"No enrolled template for {st.full_name}")
        _audit(conn, st.student_id, purp, "Template deleted", _text(note))


def audit_log(*, student_id: str | None = None,
              limit: int = 500) -> list[dict[str, Any]]:
    _require_ops("the biometric audit log")
    init_db()
    with _connect() as conn:
        if student_id:
            rows = conn.execute(
                "SELECT * FROM biometric_audit WHERE student_id = ? "
                "ORDER BY log_id DESC LIMIT ?", (student_id.strip(), int(limit)))
        else:
            rows = conn.execute(
                "SELECT * FROM biometric_audit ORDER BY log_id DESC LIMIT ?",
                (int(limit),))
        return [dict(r) for r in rows]


def refusals_on(day: str | None = None) -> int:
    init_db()
    d = day or _dt.date.today().isoformat()
    with _connect() as conn:
        return int(conn.execute(
            "SELECT COUNT(*) FROM biometric_audit WHERE event = "
            "'Biometric refused' AND date(at) = ?", (d,)).fetchone()[0])
