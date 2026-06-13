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

REFERENCE_STATUSES: tuple[str, ...] = (
    "Not requested", "Requested", "Received", "Declined",
)
DEFAULT_REFERENCE_STATUS: str = "Not requested"

# Document categories an applicant file can hold.
DOCUMENT_TYPES: tuple[str, ...] = (
    "Personal Statement", "Reference Letter", "Transcript",
    "Photo", "Other",
)
# Interview scorecard dimensions (each rated 1–5).
SCORE_DIMENSIONS: tuple[str, ...] = (
    "motivation", "subject_fit", "attainment",
)
RECOMMENDATIONS: tuple[str, ...] = (
    "Strong offer", "Offer", "Borderline", "Reject",
)

# Standardised decision reason codes (item 33) feeding reporting.
DECISION_REASONS: tuple[str, ...] = (
    "Meets entry criteria",
    "Strong interview",
    "Insufficient predicted grades",
    "Subject combination unavailable",
    "Incomplete application",
    "Better suited to another pathway",
    "Withdrawn by applicant",
    "Capacity reached",
    "Other",
)

# Fields that must be present (non-blank) for a complete applicant record.
# Ordered so the "missing fields" message reads top-to-bottom of the form.
REQUIRED_FIELDS: tuple[tuple[str, str], ...] = (
    ("first_name",         "First name"),
    ("last_name",          "Last name"),
    ("dob",                "Date of birth"),
    ("email",              "Email"),
    ("phone",              "Phone"),
    ("predicted_gcses",    "Predicted GCSEs"),
    ("subject_1",          "Subject 1"),
    ("subject_2",          "Subject 2"),
    ("subject_3",          "Subject 3"),
    ("application_source", "Application source"),
    ("submitted_at",       "Submitted date"),
)

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
    reference_status      TEXT NOT NULL DEFAULT 'Not requested',
    created_at            TEXT DEFAULT (datetime('now')),
    updated_at            TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_adm_status     ON admissions_applicants(status);
CREATE INDEX IF NOT EXISTS idx_adm_submitted  ON admissions_applicants(submitted_at);
CREATE INDEX IF NOT EXISTS idx_adm_last_name  ON admissions_applicants(last_name);
CREATE INDEX IF NOT EXISTS idx_adm_email      ON admissions_applicants(email);

-- Append-only activity log powering the applicant timeline.
CREATE TABLE IF NOT EXISTS admissions_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_id  TEXT NOT NULL,
    at            TEXT NOT NULL DEFAULT (datetime('now')),
    kind          TEXT NOT NULL DEFAULT 'event',
    detail        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_adm_evt_aid ON admissions_events(applicant_id);

-- Threaded notes (timestamped + attributed), distinct from the freeform
-- single `notes` column on the applicant row.
CREATE TABLE IF NOT EXISTS admissions_notes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_id  TEXT NOT NULL,
    at            TEXT NOT NULL DEFAULT (datetime('now')),
    author        TEXT,
    body          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_adm_note_aid ON admissions_notes(applicant_id);

-- Attached documents (copied into a managed folder; path stored here).
CREATE TABLE IF NOT EXISTS admissions_documents (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_id  TEXT NOT NULL,
    doc_type      TEXT NOT NULL DEFAULT 'Other',
    label         TEXT,
    path          TEXT NOT NULL,
    added_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_adm_doc_aid ON admissions_documents(applicant_id);

-- One interview scorecard per applicant (latest wins; upserted).
CREATE TABLE IF NOT EXISTS admissions_interview_scores (
    applicant_id    TEXT PRIMARY KEY,
    motivation      INTEGER,
    subject_fit     INTEGER,
    attainment      INTEGER,
    recommendation  TEXT,
    scored_by       TEXT,
    comments        TEXT,
    at              TEXT NOT NULL DEFAULT (datetime('now'))
);
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
    reference_status: str = DEFAULT_REFERENCE_STATUS
    offer_expiry: str | None = None
    waitlist_rank: int | None = None
    decision_reason: str | None = None
    follow_up: bool = False

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
class Event:
    id: int
    applicant_id: str
    at: str
    kind: str
    detail: str


@dataclass
class Note:
    id: int
    applicant_id: str
    at: str
    author: str | None
    body: str


@dataclass
class Document:
    id: int
    applicant_id: str
    doc_type: str
    label: str | None
    path: str
    added_at: str


@dataclass
class InterviewScore:
    applicant_id: str
    motivation: int | None
    subject_fit: int | None
    attainment: int | None
    recommendation: str | None
    scored_by: str | None
    comments: str | None
    at: str

    @property
    def average(self) -> float | None:
        vals = [v for v in (self.motivation, self.subject_fit,
                            self.attainment) if v is not None]
        return round(sum(vals) / len(vals), 1) if vals else None


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
        _migrate(conn)
    logger.debug("Admissions schema ready at %s", DB_PATH)

    _DB_READY = True


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns introduced after the original schema (idempotent)."""
    cols = {r["name"] for r in conn.execute(
        "PRAGMA table_info(admissions_applicants)").fetchall()}
    additions = {
        "reference_status": "TEXT NOT NULL DEFAULT 'Not requested'",
        "offer_expiry":     "TEXT",
        "waitlist_rank":    "INTEGER",
        "decision_reason":  "TEXT",
        "follow_up":        "INTEGER NOT NULL DEFAULT 0",
    }
    changed = False
    for name, ddl in additions.items():
        if name not in cols:
            conn.execute(
                f"ALTER TABLE admissions_applicants ADD COLUMN {name} {ddl}")
            changed = True
    if changed:
        conn.commit()


def _documents_dir() -> "Path":
    from pathlib import Path
    d = Path(DB_PATH).parent / "admissions_documents"
    d.mkdir(parents=True, exist_ok=True)
    return d


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
        reference_status=(r["reference_status"]
                          if "reference_status" in r.keys()
                          else DEFAULT_REFERENCE_STATUS),
        offer_expiry=(r["offer_expiry"]
                      if "offer_expiry" in r.keys() else None),
        waitlist_rank=(r["waitlist_rank"]
                       if "waitlist_rank" in r.keys() else None),
        decision_reason=(r["decision_reason"]
                         if "decision_reason" in r.keys() else None),
        follow_up=bool(r["follow_up"])
        if "follow_up" in r.keys() else False,
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _is_blank(value: Any) -> bool:
    return value in (None, "") or (
        isinstance(value, str) and not value.strip())


def missing_required(payload: dict[str, Any]) -> list[str]:
    """Return the labels of every required field that is blank/missing.

    Returns all of them at once (not just the first) so callers can show a
    complete list rather than making the user fix fields one at a time.
    """
    missing: list[str] = []
    for key, label in REQUIRED_FIELDS:
        if _is_blank(payload.get(key)):
            missing.append(label)
    return missing


def require_complete(payload: dict[str, Any]) -> None:
    """Raise ValidationError listing every missing required field."""
    missing = missing_required(payload)
    if missing:
        raise ValidationError(
            "Missing required field(s): " + ", ".join(missing))


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
    require_complete(payload)
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
        _log_event(conn, aid,
                   f"Application created (source: {p['application_source']}, "
                   f"status: {p['status']})", kind="create")
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
        for detail in _describe_changes(existing, p):
            _log_event(conn, applicant_id, detail, kind="update")
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


# ── Activity timeline ─────────────────────────────────────────────

def _log_event(conn: sqlite3.Connection, applicant_id: str,
                detail: str, *, kind: str = "event") -> None:
    """Append a timeline event. Uses the caller's open connection."""
    conn.execute(
        "INSERT INTO admissions_events (applicant_id, kind, detail) "
        "VALUES (?, ?, ?)", (applicant_id, kind, detail))


def _describe_changes(existing: Applicant, p: dict[str, Any]) -> list[str]:
    """Human-readable summary of notable field changes for the timeline."""
    out: list[str] = []
    if p["status"] != existing.status:
        out.append(f"Status: {existing.status} → {p['status']}")
    if p["offer_type"] != existing.offer_type and p["offer_type"]:
        cond = f" ({p['offer_conditions']})" if p["offer_conditions"] else ""
        out.append(f"Offer: {p['offer_type']}{cond}")
    if p["interview_date"] != existing.interview_date and p["interview_date"]:
        who = f" with {p['interviewer']}" if p["interviewer"] else ""
        out.append(f"Interview set for {p['interview_date']}{who}")
    if (p["converted_student_id"] != existing.converted_student_id
            and p["converted_student_id"]):
        out.append(f"Enrolled as student {p['converted_student_id']}")
    return out


def list_events(applicant_id: str) -> list[Event]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM admissions_events WHERE applicant_id = ? "
            "ORDER BY at DESC, id DESC", (applicant_id,)).fetchall()
    return [Event(id=r["id"], applicant_id=r["applicant_id"],
                  at=r["at"], kind=r["kind"], detail=r["detail"])
            for r in rows]


# ── Threaded notes ────────────────────────────────────────────────

def add_note(applicant_id: str, body: str, *,
              author: str | None = None) -> Note:
    init_db()
    body = (body or "").strip()
    if not body:
        raise ValidationError("Note body is required")
    if get_applicant(applicant_id) is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO admissions_notes (applicant_id, author, body) "
            "VALUES (?, ?, ?)", (applicant_id, author or None, body))
        _log_event(conn, applicant_id,
                   f"Note added by {author or 'unknown'}", kind="note")
        conn.commit()
        nid = cur.lastrowid
        r = conn.execute("SELECT * FROM admissions_notes WHERE id = ?",
                          (nid,)).fetchone()
    return Note(id=r["id"], applicant_id=r["applicant_id"], at=r["at"],
                author=r["author"], body=r["body"])


def list_notes(applicant_id: str) -> list[Note]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM admissions_notes WHERE applicant_id = ? "
            "ORDER BY at DESC, id DESC", (applicant_id,)).fetchall()
    return [Note(id=r["id"], applicant_id=r["applicant_id"], at=r["at"],
                 author=r["author"], body=r["body"]) for r in rows]


# ── Documents ─────────────────────────────────────────────────────

def add_document(applicant_id: str, source_path: str, *,
                  doc_type: str = "Other",
                  label: str | None = None) -> Document:
    """Copy ``source_path`` into the managed documents folder and record it."""
    import shutil
    from pathlib import Path
    init_db()
    if get_applicant(applicant_id) is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    if doc_type not in DOCUMENT_TYPES:
        raise ValidationError(
            f"Document type must be one of: {', '.join(DOCUMENT_TYPES)}")
    src = Path(source_path)
    if not src.is_file():
        raise ValidationError(f"File not found: {source_path}")
    dest_dir = _documents_dir() / applicant_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{secrets.randbelow(1_000_000):06d}_{src.name}"
    shutil.copy2(src, dest)
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO admissions_documents "
            "(applicant_id, doc_type, label, path) VALUES (?, ?, ?, ?)",
            (applicant_id, doc_type, label or src.name, str(dest)))
        _log_event(conn, applicant_id,
                   f"Document attached: {doc_type} — {label or src.name}",
                   kind="document")
        conn.commit()
        did = cur.lastrowid
        r = conn.execute("SELECT * FROM admissions_documents WHERE id = ?",
                          (did,)).fetchone()
    return Document(id=r["id"], applicant_id=r["applicant_id"],
                    doc_type=r["doc_type"], label=r["label"],
                    path=r["path"], added_at=r["added_at"])


def list_documents(applicant_id: str) -> list[Document]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM admissions_documents WHERE applicant_id = ? "
            "ORDER BY added_at DESC, id DESC", (applicant_id,)).fetchall()
    return [Document(id=r["id"], applicant_id=r["applicant_id"],
                     doc_type=r["doc_type"], label=r["label"],
                     path=r["path"], added_at=r["added_at"]) for r in rows]


def get_photo(applicant_id: str) -> Document | None:
    """Most recently added 'Photo' document, if any."""
    return next((d for d in list_documents(applicant_id)
                 if d.doc_type == "Photo"), None)


def remove_document(doc_id: int) -> bool:
    init_db()
    from pathlib import Path
    with _connect() as conn:
        r = conn.execute("SELECT * FROM admissions_documents WHERE id = ?",
                          (doc_id,)).fetchone()
        if r is None:
            return False
        try:
            Path(r["path"]).unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not delete document file %s", r["path"])
        conn.execute("DELETE FROM admissions_documents WHERE id = ?",
                      (doc_id,))
        _log_event(conn, r["applicant_id"],
                   f"Document removed: {r['label'] or r['doc_type']}",
                   kind="document")
        conn.commit()
    return True


# ── References ────────────────────────────────────────────────────

def set_reference_status(applicant_id: str, status: str) -> Applicant:
    init_db()
    if status not in REFERENCE_STATUSES:
        raise ValidationError(
            f"Reference status must be one of: "
            f"{', '.join(REFERENCE_STATUSES)}")
    existing = get_applicant(applicant_id)
    if existing is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    with _connect() as conn:
        conn.execute(
            "UPDATE admissions_applicants SET reference_status = ?, "
            "updated_at = datetime('now') WHERE applicant_id = ?",
            (status, applicant_id))
        if status != existing.reference_status:
            _log_event(conn, applicant_id,
                       f"Reference: {existing.reference_status} → {status}",
                       kind="reference")
        conn.commit()
    out = get_applicant(applicant_id)
    assert out is not None
    return out


# ── Interview scorecard ───────────────────────────────────────────

def _validate_score(value: Any, label: str) -> int | None:
    if value in (None, ""):
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a whole number 1–5") from None
    if not 1 <= n <= 5:
        raise ValidationError(f"{label} must be between 1 and 5")
    return n


def save_interview_score(applicant_id: str, *,
                          motivation: Any = None,
                          subject_fit: Any = None,
                          attainment: Any = None,
                          recommendation: str | None = None,
                          scored_by: str | None = None,
                          comments: str | None = None) -> InterviewScore:
    init_db()
    if get_applicant(applicant_id) is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    m = _validate_score(motivation, "Motivation")
    sf = _validate_score(subject_fit, "Subject fit")
    at_ = _validate_score(attainment, "Attainment")
    if recommendation and recommendation not in RECOMMENDATIONS:
        raise ValidationError(
            f"Recommendation must be one of: {', '.join(RECOMMENDATIONS)}")
    with _connect() as conn:
        conn.execute(
            """INSERT INTO admissions_interview_scores
                   (applicant_id, motivation, subject_fit, attainment,
                    recommendation, scored_by, comments, at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(applicant_id) DO UPDATE SET
                   motivation=excluded.motivation,
                   subject_fit=excluded.subject_fit,
                   attainment=excluded.attainment,
                   recommendation=excluded.recommendation,
                   scored_by=excluded.scored_by,
                   comments=excluded.comments,
                   at=excluded.at""",
            (applicant_id, m, sf, at_, recommendation or None,
             scored_by or None, (comments or "").strip() or None))
        _log_event(conn, applicant_id,
                   f"Interview scored (rec: {recommendation or '—'})",
                   kind="interview")
        conn.commit()
    out = get_interview_score(applicant_id)
    assert out is not None
    return out


def get_interview_score(applicant_id: str) -> InterviewScore | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM admissions_interview_scores WHERE applicant_id = ?",
            (applicant_id,)).fetchone()
    if r is None:
        return None
    return InterviewScore(
        applicant_id=r["applicant_id"], motivation=r["motivation"],
        subject_fit=r["subject_fit"], attainment=r["attainment"],
        recommendation=r["recommendation"], scored_by=r["scored_by"],
        comments=r["comments"], at=r["at"])


# ── Duplicate detection ───────────────────────────────────────────

def find_duplicates(*, email: str | None = None,
                     first_name: str | None = None,
                     last_name: str | None = None,
                     dob: str | None = None,
                     exclude_id: str | None = None) -> list[Applicant]:
    """Potential duplicates: same email, or same name + date of birth."""
    init_db()
    matches: dict[str, Applicant] = {}
    with _connect() as conn:
        if email and email.strip():
            for r in conn.execute(
                    "SELECT * FROM admissions_applicants "
                    "WHERE email = ? COLLATE NOCASE", (email.strip(),)):
                matches[r["applicant_id"]] = _row(r)
        if first_name and last_name and dob:
            for r in conn.execute(
                    "SELECT * FROM admissions_applicants WHERE "
                    "first_name = ? COLLATE NOCASE AND "
                    "last_name = ? COLLATE NOCASE AND dob = ?",
                    (first_name.strip(), last_name.strip(), dob.strip())):
                matches[r["applicant_id"]] = _row(r)
    if exclude_id:
        matches.pop(exclude_id, None)
    return list(matches.values())


# ── Lightweight column setters (preserved across update_applicant) ──

_EXTRA_COLS = ("offer_expiry", "waitlist_rank", "decision_reason",
               "follow_up")


def _set_extra(applicant_id: str, *, event: str | None = None,
                event_kind: str = "update", **fields: Any) -> Applicant:
    init_db()
    bad = set(fields) - set(_EXTRA_COLS)
    if bad:
        raise ValidationError(f"Unknown column(s): {', '.join(bad)}")
    if get_applicant(applicant_id) is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    sets = ", ".join(f"{k} = ?" for k in fields)
    with _connect() as conn:
        conn.execute(
            f"UPDATE admissions_applicants SET {sets}, "
            "updated_at = datetime('now') WHERE applicant_id = ?",
            (*fields.values(), applicant_id))
        if event:
            _log_event(conn, applicant_id, event, kind=event_kind)
        conn.commit()
    out = get_applicant(applicant_id)
    assert out is not None
    return out


# ── Interview lifecycle (items 26, 27) ────────────────────────────

def reschedule_interview(applicant_id: str, *, new_date: str,
                          reason: str | None = None,
                          interviewer: str | None = None) -> Applicant:
    a = get_applicant(applicant_id)
    if a is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    new_date = _validate_date(new_date, "Interview date", required=True)
    payload: dict[str, Any] = {"interview_date": new_date,
                               "status": "Interview Scheduled"}
    if interviewer is not None:
        payload["interviewer"] = interviewer
    updated = update_applicant(applicant_id, payload)
    with _connect() as conn:
        _log_event(conn, applicant_id,
                   f"Interview rescheduled {a.interview_date or '—'} → "
                   f"{new_date}" + (f" ({reason})" if reason else ""),
                   kind="interview")
        conn.commit()
    return updated


def cancel_interview(applicant_id: str, *,
                      reason: str | None = None) -> Applicant:
    a = get_applicant(applicant_id)
    if a is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    updated = update_applicant(applicant_id, {
        "interview_date": None, "interviewer": None,
        "status": "Under Review"})
    with _connect() as conn:
        _log_event(conn, applicant_id,
                   "Interview cancelled"
                   + (f" ({reason})" if reason else ""), kind="interview")
        conn.commit()
    return updated


def mark_no_show(applicant_id: str, *, follow_up: bool = True) -> Applicant:
    a = get_applicant(applicant_id)
    if a is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    with _connect() as conn:
        conn.execute(
            "UPDATE admissions_applicants SET follow_up = ?, "
            "updated_at = datetime('now') WHERE applicant_id = ?",
            (1 if follow_up else 0, applicant_id))
        _log_event(conn, applicant_id,
                   "Interview no-show recorded"
                   + (" — follow-up flagged" if follow_up else ""),
                   kind="interview")
        conn.commit()
    out = get_applicant(applicant_id)
    assert out is not None
    return out


def set_follow_up(applicant_id: str, flag: bool) -> Applicant:
    return _set_extra(applicant_id, follow_up=1 if flag else 0,
                       event=("Follow-up flagged" if flag
                              else "Follow-up cleared"))


def interview_to_ics(applicant_id: str) -> str:
    """Minimal all-day VCALENDAR for the applicant's interview."""
    a = get_applicant(applicant_id)
    if a is None or not a.interview_date:
        raise ValidationError("Applicant has no scheduled interview")
    dt = a.interview_date.replace("-", "")
    nxt = (_dt.date.fromisoformat(a.interview_date)
           + _dt.timedelta(days=1)).isoformat().replace("-", "")
    return (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
        "PRODID:-//SixthForm//Admissions//EN\r\nBEGIN:VEVENT\r\n"
        f"UID:interview-{a.applicant_id}@sixthform\r\n"
        f"DTSTART;VALUE=DATE:{dt}\r\nDTEND;VALUE=DATE:{nxt}\r\n"
        f"SUMMARY:Sixth-form interview — {a.full_name}\r\n"
        f"DESCRIPTION:Applicant {a.applicant_id}. Interviewer: "
        f"{a.interviewer or 'TBC'}. Subjects: "
        f"{', '.join(a.subjects) or 'TBC'}.\r\n"
        "END:VEVENT\r\nEND:VCALENDAR\r\n")


# ── Offers (items 29–33) ──────────────────────────────────────────

def set_offer_expiry(applicant_id: str, expiry: str | None) -> Applicant:
    expiry = _validate_date(expiry, "Offer expiry") if expiry else None
    return _set_extra(applicant_id, offer_expiry=expiry,
                       event=(f"Offer expiry set to {expiry}" if expiry
                              else "Offer expiry cleared"), event_kind="offer")


def list_expiring_offers(*, within_days: int = 7) -> list[Applicant]:
    today = _dt.date.today()
    horizon = (today + _dt.timedelta(days=within_days)).isoformat()
    return [a for a in list_applicants()
            if a.status == "Offer Made" and a.offer_expiry
            and a.offer_expiry <= horizon]


def render_offer_letter(applicant_id: str) -> str:
    a = get_applicant(applicant_id)
    if a is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    today = _dt.date.today().isoformat()
    cond = a.offer_conditions or "(no specific conditions)"
    kind = a.offer_type or "Conditional"
    body = [
        f"Date: {today}",
        f"Our ref: {a.applicant_id}",
        "",
        f"Dear {a.first_name} {a.last_name},",
        "",
        f"Following the review of your application, we are pleased to make "
        f"you a {kind.lower()} offer of a place in our Sixth Form to study:",
        "  " + (", ".join(a.subjects) if a.subjects else "(subjects TBC)"),
        "",
        f"Conditions of offer: {cond}",
    ]
    if a.offer_expiry:
        body.append(f"This offer must be accepted by {a.offer_expiry}.")
    body += [
        "",
        "We look forward to welcoming you.",
        "",
        "Yours sincerely,",
        "Admissions Team",
    ]
    return "\n".join(body)


def render_status_email(applicant_id: str) -> tuple[str, str]:
    """Return (subject, body) acknowledgement/decision email text."""
    a = get_applicant(applicant_id)
    if a is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    name = a.first_name
    s = a.status
    if s == "Offer Made":
        sub = "Your Sixth Form offer"
        msg = (f"Dear {name},\n\nWe are delighted to offer you a place. "
               f"Conditions: {a.offer_conditions or 'none'}.")
        if a.offer_expiry:
            msg += f"\nPlease respond by {a.offer_expiry}."
    elif s == "Rejected":
        sub = "Your Sixth Form application"
        msg = (f"Dear {name},\n\nThank you for applying. On this occasion "
               f"we are unable to offer you a place.")
        if a.decision_reason:
            msg += f"\nReason: {a.decision_reason}."
    elif s == "Interview Scheduled":
        sub = "Your Sixth Form interview"
        msg = (f"Dear {name},\n\nYour interview is scheduled for "
               f"{a.interview_date} with {a.interviewer or 'our team'}.")
    elif s in ("Offer Accepted", "Enrolled"):
        sub = "Welcome to Sixth Form"
        msg = (f"Dear {name},\n\nThank you for accepting your place. "
               f"We look forward to seeing you.")
    else:
        sub = "Your Sixth Form application — update"
        msg = (f"Dear {name},\n\nYour application status is now: {s}.")
    return sub, msg + "\n\nKind regards,\nAdmissions Team"


# ── Waitlist (item 34) ────────────────────────────────────────────

def set_waitlist_rank(applicant_id: str, rank: int | None) -> Applicant:
    if rank is not None and rank < 1:
        raise ValidationError("Waitlist rank must be 1 or greater")
    return _set_extra(applicant_id, waitlist_rank=rank,
                       event=(f"Waitlist rank set to {rank}" if rank
                              else "Removed from waitlist ordering"))


def get_waitlist() -> list[Applicant]:
    rows = [a for a in list_applicants() if a.status == "Waitlisted"]
    rows.sort(key=lambda a: (a.waitlist_rank is None,
                              a.waitlist_rank or 0, a.submitted_at))
    return rows


def move_waitlist(applicant_id: str, direction: int) -> list[Applicant]:
    """Swap an applicant up (-1) or down (+1) the waitlist ordering."""
    wl = get_waitlist()
    ids = [a.applicant_id for a in wl]
    if applicant_id not in ids:
        raise ValidationError("Applicant is not on the waitlist")
    i = ids.index(applicant_id)
    j = i + direction
    if not 0 <= j < len(ids):
        return wl
    ids[i], ids[j] = ids[j], ids[i]
    for rank, aid in enumerate(ids, start=1):
        _set_extra(aid, waitlist_rank=rank)
    return get_waitlist()


# ── Decision reason (item 33) integrated helper ───────────────────

def record_decision(applicant_id: str, status: str, *,
                     reason: str | None = None,
                     decided_by: str | None = None,
                     notes: str | None = None) -> Applicant:
    if reason and reason not in DECISION_REASONS:
        raise ValidationError(
            f"Reason must be one of: {', '.join(DECISION_REASONS)}")
    out = set_status(applicant_id, status, decision_by=decided_by,
                     decision_notes=notes)
    if reason is not None:
        out = _set_extra(applicant_id, decision_reason=reason)
    return out


# ── Conversion gate (items 37, 40) ────────────────────────────────

def pre_conversion_check(applicant_id: str) -> list[str]:
    """Return a list of blocking issues; empty means ready to enrol."""
    a = get_applicant(applicant_id)
    if a is None:
        return ["Applicant not found"]
    issues: list[str] = []
    if a.status not in ("Offer Accepted", "Enrolled"):
        issues.append(f"Status is '{a.status}', not 'Offer Accepted'")
    if not (a.subject_1 and a.subject_2 and a.subject_3):
        issues.append("Fewer than three A-Level subjects selected")
    if not a.email:
        issues.append("No email address on file")
    if a.offer_expiry and a.offer_expiry < _dt.date.today().isoformat() \
            and not a.is_enrolled:
        issues.append(f"Offer expired on {a.offer_expiry}")
    return issues


# ── GCSE-vs-conditions heuristic (item 14) ────────────────────────

_GRADE_RE = re.compile(r"\b([1-9])\b")


def gcse_concern(predicted: str | None,
                  conditions: str | None) -> str | None:
    """Best-effort flag when predicted GCSEs look below offer conditions.

    Extracts the highest single-digit grade required in the conditions and
    checks the predicted grades clear it. Returns a warning string, or None
    when nothing obvious is amiss / unparseable.
    """
    if not predicted or not conditions:
        return None
    req = [int(g) for g in _GRADE_RE.findall(conditions)]
    pred = [int(g) for g in _GRADE_RE.findall(predicted)]
    if not req or not pred:
        return None
    needed = max(req)
    below = sorted(g for g in pred if g < needed)
    if below:
        return (f"Predicted grades include {below} below the highest "
                f"required grade ({needed}) in the offer conditions.")
    return None


# ── Analytics (items 41–45) ───────────────────────────────────────

_HAPPY_PATH: tuple[str, ...] = (
    "Submitted", "Under Review", "Interview Scheduled",
    "Interviewed", "Offer Made", "Offer Accepted", "Enrolled",
)


def funnel() -> list[tuple[str, int]]:
    """Count applicants who *reached* each happy-path stage, using the
    transition events plus current status (monotonic)."""
    init_db()
    idx = {s: i for i, s in enumerate(_HAPPY_PATH)}
    reached_counts = [0] * len(_HAPPY_PATH)
    with _connect() as conn:
        events_by = {}
        for e in conn.execute(
                "SELECT applicant_id, detail FROM admissions_events "
                "WHERE detail LIKE 'Status:%'"):
            events_by.setdefault(e["applicant_id"], []).append(e["detail"])
    for a in list_applicants():
        max_i = idx.get(a.status, -1)
        for detail in events_by.get(a.applicant_id, []):
            tgt = detail.split("→")[-1].strip()
            if tgt in idx:
                max_i = max(max_i, idx[tgt])
        # Everyone was at least Submitted.
        max_i = max(max_i, 0)
        for i in range(max_i + 1):
            reached_counts[i] += 1
    return list(zip(_HAPPY_PATH, reached_counts))


def source_effectiveness() -> list[dict[str, Any]]:
    rows = list_applicants()
    out = []
    for src in SOURCES:
        sub = [a for a in rows if a.application_source == src]
        if not sub:
            continue
        enrolled = sum(1 for a in sub if a.status == "Enrolled")
        offers = sum(1 for a in sub if a.status in (
            "Offer Made", "Offer Accepted", "Offer Declined", "Enrolled"))
        out.append({
            "source": src, "total": len(sub), "offers": offers,
            "enrolled": enrolled,
            "conversion": round(100 * enrolled / len(sub), 1),
        })
    return sorted(out, key=lambda d: -d["conversion"])


def time_to_decision_stats() -> dict[str, Any]:
    days = []
    for a in list_applicants():
        if a.decision_date and a.submitted_at:
            d0 = _try_date(a.submitted_at)
            d1 = _try_date(a.decision_date)
            if d0 and d1 and d1 >= d0:
                days.append((d1 - d0).days)
    if not days:
        return {"count": 0, "avg": None, "median": None,
                "min": None, "max": None}
    days.sort()
    n = len(days)
    median = (days[n // 2] if n % 2 else
              (days[n // 2 - 1] + days[n // 2]) / 2)
    return {"count": n, "avg": round(sum(days) / n, 1),
            "median": median, "min": days[0], "max": days[-1]}


def applications_by_week() -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for a in list_applicants():
        d = _try_date(a.submitted_at)
        if d is None:
            continue
        iso = d.isocalendar()
        key = f"{iso[0]}-W{iso[1]:02d}"
        counts[key] = counts.get(key, 0) + 1
    return sorted(counts.items())


def subject_demand() -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for a in list_applicants():
        for s in a.subjects:
            counts[s] = counts.get(s, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def _try_date(value: str | None) -> "_dt.date | None":
    if not value:
        return None
    try:
        return _dt.date.fromisoformat(value[:10])
    except ValueError:
        return None


# ── CSV import / export (items 47, 48) ────────────────────────────

_CSV_FIELDS = (
    "applicant_id", "first_name", "last_name", "dob", "email", "phone",
    "address", "previous_school", "predicted_gcses",
    "subject_1", "subject_2", "subject_3", "reference_name",
    "reference_contact", "application_source", "submitted_at", "status",
    "offer_type", "offer_conditions", "interview_date", "interviewer",
    "decision_by", "decision_date", "decision_reason", "reference_status",
)


def export_csv(path: str, applicants: list[Applicant] | None = None) -> int:
    import csv
    rows = applicants if applicants is not None else list_applicants()
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=_CSV_FIELDS)
        w.writeheader()
        for a in rows:
            w.writerow({f: getattr(a, f, "") or "" for f in _CSV_FIELDS})
    logger.info("Exported %d applicants to %s", len(rows), path)
    return len(rows)


def import_csv(path: str) -> tuple[int, list[str]]:
    """Create applicants from a CSV. Returns (created_count, errors)."""
    import csv
    init_db()
    created, errors = 0, []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for i, row in enumerate(reader, start=2):
            try:
                payload = {k: (row.get(k) or "").strip()
                           for k in _CSV_FIELDS if k != "applicant_id"}
                if not payload.get("submitted_at"):
                    payload["submitted_at"] = _dt.date.today().isoformat()
                create_applicant(payload)
                created += 1
            except Exception as e:  # noqa: BLE001 — report per row
                errors.append(f"Row {i}: {e}")
    logger.info("Imported %d applicants from %s (%d errors)",
                created, path, len(errors))
    return created, errors


# ── GDPR export / erasure (item 50) ───────────────────────────────

def gdpr_export(applicant_id: str) -> dict[str, Any]:
    a = get_applicant(applicant_id)
    if a is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    from dataclasses import asdict
    score = get_interview_score(applicant_id)
    return {
        "applicant": asdict(a),
        "notes": [asdict(n) for n in list_notes(applicant_id)],
        "events": [asdict(e) for e in list_events(applicant_id)],
        "documents": [asdict(d) for d in list_documents(applicant_id)],
        "interview_score": asdict(score) if score else None,
    }


def erase_applicant(applicant_id: str) -> bool:
    """Hard-delete the applicant and ALL related records/files (GDPR)."""
    init_db()
    import shutil
    from pathlib import Path
    if get_applicant(applicant_id) is None:
        return False
    for d in list_documents(applicant_id):
        try:
            Path(d.path).unlink(missing_ok=True)
        except OSError:
            pass
    doc_dir = _documents_dir() / applicant_id
    if doc_dir.exists():
        shutil.rmtree(doc_dir, ignore_errors=True)
    with _connect() as conn:
        for tbl in ("admissions_events", "admissions_notes",
                     "admissions_documents", "admissions_interview_scores",
                     "admissions_applicants"):
            conn.execute(f"DELETE FROM {tbl} WHERE applicant_id = ?",
                          (applicant_id,))
        conn.commit()
    logger.info("GDPR erase: removed all data for %s", applicant_id)
    return True


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
