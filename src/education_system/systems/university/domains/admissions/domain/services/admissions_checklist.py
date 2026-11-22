"""Conditions & Documents: the casework that lets an application enrol.

``readiness_issues`` refuses conversion while any offer condition or
required document is open, and until the status is ``ready_to_enrol``
with a right-to-study decision on file. This module is the staff side of
each of those gates, built on the lifecycle and policy functions that
already existed but that nothing called:

* conditions - :func:`satisfy_condition` (``lifecycle.satisfy_condition``
  with an evidence note) or :func:`waive_condition` with a reason;
* documents - :func:`verify_document` (``lifecycle.verify_requirement``),
  attaching an uploaded file or a file already on the application;
* the policy decisions - :func:`record_right_to_study`,
  :func:`record_deposit` (``admissions_policies``);
* the status - :func:`advance_status` along ``ALLOWED_TRANSITIONS``;
* :func:`convert` - ``lifecycle.convert_to_student``.

Each action requires admissions staff (``admissions_casework.require_manager``)
and is written to the application's casework audit trail.
"""

from __future__ import annotations

import logging
from typing import Any

from education_system.systems.university.domains.admissions.domain.services import (
    admissions_casework as casework,
)
from education_system.systems.university.domains.admissions.domain.services import (
    admissions_lifecycle as lifecycle,
)
from education_system.systems.university.domains.admissions.domain.services import (
    admissions_postgraduate as postgraduate,
)
from education_system.systems.university.domains.admissions.domain.services import (
    admissions_sponsors as sponsors,
)
from education_system.systems.university.domains.admissions.domain.services.admissions_policies import (
    DepositPolicy,
    RightToStudyPolicy,
)
from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)
from education_system.systems.university.services.boundary_errors import (
    AdmissionsBoundaryError,
)

logger = logging.getLogger(__name__)

CONDITION_TYPES = ("academic", "english_language", "deposit", "sponsorship",
                   "right_to_study", "dbs_check", "occupational_health", "other")
REQUIREMENT_TYPES = ("transcript", "certificate", "identity", "english_language",
                     "personal_statement", "portfolio", "dbs_check", "other")

_CONDITION_COLUMNS = (("decided_by", "TEXT"), ("waiver_reason", "TEXT"))
_DECISION_TABLES = {
    "right_to_study": "admission_right_to_study_decisions",
    "deposit": "admission_deposit_decisions",
    "sponsorship": "admission_sponsorship_decisions",
}


def _ensure_condition_columns(conn) -> None:
    """Who satisfied or waived a condition, and why it was waived."""
    have = {r[1] for r in conn.execute("PRAGMA table_info(admission_conditions)")}
    for column, kind in _CONDITION_COLUMNS:
        if column not in have:
            # db-audit: ignore[DBW001] - literal column list above
            conn.execute(f"ALTER TABLE admission_conditions ADD COLUMN {column} {kind}")


def _has_table(conn, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (name,)).fetchone() is not None


def _decisions(conn, application_id: int) -> dict[str, dict | None]:
    out: dict[str, dict | None] = {}
    for key, table in _DECISION_TABLES.items():
        if not _has_table(conn, table):
            out[key] = None
            continue
        # db-audit: ignore[DBW001] - table name from the literal map above
        row = conn.execute(f"SELECT * FROM {table} WHERE application_id = ?",
                           (int(application_id),)).fetchone()
        out[key] = dict(row) if row else None
    return out


def _requirement_rows(conn, application_id: int) -> list[dict]:
    return [dict(r) for r in conn.execute(
        """SELECT r.*, d.document_name, d.original_filename
             FROM admission_requirements r
             LEFT JOIN documents d ON d.document_id = r.evidence_document_id
            WHERE r.application_id = ? ORDER BY r.requirement_id""",
        (int(application_id),)).fetchall()]


# ── Read model ──────────────────────────────────────────────────────

def checklist(application_id: int) -> dict:
    """Everything the Conditions & Documents panel shows for one application."""
    aid = int(application_id)
    with transaction() as conn:
        _ensure_condition_columns(conn)
        casework.ensure_audit(conn)
        app = dict(casework.application_row(conn, aid))
        conditions = [dict(r) for r in conn.execute(
            "SELECT * FROM admission_conditions WHERE application_id = ? "
            "ORDER BY condition_id", (aid,)).fetchall()]
        requirements = _requirement_rows(conn, aid)
        decisions = _decisions(conn, aid)
    status = (app.get("status") or lifecycle.SUBMITTED).strip().lower()
    try:
        issues = lifecycle.readiness_issues(aid)
    except Exception as exc:
        logger.exception("Readiness check failed for application %s", aid)
        issues = [f"readiness could not be evaluated: {exc}"]
    converted = bool(app.get("converted_student_id"))
    return {
        "application": app,
        "conditions": conditions,
        "requirements": requirements,
        "documents": casework.application_documents(aid),
        "decisions": decisions,
        "has_deposit_condition": any(c["condition_type"] == "deposit" for c in conditions),
        "has_sponsorship_condition": any(
            c["condition_type"] == "sponsorship" for c in conditions),
        "sponsor": sponsors.admissions_sponsor_for(application_id=aid),
        "postgraduate": postgraduate.is_postgraduate(app.get("application_type")),
        "issues": [] if converted else issues,
        "ready": not issues and not converted,
        "converted_student_id": app.get("converted_student_id"),
        "next_statuses": sorted(lifecycle.ALLOWED_TRANSITIONS.get(status, frozenset())
                                - {lifecycle.ENROLLED}),
        "audit": casework.audit_trail(aid),
    }


def applications(*, search: str = "", limit: int = 300) -> list[dict]:
    """Applications to pick from, newest first, with a one-word readiness hint."""
    like = f"%{(search or '').strip()}%"
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT a.application_id, a.application_type, a.program_applied,
                      a.academic_year, a.status, a.converted_student_id,
                      p.first_name, p.last_name, p.email,
                      (SELECT COUNT(*) FROM admission_conditions c
                        WHERE c.application_id = a.application_id
                          AND c.status NOT IN ('satisfied', 'superseded', 'waived'))
                          AS open_conditions,
                      (SELECT COUNT(*) FROM admission_requirements r
                        WHERE r.application_id = a.application_id
                          AND r.required = 1 AND r.status != 'verified')
                          AS open_requirements
                 FROM admission_applications a
                 LEFT JOIN admission_prospects p ON p.prospect_id = a.prospect_id
                WHERE (? = '%%' OR p.first_name LIKE ? OR p.last_name LIKE ?
                       OR p.email LIKE ? OR a.program_applied LIKE ?
                       OR CAST(a.application_id AS TEXT) = ?)
                ORDER BY a.application_id DESC LIMIT ?""",
            (like, like, like, like, like, (search or "").strip(), int(limit)),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Conditions ─────────────────────────────────────────────────────

def _condition(conn, condition_id: int):
    _ensure_condition_columns(conn)
    row = conn.execute("SELECT * FROM admission_conditions WHERE condition_id = ?",
                       (int(condition_id),)).fetchone()
    if row is None:
        raise AdmissionsBoundaryError(f"Condition ID {condition_id} does not exist.")
    return row


def _open_condition(condition_id: int):
    with transaction() as conn:
        row = _condition(conn, condition_id)
    if row["status"] in lifecycle.CLOSED_CONDITION_STATES:
        raise AdmissionsBoundaryError(f"This condition is already {row['status']}")
    return row


def add_condition(viewer: Any, application_id: int, condition_type: str,
                  description: str, *, due_date: str = "", amount: float | None = None,
                  currency: str = "", sponsor_name: str = "") -> int:
    actor = casework.require_manager(viewer)
    if condition_type not in CONDITION_TYPES or not (description or "").strip():
        raise AdmissionsBoundaryError("Choose a condition type and describe the condition")
    condition_id = lifecycle.add_condition(
        application_id, condition_type, description.strip(), amount=amount,
        currency=currency, sponsor_name=sponsor_name, due_date=due_date)
    with transaction() as conn:
        casework.audit(conn, application_id, "condition_added", actor,
                       target_type="condition", target_id=condition_id,
                       detail={"type": condition_type, "description": description.strip()})
    return condition_id


def satisfy_condition(viewer: Any, condition_id: int, evidence_note: str) -> None:
    """Mark a condition met, recording what showed it was met."""
    actor = casework.require_manager(viewer)
    note = (evidence_note or "").strip()
    if not note:
        raise AdmissionsBoundaryError("Record the evidence that the condition was met")
    row = _open_condition(condition_id)
    lifecycle.satisfy_condition(int(condition_id), evidence_reference=note)
    with transaction() as conn:
        conn.execute("UPDATE admission_conditions SET decided_by = ? WHERE condition_id = ?",
                     (actor, int(condition_id)))
        casework.audit(conn, row["application_id"], "condition_satisfied", actor,
                       target_type="condition", target_id=condition_id,
                       detail={"evidence": note, "description": row["description"]})


def waive_condition(viewer: Any, condition_id: int, reason: str) -> None:
    """Set a condition aside. Needs a reason; the reason is kept on the row."""
    actor = casework.require_manager(viewer)
    reason = (reason or "").strip()
    if not reason:
        raise AdmissionsBoundaryError("A reason is required to waive a condition")
    row = _open_condition(condition_id)
    with transaction() as conn:
        conn.execute(
            """UPDATE admission_conditions
                  SET status = 'waived', satisfied_at = ?, waiver_reason = ?,
                      decided_by = ?
                WHERE condition_id = ?""",
            (casework.now(), reason, actor, int(condition_id)))
        casework.audit(conn, row["application_id"], "condition_waived", actor,
                       target_type="condition", target_id=condition_id,
                       detail={"reason": reason, "description": row["description"]})


# ── Documents ──────────────────────────────────────────────────────

def add_requirement(viewer: Any, application_id: int, requirement_type: str,
                    description: str, *, due_date: str = "", required: bool = True) -> int:
    actor = casework.require_manager(viewer)
    if requirement_type not in REQUIREMENT_TYPES or not (description or "").strip():
        raise AdmissionsBoundaryError("Choose a document type and describe what is needed")
    requirement_id = lifecycle.add_requirement(
        application_id, requirement_type, description.strip(), due_date=due_date,
        required=required)
    with transaction() as conn:
        casework.audit(conn, application_id, "requirement_added", actor,
                       target_type="requirement", target_id=requirement_id,
                       detail={"type": requirement_type, "description": description.strip()})
    return requirement_id


def verify_document(viewer: Any, requirement_id: int, *, file_path: str | None = None,
                    document_id: int | None = None, notes: str = "") -> int | None:
    """Verify a required document, attaching the evidence.

    ``file_path`` uploads a new file onto the application; ``document_id``
    uses one already there. Verifying without either needs a note saying
    how it was seen (e.g. original sighted at the counter).
    """
    actor = casework.require_manager(viewer)
    notes = (notes or "").strip()
    if not file_path and document_id is None and not notes:
        raise AdmissionsBoundaryError(
            "Attach the document, choose one on file, or note how it was verified")
    with transaction() as conn:
        req = conn.execute("SELECT * FROM admission_requirements WHERE requirement_id = ?",
                           (int(requirement_id),)).fetchone()
        if req is None:
            raise AdmissionsBoundaryError(f"Requirement ID {requirement_id} does not exist.")
        if req["status"] == "verified":
            raise AdmissionsBoundaryError("This document is already verified")
        if file_path:
            document_id = casework.store_document(
                conn, req["application_id"], document_type=req["requirement_type"],
                uploaded_by=actor, source_path=file_path, verified=True,
                document_name=req["description"])
        elif document_id is not None:
            _verify_existing_document(conn, req["application_id"], int(document_id), actor)
    lifecycle.verify_requirement(int(requirement_id), verified_by=actor,
                                 document_id=document_id, notes=notes)
    with transaction() as conn:
        casework.audit(conn, req["application_id"], "document_verified", actor,
                       target_type="requirement", target_id=requirement_id,
                       detail={"document_id": document_id, "notes": notes})
    return document_id


def _verify_existing_document(conn, application_id: int, document_id: int, actor: str) -> None:
    doc = conn.execute(
        "SELECT document_id FROM documents WHERE document_id = ? "
        "AND reference_type = 'application' AND reference_id = ?",
        (document_id, str(int(application_id)))).fetchone()
    if doc is None:
        raise AdmissionsBoundaryError("That document is not on this application")
    conn.execute(
        "UPDATE documents SET verification_status = 'verified', verification_date = ?, "
        "verified_by = ? WHERE document_id = ?", (casework.now(), actor, document_id))


# ── Policy decisions, status and conversion ───────────────────────

def record_right_to_study(viewer: Any, application_id: int, route: str,
                          evidence_reference: str, *, valid_until: str | None = None) -> str:
    actor = casework.require_manager(viewer)
    status = RightToStudyPolicy().approve(
        int(application_id), route=route, evidence_reference=evidence_reference,
        actor_id=actor, valid_until=valid_until or None)
    with transaction() as conn:
        casework.audit(conn, application_id, "right_to_study_recorded", actor,
                       target_type="right_to_study", target_id=application_id,
                       detail={"route": route, "evidence": evidence_reference,
                               "valid_until": valid_until, "status": status})
    return status


def record_deposit(viewer: Any, application_id: int, *, required_amount: float,
                   received_amount: float, payment_reference: str,
                   currency: str = "GBP") -> str:
    actor = casework.require_manager(viewer)
    if not (payment_reference or "").strip():
        raise AdmissionsBoundaryError("A payment reference is required")
    status = DepositPolicy(float(required_amount), currency).decide(
        int(application_id), received_amount=float(received_amount),
        payment_reference=payment_reference.strip(), actor_id=actor)
    with transaction() as conn:
        casework.audit(conn, application_id, "deposit_recorded", actor,
                       target_type="deposit", target_id=application_id,
                       detail={"required": required_amount, "received": received_amount,
                               "reference": payment_reference, "status": status})
    return status


def advance_status(viewer: Any, application_id: int, to_status: str, reason: str = "") -> str:
    """Move the application one step along the lifecycle. Enrolment itself
    happens only through :func:`convert`."""
    actor = casework.require_manager(viewer)
    if to_status == lifecycle.ENROLLED:
        raise AdmissionsBoundaryError("Use Convert to Student to enrol")
    lifecycle.transition(int(application_id), to_status, reason=reason or "", actor_id=actor)
    with transaction() as conn:
        casework.audit(conn, application_id, "status_changed", actor,
                       target_type="application", target_id=application_id,
                       detail={"to": to_status, "reason": reason})
    return to_status


def convert(viewer: Any, application_id: int) -> str:
    """Convert a ready applicant into a student. Refuses with the reasons
    when anything is still open."""
    actor = casework.require_manager(viewer)
    issues = lifecycle.readiness_issues(int(application_id))
    if issues and not lifecycle.get_application(int(application_id)).get("converted_student_id"):
        raise AdmissionsBoundaryError("Not ready to enrol: " + "; ".join(issues))
    student_id = lifecycle.convert_to_student(int(application_id), actor_id=actor)
    with transaction() as conn:
        casework.audit(conn, application_id, "converted_to_student", actor,
                       target_type="application", target_id=application_id,
                       detail={"student_id": student_id})
    return student_id


__all__ = [
    "CONDITION_TYPES", "REQUIREMENT_TYPES", "add_condition", "add_requirement",
    "advance_status", "applications", "checklist", "convert", "record_deposit",
    "record_right_to_study", "satisfy_condition", "verify_document", "waive_condition",
]
