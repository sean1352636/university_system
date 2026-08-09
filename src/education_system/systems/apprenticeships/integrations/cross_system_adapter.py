"""This system's side of the platform transition contract.

Secondary, sixth form, FE College and university all feed apprenticeships,
and a completed higher apprentice can go on to a degree. This module is
what makes those moves land as real records instead of as a note on a
transition row: the platform orchestrates, and the four methods here
answer for *this system only* — see
``platform.cross_system.adapters.base`` for the contract.

The dependency points inwards. Nothing in ``platform/`` imports this
module; it registers itself with the platform's registry when
:func:`register` is called at launch, and the platform then addresses it
by the system key ``"apprenticeships"``.

Two things are specific to work-based learning and worth stating:

**An arriving learner is an Applicant, never an apprentice.** A school
can hand over in June, but nobody is on programme until an employer has
signed and the eligibility check has passed. ``create_applicant`` creates
the record at status ``Applicant``; ``create_enrolment`` is what moves it
to ``On Programme``. Between those two the record deliberately has no
employer, and that is the normal state, not an incomplete one.

**Leaving is Withdrawn or Transferred, never a delete.** The funding and
audit trail has to survive a departure — an apprentice who left has a
claim history that the ESFA can still ask about.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from education_system.platform.cross_system.adapters import registry
from education_system.platform.cross_system.adapters.base import (
    AdapterError,
    ApplicantResult,
    EnrolmentResult,
    ExportResult,
    HandoverRequest,
    PhaseAdapter,
)
from education_system.systems.apprenticeships.infrastructure.persistence.schema import (
    connect,
    init_db,
)

logger = logging.getLogger(__name__)

SYSTEM_KEY = "apprenticeships"


# ---------------------------------------------------------------------------
# Handover → apprentice fields
# ---------------------------------------------------------------------------

def _text(value: Any) -> str | None:
    """Flatten a handover value to something a TEXT column can hold.

    Handover fields are whatever the source system chose to put in them —
    a string, a dict of sub-fields, a list of qualifications. The identity
    fields are read structurally below; everything else is narrative that
    a tutor reads, so it is stored rather than parsed.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        return "; ".join(f"{k}: {v}" for k, v in value.items() if v is not None) or None
    if isinstance(value, (list, tuple)):
        return "; ".join(str(v) for v in value if v is not None) or None
    return str(value)


def _identity(handover: HandoverRequest) -> dict[str, Any]:
    """Pull name / DOB / ULN out of whichever identity field was sent.

    Each boundary names this field for its own vocabulary
    (``learner_identity`` here, ``student_identity`` on the school
    boundaries), and a caller driving the workflow by hand may have put
    the fields at the top level instead. All three shapes are accepted —
    refusing a handover over the spelling of a key would strand a real
    learner mid-transfer.
    """
    raw = (handover.get("learner_identity")
           or handover.get("student_identity")
           or handover.get("child_identity")
           or {})
    if not isinstance(raw, dict):
        raw = {}
    merged = {**handover.payload, **raw}

    def pick(*names: str) -> Any:
        for n in names:
            if merged.get(n) not in (None, ""):
                return merged[n]
        return None

    given = pick("given_name", "first_name", "legal_first_name", "forename")
    family = pick("family_name", "last_name", "legal_last_name", "surname")
    full = pick("full_name", "name")
    if (not given or not family) and isinstance(full, str) and full.strip():
        parts = full.strip().split()
        given = given or parts[0]
        family = family or (" ".join(parts[1:]) or parts[0])
    return {
        "given_name": _text(given),
        "family_name": _text(family),
        "date_of_birth": _text(pick("date_of_birth", "dob")),
        "uln": _text(pick("uln", "unique_learner_number")),
        "email": _text(pick("email", "personal_email")),
        "phone": _text(pick("phone", "mobile", "telephone")),
    }


def _prior_learning(handover: HandoverRequest) -> str | None:
    """Everything that shortens or reshapes the programme, as one note.

    Recognised prior learning reduces the funding band and can shorten
    the practical period, so it must not be dropped on the floor when it
    arrives under a source-specific key.
    """
    bits = []
    for key in ("prior_learning", "prior_attainment", "vocational_profile",
                "functional_skills", "achieved_qualifications",
                "gcse_results", "predicted_qualifications",
                "predicted_grades", "module_credits", "programme_registration"):
        text = _text(handover.get(key))
        if text:
            bits.append(f"{key.replace('_', ' ')}: {text}")
    return "\n".join(bits) or None


def _support_needs(handover: HandoverRequest) -> str | None:
    """SEND, medical and support indicators, as one note.

    These are the sensitive fields — if consent was withheld,
    ``build_handover`` has already stripped them and this returns None.
    The workplace risk assessment and EPA reasonable adjustments are
    built from whatever does arrive.
    """
    bits = []
    for key in ("send_support", "support_indicators", "medical_requirements",
                "attendance_behaviour", "support_referral"):
        text = _text(handover.get(key))
        if text:
            bits.append(f"{key.replace('_', ' ')}: {text}")
    return "\n".join(bits) or None


def _arrival_note(handover: HandoverRequest) -> str:
    parts = [
        f"Arrived from {handover.source_system} via transition "
        f"{handover.transition_id or '(none)'}",
        f"journey {handover.journey_id}",
    ]
    if handover.consent_reference:
        parts.append(f"consent {handover.consent_reference}")
    careers = _text(handover.get("careers_record"))
    if careers:
        parts.append(f"careers: {careers}")
    eligibility = _text(handover.get("eligibility_evidence"))
    if eligibility:
        parts.append(f"eligibility evidence: {eligibility}")
    employer = _text(handover.get("employer_details"))
    if employer:
        parts.append(f"employer named at handover: {employer}")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# The adapter
# ---------------------------------------------------------------------------

class ApprenticeshipsAdapter(PhaseAdapter):
    """Apprenticeships' side of the four-method transition contract."""

    system = SYSTEM_KEY

    # ── Destination side ────────────────────────────────────────────

    def create_applicant(self, handover: HandoverRequest) -> ApplicantResult:
        """Create (or find) the Applicant record for an arriving learner.

        Idempotent on ``journey_id``: a redelivered bus event finds the
        row stamped by the first delivery and returns it unchanged, so a
        learner cannot be enrolled twice by a retry.
        """
        init_db()
        identity = _identity(handover)
        if not identity["given_name"] or not identity["family_name"]:
            raise AdapterError(
                f"Handover for journey {handover.journey_id} carries no usable "
                f"name; apprenticeships cannot create an applicant without "
                f"one (boundary {handover.boundary})")

        with connect() as conn:
            existing = conn.execute(
                "SELECT apprentice_id, status FROM apprentices WHERE journey_id = ?",
                (handover.journey_id,)).fetchone()
            if existing is not None:
                logger.info(
                    "Journey %s already has apprentice %s (%s) — handover "
                    "from %s is a no-op", handover.journey_id,
                    existing["apprentice_id"], existing["status"],
                    handover.source_system)
                return ApplicantResult(
                    local_applicant_id=str(existing["apprentice_id"]),
                    notes=f"existing record, status {existing['status']}")

            # A learner may already be here under their ULN without a
            # journey stamp — matched from a previous import, or created
            # locally before the platform knew about them. Adopt that row
            # rather than creating a second record for one person.
            uln = identity["uln"]
            if uln:
                by_uln = conn.execute(
                    "SELECT apprentice_id, status FROM apprentices WHERE uln = ?",
                    (uln,)).fetchone()
                if by_uln is not None:
                    conn.execute(
                        "UPDATE apprentices SET journey_id = ?, "
                        "updated_at = datetime('now') WHERE apprentice_id = ?",
                        (handover.journey_id, by_uln["apprentice_id"]))
                    logger.info(
                        "Matched journey %s onto existing apprentice %s by ULN",
                        handover.journey_id, by_uln["apprentice_id"])
                    return ApplicantResult(
                        local_applicant_id=str(by_uln["apprentice_id"]),
                        notes="matched on ULN")

            cur = conn.execute(
                """INSERT INTO apprentices
                     (journey_id, uln, given_name, family_name, date_of_birth,
                      email, phone, status, prior_learning, support_needs, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'Applicant', ?, ?, ?)""",
                (handover.journey_id, identity["uln"], identity["given_name"],
                 identity["family_name"], identity["date_of_birth"],
                 identity["email"], identity["phone"],
                 _prior_learning(handover), _support_needs(handover),
                 _arrival_note(handover)))
            apprentice_id = int(cur.lastrowid)

        logger.info("Created apprentice applicant %s for journey %s (from %s)",
                    apprentice_id, handover.journey_id, handover.source_system)
        return ApplicantResult(
            local_applicant_id=str(apprentice_id),
            institution_id=handover.institution_id,
            notes=f"applicant created from {handover.boundary}")

    def create_enrolment(self, journey_id: str,
                         application_id: str | None = None,
                         **details: Any) -> EnrolmentResult:
        """Put an accepted applicant on programme.

        This is the point an apprenticeship actually starts, so it is
        also the point the employer and programme become required: an
        apprentice with no employer is not an apprentice. Callers that
        have not settled those yet should leave the record as an
        Applicant rather than calling this early.

        Idempotent on ``journey_id`` — a record already on programme (or
        beyond, at gateway or EPA) is returned untouched rather than
        having its start date rewritten by a duplicate event.
        """
        init_db()
        start_date = details.get("start_date") or date.today().isoformat()

        with connect() as conn:
            row = conn.execute(
                "SELECT apprentice_id, status, start_date FROM apprentices "
                "WHERE journey_id = ?", (journey_id,)).fetchone()
            if row is None:
                raise AdapterError(
                    f"No apprentice record for journey {journey_id}; "
                    f"create_applicant must run before create_enrolment")

            apprentice_id = int(row["apprentice_id"])
            if row["status"] != "Applicant":
                logger.info(
                    "Apprentice %s is already %s — create_enrolment is a "
                    "no-op", apprentice_id, row["status"])
                return EnrolmentResult(
                    local_student_id=str(apprentice_id),
                    start_date=row["start_date"],
                    notes=f"already {row['status']}")

            patch: dict[str, Any] = {"status": "On Programme",
                                     "start_date": start_date}
            for field in ("programme_id", "employer_id", "workplace_id",
                          "tutor_id", "planned_end_date", "weekly_hours",
                          "funding_model"):
                if details.get(field) is not None:
                    patch[field] = details[field]

            assignments = ", ".join(f"{k} = ?" for k in patch)
            conn.execute(
                f"UPDATE apprentices SET {assignments}, "
                "updated_at = datetime('now') WHERE apprentice_id = ?",
                [*patch.values(), apprentice_id])
            # The status column and its history have to agree; writing
            # them in one transaction is what keeps them that way.
            conn.execute(
                """INSERT INTO apprentice_status_history
                     (apprentice_id, from_status, to_status, reason,
                      effective_date, actor)
                   VALUES (?, 'Applicant', 'On Programme', ?, ?, ?)""",
                (apprentice_id,
                 details.get("reason") or "cross-system transition",
                 start_date, details.get("actor") or "platform"))

        logger.info("Apprentice %s on programme from %s (journey %s)",
                    apprentice_id, start_date, journey_id)
        return EnrolmentResult(
            local_student_id=str(apprentice_id),
            institution_id=details.get("institution_id"),
            start_date=start_date,
            notes="placed on programme by cross-system transition")

    # ── Source side ─────────────────────────────────────────────────

    def export_handover(self, local_student_id: str,
                        consent: bool | set[str] | None = None,
                        *, destination_system: str | None = None
                        ) -> ExportResult:
        """Gather what this system holds about a departing apprentice.

        Returns everything for the boundary's field keys and lets
        ``handover.build_handover`` apply consent — filtering here as
        well would mean two places deciding what a learner agreed to,
        and eventually disagreeing.

        The EPA grade is the headline: an apprentice progressing to a
        degree is admitted on their standard and grade, not on the
        portfolio behind it.
        """
        init_db()
        with connect() as conn:
            row = conn.execute(
                """SELECT a.*, p.title AS programme_title, p.level AS programme_level,
                          p.reference AS programme_reference,
                          e.name AS employer_name
                     FROM apprentices a
                     LEFT JOIN programmes p ON p.programme_id = a.programme_id
                     LEFT JOIN employers  e ON e.employer_id  = a.employer_id
                    WHERE a.apprentice_id = ?""",
                (local_student_id,)).fetchone()
            if row is None:
                raise AdapterError(
                    f"No apprentice {local_student_id} to export")

            # Latest sitting wins: a resit supersedes the attempt before it.
            epa = conn.execute(
                "SELECT grade, method, assessed_date, attempt FROM epa_results "
                "WHERE apprentice_id = ? "
                "ORDER BY assessed_date DESC, result_id DESC LIMIT 1",
                (local_student_id,)).fetchone()
            skills = conn.execute(
                "SELECT subject, level, status FROM functional_skills "
                "WHERE apprentice_id = ?", (local_student_id,)).fetchall()
            evidence = conn.execute(
                "SELECT COUNT(*) FROM portfolio_evidence "
                "WHERE apprentice_id = ? AND status = 'Accepted'",
                (local_student_id,)).fetchone()

        record: dict[str, Any] = {
            "learner_identity": {
                "given_name": row["given_name"],
                "family_name": row["family_name"],
                "date_of_birth": row["date_of_birth"],
                "uln": row["uln"],
            },
            "standard_completed": {
                "standard": row["programme_title"],
                "reference": row["programme_reference"],
                "level": row["programme_level"],
                "status": row["status"],
                "completion_date": row["actual_end_date"],
            },
            "functional_skills": [
                {"subject": s["subject"], "level": s["level"],
                 "status": s["status"]} for s in skills
            ] or None,
            "prior_learning": row["prior_learning"],
            "portfolio_summary": {
                "accepted_evidence_items": evidence[0] if evidence else 0,
            },
            "employer_reference": row["employer_name"],
            "support_referral": row["support_needs"],
        }
        if epa is not None:
            record["epa_result"] = {"grade": epa["grade"],
                                    "method": epa["method"],
                                    "assessed_date": epa["assessed_date"],
                                    "attempt": epa["attempt"]}

        logger.info("Exported apprentice %s for handover to %s",
                    local_student_id, destination_system or "(unspecified)")
        return ExportResult(record=record,
                            local_student_id=str(local_student_id))

    def close_enrolment(self, local_student_id: str,
                        reason: str, **details: Any) -> None:
        """Close the record when an apprentice leaves. Never deletes.

        ``Transferred`` when they have gone to another provider,
        ``Withdrawn`` otherwise. A record already at a terminal status is
        left alone — re-closing would append a second history row saying
        the same thing.

        A learner who is *also* enrolled elsewhere (a degree apprentice
        at the university) must not reach this method at all: the
        platform is told not to close the source via ``close_source=False``
        on the transition.
        """
        init_db()
        status = details.get("status") or (
            "Transferred" if "transfer" in reason.lower() else "Withdrawn")
        effective = details.get("end_date") or date.today().isoformat()

        with connect() as conn:
            row = conn.execute(
                "SELECT status FROM apprentices WHERE apprentice_id = ?",
                (local_student_id,)).fetchone()
            if row is None:
                logger.warning(
                    "close_enrolment: no apprentice %s (already removed?)",
                    local_student_id)
                return
            if row["status"] in ("Withdrawn", "Transferred", "Completed"):
                logger.info("Apprentice %s is already %s — not re-closing",
                            local_student_id, row["status"])
                return

            conn.execute(
                "UPDATE apprentices SET status = ?, actual_end_date = ?, "
                "updated_at = datetime('now') WHERE apprentice_id = ?",
                (status, effective, local_student_id))
            conn.execute(
                """INSERT INTO apprentice_status_history
                     (apprentice_id, from_status, to_status, reason,
                      effective_date, actor)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (local_student_id, row["status"], status, reason, effective,
                 details.get("actor") or "platform"))
            # A withdrawal is a funding event, not just a status change:
            # the ESFA can ask about the claim history for a learner who
            # left, so the departure gets its own row.
            conn.execute(
                """INSERT INTO withdrawals
                     (apprentice_id, withdrawal_date, last_activity_date,
                      reason, notes, recorded_by)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (local_student_id, effective, details.get("last_activity_date"),
                 reason, details.get("notes"),
                 details.get("actor") or "platform"))

        logger.info("Apprentice %s closed as %s (%s)", local_student_id,
                    status, reason)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

ADAPTER = ApprenticeshipsAdapter()


def register() -> ApprenticeshipsAdapter:
    """Register this adapter with the platform. Idempotent.

    Called from the launcher rather than at package import: importing the
    apprenticeships package should not drag the platform's cross-system
    stack in behind it, and a system that is never launched does not need
    to be reachable.
    """
    registry.register(ADAPTER, replace=True)
    return ADAPTER


__all__ = ["SYSTEM_KEY", "ApprenticeshipsAdapter", "ADAPTER", "register"]
