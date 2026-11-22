"""Admissions — pre-enrolment applicant pipeline for the Sixth Form System.

One row per applicant. Applicants progress through a status workflow:

    (Online - unverified →)   public web form; staff verify first
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
from education_system import paths
from education_system.systems.sixth_form.domain.admissions import (
    _guard,
    status_rules,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ADMISSIONS_DB

#: Status of an application that arrived through the public online form
#: (api/sixth_form/routes/applications_routes.py) and has not yet been
#: checked by staff. Verification moves it to "Submitted".
ONLINE_UNVERIFIED: str = "Online - unverified"

STATUSES: tuple[str, ...] = (
    ONLINE_UNVERIFIED,
    "Submitted",
    "Under Review",
    "Interview Scheduled",
    "Interviewed",
    "Offer Made",
    "Offer Accepted",
    "Deferred",
    "Offer Declined",
    "Waitlisted",
    "Rejected",
    "Withdrawn",
    "Enrolled",
)
DEFAULT_STATUS: str = "Submitted"
#: Statuses a new application may start in (anything later is reached
#: through the workflow so each decision is recorded).
INITIAL_STATUSES: tuple[str, ...] = (ONLINE_UNVERIFIED, "Submitted",
                                     "Under Review")
OPEN_STATUSES: tuple[str, ...] = (
    ONLINE_UNVERIFIED, "Submitted", "Under Review", "Interview Scheduled",
    "Interviewed", "Offer Made", "Waitlisted", "Deferred",
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
    "Offer conditions not met",
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
    # One choice is enough: a BTEC, T Level or two-A-level programme is a
    # complete application. "Subject 1" is also satisfied by a non-empty
    # ``programme_choices`` list (see missing_required).
    ("subject_1",          "Subject 1"),
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

-- Every qualification the applicant wants to study (any mix: A levels,
-- a fourth A level, BTEC, T Level, EPQ, Core Maths, GCSE resits). The
-- subject_1..3 columns mirror the first three A-level-type choices so
-- every older screen keeps working.
CREATE TABLE IF NOT EXISTS admissions_programme_choices (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_id        TEXT NOT NULL,
    qualification_type  TEXT NOT NULL,
    subject             TEXT NOT NULL,
    sort_order          INTEGER NOT NULL DEFAULT 0,
    notes               TEXT,
    UNIQUE (applicant_id, qualification_type, subject),
    FOREIGN KEY (applicant_id) REFERENCES admissions_applicants(applicant_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_adm_choice_aid
    ON admissions_programme_choices(applicant_id);

-- One row per converted applicant: what convert_to_student carried
-- across and the outcome of each step (enrolment, aims, prior
-- attainment, photo, onboarding), so nothing is lost silently.
CREATE TABLE IF NOT EXISTS admissions_conversions (
    applicant_id   TEXT PRIMARY KEY,
    student_id     TEXT NOT NULL,
    converted_at   TEXT NOT NULL DEFAULT (datetime('now')),
    converted_by   TEXT,
    academic_year  TEXT,
    enrolment_id   INTEGER,
    checklist_id   INTEGER,
    carried_json   TEXT,
    steps_json     TEXT,
    FOREIGN KEY (applicant_id) REFERENCES admissions_applicants(applicant_id)
        ON DELETE CASCADE
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
    uln: str | None = None
    upn: str | None = None
    # Profile, eligibility and lifecycle columns (see PROFILE_COLUMNS);
    # written by applicant_details / record_safety, never by the form.
    intake_year: str | None = None
    sex: str | None = None
    ethnicity: str | None = None
    nationality: str | None = None
    first_language: str | None = None
    residency_status: str | None = None
    lldd: bool = False
    ehcp: bool = False
    looked_after: bool = False
    care_leaver: bool = False
    young_carer: bool = False
    fsm_eligible: bool = False
    bursary_interest: bool = False
    guaranteed_place: bool = False
    consent_contact_school: bool = False
    parent_consent: bool = False
    withdrawal_reason: str | None = None
    deferred_from: str | None = None
    archived_at: str | None = None
    archived_by: str | None = None
    archive_reason: str | None = None
    merged_into: str | None = None
    converting_at: str | None = None

    @property
    def is_archived(self) -> bool:
        return bool(self.archived_at)

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
    actor: str | None = None


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
class ProgrammeChoice:
    id: int | None              # None = derived from the subject slots
    applicant_id: str
    qualification_type: str
    subject: str
    sort_order: int
    notes: str | None = None

    @property
    def label(self) -> str:
        return f"{self.qualification_type} {self.subject}"


@dataclass
class ConversionRecord:
    applicant_id: str
    student_id: str
    converted_at: str
    converted_by: str | None
    academic_year: str | None
    enrolment_id: int | None
    checklist_id: int | None
    carried: dict[str, Any]
    steps: list[dict[str, str]]


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
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        _migrate(conn)
    logger.debug("Admissions schema ready at %s", DB_PATH)

    _DB_READY = True


#: Columns added for the admissions cycle, ILR/safeguarding profile,
#: eligibility flags and record lifecycle. Flags are 0/1 integers.
PROFILE_COLUMNS: dict[str, str] = {
    "intake_year":            "TEXT",
    "sex":                    "TEXT",
    "ethnicity":              "TEXT",
    "nationality":            "TEXT",
    "first_language":         "TEXT",
    "residency_status":       "TEXT",
    "lldd":                   "INTEGER NOT NULL DEFAULT 0",
    "ehcp":                   "INTEGER NOT NULL DEFAULT 0",
    "looked_after":           "INTEGER NOT NULL DEFAULT 0",
    "care_leaver":            "INTEGER NOT NULL DEFAULT 0",
    "young_carer":            "INTEGER NOT NULL DEFAULT 0",
    "fsm_eligible":           "INTEGER NOT NULL DEFAULT 0",
    "bursary_interest":       "INTEGER NOT NULL DEFAULT 0",
    "guaranteed_place":       "INTEGER NOT NULL DEFAULT 0",
    "consent_contact_school": "INTEGER NOT NULL DEFAULT 0",
    "parent_consent":         "INTEGER NOT NULL DEFAULT 0",
    "withdrawal_reason":      "TEXT",
    "deferred_from":          "TEXT",
    "archived_at":            "TEXT",
    "archived_by":            "TEXT",
    "archive_reason":         "TEXT",
    "merged_into":            "TEXT",
    "converting_at":          "TEXT",
}
FLAG_COLUMNS: tuple[str, ...] = tuple(
    k for k, v in PROFILE_COLUMNS.items() if v.startswith("INTEGER"))


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
        # Learner identifiers carried through to the student record at
        # conversion (ULN) and used to match a Year 11 CTF (UPN).
        "uln":              "TEXT",
        "upn":              "TEXT",
        **PROFILE_COLUMNS,
    }
    changed = False
    for name, ddl in additions.items():
        if name not in cols:
            conn.execute(
                f"ALTER TABLE admissions_applicants ADD COLUMN {name} {ddl}")
            changed = True
    # Who did it: every timeline event is stamped with the signed-in user.
    evt_cols = {r["name"] for r in conn.execute(
        "PRAGMA table_info(admissions_events)").fetchall()}
    if "actor" not in evt_cols:
        conn.execute("ALTER TABLE admissions_events ADD COLUMN actor TEXT")
        changed = True
    conn.execute("CREATE INDEX IF NOT EXISTS idx_adm_intake "
                 "ON admissions_applicants(intake_year)")
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
        uln=r["uln"] if "uln" in r.keys() else None,
        upn=r["upn"] if "upn" in r.keys() else None,
        **{k: (bool(r[k]) if k in FLAG_COLUMNS else r[k])
           for k in PROFILE_COLUMNS if k in r.keys()},
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


class PossibleDuplicate(ValidationError):
    """The new application matches one already on file. ``matches`` holds
    them; pass ``allow_duplicate=True`` once a person has checked."""

    def __init__(self, matches: list["Applicant"]):
        self.matches = matches
        names = ", ".join(f"{m.applicant_id} {m.full_name} ({m.status})"
                          for m in matches[:5])
        super().__init__(f"Possible duplicate of: {names}")


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
        if key == "subject_1" and payload.get("programme_choices"):
            continue
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
        from education_system.systems.sixth_form.domain.academics.subjects import (
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

def default_intake_year(today: _dt.date | None = None) -> str:
    """The September intake a new application is for: applications made
    from September onwards are for next September; January–August ones
    are for this coming September. The admissions cycles set up in
    :mod:`cycles` take precedence where one is open."""
    d = today or _dt.date.today()
    try:
        from education_system.systems.sixth_form.domain.admissions import (
            cycles as _cycles,
        )
        open_cycle = _cycles.open_cycle_for(d)
        if open_cycle:
            return open_cycle
    except ImportError:
        pass
    y = d.year + 1 if d.month >= 9 else d.year
    return f"{y}/{str(y + 1)[-2:]}"

def create_applicant(payload: dict[str, Any], *,
                     allow_duplicate: bool = False,
                     incomplete_ok: bool = False) -> Applicant:
    """Create an application. It starts in one of
    :data:`INITIAL_STATUSES` (later statuses are reached through the
    workflow) and is checked against existing applicants first: a match on
    e-mail, or name + date of birth, raises :class:`PossibleDuplicate`
    unless ``allow_duplicate``.

    ``incomplete_ok`` skips the completeness check for a record that
    arrives from another system (e.g. a Year 11 handover from Secondary,
    which carries no contact details or subject choices yet); the gaps
    are filled in by admissions staff."""
    init_db()
    _guard.require("creating applications")
    if not incomplete_ok:
        require_complete(payload)
    p = _validate_payload(payload)
    if p["status"] not in INITIAL_STATUSES:
        raise ValidationError(
            "A new application starts as one of: "
            f"{', '.join(INITIAL_STATUSES)}")
    if p["converted_student_id"]:
        raise ValidationError(
            "A new application cannot be linked to a student; convert it.")
    if not allow_duplicate:
        dups = [d for d in find_duplicates(
            email=p["email"], first_name=p["first_name"],
            last_name=p["last_name"], dob=p["dob"]) if not d.is_archived]
        if dups:
            raise PossibleDuplicate(dups)
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
        intake = (payload.get("intake_year") or "").strip() or None
        if intake is None:
            intake = default_intake_year()
        conn.execute("UPDATE admissions_applicants SET intake_year = ? "
                     "WHERE applicant_id = ?", (intake, aid))
        conn.commit()
    if payload.get("programme_choices"):
        set_programme_choices(aid, payload["programme_choices"])
    out = get_applicant(aid)
    assert out is not None
    logger.info("Created applicant %s %s %s (source=%s, status=%s)",
                aid, p["first_name"], p["last_name"],
                p["application_source"], p["status"])
    return out


def get_applicant(applicant_id: str) -> Applicant | None:
    init_db()
    _guard.require("applicant records")
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
    intake_year: str | None = None,
    include_archived: bool = False,
) -> list[Applicant]:
    """Applicants matching the filters. Archived (and merged) records are
    left out unless ``include_archived``."""
    init_db()
    _guard.require("applicant records")
    clauses, args = [], []
    if not include_archived:
        clauses.append("archived_at IS NULL")
    if intake_year:
        clauses.append("intake_year = ?")
        args.append(intake_year.strip())
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
           "  WHEN 'Online - unverified' THEN -1 "
           "  WHEN 'Submitted'           THEN 0 "
           "  WHEN 'Under Review'        THEN 1 "
           "  WHEN 'Interview Scheduled' THEN 2 "
           "  WHEN 'Interviewed'         THEN 3 "
           "  WHEN 'Offer Made'          THEN 4 "
           "  WHEN 'Offer Accepted'      THEN 5 "
           "  WHEN 'Deferred'            THEN 5 "
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
    _guard.require("changing applications")
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
    try:
        status_rules.check(existing.status, p["status"])
    except status_rules.TransitionError as e:
        raise ValidationError(str(e)) from e
    if (p["converted_student_id"] != existing.converted_student_id
            and not status_rules.is_converting()):
        raise ValidationError(
            "The student link is set only by converting the applicant.")
    if existing.is_archived and not status_rules.is_converting():
        raise ValidationError(
            f"{applicant_id} is archived; restore it before changing it.")
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
    slots_before = [existing.subject_1, existing.subject_2, existing.subject_3]
    slots_after = [p["subject_1"], p["subject_2"], p["subject_3"]]
    if slots_before != slots_after:
        _reconcile_choices_with_slots(applicant_id, slots_after)
    out = get_applicant(applicant_id)
    assert out is not None
    if out.status != existing.status:
        # A pupil sent by a secondary school: tell the school's post-16
        # board (best effort; no-op for anyone else).
        from education_system.systems.sixth_form.domain.admissions import (
            secondary_handover,
        )
        secondary_handover.report_status(applicant_id, out.status)
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
    elif status in TERMINAL_STATUSES or status.startswith("Offer"):
        payload["decision_by"] = _guard.actor()
    if decision_notes is not None:
        payload["decision_notes"] = decision_notes
    return update_applicant(applicant_id, payload)


def reopen_application(applicant_id: str, *, reason: str) -> Applicant:
    """Reopen a declined, rejected or withdrawn application (to Under
    Review). Needs a reason, which goes on the timeline."""
    _guard.require("reopening applications")
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Give a reason for reopening the application.")
    a = get_applicant(applicant_id)
    if a is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    if a.status not in status_rules.REOPENABLE:
        raise ValidationError(
            f"Only a closed application can be reopened (this one is "
            f"{a.status}).")
    with status_rules.reopening():
        out = update_applicant(applicant_id,
                               {"status": status_rules.REOPEN_TO})
    with _connect() as conn:
        _log_event(conn, applicant_id, f"Application reopened: {reason}",
                   kind="status")
        conn.commit()
    return out


def allowed_statuses(applicant_id: str) -> tuple[str, ...]:
    """Statuses this applicant may be moved to next (for pickers)."""
    a = get_applicant(applicant_id)
    return status_rules.allowed_next(a.status) if a else ()


def _slots():
    from education_system.systems.sixth_form.domain.admissions import (
        interviews,
    )
    return interviews


def _future_date(value: Any, label: str) -> str:
    d = _validate_date(value, label, required=True)
    assert d is not None
    if d < _dt.date.today().isoformat():
        raise ValidationError(f"{label} {d} is in the past")
    return d


def schedule_interview(applicant_id: str, *,
                        interview_date: str | None = None,
                        interviewer: str | None = None,
                        slot_id: int | None = None) -> Applicant:
    """Schedule the applicant's interview.

    With ``slot_id`` the applicant is booked into that interview slot
    (:func:`interviews.book` — capacity, clash and double-booking checks)
    and the date / panel come from the slot. Without it a bare date is
    set; a past date is refused, and so is an applicant already booked
    into a slot (reschedule or cancel that booking instead).
    """
    interviews = _slots()
    if slot_id is not None and not interviews.driving():
        interviews.book(applicant_id, int(slot_id))
        out = get_applicant(applicant_id)
        assert out is not None
        return out
    interview_date = _future_date(interview_date, "Interview date")
    if not interviews.driving():
        b = interviews.active_booking(applicant_id)
        if b is not None:
            raise ValidationError(
                f"{applicant_id} is booked into interview slot "
                f"#{b.slot_id}; reschedule or cancel that booking instead")
    return update_applicant(applicant_id, {
        "interview_date": interview_date,
        "interviewer": interviewer,
        "status": "Interview Scheduled",
    })


def record_interview(applicant_id: str, *,
                      interview_notes: str | None = None) -> Applicant:
    """Record that the interview took place (the slot booking, if any,
    becomes Attended)."""
    out = update_applicant(applicant_id, {
        "interview_notes": interview_notes,
        "status": "Interviewed",
    })
    _slots().close_booking(applicant_id, "Attended")
    return out


def make_offer(applicant_id: str, *,
                offer_type: str = DEFAULT_OFFER_TYPE,
                conditions: str | None = None,
                decided_by: str | None = None,
                override_capacity: bool = False) -> Applicant:
    """Offer a place. A real offer (Conditional / Unconditional) is
    checked against the places set for each programme the applicant
    chose in their cycle (:mod:`capacity`): when one is full this raises
    ``capacity.CapacityFull`` unless ``override_capacity``, and an
    override is noted on the timeline. Where the cycle sets an offer
    response time and the applicant has no live expiry date, the offer
    expiry is set from it."""
    if offer_type not in OFFER_TYPES:
        raise ValidationError(
            f"Offer type must be one of: {', '.join(OFFER_TYPES)}")
    from education_system.systems.sixth_form.domain.admissions import (
        capacity as _capacity,
        cycles as _cycles,
    )
    full: list[str] = []
    if offer_type in ("Conditional", "Unconditional"):
        full = _capacity.check_offer_capacity(applicant_id)
        if full and not override_capacity:
            raise _capacity.CapacityFull(applicant_id, full)
    out = update_applicant(applicant_id, {
        "status": "Offer Made",
        "offer_type": offer_type,
        "offer_conditions": conditions,
        "decision_by": decided_by,
        "decision_date": _dt.date.today().isoformat(),
    })
    if full:
        with _connect() as conn:
            _log_event(conn, applicant_id,
                       "Capacity override: offer made although "
                       f"{', '.join(full)} {'is' if len(full) == 1 else 'are'}"
                       " full", kind="offer")
            conn.commit()
        logger.warning("Capacity override for %s by %s (%s)", applicant_id,
                       _guard.actor(), ", ".join(full))
    today = _dt.date.today()
    if not out.offer_expiry or out.offer_expiry < today.isoformat():
        days = _cycles.offer_response_days(out.intake_year)
        if days:
            out = set_offer_expiry(
                applicant_id, (today + _dt.timedelta(days=days)).isoformat())
    return out


def accept_offer(applicant_id: str) -> Applicant:
    return set_status(applicant_id, "Offer Accepted")


def decline_offer(applicant_id: str, *,
                  reason: str | None = None) -> Applicant:
    if reason and reason not in WITHDRAWAL_REASONS:
        raise ValidationError(
            f"Reason must be one of: {', '.join(WITHDRAWAL_REASONS)}")
    out = set_status(applicant_id, "Offer Declined")
    if reason:
        _set_profile(applicant_id, withdrawal_reason=reason,
                     event=f"Declined: {reason}")
        out = get_applicant(applicant_id) or out
    return out


def defer(applicant_id: str, *, to_intake: str,
          reason: str | None = None) -> Applicant:
    """Hold an offer over to a later intake year (status Deferred)."""
    a = get_applicant(applicant_id)
    if a is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    to_intake = (to_intake or "").strip()
    if not re.match(r"^\d{4}/\d{2}$", to_intake):
        raise ValidationError("Intake year must look like '2027/28'")
    if a.intake_year and to_intake <= a.intake_year:
        raise ValidationError("Defer to a later intake year.")
    out = set_status(applicant_id, "Deferred", decision_notes=reason)
    _set_profile(applicant_id, deferred_from=a.intake_year,
                 intake_year=to_intake,
                 event=f"Deferred from {a.intake_year or '—'} to {to_intake}"
                       + (f" ({reason})" if reason else ""))
    return get_applicant(applicant_id) or out


def _set_profile(applicant_id: str, *, event: str | None = None,
                 **fields: Any) -> None:
    """Write profile/lifecycle columns (see PROFILE_COLUMNS)."""
    bad = set(fields) - set(PROFILE_COLUMNS)
    if bad:
        raise ValidationError(f"Unknown column(s): {', '.join(sorted(bad))}")
    if not fields:
        return
    sets = ", ".join(f"{k} = ?" for k in fields)
    vals = [int(bool(v)) if k in FLAG_COLUMNS else v
            for k, v in fields.items()]
    with _connect() as conn:
        conn.execute(
            f"UPDATE admissions_applicants SET {sets}, "  # noqa: S608 — keys checked above
            "updated_at = datetime('now') WHERE applicant_id = ?",
            (*vals, applicant_id))
        if event:
            _log_event(conn, applicant_id, event, kind="update")
        conn.commit()


def reject(applicant_id: str, *, decided_by: str | None = None,
            notes: str | None = None) -> Applicant:
    return set_status(applicant_id, "Rejected",
                       decision_by=decided_by, decision_notes=notes)


#: Why an applicant withdrew or declined (reporting and ILR destinations).
WITHDRAWAL_REASONS: tuple[str, ...] = (
    "Accepted a place elsewhere (sixth form/college)",
    "Apprenticeship or employment",
    "Moved away",
    "Course not running / not offered",
    "Did not meet entry requirements",
    "Changed mind about subjects",
    "Personal or family reasons",
    "No response from applicant",
    "Other",
)


def withdraw(applicant_id: str, *, notes: str | None = None,
             reason: str | None = None) -> Applicant:
    if reason and reason not in WITHDRAWAL_REASONS:
        raise ValidationError(
            f"Reason must be one of: {', '.join(WITHDRAWAL_REASONS)}")
    out = set_status(applicant_id, "Withdrawn", decision_notes=notes)
    if reason:
        _set_profile(applicant_id, withdrawal_reason=reason,
                     event=f"Withdrawal reason: {reason}")
        out = get_applicant(applicant_id) or out
    return out


#: Statuses an applicant can be deleted outright from (nothing decided
#: yet). Anything further along is archived instead, so its history,
#: decisions and any student link survive.
DELETABLE_STATUSES: tuple[str, ...] = (ONLINE_UNVERIFIED, "Submitted")


class HasHistory(ValidationError):
    """Delete refused: the record has progressed; archive it instead."""


def delete_applicant(applicant_id: str) -> bool:
    """Delete an application entered by mistake.

    Only one that has not progressed (``DELETABLE_STATUSES``, never
    converted, no references/results/conversion) can be deleted; the
    rest raise :class:`HasHistory` — archive them with
    :func:`record_safety.archive_applicant`. Its notes, events,
    documents (and files), scores and choices go with it."""
    init_db()
    _guard.require("deleting applications")
    a = get_applicant(applicant_id)
    if a is None:
        return False
    from education_system.systems.sixth_form.domain.admissions import (
        record_safety,
    )
    blockers = record_safety.delete_blockers(a)
    if blockers:
        raise HasHistory(
            f"{applicant_id} cannot be deleted ({'; '.join(blockers)}). "
            "Archive it instead.")
    record_safety.purge_applicant_rows(applicant_id)
    logger.info("Deleted applicant %s (by %s)", applicant_id,
                _guard.actor())
    return True


# ── Activity timeline ─────────────────────────────────────────────

def _log_event(conn: sqlite3.Connection, applicant_id: str,
                detail: str, *, kind: str = "event") -> None:
    """Append a timeline event. Uses the caller's open connection."""
    conn.execute(
        "INSERT INTO admissions_events (applicant_id, kind, detail, actor) "
        "VALUES (?, ?, ?, ?)", (applicant_id, kind, detail, _guard.actor()))


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
    for key, label in _AUDITED_FIELDS:
        old, new = getattr(existing, key), p.get(key)
        if (old or None) == (new or None):
            continue
        if key in _LONG_TEXT_FIELDS:
            out.append(f"{label} edited")
        else:
            out.append(f"{label}: {old or '—'} → {new or '—'}")
    return out


#: Fields whose every change goes on the timeline (status, offer,
#: interview and conversion are described above).
_AUDITED_FIELDS: tuple[tuple[str, str], ...] = (
    ("first_name", "First name"), ("last_name", "Last name"),
    ("dob", "Date of birth"), ("email", "Email"), ("phone", "Phone"),
    ("address", "Address"), ("previous_school", "Previous school"),
    ("predicted_gcses", "Predicted GCSEs"),
    ("subject_1", "Subject 1"), ("subject_2", "Subject 2"),
    ("subject_3", "Subject 3"),
    ("reference_name", "Referee"), ("reference_contact", "Referee contact"),
    ("application_source", "Source"), ("submitted_at", "Submitted on"),
    ("offer_conditions", "Offer conditions"),
    ("interview_notes", "Interview notes"),
    ("decision_notes", "Decision notes"), ("notes", "Notes"),
)
_LONG_TEXT_FIELDS = {"interview_notes", "decision_notes", "notes",
                     "predicted_gcses", "offer_conditions"}


def list_events(applicant_id: str) -> list[Event]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM admissions_events WHERE applicant_id = ? "
            "ORDER BY at DESC, id DESC", (applicant_id,)).fetchall()
    return [Event(id=r["id"], applicant_id=r["applicant_id"],
                  at=r["at"], kind=r["kind"], detail=r["detail"],
                  actor=r["actor"] if "actor" in r.keys() else None)
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
    _guard.require("removing applicant documents")
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
    """Hand-set the reference status. Once the applicant has tracked
    references (:mod:`references`) the status follows the tracker, and a
    value that disagrees with it is refused."""
    init_db()
    _guard.require("changing applications")
    if status not in REFERENCE_STATUSES:
        raise ValidationError(
            f"Reference status must be one of: "
            f"{', '.join(REFERENCE_STATUSES)}")
    existing = get_applicant(applicant_id)
    if existing is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    from education_system.systems.sixth_form.domain.admissions import (
        references as _refs,
    )
    tracked = _refs.tracker_status(applicant_id)
    if tracked is not None and tracked != status:
        raise ValidationError(
            f"References for {applicant_id} are tracked (status "
            f"{tracked}); update the reference itself in References.")
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
               "follow_up", "uln", "upn")


def _set_extra(applicant_id: str, *, event: str | None = None,
                event_kind: str = "update", **fields: Any) -> Applicant:
    init_db()
    _guard.require("changing applications")
    bad = set(fields) - set(_EXTRA_COLS)
    if bad:
        raise ValidationError(f"Unknown column(s): {', '.join(bad)}")
    existing = get_applicant(applicant_id)
    if existing is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    if existing.is_archived:
        raise ValidationError(
            f"{applicant_id} is archived; restore it before changing it.")
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

def reschedule_interview(applicant_id: str, *, new_date: str | None = None,
                          reason: str | None = None,
                          interviewer: str | None = None,
                          slot_id: int | None = None) -> Applicant:
    """Move the interview. With ``slot_id`` the slot booking moves
    (:func:`interviews.reschedule`, history kept). A bare ``new_date``
    must not be in the past, and is refused while the applicant holds a
    slot booking (choose another slot instead)."""
    interviews = _slots()
    if slot_id is not None and not interviews.driving():
        interviews.reschedule(applicant_id, int(slot_id), reason=reason)
        out = get_applicant(applicant_id)
        assert out is not None
        return out
    a = get_applicant(applicant_id)
    if a is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    new_date = _future_date(new_date, "Interview date")
    if not interviews.driving():
        b = interviews.active_booking(applicant_id)
        if b is not None:
            raise ValidationError(
                f"{applicant_id} is booked into interview slot "
                f"#{b.slot_id}; choose another slot to reschedule")
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
    """Cancel the interview; a slot booking is cancelled too (kept in the
    booking history)."""
    interviews = _slots()
    if not interviews.driving():
        b = interviews.active_booking(applicant_id)
        if b is not None:
            interviews.cancel_booking(b.booking_id, reason=reason)
            out = get_applicant(applicant_id)
            assert out is not None
            return out
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
    """Record a missed interview (the slot booking, if any, becomes
    No-show) and optionally flag the applicant for follow-up."""
    init_db()
    _guard.require("recording interviews")
    a = get_applicant(applicant_id)
    if a is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    if a.is_archived:
        raise ValidationError(
            f"{applicant_id} is archived; restore it before changing it.")
    _slots().close_booking(applicant_id, "No-show")
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


def list_expiring_offers(*, within_days: int = 7,
                         include_expired: bool = True,
                         today: _dt.date | None = None) -> list[Applicant]:
    """Offers still waiting for an answer (Offer Made) whose expiry is
    within *within_days* of *today* — including ones already past expiry
    unless ``include_expired`` is False. Soonest first."""
    init_db()
    _guard.require("applicant records")
    day = today or _dt.date.today()
    horizon = (day + _dt.timedelta(days=within_days)).isoformat()
    sql = ("SELECT * FROM admissions_applicants WHERE status = 'Offer Made' "
           "AND archived_at IS NULL AND offer_expiry IS NOT NULL "
           "AND offer_expiry <> '' AND offer_expiry <= ?")
    args: list[Any] = [horizon]
    if not include_expired:
        sql += " AND offer_expiry >= ?"
        args.append(day.isoformat())
    with _connect() as conn:
        return [_row(r) for r in conn.execute(
            sql + " ORDER BY offer_expiry, last_name", args).fetchall()]


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
    if a.is_enrolled:
        return []
    if a.status != "Offer Accepted":
        issues.append(f"Status is '{a.status}', not 'Offer Accepted'")
    if a.is_archived:
        issues.append("The application is archived")
    if not list_programme_choices(applicant_id):
        issues.append("No programme choices (subjects / qualifications)")
    if not a.email:
        issues.append("No email address on file")
    if a.offer_expiry and a.offer_expiry < _dt.date.today().isoformat() \
            and not a.is_enrolled:
        issues.append(f"Offer expired on {a.offer_expiry}")
    return issues


# ── GDPR erasure (export, reports and letters: applicant_reports) ──

def erase_applicant(applicant_id: str) -> bool:
    """GDPR erasure. Needs an erasure request approved by a second person
    (see :mod:`record_safety`); refuses an applicant who became a student
    (their data is now the student record's, erased through student
    GDPR). Returns False when there is no such applicant."""
    from education_system.systems.sixth_form.domain.admissions import (
        record_safety,
    )
    return record_safety.erase_if_approved(applicant_id)


# ── Split-out modules (re-exported so existing callers keep working) ──
# Imported last: they import names defined above from this module.
from education_system.systems.sixth_form.domain.admissions.programme_choices import (  # noqa: E402
    ONE_YEAR_TYPES,
    _a_level_types,
    _normalise_choice,
    _reconcile_choices_with_slots,
    _stored_choices,
    add_programme_choice,
    list_programme_choices,
    programme_types,
    remove_programme_choice,
    set_programme_choices,
)
from education_system.systems.sixth_form.domain.admissions.conversion import (  # noqa: E402
    conversion_for_student,
    convert_to_student,
    default_academic_year,
    get_conversion,
)
