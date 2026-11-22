"""Special Education (SEND) side of the platform transition contract.

Primary and secondary schools send requests here through the platform
(``platform.cross_system.send_referrals``); this adapter is the SEND
service's end. The pupil stays at their school throughout - the SEND case
runs alongside the school place.

* ``create_applicant`` - a school's request arrives: the pupil is found
  (journey, UPN, or name and date of birth) or added to the SEND register,
  the parents/carers the school released become contacts, the request is
  recorded under School Requests and, for an EHC needs assessment request,
  an EHCP opens at *Requested* (unless one is already open). Idempotent on
  the transition.
* ``create_enrolment`` - the case is open (the learner is Active).
* ``export_handover`` - the SEND service's summary of the pupil.
* ``close_enrolment`` - the case closes: the learner is archived. Never
  deletes.

Nothing here imports a school system.
"""

from __future__ import annotations

import logging
import re
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

SYSTEM_KEY = "special_education"
SCHOOL_NAMES = {"primary": "Primary School", "secondary": "Secondary School"}
#: School census SEN codes → the SEND register's status, and back.
_SEN = {"N": "Monitoring", "K": "SEN Support", "E": "EHCP"}
_SEN_BACK = {"Monitoring": "N", "SEN Support": "K", "EHCP": "E", "No longer SEN": "N"}
_UPN = re.compile(r"^[A-Z][0-9]{11}[0-9A-Z]$")


def send_year(value: Any) -> str | None:
    """A school's year group ("R", "4", 9, "Year 9") as the register records it."""
    text = str(value or "").strip()
    if not text:
        return None
    if text.upper() in ("R", "RECEPTION"):
        return "Reception"
    if text.lower() == "nursery":
        return "Nursery"
    digits = text.lower().replace("year", "").strip()
    return f"Year {int(digits)}" if digits.isdigit() and 1 <= int(digits) <= 14 else None


def _gender(value: Any) -> str:
    t = " ".join(str(value or "").split()).lower()
    if t in ("f", "female", "girl"):
        return "Female"
    if t in ("m", "male", "boy"):
        return "Male"
    if t in ("other", "non-binary"):
        return "Other"
    return "Not stated"


def _identity(handover: HandoverRequest) -> dict[str, Any]:
    for key in ("child_identity", "student_identity", "learner_identity"):
        raw = handover.get(key)
        if isinstance(raw, dict) and raw:
            return raw
    return {}


def _block(handover: HandoverRequest, key: str) -> dict[str, Any]:
    raw = handover.get(key)
    return raw if isinstance(raw, dict) else {}


def _sen(handover: HandoverRequest) -> dict[str, Any]:
    for key in ("send_provision", "access_arrangements"):
        block = _block(handover, key)
        if block:
            return block
    return {}


def _need(code: Any) -> str | None:
    """A census need code ("ASD") as the register's choice ("ASD - Autistic …")."""
    from education_system.systems.special_education.modules import learners
    text = str(code or "").strip().upper()
    if not text:
        return None
    return next((n for n in learners.NEEDS if n.upper().startswith(text + " ")), None)


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


def _notes(handover: HandoverRequest, school: str) -> str:
    sen = _sen(handover)
    lines = [f"Added from a request by {school} through the platform."]
    needs = sen.get("needs") or []
    if needs and not _need(sen.get("primary_need")):
        lines.append("School's areas of need: " + ", ".join(str(n) for n in needs))
    for key, label in (("provision", "School's provision"), ("strategies", "Strategies"),
                       ("access_arrangements", "Access arrangements"),
                       ("exam_access", "Exam access")):
        if sen.get(key) and isinstance(sen[key], str):
            lines.append(f"{label}: {sen[key]}")
    medical = _medical_text(handover.get("medical_requirements"))
    if medical:
        lines.append("Medical: " + medical.replace("\n", "; "))
    return "\n".join(lines)


# ── lookups ──────────────────────────────────────────────────────────

def _learner_for(journey_id: str | None, identity: dict[str, Any]) -> int | None:
    from education_system.systems.special_education.infrastructure import database as db
    with db.connect() as conn:
        if journey_id:
            row = conn.execute("SELECT id FROM learners WHERE journey_id = ?",
                               (journey_id,)).fetchone()
            if row:
                return int(row[0])
        upn = str(identity.get("upn") or "").strip().upper()
        if upn:
            row = conn.execute("SELECT id FROM learners WHERE UPPER(upn) = ?",
                               (upn,)).fetchone()
            if row:
                return int(row[0])
        row = conn.execute(
            "SELECT id FROM learners WHERE LOWER(first_name) = LOWER(?) AND "
            "LOWER(last_name) = LOWER(?) AND dob = ?",
            (identity.get("first_name") or "", identity.get("last_name") or "",
             str(identity.get("date_of_birth") or "")[:10])).fetchone()
        return int(row[0]) if row else None


class SpecialEducationAdapter(PhaseAdapter):
    """The SEND service's side of the four-method transition contract."""

    system = SYSTEM_KEY

    # ── Destination side ────────────────────────────────────────────

    def create_applicant(self, handover: HandoverRequest) -> ApplicantResult:
        """A school's request: the pupil on the register, the request, and
        for an assessment request an EHCP at Requested."""
        from education_system.systems.special_education.core import records as r
        from education_system.systems.special_education.infrastructure import database as db
        from education_system.systems.special_education.modules import learners, requests

        if not handover.transition_id:
            raise AdapterError("A request to the SEND service needs its transition id")
        done = requests.for_transition(handover.transition_id)
        if done is not None:
            row = r.get(learners.LEARNERS, done["learner_id"]) or {}
            return ApplicantResult(local_applicant_id=str(done["learner_id"]),
                                   year_group=row.get("year_group"),
                                   notes="request already recorded")
        ident = _identity(handover)
        first, last = ident.get("first_name"), ident.get("last_name")
        dob = str(ident.get("date_of_birth") or "")[:10]
        if not (first and last and dob):
            raise AdapterError("The request needs the pupil's name and date of birth")
        details = _block(handover, "request_details")
        source = handover.source_system or ""
        school = SCHOOL_NAMES.get(source) or ident.get("school_name") or source
        year = send_year(ident.get("year_group"))
        sen = _sen(handover)
        actor = f"platform:{source}"
        learner_id = _learner_for(handover.journey_id, ident)
        try:
            if learner_id is None:
                upn = str(ident.get("upn") or "").strip().upper()
                learner_id = r.save(learners.LEARNERS, {
                    "first_name": first, "last_name": last,
                    "preferred_name": ident.get("preferred_name") or "",
                    "dob": dob, "gender": _gender(ident.get("gender")),
                    "upn": upn if _UPN.match(upn) else "",
                    "year_group": year or "", "setting": school,
                    "sen_status": _SEN.get(str(sen.get("sen_status") or "").upper(),
                                           "SEN Support"),
                    "primary_need": _need(sen.get("primary_need")) or "",
                    "secondary_need": _need(sen.get("secondary_need")) or "",
                    "date_identified": date.today().isoformat(),
                    "notes": _notes(handover, school), "status": "Active",
                }, actor=actor)
                self._add_guardians(learner_id, handover.get("guardians"), actor)
            with db.connect() as conn:
                # Known already (an earlier case, perhaps at another school):
                # the case is open again and the setting is where they are now.
                conn.execute(
                    "UPDATE learners SET status = 'Active', setting = ?, "
                    "year_group = COALESCE(?, year_group), "
                    "journey_id = COALESCE(NULLIF(journey_id, ''), ?), "
                    "updated_at = datetime('now') WHERE id = ?",
                    (school, year, handover.journey_id, learner_id))
            request = details.get("request")
            r.save(requests.SCHOOL_REQUESTS, {
                "learner_id": learner_id,
                "received": details.get("request_date") or date.today().isoformat(),
                "school": school,
                "request": request if request in requests.KINDS else "Other",
                "referrer": details.get("referrer") or "",
                "summary": details.get("summary") or "",
                "tried": details.get("tried") or "",
                "status": "New", "source_system": source,
                "transition_id": handover.transition_id,
                "consent_to_share": 1 if details.get("consent") else 0,
                "safeguarding_ref": str(handover.get("safeguarding_reference") or "")[:120],
            }, actor=actor)
            if request == requests.EHCNA:
                self._open_ehcp(learner_id, details, school, actor)
        except r.ValidationError as exc:
            raise AdapterError(f"The SEND service couldn't record the request: {exc}") \
                from exc
        finally:
            # Hooks fired by these saves told the school already; their lines
            # are for a person at a SEND form, and there isn't one here.
            r.take_notices()
        logger.info("SEND request for journey %s from %s: learner %s",
                    handover.journey_id, source, learner_id)
        return ApplicantResult(local_applicant_id=str(learner_id), year_group=year,
                               notes=f"request recorded from {handover.boundary}")

    @staticmethod
    def _open_ehcp(learner_id: int, details: dict, school: str, actor: str) -> None:
        from education_system.systems.special_education.core import records as r
        from education_system.systems.special_education.modules import ehcp
        open_plans = [p for p in r.list_records(ehcp.EHCPS, learner_id=learner_id)
                      if p.get("stage") not in ehcp.CLOSED]
        if open_plans:
            return   # already being assessed / has a plan: the request is on file
        r.save(ehcp.EHCPS, {
            "learner_id": learner_id,
            "request_date": details.get("request_date") or date.today().isoformat(),
            "requested_by": "School/setting", "stage": "Requested",
            "notes": f"Requested by {school}"
                     + (f" ({details['referrer']})" if details.get("referrer") else "")
                     + " through the platform.",
        }, actor=actor)

    @staticmethod
    def _add_guardians(learner_id: int, guardians: Any, actor: str) -> None:
        from education_system.systems.special_education.core import records as r
        from education_system.systems.special_education.modules import learners
        if isinstance(guardians, dict):
            guardians = [guardians]
        rels = learners.CONTACTS.fields_by_name["relationship"].choices
        for g in guardians or []:
            if not isinstance(g, dict) or not g.get("name"):
                continue
            if not (g.get("phone") or g.get("email")):
                continue   # the register needs a way to reach them
            rel = str(g.get("relationship") or "")
            rel = next((x for x in rels if x.lower() == rel.lower()), "Other")
            values = {"learner_id": learner_id, "name": str(g["name"])[:120],
                      "relationship": rel,
                      "parental_responsibility": 1 if g.get("parental_responsibility",
                                                            True) else 0,
                      "phone": g.get("phone") or "", "email": g.get("email") or ""}
            try:
                r.save(learners.CONTACTS, values, actor=actor)
            except r.ValidationError:
                logger.info("SEND contact from the school refused for learner %s",
                            learner_id)

    def create_enrolment(self, journey_id: str, application_id: str | None = None,
                         **details: Any) -> EnrolmentResult:
        """The case is open: the learner is Active on the register."""
        from education_system.systems.special_education.core import records as r
        from education_system.systems.special_education.infrastructure import database as db
        from education_system.systems.special_education.modules import learners

        learner_id = _learner_for(journey_id, {}) or (
            int(application_id) if application_id and str(application_id).isdigit()
            else None)
        row = r.get(learners.LEARNERS, learner_id) if learner_id else None
        if row is None:
            raise AdapterError(f"No SEND learner for journey {journey_id}; the request "
                               "must arrive first")
        with db.connect() as conn:
            conn.execute("UPDATE learners SET status = 'Active' WHERE id = ?", (row["id"],))
        return EnrolmentResult(local_student_id=str(row["id"]),
                               year_group=row.get("year_group"),
                               start_date=details.get("start_date"), notes="case open")

    # ── Source side ─────────────────────────────────────────────────

    def export_handover(self, local_student_id: str,
                        consent: bool | set[str] | None = None, *,
                        destination_system: str | None = None) -> ExportResult:
        """The SEND service's summary: identity, parents, SEN status and
        needs, the current EHCP and provision (sensitive parts are withheld
        by ``handover.build_handover`` without consent)."""
        from education_system.systems.special_education.core import records as r
        from education_system.systems.special_education.modules import (
            ehcp,
            learners,
            provision,
        )

        try:
            row = r.get(learners.LEARNERS, int(str(local_student_id)))
        except ValueError:
            row = None
        if row is None:
            raise AdapterError(f"No SEND learner {local_student_id}")
        lid = row["id"]
        record: dict[str, Any] = {"child_identity": {
            "first_name": row["first_name"], "last_name": row["last_name"],
            "preferred_name": row.get("preferred_name"), "date_of_birth": row["dob"],
            "gender": row.get("gender"), "upn": row.get("upn") or None,
            "send_year_group": row.get("year_group"), "setting": row.get("setting"),
            "send_learner_id": str(lid)}}
        guardians = [{"name": c["name"], "relationship": c["relationship"],
                      "phone": c.get("phone"), "email": c.get("email"),
                      "parental_responsibility": bool(c.get("parental_responsibility"))}
                     for c in r.list_records(learners.CONTACTS, learner_id=lid)
                     if c["relationship"] not in ("Social worker", "Advocate")]
        if guardians:
            record["guardians"] = guardians
        plans = r.list_records(ehcp.EHCPS, learner_id=lid)
        live = [p for p in r.list_records(provision.PROVISION, learner_id=lid)
                if p.get("status") == "Active"]
        record["send_provision"] = {
            "sen_status": _SEN_BACK.get(row.get("sen_status") or "", "K"),
            "sen_status_label": row.get("sen_status"),
            "ehcp": row.get("sen_status") == "EHCP",
            "primary_need": row.get("primary_need"),
            "secondary_need": row.get("secondary_need"),
            "ehcp_stage": plans[0]["stage"] if plans else None,
            "ehcp_issued_on": plans[0].get("final_date") if plans else None,
            "provision": "; ".join(p["name"] for p in live) or None,
        }
        return ExportResult(record=record, local_student_id=str(lid))

    def close_enrolment(self, local_student_id: str, reason: str,
                        **details: Any) -> None:
        """The case closes: the learner is archived (kept, never deleted)."""
        from education_system.systems.special_education.infrastructure import database as db
        try:
            lid = int(str(local_student_id))
        except ValueError:
            logger.warning("close_enrolment: bad SEND learner id %s", local_student_id)
            return
        with db.connect() as conn:
            n = conn.execute("UPDATE learners SET status = 'Archived', updated_at = "
                             "datetime('now') WHERE id = ? AND status = 'Active'",
                             (lid,)).rowcount
            if n:
                conn.execute("INSERT INTO history (actor, record_type, record_id, learner_id, "
                             "action, summary) VALUES ('platform', 'learners', ?, ?, "
                             "'updated', ?)", (lid, lid, f"Case closed: {reason[:200]}"))


ADAPTER = SpecialEducationAdapter()


def register() -> SpecialEducationAdapter:
    """Register this adapter with the platform. Idempotent."""
    registry.register(ADAPTER, replace=True)
    return ADAPTER


__all__ = ["SYSTEM_KEY", "SpecialEducationAdapter", "ADAPTER", "send_year", "register"]
