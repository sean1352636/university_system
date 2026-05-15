"""Admissions — pre-enrolment applicant pipeline for the Sixth Form System.

One row per applicant. Applicants progress through a status workflow:

    Submitted → Under Review → Interview Scheduled → Interviewed
              → Offer Made → Offer Accepted | Offer Declined
              → Enrolled (once converted to a `students` row)
              → Waitlisted | Rejected | Withdrawn (terminal)

When an applicant is accepted and enrolled, ``convert_to_student``
creates a row in the ``students`` table and stores the new
``student_id`` back on the applicant. The applicant row is preserved
(audit trail) — it's not deleted.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import secrets
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.sixthform_system.core import paths
from education_system.sixthform_system.modules.domain.students.admissions import (
    admissions as data,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.ADMISSIONS_DB

STATUSES: tuple[str, ...] = (
    "Submitted",
    "Under Review",
    "Interview Scheduled",
    "Interviewed",
    "Offer Made",
    "Offer Accepted",
    "Offer Declined",
    "Waitlisted",
    "Rejected",
    "Withdrawn",
    "Enrolled",
)
DEFAULT_STATUS: str = "Submitted"
OPEN_STATUSES: tuple[str, ...] = (
    "Submitted", "Under Review", "Interview Scheduled",
    "Interviewed", "Offer Made", "Waitlisted",
)
TERMINAL_STATUSES: tuple[str, ...] = (
    "Offer Declined", "Rejected", "Withdrawn", "Enrolled",
)

OFFER_TYPES: tuple[str, ...] = (
    "Unconditional", "Conditional", "Waitlist", "Not Offered",
)
DEFAULT_OFFER_TYPE: str = "Conditional"

SOURCES: tuple[str, ...] = (
    "Direct",
    "Open Evening",
    "School Referral",
    "Online Application",
    "Walk-in",
    "Transfer",
    "Other",
)
DEFAULT_SOURCE: str = "Direct"

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DATE_RE  = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PHONE_RE = re.compile(r"^[0-9 +()\-]+$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS admissions_applicants (
    applicant_id          TEXT PRIMARY KEY,
    first_name            TEXT NOT NULL,
    last_name             TEXT NOT NULL,
    dob                   TEXT,
    email                 TEXT,
    phone                 TEXT,
    address               TEXT,
    previous_school       TEXT,
    predicted_gcses       TEXT,
    subject_1             TEXT,
    subject_2             TEXT,
    subject_3             TEXT,
    reference_name        TEXT,
    reference_contact     TEXT,
    application_source    TEXT NOT NULL DEFAULT 'Direct',
    submitted_at          TEXT NOT NULL,
    status                TEXT NOT NULL DEFAULT 'Submitted',
    offer_type            TEXT,
    offer_conditions      TEXT,
    interview_date        TEXT,
    interviewer           TEXT,
    interview_notes       TEXT,
    decision_by           TEXT,
    decision_date         TEXT,
    decision_notes        TEXT,
    converted_student_id  TEXT,
    notes                 TEXT,
    created_at            TEXT DEFAULT (datetime('now')),
    updated_at            TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_adm_status     ON admissions_applicants(status);
CREATE INDEX IF NOT EXISTS idx_adm_submitted  ON admissions_applicants(submitted_at);
CREATE INDEX IF NOT EXISTS idx_adm_last_name  ON admissions_applicants(last_name);
CREATE INDEX IF NOT EXISTS idx_adm_email      ON admissions_applicants(email);
"""


@dataclass
class Applicant:
    applicant_id: str
    first_name: str
    last_name: str
    dob: str | None
    email: str | None
    phone: str | None
    address: str | None
    previous_school: str | None
    predicted_gcses: str | None
    subject_1: str | None
    subject_2: str | None
    subject_3: str | None
    reference_name: str | None
    reference_contact: str | None
    application_source: str
    submitted_at: str
    status: str
    offer_type: str | None
    offer_conditions: str | None
    interview_date: str | None
    interviewer: str | None
    interview_notes: str | None
    decision_by: str | None
    decision_date: str | None
    decision_notes: str | None
    converted_student_id: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def subjects(self) -> list[str]:
        return [s for s in (self.subject_1, self.subject_2, self.subject_3)
                if s]

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES

    @property
    def is_enrolled(self) -> bool:
        return self.status == "Enrolled" and bool(self.converted_student_id)


@dataclass
class Summary:
    total: int
    by_status: dict[str, int]
    by_source: dict[str, int]
    open_count: int
    awaiting_decision: int       # Under Review, Interviewed
    pending_offers: int          # Offer Made
    converted: int               # Enrolled
    rejected: int
    upcoming_interviews: int     # interview_date in [today, today+window]


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Admissions schema ready at %s", DB_PATH)

    _DB_READY = True


def _row(r: sqlite3.Row) -> Applicant:
    return Applicant(
        applicant_id=r["applicant_id"],
        first_name=r["first_name"], last_name=r["last_name"],
        dob=r["dob"], email=r["email"], phone=r["phone"],
        address=r["address"],
        previous_school=r["previous_school"],
        predicted_gcses=r["predicted_gcses"],
        subject_1=r["subject_1"], subject_2=r["subject_2"],
        subject_3=r["subject_3"],
        reference_name=r["reference_name"],
        reference_contact=r["reference_contact"],
        application_source=r["application_source"],
        submitted_at=r["submitted_at"], status=r["status"],
        offer_type=r["offer_type"],
        offer_conditions=r["offer_conditions"],
        interview_date=r["interview_date"],
        interviewer=r["interviewer"],
        interview_notes=r["interview_notes"],
        decision_by=r["decision_by"],
        decision_date=r["decision_date"],
        decision_notes=r["decision_notes"],
        converted_student_id=r["converted_student_id"],
        notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_date(value: Any, label: str, *,
                    required: bool = False) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
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


def _validate_email(value: Any) -> str | None:
    if not value:
        return None
    s = str(value).strip()
    if not _EMAIL_RE.match(s):
        raise ValidationError("Email is not a valid address")
    return s


def _validate_phone(value: Any) -> str | None:
    if not value:
        return None
    s = str(value).strip()
    if not _PHONE_RE.match(s):
        raise ValidationError("Phone contains invalid characters")
    return s


def _validate_subject(value: Any, field_name: str) -> str | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        return None
    s = str(value).strip()
    # Validate against the live subjects catalogue, but tolerate a
    # missing/empty table by falling back to "free text accepted".
    try:
        from education_system.sixthform_system.modules.domain.academics.subjects import (
            subjects as _subjects,
        )
        names = {x.name for x in _subjects.list_subjects()}
        if names and s not in names:
            raise ValidationError(
                f"{field_name}: {s!r} is not a recognised subject")
    except ValidationError:
        raise
    except Exception:
        pass
    return s


def _validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["first_name"] = _require(payload.get("first_name"),
                                    "First name").strip()
    out["last_name"]  = _require(payload.get("last_name"),
                                    "Last name").strip()
    out["dob"]               = _validate_date(payload.get("dob"),
                                                  "Date of birth")
    out["email"]             = _validate_email(payload.get("email"))
    out["phone"]             = _validate_phone(payload.get("phone"))
    out["address"]           = (payload.get("address") or "").strip() or None
    out["previous_school"]   = (payload.get("previous_school")
                                  or "").strip() or None
    out["predicted_gcses"]   = (payload.get("predicted_gcses")
                                  or "").strip() or None
    out["subject_1"]         = _validate_subject(
        payload.get("subject_1"), "Subject 1")
    out["subject_2"]         = _validate_subject(
        payload.get("subject_2"), "Subject 2")
    out["subject_3"]         = _validate_subject(
        payload.get("subject_3"), "Subject 3")
    out["reference_name"]    = (payload.get("reference_name")
                                  or "").strip() or None
    out["reference_contact"] = (payload.get("reference_contact")
                                  or "").strip() or None

    source = (payload.get("application_source") or DEFAULT_SOURCE).strip()
    if source not in SOURCES:
        raise ValidationError(
            f"Application source must be one of: {', '.join(SOURCES)}")
    out["application_source"] = source

    out["submitted_at"] = _validate_date(
        payload.get("submitted_at"), "Submitted on", required=True)

    status = (payload.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    offer_type = (payload.get("offer_type") or "").strip()
    if offer_type:
        if offer_type not in OFFER_TYPES:
            raise ValidationError(
                f"Offer type must be one of: {', '.join(OFFER_TYPES)}")
    out["offer_type"] = offer_type or None
    out["offer_conditions"] = (payload.get("offer_conditions")
                                or "").strip() or None

    out["interview_date"] = _validate_date(
        payload.get("interview_date"), "Interview date")
    out["interviewer"]      = (payload.get("interviewer")
                                  or "").strip() or None
    out["interview_notes"]  = (payload.get("interview_notes")
                                  or "").strip() or None

    out["decision_by"]      = (payload.get("decision_by")
                                  or "").strip() or None
    out["decision_date"]    = _validate_date(
        payload.get("decision_date"), "Decision date")
    out["decision_notes"]   = (payload.get("decision_notes")
                                  or "").strip() or None

    out["converted_student_id"] = (payload.get("converted_student_id")
                                      or "").strip() or None
    out["notes"]            = (payload.get("notes") or "").strip() or None
    return out


# ── ID generation ─────────────────────────────────────────────────

def generate_applicant_id() -> str:
    """A1-prefixed 8-character id (random suffix, retried on collision)."""
    for _ in range(10):
        candidate = f"A{secrets.randbelow(10_000_000):07d}"
        with _connect() as conn:
            if not conn.execute(
                    "SELECT 1 FROM admissions_applicants "
                    "WHERE applicant_id = ?", (candidate,)).fetchone():
                return candidate
    raise RuntimeError("Could not generate a unique applicant id")


# ── CRUD ──────────────────────────────────────────────────────────

def create_applicant(payload: dict[str, Any]) -> Applicant:
    init_db()
    p = _validate_payload(payload)
    aid = generate_applicant_id()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO admissions_applicants
                   (applicant_id, first_name, last_name, dob, email,
                    phone, address, previous_school, predicted_gcses,
                    subject_1, subject_2, subject_3,
                    reference_name, reference_contact,
                    application_source, submitted_at, status,
                    offer_type, offer_conditions,
                    interview_date, interviewer, interview_notes,
                    decision_by, decision_date, decision_notes,
                    converted_student_id, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (aid, p["first_name"], p["last_name"], p["dob"], p["email"],
             p["phone"], p["address"], p["previous_school"],
             p["predicted_gcses"],
             p["subject_1"], p["subject_2"], p["subject_3"],
             p["reference_name"], p["reference_contact"],
             p["application_source"], p["submitted_at"], p["status"],
             p["offer_type"], p["offer_conditions"],
             p["interview_date"], p["interviewer"], p["interview_notes"],
             p["decision_by"], p["decision_date"], p["decision_notes"],
             p["converted_student_id"], p["notes"]),
        )
        conn.commit()
    out = get_applicant(aid)
    assert out is not None
    logger.info("Created applicant %s %s %s (source=%s, status=%s)",
                aid, p["first_name"], p["last_name"],
                p["application_source"], p["status"])
    return out


def get_applicant(applicant_id: str) -> Applicant | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM admissions_applicants WHERE applicant_id = ?",
            (applicant_id.strip(),)).fetchone()
        return _row(r) if r else None


def list_applicants(
    *,
    status: str | None = None,
    source: str | None = None,
    open_only: bool = False,
    has_offer: bool = False,
    enrolled_only: bool = False,
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[Applicant]:
    init_db()
    clauses, args = [], []
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if source:
        if source not in SOURCES:
            raise ValidationError(
                f"Source must be one of: {', '.join(SOURCES)}")
        clauses.append("application_source = ?")
        args.append(source)
    if open_only:
        ph = ",".join("?" * len(OPEN_STATUSES))
        clauses.append(f"status IN ({ph})")
        args.extend(OPEN_STATUSES)
    if has_offer:
        clauses.append("status IN ('Offer Made','Offer Accepted',"
                       "'Offer Declined')")
    if enrolled_only:
        clauses.append("status = 'Enrolled'")
    if search:
        s = f"%{search.strip()}%"
        clauses.append(
            "(applicant_id LIKE ? OR first_name LIKE ? OR "
            "last_name LIKE ? OR email LIKE ?)")
        args.extend([s, s, s, s])
    if date_from:
        clauses.append("submitted_at >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("submitted_at <= ?")
        args.append(_validate_date(date_to, "date_to"))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM admissions_applicants {where} "
           "ORDER BY CASE status "
           "  WHEN 'Submitted'           THEN 0 "
           "  WHEN 'Under Review'        THEN 1 "
           "  WHEN 'Interview Scheduled' THEN 2 "
           "  WHEN 'Interviewed'         THEN 3 "
           "  WHEN 'Offer Made'          THEN 4 "
           "  WHEN 'Offer Accepted'      THEN 5 "
           "  WHEN 'Waitlisted'          THEN 6 "
           "  WHEN 'Offer Declined'      THEN 7 "
           "  WHEN 'Rejected'            THEN 8 "
           "  WHEN 'Withdrawn'           THEN 9 "
           "  WHEN 'Enrolled'            THEN 10 "
           "  ELSE 11 END, "
           "submitted_at DESC, last_name ASC")
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def update_applicant(applicant_id: str,
                     payload: dict[str, Any]) -> Applicant:
    init_db()
    existing = get_applicant(applicant_id)
    if existing is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    merged: dict[str, Any] = {
        "first_name":           payload.get("first_name",
                                            existing.first_name),
        "last_name":            payload.get("last_name",
                                            existing.last_name),
        "dob":                  payload.get("dob", existing.dob),
        "email":                payload.get("email", existing.email),
        "phone":                payload.get("phone", existing.phone),
        "address":              payload.get("address", existing.address),
        "previous_school":      payload.get("previous_school",
                                            existing.previous_school),
        "predicted_gcses":      payload.get("predicted_gcses",
                                            existing.predicted_gcses),
        "subject_1":            payload.get("subject_1",
                                            existing.subject_1),
        "subject_2":            payload.get("subject_2",
                                            existing.subject_2),
        "subject_3":            payload.get("subject_3",
                                            existing.subject_3),
        "reference_name":       payload.get("reference_name",
                                            existing.reference_name),
        "reference_contact":    payload.get("reference_contact",
                                            existing.reference_contact),
        "application_source":   payload.get("application_source",
                                            existing.application_source),
        "submitted_at":         payload.get("submitted_at",
                                            existing.submitted_at),
        "status":               payload.get("status", existing.status),
        "offer_type":           payload.get("offer_type",
                                            existing.offer_type),
        "offer_conditions":     payload.get("offer_conditions",
                                            existing.offer_conditions),
        "interview_date":       payload.get("interview_date",
                                            existing.interview_date),
        "interviewer":          payload.get("interviewer",
                                            existing.interviewer),
        "interview_notes":      payload.get("interview_notes",
                                            existing.interview_notes),
        "decision_by":          payload.get("decision_by",
                                            existing.decision_by),
        "decision_date":        payload.get("decision_date",
                                            existing.decision_date),
        "decision_notes":       payload.get("decision_notes",
                                            existing.decision_notes),
        "converted_student_id": payload.get(
            "converted_student_id", existing.converted_student_id),
        "notes":                payload.get("notes", existing.notes),
    }
    p = _validate_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE admissions_applicants SET
                   first_name = ?, last_name = ?, dob = ?, email = ?,
                   phone = ?, address = ?, previous_school = ?,
                   predicted_gcses = ?, subject_1 = ?, subject_2 = ?,
                   subject_3 = ?, reference_name = ?,
                   reference_contact = ?, application_source = ?,
                   submitted_at = ?, status = ?, offer_type = ?,
                   offer_conditions = ?, interview_date = ?,
                   interviewer = ?, interview_notes = ?,
                   decision_by = ?, decision_date = ?,
                   decision_notes = ?, converted_student_id = ?,
                   notes = ?, updated_at = datetime('now')
               WHERE applicant_id = ?""",
            (p["first_name"], p["last_name"], p["dob"], p["email"],
             p["phone"], p["address"], p["previous_school"],
             p["predicted_gcses"], p["subject_1"], p["subject_2"],
             p["subject_3"], p["reference_name"], p["reference_contact"],
             p["application_source"], p["submitted_at"], p["status"],
             p["offer_type"], p["offer_conditions"],
             p["interview_date"], p["interviewer"], p["interview_notes"],
             p["decision_by"], p["decision_date"], p["decision_notes"],
             p["converted_student_id"], p["notes"], applicant_id),
        )
        conn.commit()
    out = get_applicant(applicant_id)
    assert out is not None
    logger.info("Updated applicant %s (status=%s)",
                applicant_id, out.status)
    return out


def set_status(applicant_id: str, status: str, *,
                decision_by: str | None = None,
                decision_notes: str | None = None,
                decision_date: str | None = None) -> Applicant:
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    payload: dict[str, Any] = {"status": status}
    if status in TERMINAL_STATUSES or status in (
            "Offer Made", "Offer Accepted", "Offer Declined"):
        payload["decision_date"] = (decision_date
                                    or _dt.date.today().isoformat())
    if decision_by is not None:
        payload["decision_by"] = decision_by
    if decision_notes is not None:
        payload["decision_notes"] = decision_notes
    return update_applicant(applicant_id, payload)


def schedule_interview(applicant_id: str, *,
                        interview_date: str,
                        interviewer: str | None = None) -> Applicant:
    return update_applicant(applicant_id, {
        "interview_date": interview_date,
        "interviewer": interviewer,
        "status": "Interview Scheduled",
    })


def record_interview(applicant_id: str, *,
                      interview_notes: str | None = None) -> Applicant:
    return update_applicant(applicant_id, {
        "interview_notes": interview_notes,
        "status": "Interviewed",
    })


def make_offer(applicant_id: str, *,
                offer_type: str = DEFAULT_OFFER_TYPE,
                conditions: str | None = None,
                decided_by: str | None = None) -> Applicant:
    if offer_type not in OFFER_TYPES:
        raise ValidationError(
            f"Offer type must be one of: {', '.join(OFFER_TYPES)}")
    return update_applicant(applicant_id, {
        "status": "Offer Made",
        "offer_type": offer_type,
        "offer_conditions": conditions,
        "decision_by": decided_by,
        "decision_date": _dt.date.today().isoformat(),
    })


def accept_offer(applicant_id: str) -> Applicant:
    return set_status(applicant_id, "Offer Accepted")


def decline_offer(applicant_id: str) -> Applicant:
    return set_status(applicant_id, "Offer Declined")


def reject(applicant_id: str, *, decided_by: str | None = None,
            notes: str | None = None) -> Applicant:
    return set_status(applicant_id, "Rejected",
                       decision_by=decided_by, decision_notes=notes)


def withdraw(applicant_id: str, *, notes: str | None = None) -> Applicant:
    return set_status(applicant_id, "Withdrawn",
                       decision_notes=notes)


def delete_applicant(applicant_id: str) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM admissions_applicants WHERE applicant_id = ?",
            (applicant_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted applicant %s", applicant_id)
            return True
        return False


# ── Conversion to a Student ────────────────────────────────────────

def convert_to_student(applicant_id: str) -> tuple[Applicant, str]:
    """Create a `students` row from the applicant. Returns the updated
    applicant and the new student_id.

    Requires:
      - status is Offer Accepted (or already Enrolled — idempotent)
      - all three subject choices set and valid against the catalogue
      - email present (the students table uses it as a unique key)
    """
    init_db()
    a = get_applicant(applicant_id)
    if a is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    if a.is_enrolled:
        logger.info(
            "Applicant %s already enrolled as %s — no-op",
            applicant_id, a.converted_student_id)
        return a, a.converted_student_id  # type: ignore[return-value]
    if a.status not in ("Offer Accepted", "Enrolled"):
        raise ValidationError(
            "Applicant must be in 'Offer Accepted' status to convert "
            "(current: " + a.status + ")")
    if not (a.subject_1 and a.subject_2 and a.subject_3):
        raise ValidationError(
            "All three A-Level subjects must be set on the applicant "
            "before conversion")
    if not a.email:
        raise ValidationError(
            "Applicant must have an email address to convert to a "
            "student record")

    from education_system.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    student = _students.create_student({
        "first_name":               a.first_name,
        "last_name":                a.last_name,
        "phone":                    a.phone,
        "email":                    a.email,
        "subject_1":                a.subject_1,
        "subject_2":                a.subject_2,
        "subject_3":                a.subject_3,
    })

    updated = update_applicant(applicant_id, {
        "status": "Enrolled",
        "converted_student_id": student.student_id,
        "decision_date": _dt.date.today().isoformat(),
    })
    logger.info("Converted applicant %s → student %s",
                applicant_id, student.student_id)
    return updated, student.student_id


# ── Summary ───────────────────────────────────────────────────────

def summary(*, upcoming_window_days: int = 14) -> Summary:
    init_db()
    today = _dt.date.today().isoformat()
    horizon = (_dt.date.today()
                + _dt.timedelta(days=upcoming_window_days)).isoformat()

    rows = list_applicants()
    by_status = {s: 0 for s in STATUSES}
    by_source = {s: 0 for s in SOURCES}
    upcoming_interviews = 0
    for a in rows:
        by_status[a.status] = by_status.get(a.status, 0) + 1
        by_source[a.application_source] = by_source.get(
            a.application_source, 0) + 1
        if a.interview_date and today <= a.interview_date <= horizon:
            upcoming_interviews += 1

    open_count = sum(by_status.get(s, 0) for s in OPEN_STATUSES)
    awaiting = (by_status.get("Under Review", 0)
                 + by_status.get("Interviewed", 0))
    pending_offers = by_status.get("Offer Made", 0)
    converted = by_status.get("Enrolled", 0)
    rejected = by_status.get("Rejected", 0)

    return Summary(
        total=len(rows),
        by_status=by_status,
        by_source=by_source,
        open_count=open_count,
        awaiting_decision=awaiting,
        pending_offers=pending_offers,
        converted=converted,
        rejected=rejected,
        upcoming_interviews=upcoming_interviews,
    )
