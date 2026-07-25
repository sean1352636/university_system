"""GDPR / data-protection records for the Primary School System.

Four related but independent registers, kept in one module so the
compliance/DPO workflow can be driven from a single CLI / GUI:

* ``gdpr_requests``  — data-subject rights requests (Subject Access,
  Erasure, Rectification, Portability, Restriction, Objection,
  Automated Decision review) with statutory due dates.
* ``gdpr_processing`` — Records of Processing Activities (RoPA),
  Article 30 register.
* ``gdpr_breaches``  — personal-data breach log with notification
  workflow.
* ``gdpr_consents``  — consent records (marketing, photography,
  trips, etc.) with grant / withdraw timestamps.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.nursery.infrastructure import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.GDPR_DB

# ── Vocabularies ──────────────────────────────────────────────────

REQUEST_TYPES: tuple[str, ...] = (
    "Subject Access (SAR)",
    "Erasure (Right to be forgotten)",
    "Rectification",
    "Portability",
    "Restriction of Processing",
    "Objection",
    "Automated Decision Review",
    "Other",
)
DEFAULT_REQUEST_TYPE: str = "Subject Access (SAR)"

REQUEST_STATUSES: tuple[str, ...] = (
    "Received", "Identity Verified", "In Review",
    "Responded", "Fulfilled", "Partially Fulfilled",
    "Refused", "Withdrawn", "Closed",
)
DEFAULT_REQUEST_STATUS: str = "Received"
OPEN_REQUEST_STATUSES: tuple[str, ...] = (
    "Received", "Identity Verified", "In Review",
)

SUBJECT_TYPES: tuple[str, ...] = (
    "Student", "Staff", "Parent / Guardian", "Applicant",
    "Alumni", "Visitor", "Other",
)
DEFAULT_SUBJECT_TYPE: str = "Student"

LAWFUL_BASES: tuple[str, ...] = (
    "Consent", "Contract", "Legal Obligation",
    "Vital Interests", "Public Task", "Legitimate Interests",
)
PROCESSING_STATUSES: tuple[str, ...] = (
    "Active", "Under Review", "Suspended", "Retired",
)
DEFAULT_PROCESSING_STATUS: str = "Active"

BREACH_SEVERITIES: tuple[str, ...] = (
    "Negligible", "Low", "Medium", "High", "Critical",
)
DEFAULT_BREACH_SEVERITY: str = "Medium"
BREACH_STATUSES: tuple[str, ...] = (
    "Reported", "Investigating", "Contained",
    "ICO Notified", "Subjects Notified", "Closed", "No Action",
)
DEFAULT_BREACH_STATUS: str = "Reported"

CONSENT_PURPOSES: tuple[str, ...] = (
    "Photography / Video", "Marketing", "Trips & Visits",
    "Medical", "Third-Party Sharing",
    "External Coursework Submission", "Newsletter",
    "Alumni Network", "Other",
)
DEFAULT_CONSENT_PURPOSE: str = "Photography / Video"

# UK GDPR default response window for DSAR is one calendar month.
DEFAULT_SAR_DUE_DAYS: int = 30

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ── DB plumbing ───────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS gdpr_requests (
    request_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_name    TEXT NOT NULL,
    subject_type    TEXT NOT NULL DEFAULT 'Student',
    subject_ref     TEXT,
    request_type    TEXT NOT NULL DEFAULT 'Subject Access (SAR)',
    received_date   TEXT NOT NULL,
    identity_verified INTEGER NOT NULL DEFAULT 0,
    due_date        TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'Received',
    responded_date  TEXT,
    handler         TEXT,
    description     TEXT,
    response_summary TEXT,
    refusal_reason  TEXT,
    contact_email   TEXT,
    contact_phone   TEXT,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS gdpr_processing (
    activity_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    controller      TEXT,
    purpose         TEXT NOT NULL,
    lawful_basis    TEXT NOT NULL DEFAULT 'Public Task',
    data_categories TEXT,
    data_subjects   TEXT,
    recipients      TEXT,
    retention       TEXT,
    transfers       TEXT,
    security_measures TEXT,
    dpia_required   INTEGER NOT NULL DEFAULT 0,
    dpia_completed  INTEGER NOT NULL DEFAULT 0,
    dpia_date       TEXT,
    status          TEXT NOT NULL DEFAULT 'Active',
    last_reviewed   TEXT,
    next_review     TEXT,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS gdpr_breaches (
    breach_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    discovered_date TEXT NOT NULL,
    occurred_date   TEXT,
    reported_by     TEXT,
    severity        TEXT NOT NULL DEFAULT 'Medium',
    status          TEXT NOT NULL DEFAULT 'Reported',
    affected_count  INTEGER NOT NULL DEFAULT 0,
    affected_categories TEXT,
    summary         TEXT NOT NULL,
    root_cause      TEXT,
    remediation     TEXT,
    ico_notifiable  INTEGER NOT NULL DEFAULT 0,
    ico_notified_date TEXT,
    ico_reference   TEXT,
    subjects_notified INTEGER NOT NULL DEFAULT 0,
    subjects_notified_date TEXT,
    closed_date     TEXT,
    lessons_learned TEXT,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS gdpr_consents (
    consent_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_name    TEXT NOT NULL,
    subject_type    TEXT NOT NULL DEFAULT 'Student',
    subject_ref     TEXT,
    purpose         TEXT NOT NULL,
    granted         INTEGER NOT NULL DEFAULT 1,
    granted_date    TEXT NOT NULL,
    expires_date    TEXT,
    withdrawn_date  TEXT,
    source          TEXT,
    detail          TEXT,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_gdpr_req_status ON gdpr_requests(status);
CREATE INDEX IF NOT EXISTS idx_gdpr_req_due    ON gdpr_requests(due_date);
CREATE INDEX IF NOT EXISTS idx_gdpr_req_type   ON gdpr_requests(request_type);
CREATE INDEX IF NOT EXISTS idx_gdpr_proc_status ON gdpr_processing(status);
CREATE INDEX IF NOT EXISTS idx_gdpr_breach_st  ON gdpr_breaches(status);
CREATE INDEX IF NOT EXISTS idx_gdpr_breach_sev ON gdpr_breaches(severity);
CREATE INDEX IF NOT EXISTS idx_gdpr_cons_ref   ON gdpr_consents(subject_ref);
CREATE INDEX IF NOT EXISTS idx_gdpr_cons_purp  ON gdpr_consents(purpose);
"""


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
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("GDPR schema ready at %s", DB_PATH)

    _DB_READY = True


# ── Types ─────────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


@dataclass
class Request:
    request_id: int
    subject_name: str
    subject_type: str
    subject_ref: str | None
    request_type: str
    received_date: str
    identity_verified: bool
    due_date: str
    status: str
    responded_date: str | None
    handler: str | None
    description: str | None
    response_summary: str | None
    refusal_reason: str | None
    contact_email: str | None
    contact_phone: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_REQUEST_STATUSES

    @property
    def days_remaining(self) -> int | None:
        try:
            due = _dt.date.fromisoformat(self.due_date)
        except ValueError:
            return None
        if not self.is_open:
            return None
        return (due - _dt.date.today()).days

    @property
    def is_overdue(self) -> bool:
        dr = self.days_remaining
        return dr is not None and dr < 0


@dataclass
class ProcessingActivity:
    activity_id: int
    name: str
    controller: str | None
    purpose: str
    lawful_basis: str
    data_categories: str | None
    data_subjects: str | None
    recipients: str | None
    retention: str | None
    transfers: str | None
    security_measures: str | None
    dpia_required: bool
    dpia_completed: bool
    dpia_date: str | None
    status: str
    last_reviewed: str | None
    next_review: str | None
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class Breach:
    breach_id: int
    title: str
    discovered_date: str
    occurred_date: str | None
    reported_by: str | None
    severity: str
    status: str
    affected_count: int
    affected_categories: str | None
    summary: str
    root_cause: str | None
    remediation: str | None
    ico_notifiable: bool
    ico_notified_date: str | None
    ico_reference: str | None
    subjects_notified: bool
    subjects_notified_date: str | None
    closed_date: str | None
    lessons_learned: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def is_open(self) -> bool:
        return self.status not in ("Closed", "No Action")


@dataclass
class Consent:
    consent_id: int
    subject_name: str
    subject_type: str
    subject_ref: str | None
    purpose: str
    granted: bool
    granted_date: str
    expires_date: str | None
    withdrawn_date: str | None
    source: str | None
    detail: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def is_active(self) -> bool:
        if not self.granted or self.withdrawn_date:
            return False
        if self.expires_date:
            try:
                if _dt.date.fromisoformat(self.expires_date) \
                        < _dt.date.today():
                    return False
            except ValueError:
                pass
        return True


# ── Validation helpers ────────────────────────────────────────────

def _require(v, label: str):
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        raise ValidationError(f"{label} is required")
    return v


def _today() -> str:
    return _dt.date.today().isoformat()


def _validate_date(v: Any, label: str, *,
                    required: bool = False) -> str | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    s = str(v).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return s


def _validate_in(v: Any, options: tuple[str, ...], label: str,
                  *, default: str | None = None,
                  required: bool = True) -> str | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        if default is not None:
            return default
        if required:
            raise ValidationError(f"{label} is required")
        return None
    s = str(v).strip()
    if s not in options:
        raise ValidationError(
            f"{label} must be one of: {', '.join(options)}")
    return s


def _validate_int(v: Any, label: str, *,
                   default: int = 0,
                   min_val: int = 0,
                   max_val: int | None = None) -> int:
    if v in (None, ""):
        return default
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a whole number") from None
    if n < min_val:
        raise ValidationError(f"{label} cannot be less than {min_val}")
    if max_val is not None and n > max_val:
        raise ValidationError(f"{label} cannot be more than {max_val}")
    return n


# ── Request CRUD ──────────────────────────────────────────────────

def _row_req(r: sqlite3.Row) -> Request:
    return Request(
        request_id=r["request_id"], subject_name=r["subject_name"],
        subject_type=r["subject_type"], subject_ref=r["subject_ref"],
        request_type=r["request_type"],
        received_date=r["received_date"],
        identity_verified=bool(r["identity_verified"]),
        due_date=r["due_date"], status=r["status"],
        responded_date=r["responded_date"],
        handler=r["handler"], description=r["description"],
        response_summary=r["response_summary"],
        refusal_reason=r["refusal_reason"],
        contact_email=r["contact_email"],
        contact_phone=r["contact_phone"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _validate_request(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["subject_name"] = str(
        _require(d.get("subject_name"), "Subject name")).strip()
    out["subject_type"] = _validate_in(
        d.get("subject_type"), SUBJECT_TYPES, "Subject type",
        default=DEFAULT_SUBJECT_TYPE)
    out["subject_ref"] = (d.get("subject_ref") or "").strip() or None
    out["request_type"] = _validate_in(
        d.get("request_type"), REQUEST_TYPES, "Request type",
        default=DEFAULT_REQUEST_TYPE)
    received = _validate_date(
        d.get("received_date") or _today(),
        "Received date", required=True)
    out["received_date"] = received
    due = d.get("due_date")
    if due in (None, "") or (isinstance(due, str) and not due.strip()):
        # Compute statutory default — one calendar month from
        # received, capped at +30 days for safety.
        try:
            base = _dt.date.fromisoformat(received)
        except ValueError:
            base = _dt.date.today()
        out["due_date"] = (base + _dt.timedelta(
            days=DEFAULT_SAR_DUE_DAYS)).isoformat()
    else:
        out["due_date"] = _validate_date(due, "Due date", required=True)
    out["identity_verified"] = bool(d.get("identity_verified"))
    out["status"] = _validate_in(
        d.get("status"), REQUEST_STATUSES, "Status",
        default=DEFAULT_REQUEST_STATUS)
    out["responded_date"] = _validate_date(
        d.get("responded_date"), "Responded date")
    out["handler"] = (d.get("handler") or "").strip() or None
    out["description"] = (d.get("description") or "").strip() or None
    out["response_summary"] = (
        d.get("response_summary") or "").strip() or None
    out["refusal_reason"] = (
        d.get("refusal_reason") or "").strip() or None
    out["contact_email"] = (
        d.get("contact_email") or "").strip() or None
    out["contact_phone"] = (
        d.get("contact_phone") or "").strip() or None
    out["notes"] = (d.get("notes") or "").strip() or None
    if out["status"] == "Refused" and not out["refusal_reason"]:
        raise ValidationError(
            "Refusal reason is required when status is 'Refused'")
    if out["status"] in ("Responded", "Fulfilled",
                          "Partially Fulfilled", "Closed") \
            and not out["responded_date"]:
        out["responded_date"] = _today()
    return out


def create_request(d: dict[str, Any]) -> Request:
    init_db()
    p = _validate_request(d)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO gdpr_requests (
                  subject_name, subject_type, subject_ref,
                  request_type, received_date, identity_verified,
                  due_date, status, responded_date, handler,
                  description, response_summary, refusal_reason,
                  contact_email, contact_phone, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (p["subject_name"], p["subject_type"], p["subject_ref"],
             p["request_type"], p["received_date"],
             int(p["identity_verified"]), p["due_date"], p["status"],
             p["responded_date"], p["handler"], p["description"],
             p["response_summary"], p["refusal_reason"],
             p["contact_email"], p["contact_phone"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_request(new_id)
    assert out is not None
    logger.info("Created GDPR request #%d (%s for %s)",
                new_id, p["request_type"], p["subject_name"])
    return out


def get_request(request_id: int) -> Request | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM gdpr_requests WHERE request_id = ?",
            (request_id,)).fetchone()
    return _row_req(r) if r else None


def list_requests(
    *,
    status: str | None = None,
    request_type: str | None = None,
    subject_type: str | None = None,
    open_only: bool = False,
    overdue_only: bool = False,
    search: str | None = None,
) -> list[Request]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if status:
        clauses.append("status = ?")
        args.append(status)
    if request_type:
        clauses.append("request_type = ?")
        args.append(request_type)
    if subject_type:
        clauses.append("subject_type = ?")
        args.append(subject_type)
    if open_only:
        ph = ",".join("?" * len(OPEN_REQUEST_STATUSES))
        clauses.append(f"status IN ({ph})")
        args.extend(OPEN_REQUEST_STATUSES)
    if search:
        clauses.append(
            "(subject_name LIKE ? OR subject_ref LIKE ? "
            "OR description LIKE ? OR notes LIKE ?)")
        like = f"%{search.strip()}%"
        args.extend([like, like, like, like])
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    sql = (f"SELECT * FROM gdpr_requests {where} "
           "ORDER BY due_date ASC, request_id DESC")
    with _connect() as conn:
        rows = [_row_req(r)
                for r in conn.execute(sql, args).fetchall()]
    if overdue_only:
        rows = [r for r in rows if r.is_overdue]
    return rows


def update_request(request_id: int, d: dict[str, Any]) -> Request:
    init_db()
    existing = get_request(request_id)
    if existing is None:
        raise ValidationError(f"No request #{request_id}")
    merged: dict[str, Any] = {
        "subject_name": d.get("subject_name", existing.subject_name),
        "subject_type": d.get("subject_type", existing.subject_type),
        "subject_ref":  d.get("subject_ref",  existing.subject_ref),
        "request_type": d.get("request_type", existing.request_type),
        "received_date": d.get("received_date",
                                existing.received_date),
        "identity_verified": d.get("identity_verified",
                                    existing.identity_verified),
        "due_date":       d.get("due_date",       existing.due_date),
        "status":         d.get("status",         existing.status),
        "responded_date": d.get("responded_date",
                                  existing.responded_date),
        "handler":          d.get("handler",          existing.handler),
        "description":      d.get("description",      existing.description),
        "response_summary": d.get("response_summary",
                                    existing.response_summary),
        "refusal_reason":   d.get("refusal_reason",
                                    existing.refusal_reason),
        "contact_email":    d.get("contact_email",
                                    existing.contact_email),
        "contact_phone":    d.get("contact_phone",
                                    existing.contact_phone),
        "notes":            d.get("notes",            existing.notes),
    }
    p = _validate_request(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE gdpr_requests SET
                  subject_name=?, subject_type=?, subject_ref=?,
                  request_type=?, received_date=?, identity_verified=?,
                  due_date=?, status=?, responded_date=?, handler=?,
                  description=?, response_summary=?, refusal_reason=?,
                  contact_email=?, contact_phone=?, notes=?,
                  updated_at=datetime('now')
               WHERE request_id=?""",
            (p["subject_name"], p["subject_type"], p["subject_ref"],
             p["request_type"], p["received_date"],
             int(p["identity_verified"]), p["due_date"], p["status"],
             p["responded_date"], p["handler"], p["description"],
             p["response_summary"], p["refusal_reason"],
             p["contact_email"], p["contact_phone"], p["notes"],
             request_id),
        )
        conn.commit()
    out = get_request(request_id)
    assert out is not None
    logger.info("Updated GDPR request #%d (status=%s)",
                request_id, out.status)
    return out


def set_request_status(request_id: int, status: str,
                        *, response_summary: str | None = None,
                        refusal_reason: str | None = None) -> Request:
    payload: dict[str, Any] = {"status": status}
    if response_summary is not None:
        payload["response_summary"] = response_summary
    if refusal_reason is not None:
        payload["refusal_reason"] = refusal_reason
    return update_request(request_id, payload)


def delete_request(request_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM gdpr_requests WHERE request_id = ?",
            (request_id,))
        conn.commit()
    if cur.rowcount:
        logger.info("Deleted GDPR request #%d", request_id)
        return True
    return False


# ── Processing-activity CRUD ──────────────────────────────────────

def _row_proc(r: sqlite3.Row) -> ProcessingActivity:
    return ProcessingActivity(
        activity_id=r["activity_id"], name=r["name"],
        controller=r["controller"], purpose=r["purpose"],
        lawful_basis=r["lawful_basis"],
        data_categories=r["data_categories"],
        data_subjects=r["data_subjects"],
        recipients=r["recipients"], retention=r["retention"],
        transfers=r["transfers"],
        security_measures=r["security_measures"],
        dpia_required=bool(r["dpia_required"]),
        dpia_completed=bool(r["dpia_completed"]),
        dpia_date=r["dpia_date"], status=r["status"],
        last_reviewed=r["last_reviewed"],
        next_review=r["next_review"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _validate_processing(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["name"] = str(_require(d.get("name"), "Name")).strip()
    out["controller"] = (d.get("controller") or "").strip() or None
    out["purpose"] = str(_require(d.get("purpose"), "Purpose")).strip()
    out["lawful_basis"] = _validate_in(
        d.get("lawful_basis"), LAWFUL_BASES, "Lawful basis",
        default="Public Task")
    out["data_categories"] = (d.get("data_categories") or "").strip() or None
    out["data_subjects"] = (d.get("data_subjects") or "").strip() or None
    out["recipients"] = (d.get("recipients") or "").strip() or None
    out["retention"] = (d.get("retention") or "").strip() or None
    out["transfers"] = (d.get("transfers") or "").strip() or None
    out["security_measures"] = (
        d.get("security_measures") or "").strip() or None
    out["dpia_required"] = bool(d.get("dpia_required"))
    out["dpia_completed"] = bool(d.get("dpia_completed"))
    out["dpia_date"] = _validate_date(d.get("dpia_date"), "DPIA date")
    out["status"] = _validate_in(
        d.get("status"), PROCESSING_STATUSES, "Status",
        default=DEFAULT_PROCESSING_STATUS)
    out["last_reviewed"] = _validate_date(
        d.get("last_reviewed"), "Last reviewed")
    out["next_review"] = _validate_date(
        d.get("next_review"), "Next review")
    out["notes"] = (d.get("notes") or "").strip() or None
    return out


def create_processing(d: dict[str, Any]) -> ProcessingActivity:
    init_db()
    p = _validate_processing(d)
    with _connect() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO gdpr_processing (
                      name, controller, purpose, lawful_basis,
                      data_categories, data_subjects, recipients,
                      retention, transfers, security_measures,
                      dpia_required, dpia_completed, dpia_date,
                      status, last_reviewed, next_review, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           ?, ?, ?)""",
                (p["name"], p["controller"], p["purpose"],
                 p["lawful_basis"], p["data_categories"],
                 p["data_subjects"], p["recipients"], p["retention"],
                 p["transfers"], p["security_measures"],
                 int(p["dpia_required"]), int(p["dpia_completed"]),
                 p["dpia_date"], p["status"], p["last_reviewed"],
                 p["next_review"], p["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
        except sqlite3.IntegrityError:
            raise ValidationError(
                f"A processing activity named "
                f"{p['name']!r} already exists") from None
    out = get_processing(new_id)
    assert out is not None
    logger.info("Created GDPR processing activity #%d (%s)",
                new_id, p["name"])
    return out


def get_processing(activity_id: int) -> ProcessingActivity | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM gdpr_processing WHERE activity_id = ?",
            (activity_id,)).fetchone()
    return _row_proc(r) if r else None


def list_processing(*, status: str | None = None,
                     lawful_basis: str | None = None,
                     search: str | None = None
                     ) -> list[ProcessingActivity]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if status:
        clauses.append("status = ?")
        args.append(status)
    if lawful_basis:
        clauses.append("lawful_basis = ?")
        args.append(lawful_basis)
    if search:
        clauses.append(
            "(name LIKE ? OR purpose LIKE ? OR controller LIKE ? "
            "OR data_categories LIKE ?)")
        like = f"%{search.strip()}%"
        args.extend([like, like, like, like])
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    sql = (f"SELECT * FROM gdpr_processing {where} "
           "ORDER BY LOWER(name)")
    with _connect() as conn:
        return [_row_proc(r)
                for r in conn.execute(sql, args).fetchall()]


def update_processing(activity_id: int,
                       d: dict[str, Any]) -> ProcessingActivity:
    init_db()
    existing = get_processing(activity_id)
    if existing is None:
        raise ValidationError(f"No processing activity #{activity_id}")
    merged = {
        "name":             d.get("name",             existing.name),
        "controller":       d.get("controller",       existing.controller),
        "purpose":          d.get("purpose",          existing.purpose),
        "lawful_basis":     d.get("lawful_basis",
                                    existing.lawful_basis),
        "data_categories":  d.get("data_categories",
                                    existing.data_categories),
        "data_subjects":    d.get("data_subjects",
                                    existing.data_subjects),
        "recipients":       d.get("recipients",       existing.recipients),
        "retention":        d.get("retention",        existing.retention),
        "transfers":        d.get("transfers",        existing.transfers),
        "security_measures": d.get("security_measures",
                                     existing.security_measures),
        "dpia_required":    d.get("dpia_required",
                                    existing.dpia_required),
        "dpia_completed":   d.get("dpia_completed",
                                    existing.dpia_completed),
        "dpia_date":        d.get("dpia_date",        existing.dpia_date),
        "status":           d.get("status",           existing.status),
        "last_reviewed":    d.get("last_reviewed",
                                    existing.last_reviewed),
        "next_review":      d.get("next_review",
                                    existing.next_review),
        "notes":            d.get("notes",            existing.notes),
    }
    p = _validate_processing(merged)
    with _connect() as conn:
        try:
            conn.execute(
                """UPDATE gdpr_processing SET
                      name=?, controller=?, purpose=?, lawful_basis=?,
                      data_categories=?, data_subjects=?, recipients=?,
                      retention=?, transfers=?, security_measures=?,
                      dpia_required=?, dpia_completed=?, dpia_date=?,
                      status=?, last_reviewed=?, next_review=?, notes=?,
                      updated_at=datetime('now')
                   WHERE activity_id=?""",
                (p["name"], p["controller"], p["purpose"],
                 p["lawful_basis"], p["data_categories"],
                 p["data_subjects"], p["recipients"], p["retention"],
                 p["transfers"], p["security_measures"],
                 int(p["dpia_required"]), int(p["dpia_completed"]),
                 p["dpia_date"], p["status"], p["last_reviewed"],
                 p["next_review"], p["notes"], activity_id),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise ValidationError(
                f"A processing activity named "
                f"{p['name']!r} already exists") from None
    out = get_processing(activity_id)
    assert out is not None
    logger.info("Updated GDPR processing activity #%d", activity_id)
    return out


def delete_processing(activity_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM gdpr_processing WHERE activity_id = ?",
            (activity_id,))
        conn.commit()
    if cur.rowcount:
        logger.info("Deleted GDPR processing activity #%d", activity_id)
        return True
    return False


# ── Breach CRUD ───────────────────────────────────────────────────

def _row_breach(r: sqlite3.Row) -> Breach:
    return Breach(
        breach_id=r["breach_id"], title=r["title"],
        discovered_date=r["discovered_date"],
        occurred_date=r["occurred_date"],
        reported_by=r["reported_by"], severity=r["severity"],
        status=r["status"], affected_count=r["affected_count"],
        affected_categories=r["affected_categories"],
        summary=r["summary"], root_cause=r["root_cause"],
        remediation=r["remediation"],
        ico_notifiable=bool(r["ico_notifiable"]),
        ico_notified_date=r["ico_notified_date"],
        ico_reference=r["ico_reference"],
        subjects_notified=bool(r["subjects_notified"]),
        subjects_notified_date=r["subjects_notified_date"],
        closed_date=r["closed_date"],
        lessons_learned=r["lessons_learned"],
        notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _validate_breach(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["title"] = str(_require(d.get("title"), "Title")).strip()
    out["discovered_date"] = _validate_date(
        d.get("discovered_date") or _today(),
        "Discovered date", required=True)
    out["occurred_date"] = _validate_date(
        d.get("occurred_date"), "Occurred date")
    out["reported_by"] = (d.get("reported_by") or "").strip() or None
    out["severity"] = _validate_in(
        d.get("severity"), BREACH_SEVERITIES, "Severity",
        default=DEFAULT_BREACH_SEVERITY)
    out["status"] = _validate_in(
        d.get("status"), BREACH_STATUSES, "Status",
        default=DEFAULT_BREACH_STATUS)
    out["affected_count"] = _validate_int(
        d.get("affected_count"), "Affected count",
        default=0, min_val=0)
    out["affected_categories"] = (
        d.get("affected_categories") or "").strip() or None
    out["summary"] = str(_require(d.get("summary"), "Summary")).strip()
    out["root_cause"] = (d.get("root_cause") or "").strip() or None
    out["remediation"] = (d.get("remediation") or "").strip() or None
    out["ico_notifiable"] = bool(d.get("ico_notifiable"))
    out["ico_notified_date"] = _validate_date(
        d.get("ico_notified_date"), "ICO notified date")
    out["ico_reference"] = (d.get("ico_reference") or "").strip() or None
    out["subjects_notified"] = bool(d.get("subjects_notified"))
    out["subjects_notified_date"] = _validate_date(
        d.get("subjects_notified_date"), "Subjects notified date")
    out["closed_date"] = _validate_date(
        d.get("closed_date"), "Closed date")
    out["lessons_learned"] = (
        d.get("lessons_learned") or "").strip() or None
    out["notes"] = (d.get("notes") or "").strip() or None
    if out["status"] == "Closed" and not out["closed_date"]:
        out["closed_date"] = _today()
    if out["ico_notifiable"] and out["status"] == "ICO Notified" \
            and not out["ico_notified_date"]:
        out["ico_notified_date"] = _today()
    return out


def create_breach(d: dict[str, Any]) -> Breach:
    init_db()
    p = _validate_breach(d)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO gdpr_breaches (
                  title, discovered_date, occurred_date, reported_by,
                  severity, status, affected_count,
                  affected_categories, summary, root_cause,
                  remediation, ico_notifiable, ico_notified_date,
                  ico_reference, subjects_notified,
                  subjects_notified_date, closed_date,
                  lessons_learned, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?)""",
            (p["title"], p["discovered_date"], p["occurred_date"],
             p["reported_by"], p["severity"], p["status"],
             p["affected_count"], p["affected_categories"],
             p["summary"], p["root_cause"], p["remediation"],
             int(p["ico_notifiable"]), p["ico_notified_date"],
             p["ico_reference"], int(p["subjects_notified"]),
             p["subjects_notified_date"], p["closed_date"],
             p["lessons_learned"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_breach(new_id)
    assert out is not None
    logger.info("Created GDPR breach #%d (%s, severity=%s)",
                new_id, p["title"], p["severity"])
    return out


def get_breach(breach_id: int) -> Breach | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM gdpr_breaches WHERE breach_id = ?",
            (breach_id,)).fetchone()
    return _row_breach(r) if r else None


def list_breaches(*, status: str | None = None,
                   severity: str | None = None,
                   open_only: bool = False,
                   ico_only: bool = False) -> list[Breach]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if status:
        clauses.append("status = ?")
        args.append(status)
    if severity:
        clauses.append("severity = ?")
        args.append(severity)
    if ico_only:
        clauses.append("ico_notifiable = 1")
    if open_only:
        clauses.append("status NOT IN ('Closed', 'No Action')")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    sql = (f"SELECT * FROM gdpr_breaches {where} "
           "ORDER BY discovered_date DESC, breach_id DESC")
    with _connect() as conn:
        return [_row_breach(r)
                for r in conn.execute(sql, args).fetchall()]


def update_breach(breach_id: int, d: dict[str, Any]) -> Breach:
    init_db()
    existing = get_breach(breach_id)
    if existing is None:
        raise ValidationError(f"No breach #{breach_id}")
    merged = {
        "title":         d.get("title",         existing.title),
        "discovered_date": d.get("discovered_date",
                                   existing.discovered_date),
        "occurred_date": d.get("occurred_date",
                                 existing.occurred_date),
        "reported_by":   d.get("reported_by",   existing.reported_by),
        "severity":      d.get("severity",      existing.severity),
        "status":        d.get("status",        existing.status),
        "affected_count": d.get("affected_count",
                                  existing.affected_count),
        "affected_categories": d.get("affected_categories",
                                        existing.affected_categories),
        "summary":       d.get("summary",       existing.summary),
        "root_cause":    d.get("root_cause",    existing.root_cause),
        "remediation":   d.get("remediation",   existing.remediation),
        "ico_notifiable": d.get("ico_notifiable",
                                  existing.ico_notifiable),
        "ico_notified_date": d.get("ico_notified_date",
                                      existing.ico_notified_date),
        "ico_reference": d.get("ico_reference", existing.ico_reference),
        "subjects_notified": d.get("subjects_notified",
                                      existing.subjects_notified),
        "subjects_notified_date": d.get(
            "subjects_notified_date",
            existing.subjects_notified_date),
        "closed_date":   d.get("closed_date",   existing.closed_date),
        "lessons_learned": d.get("lessons_learned",
                                   existing.lessons_learned),
        "notes":         d.get("notes",         existing.notes),
    }
    p = _validate_breach(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE gdpr_breaches SET
                  title=?, discovered_date=?, occurred_date=?,
                  reported_by=?, severity=?, status=?,
                  affected_count=?, affected_categories=?,
                  summary=?, root_cause=?, remediation=?,
                  ico_notifiable=?, ico_notified_date=?,
                  ico_reference=?, subjects_notified=?,
                  subjects_notified_date=?, closed_date=?,
                  lessons_learned=?, notes=?,
                  updated_at=datetime('now')
               WHERE breach_id=?""",
            (p["title"], p["discovered_date"], p["occurred_date"],
             p["reported_by"], p["severity"], p["status"],
             p["affected_count"], p["affected_categories"],
             p["summary"], p["root_cause"], p["remediation"],
             int(p["ico_notifiable"]), p["ico_notified_date"],
             p["ico_reference"], int(p["subjects_notified"]),
             p["subjects_notified_date"], p["closed_date"],
             p["lessons_learned"], p["notes"], breach_id),
        )
        conn.commit()
    out = get_breach(breach_id)
    assert out is not None
    logger.info("Updated GDPR breach #%d (status=%s)",
                breach_id, out.status)
    return out


def delete_breach(breach_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM gdpr_breaches WHERE breach_id = ?",
            (breach_id,))
        conn.commit()
    if cur.rowcount:
        logger.info("Deleted GDPR breach #%d", breach_id)
        return True
    return False


# ── Consent CRUD ──────────────────────────────────────────────────

def _row_cons(r: sqlite3.Row) -> Consent:
    return Consent(
        consent_id=r["consent_id"], subject_name=r["subject_name"],
        subject_type=r["subject_type"], subject_ref=r["subject_ref"],
        purpose=r["purpose"], granted=bool(r["granted"]),
        granted_date=r["granted_date"],
        expires_date=r["expires_date"],
        withdrawn_date=r["withdrawn_date"],
        source=r["source"], detail=r["detail"],
        notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _validate_consent(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["subject_name"] = str(
        _require(d.get("subject_name"), "Subject name")).strip()
    out["subject_type"] = _validate_in(
        d.get("subject_type"), SUBJECT_TYPES, "Subject type",
        default=DEFAULT_SUBJECT_TYPE)
    out["subject_ref"] = (d.get("subject_ref") or "").strip() or None
    purpose = str(_require(d.get("purpose"), "Purpose")).strip()
    out["purpose"] = purpose
    out["granted"] = (d.get("granted") if d.get("granted")
                       is not None else True)
    out["granted"] = bool(out["granted"])
    out["granted_date"] = _validate_date(
        d.get("granted_date") or _today(),
        "Granted date", required=True)
    out["expires_date"] = _validate_date(
        d.get("expires_date"), "Expires date")
    out["withdrawn_date"] = _validate_date(
        d.get("withdrawn_date"), "Withdrawn date")
    out["source"] = (d.get("source") or "").strip() or None
    out["detail"] = (d.get("detail") or "").strip() or None
    out["notes"] = (d.get("notes") or "").strip() or None
    return out


def create_consent(d: dict[str, Any]) -> Consent:
    init_db()
    p = _validate_consent(d)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO gdpr_consents (
                  subject_name, subject_type, subject_ref, purpose,
                  granted, granted_date, expires_date,
                  withdrawn_date, source, detail, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (p["subject_name"], p["subject_type"], p["subject_ref"],
             p["purpose"], int(p["granted"]), p["granted_date"],
             p["expires_date"], p["withdrawn_date"], p["source"],
             p["detail"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_consent(new_id)
    assert out is not None
    logger.info("Created GDPR consent #%d (%s for %s)",
                new_id, p["purpose"], p["subject_name"])
    return out


def get_consent(consent_id: int) -> Consent | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM gdpr_consents WHERE consent_id = ?",
            (consent_id,)).fetchone()
    return _row_cons(r) if r else None


def list_consents(*, subject_ref: str | None = None,
                    purpose: str | None = None,
                    active_only: bool = False,
                    search: str | None = None) -> list[Consent]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if subject_ref:
        clauses.append("subject_ref = ?")
        args.append(subject_ref.strip())
    if purpose:
        clauses.append("purpose = ?")
        args.append(purpose)
    if search:
        like = f"%{search.strip()}%"
        clauses.append(
            "(subject_name LIKE ? OR subject_ref LIKE ? "
            "OR detail LIKE ? OR notes LIKE ?)")
        args.extend([like, like, like, like])
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    sql = (f"SELECT * FROM gdpr_consents {where} "
           "ORDER BY granted_date DESC, consent_id DESC")
    with _connect() as conn:
        rows = [_row_cons(r)
                for r in conn.execute(sql, args).fetchall()]
    if active_only:
        rows = [r for r in rows if r.is_active]
    return rows


def update_consent(consent_id: int, d: dict[str, Any]) -> Consent:
    init_db()
    existing = get_consent(consent_id)
    if existing is None:
        raise ValidationError(f"No consent #{consent_id}")
    merged = {
        "subject_name": d.get("subject_name", existing.subject_name),
        "subject_type": d.get("subject_type", existing.subject_type),
        "subject_ref":  d.get("subject_ref",  existing.subject_ref),
        "purpose":      d.get("purpose",      existing.purpose),
        "granted":      d.get("granted",      existing.granted),
        "granted_date": d.get("granted_date", existing.granted_date),
        "expires_date": d.get("expires_date", existing.expires_date),
        "withdrawn_date": d.get("withdrawn_date",
                                  existing.withdrawn_date),
        "source":       d.get("source",       existing.source),
        "detail":       d.get("detail",       existing.detail),
        "notes":        d.get("notes",        existing.notes),
    }
    p = _validate_consent(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE gdpr_consents SET
                  subject_name=?, subject_type=?, subject_ref=?,
                  purpose=?, granted=?, granted_date=?,
                  expires_date=?, withdrawn_date=?,
                  source=?, detail=?, notes=?,
                  updated_at=datetime('now')
               WHERE consent_id=?""",
            (p["subject_name"], p["subject_type"], p["subject_ref"],
             p["purpose"], int(p["granted"]), p["granted_date"],
             p["expires_date"], p["withdrawn_date"], p["source"],
             p["detail"], p["notes"], consent_id),
        )
        conn.commit()
    out = get_consent(consent_id)
    assert out is not None
    logger.info("Updated GDPR consent #%d", consent_id)
    return out


def withdraw_consent(consent_id: int,
                      *, withdrawn_date: str | None = None,
                      notes: str | None = None) -> Consent:
    return update_consent(consent_id, {
        "granted": False,
        "withdrawn_date": withdrawn_date or _today(),
        "notes": notes if notes is not None
        else (get_consent(consent_id).notes if get_consent(
            consent_id) else None),
    })


def delete_consent(consent_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM gdpr_consents WHERE consent_id = ?",
            (consent_id,))
        conn.commit()
    if cur.rowcount:
        logger.info("Deleted GDPR consent #%d", consent_id)
        return True
    return False


# ── Summary ───────────────────────────────────────────────────────

@dataclass
class GdprOverview:
    total_requests: int
    open_requests: int
    overdue_requests: int
    requests_by_status: dict[str, int]
    requests_by_type: dict[str, int]
    total_processing: int
    processing_active: int
    processing_due_review: int
    total_breaches: int
    open_breaches: int
    high_or_critical_breaches: int
    ico_notifiable_open: int
    total_consents: int
    active_consents: int
    withdrawn_consents: int


def overview() -> GdprOverview:
    init_db()
    reqs = list_requests()
    open_r = [r for r in reqs if r.is_open]
    overdue_r = [r for r in reqs if r.is_overdue]
    by_status: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for r in reqs:
        by_status[r.status] = by_status.get(r.status, 0) + 1
        by_type[r.request_type] = by_type.get(r.request_type, 0) + 1
    procs = list_processing()
    today = _dt.date.today()
    due_proc = 0
    for p in procs:
        if p.next_review:
            try:
                if _dt.date.fromisoformat(p.next_review) <= today:
                    due_proc += 1
            except ValueError:
                pass
    breaches = list_breaches()
    open_b = [b for b in breaches if b.is_open]
    hi_b = [b for b in breaches
            if b.severity in ("High", "Critical")]
    ico_open = [b for b in open_b if b.ico_notifiable]
    consents = list_consents()
    return GdprOverview(
        total_requests=len(reqs),
        open_requests=len(open_r),
        overdue_requests=len(overdue_r),
        requests_by_status=by_status, requests_by_type=by_type,
        total_processing=len(procs),
        processing_active=sum(1 for p in procs
                                if p.status == "Active"),
        processing_due_review=due_proc,
        total_breaches=len(breaches), open_breaches=len(open_b),
        high_or_critical_breaches=len(hi_b),
        ico_notifiable_open=len(ico_open),
        total_consents=len(consents),
        active_consents=sum(1 for c in consents if c.is_active),
        withdrawn_consents=sum(1 for c in consents
                                 if c.withdrawn_date),
    )
