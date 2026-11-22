"""Local Authority Education's side of the platform transition contract.

Two kinds of link run through this adapter (nothing here imports another
system; see ``platform.cross_system.local_authority_links``):

* **Primary / Secondary → the authority** (notifications):
  ``create_applicant`` finds the child (journey, UPN, or name and date of
  birth) or adds them - with the school marked as this platform's primary
  or secondary in the Schools Register (added the first time it notifies),
  the parents and carers it sent, and the SEN, free school meals and EAL
  details the parent consented to share - then records the notification
  where it belongs: an attendance case, an exclusion, a CME case, an EHE
  record or an EHC needs assessment. Idempotent on the transition.
* **The authority → Primary / Secondary** (school places):
  ``export_handover`` is the child as the authority holds them: identity
  (year group as the receiving school counts it), the parents and carers
  with parental responsibility who may be contacted, SEN status and EHC
  plan (released only as consent allows).

``create_enrolment`` confirms the child is on the authority's books;
``close_enrolment`` only adds a note - the authority's record of a child is
never closed by another system.
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

SYSTEM_KEY = "local_authority"
SCHOOL_NAMES = {"primary": "Primary School", "secondary": "Secondary School"}

# The platform's notification kinds (local_authority_links.KINDS).
ATTENDANCE, SUSPENSION, PERMANENT = ("Attendance referral", "Suspension",
                                     "Permanent exclusion")
CME, EHE, EHCNA = ("Child missing education", "Elective home education",
                   "EHC needs assessment request")
_CME_SOURCE = {"Taken off roll - destination not known": "School (removed from roll)",
               "Unexplained absence of 10 school days or more":
                   "School (unexplained absence)"}
_SEN = {"E": "EHC plan", "K": "SEN Support"}
_RELATIONSHIP = {"mother": "Mother", "mum": "Mother", "father": "Father", "dad": "Father",
                 "step-parent": "Step-parent", "stepparent": "Step-parent",
                 "step mother": "Step-parent", "step father": "Step-parent",
                 "foster carer": "Foster carer", "kinship carer": "Kinship carer",
                 "grandparent": "Grandparent", "grandmother": "Grandparent",
                 "grandfather": "Grandparent", "sibling": "Sibling", "brother": "Sibling",
                 "sister": "Sibling", "aunt": "Other relative", "uncle": "Other relative"}
_GENDER = {"f": "Female", "female": "Female", "girl": "Female", "m": "Male",
           "male": "Male", "boy": "Male"}


def _block(handover: HandoverRequest, key: str) -> dict[str, Any]:
    raw = handover.get(key)
    return raw if isinstance(raw, dict) else {}


def _identity(handover: HandoverRequest) -> dict[str, Any]:
    for key in ("child_identity", "student_identity", "learner_identity"):
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


def _child_id(local_student_id: Any) -> int | None:
    """A child's row id from its id or its reference (``LA000012``)."""
    from education_system.systems.local_authority.infrastructure import database as db
    text = str(local_student_id or "").strip()
    if text.isdigit():
        return int(text)
    with db.connect() as conn:
        row = conn.execute("SELECT id FROM learners WHERE child_ref = ? COLLATE NOCASE",
                           (text,)).fetchone()
    return int(row[0]) if row else None


def _child_for(journey_id: str | None, ident: dict[str, Any]) -> int | None:
    from education_system.systems.local_authority.infrastructure import database as db
    upn = str(ident.get("upn") or "").upper().replace(" ", "")
    first = ident.get("first_name") or ident.get("given_name")
    last = ident.get("last_name") or ident.get("family_name")
    dob = str(ident.get("date_of_birth") or ident.get("dob") or "")[:10]
    with db.connect() as conn:
        if journey_id:
            row = conn.execute("SELECT id FROM learners WHERE journey_id = ?",
                               (journey_id,)).fetchone()
            if row:
                return int(row[0])
        if upn:
            row = conn.execute("SELECT id FROM learners WHERE upn = ?", (upn,)).fetchone()
            if row:
                return int(row[0])
        if first and last and dob:
            row = conn.execute(
                "SELECT id FROM learners WHERE first_name = ? COLLATE NOCASE AND "
                "last_name = ? COLLATE NOCASE AND dob = ?", (first, last, dob)).fetchone()
            if row:
                return int(row[0])
    return None


def _guardians(handover: HandoverRequest) -> list[dict[str, Any]]:
    raw = handover.get("guardians") or []
    if isinstance(raw, dict):
        raw = [raw]
    return [g for g in raw if isinstance(g, dict) and (g.get("name") or g.get("full_name"))]


def school_year(year_group: str, destination: str | None) -> str:
    """The authority's "Year 7" / "Reception" as the receiving school counts
    it: the primary's "R" / "1"-"6", the secondary's "7"-"11"."""
    text = str(year_group or "")
    if text == "Reception":
        return "R" if destination == "primary" else text
    if text.startswith("Year ") and text[5:].isdigit():
        return text[5:]
    return text


class LocalAuthorityAdapter(PhaseAdapter):
    """Local Authority Education's side of the four-method transition contract."""

    system = SYSTEM_KEY

    # ── Destination side (a school's notification) ──────────────────

    def create_applicant(self, handover: HandoverRequest) -> ApplicantResult:
        """A school's notification: the child (found or added) and the
        authority's record of what the school told it."""
        from education_system.systems.local_authority.core import records as r
        from education_system.systems.local_authority.infrastructure import database as db
        from education_system.systems.local_authority.modules import children, schools

        if not handover.transition_id:
            raise AdapterError("A notification needs its transition id")
        done = self._already(handover.transition_id)
        if done is not None:
            return ApplicantResult(local_applicant_id=str(done),
                                   notes="notification already recorded")
        ident = _identity(handover)
        if not (ident.get("first_name") and ident.get("last_name")
                and ident.get("date_of_birth")):
            raise AdapterError("The notification needs the pupil's name and date of birth")
        details = _block(handover, "notification_details")
        source = handover.source_system or ""
        if source not in SCHOOL_NAMES:
            raise AdapterError(f"{source!r} doesn't send notifications to the authority")
        actor = f"platform:{source}"
        try:
            school_id = schools.linked_school(source, SCHOOL_NAMES[source])
            child_id = _child_for(handover.journey_id, ident)
            if child_id is None:
                child_id = self._add_child(handover, ident, school_id, actor)
            else:
                self._update_child(child_id, handover, school_id)
            # Linked before the record is made, so its hooks reach the school.
            with db.connect() as conn:
                conn.execute("UPDATE learners SET journey_id = COALESCE(NULLIF(journey_id, ''),"
                             " ?), updated_at = datetime('now') WHERE id = ?",
                             (handover.journey_id, child_id))
            what = self._record(details, child_id, school_id, source,
                                handover.transition_id, actor)
        except r.ValidationError as exc:
            raise AdapterError(f"The local authority couldn't record it: {exc}") from exc
        finally:
            r.take_notices()   # hooks fired by these saves are for a person at a form
        row = r.get(children.CHILDREN, child_id) or {}
        logger.info("LA notification (%s) for journey %s from %s: child %s",
                    details.get("kind"), handover.journey_id, source, child_id)
        return ApplicantResult(local_applicant_id=str(child_id),
                               year_group=children.year_group(r.to_date(row.get("dob"))),
                               notes=f"{what} for {row.get('child_ref')}")

    @staticmethod
    def _already(transition_id: str) -> int | None:
        from education_system.systems.local_authority.infrastructure import database as db
        from education_system.systems.local_authority.modules import (  # noqa: F401
            exclusions, send, welfare,
        )
        with db.connect() as conn:
            for table in ("attendance_cases", "exclusions", "cme", "ehe", "ehc_requests"):
                row = conn.execute(f"SELECT learner_id FROM {table} WHERE "  # nosec B608
                                   "transition_id = ?", (transition_id,)).fetchone()
                if row:
                    return int(row[0])
        return None

    @staticmethod
    def _support(handover: HandoverRequest) -> dict[str, Any]:
        """SEN, FSM and EAL - present only when the parent consented."""
        out: dict[str, Any] = {}
        send = handover.get("send_provision")
        if isinstance(send, dict) and _SEN.get(str(send.get("sen_status") or "").upper()):
            out["sen_status"] = _SEN[str(send["sen_status"]).upper()]
        elif isinstance(send, dict) and send.get("ehcp"):
            out["sen_status"] = "EHC plan"
        ind = handover.get("support_indicators")
        if isinstance(ind, dict):
            if ind.get("fsm"):
                out["free_school_meals"] = 1
            if ind.get("eal"):
                out["eal"] = 1
            if ind.get("lac"):
                out["social_care"] = "Looked after"
        return out

    def _add_child(self, handover: HandoverRequest, ident: dict, school_id: int,
                   actor: str) -> int:
        from education_system.systems.local_authority.core import records as r
        from education_system.systems.local_authority.modules import children
        school = SCHOOL_NAMES.get(handover.source_system or "", "a school")
        values = {
            "first_name": ident["first_name"], "last_name": ident["last_name"],
            "preferred_name": ident.get("preferred_name") or "",
            "dob": str(ident["date_of_birth"])[:10],
            "gender": _GENDER.get(str(ident.get("gender") or "").strip().lower(), ""),
            "upn": ident.get("upn") or "", "education": "At school",
            "school_id": school_id, "address_line1": ident.get("address_line1") or "",
            "town": ident.get("town") or "", "postcode": ident.get("postcode") or "",
            "status": "Resident",
            "notes": f"Added from a notification by {school} through the platform.",
            **self._support(handover),
        }
        try:
            child_id = r.save(children.CHILDREN, values, actor=actor)
        except r.ValidationError as first:
            # A detail the authority's checks refuse (an odd UPN or postcode)
            # mustn't stop the notification: keep what passes, and say so.
            for key in ("upn", "postcode", "preferred_name"):
                values[key] = ""
            values["notes"] += f"\nSome details from {school} weren't kept: {first}"
            child_id = r.save(children.CHILDREN, values, actor=actor)
        self._add_contacts(child_id, handover, actor)
        return child_id

    def _update_child(self, child_id: int, handover: HandoverRequest, school_id: int) -> None:
        """A known child: the school they're notified from is on record, and
        what the parent consented to share is kept up to date."""
        from education_system.systems.local_authority.core import records as r
        from education_system.systems.local_authority.modules import children
        row = r.get(children.CHILDREN, child_id) or {}
        values = {}
        if row.get("education") in ("At school", "Not in education", "Not yet school age",
                                    "Early years setting") \
                and row.get("school_id") != school_id:
            values.update({"education": "At school", "school_id": school_id})
        for key, value in self._support(handover).items():
            if row.get(key) != value and not (key == "sen_status"
                                              and row.get("sen_status") == "EHC plan"):
                values[key] = value
        if values:
            try:
                r.save(children.CHILDREN, values, record_id=child_id,
                       actor=f"platform:{handover.source_system}")
            except r.ValidationError as exc:
                logger.warning("LA child %s not updated from the school: %s", child_id, exc)
        if not r.list_records(children.CONTACTS, learner_id=child_id):
            self._add_contacts(child_id, handover, f"platform:{handover.source_system}")

    @staticmethod
    def _add_contacts(child_id: int, handover: HandoverRequest, actor: str) -> None:
        from education_system.systems.local_authority.core import records as r
        from education_system.systems.local_authority.modules import children
        main = False
        for g in _guardians(handover):
            rel = str(g.get("relationship") or "").strip().lower()
            values = {"learner_id": child_id, "name": g.get("name") or g.get("full_name"),
                      "relationship": _RELATIONSHIP.get(rel, "Other"),
                      "parental_responsibility": 1 if g.get("parental_responsibility",
                                                            True) else 0,
                      "phone": g.get("phone") or "", "email": g.get("email") or "",
                      "notes": "From the school, through the platform."}
            if not main and values["parental_responsibility"] and \
                    (values["phone"] or values["email"]):
                values["is_primary"] = 1
            try:
                r.save(children.CONTACTS, values, actor=actor)
                main = main or bool(values.get("is_primary"))
            except r.ValidationError as exc:
                for key in ("phone", "email"):
                    values[key] = ""
                values["is_primary"] = 0
                values["notes"] += f" Not kept: {exc}"
                try:
                    r.save(children.CONTACTS, values, actor=actor)
                except r.ValidationError:
                    logger.warning("Contact for LA child %s not added: %s", child_id, exc)

    @staticmethod
    def _record(details: dict, child_id: int, school_id: int, source: str,
                transition_id: str, actor: str) -> str:
        """Record the notification where it belongs. Returns what was made."""
        from education_system.systems.local_authority.core import records as r
        from education_system.systems.local_authority.modules import exclusions, send, welfare
        kind = details.get("kind")
        on = str(details.get("notified_on") or date.today().isoformat())[:10]
        who = details.get("referrer") or SCHOOL_NAMES[source]
        link = {"source_system": source, "transition_id": transition_id}
        if kind == ATTENDANCE:
            text = (f"Referred by {who} on {on}: attendance {details.get('attendance_pct')}%"
                    + (f", {details['sessions_missed']} unauthorised sessions"
                       if details.get("sessions_missed") not in (None, "") else "")
                    + f". Support the school has tried: {details.get('support_tried')}")
            open_case = r.list_records(welfare.ATTENDANCE_CASES, learner_id=child_id,
                                       equals={"status": "Open"})
            if open_case:   # one open case per child: the referral joins it
                case = open_case[0]
                r.save(welfare.ATTENDANCE_CASES, {
                    "attendance_pct": details.get("attendance_pct"),
                    "school_id": case.get("school_id") or school_id,
                    "barriers": "\n".join(x for x in (case.get("barriers"), text) if x),
                    **link}, record_id=case["id"], actor=actor)
                return "added to the open attendance case"
            r.save(welfare.ATTENDANCE_CASES, {
                "learner_id": child_id, "school_id": school_id, "referred_on": on,
                "attendance_pct": details.get("attendance_pct"), "barriers": text,
                "status": "Open", **link}, actor=actor)
            return "attendance case opened"
        if kind in (SUSPENSION, PERMANENT):
            r.save(exclusions.EXCLUSIONS, {
                "learner_id": child_id, "school_id": school_id, "kind": kind,
                "start_date": details.get("start_date"),
                "days": details.get("days") if kind == SUSPENSION else None,
                "reason": details.get("reason"), "notified_on": on,
                "outcome": "Awaiting review" if kind == PERMANENT else None,
                "notes": "\n".join(x for x in (f"Notified by {who} through the platform.",
                                               details.get("background") or "") if x),
                **link}, actor=actor)
            return f"{kind.lower()} recorded"
        if kind == CME:
            r.save(welfare.CME, {
                "learner_id": child_id, "reported_on": on,
                "source": _CME_SOURCE.get(details.get("reason"), "Other"),
                "last_school_id": school_id,
                "enquiries": (f"{details.get('reason')}"
                              + (f"; last seen {details['last_seen']}"
                                 if details.get("last_seen") else "")
                              + f". School's enquiries ({who}): {details.get('enquiries')}"),
                "status": "Open", **link}, actor=actor)
            return "missing education case opened"
        if kind == EHE:
            r.save(welfare.EHE, {
                "learner_id": child_id, "notified_on": details.get("notice_date") or on,
                "from_school_id": school_id, "status": "Active",
                "notes": "\n".join(x for x in (
                    f"Notified by {who} through the platform.",
                    details.get("background") or "") if x), **link}, actor=actor)
            return "home education recorded"
        if kind == EHCNA:
            r.save(send.EHC_REQUESTS, {
                "learner_id": child_id, "received_on": on, "requested_by": "School / college",
                "setting_id": school_id,
                "notes": "\n".join(x for x in (
                    f"Requested by {who} through the platform: {details.get('summary')}",
                    f"Tried: {details['tried']}" if details.get("tried") else "") if x),
                **link}, actor=actor)
            return "EHC needs assessment request recorded"
        raise AdapterError(f"The authority doesn't take {kind!r} notifications")

    def create_enrolment(self, journey_id: str, application_id: str | None = None,
                         **details: Any) -> EnrolmentResult:
        """The child is on the authority's books."""
        from education_system.systems.local_authority.core import records as r
        from education_system.systems.local_authority.modules import children
        child_id = _child_for(journey_id, {}) or _child_id(application_id)
        row = r.get(children.CHILDREN, child_id) if child_id else None
        if row is None:
            raise AdapterError(f"No local authority child for journey {journey_id}; "
                               "the notification must arrive first")
        return EnrolmentResult(local_student_id=str(row["id"]),
                               start_date=details.get("start_date"),
                               notes=f"child {row.get('child_ref')}")

    # ── Source side (a school place) ─────────────────────────────────

    def export_handover(self, local_student_id: str,
                        consent: bool | set[str] | None = None, *,
                        destination_system: str | None = None) -> ExportResult:
        """The child as the authority holds them. Consent is applied by
        ``handover.build_handover`` (SEN is sensitive)."""
        from education_system.systems.local_authority.core import records as r
        from education_system.systems.local_authority.modules import children, schools, send

        cid = _child_id(local_student_id)
        row = r.get(children.CHILDREN, cid) if cid else None
        if row is None:
            raise AdapterError(f"No local authority child {local_student_id}")
        cid = row["id"]
        dob = r.to_date(row.get("dob"))
        guardians = [
            {"name": c["name"], "relationship": c["relationship"],
             "phone": c.get("phone") or None, "email": c.get("email") or None,
             "parental_responsibility": bool(c.get("parental_responsibility"))}
            for c in r.list_records(children.CONTACTS, learner_id=cid)
            if not c.get("no_contact") and c.get("relationship") != "Social worker"]
        plan = next((p for p in r.list_records(send.EHC_PLANS, learner_id=cid)
                     if p.get("status") == "Active"), None)
        sen = {"EHC plan": "E", "SEN Support": "K"}.get(row.get("sen_status") or "")
        record: dict[str, Any] = {
            "child_identity": {
                "first_name": row["first_name"], "last_name": row["last_name"],
                "preferred_name": row.get("preferred_name") or None,
                "date_of_birth": row.get("dob"), "gender": row.get("gender") or None,
                "upn": row.get("upn") or None,
                "year_group": school_year(children.year_group(dob), destination_system),
                "address_line1": row.get("address_line1") or None,
                "town": row.get("town") or None, "postcode": row.get("postcode") or None,
                "local_authority_ref": row.get("child_ref"),
                "school_name": schools.school_name(row.get("school_id")) or None},
            "guardians": guardians or None,
            "send_provision": ({"sen_status": sen, "ehcp": bool(plan),
                                "primary_need": (plan or {}).get("primary_need"),
                                "ehcp_issued_on": (plan or {}).get("issued_on")}
                               if sen else None),
        }
        return ExportResult(record={k: v for k, v in record.items() if v is not None},
                            local_student_id=str(cid))

    def close_enrolment(self, local_student_id: str, reason: str,
                        **details: Any) -> None:
        """The authority's record of a child isn't closed by a school: a note."""
        from education_system.systems.local_authority.infrastructure import database as db
        cid = _child_id(local_student_id)
        if cid is None:
            logger.warning("close_enrolment: no local authority child %s", local_student_id)
            return
        with db.connect() as conn:
            conn.execute("INSERT INTO history (actor, record_type, record_id, learner_id, "
                         "action, summary) VALUES ('platform', 'learners', ?, ?, 'updated', "
                         "?)", (cid, cid, f"Platform: {reason[:200]}"))


ADAPTER = LocalAuthorityAdapter()


def register() -> LocalAuthorityAdapter:
    """Register this adapter with the platform. Idempotent."""
    registry.register(ADAPTER, replace=True)
    return ADAPTER


__all__ = ["SYSTEM_KEY", "LocalAuthorityAdapter", "ADAPTER", "school_year", "register"]
