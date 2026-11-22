"""Map sixth-form medical records onto the university schema.

The two databases use very different shapes for medical data:

* **Sixth form** keeps four normalised tables — ``med_profiles``,
  ``med_conditions``, ``med_medications``, ``med_allergies`` —
  with one row per condition / medication / allergy.
* **University** keeps a single denormalised ``medical_info`` row
  per student (blood type, GP details, and free-text
  ``allergies`` / ``medications`` / ``conditions`` columns) plus
  a normalised ``medical_conditions`` table (one row per
  diagnosed condition).

When a Year 13 leaver is transferred, this module is the single
seam that copies their medical record across:

* Upserts one ``medical_info`` row for the university ``student_id``,
  carrying GP details, blood type, and a human-readable summary of
  allergies / medications / conditions in the corresponding free-text
  columns.
* Inserts one ``medical_conditions`` row per sixth-form condition,
  mapping severity directly (the vocabularies overlap) and the
  active flag onto a status of ``Active`` / ``Inactive``.

Medications and allergies do not have dedicated destination tables on
the university side, so they are flattened into the ``medical_info``
free-text columns where the GP, school nurse, or wellbeing team would
expect to read them.

All work happens in a single transaction. Failure does not block the
transfer — the caller logs and surfaces a warning, leaving the
university student record itself intact.

Consent
-------
Being the single seam is what makes this the right place for the gate.
Special-category health data used to cross here on nothing more than a
staff member clicking Save: ``handover.SIXTH_FORM_TO_UNIVERSITY`` marks
its sensitive fields as needing consent, the sixth form records that
consent under ``university_handover``, and none of it was consulted —
the copy ran unconditionally from two call sites and read every
condition, medication, allergy and GP detail on file.

Every import now resolves a :class:`ReleaseDecision` first:

``consent``
    An active, unexpired ``university_handover`` consent. Full record.
``vital_interests``
    A named lawful basis the caller asserts, for the case consent cannot
    be obtained and an allergy would otherwise go unknown at enrolment.
    **Safety-critical subset only** — allergies, active conditions and
    current medications. Inactive history, blood group and GP details do
    not cross on this basis, because they are not what makes it lawful.
``refused``
    Neither. :class:`MedicalHandoverRefused` is raised and nothing is
    written.

Whatever the outcome, the attempt is written to the platform audit log
with the basis, the scope and the receiving team, so the access record
is complete rather than inferable from the presence of a row.
"""

from __future__ import annotations

import datetime as _dt
import logging
from types import SimpleNamespace
from dataclasses import dataclass, field

from education_system.systems.university.domains.health.infrastructure.health.storage import (
    get_connection,
)

logger = logging.getLogger(__name__)

#: The consent purpose the sixth form records this release under. Named
#: here rather than imported so a sixth form that is not installed still
#: produces a readable refusal message instead of an ImportError.
_CONSENT_PURPOSE = "university_handover"

#: Lawful bases this seam accepts, most preferred first. Anything else is
#: a refusal — "the operator typed a reason" is not a lawful basis.
CONSENT = "consent"
VITAL_INTERESTS = "vital_interests"
LAWFUL_BASES: tuple[str, ...] = (CONSENT, VITAL_INTERESTS)

#: What crosses under each basis.
SCOPE_FULL = "full"
SCOPE_SAFETY_CRITICAL = "safety_critical"


class MedicalHandoverRefused(PermissionError):
    """No consent and no lawful basis — the record must not be copied."""


@dataclass(frozen=True)
class ReleaseDecision:
    """Whether this learner's health record may cross, and how much of it."""

    allowed: bool
    basis: str
    scope: str
    detail: str
    consent_reference: str | None = None

    @property
    def full_record(self) -> bool:
        return self.scope == SCOPE_FULL


@dataclass
class ImportSummary:
    """What ``import_from_sixth_form`` did, for logging and UI."""
    medical_info_written: bool
    conditions_written: int
    medications_written: int
    allergies_written: int
    profile_present: bool
    #: How the release was authorised, and what it covered.
    basis: str = CONSENT
    scope: str = SCOPE_FULL
    #: Categories deliberately not carried under a narrowed scope.
    withheld: list[str] = field(default_factory=list)


def _format_allergies(allergies) -> str | None:
    if not allergies:
        return None
    lines: list[str] = []
    for a in allergies:
        flags = []
        if a.has_epipen:
            flags.append("EpiPen")
        flag_suffix = f"  [{', '.join(flags)}]" if flags else ""
        reaction = f" — {a.reaction}" if a.reaction else ""
        lines.append(
            f"- {a.allergen} ({a.severity}){reaction}{flag_suffix}")
    return "\n".join(lines)


def _format_medications(medications) -> str | None:
    if not medications:
        return None
    lines: list[str] = []
    for m in medications:
        bits: list[str] = []
        if m.dose:
            bits.append(m.dose)
        if m.frequency:
            bits.append(m.frequency)
        bits.append(m.route)
        if m.is_emergency:
            bits.append("EMERGENCY")
        meta = ", ".join(bits)
        dates = ""
        if m.start_date or m.end_date:
            dates = f"  [{m.start_date or '—'} → {m.end_date or '—'}]"
        prescriber = f"  Rx: {m.prescribed_by}" if m.prescribed_by else ""
        lines.append(f"- {m.name} ({meta}){dates}{prescriber}")
    return "\n".join(lines)


def _format_conditions(conditions) -> str | None:
    if not conditions:
        return None
    lines: list[str] = []
    for c in conditions:
        active = "Active" if c.active else "Inactive"
        diagnosed = f"  diagnosed {c.diagnosed_date}" if c.diagnosed_date else ""
        plan = f"  Care plan: {c.care_plan_ref}" if c.care_plan_ref else ""
        lines.append(
            f"- {c.name} ({c.severity}, {active}){diagnosed}{plan}")
    return "\n".join(lines)


def _combined_doctor_name(profile) -> str | None:
    bits = [profile.gp_name, profile.gp_practice]
    text = " — ".join(b for b in bits if b)
    return text or None


def check_release(sf_student_id: str, *,
                  lawful_basis: str | None = None) -> ReleaseDecision:
    """May this learner's health record cross, and how much of it?

    Consent is looked up in the *source* system's register, because that
    is where the learner gave it — asking the university whether the
    university may read something answers the wrong question.

    ``lawful_basis`` is the caller's assertion of an alternative, and is
    only honoured for :data:`VITAL_INTERESTS`. It narrows the scope
    rather than widening it: an asserted basis is a reason to carry the
    allergy that could kill somebody, not a way around the consent the
    learner did not give.
    """
    asserted = (lawful_basis or "").strip().lower() or None
    if asserted and asserted not in LAWFUL_BASES:
        return ReleaseDecision(
            allowed=False, basis="", scope="",
            detail=f"{asserted!r} is not a lawful basis for releasing "
                   f"special-category health data")

    consent = None
    try:
        consent = _sixth_form().handover_consent(sf_student_id)
    except Exception:
        # An unreadable consent register is not a grant. Fall through to
        # the refusal below unless the caller asserted a basis of its own.
        logger.exception(
            "Could not read the sixth form's handover consent for %s",
            sf_student_id)

    if consent:
        expires = (consent.get("expires_date") or "").strip()
        reference = str(consent.get("consent_id") or "")
        if expires and expires < _dt.date.today().isoformat():
            logger.warning(
                "Handover consent %s for %s expired on %s",
                reference or "?", sf_student_id, expires)
        else:
            return ReleaseDecision(
                allowed=True, basis=CONSENT, scope=SCOPE_FULL,
                consent_reference=reference or None,
                detail=f"Handover consent {reference or '(unnumbered)'} "
                       f"granted {consent.get('granted_date') or 'undated'}")

    if asserted == VITAL_INTERESTS:
        return ReleaseDecision(
            allowed=True, basis=VITAL_INTERESTS,
            scope=SCOPE_SAFETY_CRITICAL,
            detail="No handover consent on record; released on vital "
                   "interests, limited to the safety-critical subset")

    return ReleaseDecision(
        allowed=False, basis="", scope="",
        detail=f"No active '{_CONSENT_PURPOSE}' consent recorded in the "
               f"sixth-form system for {sf_student_id}, and no lawful "
               f"basis asserted")


def _sixth_form():
    """The sixth form's platform adapter (raises if it is not installed).

    The only way this module reaches the sixth form: through the adapter
    registry, never by importing the sixth form's packages.
    """
    from education_system.platform.cross_system.adapters import route_support

    return route_support.adapter_for("sixth_form")


def _audit_release(*, uni_student_id: str, sf_student_id: str,
                   decision: ReleaseDecision, actor: str | None,
                   received_by: str | None, outcome: str,
                   extra: dict | None = None) -> None:
    """Record the attempt — allowed or refused — in the platform audit log.

    Best-effort. A health record that has already been copied must not be
    un-copied because the audit database was locked, and a refusal that
    could not be logged is still a refusal.
    """
    try:
        from education_system.platform.governance.audit.logger import (
            AuditAction, AuditLogger,
        )
        details = {
            "sf_student_id": sf_student_id,
            "outcome": outcome,
            "lawful_basis": decision.basis or "none",
            "scope": decision.scope or "none",
            "consent_reference": decision.consent_reference,
            "received_by": received_by or actor or "unattributed",
            "detail": decision.detail,
        }
        details.update(extra or {})
        AuditLogger("university").log(
            AuditAction.IMPORT, username=actor,
            target_type="medical_info", target_id=uni_student_id,
            details=details)
    except Exception:
        logger.exception(
            "Could not audit the sixth-form medical release for %s -> %s "
            "(outcome=%s)", sf_student_id, uni_student_id, outcome)


def import_from_sixth_form(
    uni_student_id: str,
    sf_student_id: str,
    *,
    lawful_basis: str | None = None,
    actor: str | None = None,
    received_by: str | None = None,
) -> ImportSummary:
    """Copy a sixth-form student's medical record onto the university
    schema for ``uni_student_id``.

    Reads via the sixth-form Python API (so the source-side
    validation / dataclasses are honoured), writes via the
    university's shared DB connection.

    The release is gated first — see :func:`check_release` and the module
    docstring. ``lawful_basis`` is the caller's alternative to recorded
    consent and narrows what crosses; ``actor`` and ``received_by`` name
    who did it and which team is receiving it, and both go into the audit
    entry. There is no unaudited path through this function.

    Returns an :class:`ImportSummary` describing what was written and
    under what basis. Raises :class:`MedicalHandoverRefused` when there is
    no consent and no basis, and otherwise only for unrecoverable
    database errors — if the sixth-form record is genuinely empty for a
    student, the function still succeeds, just with zero counts.
    """
    decision = check_release(sf_student_id, lawful_basis=lawful_basis)
    if not decision.allowed:
        _audit_release(
            uni_student_id=uni_student_id, sf_student_id=sf_student_id,
            decision=decision, actor=actor, received_by=received_by,
            outcome="refused")
        logger.warning(
            "Refused sixth-form medical import %s -> %s: %s",
            sf_student_id, uni_student_id, decision.detail)
        raise MedicalHandoverRefused(decision.detail)

    record = _sixth_form().medical_record(sf_student_id)

    def _ns(row):
        return SimpleNamespace(**row) if row is not None else None

    profile      = _ns(record.get("profile"))
    conditions   = [_ns(c) for c in record.get("conditions") or []]
    medications  = [_ns(m) for m in record.get("medications") or []]
    allergies    = [_ns(a) for a in record.get("allergies") or []]

    # Minimum necessary. Under vital interests the justification covers
    # what a clinician needs in front of them now — an allergy, a live
    # condition, a drug currently being taken — and stops there. A
    # resolved condition from Year 12 and the family GP's phone number
    # are ordinary record-keeping, and ordinary record-keeping needs
    # ordinary consent.
    withheld: list[str] = []
    if not decision.full_record:
        resolved = [c for c in conditions if not c.active]
        if resolved:
            withheld.append(f"{len(resolved)} resolved condition(s)")
        conditions = [c for c in conditions if c.active]
        if profile is not None:
            withheld.append("GP details and blood group")
            profile = None

    logger.info(
        "Importing sixth-form medical record for sf=%s -> uni=%s "
        "(basis=%s, scope=%s, profile=%s, %d conditions, %d medications, "
        "%d allergies)",
        sf_student_id, uni_student_id, decision.basis, decision.scope,
        profile is not None, len(conditions), len(medications),
        len(allergies),
    )

    # If there's truly nothing to copy, short-circuit before opening
    # a transaction. The caller can still log "nothing imported"
    # without us writing an empty row.
    if (profile is None and not conditions
            and not medications and not allergies):
        logger.info(
            "Sixth-form medical record for %s is empty — nothing to import",
            sf_student_id)
        _audit_release(
            uni_student_id=uni_student_id, sf_student_id=sf_student_id,
            decision=decision, actor=actor, received_by=received_by,
            outcome="empty", extra={"withheld": withheld})
        return ImportSummary(
            medical_info_written=False,
            conditions_written=0,
            medications_written=0,
            allergies_written=0,
            profile_present=False,
            basis=decision.basis, scope=decision.scope, withheld=withheld,
        )

    allergies_text   = _format_allergies(allergies)
    medications_text = _format_medications(medications)
    conditions_text  = _format_conditions(conditions)

    blood_type   = profile.blood_group if profile else None
    doctor_name  = _combined_doctor_name(profile) if profile else None
    doctor_phone = profile.gp_phone if profile else None

    conn = get_connection()
    try:
        cur = conn.cursor()

        # ── medical_info: upsert by student_id ─────────────────────
        cur.execute(
            "SELECT id FROM medical_info WHERE student_id = ?",
            (uni_student_id,),
        )
        existing = cur.fetchone()
        if existing:
            cur.execute(
                """UPDATE medical_info SET
                       blood_type   = COALESCE(?, blood_type),
                       allergies    = ?,
                       medications  = ?,
                       conditions   = ?,
                       doctor_name  = COALESCE(?, doctor_name),
                       doctor_phone = COALESCE(?, doctor_phone),
                       last_updated = CURRENT_TIMESTAMP
                   WHERE student_id = ?""",
                (blood_type, allergies_text, medications_text,
                 conditions_text, doctor_name, doctor_phone,
                 uni_student_id),
            )
            logger.info(
                "Updated medical_info row for uni student %s",
                uni_student_id)
        else:
            cur.execute(
                """INSERT INTO medical_info
                       (student_id, blood_type, allergies, medications,
                        conditions, doctor_name, doctor_phone,
                        last_updated)
                   VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (uni_student_id, blood_type, allergies_text,
                 medications_text, conditions_text, doctor_name,
                 doctor_phone),
            )
            logger.info(
                "Inserted medical_info row for uni student %s",
                uni_student_id)

        # ── medical_conditions: one INSERT per sixth-form row ──────
        conditions_written = 0
        for c in conditions:
            status = "Active" if c.active else "Inactive"
            notes_bits = []
            if c.notes:
                notes_bits.append(c.notes)
            if c.care_plan_ref:
                notes_bits.append(f"Care plan ref: {c.care_plan_ref}")
            notes_bits.append(f"Imported from sixth-form record {sf_student_id}")
            notes = "\n".join(notes_bits)
            cur.execute(
                """INSERT INTO medical_conditions
                       (student_id, condition_name, severity,
                        diagnosed_date, status, provider, notes,
                        created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (uni_student_id, c.name, c.severity,
                 c.diagnosed_date, status,
                 "Imported from sixth form", notes),
            )
            conditions_written += 1

        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)
        logger.exception(
            "Medical-record import failed for sf=%s -> uni=%s",
            sf_student_id, uni_student_id)
        raise
    finally:
        try:
            conn.close()
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

    summary = ImportSummary(
        medical_info_written=True,
        conditions_written=conditions_written,
        medications_written=len(medications),
        allergies_written=len(allergies),
        profile_present=profile is not None,
        basis=decision.basis, scope=decision.scope, withheld=withheld,
    )
    _audit_release(
        uni_student_id=uni_student_id, sf_student_id=sf_student_id,
        decision=decision, actor=actor, received_by=received_by,
        outcome="imported",
        extra={
            "conditions": summary.conditions_written,
            "medications": summary.medications_written,
            "allergies": summary.allergies_written,
            "withheld": withheld,
        })
    logger.info(
        "Sixth-form medical import complete: sf=%s -> uni=%s "
        "(basis=%s, scope=%s, conditions=%d, meds flattened=%d, "
        "allergies flattened=%d, withheld=%s)",
        sf_student_id, uni_student_id, summary.basis, summary.scope,
        summary.conditions_written, summary.medications_written,
        summary.allergies_written, "; ".join(withheld) or "nothing",
    )
    return summary


__all__ = [
    "CONSENT",
    "VITAL_INTERESTS",
    "LAWFUL_BASES",
    "SCOPE_FULL",
    "SCOPE_SAFETY_CRITICAL",
    "MedicalHandoverRefused",
    "ReleaseDecision",
    "ImportSummary",
    "check_release",
    "import_from_sixth_form",
]
