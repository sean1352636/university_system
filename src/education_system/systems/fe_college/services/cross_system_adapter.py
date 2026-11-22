"""This system's side of the platform transition contract.

FE College joined the cross-system registry alongside apprenticeships, so
a learner arriving from a secondary school, or converting from a study
programme onto an apprenticeship, lands as a real record rather than as a
note on a transition row. See ``platform.cross_system.adapters.base`` for
the contract; the platform orchestrates and the four methods here answer
for *this system only*.

The dependency points inwards: nothing in ``platform/`` imports this
module. It registers itself when :func:`register` is called at launch,
and the platform then addresses it by the system key ``"fe_college"``.

This lives in ``services/`` rather than a new ``integrations/`` package
because it is exactly what the layer is for — orchestration over the
repositories, with the domain rules (``Student.validate``, the status
vocabulary) still owning correctness.

One rule specific to FE: **the concurrent case is normal here.** An FE
learner who picks up an apprenticeship usually stays enrolled for the
qualification the college delivers, so ``close_enrolment`` is only called
when they have genuinely left. The platform decides that, via
``close_source=False`` on the transition.
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
from education_system.systems.fe_college.infrastructure.persistence import transaction
from education_system.systems.fe_college.infrastructure.persistence.schema import init_db

logger = logging.getLogger(__name__)

SYSTEM_KEY = "fe_college"


# ---------------------------------------------------------------------------
# Handover → student fields
# ---------------------------------------------------------------------------

def _text(value: Any) -> str:
    """Flatten a handover value into something a TEXT column can hold.

    Returns ``""`` rather than None: the FE ``Student`` model uses empty
    strings for absent optional text throughout, and mixing the two
    conventions in one row makes every reader test for both.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return "; ".join(f"{k}: {v}" for k, v in value.items() if v is not None)
    if isinstance(value, (list, tuple)):
        return "; ".join(str(v) for v in value if v is not None)
    return str(value)


def _identity(handover: HandoverRequest) -> dict[str, str]:
    """Pull name / DOB / ULN out of whichever identity field was sent.

    Boundaries name this field for their own vocabulary
    (``student_identity`` from secondary, ``learner_identity`` from
    apprenticeships), and a caller driving the workflow by hand may have
    put the fields at the top level. All shapes are accepted — refusing a
    handover over the spelling of a key would strand a real learner.
    """
    raw = (handover.get("student_identity")
           or handover.get("learner_identity")
           or handover.get("child_identity")
           or {})
    if not isinstance(raw, dict):
        raw = {}
    contact = handover.get("contact_details") or {}
    if not isinstance(contact, dict):
        contact = {}
    merged = {**handover.payload, **contact, **raw}

    def pick(*names: str) -> Any:
        for n in names:
            if merged.get(n) not in (None, ""):
                return merged[n]
        return None

    first = pick("first_name", "given_name", "legal_first_name", "forename")
    last = pick("last_name", "family_name", "legal_last_name", "surname")
    full = pick("full_name", "name")
    if (not first or not last) and isinstance(full, str) and full.strip():
        parts = full.strip().split()
        first = first or parts[0]
        last = last or (" ".join(parts[1:]) or parts[0])
    return {
        "first_name": _text(first),
        "last_name": _text(last),
        "date_of_birth": _text(pick("date_of_birth", "dob")),
        "uln": _text(pick("uln", "unique_learner_number")),
        "email": _text(pick("email", "personal_email")),
        "phone": _text(pick("phone", "mobile", "telephone")),
    }


def _prior_attainment(handover: HandoverRequest) -> str:
    """Everything that decides what the learner may enrol onto."""
    bits = []
    for key in ("gcse_results", "predicted_grades", "ks2_results",
                "core_assessments", "prior_attainment", "prior_learning",
                "achieved_qualifications", "functional_skills",
                "standard_completed", "epa_result"):
        text = _text(handover.get(key))
        if text:
            bits.append(f"{key.replace('_', ' ')}: {text}")
    return "\n".join(bits)


def _learning_support(handover: HandoverRequest) -> str:
    """SEND and support detail, as one note.

    These are the sensitive fields; if consent was withheld,
    ``build_handover`` has already stripped them and this comes back empty.
    """
    bits = []
    for key in ("send_provision", "send_support", "access_arrangements",
                "support_indicators", "current_interventions",
                "medical_requirements", "support_referral"):
        text = _text(handover.get(key))
        if text:
            bits.append(f"{key.replace('_', ' ')}: {text}")
    return "\n".join(bits)


def _has_ehcp(handover: HandoverRequest) -> int:
    """Whether the handover mentions an EHCP anywhere in the SEND fields.

    A keyword test, not a parse: the source systems record EHCP status as
    free text within a wider SEND field rather than as a flag, and an
    EHCP that fails to cross is a statutory duty missed. False positives
    cost a conversation; false negatives cost support the learner is
    legally entitled to.
    """
    haystack = " ".join(
        _text(handover.get(k)) for k in
        ("send_provision", "send_support", "access_arrangements",
         "support_indicators")).lower()
    return int("ehcp" in haystack or "education, health and care" in haystack)


def _age_band(date_of_birth: str) -> str:
    """The learner type for an age: 19 or over on 31 August is an adult."""
    try:
        dob = date.fromisoformat(str(date_of_birth)[:10])
    except ValueError:
        return "16-18 Study Programme"
    today = date.today()
    cutoff = date(today.year if today.month > 8 else today.year - 1, 8, 31)
    age = cutoff.year - dob.year - ((cutoff.month, cutoff.day) < (dob.month, dob.day))
    return "19+ Adult Learner" if age >= 19 else "16-18 Study Programme"


# ---------------------------------------------------------------------------
# The adapter
# ---------------------------------------------------------------------------

class FeCollegeAdapter(PhaseAdapter):
    """FE College's side of the four-method transition contract."""

    system = SYSTEM_KEY

    # ── Learner logins ──────────────────────────────────────────────

    learner_login_roles = ("student", "alumni")

    def learner_ids_for_login(self, account: dict) -> list[str]:
        """The learner this login signs in as, by FE's own rule — exactly.

        ``CollegeSession._find_student`` tries the username as a student id
        first, then a search on the email and then the username. The id
        step is used as is. The search is fuzzy (``LIKE`` over names, ids
        and emails) and settles for any single hit, which is fine for
        opening a screen but not for a record link, so here it is narrowed
        to an exact email match. Every exact match is returned:
        ``students.email`` is not unique, and two learners on one address
        must be seen, not guessed between.
        """
        from education_system.systems.fe_college.services import student_service

        username = str(account.get("username") or "").strip()
        if username:
            found = student_service.get(username.upper())
            if found is not None:
                return [found.student_id]
        for term in (account.get("email"), username):
            address = str(term or "").strip().lower()
            if not address or "@" not in address:
                continue
            exact = sorted({s.student_id for s in student_service.search(address)
                            if (s.email or "").strip().lower() == address})
            if exact:
                return exact
        return []

    # ── Destination side ────────────────────────────────────────────

    def create_applicant(self, handover: HandoverRequest) -> ApplicantResult:
        """Create (or find) the applicant record for an arriving learner.

        Idempotent on ``journey_id``: a redelivered bus event finds the
        row stamped by the first delivery rather than creating a second
        learner.
        """
        init_db()
        identity = _identity(handover)
        if not identity["first_name"] or not identity["last_name"]:
            raise AdapterError(
                f"Handover for journey {handover.journey_id} carries no usable "
                f"name; fe_college cannot create an applicant without one "
                f"(boundary {handover.boundary})")

        # Imported here, not at module load: the domain module pulls in the
        # config vocabulary, and an adapter that is registered but never
        # called should not pay for that.
        from education_system.systems.fe_college.domain.students.models import (
            next_student_id,
        )

        with transaction() as conn:
            existing = conn.execute(
                "SELECT student_id, status FROM students WHERE journey_id = ?",
                (handover.journey_id,)).fetchone()
            if existing is not None:
                logger.info(
                    "Journey %s already has FE learner %s (%s) — handover "
                    "from %s is a no-op", handover.journey_id,
                    existing["student_id"], existing["status"],
                    handover.source_system)
                return ApplicantResult(
                    local_applicant_id=existing["student_id"],
                    notes=f"existing record, status {existing['status']}")

            # A learner may already be here under their ULN without a
            # journey stamp — created locally before the platform knew
            # about them. Adopt that row rather than duplicating a person.
            if identity["uln"]:
                by_uln = conn.execute(
                    "SELECT student_id, status FROM students "
                    "WHERE uln = ? AND uln <> ''",
                    (identity["uln"],)).fetchone()
                if by_uln is not None:
                    conn.execute(
                        "UPDATE students SET journey_id = ?, "
                        "updated_at = datetime('now') WHERE student_id = ?",
                        (handover.journey_id, by_uln["student_id"]))
                    logger.info(
                        "Matched journey %s onto existing FE learner %s by ULN",
                        handover.journey_id, by_uln["student_id"])
                    return ApplicantResult(
                        local_applicant_id=by_uln["student_id"],
                        notes="matched on ULN")

            used = [r[0] for r in conn.execute(
                "SELECT student_id FROM students").fetchall()]
            student_id = next_student_id(used)

            # A learner arriving from apprenticeships is on the Apprentice
            # study programme, one from adult education is a 19+ adult
            # learner; everyone else defaults by age band.
            learner_type = {"apprenticeships": "Apprentice",
                            "adult_education": "19+ Adult Learner"}.get(
                handover.source_system, "16-18 Study Programme")
            if handover.source_system == "training_provider":
                # Short-course learners are any age: band them by it.
                learner_type = _age_band(identity["date_of_birth"])

            conn.execute(
                """INSERT INTO students
                     (student_id, journey_id, first_name, last_name,
                      date_of_birth, uln, email, phone, learner_type,
                      status, prior_attainment, has_ehcp, learning_support,
                      notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'applicant', ?, ?, ?, ?)""",
                (student_id, handover.journey_id, identity["first_name"],
                 identity["last_name"], identity["date_of_birth"] or None,
                 identity["uln"], identity["email"], identity["phone"],
                 learner_type, _prior_attainment(handover),
                 _has_ehcp(handover), _learning_support(handover),
                 f"Arrived from {handover.source_system} via transition "
                 f"{handover.transition_id or '(none)'}; "
                 f"journey {handover.journey_id}"))

        logger.info("Created FE applicant %s for journey %s (from %s)",
                    student_id, handover.journey_id, handover.source_system)
        return ApplicantResult(
            local_applicant_id=student_id,
            institution_id=handover.institution_id,
            year_group=handover.year_group,
            notes=f"applicant created from {handover.boundary}")

    def create_enrolment(self, journey_id: str,
                         application_id: str | None = None,
                         **details: Any) -> EnrolmentResult:
        """Promote an accepted applicant to an enrolled learner.

        Idempotent on ``journey_id``: a learner already enrolled (or
        beyond) is returned untouched rather than having their start date
        rewritten by a duplicate event.

        Enrolling onto a *course* is a separate act with its own rules
        (entry requirements, funding, timetable) and stays in
        ``student_service.enrol``. This method establishes the learner on
        roll, which is what the platform's contract asks for.
        """
        init_db()
        start_date = details.get("start_date") or date.today().isoformat()

        with transaction() as conn:
            row = conn.execute(
                "SELECT student_id, status, start_date FROM students "
                "WHERE journey_id = ?", (journey_id,)).fetchone()
            if row is None:
                raise AdapterError(
                    f"No FE learner for journey {journey_id}; "
                    f"create_applicant must run before create_enrolment")

            student_id = row["student_id"]
            if row["status"] != "applicant":
                logger.info(
                    "FE learner %s is already %s — create_enrolment is a "
                    "no-op", student_id, row["status"])
                return EnrolmentResult(local_student_id=student_id,
                                       start_date=row["start_date"],
                                       notes=f"already {row['status']}")

            patch: dict[str, Any] = {"status": "enrolled",
                                     "start_date": start_date}
            for field in ("tutor_group", "personal_tutor", "mode_of_study",
                          "learner_type"):
                if details.get(field):
                    patch[field] = details[field]

            assignments = ", ".join(f"{k} = ?" for k in patch)
            conn.execute(
                f"UPDATE students SET {assignments}, "
                "updated_at = datetime('now') WHERE student_id = ?",
                [*patch.values(), student_id])

        logger.info("FE learner %s enrolled from %s (journey %s)",
                    student_id, start_date, journey_id)
        return EnrolmentResult(
            local_student_id=student_id,
            institution_id=details.get("institution_id"),
            year_group=details.get("year_group"),
            start_date=start_date,
            notes="enrolled by cross-system transition")

    # ── Source side ─────────────────────────────────────────────────

    def export_handover(self, local_student_id: str,
                        consent: bool | set[str] | None = None,
                        *, destination_system: str | None = None
                        ) -> ExportResult:
        """Gather what the college holds about a departing learner.

        Returns everything for the boundary's field keys and lets
        ``handover.build_handover`` apply consent — filtering here too
        would put the consent decision in two places, and eventually they
        would disagree.
        """
        init_db()
        with transaction() as conn:
            row = conn.execute(
                "SELECT * FROM students WHERE student_id = ?",
                (local_student_id,)).fetchone()
            if row is None:
                raise AdapterError(
                    f"No FE learner {local_student_id} to export")

            # Units achieved so far are what a training provider maps
            # onto recognised prior learning, so they cross as structured
            # rows rather than as a summary sentence.
            aims = conn.execute(
                """SELECT c.title AS course, c.level, c.qualification_type,
                          e.academic_year, e.status, e.is_main_aim,
                          e.start_date, e.end_date,
                          e.predicted_grade, e.final_grade
                     FROM enrolments e
                     LEFT JOIN courses c ON c.course_id = e.course_id
                    WHERE e.student_id = ?
                    ORDER BY e.is_main_aim DESC, e.academic_year""",
                (local_student_id,)).fetchall()

        record: dict[str, Any] = {
            "learner_identity": {
                "first_name": row["first_name"],
                "last_name": row["last_name"],
                "date_of_birth": row["date_of_birth"],
                "uln": row["uln"],
            },
            "contact_details": {
                "email": row["email"],
                "phone": row["phone"],
                "address": row["address"],
                "postcode": row["postcode"],
            },
            "vocational_profile": {
                "learner_type": row["learner_type"],
                "mode_of_study": row["mode_of_study"],
                "status": row["status"],
                "courses": [dict(a) for a in aims],
            },
            "prior_attainment": row["prior_attainment"],
            "prior_learning": row["prior_attainment"],
            "send_support": row["learning_support"] or (
                "EHCP in place" if row["has_ehcp"] else None),
            "support_indicators": row["learning_support"],
        }

        logger.info("Exported FE learner %s for handover to %s",
                    local_student_id, destination_system or "(unspecified)")
        return ExportResult(record=record,
                            local_student_id=str(local_student_id))

    def receive_training_result(self, local_student_id: str,
                                result: dict[str, Any]) -> str | None:
        """A short course the college sent the learner on, from the training
        provider (``platform.cross_system.training_provider_requests``).

        A certificate goes onto the learner's prior attainment (it can be a
        licence to practise a course needs) and their notes; any other
        outcome goes onto their notes. Returns a line for the sender's log.
        """
        init_db()
        when = result.get("issued_on") or result.get("on") or date.today().isoformat()
        course = result.get("course") or "short course"
        if result.get("kind") == "certificate":
            level = f" ({result['level']})" if result.get("level") else ""
            expires = f", expires {result['expires_on']}" if result.get("expires_on") else ""
            line = (f"{course}{level} - certificate {result.get('cert_no') or ''} "
                    f"issued {when}{expires} (training provider)")
        else:
            line = f"{course}: {result.get('outcome') or 'update'} {when} (training provider)"
        with transaction() as conn:
            row = conn.execute("SELECT prior_attainment, notes FROM students "
                               "WHERE student_id = ?", (local_student_id,)).fetchone()
            if row is None:
                logger.warning("receive_training_result: no FE learner %s", local_student_id)
                return None
            prior = row["prior_attainment"] or ""
            if result.get("kind") == "certificate" and line not in prior:
                prior = f"{prior}\n{line}".strip()
            notes = row["notes"] or ""
            if line not in notes:
                notes = f"{notes}\n{line}".strip()
            conn.execute("UPDATE students SET prior_attainment = ?, notes = ?, "
                         "updated_at = datetime('now') WHERE student_id = ?",
                         (prior, notes, local_student_id))
        return line

    def close_enrolment(self, local_student_id: str,
                        reason: str, **details: Any) -> None:
        """Close the local record when a learner leaves. Never deletes.

        ``transferred`` when they have gone to another provider or system,
        ``withdrawn`` otherwise. A record already at a terminal status is
        left alone.

        Not called for a learner who keeps their college place while
        starting an apprenticeship — that is the common FE case, and the
        platform expresses it with ``close_source=False``.
        """
        init_db()
        status = details.get("status") or (
            "transferred" if "transfer" in reason.lower()
            or "progress" in reason.lower() else "withdrawn")
        end_date = details.get("end_date") or date.today().isoformat()

        with transaction() as conn:
            row = conn.execute(
                "SELECT status, notes FROM students WHERE student_id = ?",
                (local_student_id,)).fetchone()
            if row is None:
                logger.warning(
                    "close_enrolment: no FE learner %s (already removed?)",
                    local_student_id)
                return
            if row["status"] in ("withdrawn", "completed", "transferred"):
                logger.info("FE learner %s is already %s — not re-closing",
                            local_student_id, row["status"])
                return

            note = f"{row['notes'] or ''}\nLeft {end_date}: {reason}".strip()
            conn.execute(
                "UPDATE students SET status = ?, end_date = ?, notes = ?, "
                "updated_at = datetime('now') WHERE student_id = ?",
                (status, end_date, note, local_student_id))
            # Close the open course enrolments too, or the learner stays
            # on registers and in achievement returns after they have left.
            conn.execute(
                "UPDATE enrolments SET status = 'withdrawn', end_date = ? "
                "WHERE student_id = ? AND status NOT IN "
                "('withdrawn', 'completed', 'transferred')",
                (end_date, local_student_id))

        logger.info("FE learner %s closed as %s (%s)", local_student_id,
                    status, reason)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

ADAPTER = FeCollegeAdapter()


def register() -> FeCollegeAdapter:
    """Register this adapter with the platform. Idempotent.

    Called from the launcher rather than at package import: importing the
    FE College package should not drag the platform's cross-system stack
    in behind it.
    """
    registry.register(ADAPTER, replace=True)
    return ADAPTER


__all__ = ["SYSTEM_KEY", "FeCollegeAdapter", "ADAPTER", "register"]
