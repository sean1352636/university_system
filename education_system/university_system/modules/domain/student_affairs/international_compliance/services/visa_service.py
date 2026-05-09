"""International student visa-sponsorship service.

All Tier-4 / Student-Route sponsor duties for one student live here:

* ``VisaRecord``                — passport / visa / BRP profile
* ``CASRecord``                 — Confirmation of Acceptance for Studies
* ``EngagementCheck``           — termly attendance/engagement evidence
* ``ChangeOfCircumstance``      — UKVI-reportable change with 10-day clock
* ``RightToStudyCheck``         — pre-enrolment ID verification
* ``ATASClearance``             — Academic Technology Approval Scheme

The schema is also created idempotently in ``init_db()`` (mirroring the
sibling ``student_id`` module) so the module works on a fresh DB even
before the alembic migration runs.
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

from education_system.university_system.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

UKVI_REPORT_WINDOW_DAYS = 10  # working days, but we treat as calendar days for the alert clock
VISA_EXPIRY_ALERT_THRESHOLDS = (90, 60, 30, 14, 7)  # days

# Subjects that typically need ATAS — the actual canonical list lives on
# gov.uk and changes; we keep a starter list and let admins toggle the flag
# per student/module from the GUI.
ATAS_RESTRICTED_PREFIXES = ("CIS200", "CIS300")  # CS-track + DS-track research-flavoured codes

VISA_STATUSES = ("pending", "active", "expired", "withdrawn", "curtailed", "completed")
CAS_STATUSES = ("issued", "used", "withdrawn", "expired")
COC_STATUSES = ("pending", "reported", "acknowledged", "closed")
COC_TYPES = (
    "withdrawal",
    "suspension",
    "interruption",
    "transfer",
    "completion_early",
    "missed_engagement",
    "address_change",
    "name_change",
    "course_length_change",
)


# ---------------------------------------------------------------------------
# Schema (idempotent)
# ---------------------------------------------------------------------------

_DDL = [
    """CREATE TABLE IF NOT EXISTS visa_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL UNIQUE,
        nationality TEXT,
        passport_number TEXT,
        passport_expiry TEXT,
        visa_type TEXT NOT NULL DEFAULT 'student_route',
        visa_number TEXT,
        visa_start_date TEXT,
        visa_expiry_date TEXT,
        brp_number TEXT,
        brp_expiry_date TEXT,
        sponsor_licence_ref TEXT,
        atas_required INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'pending',
        notes TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS idx_visa_records_status ON visa_records(status)",
    "CREATE INDEX IF NOT EXISTS idx_visa_records_visa_expiry ON visa_records(visa_expiry_date)",
    """CREATE TABLE IF NOT EXISTS cas_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        cas_number TEXT NOT NULL UNIQUE,
        issued_at TEXT NOT NULL DEFAULT (datetime('now')),
        issued_by INTEGER,
        programme TEXT,
        course_start_date TEXT,
        course_end_date TEXT,
        tuition_fee_gbp REAL,
        tuition_fee_paid_gbp REAL DEFAULT 0,
        living_costs_gbp REAL,
        status TEXT NOT NULL DEFAULT 'issued',
        withdrawn_reason TEXT,
        withdrawn_at TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_cas_records_student_id ON cas_records(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_cas_records_status ON cas_records(status)",
    """CREATE TABLE IF NOT EXISTS visa_engagement_checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        check_date TEXT NOT NULL DEFAULT (date('now')),
        term TEXT,
        method TEXT,
        evidence TEXT,
        outcome TEXT NOT NULL DEFAULT 'engaged',
        recorded_by INTEGER,
        recorded_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS idx_engage_student_id ON visa_engagement_checks(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_engage_outcome ON visa_engagement_checks(outcome)",
    """CREATE TABLE IF NOT EXISTS visa_change_of_circumstance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        change_type TEXT NOT NULL,
        occurred_on TEXT NOT NULL DEFAULT (date('now')),
        details TEXT,
        ukvi_report_due TEXT,
        ukvi_reported_at TEXT,
        ukvi_report_reference TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        recorded_by INTEGER,
        recorded_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS idx_coc_student_id ON visa_change_of_circumstance(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_coc_status ON visa_change_of_circumstance(status)",
    """CREATE TABLE IF NOT EXISTS right_to_study_checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        checked_at TEXT NOT NULL DEFAULT (datetime('now')),
        checked_by INTEGER,
        method TEXT,
        documents_seen TEXT,
        outcome TEXT NOT NULL DEFAULT 'pass',
        notes TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_rts_student_id ON right_to_study_checks(student_id)",
    """CREATE TABLE IF NOT EXISTS atas_clearances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        module_code TEXT,
        certificate_number TEXT,
        issued_on TEXT,
        expires_on TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        notes TEXT,
        recorded_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS idx_atas_student_id ON atas_clearances(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_atas_status ON atas_clearances(status)",
    """CREATE TABLE IF NOT EXISTS visa_expiry_alert_log (
        student_id      TEXT    NOT NULL,
        threshold_days  INTEGER NOT NULL,
        sent_at         TEXT    NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (student_id, threshold_days)
    )""",
]


def init_db() -> None:
    """Create all visa-sponsorship tables if they do not already exist."""
    with get_connection() as conn:
        for stmt in _DDL:
            conn.execute(stmt)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@dataclass
class VisaRecord:
    student_id: str
    nationality: Optional[str] = None
    passport_number: Optional[str] = None
    passport_expiry: Optional[str] = None
    visa_type: str = "student_route"
    visa_number: Optional[str] = None
    visa_start_date: Optional[str] = None
    visa_expiry_date: Optional[str] = None
    brp_number: Optional[str] = None
    brp_expiry_date: Optional[str] = None
    sponsor_licence_ref: Optional[str] = None
    atas_required: bool = False
    status: str = "pending"
    notes: Optional[str] = None
    id: Optional[int] = None


@dataclass
class CASRecord:
    student_id: str
    cas_number: str
    programme: Optional[str] = None
    course_start_date: Optional[str] = None
    course_end_date: Optional[str] = None
    tuition_fee_gbp: Optional[float] = None
    living_costs_gbp: Optional[float] = None
    status: str = "issued"
    id: Optional[int] = None


@dataclass
class EngagementCheck:
    student_id: str
    check_date: str
    term: Optional[str] = None
    method: Optional[str] = None
    evidence: Optional[str] = None
    outcome: str = "engaged"
    id: Optional[int] = None


@dataclass
class ChangeOfCircumstance:
    student_id: str
    change_type: str
    occurred_on: str
    details: Optional[str] = None
    ukvi_report_due: Optional[str] = None
    status: str = "pending"
    id: Optional[int] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today() -> str:
    return date.today().isoformat()


def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def generate_cas_number() -> str:
    """Generate a CAS-style reference. UKVI CAS numbers are 14 chars.

    Format: ``E4U`` (institution prefix) + ``YY`` (issue year) + 9 hex digits.
    Real CAS numbers come from SMS (Sponsor Management System); this is
    only used when the GUI auto-generates a placeholder for internal use.
    """
    return f"E4U{datetime.now().strftime('%y')}{secrets.token_hex(5)[:9].upper()}"


def is_atas_required_for_module(module_code: str) -> bool:
    """Return True when a module's code matches a restricted prefix.

    The official list is at gov.uk/guidance/academic-technology-approval-
    scheme. Admins can override per-record from the GUI."""
    if not module_code:
        return False
    return any(module_code.startswith(p) for p in ATAS_RESTRICTED_PREFIXES)


# ---------------------------------------------------------------------------
# Visa records
# ---------------------------------------------------------------------------

def upsert_visa_record(record: VisaRecord) -> int:
    """Create or update the visa profile for a student. Returns row id."""
    init_db()
    with get_connection() as conn:
        cur = conn.execute(
            "SELECT id FROM visa_records WHERE student_id = ?", (record.student_id,)
        )
        row = cur.fetchone()
        if row:
            row_id = row[0] if isinstance(row, tuple) else row["id"]
            conn.execute(
                """UPDATE visa_records SET
                    nationality = ?, passport_number = ?, passport_expiry = ?,
                    visa_type = ?, visa_number = ?, visa_start_date = ?,
                    visa_expiry_date = ?, brp_number = ?, brp_expiry_date = ?,
                    sponsor_licence_ref = ?, atas_required = ?, status = ?,
                    notes = ?, updated_at = ?
                WHERE id = ?""",
                (
                    record.nationality, record.passport_number, record.passport_expiry,
                    record.visa_type, record.visa_number, record.visa_start_date,
                    record.visa_expiry_date, record.brp_number, record.brp_expiry_date,
                    record.sponsor_licence_ref, 1 if record.atas_required else 0,
                    record.status, record.notes, _now(), row_id,
                ),
            )
            return row_id
        cur = conn.execute(
            """INSERT INTO visa_records (
                student_id, nationality, passport_number, passport_expiry,
                visa_type, visa_number, visa_start_date, visa_expiry_date,
                brp_number, brp_expiry_date, sponsor_licence_ref,
                atas_required, status, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.student_id, record.nationality, record.passport_number,
                record.passport_expiry, record.visa_type, record.visa_number,
                record.visa_start_date, record.visa_expiry_date, record.brp_number,
                record.brp_expiry_date, record.sponsor_licence_ref,
                1 if record.atas_required else 0, record.status, record.notes,
            ),
        )
        return cur.lastrowid


def get_visa_record(student_id: str) -> Optional[dict]:
    init_db()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM visa_records WHERE student_id = ?", (student_id,)
        ).fetchone()
        return dict(row) if row else None


def list_visa_records(status: Optional[str] = None) -> list[dict]:
    init_db()
    with get_connection() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM visa_records WHERE status = ? ORDER BY visa_expiry_date",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM visa_records ORDER BY visa_expiry_date"
            ).fetchall()
        return [dict(r) for r in rows]


def list_expiring_visas(within_days: int = 90) -> list[dict]:
    """Visas/BRPs expiring within `within_days`. Drives the alert email."""
    init_db()
    cutoff = (date.today() + timedelta(days=within_days)).isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM visa_records
               WHERE status IN ('active', 'pending')
                 AND (
                    (visa_expiry_date IS NOT NULL AND visa_expiry_date <= ?)
                    OR (brp_expiry_date IS NOT NULL AND brp_expiry_date <= ?)
                 )
               ORDER BY visa_expiry_date""",
            (cutoff, cutoff),
        ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# CAS issuance
# ---------------------------------------------------------------------------

def issue_cas(
    student_id: str,
    programme: str,
    course_start_date: str,
    course_end_date: str,
    tuition_fee_gbp: float,
    living_costs_gbp: float = 0,
    issued_by: Optional[int] = None,
    cas_number: Optional[str] = None,
) -> dict:
    """Record a new CAS issuance. Returns the inserted row.

    ``cas_number`` is auto-generated when omitted (placeholder; real CAS
    references must come from SMS)."""
    init_db()
    cas_number = cas_number or generate_cas_number()
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO cas_records (
                student_id, cas_number, issued_by, programme,
                course_start_date, course_end_date,
                tuition_fee_gbp, living_costs_gbp, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'issued')""",
            (
                student_id, cas_number, issued_by, programme,
                course_start_date, course_end_date,
                tuition_fee_gbp, living_costs_gbp,
            ),
        )
        row_id = cur.lastrowid
        row = conn.execute("SELECT * FROM cas_records WHERE id = ?", (row_id,)).fetchone()
    logger.info("CAS issued %s for student %s", cas_number, student_id)
    return dict(row)


def withdraw_cas(cas_number: str, reason: str) -> bool:
    init_db()
    with get_connection() as conn:
        cur = conn.execute(
            """UPDATE cas_records SET status='withdrawn',
                  withdrawn_reason=?, withdrawn_at=?
               WHERE cas_number = ? AND status != 'withdrawn'""",
            (reason, _now(), cas_number),
        )
        return cur.rowcount > 0


def list_cas_for_student(student_id: str) -> list[dict]:
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM cas_records WHERE student_id = ? ORDER BY issued_at DESC",
            (student_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Engagement checks
# ---------------------------------------------------------------------------

def record_engagement_check(
    student_id: str,
    term: str,
    method: str,
    outcome: str = "engaged",
    evidence: Optional[str] = None,
    recorded_by: Optional[int] = None,
    check_date: Optional[str] = None,
) -> int:
    """Log a sponsor-duty engagement check (e.g. "Term 1 attendance ≥80%")."""
    init_db()
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO visa_engagement_checks (
                student_id, check_date, term, method, evidence, outcome, recorded_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (student_id, check_date or _today(), term, method, evidence, outcome, recorded_by),
        )
        row_id = cur.lastrowid
    if outcome == "missed":
        log_change_of_circumstance(
            student_id=student_id,
            change_type="missed_engagement",
            details=f"Missed engagement at {term} check via {method}",
            recorded_by=recorded_by,
        )
    return row_id


def list_engagement_checks(student_id: str) -> list[dict]:
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM visa_engagement_checks WHERE student_id = ? "
            "ORDER BY check_date DESC", (student_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def students_with_overdue_engagement(days_since: int = 90) -> list[str]:
    """Student IDs whose most-recent engagement check is older than ``days_since``
    days (or who have no check on file but do have an active visa record)."""
    init_db()
    cutoff = (date.today() - timedelta(days=days_since)).isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT v.student_id
               FROM visa_records v
               LEFT JOIN (
                   SELECT student_id, MAX(check_date) AS last_check
                   FROM visa_engagement_checks GROUP BY student_id
               ) e ON e.student_id = v.student_id
               WHERE v.status = 'active'
                 AND (e.last_check IS NULL OR e.last_check < ?)""",
            (cutoff,),
        ).fetchall()
        return [r[0] if isinstance(r, tuple) else r["student_id"] for r in rows]


# ---------------------------------------------------------------------------
# Change of circumstance (10-day UKVI clock)
# ---------------------------------------------------------------------------

def log_change_of_circumstance(
    student_id: str,
    change_type: str,
    details: Optional[str] = None,
    occurred_on: Optional[str] = None,
    recorded_by: Optional[int] = None,
) -> int:
    """Open a UKVI report ticket. ``ukvi_report_due`` is set to occurred + 10 days."""
    init_db()
    if change_type not in COC_TYPES:
        raise ValueError(f"unknown change_type {change_type}; valid: {COC_TYPES}")
    occurred_on = occurred_on or _today()
    occurred_dt = _parse_date(occurred_on) or date.today()
    due = (occurred_dt + timedelta(days=UKVI_REPORT_WINDOW_DAYS)).isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO visa_change_of_circumstance (
                student_id, change_type, occurred_on, details,
                ukvi_report_due, status, recorded_by
            ) VALUES (?, ?, ?, ?, ?, 'pending', ?)""",
            (student_id, change_type, occurred_on, details, due, recorded_by),
        )
        return cur.lastrowid


def mark_coc_reported(coc_id: int, ukvi_reference: str) -> bool:
    init_db()
    with get_connection() as conn:
        cur = conn.execute(
            """UPDATE visa_change_of_circumstance
               SET status='reported', ukvi_reported_at=?, ukvi_report_reference=?
               WHERE id = ?""",
            (_now(), ukvi_reference, coc_id),
        )
        return cur.rowcount > 0


def list_pending_coc(only_overdue: bool = False) -> list[dict]:
    init_db()
    with get_connection() as conn:
        if only_overdue:
            rows = conn.execute(
                """SELECT * FROM visa_change_of_circumstance
                   WHERE status = 'pending' AND ukvi_report_due < ?
                   ORDER BY ukvi_report_due""",
                (_today(),),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM visa_change_of_circumstance
                   WHERE status = 'pending'
                   ORDER BY ukvi_report_due"""
            ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Right-to-study checks
# ---------------------------------------------------------------------------

def record_right_to_study_check(
    student_id: str,
    method: str,
    documents_seen: str,
    outcome: str = "pass",
    notes: Optional[str] = None,
    checked_by: Optional[int] = None,
) -> int:
    init_db()
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO right_to_study_checks (
                student_id, checked_by, method, documents_seen, outcome, notes
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (student_id, checked_by, method, documents_seen, outcome, notes),
        )
        return cur.lastrowid


def has_passing_right_to_study(student_id: str) -> bool:
    init_db()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM right_to_study_checks "
            "WHERE student_id = ? AND outcome = 'pass' LIMIT 1",
            (student_id,),
        ).fetchone()
        return row is not None


# ---------------------------------------------------------------------------
# ATAS clearance
# ---------------------------------------------------------------------------

def record_atas_clearance(
    student_id: str,
    module_code: Optional[str],
    certificate_number: Optional[str],
    issued_on: Optional[str],
    expires_on: Optional[str],
    status: str = "cleared",
    notes: Optional[str] = None,
) -> int:
    init_db()
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO atas_clearances (
                student_id, module_code, certificate_number,
                issued_on, expires_on, status, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (student_id, module_code, certificate_number,
             issued_on, expires_on, status, notes),
        )
        return cur.lastrowid


def has_valid_atas(student_id: str, module_code: Optional[str] = None) -> bool:
    init_db()
    with get_connection() as conn:
        if module_code:
            row = conn.execute(
                """SELECT expires_on FROM atas_clearances
                   WHERE student_id = ? AND module_code = ? AND status = 'cleared'
                   ORDER BY recorded_at DESC LIMIT 1""",
                (student_id, module_code),
            ).fetchone()
        else:
            row = conn.execute(
                """SELECT expires_on FROM atas_clearances
                   WHERE student_id = ? AND status = 'cleared'
                   ORDER BY recorded_at DESC LIMIT 1""",
                (student_id,),
            ).fetchone()
        if not row:
            return False
        expires = row[0] if isinstance(row, tuple) else row["expires_on"]
        if not expires:
            return True
        return _parse_date(expires) is None or _parse_date(expires) >= date.today()


def atas_required_for_student_modules(student_id: str) -> list[str]:
    """Return module codes the student is enrolled on that need ATAS."""
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT module_code FROM student_modules WHERE student_id = ?",
            (student_id,),
        ).fetchall()
    codes = [r[0] if isinstance(r, tuple) else r["module_code"] for r in rows]
    return [c for c in codes if is_atas_required_for_module(c)]


# ---------------------------------------------------------------------------
# Email notifications
# ---------------------------------------------------------------------------

def _send_template(template_name: str, email: str, vars_: dict) -> bool:
    """Best-effort wrapper around the unified email service."""
    try:
        from education_system.university_system.infrastructure.email.email_service import (
            send_template_email,
        )
        return bool(send_template_email(template_name, email, vars_))
    except Exception as exc:
        logger.warning("visa-email %s -> %s failed: %s", template_name, email, exc)
        return False


def notify_cas_issued(student_id: str, email: str, cas: dict, first_name: str = "") -> bool:
    return _send_template(
        "cas_issued",
        email,
        {
            "first_name": first_name,
            "student_id": student_id,
            "cas_number": cas.get("cas_number", ""),
            "programme": cas.get("programme", ""),
            "course_start_date": cas.get("course_start_date", ""),
            "course_end_date": cas.get("course_end_date", ""),
            "tuition_fee_gbp": f"{cas.get('tuition_fee_gbp', 0):.2f}",
        },
    )


def notify_visa_expiry(student_id: str, email: str, visa: dict, days_left: int,
                        first_name: str = "") -> bool:
    return _send_template(
        "visa_expiry_warning",
        email,
        {
            "first_name": first_name,
            "student_id": student_id,
            "visa_number": visa.get("visa_number") or "",
            "visa_expiry_date": visa.get("visa_expiry_date") or "",
            "brp_number": visa.get("brp_number") or "",
            "brp_expiry_date": visa.get("brp_expiry_date") or "",
            "days_left": str(days_left),
        },
    )


def notify_change_of_circumstance(student_id: str, email: str, coc: dict,
                                   first_name: str = "") -> bool:
    return _send_template(
        "change_of_circumstance_recorded",
        email,
        {
            "first_name": first_name,
            "student_id": student_id,
            "change_type": coc.get("change_type", ""),
            "occurred_on": coc.get("occurred_on", ""),
            "details": coc.get("details", "") or "",
            "ukvi_report_due": coc.get("ukvi_report_due", "") or "",
        },
    )


def notify_right_to_study_required(student_id: str, email: str, first_name: str = "") -> bool:
    return _send_template(
        "right_to_study_check_required",
        email,
        {"first_name": first_name, "student_id": student_id},
    )


# ---------------------------------------------------------------------------
# Bulk alert run
# ---------------------------------------------------------------------------

def _student_email_lookup(student_ids: list[str]) -> dict[str, tuple[str, str]]:
    if not student_ids:
        return {}
    placeholders = ",".join("?" for _ in student_ids)
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT student_id, email_address, first_name "
            f"FROM students WHERE student_id IN ({placeholders})",
            student_ids,
        ).fetchall()
    out: dict[str, tuple[str, str]] = {}
    for r in rows:
        if isinstance(r, tuple):
            sid, email, first = r
        else:
            sid, email, first = r["student_id"], r["email_address"], r["first_name"]
        out[sid] = (email or "", first or "")
    return out


def _bucket_for_days_left(days_left: int) -> Optional[int]:
    """Map ``days_left`` to the smallest matching alert threshold.

    e.g. 95 → None (no alert yet), 89 → 90, 31 → 60, 14 → 14.
    Thresholds are descending, smallest match wins."""
    for t in sorted(VISA_EXPIRY_ALERT_THRESHOLDS):
        if days_left <= t:
            return t
    return None


def _alert_already_sent(student_id: str, threshold: int) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM visa_expiry_alert_log "
            "WHERE student_id = ? AND threshold_days = ?",
            (student_id, threshold),
        ).fetchone()
        return row is not None


def _mark_alert_sent(student_id: str, threshold: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO visa_expiry_alert_log (student_id, threshold_days) "
            "VALUES (?, ?)",
            (student_id, threshold),
        )


def run_scheduled_visa_expiry_alerts() -> int:
    """Daily scheduler entry point.

    For every active visa expiring within the largest configured threshold,
    sends one email per (student, threshold) bucket and never re-sends the
    same combination. Designed to be called once per day from the email
    scheduler. Returns the number of emails sent on this run."""
    init_db()
    largest = max(VISA_EXPIRY_ALERT_THRESHOLDS)
    candidates = list_expiring_visas(within_days=largest)
    if not candidates:
        return 0

    contacts = _student_email_lookup([v["student_id"] for v in candidates])
    today = date.today()
    sent = 0
    for v in candidates:
        sid = v["student_id"]
        email, first = contacts.get(sid, ("", ""))
        if not email:
            continue
        # Pick the soonest of visa / BRP expiry
        soonest = min(
            (d for d in (_parse_date(v.get("visa_expiry_date")),
                          _parse_date(v.get("brp_expiry_date"))) if d),
            default=None,
        )
        if not soonest:
            continue
        days_left = (soonest - today).days
        if days_left < 0:
            continue  # already expired — handled by curtailment workflow
        bucket = _bucket_for_days_left(days_left)
        if bucket is None:
            continue
        if _alert_already_sent(sid, bucket):
            continue
        if notify_visa_expiry(sid, email, v, days_left, first_name=first):
            _mark_alert_sent(sid, bucket)
            sent += 1
    return sent


def run_visa_expiry_alerts(threshold_days: int = 90) -> int:
    """Send visa-expiry warning emails for visas expiring inside ``threshold_days``.

    Returns the number of emails sent. Safe to call repeatedly; deduping
    across runs is left to the email layer."""
    expiring = list_expiring_visas(within_days=threshold_days)
    if not expiring:
        return 0
    contacts = _student_email_lookup([v["student_id"] for v in expiring])
    sent = 0
    today = date.today()
    for v in expiring:
        sid = v["student_id"]
        email, first = contacts.get(sid, ("", ""))
        if not email:
            continue
        # Pick the soonest of visa / BRP expiry
        candidates = [_parse_date(v.get("visa_expiry_date")), _parse_date(v.get("brp_expiry_date"))]
        soonest = min((d for d in candidates if d), default=None)
        days_left = (soonest - today).days if soonest else threshold_days
        if notify_visa_expiry(sid, email, v, days_left, first_name=first):
            sent += 1
    return sent


__all__ = [
    "VisaRecord", "CASRecord", "EngagementCheck", "ChangeOfCircumstance",
    "VISA_STATUSES", "CAS_STATUSES", "COC_STATUSES", "COC_TYPES",
    "VISA_EXPIRY_ALERT_THRESHOLDS", "UKVI_REPORT_WINDOW_DAYS",
    "init_db", "generate_cas_number", "is_atas_required_for_module",
    "upsert_visa_record", "get_visa_record", "list_visa_records",
    "list_expiring_visas",
    "issue_cas", "withdraw_cas", "list_cas_for_student",
    "record_engagement_check", "list_engagement_checks",
    "students_with_overdue_engagement",
    "log_change_of_circumstance", "mark_coc_reported", "list_pending_coc",
    "record_right_to_study_check", "has_passing_right_to_study",
    "record_atas_clearance", "has_valid_atas",
    "atas_required_for_student_modules",
    "notify_cas_issued", "notify_visa_expiry",
    "notify_change_of_circumstance", "notify_right_to_study_required",
    "run_visa_expiry_alerts", "run_scheduled_visa_expiry_alerts",
]
