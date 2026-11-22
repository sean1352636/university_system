"""Third-party sponsors recorded by admissions.

A sponsorship *condition* has always carried only a ``sponsor_name``. That
stays; this module adds the sponsor itself to the application - the
organisation, who to contact, the sponsor's own reference and the sponsor
letter (stored as an application document) - so the record outlives the
offer and finance can bill the right body after enrolment.

Finance reads it through :func:`admissions_sponsor_for` (by student id
once converted, or by application id) and never touches the table, so
the shape of ``admission_sponsors`` stays admissions' own business.
"""

from __future__ import annotations

import logging
from typing import Any

from education_system.systems.university.domains.admissions.domain.services import (
    admissions_casework as casework,
)
from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)
from education_system.systems.university.services.boundary_errors import (
    AdmissionsBoundaryError,
)

logger = logging.getLogger(__name__)

COVERS = ("tuition", "tuition_and_fees", "tuition_fees_and_living", "other")

_DDL = """
CREATE TABLE IF NOT EXISTS admission_sponsors (
    sponsor_record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL,
    organisation TEXT NOT NULL,
    contact_name TEXT,
    contact_email TEXT,
    sponsor_reference TEXT,
    covers TEXT NOT NULL DEFAULT 'tuition',
    amount REAL,
    currency TEXT NOT NULL DEFAULT 'GBP',
    valid_until TEXT,
    letter_document_id INTEGER,
    status TEXT NOT NULL DEFAULT 'active',
    withdrawn_reason TEXT,
    recorded_by TEXT NOT NULL,
    recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (application_id)
        REFERENCES admission_applications(application_id) ON DELETE CASCADE
)
"""


def ensure(conn) -> None:
    conn.execute(_DDL)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_admission_sponsors_app "
                 "ON admission_sponsors(application_id, status)")
    casework.ensure_audit(conn)


def record_sponsor(viewer: Any, application_id: int, organisation: str, *,
                   contact_name: str = "", contact_email: str = "",
                   sponsor_reference: str = "", covers: str = "tuition",
                   amount: float | None = None, currency: str = "GBP",
                   valid_until: str = "", letter_path: str | None = None,
                   approve_sponsorship: bool = False) -> int:
    """Record a sponsor (and its letter) on the application.

    ``approve_sponsorship`` also records the admissions sponsorship policy
    decision that ``readiness_issues`` checks when the offer carries a
    sponsorship condition - the letter is the evidence for it.
    """
    actor = casework.require_manager(viewer)
    organisation = (organisation or "").strip()
    if not organisation:
        raise AdmissionsBoundaryError("The sponsoring organisation is required")
    if covers not in COVERS:
        raise AdmissionsBoundaryError("Covers must be one of " + ", ".join(COVERS))
    if approve_sponsorship and not (letter_path or sponsor_reference.strip()):
        raise AdmissionsBoundaryError(
            "Approving sponsorship needs the sponsor letter or the sponsor's reference")
    with transaction() as conn:
        ensure(conn)
        casework.application_row(conn, application_id)
        letter_id = None
        if letter_path:
            letter_id = casework.store_document(
                conn, application_id, document_type="sponsor_letter",
                uploaded_by=actor, source_path=letter_path, verified=True,
                document_name=f"Sponsor letter: {organisation}")
        record_id = int(conn.execute(
            """INSERT INTO admission_sponsors
                 (application_id, organisation, contact_name, contact_email,
                  sponsor_reference, covers, amount, currency, valid_until,
                  letter_document_id, recorded_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (int(application_id), organisation, contact_name.strip(),
             contact_email.strip(), sponsor_reference.strip(), covers, amount,
             (currency or "GBP").upper(), valid_until or None, letter_id, actor),
        ).lastrowid)
        casework.audit(conn, application_id, "sponsor_recorded", actor,
                       target_type="sponsor", target_id=record_id,
                       detail={"organisation": organisation, "covers": covers,
                               "amount": amount, "letter_document_id": letter_id})
    if approve_sponsorship:
        _approve_policy(actor, application_id, organisation,
                        sponsor_reference.strip() or f"letter document {letter_id}",
                        amount, valid_until)
    return record_id


def _approve_policy(actor, application_id, organisation, reference, amount,
                    valid_until) -> None:
    from education_system.systems.university.domains.admissions.domain.services.admissions_policies import (
        SponsorshipPolicy,
    )
    status = SponsorshipPolicy().approve(
        int(application_id), sponsor_name=organisation, reference=reference,
        actor_id=actor, amount=amount, valid_until=valid_until or None)
    with transaction() as conn:
        casework.audit(conn, application_id, "sponsorship_decision", actor,
                       target_type="sponsor", target_id=application_id,
                       detail={"organisation": organisation, "status": status})


def withdraw_sponsor(viewer: Any, sponsor_record_id: int, reason: str) -> None:
    actor = casework.require_manager(viewer)
    if not (reason or "").strip():
        raise AdmissionsBoundaryError("A reason is required")
    with transaction() as conn:
        ensure(conn)
        row = conn.execute("SELECT * FROM admission_sponsors WHERE sponsor_record_id = ?",
                           (int(sponsor_record_id),)).fetchone()
        if row is None:
            raise AdmissionsBoundaryError(f"Sponsor record {sponsor_record_id} does not exist")
        conn.execute("UPDATE admission_sponsors SET status = 'withdrawn', withdrawn_reason = ? "
                     "WHERE sponsor_record_id = ?", (reason.strip(), int(sponsor_record_id)))
        casework.audit(conn, row["application_id"], "sponsor_withdrawn", actor,
                       target_type="sponsor", target_id=sponsor_record_id,
                       detail={"reason": reason.strip()})


def sponsors_for_application(application_id: int) -> list[dict]:
    with get_connection() as conn:
        ensure(conn)
        return [dict(r) for r in conn.execute(
            "SELECT * FROM admission_sponsors WHERE application_id = ? "
            "ORDER BY sponsor_record_id DESC", (int(application_id),)).fetchall()]


def admissions_sponsor_for(student_id: str | None = None, *,
                           application_id: int | None = None) -> dict | None:
    """The active sponsor admissions recorded, for finance to read.

    Pass the student id (after conversion) or the application id. Returns
    the most recently recorded active sponsor as a plain dict - keys
    ``sponsor_record_id, application_id, student_id, organisation,
    contact_name, contact_email, sponsor_reference, covers, amount,
    currency, valid_until, letter_document_id, recorded_by, recorded_at,
    sponsorship_decision`` (``approved`` / ``expired`` / ``None``) - or
    ``None`` when there is no sponsor or no such application.
    """
    if student_id is None and application_id is None:
        raise ValueError("Give a student_id or an application_id")
    with get_connection() as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                            "AND name='admission_sponsors'").fetchone():
            return None
        if application_id is None:
            app = conn.execute(
                "SELECT application_id FROM admission_applications "
                "WHERE converted_student_id = ? ORDER BY application_id DESC LIMIT 1",
                (str(student_id),)).fetchone()
            if app is None:
                return None
            application_id = int(app["application_id"])
        row = conn.execute(
            """SELECT s.*, a.converted_student_id AS student_id
                 FROM admission_sponsors s
                 JOIN admission_applications a ON a.application_id = s.application_id
                WHERE s.application_id = ? AND s.status = 'active'
                ORDER BY s.sponsor_record_id DESC LIMIT 1""",
            (int(application_id),)).fetchone()
        if row is None:
            return None
        decision = None
        if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                        "AND name='admission_sponsorship_decisions'").fetchone():
            found = conn.execute(
                "SELECT status FROM admission_sponsorship_decisions WHERE application_id = ?",
                (int(application_id),)).fetchone()
            decision = found["status"] if found else None
    keys = ("sponsor_record_id", "application_id", "student_id", "organisation",
            "contact_name", "contact_email", "sponsor_reference", "covers", "amount",
            "currency", "valid_until", "letter_document_id", "recorded_by", "recorded_at")
    out = {k: row[k] for k in keys}
    out["sponsorship_decision"] = decision
    return out


__all__ = ["COVERS", "admissions_sponsor_for", "record_sponsor",
           "sponsors_for_application", "withdraw_sponsor"]
