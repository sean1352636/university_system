"""Alternative Provision side of the platform transition contract.

Primary and secondary schools refer pupils here through the platform
(``platform.cross_system.ap_referrals``); this adapter is the AP's end:

* ``create_applicant`` - a school's referral arrives: the pupil is found
  (journey, UPN, or name and date of birth) or created as *Referred*, the
  parents/carers the school released become contacts, and an open referral
  (status New) is recorded with the school's reason, registration and
  consent. Idempotent on the transition.
* ``create_enrolment`` - the pupil is on roll here.
* ``export_handover`` - what the AP releases when the pupil goes back to a
  school (identity, parents, the reintegration plan, attendance, progress,
  qualifications, behaviour, exclusions, SEN and medical; the platform
  withholds the sensitive parts without the parent's consent).
* ``close_enrolment`` - the pupil leaves: status Left, and any active or
  planned placement ends. Never deletes.

Nothing here imports a school system.
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

logger = logging.getLogger(__name__)

SYSTEM_KEY = "alternative_provision"
SCHOOL_NAMES = {"primary": "Primary School", "secondary": "Secondary School"}
_SEN = {"N": "No SEN", "K": "SEN Support", "E": "EHC plan"}
_SEN_BACK = {v: k for k, v in _SEN.items()}
_SEN_BACK["EHC needs assessment"] = "K"


# ── year groups and other conversions ────────────────────────────────

def ap_year(value: Any) -> str | None:
    """A school's year group ("R", "4", 9, "Year 9") as the AP records it."""
    text = str(value or "").strip()
    if not text:
        return None
    if text.upper() in ("R", "RECEPTION"):
        return "Reception"
    digits = text.lower().replace("year", "").strip()
    return f"Year {int(digits)}" if digits.isdigit() else None


def school_year(ap_year_group: str | None, system: str | None) -> Any:
    """The AP year group in the format *system* records it."""
    text = str(ap_year_group or "")
    if text == "Reception":
        return "R" if system == "primary" else None
    digits = text.replace("Year", "").strip()
    if not digits.isdigit():
        return None
    n = int(digits)
    if system == "primary":
        return str(n) if 1 <= n <= 6 else None
    if system == "secondary":
        return n if 7 <= n <= 11 else None
    return text


def _gender(value: Any) -> str:
    from education_system.systems.alternative_provision.modules import learners
    t = " ".join(str(value or "").split()).lower()
    if t in ("f", "female", "girl"):
        return "Female"
    if t in ("m", "male", "boy"):
        return "Male"
    return next((g for g in learners.GENDERS if g.lower() == t), "Prefer not to say")


def _identity(handover: HandoverRequest) -> dict[str, Any]:
    for key in ("child_identity", "student_identity", "learner_identity"):
        raw = handover.get(key)
        if isinstance(raw, dict) and raw:
            return raw
    return {}


def _block(handover: HandoverRequest, key: str) -> dict[str, Any]:
    raw = handover.get(key)
    return raw if isinstance(raw, dict) else {}


def _medical_text(raw: Any) -> str:
    if not raw:
        return ""
    if isinstance(raw, dict):
        parts = [str(raw.get("notes") or "").strip()]
        for c in raw.get("conditions") or []:
            parts.append(str(c.get("condition") if isinstance(c, dict) else c))
        for a in raw.get("allergies") or []:
            parts.append("Allergy: " + str(a.get("allergen") if isinstance(a, dict) else a))
        return "\n".join(p for p in parts if p and p != "None")
    return str(raw).strip()


def _send_status(handover: HandoverRequest) -> str:
    for key in ("send_provision", "access_arrangements", "send_support"):
        block = _block(handover, key)
        code = str(block.get("sen_status") or "").strip().upper()
        if code in _SEN:
            return _SEN[code]
        if block.get("ehcp"):
            return "EHC plan"
    return "No SEN"


# ── lookups ──────────────────────────────────────────────────────────

def _pupil_for(journey_id: str | None, identity: dict[str, Any]) -> dict | None:
    from education_system.systems.alternative_provision.infrastructure import database as db
    with db.connect() as conn:
        if journey_id:
            row = conn.execute("SELECT id FROM learners WHERE journey_id = ?",
                               (journey_id,)).fetchone()
            if row:
                return {"id": row[0]}
        upn = str(identity.get("upn") or "").strip().upper()
        if upn:
            row = conn.execute("SELECT id FROM learners WHERE UPPER(upn) = ?",
                               (upn,)).fetchone()
            if row:
                return {"id": row[0]}
        row = conn.execute(
            "SELECT id FROM learners WHERE LOWER(first_name) = LOWER(?) AND "
            "LOWER(last_name) = LOWER(?) AND dob = ?",
            (identity.get("first_name") or "", identity.get("last_name") or "",
             identity.get("date_of_birth") or "")).fetchone()
        return {"id": row[0]} if row else None


def _referral_for(transition_id: str) -> dict | None:
    from education_system.systems.alternative_provision.infrastructure import database as db
    with db.connect() as conn:
        row = conn.execute("SELECT id, learner_id FROM referrals WHERE transition_id = ?",
                           (transition_id,)).fetchone()
    return {"id": row[0], "learner_id": row[1]} if row else None


class AlternativeProvisionAdapter(PhaseAdapter):
    """Alternative Provision's side of the four-method transition contract."""

    system = SYSTEM_KEY

    # ── Destination side ────────────────────────────────────────────

    def create_applicant(self, handover: HandoverRequest) -> ApplicantResult:
        """A school's referral: a Referred pupil and an open referral."""
        from education_system.systems.alternative_provision.core import records as r
        from education_system.systems.alternative_provision.infrastructure import database as db
        from education_system.systems.alternative_provision.modules import learners, referrals

        if not handover.transition_id:
            raise AdapterError("A referral to alternative provision needs its transition id")
        done = _referral_for(handover.transition_id)
        if done is not None:
            row = r.get(learners.LEARNERS, done["learner_id"]) or {}
            return ApplicantResult(local_applicant_id=str(done["learner_id"]),
                                   year_group=row.get("year_group"),
                                   notes="referral already recorded")
        ident = _identity(handover)
        first, last = ident.get("first_name"), ident.get("last_name")
        dob = ident.get("date_of_birth")
        if not (first and last and dob):
            raise AdapterError("The referral needs the pupil's name and date of birth")
        details = _block(handover, "referral_details")
        source = handover.source_system or ""
        school = ident.get("school_name") or SCHOOL_NAMES.get(source, source)
        sole = details.get("registration") == "sole"
        try:
            today = date.today()
            year = ap_year(ident.get("year_group")) or learners.year_group_for(
                date.fromisoformat(str(dob)[:10]), today)
        except ValueError as exc:
            raise AdapterError(f"Bad date of birth on the referral: {dob}") from exc

        found = _pupil_for(handover.journey_id, ident)
        actor = f"platform:{source}"
        try:
            if found is None:
                support = _block(handover, "support_indicators")
                upn = str(ident.get("upn") or "").strip().upper()
                pupil_id = r.save(learners.LEARNERS, {
                    "first_name": first, "last_name": last,
                    "preferred_name": ident.get("preferred_name") or "",
                    "dob": str(dob)[:10], "gender": _gender(ident.get("gender")),
                    "upn": upn if upn and learners.upn_ok(upn) else "",
                    "year_group": year, "home_school": school,
                    "registration": learners.REGISTRATION[0 if sole else 1],
                    "sen_status": _send_status(handover),
                    "looked_after": 1 if support.get("lac") else 0,
                    "pupil_premium": 1 if support.get("pupil_premium") else 0,
                    "free_school_meals": 1 if support.get("fsm") else 0,
                    "eal": 1 if support.get("eal") else 0,
                    "medical_notes": _medical_text(handover.get("medical_requirements")),
                    "address_line1": ident.get("address_line1") or "",
                    "town": ident.get("town") or "",
                    "postcode": ident.get("postcode") or "",
                    "status": "Referred",
                    "notes": f"Referred by {school} through the platform.",
                }, actor=actor)
                self._add_guardians(pupil_id, handover.get("guardians"), actor)
            else:
                # Known here already (an earlier placement): a Left or
                # Reintegrated pupil goes back on roll when the placement starts.
                pupil_id = found["id"]
            with db.connect() as conn:
                conn.execute("UPDATE learners SET journey_id = ? WHERE id = ? AND "
                             "(journey_id IS NULL OR journey_id = '')",
                             (handover.journey_id, pupil_id))
            reason = details.get("reason")
            values = {
                "learner_id": pupil_id, "received": date.today().isoformat(),
                "referred_by": school,
                "referrer_name": details.get("referrer") or "",
                "reason": reason if reason in referrals.REASONS else "Other",
                "excluded_from": details.get("excluded_from") or None,
                "summary": details.get("summary") or "",
                "registration": "Sole" if sole else "Dual",
                "source_system": source, "transition_id": handover.transition_id,
                "consent_to_share": 1 if details.get("consent") else 0,
                "safeguarding_ref": str(handover.get("safeguarding_reference") or "")[:120],
                "status": "New",
            }
            try:
                r.save(referrals.REFERRALS, values, actor=actor)
            except r.ValidationError as exc:
                if "open referral" not in str(exc):
                    raise
                # The AP already has an open referral for this pupil (made by
                # hand): link it to the school's instead of making a second.
                with db.connect() as conn:
                    conn.execute(
                        "UPDATE referrals SET transition_id = ?, source_system = ?, "
                        "registration = ?, consent_to_share = ?, safeguarding_ref = ?, "
                        "updated_at = datetime('now') WHERE learner_id = ? AND status IN "
                        "('New', 'Triage', 'Waiting list') AND (transition_id IS NULL OR "
                        "transition_id = '')",
                        (handover.transition_id, source, values["registration"],
                         values["consent_to_share"], values["safeguarding_ref"], pupil_id))
        except r.ValidationError as exc:
            raise AdapterError(f"The AP couldn't record the referral: {exc}") from exc
        logger.info("AP referral for journey %s from %s: pupil %s", handover.journey_id,
                    source, pupil_id)
        return ApplicantResult(local_applicant_id=str(pupil_id), year_group=year,
                               notes=f"referral recorded from {handover.boundary}")

    @staticmethod
    def _add_guardians(pupil_id: int, guardians: Any, actor: str) -> None:
        from education_system.systems.alternative_provision.core import records as r
        from education_system.systems.alternative_provision.modules import learners
        if isinstance(guardians, dict):
            guardians = [guardians]
        first = True
        for g in guardians or []:
            if not isinstance(g, dict) or not g.get("name"):
                continue
            rel = str(g.get("relationship") or "")
            rel = next((x for x in learners.RELATIONSHIPS if x.lower() == rel.lower()),
                       "Other")
            values = {"learner_id": pupil_id, "name": str(g["name"])[:120],
                      "relationship": rel,
                      "parental_responsibility": 1 if g.get("parental_responsibility",
                                                            True) else 0,
                      "phone": g.get("phone") or "", "email": g.get("email") or "",
                      "is_primary": 1 if first and (g.get("phone") or g.get("email")) else 0}
            try:
                r.save(learners.CONTACTS, values, actor=actor)
            except r.ValidationError:
                # A number or address the AP's rules refuse: keep the person.
                values.update(phone="", email="", is_primary=0,
                              notes=f"From the school: {g.get('phone') or ''} "
                                    f"{g.get('email') or ''}".strip())
                r.save(learners.CONTACTS, values, actor=actor)
            first = first and not values["is_primary"]

    def create_enrolment(self, journey_id: str, application_id: str | None = None,
                         **details: Any) -> EnrolmentResult:
        """The pupil is on roll at the AP."""
        from education_system.systems.alternative_provision.core import records as r
        from education_system.systems.alternative_provision.infrastructure import database as db
        from education_system.systems.alternative_provision.modules import learners

        found = _pupil_for(journey_id, {})
        pupil_id = found["id"] if found else (int(application_id) if application_id else None)
        row = r.get(learners.LEARNERS, pupil_id) if pupil_id else None
        if row is None:
            raise AdapterError(f"No AP pupil for journey {journey_id}; the referral "
                               "must arrive first")
        start = str(details.get("start_date") or date.today().isoformat())[:10]
        with db.connect() as conn:
            learners.set_status(conn, row["id"], "On roll", only_if=("Referred", "Left",
                                                                    "Reintegrated"),
                                on=start, actor="platform", why="admitted")
        return EnrolmentResult(local_student_id=str(row["id"]),
                               year_group=row.get("year_group"), start_date=start,
                               notes="on roll")

    # ── Source side ─────────────────────────────────────────────────

    def export_handover(self, local_student_id: str,
                        consent: bool | set[str] | None = None, *,
                        destination_system: str | None = None) -> ExportResult:
        """What the AP holds for the AP → school keys (sensitive ones are
        gathered regardless; ``handover.build_handover`` withholds them)."""
        from education_system.systems.alternative_provision.core import records as r
        from education_system.systems.alternative_provision.modules import (
            attendance,
            behaviour,
            learners,
            learning,
            reintegration,
        )

        try:
            pupil = r.get(learners.LEARNERS, int(str(local_student_id)))
        except ValueError:
            pupil = None
        if pupil is None:
            raise AdapterError(f"No AP pupil {local_student_id}")
        pid = pupil["id"]
        record: dict[str, Any] = {
            "child_identity": {
                "first_name": pupil["first_name"], "last_name": pupil["last_name"],
                "preferred_name": pupil.get("preferred_name"),
                "date_of_birth": pupil["dob"], "gender": pupil.get("gender"),
                "upn": pupil.get("upn") or None,
                "year_group": school_year(pupil.get("year_group"), destination_system),
                "ap_year_group": pupil.get("year_group"),
                "ap_pupil_id": str(pid), "school_name": "Alternative Provision",
                "address_line1": pupil.get("address_line1"), "town": pupil.get("town"),
                "postcode": pupil.get("postcode"),
            },
        }
        guardians = [{"name": c["name"], "relationship": c["relationship"],
                      "phone": c.get("phone"), "email": c.get("email"),
                      "parental_responsibility": bool(c.get("parental_responsibility"))}
                     for c in r.list_records(learners.CONTACTS, learner_id=pid)
                     if not c.get("no_contact") and c["relationship"] not in (
                         "Social worker", "Residential key worker")]
        if guardians:
            record["guardians"] = guardians
        plans = r.list_records(reintegration.REINTEGRATION, learner_id=pid)
        if plans:
            p = plans[0]
            record["reintegration_plan"] = {
                "target_school": p.get("target_school"), "readiness": p.get("readiness"),
                "phased_start": p.get("phased_start"), "full_return": p.get("full_return"),
                "school_contact": p.get("school_contact"),
                "transition_meeting": p.get("transition_meeting"), "status": p.get("status")}
            if p.get("support_package"):
                record["reintegration_support"] = p["support_package"]
        pct = attendance.rate(pid)
        if pct is not None:
            record["attendance_summary"] = {"percent": pct, "persistent_absence": pct < 90}
        progress = r.list_records(learning.PROGRESS, learner_id=pid)
        if progress:
            record["progress_summary"] = [
                {"subject": x["subject"], "kind": x["kind"], "assessed_on": x["assessed_on"],
                 "result": x["result"]} for x in progress[:12]]
        quals = r.list_records(learning.QUALIFICATIONS_RT, learner_id=pid)
        if quals:
            record["qualifications"] = [
                {"qualification": q["qualification"], "subject": q["subject"],
                 "level": q.get("level"), "status": q["status"], "result": q.get("result")}
                for q in quals]
        incidents = r.list_records(behaviour.INCIDENTS, learner_id=pid)
        if incidents:
            by: dict[str, int] = {}
            for i in incidents:
                by[i["severity"]] = by.get(i["severity"], 0) + 1
            record["behaviour_summary"] = {"incidents": len(incidents), "by_severity": by,
                                           "latest": incidents[0].get("incident_date")}
        cases = r.list_records(behaviour.SUSPENSIONS, learner_id=pid)
        if cases:
            record["exclusion_history"] = [
                {"type": c["kind"], "start_date": c["start_date"], "days": c.get("days"),
                 "reason": c["reason"], "status": c["status"]} for c in cases]
        sen = pupil.get("sen_status") or "No SEN"
        live_plans = [p for p in r.list_records(learning.PLANS, learner_id=pid)
                      if p.get("status") == "Active"]
        if sen != "No SEN" or live_plans:
            record["send_provision"] = {
                "sen_status": _SEN_BACK.get(sen, "N"), "ehcp": sen == "EHC plan",
                "provision": "; ".join(f"{p['kind']}: {p['targets']}" for p in live_plans)
                or None}
        if pupil.get("medical_notes"):
            record["medical_requirements"] = {"notes": pupil["medical_notes"],
                                              "conditions": []}
        return ExportResult(record=record, local_student_id=str(pid))

    def close_enrolment(self, local_student_id: str, reason: str,
                        **details: Any) -> None:
        """The pupil left the AP: status Left (unless already Reintegrated
        or Left) and their active / planned placements end. Never deletes."""
        from education_system.systems.alternative_provision.infrastructure import database as db
        from education_system.systems.alternative_provision.modules import learners

        try:
            pid = int(str(local_student_id))
        except ValueError:
            logger.warning("close_enrolment: bad AP pupil id %s", local_student_id)
            return
        end = str(details.get("end_date") or date.today().isoformat())[:10]
        with db.connect() as conn:
            learners.set_status(conn, pid, "Left", only_if=("On roll", "Referred"), on=end,
                                actor="platform", why=reason[:200])
            ended = conn.execute(
                "UPDATE placements SET status = 'Ended', end_date = ?, end_reason = 'Other', "
                "updated_at = datetime('now') WHERE learner_id = ? AND status IN "
                "('Active', 'Planned')", (end, pid)).rowcount
            if ended:
                conn.execute("INSERT INTO history (actor, record_type, record_id, learner_id, "
                             "action, summary) VALUES ('platform', 'placements', ?, ?, "
                             "'updated', ?)", (pid, pid, f"{ended} placement(s) ended: "
                                                          f"{reason[:200]}"))


ADAPTER = AlternativeProvisionAdapter()


def register() -> AlternativeProvisionAdapter:
    """Register this adapter with the platform. Idempotent."""
    registry.register(ADAPTER, replace=True)
    return ADAPTER


__all__ = ["SYSTEM_KEY", "AlternativeProvisionAdapter", "ADAPTER", "ap_year",
           "school_year", "register"]
