"""My Mitigating Circumstances: the student side of MC/EC claims.

The staff window (Mitigating Circumstances, admin/staff only) takes any
student id. Here the student id is fixed to the signed-in student, every
read is filtered to it, and every write checks the claim belongs to them
first, so a student can submit, add evidence to and withdraw only their own
claims. Panel decisions, verification and extensions stay with staff; the
student sees the outcome (claim status and any extension granted).

The service is passed in so callers (GUI, CLI, tests) share one rule set.
"""

from __future__ import annotations

from datetime import date

from education_system.systems.university.application.self_service.identity import SelfServiceError

#: Statuses in which the student may still withdraw or add evidence.
OPEN_STATUSES = ("submitted", "evidence_pending", "under_review")
#: Evidence the student may describe; staff verify it.
EVIDENCE_TYPES = ("medical_note", "death_certificate", "police_report",
                  "letter_of_support", "it_incident_ref", "other")


def _iso(value: str | None, label: str) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise SelfServiceError(f"{label} must be a date in YYYY-MM-DD form.") from exc


def own_claims(service, student_id) -> list[dict]:
    """The student's claims, newest first."""
    return service.list_claims(student_id=str(student_id))


def own_claim(service, student_id, claim_id) -> dict:
    """One claim, refusing any that is not the student's own."""
    claim = service.get_claim(int(claim_id))
    if not claim or str(claim.get("student_id")) != str(student_id):
        raise SelfServiceError(f"You have no claim #{claim_id}.")
    return claim


def validate_claim(data: dict, valid_grounds) -> dict:
    """Clean the student's form: grounds from the list, a description, and an
    ordered affected period."""
    grounds = (data.get("grounds") or "").strip()
    if grounds not in valid_grounds:
        raise SelfServiceError("Choose the grounds for your claim from the list.")
    description = (data.get("description") or "").strip()
    if not description:
        raise SelfServiceError("Please describe what happened.")
    start = _iso(data.get("period_start"), "Period start")
    end = _iso(data.get("period_end"), "Period end")
    if start and end and end < start:
        raise SelfServiceError("The affected period ends before it starts.")
    return {
        "module_code": (data.get("module_code") or "").strip().upper() or None,
        "assessment_ref": (data.get("assessment_ref") or "").strip() or None,
        "grounds": grounds,
        "description": description,
        "period_start": start,
        "period_end": end,
        "impact_statement": (data.get("impact_statement") or "").strip() or None,
        "requested_remedy": (data.get("requested_remedy") or "").strip() or None,
    }


def submit_own_claim(service, student_id, username: str, data: dict, valid_grounds) -> int:
    """Submit a claim for the signed-in student; returns the claim id."""
    clean = validate_claim(data, valid_grounds)
    return service.submit_claim(student_id=str(student_id), submitted_by=username, **clean)


def add_own_evidence(service, student_id, claim_id, evidence_type: str,
                     description: str, document_ref: str | None = None) -> int:
    """Describe evidence for one of the student's open claims."""
    claim = own_claim(service, student_id, claim_id)
    if claim.get("status") not in OPEN_STATUSES:
        raise SelfServiceError(
            f"Claim #{claim_id} is {claim.get('status')}; evidence can no longer be added.")
    if evidence_type not in EVIDENCE_TYPES:
        raise SelfServiceError("Choose the type of evidence from the list.")
    if not (description or "").strip():
        raise SelfServiceError("Please say what the evidence is.")
    return service.add_evidence(claim_id=int(claim_id), evidence_type=evidence_type,
                                description=description.strip(),
                                document_ref=(document_ref or "").strip() or None)


def withdraw_own_claim(service, student_id, claim_id) -> None:
    """Withdraw one of the student's claims before a decision."""
    claim = own_claim(service, student_id, claim_id)
    if claim.get("status") not in OPEN_STATUSES:
        raise SelfServiceError(
            f"Claim #{claim_id} is {claim.get('status')} and can no longer be withdrawn.")
    service.withdraw_claim(int(claim_id))


def own_evidence(service, student_id, claim_id) -> list[dict]:
    own_claim(service, student_id, claim_id)
    return service.list_evidence(int(claim_id))


def own_extensions(service, student_id) -> list[dict]:
    """Deadline extensions granted to the student."""
    return service.list_extensions(student_id=str(student_id))
