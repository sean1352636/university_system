"""Sixth-form-side consumer for secondary progression events.

Subscribes to ``student.progression.completed`` on the durable
cross-system bus and admits the pupil into the sixth form (the
``college`` slot).

Before a student is created the pupil is matched against admissions —
UPN first, then name + date of birth:

* **an open application** (anything from Submitted to Offer Accepted or
  Deferred) — the transferred data is attached to it instead: UPN / ULN
  filled where blank, sex, the parent/carer as a contact, and a
  timeline note listing what arrived (subject choices, journey id). No
  student is created; staff convert the applicant as usual and the
  conversion links the platform journey (:func:`pending_journey`).
* **an applicant already converted** — that student is used, so the
  journey links to the existing record and no duplicate is made.
* **no match** (or only closed applications) — today's behaviour: a
  ``students`` row linked to the canonical ``journey_id``. The in-process
  ``sixthform_transfer`` flow forwards real subject choices on the
  payload; the distinct, valid ones are kept. With no choices the
  student is created with **no** subjects — nothing is invented — and an
  onboarding checklist is opened with a "choose subjects" task.

Every event is written to ``admissions_intake_log`` with what was done
(:func:`list_intake_log`). The consumer runs with nobody signed in, so
its work runs as ``system:college-intake`` with the ``admissions`` and
``students.manage`` capabilities.

Idempotent: re-delivery is dropped by the bus, and a journey whose
``college`` slot is already filled is skipped.

Drained by :func:`drain_intake`, called on sixth-form startup.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from education_system.platform.cross_system import progression

logger = logging.getLogger(__name__)

CONSUMER_SYSTEM = "sixth_form"

#: Applicant statuses an intake attaches to (the application is live).
ATTACHABLE_STATUSES: tuple[str, ...] = (
    "Online - unverified", "Submitted", "Under Review", "Interview Scheduled",
    "Interviewed", "Offer Made", "Offer Accepted", "Waitlisted", "Deferred",
)

_LOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS admissions_intake_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    at             TEXT NOT NULL DEFAULT (datetime('now')),
    journey_id     TEXT NOT NULL,
    action         TEXT NOT NULL,
    applicant_id   TEXT,
    student_id     TEXT,
    matched_on     TEXT,
    detail         TEXT,
    payload_json   TEXT,
    linked_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_adm_intake_journey
    ON admissions_intake_log(journey_id);
CREATE INDEX IF NOT EXISTS idx_adm_intake_aid
    ON admissions_intake_log(applicant_id);
"""

#: Payload keys kept out of the log copy (contact details live in the
#: applicant/student record they were written to).
_PRIVATE_KEYS = ("phone", "parent_phone", "parent_email", "email")


@dataclass
class IntakeEntry:
    id: int
    at: str
    journey_id: str
    action: str          # created / attached / existing student / failed
    applicant_id: str | None
    student_id: str | None
    matched_on: str | None
    detail: str | None
    linked_at: str | None


def _adm():
    from education_system.systems.sixth_form.domain.admissions import (
        admissions,
    )
    return admissions


def _guard():
    from education_system.systems.sixth_form.domain.admissions import _guard
    return _guard


_READY = False


def _init_log() -> None:
    global _READY
    if _READY:
        return
    adm = _adm()
    adm.init_db()
    with adm._connect() as conn:
        conn.executescript(_LOG_SCHEMA)
        conn.commit()
    _READY = True


def _log(journey_id: str, action: str, *, applicant_id: str | None = None,
         student_id: str | None = None, matched_on: str | None = None,
         detail: str | None = None, payload: dict | None = None) -> None:
    _init_log()
    safe = {k: v for k, v in (payload or {}).items()
            if k not in _PRIVATE_KEYS}
    with _adm()._connect() as conn:
        conn.execute(
            "INSERT INTO admissions_intake_log (journey_id, action, "
            "applicant_id, student_id, matched_on, detail, payload_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (journey_id, action, applicant_id, student_id, matched_on,
             detail, json.dumps(safe, default=str)))
        conn.commit()


def list_intake_log(*, limit: int = 200) -> list[IntakeEntry]:
    """What the intake did with each progression event, newest first."""
    _init_log()
    _guard().require("the secondary intake log")
    with _adm()._connect() as conn:
        rows = conn.execute(
            "SELECT * FROM admissions_intake_log ORDER BY id DESC LIMIT ?",
            (int(limit),)).fetchall()
    return [IntakeEntry(id=r["id"], at=r["at"], journey_id=r["journey_id"],
                        action=r["action"], applicant_id=r["applicant_id"],
                        student_id=r["student_id"],
                        matched_on=r["matched_on"], detail=r["detail"],
                        linked_at=r["linked_at"]) for r in rows]


def pending_journey(applicant_id: str) -> str | None:
    """The platform journey an intake attached to this applicant and not
    yet linked to a student (conversion links it)."""
    _init_log()
    with _adm()._connect() as conn:
        r = conn.execute(
            "SELECT journey_id FROM admissions_intake_log WHERE "
            "applicant_id = ? AND action = 'attached' AND linked_at IS NULL "
            "ORDER BY id DESC LIMIT 1", (applicant_id,)).fetchone()
    return r["journey_id"] if r else None


def link_pending_journey(applicant_id: str, student_id: str) -> str | None:
    """Link the attached journey (if any) to the converted student in the
    platform identity registry. Returns the journey id linked."""
    journey_id = pending_journey(applicant_id)
    if not journey_id:
        return None
    from education_system.platform.cross_system import identity_service
    identity_service.link_system(journey_id, CONSUMER_SYSTEM,
                                 student_id=student_id, set_current=True)
    identity_service.record_transition_once(
        journey_id, from_system=_intake.from_system,
        to_system=CONSUMER_SYSTEM,
        reason="secondary progression intake (converted from admissions)")
    with _adm()._connect() as conn:
        conn.execute(
            "UPDATE admissions_intake_log SET linked_at = datetime('now'), "
            "student_id = ? WHERE applicant_id = ? AND journey_id = ? AND "
            "linked_at IS NULL", (student_id, applicant_id, journey_id))
        conn.commit()
    return journey_id


def _valid_choices(payload: dict) -> list[str]:
    """The distinct subject choices on the payload that the subject
    catalogue knows, in order (possibly none)."""
    chosen: list[str] = []
    for key in ("subject_1", "subject_2", "subject_3"):
        s = (payload.get(key) or "").strip()
        if s and s not in chosen:
            chosen.append(s)
    try:
        from education_system.systems.sixth_form.domain.academics.subjects import (
            subjects as _subjects,
        )
        valid = [s for s in chosen if _subjects.is_valid_subject(s)]
    except ImportError:
        valid = chosen
    dropped = [s for s in chosen if s not in valid]
    if dropped:
        logger.warning("College intake: subject choice(s) %s not in the "
                       "catalogue — left for staff to choose", dropped)
    return valid


def _names(journey_id: str, payload: dict) -> tuple[str, str, str]:
    from education_system.platform.cross_system import person
    p = person.get(journey_id)
    first = payload.get("first_name") or (p.legal_first_name if p else "")
    last = payload.get("last_name") or (p.legal_last_name if p else "")
    dob = payload.get("date_of_birth") or (p.date_of_birth if p else "")
    return first or "", last or "", dob or ""


def _match_applicant(payload: dict, first: str, last: str, dob: str
                     ) -> tuple[Any, str | None]:
    """(applicant, how) — UPN first, then name + DOB. Prefers a converted
    applicant, then a live one; closed applications never match."""
    adm = _adm()
    upn = (payload.get("upn") or "").strip().upper()
    candidates: list[tuple[Any, str]] = []
    if upn:
        for a in adm.list_applicants():
            if (a.upn or "").upper() == upn:
                candidates.append((a, "UPN"))
    if not candidates and first and last and dob:
        candidates = [(a, "name + DOB") for a in adm.find_duplicates(
            first_name=first, last_name=last, dob=dob) if not a.is_archived]
    for a, how in candidates:
        if a.converted_student_id:
            return a, how
    for a, how in candidates:
        if a.status in ATTACHABLE_STATUSES:
            return a, how
    return None, None


def _attach(journey_id: str, a: Any, payload: dict, how: str) -> list[str]:
    """Write the transferred data onto the applicant; return what was
    done."""
    from education_system.systems.sixth_form.domain.admissions import (
        applicant_details as _details,
    )
    adm = _adm()
    done: list[str] = []
    extra: dict[str, str] = {}
    upn = (payload.get("upn") or "").strip().upper()
    uln = (payload.get("uln") or "").strip()
    if upn and not a.upn:
        extra["upn"] = upn
    if uln and not a.uln:
        extra["uln"] = uln
    if extra:
        adm._set_extra(a.applicant_id, event="Identifiers from the secondary "
                       "progression intake", **extra)
        done.append("set " + ", ".join(k.upper() for k in extra))
    sex = (payload.get("gender") or "").strip().lower()
    if sex in _details.SEXES and not a.sex:
        try:
            _details.update_profile(a.applicant_id, sex=sex)
            done.append("set sex")
        except adm.ValidationError as e:
            done.append(f"sex not set ({e})")
    pname = (payload.get("parent_name") or "").strip()
    pphone = (payload.get("parent_phone") or "").strip()
    pemail = (payload.get("parent_email") or "").strip()
    if pname and (pphone or pemail):
        have = {c.name.lower() for c in _details.list_contacts(a.applicant_id)}
        if pname.lower() not in have:
            try:
                _details.add_contact(a.applicant_id, {
                    "name": pname, "relationship": "Parent",
                    "phone": pphone or None, "email": pemail or None,
                    "is_emergency": True, "parental_responsibility": True})
                done.append("added parent/carer contact")
            except adm.ValidationError as e:
                done.append(f"parent/carer contact not added ({e})")
    choices = _valid_choices(payload)
    lines = [f"Secondary progression intake (journey {journey_id}, matched "
             f"on {how}): the pupil's record arrived from the secondary "
             "school."]
    if choices:
        lines.append("Subject choices on the transfer: " + ", ".join(choices))
    others = sorted(k for k, v in payload.items() if v not in (None, "")
                    and k not in _PRIVATE_KEYS and k not in (
                        "first_name", "last_name", "date_of_birth", "upn",
                        "uln", "gender", "parent_name", "subject_1",
                        "subject_2", "subject_3"))
    if others:
        lines.append("Other transfer data: " + ", ".join(
            f"{k}={payload[k]}" for k in others))
    lines.append("No student record was created — convert the applicant "
                 "to enrol them.")
    adm.add_note(a.applicant_id, "\n".join(lines),
                 author="system:college-intake")
    done.append("timeline note")
    return done


def _create_student(journey_id: str, payload: dict, first: str, last: str,
                    dob: str) -> str:
    from education_system.systems.sixth_form.domain.learners.students import (
        students,
    )
    chosen = (_valid_choices(payload) + ["", "", ""])[:3]
    student = students.create_student(allow_duplicate=True, data={
        "first_name": first,
        "last_name": last,
        "middle_name": payload.get("middle_name") or "",
        "title": payload.get("title") or "",
        "gender": payload.get("gender") or "",
        "date_of_birth": dob,
        "phone": payload.get("phone") or "",
        "emergency_contact_name": payload.get("parent_name") or "",
        "emergency_contact_phone": payload.get("parent_phone") or "",
        "emergency_contact_relation": "Parent/Carer"
        if (payload.get("parent_name") or payload.get("parent_phone")) else "",
        "subject_1": chosen[0],
        "subject_2": chosen[1],
        "subject_3": chosen[2],
        "status": "Active",
    })
    _open_onboarding(student.student_id, has_subjects=any(chosen))
    return student.student_id


def _admit(journey_id: str, payload: dict) -> str | None:
    """Admit a pupil from a progression payload (see the module doc).
    Returns the sixth-form student id to link, or None when the pupil
    was attached to an open application instead."""
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    with _guard().system_actor("college-intake", capabilities=(
            access.ADMISSIONS, access.STUDENTS_MANAGE)):
        first, last, dob = _names(journey_id, payload)
        try:
            a, how = _match_applicant(payload, first, last, dob)
        except Exception:  # noqa: BLE001 — matching must not lose the pupil
            logger.exception("College intake: applicant match failed for %s",
                             journey_id)
            a, how = None, None
        if a is not None and a.converted_student_id:
            _log(journey_id, "existing student", applicant_id=a.applicant_id,
                 student_id=a.converted_student_id, matched_on=how,
                 detail=f"Applicant {a.applicant_id} was already converted; "
                        "journey linked to that student",
                 payload=payload)
            return a.converted_student_id
        if a is not None:
            try:
                done = _attach(journey_id, a, payload, how or "")
                _log(journey_id, "attached", applicant_id=a.applicant_id,
                     matched_on=how, detail="; ".join(done), payload=payload)
                logger.info("College intake: journey %s attached to open "
                            "applicant %s (%s)", journey_id, a.applicant_id,
                            how)
                return None
            except Exception as e:  # noqa: BLE001 — fall back to a student
                logger.exception("College intake: attaching %s to %s failed",
                                 journey_id, a.applicant_id)
                _log(journey_id, "failed", applicant_id=a.applicant_id,
                     matched_on=how, detail=f"Attach failed ({e}); a "
                     "student record was created instead", payload=payload)
        sid = _create_student(journey_id, payload, first, last, dob)
        _log(journey_id, "created", student_id=sid,
             detail="No open application matched; student created",
             payload=payload)
        return sid


def _open_onboarding(student_id: str, *, has_subjects: bool) -> None:
    """Open the onboarding checklist from the template chosen for the
    learner (workflow.choose_template); ask for subjects when none came."""
    try:
        from education_system.systems.sixth_form.domain.admissions.onboarding import (
            onboarding, workflow,
        )
        extra = [] if has_subjects else [
            (onboarding.CHOOSE_SUBJECTS_TASK, "Academic", True)]
        opened = workflow.open_for_learner(
            student_id, extra_tasks=extra,
            notes="Opened by the secondary progression intake")
        for problem in opened.problems:
            logger.warning("College intake: onboarding for %s: %s",
                           student_id, problem)
    except Exception:
        # The student exists; a missing checklist is visible on the
        # onboarding screen and must not undo the admission.
        logger.exception("College intake: onboarding checklist not opened "
                         "for %s", student_id)


_intake = progression.ProgressionIntake(
    CONSUMER_SYSTEM, _admit,
    handler_name="college.students.college_intake",
    from_system="secondary")


def register_intake_consumer() -> None:
    """Idempotently subscribe the intake handler to the bus."""
    _intake.register()


def drain_intake(*, db_path: str | None = None) -> int:
    """Process any pending secondary progression events. Returns the
    number of (event, handler) dispatches. Safe to call repeatedly."""
    return _intake.drain(db_path=db_path)
