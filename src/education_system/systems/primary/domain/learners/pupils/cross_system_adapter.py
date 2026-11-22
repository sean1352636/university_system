"""Primary School side of the platform transition contract.

Both ends of the primary phase meet the platform here. Reception places
arrive from the nursery (``create_applicant`` then ``create_enrolment``);
Year 6 leavers export to secondary and are closed off roll
(``export_handover`` / ``close_enrolment``).

An arriving child is an *applicant* until the destination admits them:
the pupil row exists at ``roll_status='applicant'`` and stays out of the
class lists until ``create_enrolment`` puts them on roll. Leaving is the
reverse, and never a delete — the leaver is written to the school's own
leavers register and the pupil row is kept at ``left``.

The handover arrives already filtered by ``handover.build_handover``. If
the parent did not consent to medical detail crossing, it is simply not in
the payload, and nothing here goes looking for it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
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

logger = logging.getLogger(__name__)

SYSTEM_KEY = "primary"
ENTRY_YEAR = "R"


@dataclass
class PupilEnrolmentResult(EnrolmentResult):
    """``EnrolmentResult`` plus the pupil's school email address."""

    email: str | None = None


def _identity(handover: HandoverRequest) -> dict[str, Any]:
    raw = (handover.get("child_identity") or handover.get("student_identity")
           or handover.get("learner_identity") or {})
    return raw if isinstance(raw, dict) else {}


def _first_guardian(handover: HandoverRequest) -> dict[str, Any]:
    guardians = handover.get("guardians") or []
    if isinstance(guardians, dict):
        guardians = [guardians]
    for guardian in guardians:
        if isinstance(guardian, dict):
            return guardian
    return {}


def _medical_notes(handover: HandoverRequest) -> str:
    """Medical alerts as the primary record holds them: one notes field.

    Allergies are folded in explicitly — the pupil record has no separate
    allergies column, and an allergy lost on the way into Reception is a
    safeguarding failure.
    """
    alerts = handover.get("medical_alerts")
    if isinstance(alerts, dict):
        parts = []
        if alerts.get("allergies"):
            parts.append(f"Allergies: {str(alerts['allergies']).strip()}")
        if alerts.get("medical_notes"):
            parts.append(str(alerts["medical_notes"]).strip())
        return ("\n".join(parts)
                or "No allergies or medical alerts recorded by the previous setting")
    if alerts:
        return str(alerts).strip()
    requirements = handover.get("medical_requirements")
    return str(requirements).strip() if requirements else ""


#: Identity keys the Add Pupil form shares with the handover's child_identity.
_IDENTITY_EXTRAS = ("middle_names", "preferred_name", "gender", "upn",
                    "address_line1", "address_line2", "town", "postcode")


def _parity_extras(identity: dict[str, Any], guardian: dict[str, Any],
                   handover: HandoverRequest) -> dict[str, Any]:
    """The Add Pupil parity fields the previous setting sent (nursery since
    2026-11-05), keyed as ``create_pupil`` takes them. Only what arrived is
    returned, so nothing is blanked."""
    out: dict[str, Any] = {key: identity[key] for key in _IDENTITY_EXTRAS
                           if identity.get(key)}
    relationship = guardian.get("relationship")
    if relationship and relationship != "Parent/Carer":
        out["parent_relationship"] = relationship
    if guardian.get("email"):
        out["parent_email"] = guardian["email"]
    send = handover.get("send_support")
    if isinstance(send, dict) and send.get("sen_status"):
        out["sen_status"] = send["sen_status"]
    needs = handover.get("communication_needs")
    if isinstance(needs, dict) and needs.get("eal"):
        out["eal"] = True
    return out


def _editable(pupil: Any) -> dict[str, Any]:
    """The fields ``update_pupil`` re-validates, taken from a pupil."""
    return {
        "first_name": pupil.first_name, "last_name": pupil.last_name,
        "year_group": pupil.year_group, "class_name": pupil.class_name or "",
        "date_of_birth": pupil.date_of_birth or "",
        "parent_name": pupil.parent_name or "",
        "parent_phone": pupil.parent_phone or "",
        "medical_notes": pupil.medical_notes or "",
        "send_status": pupil.send_status or "",
    }


def leaver_id_for(pupil_id: str) -> str | None:
    """The leavers-register entry for a pupil, if one has been written."""
    from education_system.systems.primary.domain.learners.pupils.leavers import leavers

    leavers.init_db()
    conn = leavers._connect()
    try:
        row = conn.execute(
            "SELECT leaver_id FROM leavers WHERE pupil_id = ? "
            "ORDER BY created_at DESC LIMIT 1", (pupil_id,)).fetchone()
    finally:
        conn.close()
    return row["leaver_id"] if row else None



# ── Export sections (primary → secondary handover) ──────────────────
# Shapes are the shared Year 6 contract; see handover.PRIMARY_TO_SECONDARY.

_SEND_STAGE_TO_STATUS = {
    "EHCP (Education, Health, Care Plan)": "E",
    "EHCP assessment in progress": "K",
    "SEN Support": "K",
}
_CLOSED_INTERVENTIONS = frozenset({"Complete", "Cancelled"})
_TERM_ORDER = {"Autumn": 1, "Spring": 2, "Summer": 3}


def _section(name: str, gather: Any, pupil: Any) -> Any:
    """One export section. A broken module costs that section, logged
    loudly, rather than the whole transfer."""
    try:
        return gather(pupil)
    except Exception:  # noqa: BLE001 - logged; the rest of the handover still goes
        logger.exception("Primary handover: could not gather %s for %s", name,
                         getattr(pupil, "pupil_id", "?"))
        return None


def _academic_year() -> str:
    from education_system.systems.primary.domain.learners.pupils import year6_transition
    return year6_transition.current_academic_year()


def _years_back(year: str, n: int = 2) -> list[str]:
    start = int(year[:4])
    return [f"{y}-{str(y + 1)[-2:]}" for y in range(start, start - n, -1)]


def _child_identity(pupil: Any) -> dict[str, Any]:
    from education_system.systems.primary import SYSTEM_NAME
    g = lambda name: getattr(pupil, name, None) or None  # noqa: E731
    return {
        "first_name": pupil.first_name,
        "middle_names": g("middle_names"),
        "last_name": pupil.last_name,
        "preferred_name": g("preferred_name"),
        "date_of_birth": pupil.date_of_birth,
        "gender": g("gender"),
        "upn": g("upn"),
        "primary_pupil_id": pupil.pupil_id,
        "year_group": pupil.year_group,
        "class_name": g("class_name"),
        "school_name": SYSTEM_NAME,
        "address_line1": g("address_line1"),
        "address_line2": g("address_line2"),
        "town": g("town"),
        "postcode": g("postcode"),
    }


def _guardians(pupil: Any) -> list[dict[str, Any]] | None:
    """Parent contacts (family only — a social worker is never listed; that
    goes through the safeguarding channel), else the pupil record's parent."""
    from education_system.systems.primary.domain.operations.communications.parent_contacts import (
        parent_contacts,
    )
    out = []
    for c in parent_contacts.contacts_for_student(pupil.pupil_id):
        if c.relationship == "Social Worker":
            continue
        out.append({
            "name": f"{c.first_name} {c.last_name}".strip(),
            "relationship": c.relationship,
            "phone": c.primary_phone or c.secondary_phone,
            "email": c.email,
            "parental_responsibility": bool(c.has_parental_responsibility),
        })
    if out:
        return out
    if not (pupil.parent_name or pupil.parent_phone):
        return None
    return [{"name": pupil.parent_name, "relationship":
             getattr(pupil, "parent_relationship", None) or "Parent/Carer",
             "phone": pupil.parent_phone, "email": getattr(pupil, "parent_email", None),
             "parental_responsibility": True}]


def _ks2_results(pupil: Any) -> dict[str, Any] | None:
    from education_system.systems.primary.domain.assessment import assessment
    from education_system.systems.primary.domain.assessment.ks2_sats import ks2_sats
    from education_system.systems.primary.domain.assessment.mtc import mtc
    from education_system.systems.primary.domain.assessment.phonics_screening import (
        phonics_screening,
    )
    sats = ks2_sats.list_for_pupil(pupil.pupil_id)
    mtcs = mtc.list_for_pupil(pupil.pupil_id)
    screens = phonics_screening.list_for_pupil(pupil.pupil_id)
    if not (sats or mtcs or screens):
        return None
    year = max((r.academic_year for r in sats), default=None)
    by_subject = {r.subject: r for r in sats if r.academic_year == year}

    def scaled(subject: str) -> int | None:
        r = by_subject.get(subject)
        return r.scaled_score if r is not None else None

    def outcome(subject: str) -> str | None:
        r = by_subject.get(subject)
        return r.outcome if r is not None else None

    writing = [r for r in assessment.list_for_pupil(pupil.pupil_id)
               if r.subject.strip().lower() == "writing"
               and (year is None or r.academic_year == year)]
    writing.sort(key=lambda r: (r.academic_year, _TERM_ORDER.get(r.term, 0)))
    latest_mtc = max(mtcs, key=lambda r: (r.academic_year, r.assessed_on or ""), default=None)
    return {
        "academic_year": year,
        "reading_scaled": scaled("Reading"),
        "maths_scaled": scaled("Maths"),
        "gps_scaled": scaled("EGPS"),
        "reading_outcome": outcome("Reading"),
        "maths_outcome": outcome("Maths"),
        "gps_outcome": outcome("EGPS"),
        "writing_ta": writing[-1].grade if writing else None,
        "science_ta": outcome("Science"),
        "mtc_score": latest_mtc.score if latest_mtc is not None else None,
        "phonics_passed": (any(r.score >= phonics_screening.PASS_MARK for r in screens)
                           if screens else None),
    }


def _core_assessments(pupil: Any) -> dict[str, Any] | None:
    from education_system.systems.primary.domain.assessment import assessment
    from education_system.systems.primary.domain.assessment.reading_levels import (
        reading_levels,
    )
    level = reading_levels.get_record(pupil.pupil_id)
    latest: dict[str, Any] = {}
    for r in assessment.list_for_pupil(pupil.pupil_id):
        key = (r.academic_year, _TERM_ORDER.get(r.term, 0), r.assessed_on or "")
        held = latest.get(r.subject)
        if held is None or key > held[0]:
            latest[r.subject] = (key, r)
    if level is None and not latest:
        return None
    return {
        "reading_level": level.band if level is not None else None,
        "latest": [{"subject": r.subject, "term": f"{r.term} {r.academic_year}",
                    "grade": r.grade, "score": r.score, "assessed_on": r.assessed_on}
                   for _k, r in sorted(latest.values(), key=lambda kv: kv[1].subject)],
    }


def _attendance_summary(pupil: Any) -> dict[str, Any] | None:
    from education_system.systems.primary.domain.academics.attendance import attendance
    from education_system.systems.primary.domain.learners.pupils import year6_transition
    year = _academic_year()
    start, end = year6_transition.year_dates(year)
    summary = attendance.pupil_summary(pupil.pupil_id, date_from=start, date_to=end)
    # "X" (not required) is not a possible session, as in pupil_summary.
    possible = sum(1 for r in summary["records"] if r.is_possible)
    if not possible:
        return None
    percent = summary["attendance_pct"]
    return {
        "academic_year": year,
        "percent": percent,
        "sessions_possible": possible,
        "sessions_attended": summary["present"],
        "unauthorised": summary["unauthorised_absent"],
        "persistent_absence": percent < 90.0,
    }


def _support_indicators(pupil: Any) -> dict[str, Any] | None:
    from education_system.systems.primary.domain.finance.pupil_premium import pupil_premium
    from education_system.systems.primary.domain.learners.pupils import year6_transition
    record = None
    for year in _years_back(_academic_year()):
        record = pupil_premium.get_for(pupil.pupil_id, year6_transition._slash_year(year))
        if record is not None:
            break
    pp = record is not None and record.status in ("Eligible", "Provisional")
    category = record.category if pp and record is not None else ""
    out = {
        "pupil_premium": pp,
        "fsm": bool(getattr(pupil, "fsm_eligible", False))
        or category in ("Ever 6 FSM", "Free school meals"),
        "lac": category == "LAC (Looked-after child)",
        "plac": category == "Post-LAC",
        "eal": bool(getattr(pupil, "eal", False)),
    }
    return out if any(out.values()) else None


def _send_provision(pupil: Any) -> dict[str, Any] | None:
    from education_system.systems.primary.domain.learners.pupils import year6_transition
    from education_system.systems.primary.domain.pastoral.send import send
    record = None
    for year in _years_back(_academic_year()):
        record = send.get_for(pupil.pupil_id, year6_transition._slash_year(year))
        if record is not None:
            break
    status = (getattr(pupil, "sen_status", None) or "").strip().upper() or None
    if record is not None and record.status != "Discharged":
        status = status or _SEND_STAGE_TO_STATUS.get(record.provision_stage, "N")
    if status is None:
        status = "K" if pupil.send_status == "yes" else "N"
    if status == "N" and (record is None or record.status == "Discharged"):
        return None
    reviews = send.list_reviews(record.send_id) if record is not None else []
    adjustments = next((r.adjustments for r in reviews if r.adjustments), None)
    ehcp = status == "E" or bool(record is not None and (
        record.ehcp_reference or record.provision_stage.startswith("EHCP (")))
    return {
        "sen_status": status,
        "ehcp": ehcp,
        "primary_need": record.primary_need if record is not None else None,
        "needs": ([n for n in (record.primary_need, record.secondary_need) if n]
                  if record is not None else []),
        "provision": record.provision_summary if record is not None else None,
        "access_arrangements": adjustments,
        "plan_review_date": record.next_review_date if record is not None else None,
    }


def _current_interventions(pupil: Any) -> list[dict[str, Any]] | None:
    from education_system.systems.primary.domain.assessment.intervention_tracking import (
        intervention_tracking,
    )
    out = []
    for i in intervention_tracking.list_interventions(pupil_id=pupil.pupil_id):
        if i.status in _CLOSED_INTERVENTIONS:
            continue
        out.append({
            "name": i.intervention_type + (f": {i.goal}" if i.goal else ""),
            "subject": i.subject_name,
            "led_by": i.led_by,
            "started_on": i.start_date,
            "notes": "; ".join(x for x in (i.frequency, i.notes) if x) or None,
        })
    return out or None


def _medical_requirements(pupil: Any) -> dict[str, Any] | None:
    from education_system.systems.primary.domain.pastoral.health.medical_records import (
        medical_records,
    )
    conditions = [{"type": r.record_type, "name": r.title, "severity": r.severity,
                   "care_plan": r.action_plan}
                  for r in medical_records.list_for_pupil(pupil.pupil_id, active_only=True)]
    notes = (pupil.medical_notes or "").strip() or None
    if not (notes or conditions):
        return None
    return {"notes": notes, "conditions": conditions}


def _transition_report(pupil: Any) -> dict[str, Any] | None:
    from education_system.systems.primary.domain.learners.pupils import year6_transition
    return year6_transition.report_payload(pupil.pupil_id)


def pupils_year_groups() -> tuple[str, ...]:
    from education_system.systems.primary.domain.learners.pupils import pupils
    return tuple(pupils.YEAR_GROUPS)


class PrimaryAdapter(PhaseAdapter):
    """Primary School's side of the four-method transition contract."""

    system = SYSTEM_KEY

    # ── Learner logins ──────────────────────────────────────────────

    learner_login_roles = ("student",)

    def learner_ids_for_login(self, account: dict) -> list[str]:
        """The pupil this login is named after: pupil id or school email.

        Primary never provisions pupil logins itself, so there is no
        sign-in rule to mirror; a login an administrator makes is paired
        only when its username is unmistakably one pupil's — the pupil id,
        or the pupil's (unique) school email.
        """
        from education_system.systems.primary.domain.learners.pupils import pupils

        username = str(account.get("username") or "").strip()
        if not username:
            return []
        pupils.init_db()
        with pupils._connect() as conn:
            rows = conn.execute(
                "SELECT pupil_id FROM pupils WHERE UPPER(pupil_id) = UPPER(?) "
                "OR LOWER(email) = LOWER(?)", (username, username)).fetchall()
        return [str(r[0]) for r in rows]

    # ── Destination side ────────────────────────────────────────────

    def create_applicant(self, handover: HandoverRequest) -> ApplicantResult:
        """Hold a place for an arriving child. Idempotent on journey_id."""
        from education_system.systems.primary.domain.learners.pupils import pupils

        if handover.source_system == "local_authority":
            return self._local_authority_place(handover)
        existing = pupils.find_by_journey(handover.journey_id)
        if (existing is not None and existing.roll_status == "left"
                and handover.source_system == "alternative_provision"):
            # Back from alternative provision to the school that sole-registered
            # them out: the same record re-opens (its leaving is kept on the
            # platform's enrolment history) instead of a duplicate pupil.
            existing = pupils.set_roll_status(existing.pupil_id, "applicant")
            logger.info("Primary pupil %s re-admitted as an applicant from "
                        "alternative provision (journey %s)",
                        existing.pupil_id, handover.journey_id)
        if existing is not None:
            return ApplicantResult(
                local_applicant_id=existing.pupil_id,
                year_group=existing.year_group,
                notes=f"existing record, {existing.roll_status}")

        identity = _identity(handover)
        first = identity.get("first_name") or identity.get("given_name")
        last = identity.get("last_name") or identity.get("family_name")
        if not first or not last:
            raise AdapterError(
                f"Handover for journey {handover.journey_id} carries no usable "
                f"name; primary cannot create an applicant without one")
        year = (handover.year_group or ENTRY_YEAR).strip()
        if year not in pupils.YEAR_GROUPS:
            raise AdapterError(
                f"Year group must be one of {', '.join(pupils.YEAR_GROUPS)}")
        guardian = _first_guardian(handover)
        send = handover.get("send_support") or handover.get("send_provision")
        base = {
            "first_name": first,
            "last_name": last,
            "year_group": year,
            "class_name": handover.get("class_name") or "",
            "date_of_birth": identity.get("date_of_birth") or "",
            "parent_name": guardian.get("name") or "",
            "parent_phone": guardian.get("phone") or "",
            "medical_notes": _medical_notes(handover),
            "send_status": "yes" if send else "",
        }
        extras = _parity_extras(identity, guardian, handover)
        try:
            try:
                pupil = pupils.create_pupil({**base, **extras}, roll_status="applicant",
                                            journey_id=handover.journey_id)
            except pupils.ValidationError as exc:
                if not extras:
                    raise
                # A detail the previous setting recorded that this school's
                # rules refuse (a UPN already held, an odd postcode) must not
                # stop the child arriving; the core record still crosses.
                logger.warning("Primary applicant for journey %s: extra details "
                               "refused (%s); creating without them",
                               handover.journey_id, exc)
                pupil = pupils.create_pupil(base, roll_status="applicant",
                                            journey_id=handover.journey_id)
        except pupils.ValidationError as exc:
            raise AdapterError(
                f"Primary could not create an applicant for journey "
                f"{handover.journey_id}: {exc}") from exc
        logger.info("Created primary applicant %s for journey %s (from %s)",
                    pupil.pupil_id, handover.journey_id, handover.source_system)
        return ApplicantResult(local_applicant_id=pupil.pupil_id, year_group=year,
                               notes=f"applicant created from {handover.boundary}")

    @staticmethod
    def _local_authority_place(handover: HandoverRequest) -> ApplicantResult:
        """A school place the local authority allocated: an accepted
        application on this school's Admissions page (enrolling it puts the
        child on roll and tells the platform). Idempotent on the transition."""
        from education_system.systems.primary.domain.admissions import admissions

        if not handover.transition_id:
            raise AdapterError("A school place needs its transition id")
        identity = _identity(handover)
        guardian = _first_guardian(handover)
        place = handover.get("placement_details") or {}
        place = place if isinstance(place, dict) else {}
        year = str(handover.year_group or identity.get("year_group") or "").strip()
        if year not in pupils_year_groups():
            raise AdapterError(f"The place is for {year or 'an unknown year'}: this school "
                               "takes Reception to Year 6")
        basis = place.get("basis") or "allocated"
        start = place.get("start_date")
        note = (f"School place from the local authority ({place.get('round') or 'in-year'}, "
                f"{str(basis).lower()})" + (f", starting {start}" if start else "")
                + (f". Ref: {place['reference']}" if place.get("reference") else "") + ".")
        try:
            app = admissions.create_platform_place({
                "applicant_first": identity.get("first_name") or identity.get("given_name"),
                "applicant_last": identity.get("last_name") or identity.get("family_name"),
                "date_of_birth": identity.get("date_of_birth") or "",
                "year_applying": year, "parent_name": guardian.get("name") or "",
                "parent_phone": guardian.get("phone") or "",
                "parent_email": guardian.get("email") or "", "notes": note,
            }, transition_id=handover.transition_id, journey_id=handover.journey_id,
                source="local_authority")
        except admissions.ValidationError as exc:
            raise AdapterError(f"Primary couldn't record the place: {exc}") from exc
        return ApplicantResult(local_applicant_id=app.application_id, year_group=year,
                               notes="accepted application on Admissions")

    @staticmethod
    def place_withdrawn(local_applicant_id: str, reason: str) -> None:
        """The local authority withdrew a place (declined, or the offer
        changed): its accepted application here is withdrawn too."""
        from education_system.systems.primary.domain.admissions import admissions
        app = admissions.get_application(str(local_applicant_id))
        if app is None or app.status in ("enrolled", "withdrawn", "rejected"):
            return
        admissions.set_status(app.application_id, "withdrawn")
        logger.info("Primary application %s withdrawn by the local authority: %s",
                    app.application_id, reason)

    def create_enrolment(self, journey_id: str,
                         application_id: str | None = None,
                         **details: Any) -> EnrolmentResult:
        """Put the applicant on roll. Idempotent on journey_id."""
        from education_system.systems.primary.domain.learners.pupils import pupils

        pupil = pupils.find_by_journey(journey_id)
        if pupil is None and application_id:
            pupil = pupils.get_pupil(str(application_id))
        if pupil is None:
            raise AdapterError(
                f"No primary applicant for journey {journey_id}; "
                f"create_applicant must run before create_enrolment")
        if pupil.roll_status == "left":
            raise AdapterError(
                f"Primary pupil {pupil.pupil_id} has left; re-admission is a "
                f"new application")
        if pupil.roll_status == "applicant":
            overrides = {key: str(details[key]).strip()
                         for key in ("year_group", "class_name")
                         if details.get(key)}
            if overrides:
                try:
                    pupils.update_pupil(pupil.pupil_id,
                                        {**_editable(pupil), **overrides})
                except pupils.ValidationError as exc:
                    raise AdapterError(str(exc)) from exc
            pupil = pupils.set_roll_status(pupil.pupil_id, pupils.ON_ROLL)
            logger.info("Primary pupil %s on roll (journey %s)",
                        pupil.pupil_id, journey_id)
        return PupilEnrolmentResult(
            local_student_id=pupil.pupil_id, year_group=pupil.year_group,
            start_date=details.get("start_date"), email=pupil.email,
            notes="on roll")

    # ── Source side ─────────────────────────────────────────────────

    def export_handover(self, local_student_id: str,
                        consent: bool | set[str] | None = None, *,
                        destination_system: str | None = None) -> ExportResult:
        """What the school holds for the PRIMARY_TO_SECONDARY keys.

        Each section is read from the module that owns it (KS2 SATs, MTC,
        phonics, reading levels, assessment records, attendance, Pupil
        Premium, SEND, interventions, medical records, parent contacts and
        the Year 6 transition report). Sensitive sections are gathered here
        regardless of consent; ``handover.build_handover`` withholds them.
        A section with nothing recorded is ``None``.
        """
        from education_system.systems.primary.domain.learners.pupils import pupils

        pupil = pupils.get_pupil(local_student_id)
        if pupil is None:
            raise AdapterError(f"No primary pupil {local_student_id} to export")
        record: dict[str, Any] = {
            "child_identity": _child_identity(pupil),
            "guardians": _section("guardians", _guardians, pupil),
            "ks2_results": _section("ks2_results", _ks2_results, pupil),
            "core_assessments": _section("core_assessments", _core_assessments, pupil),
            "attendance_summary": _section("attendance_summary", _attendance_summary, pupil),
            "support_indicators": _section("support_indicators", _support_indicators, pupil),
            "send_provision": _section("send_provision", _send_provision, pupil),
            "current_interventions": _section("current_interventions",
                                              _current_interventions, pupil),
            "medical_requirements": _section("medical_requirements",
                                             _medical_requirements, pupil),
            "transition_report": _section("transition_report", _transition_report, pupil),
        }
        return ExportResult(record=record, local_student_id=pupil.pupil_id)

    def close_enrolment(self, local_student_id: str, reason: str,
                        **details: Any) -> None:
        """Record the leaver and take the pupil off roll. Never deletes."""
        from education_system.systems.primary.domain.learners.pupils import pupils
        from education_system.systems.primary.domain.learners.pupils.leavers import leavers

        pupil = pupils.get_pupil(local_student_id)
        if pupil is None:
            logger.warning("close_enrolment: no primary pupil %s", local_student_id)
            return
        if pupil.roll_status == "left":
            logger.info("Primary pupil %s has already left — not re-closing",
                        local_student_id)
            return
        end_date = details.get("end_date") or date.today().isoformat()
        if leaver_id_for(pupil.pupil_id) is None:
            leavers.create_leaver({
                "pupil_id": pupil.pupil_id,
                "first_name": pupil.first_name,
                "last_name": pupil.last_name,
                "date_of_birth": pupil.date_of_birth or "",
                "year_left": pupil.year_group,
                "leaving_date": end_date,
                "destination_school": (details.get("destination_school")
                                       or details.get("destination") or ""),
                "current_email": details.get("current_email") or "",
                "parent_phone": pupil.parent_phone or "",
                "reason": reason,
                "status": "active",
                "notes": details.get("notes") or "",
            })
        pupils.set_roll_status(pupil.pupil_id, "left", left_date=end_date,
                               exit_reason=reason)
        logger.info("Primary pupil %s taken off roll (%s)", pupil.pupil_id, reason)

    # ── The SEND service (platform.cross_system.send_referrals) ─────

    def receive_send_update(self, local_student_id: str,
                            update: dict[str, Any]) -> str | None:
        """An EHCP decision from the SEND service (or the local authority's
        EHC team, ``update["by"]``), onto this school's SEN record: this year's SEND register stage (assessment in progress,
        EHC plan, SEN support) with a dated note, and the pupil's SEN status
        (EHC plan when the final plan is issued, SEN support when it
        ceases). Returns what changed."""
        import datetime as _dt

        from education_system.platform.cross_system.send_referrals import describe
        from education_system.systems.primary.domain.learners.pupils import (
            pupils,
            year6_transition,
        )
        from education_system.systems.primary.domain.pastoral.send import send

        if update.get("kind") != "ehcp":
            return None
        pupil = pupils.get_pupil(str(local_student_id))
        if pupil is None:
            raise AdapterError(f"No primary pupil {local_student_id}")
        stage = update.get("stage")
        new_stage = _SEND_SERVICE_STAGE.get(stage)
        year = year6_transition._slash_year(_academic_year())
        record = send.get_for(pupil.pupil_id, year)
        cols = ("provision_stage", "primary_need", "secondary_need", "status", "senco",
                "keyworker", "parent_contact", "parent_email", "ehcp_reference",
                "start_date", "next_review_date", "provision_summary", "diagnosis",
                "notes")
        data: dict[str, Any] = ({c: getattr(record, c) for c in cols} if record is not None
                                else {"start_date": _dt.date.today().isoformat(),
                                      "status": "Active"})
        line = f"{_dt.date.today().isoformat()} {describe(update)}"
        data["notes"] = "\n".join(x for x in (data.get("notes"), line) if x)
        if new_stage and not (stage in ("Refused to assess", "Not issued")
                              and str(data.get("provision_stage") or "").startswith(
                                  "EHCP (")):
            data["provision_stage"] = new_stage
        data["status"] = "Active" if data.get("status") == "Discharged" else data["status"]
        send.upsert({**data, "pupil_id": pupil.pupil_id, "academic_year": year})
        target = {"Final issued": "E", "Ceased": "K"}.get(stage)
        if target == "K" and pupil.sen_status != "E":
            target = None
        if target and target != pupil.sen_status:
            try:
                pupils.update_pupil(pupil.pupil_id, {**_editable(pupil), "sen_status": target})
            except pupils.ValidationError as exc:
                raise AdapterError(str(exc)) from exc
            return ("SEN status is now EHC plan" if target == "E"
                    else "SEN status is back to SEN support")
        return f"SEND register: {data['provision_stage'].lower()}" if new_stage else None


#: The SEND service's EHCP stage → this school's SEND register stage.
_SEND_SERVICE_STAGE = {
    "Requested": "EHCP assessment in progress",
    "Assessing": "EHCP assessment in progress",
    "Draft issued": "EHCP assessment in progress",
    "Final issued": "EHCP (Education, Health, Care Plan)",
    "Refused to assess": "SEN Support",
    "Not issued": "SEN Support",
    "Ceased": "SEN Support",
}



ADAPTER = PrimaryAdapter()


def register() -> PrimaryAdapter:
    """Register this adapter with the platform. Idempotent."""
    registry.register(ADAPTER, replace=True)
    return ADAPTER


__all__ = ["SYSTEM_KEY", "PrimaryAdapter", "PupilEnrolmentResult", "ADAPTER",
           "leaver_id_for", "register"]
