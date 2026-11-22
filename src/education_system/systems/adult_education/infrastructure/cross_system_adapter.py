"""Adult Education's side of the platform transition contract.

Three links on the platform run through this adapter (nothing here imports
another system):

* **FE College → Adult Education** (``platform.cross_system.
  adult_education_applications``): ``create_applicant`` finds the adult
  (journey, ULN, e-mail, or name and date of birth) or adds them as an
  *Enquiry*, and records the referral on *Referrals from FE College*.
  Idempotent on the transition.
* **Adult Education → FE College** (``fe_applications``) and **Adult
  Education → University** (``university_applications``, Access to HE):
  ``export_handover`` is what this service holds - identity, contact,
  current courses, achievements, prior qualifications, employment and
  (only with consent, filtered by ``handover.build_handover``) support.
* ``close_enrolment`` - the learner left for FE or university: the
  destination is recorded on *Progression & Destinations* and, with no
  course still open, the learner is marked Completed. Never deletes.
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

SYSTEM_KEY = "adult_education"
SOURCE_NAMES = {"fe_college": "FE College"}
_OPEN_ENROLMENTS = ("Enrolled", "Waiting list")


def _block(handover: HandoverRequest, key: str) -> dict[str, Any]:
    raw = handover.get(key)
    return raw if isinstance(raw, dict) else {}


def _identity(handover: HandoverRequest) -> dict[str, Any]:
    for key in ("learner_identity", "student_identity", "child_identity"):
        raw = handover.get(key)
        if isinstance(raw, dict) and raw:
            return raw
    return {}


def _text(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, dict):
        return "; ".join(f"{k.replace('_', ' ')}: {_text(v)}" for k, v in value.items()
                         if v not in (None, "", [], {}))
    if isinstance(value, (list, tuple)):
        return "; ".join(_text(v) for v in value if v not in (None, "", [], {}))
    return str(value).strip()


def _gender(value: Any) -> str:
    t = " ".join(str(value or "").split()).lower()
    return {"f": "Female", "female": "Female", "m": "Male", "male": "Male",
            "non-binary": "Non-binary", "other": "Other"}.get(t, "Prefer not to say")


def _learner_id(local_student_id: Any) -> int | None:
    """A learner's row id from its id or its reference (``AE000012``)."""
    from education_system.systems.adult_education.infrastructure import database as db
    text = str(local_student_id or "").strip()
    if text.isdigit():
        return int(text)
    with db.connect() as conn:
        row = conn.execute("SELECT id FROM learners WHERE learner_ref = ? COLLATE NOCASE",
                           (text,)).fetchone()
    return int(row[0]) if row else None


def _learner_for(journey_id: str | None, identity: dict[str, Any],
                 contact: dict[str, Any]) -> int | None:
    from education_system.systems.adult_education.infrastructure import database as db
    with db.connect() as conn:
        if journey_id:
            row = conn.execute("SELECT id FROM learners WHERE journey_id = ?",
                               (journey_id,)).fetchone()
            if row:
                return int(row[0])
        uln = str(identity.get("uln") or "").replace(" ", "")
        if uln:
            row = conn.execute("SELECT id FROM learners WHERE uln = ?", (uln,)).fetchone()
            if row:
                return int(row[0])
        email = str(contact.get("email") or identity.get("email") or "").strip()
        if email:
            row = conn.execute("SELECT id FROM learners WHERE email = ? COLLATE NOCASE",
                               (email,)).fetchone()
            if row:
                return int(row[0])
        row = conn.execute(
            "SELECT id FROM learners WHERE first_name = ? COLLATE NOCASE AND "
            "last_name = ? COLLATE NOCASE AND dob = ?",
            (identity.get("first_name") or "", identity.get("last_name") or "",
             str(identity.get("date_of_birth") or identity.get("dob") or "")[:10])).fetchone()
        return int(row[0]) if row else None


def _support_text(handover: HandoverRequest) -> str:
    """Support detail the college released (only present with consent)."""
    return "\n".join(t for t in (_text(handover.get(k)) for k in
                                 ("send_support", "support_indicators", "support_plan",
                                  "reasonable_adjustments")) if t)


class AdultEducationAdapter(PhaseAdapter):
    """Adult Education's side of the four-method transition contract."""

    system = SYSTEM_KEY

    # ── Destination side (FE College → Adult Education) ──────────────

    def create_applicant(self, handover: HandoverRequest) -> ApplicantResult:
        """An FE referral: the learner (found, or added as an Enquiry) and
        the referral on *Referrals from FE College*."""
        from education_system.systems.adult_education.core import records as r
        from education_system.systems.adult_education.infrastructure import database as db
        from education_system.systems.adult_education.modules import learners, referrals

        if not handover.transition_id:
            raise AdapterError("A referral to adult education needs its transition id")
        done = referrals.for_transition(handover.transition_id)
        if done is not None:
            return ApplicantResult(local_applicant_id=str(done["learner_id"]),
                                   notes="referral already recorded")
        ident = _identity(handover)
        contact = _block(handover, "contact_details")
        first, last = ident.get("first_name"), ident.get("last_name")
        dob = str(ident.get("date_of_birth") or ident.get("dob") or "")[:10]
        if not (first and last and dob):
            raise AdapterError("The referral needs the learner's name and date of birth")
        details = _block(handover, "referral_details")
        source = handover.source_system or ""
        college = SOURCE_NAMES.get(source, source or "FE College")
        actor = f"platform:{source}"
        learner_id = _learner_for(handover.journey_id, ident, contact)
        try:
            if learner_id is None:
                learner_id = self._add_learner(handover, ident, contact, dob, college, actor)
            with db.connect() as conn:
                conn.execute(
                    "UPDATE learners SET journey_id = COALESCE(NULLIF(journey_id, ''), ?), "
                    "updated_at = datetime('now') WHERE id = ?",
                    (handover.journey_id, learner_id))
            r.save(referrals.FE_REFERRALS, {
                "learner_id": learner_id,
                "received": str(details.get("referral_date") or date.today().isoformat())[:10],
                "college": college,
                "course": str(details.get("course") or "Not stated")[:200],
                "reason": details.get("reason") or "",
                "intended_start": details.get("intended_start") or None,
                "referrer": details.get("referrer") or "",
                "status": "New", "source_system": source,
                "transition_id": handover.transition_id,
                "consent_to_share": 1 if details.get("consent") else 0,
                "safeguarding_ref": str(handover.get("safeguarding_reference") or "")[:120],
            }, actor=actor)
        except r.ValidationError as exc:
            raise AdapterError(f"Adult Education couldn't record the referral: {exc}") \
                from exc
        finally:
            # Hooks fired by these saves are for a person at a form; there
            # isn't one here.
            r.take_notices()
        row = r.get(learners.LEARNERS, learner_id) or {}
        logger.info("FE referral for journey %s from %s: adult learner %s",
                    handover.journey_id, source, learner_id)
        return ApplicantResult(local_applicant_id=str(learner_id),
                               notes=f"referral recorded for {row.get('learner_ref')}")

    @staticmethod
    def _add_learner(handover: HandoverRequest, ident: dict, contact: dict, dob: str,
                     college: str, actor: str) -> int:
        from education_system.systems.adult_education.core import records as r
        from education_system.systems.adult_education.modules import learners
        prior = _text(handover.get("prior_attainment"))
        notes = [f"Referred by {college} through the platform."]
        if prior:
            notes.append(f"Prior attainment ({college}): {prior}")
        support = _support_text(handover)
        values = {
            "first_name": ident["first_name"], "last_name": ident["last_name"],
            "dob": dob, "gender": _gender(ident.get("gender")),
            "email": contact.get("email") or "", "phone": contact.get("phone") or "",
            "address_line1": contact.get("address") or "",
            "postcode": contact.get("postcode") or "",
            "uln": str(ident.get("uln") or "").replace(" ", ""),
            "support_needs": support, "has_learning_difficulty": 1 if support else 0,
            "status": "Enquiry", "notes": "\n".join(notes),
        }
        try:
            return r.save(learners.LEARNERS, values, actor=actor)
        except r.ValidationError as first:
            # A detail this service's checks refuse (an old ULN, a phone
            # number in another format) shouldn't strand the referral: keep
            # the learner with what passes and say what was left off.
            for key in ("uln", "postcode", "phone", "email", "address_line1"):
                values[key] = ""
            values["notes"] += f"\nSome details from {college} weren't kept: {first}"
            return r.save(learners.LEARNERS, values, actor=actor)

    def create_enrolment(self, journey_id: str, application_id: str | None = None,
                         **details: Any) -> EnrolmentResult:
        """The learner is on this service's books (their classes are
        enrolled on the Enrolments page)."""
        from education_system.systems.adult_education.core import records as r
        from education_system.systems.adult_education.modules import learners

        learner_id = _learner_for(journey_id, {}, {}) or _learner_id(application_id)
        row = r.get(learners.LEARNERS, learner_id) if learner_id else None
        if row is None:
            raise AdapterError(f"No adult learner for journey {journey_id}; the referral "
                               "must arrive first")
        return EnrolmentResult(local_student_id=str(row["id"]),
                               start_date=details.get("start_date"),
                               notes=f"learner {row.get('learner_ref')}")

    # ── Source side (→ FE College, → University) ─────────────────────

    def export_handover(self, local_student_id: str,
                        consent: bool | set[str] | None = None, *,
                        destination_system: str | None = None) -> ExportResult:
        """What this service holds about the learner. Consent is applied by
        ``handover.build_handover`` (support is sensitive)."""
        from education_system.systems.adult_education.core import records as r
        from education_system.systems.adult_education.infrastructure import database as db
        from education_system.systems.adult_education.modules import learners, support

        lid = _learner_id(local_student_id)
        row = r.get(learners.LEARNERS, lid) if lid else None
        if row is None:
            raise AdapterError(f"No adult education learner {local_student_id}")
        lid = row["id"]
        with db.connect() as conn:
            courses = [dict(x) for x in conn.execute(
                "SELECT c.title AS course, c.level, c.subject, c.accredited, "
                "c.awarding_body, c.qualification_ref, k.start_date, k.end_date, "
                "e.status, e.outcome, e.enrolled_on "
                "FROM enrolments e JOIN classes k ON k.id = e.class_id "
                "JOIN courses c ON c.id = k.course_id WHERE e.learner_id = ? "
                "ORDER BY k.start_date", (lid,)).fetchall()]
        current = [{k: c[k] for k in ("course", "level", "subject", "start_date", "end_date",
                                      "status")}
                   for c in courses if c["status"] in _OPEN_ENROLMENTS]
        achieved = [{"course": c["course"], "level": c["level"], "outcome": c["outcome"],
                     "accredited": bool(c["accredited"]),
                     "awarding_body": c.get("awarding_body"),
                     "qualification_ref": c.get("qualification_ref"),
                     "completed": c["end_date"]}
                    for c in courses if c["status"] == "Completed"
                    and c["outcome"] in ("Achieved", "Partially achieved")]
        prior = [{"title": q["title"], "level": q["level"], "subject": q.get("subject"),
                  "grade": q.get("grade"), "date_achieved": q.get("date_achieved"),
                  "evidence": q.get("evidence_status")}
                 for q in r.list_records(learners.PRIOR, learner_id=lid)
                 if q.get("evidence_status") != "Rejected"]
        plans = [{"need": p["need"], "support": p["support"],
                  "adjustments": p.get("adjustments"), "review_date": p.get("review_date")}
                 for p in r.list_records(support.SUPPORT, learner_id=lid)
                 if p.get("status") == "Active"]
        address = ", ".join(x for x in (row.get("address_line1"), row.get("address_line2"),
                                        row.get("town")) if x)
        record: dict[str, Any] = {
            "student_identity": {
                "first_name": row["first_name"], "last_name": row["last_name"],
                "preferred_name": row.get("preferred_name") or None,
                "date_of_birth": row["dob"], "gender": row.get("gender"),
                "uln": row.get("uln") or None, "learner_ref": row.get("learner_ref"),
                "adult_education_learner_id": str(lid)},
            "contact_details": {"email": row.get("email") or None,
                                "phone": row.get("phone") or None,
                                "address": address or None,
                                "postcode": row.get("postcode") or None},
            "current_programme": current or None,
            "achieved_qualifications": achieved or None,
            "prior_learning": prior or None,
            "employment": {"employment_status": row.get("employment_status")}
            if row.get("employment_status") else None,
        }
        if row.get("support_needs") or plans:
            record["support_referral"] = {
                "learning_difficulty": bool(row.get("has_learning_difficulty")),
                "needs": row.get("support_needs") or None, "plans": plans or None}
        return ExportResult(record={k: v for k, v in record.items() if v is not None},
                            local_student_id=str(lid))

    def close_enrolment(self, local_student_id: str, reason: str,
                        **details: Any) -> None:
        """The learner left for FE or university: the destination goes on
        *Progression & Destinations*; with no course still open the learner
        is Completed. Never deletes."""
        from education_system.systems.adult_education.core import records as r
        from education_system.systems.adult_education.infrastructure import database as db
        from education_system.systems.adult_education.modules import progress

        lid = _learner_id(local_student_id)
        if lid is None:
            logger.warning("close_enrolment: no adult learner %s", local_student_id)
            return
        text = (reason or "").lower()
        destination = ("Higher education" if "universit" in text
                       else "FE college" if "fe college" in text or "further" in text
                       else "Unknown")
        when = str(details.get("end_date") or date.today().isoformat())[:10]
        when = min(when, date.today().isoformat())   # destinations are recorded after
        try:
            r.save(progress.DESTINATIONS, {
                "learner_id": lid, "recorded_on": when, "destination": destination,
                "details": f"{reason} (through the platform)"[:200], "source": "Learner",
            }, actor="platform")
        except r.ValidationError as exc:
            logger.warning("Destination for adult learner %s not recorded: %s", lid, exc)
        finally:
            r.take_notices()
        with db.connect() as conn:
            still_open = conn.execute(
                "SELECT COUNT(*) FROM enrolments WHERE learner_id = ? AND status IN "
                "('Enrolled', 'Waiting list')", (lid,)).fetchone()[0]
            if still_open:
                return
            n = conn.execute("UPDATE learners SET status = 'Completed', updated_at = "
                             "datetime('now') WHERE id = ? AND status IN "
                             "('Active', 'On a break')", (lid,)).rowcount
            if n:
                conn.execute("INSERT INTO history (actor, record_type, record_id, learner_id, "
                             "action, summary) VALUES ('platform', 'learners', ?, ?, "
                             "'updated', ?)", (lid, lid, f"Left: {reason[:200]}"))


ADAPTER = AdultEducationAdapter()


def register() -> AdultEducationAdapter:
    """Register this adapter with the platform. Idempotent."""
    registry.register(ADAPTER, replace=True)
    return ADAPTER


__all__ = ["SYSTEM_KEY", "AdultEducationAdapter", "ADAPTER", "register"]
