"""Training Provider's side of the platform transition contract.

Four links on the platform run through this adapter (nothing here imports
another system):

* **Apprenticeships / FE College → Training Provider**
  (``platform.cross_system.training_provider_requests``): ``create_applicant``
  finds the learner (journey, ULN, e-mail, or name and date of birth) or
  adds them, sets up who pays as a client (the sender, or the employer),
  and records the request on *Training Requests*. Idempotent on the
  transition.
* **Training Provider → Apprenticeships** (``apprenticeship_applications``)
  and **→ FE College** (``fe_applications``): ``export_handover`` is what
  this provider holds - identity, contact, employer, the certificates
  achieved here and (only with consent, filtered by
  ``handover.build_handover``) support needs.
* ``close_enrolment`` - a short-course record isn't a programme: leaving
  only adds a note. Never deletes, never archives.
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

SYSTEM_KEY = "training_provider"
SOURCE_NAMES = {"apprenticeships": "Apprenticeships", "fe_college": "FE College"}
#: The client kind a sender is set up as, when it pays.
_SENDER_KINDS = {"fe_college": "School / college", "apprenticeships": "Other"}


def _block(handover: HandoverRequest, key: str) -> dict[str, Any]:
    raw = handover.get(key)
    return raw if isinstance(raw, dict) else {}


def _identity(handover: HandoverRequest) -> dict[str, Any]:
    raw: dict[str, Any] = {}
    for key in ("learner_identity", "student_identity", "child_identity"):
        if isinstance(handover.get(key), dict) and handover.get(key):
            raw = handover.get(key)
            break
    return {"first_name": raw.get("first_name") or raw.get("given_name") or "",
            "last_name": raw.get("last_name") or raw.get("family_name") or "",
            "dob": str(raw.get("date_of_birth") or raw.get("dob") or "")[:10],
            "uln": str(raw.get("uln") or "").replace(" ", "")}


def _text(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, dict):
        return "; ".join(f"{k.replace('_', ' ')}: {_text(v)}" for k, v in value.items()
                         if v not in (None, "", [], {}))
    if isinstance(value, (list, tuple)):
        return "; ".join(_text(v) for v in value if v not in (None, "", [], {}))
    return str(value).strip()


def _learner_id(local_student_id: Any) -> int | None:
    """A learner's row id from its id or its reference (``TP000012``)."""
    from education_system.systems.training_provider.infrastructure import database as db
    text = str(local_student_id or "").strip()
    if text.isdigit():
        return int(text)
    with db.connect() as conn:
        row = conn.execute("SELECT id FROM learners WHERE learner_ref = ? COLLATE NOCASE",
                           (text,)).fetchone()
    return int(row[0]) if row else None


def _learner_for(journey_id: str | None, ident: dict[str, Any],
                 contact: dict[str, Any]) -> int | None:
    from education_system.systems.training_provider.infrastructure import database as db
    with db.connect() as conn:
        if journey_id:
            row = conn.execute("SELECT id FROM learners WHERE journey_id = ?",
                               (journey_id,)).fetchone()
            if row:
                return int(row[0])
        if ident.get("uln"):
            row = conn.execute("SELECT id FROM learners WHERE uln = ?",
                               (ident["uln"],)).fetchone()
            if row:
                return int(row[0])
        email = str(contact.get("email") or "").strip().lower()
        if email:
            row = conn.execute("SELECT id FROM learners WHERE email = ?", (email,)).fetchone()
            if row:
                return int(row[0])
        if ident.get("dob"):
            row = conn.execute(
                "SELECT id FROM learners WHERE first_name = ? COLLATE NOCASE AND "
                "last_name = ? COLLATE NOCASE AND dob = ?",
                (ident["first_name"], ident["last_name"], ident["dob"])).fetchone()
            if row:
                return int(row[0])
    return None


def _client(name: str, kind: str, actor: str) -> int | None:
    """The client called *name*, set up if it's new."""
    from education_system.systems.training_provider.core import records as r
    from education_system.systems.training_provider.infrastructure import database as db
    from education_system.systems.training_provider.modules import clients
    name = (name or "").strip()[:120]
    if not name:
        return None
    with db.connect() as conn:
        row = conn.execute("SELECT id FROM clients WHERE name = ? COLLATE NOCASE",
                           (name,)).fetchone()
    if row:
        return int(row[0])
    try:
        return r.save(clients.CLIENTS, {"name": name, "kind": kind,
                                        "notes": "Set up from a training request through "
                                                 "the platform."}, actor=actor)
    except r.ValidationError as exc:
        logger.warning("Client %r not set up: %s", name, exc)
        return None


class TrainingProviderAdapter(PhaseAdapter):
    """Training Provider's side of the four-method transition contract."""

    system = SYSTEM_KEY

    # ── Destination side (Apprenticeships / FE College → here) ───────

    def create_applicant(self, handover: HandoverRequest) -> ApplicantResult:
        """A training request: the learner (found or added), who pays, and
        the request on *Training Requests*."""
        from education_system.systems.training_provider.core import records as r
        from education_system.systems.training_provider.infrastructure import database as db
        from education_system.systems.training_provider.modules import learners, requests

        if not handover.transition_id:
            raise AdapterError("A training request needs its transition id")
        done = requests.for_transition(handover.transition_id)
        if done is not None:
            return ApplicantResult(local_applicant_id=str(done["learner_id"]),
                                   notes="request already recorded")
        ident = _identity(handover)
        if not (ident["first_name"] and ident["last_name"] and ident["dob"]):
            raise AdapterError("The request needs the learner's name and date of birth")
        contact = _block(handover, "contact_details")
        details = _block(handover, "referral_details")
        source = handover.source_system or ""
        sender = SOURCE_NAMES.get(source, source or "Linked sender")
        actor = f"platform:{source}"
        payer = details.get("payer") if details.get("payer") in requests.PAYERS \
            else requests.PAYERS[0]
        employer = _text(handover.get("employer_reference") or handover.get("employer"))
        try:
            bill_to = None
            if payer == requests.PAYERS[0]:
                bill_to = _client(sender, _SENDER_KINDS.get(source, "Other"), actor)
            elif payer == requests.PAYERS[1] and employer:
                bill_to = _client(employer, "Private company", actor)
            learner_id = _learner_for(handover.journey_id, ident, contact)
            if learner_id is None:
                learner_id = self._add_learner(handover, ident, contact, payer, bill_to,
                                               sender, actor)
            with db.connect() as conn:
                conn.execute(
                    "UPDATE learners SET journey_id = COALESCE(NULLIF(journey_id, ''), ?), "
                    "updated_at = datetime('now') WHERE id = ?",
                    (handover.journey_id, learner_id))
            r.save(requests.TRAINING_REQUESTS, {
                "learner_id": learner_id,
                "received": str(details.get("request_date") or date.today().isoformat())[:10],
                "sender": sender,
                "course": str(details.get("course") or "Not stated")[:200],
                "reason": details.get("reason") or "",
                "needed_by": details.get("needed_by") or None,
                "payer": payer, "bill_to": bill_to,
                "po_number": str(details.get("po_number") or "")[:60],
                "referrer": details.get("referrer") or "",
                "status": "New", "source_system": source,
                "transition_id": handover.transition_id,
                "consent_to_share": 1 if details.get("consent") else 0,
                "safeguarding_ref": str(handover.get("safeguarding_reference") or "")[:120],
            }, actor=actor)
        except r.ValidationError as exc:
            raise AdapterError(f"The training provider couldn't record the request: "
                               f"{exc}") from exc
        finally:
            # Hooks fired by these saves are for a person at a form.
            r.take_notices()
        row = r.get(learners.LEARNERS, learner_id) or {}
        logger.info("Training request for journey %s from %s: learner %s",
                    handover.journey_id, source, learner_id)
        return ApplicantResult(local_applicant_id=str(learner_id),
                               notes=f"request recorded for {row.get('learner_ref')}")

    @staticmethod
    def _add_learner(handover: HandoverRequest, ident: dict, contact: dict, payer: str,
                     bill_to: int | None, sender: str, actor: str) -> int:
        from education_system.systems.training_provider.core import records as r
        from education_system.systems.training_provider.modules import learners, requests
        support = "\n".join(t for t in (
            _text(handover.get(k)) for k in ("support_referral", "send_support",
                                             "support_plan", "reasonable_adjustments")) if t)
        employer_pays = payer == requests.PAYERS[1] and bill_to
        values = {
            "first_name": ident["first_name"], "last_name": ident["last_name"],
            "dob": ident["dob"], "email": contact.get("email") or "",
            "phone": contact.get("phone") or "",
            "address_line1": contact.get("address") or "",
            "postcode": contact.get("postcode") or "", "uln": ident["uln"],
            "funding": ("Employer" if employer_pays else
                        "Funded (grant / skills fund)" if payer == requests.PAYERS[3]
                        else "Self-funded"),
            "client_id": bill_to if employer_pays else None,
            "support_needs": support, "status": "Active",
            "notes": f"Sent by {sender} through the platform ({payer.lower()}).",
        }
        try:
            return r.save(learners.LEARNERS, values, actor=actor)
        except r.ValidationError as first:
            # A detail this provider's checks refuse shouldn't strand the
            # request: keep the learner with what passes, and say so.
            for key in ("uln", "postcode", "phone", "email", "address_line1"):
                values[key] = ""
            values["notes"] += f"\nSome details from {sender} weren't kept: {first}"
            return r.save(learners.LEARNERS, values, actor=actor)

    def create_enrolment(self, journey_id: str, application_id: str | None = None,
                         **details: Any) -> EnrolmentResult:
        """The learner is on this provider's books (their sessions are
        booked on the Bookings page)."""
        from education_system.systems.training_provider.core import records as r
        from education_system.systems.training_provider.modules import learners

        learner_id = _learner_for(journey_id, {}, {}) or _learner_id(application_id)
        row = r.get(learners.LEARNERS, learner_id) if learner_id else None
        if row is None:
            raise AdapterError(f"No training provider learner for journey {journey_id}; "
                               "the request must arrive first")
        return EnrolmentResult(local_student_id=str(row["id"]),
                               start_date=details.get("start_date"),
                               notes=f"learner {row.get('learner_ref')}")

    # ── Source side (→ Apprenticeships, → FE College) ────────────────

    def export_handover(self, local_student_id: str,
                        consent: bool | set[str] | None = None, *,
                        destination_system: str | None = None) -> ExportResult:
        """What this provider holds about the learner. Consent is applied by
        ``handover.build_handover`` (support is sensitive)."""
        from education_system.systems.training_provider.core import records as r
        from education_system.systems.training_provider.infrastructure import database as db
        from education_system.systems.training_provider.modules import clients, learners

        lid = _learner_id(local_student_id)
        row = r.get(learners.LEARNERS, lid) if lid else None
        if row is None:
            raise AdapterError(f"No training provider learner {local_student_id}")
        lid = row["id"]
        with db.connect() as conn:
            certs = [dict(x) for x in conn.execute(
                "SELECT c.title AS course, c.level, c.kind, c.awarding_body, "
                "c.guided_hours, k.cert_no, k.issued_on, k.expires_on "
                "FROM certificates k JOIN sessions s ON s.id = k.session_id "
                "JOIN courses c ON c.id = s.course_id "
                "WHERE k.learner_id = ? AND k.status = 'Issued' ORDER BY k.issued_on",
                (lid,)).fetchall()]
        employer = r.get(clients.CLIENTS, row["client_id"]) if row.get("client_id") else None
        address = ", ".join(x for x in (row.get("address_line1"), row.get("town")) if x)
        contact = {k: v for k, v in (("email", row.get("email")), ("phone", row.get("phone")),
                                     ("address", address), ("postcode", row.get("postcode")))
                   if v}
        record: dict[str, Any] = {
            "learner_identity": {
                "first_name": row["first_name"], "last_name": row["last_name"],
                "date_of_birth": row.get("dob"), "uln": row.get("uln") or None,
                "learner_ref": row.get("learner_ref"),
                "training_provider_learner_id": str(lid)},
            "contact_details": contact or None,
            "achieved_qualifications": [
                {"course": c["course"], "level": c["level"], "type": c["kind"],
                 "awarding_body": c["awarding_body"], "certificate": c["cert_no"],
                 "issued_on": c["issued_on"], "expires_on": c["expires_on"]}
                for c in certs] or None,
            "employment": ({"employer": employer["name"], "job_title": row.get("job_title")}
                           if employer else None),
            "employer_details": ({"name": employer["name"], "job_title": row.get("job_title")}
                                 if employer else None),
            "support_referral": row.get("support_needs") or None,
        }
        return ExportResult(record={k: v for k, v in record.items() if v is not None},
                            local_student_id=str(lid))

    def close_enrolment(self, local_student_id: str, reason: str,
                        **details: Any) -> None:
        """A short-course record isn't a programme to leave: the learner
        stays (certificates expire and are renewed), with a note."""
        from education_system.systems.training_provider.infrastructure import database as db
        lid = _learner_id(local_student_id)
        if lid is None:
            logger.warning("close_enrolment: no training provider learner %s",
                           local_student_id)
            return
        with db.connect() as conn:
            conn.execute("INSERT INTO history (actor, record_type, record_id, learner_id, "
                         "action, summary) VALUES ('platform', 'learners', ?, ?, 'updated', "
                         "?)", (lid, lid, f"Moved on: {reason[:200]}"))


ADAPTER = TrainingProviderAdapter()


def register() -> TrainingProviderAdapter:
    """Register this adapter with the platform. Idempotent."""
    registry.register(ADAPTER, replace=True)
    return ADAPTER


__all__ = ["SYSTEM_KEY", "TrainingProviderAdapter", "ADAPTER", "register"]
