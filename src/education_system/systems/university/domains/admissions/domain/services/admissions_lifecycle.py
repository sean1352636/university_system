"""Authoritative applicant-to-enrolment lifecycle.

The CRM owns prospects and applications; this service adds the guarded
workflow which turns an accepted applicant into a student.  No intake path
should create an active student before :data:`READY_TO_ENROL`.
"""

from __future__ import annotations

import secrets
import logging
from datetime import datetime
from typing import Any

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)
from education_system.systems.university.infrastructure.database.schema_version import (
    require_tables,
)
from education_system.systems.university.services.boundary_errors import (
    AdmissionsBoundaryError,
)

logger = logging.getLogger(__name__)

SUBMITTED = "submitted"
DOCUMENTS_PENDING = "documents_pending"
UNDER_REVIEW = "under_review"
DECISION_PENDING = "decision_pending"
CONDITIONAL_OFFER = "conditional_offer"
UNCONDITIONAL_OFFER = "unconditional_offer"
ACCEPTED = "accepted"
CONDITIONS_MET = "conditions_met"
RIGHT_TO_STUDY = "right_to_study"
REGISTRATION_PENDING = "registration_pending"
READY_TO_ENROL = "ready_to_enrol"
ENROLLED = "enrolled"
DECLINED = "declined"
DEFERRED = "deferred"
LAPSED = "lapsed"

TERMINAL_STATES = frozenset({ENROLLED, DECLINED, LAPSED})

#: Condition states that no longer hold enrolment back.
CLOSED_CONDITION_STATES = frozenset({"satisfied", "superseded", "waived"})

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    SUBMITTED: frozenset({DOCUMENTS_PENDING, UNDER_REVIEW, DECLINED, DEFERRED}),
    DOCUMENTS_PENDING: frozenset({UNDER_REVIEW, DECLINED, DEFERRED}),
    UNDER_REVIEW: frozenset({
        DECISION_PENDING, CONDITIONAL_OFFER, UNCONDITIONAL_OFFER,
        DECLINED, DEFERRED,
    }),
    DECISION_PENDING: frozenset({
        CONDITIONAL_OFFER, UNCONDITIONAL_OFFER, DECLINED, DEFERRED,
    }),
    CONDITIONAL_OFFER: frozenset({ACCEPTED, DECLINED, DEFERRED, LAPSED}),
    UNCONDITIONAL_OFFER: frozenset({ACCEPTED, DECLINED, DEFERRED, LAPSED}),
    ACCEPTED: frozenset({
        CONDITIONS_MET, RIGHT_TO_STUDY, REGISTRATION_PENDING,
        DECLINED, DEFERRED,
    }),
    CONDITIONS_MET: frozenset({
        RIGHT_TO_STUDY, REGISTRATION_PENDING, DECLINED, DEFERRED,
    }),
    RIGHT_TO_STUDY: frozenset({
        REGISTRATION_PENDING, READY_TO_ENROL, DECLINED, DEFERRED,
    }),
    REGISTRATION_PENDING: frozenset({
        READY_TO_ENROL, DECLINED, DEFERRED,
    }),
    READY_TO_ENROL: frozenset({ENROLLED, DEFERRED}),
    DEFERRED: frozenset({SUBMITTED, DECLINED}),
}


def _ensure() -> None:
    require_tables(
        (
            "admission_applications",
            frozenset({
                "application_id", "status", "accepted_choice_id",
                "converted_student_id", "lifecycle_updated_at",
            }),
        ),
        (
            "admission_application_choices",
            frozenset({"choice_id", "application_id", "programme_code"}),
        ),
        (
            "admission_requirements",
            frozenset({"requirement_id", "application_id", "status"}),
        ),
        (
            "admission_conditions",
            frozenset({"condition_id", "application_id", "status"}),
        ),
        (
            "admission_status_history",
            frozenset({"history_id", "application_id", "to_status"}),
        ),
    )


def _application(conn, application_id: int):
    row = conn.execute(
        "SELECT * FROM admission_applications WHERE application_id = ?",
        (application_id,),
    ).fetchone()
    if row is None:
        raise AdmissionsBoundaryError(f"Application ID {application_id} does not exist.")
    return row


def transition(application_id: int, to_status: str, *, reason: str = "",
               actor_id: str = "", force: bool = False) -> dict[str, Any]:
    """Move an application through the state machine and audit the change."""
    _ensure()
    target = (to_status or "").strip().lower()
    with transaction() as conn:
        app = _application(conn, application_id)
        current = (app["status"] or SUBMITTED).strip().lower()
        if target == current:
            return dict(app)
        if not force and target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
            raise AdmissionsBoundaryError(
                f"Invalid admissions transition {current!r} -> {target!r}"
            )
        conn.execute(
            """UPDATE admission_applications
                  SET status = ?, lifecycle_updated_at = ?
                WHERE application_id = ?""",
            (target, datetime.now().isoformat(), application_id),
        )
        conn.execute(
            """INSERT INTO admission_status_history
                   (application_id, from_status, to_status, reason, actor_id)
               VALUES (?, ?, ?, ?, ?)""",
            (application_id, current, target, reason, actor_id),
        )
    return get_application(application_id)


def get_application(application_id: int) -> dict[str, Any]:
    """Return an application with its choices, checklist and audit history."""
    _ensure()
    with get_connection() as conn:
        app = _application(conn, application_id)
        result = dict(app)
        for key, table, order in (
            ("choices", "admission_application_choices", "rank, choice_id"),
            ("requirements", "admission_requirements", "requirement_id"),
            ("interviews", "admission_interviews", "scheduled_at, interview_id"),
            ("conditions", "admission_conditions", "condition_id"),
            ("history", "admission_status_history", "history_id"),
        ):
            result[key] = [
                # db-audit: ignore[DBW001] - statement builds SQL without splicing a value
                dict(row) for row in conn.execute(
                    f"SELECT * FROM {table} WHERE application_id = ? "
                    f"ORDER BY {order}",
                    (application_id,),
                ).fetchall()
            ]
        return result


def add_choice(application_id: int, programme_code: str, *,
               programme_name: str = "", entry_year: str = "",
               rank: int = 1) -> int:
    _ensure()
    if rank < 1:
        raise AdmissionsBoundaryError("Choice rank must be at least 1")
    with transaction() as conn:
        _application(conn, application_id)
        cur = conn.execute(
            """INSERT INTO admission_application_choices
                   (application_id, programme_code, programme_name,
                    entry_year, rank)
               VALUES (?, ?, ?, ?, ?)""",
            (application_id, programme_code, programme_name, entry_year, rank),
        )
        return int(cur.lastrowid)


def accept_choice(application_id: int, choice_id: int) -> None:
    _ensure()
    with transaction() as conn:
        _application(conn, application_id)
        choice = conn.execute(
            """SELECT choice_id FROM admission_application_choices
                WHERE choice_id = ? AND application_id = ?""",
            (choice_id, application_id),
        ).fetchone()
        if choice is None:
            raise AdmissionsBoundaryError("Choice does not belong to this application")
        conn.execute(
            "UPDATE admission_application_choices SET choice_status = "
            "CASE WHEN choice_id = ? THEN 'accepted' ELSE 'declined' END "
            "WHERE application_id = ?",
            (choice_id, application_id),
        )
        conn.execute(
            "UPDATE admission_applications SET accepted_choice_id = ? "
            "WHERE application_id = ?",
            (choice_id, application_id),
        )


def add_requirement(application_id: int, requirement_type: str,
                    description: str, *, due_date: str = "",
                    required: bool = True) -> int:
    _ensure()
    with transaction() as conn:
        _application(conn, application_id)
        cur = conn.execute(
            """INSERT INTO admission_requirements
                   (application_id, requirement_type, description,
                    due_date, required)
               VALUES (?, ?, ?, ?, ?)""",
            (application_id, requirement_type, description, due_date,
             int(required)),
        )
        return int(cur.lastrowid)


def verify_requirement(requirement_id: int, *, verified_by: str,
                       document_id: int | None = None, notes: str = "") -> None:
    _ensure()
    with transaction() as conn:
        cur = conn.execute(
            """UPDATE admission_requirements
                  SET status = 'verified', verified_by = ?, verified_at = ?,
                      evidence_document_id = ?, notes = ?
                WHERE requirement_id = ?""",
            (verified_by, datetime.now().isoformat(), document_id, notes,
             requirement_id),
        )
        if cur.rowcount != 1:
            raise AdmissionsBoundaryError(f"Requirement ID {requirement_id} does not exist.")


def schedule_activity(application_id: int, scheduled_at: str, *,
                      activity_type: str = "interview", format: str = "",
                      location: str = "", panel: str = "") -> int:
    """Schedule an interview or audition."""
    if activity_type not in {"interview", "audition"}:
        raise AdmissionsBoundaryError("activity_type must be 'interview' or 'audition'")
    _ensure()
    with transaction() as conn:
        _application(conn, application_id)
        cur = conn.execute(
            """INSERT INTO admission_interviews
                   (application_id, activity_type, scheduled_at, format,
                    location, panel)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (application_id, activity_type, scheduled_at, format, location,
             panel),
        )
        return int(cur.lastrowid)


def add_condition(application_id: int, condition_type: str, description: str,
                  *, amount: float | None = None, currency: str = "",
                  sponsor_name: str = "", due_date: str = "") -> int:
    """Add an academic, deposit, sponsorship or right-to-study condition."""
    _ensure()
    with transaction() as conn:
        _application(conn, application_id)
        cur = conn.execute(
            """INSERT INTO admission_conditions
                   (application_id, condition_type, description, amount,
                    currency, sponsor_name, due_date)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (application_id, condition_type, description, amount, currency,
             sponsor_name, due_date),
        )
        return int(cur.lastrowid)


def satisfy_condition(condition_id: int, *,
                      evidence_reference: str = "") -> None:
    _ensure()
    with transaction() as conn:
        cur = conn.execute(
            """UPDATE admission_conditions
                  SET status = 'satisfied', satisfied_at = ?,
                      evidence_reference = ?
                WHERE condition_id = ?""",
            (datetime.now().isoformat(), evidence_reference, condition_id),
        )
        if cur.rowcount != 1:
            raise AdmissionsBoundaryError(f"Condition ID {condition_id} does not exist.")


def readiness_issues(application_id: int) -> list[str]:
    """Return the reasons an accepted application cannot yet enrol."""
    app = get_application(application_id)
    issues: list[str] = []
    if app["status"] != READY_TO_ENROL:
        issues.append(f"status is {app['status']!r}, not {READY_TO_ENROL!r}")
    if not app.get("accepted_choice_id"):
        issues.append("no accepted programme choice")
    if any(r["required"] and r["status"] != "verified"
           for r in app["requirements"]):
        issues.append("required documents/checks remain outstanding")
    # "superseded" marks a condition of an offer the learner no longer
    # holds — a missed Firm replaced by the Insurance, or a Clearing place —
    # recorded by sixthform_handover_records rather than deleted. "waived"
    # is admissions staff setting a condition aside with a recorded reason
    # (admissions_checklist.waive_condition).
    if any(c["status"] not in CLOSED_CONDITION_STATES
           for c in app["conditions"]):
        issues.append("offer, deposit or sponsorship conditions remain outstanding")
    issues.extend(_postgraduate_issues(application_id, app))
    try:
        from education_system.systems.university.domains.admissions.domain import (
            sixthform_handover_records as _handover_records,
        )
        deferred = _handover_records.deferred_entry_issue(application_id)
    except Exception:
        logger.exception("Could not check deferred entry for application %s",
                         application_id)
        deferred = None
    if deferred:
        issues.append(deferred)
    with get_connection() as conn:
        condition_types = {
            row["condition_type"]
            for row in conn.execute(
                "SELECT condition_type FROM admission_conditions WHERE application_id = ?",
                (application_id,),
            ).fetchall()
        }
        if "deposit" in condition_types:
            deposit = conn.execute(
                "SELECT status FROM admission_deposit_decisions WHERE application_id = ?",
                (application_id,),
            ).fetchone()
            if deposit is None or deposit["status"] != "satisfied":
                issues.append("deposit policy decision is not satisfied")
        if "sponsorship" in condition_types:
            sponsorship = conn.execute(
                "SELECT status FROM admission_sponsorship_decisions WHERE application_id = ?",
                (application_id,),
            ).fetchone()
            if sponsorship is None or sponsorship["status"] != "approved":
                issues.append("sponsorship policy decision is not approved")
        right_to_study = conn.execute(
            "SELECT status FROM admission_right_to_study_decisions WHERE application_id = ?",
            (application_id,),
        ).fetchone()
        if right_to_study is None or right_to_study["status"] != "approved":
            issues.append("right-to-study policy decision is not approved")
    return issues


def _postgraduate_issues(application_id: int, app: dict) -> list[str]:
    """References, and for research degrees the proposal, supervisor
    agreement and interview — gates just like conditions."""
    from education_system.systems.university.domains.admissions.domain.services import (
        admissions_postgraduate,
    )
    if not admissions_postgraduate.is_postgraduate(app.get("application_type")):
        return []
    try:
        return admissions_postgraduate.requirement_issues(application_id)
    except Exception as exc:
        logger.exception("Postgraduate checks failed for application %s",
                         application_id)
        return [f"postgraduate requirements could not be checked: {exc}"]


def convert_to_student(application_id: int, *, actor_id: str = "") -> str:
    """Atomically create the student, registration, history and outbox event."""
    existing = get_application(application_id).get("converted_student_id")
    if existing:
        return str(existing)
    issues = readiness_issues(application_id)
    if issues:
        raise AdmissionsBoundaryError("Application is not ready to enrol: " + "; ".join(issues))
    with transaction() as conn:
        locked_app = _application(conn, application_id)
        if locked_app["converted_student_id"]:
            return str(locked_app["converted_student_id"])
        row = conn.execute(
            """SELECT p.*, c.programme_code, a.academic_year, a.journey_id,
                      a.application_type, a.external_reference
                 FROM admission_applications a
                 JOIN admission_prospects p ON p.prospect_id = a.prospect_id
                 JOIN admission_application_choices c
                   ON c.choice_id = a.accepted_choice_id
                WHERE a.application_id = ?""",
            (application_id,),
        ).fetchone()
        if row is None:
            raise AdmissionsBoundaryError("Applicant or accepted choice is missing")
        student_id = _allocate_student_id(conn, row)

        now = datetime.now().isoformat()
        conn.execute(
            """INSERT INTO students
                 (student_id, email_address, first_name, last_name, dob, age,
                  course, registration_datetime, status, enrollment_date,
                  journey_id, academic_year)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Registration Pending', ?, ?, ?)""",
            (
                student_id,
                row["email"],
                row["first_name"],
                row["last_name"],
                row["date_of_birth"],
                None,
                row["programme_code"],
                now,
                now,
                row["journey_id"],
                row["academic_year"],
            ),
        )
        registration = _insert_registration(conn, row, student_id, application_id, actor_id)
        programme_registration = conn.execute(
            """INSERT INTO programme_registrations
                 (student_id, programme_code, academic_year, occurrence_code,
                  mode_of_study, status, effective_from, registered_at)
               VALUES (?, ?, ?, 'MAIN', 'full-time', 'registered', ?, ?)""",
            (
                student_id, row["programme_code"], row["academic_year"],
                now[:10], now,
            ),
        )
        history = conn.execute(
            """INSERT INTO student_lifecycle_history
                 (student_id, action, from_status, to_status, effective_date,
                  academic_year, new_programme, reason, actor_id)
               VALUES (?, 'initial_registration', 'Registration Pending',
                       'Active', ?, ?, ?, 'Admissions conversion', ?)""",
            (
                student_id, now[:10], row["academic_year"],
                row["programme_code"], actor_id or "admissions",
            ),
        )
        payload = {
            "student_id": student_id,
            "application_id": application_id,
            "registration_id": int(registration.lastrowid),
            "programme_registration_id": int(programme_registration.lastrowid),
            "programme_code": row["programme_code"],
            "academic_year": row["academic_year"],
        }
        import json
        for target in (
            "finance", "module_enrolments", "visa_monitoring",
            "accommodation", "library", "student_account",
        ):
            conn.execute(
                """INSERT INTO student_lifecycle_actions
                     (history_id, student_id, target_system, action, payload_json)
                   VALUES (?, ?, ?, 'initial_registration', ?)""",
                (int(history.lastrowid), student_id, target, json.dumps(payload)),
            )
        _stage_pgr_handover(conn, application_id, int(history.lastrowid),
                            student_id, payload, actor_id)
        conn.execute(
            """UPDATE admission_applications
                  SET converted_student_id = ?, enrollment_confirmed = 1,
                      status = 'enrolled', lifecycle_updated_at = ?
                WHERE application_id = ?""",
            (student_id, now, application_id),
        )
        conn.execute(
            """INSERT INTO admission_status_history
                 (application_id, from_status, to_status, reason, actor_id)
               VALUES (?, 'ready_to_enrol', 'enrolled',
                       'Applicant atomically converted and registered', ?)""",
            (application_id, actor_id),
        )
        conn.execute(
            "UPDATE students SET status = 'Active' WHERE student_id = ?",
            (student_id,),
        )
        from education_system.systems.university.infrastructure.events import (
            transactional_publisher,
        )
        transactional_publisher.publish(
            conn,
            "admissions.student.converted",
            payload,
            aggregate_id=student_id,
            idempotency_key=f"admissions:{application_id}:converted",
        )

    _project_conversion(row, student_id, application_id, actor_id)
    return student_id


def _stage_pgr_handover(conn, application_id: int, history_id: int,
                        student_id: str, payload: dict, actor_id: str) -> None:
    """For a research applicant, queue the proposal and the supervisors who
    agreed for the PGR record (``research_pgr`` lifecycle action), in the
    conversion's own transaction."""
    import json
    from education_system.systems.university.domains.admissions.domain.services import (
        admissions_postgraduate,
    )
    handover = admissions_postgraduate.pgr_handover(conn, application_id)
    if handover is None:
        return
    conn.execute(
        """INSERT INTO student_lifecycle_actions
             (history_id, student_id, target_system, action, payload_json)
           VALUES (?, ?, 'research_pgr', 'initial_registration', ?)""",
        (history_id, student_id,
         json.dumps({**payload, **handover, "actor_id": actor_id or "admissions"})),
    )


def _allocate_student_id(conn, row) -> str:
    """A free student ID: a degree apprentice keeps their reference if it is
    free, everyone else gets a random seven-digit number."""
    requested_student_id = (
        str(row["external_reference"] or "").strip()
        if row["application_type"] == "degree_apprenticeship" else ""
    )
    for attempt in range(20):
        student_id = (
            requested_student_id if attempt == 0 and requested_student_id
            else str(secrets.randbelow(9_000_000) + 1_000_000)
        )
        exists = conn.execute(
            "SELECT 1 FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()
        if exists is None:
            return student_id
    raise AdmissionsBoundaryError("Could not allocate a university student ID")


def _insert_registration(conn, row, student_id: str, application_id: int, actor_id: str):
    """The initial student registration, pinned to the programme's
    regulation version where there is one. Returns the insert cursor."""
    from education_system.systems.university.domains.learners.domain.student_lifecycle import (
        _regulation_version,
    )
    regulation_version = _regulation_version(
        conn, row["programme_code"], row["academic_year"]
    )
    registration_columns = {
        column[1] for column in conn.execute(
            "PRAGMA table_info(student_registrations)"
        ).fetchall()
    }
    if "regulation_version_id" in registration_columns:
        registration = conn.execute(
            """INSERT INTO student_registrations
                 (student_id, academic_year, registration_type,
                  programme_code, registered_by, declarations_json,
                  regulation_version_id)
               VALUES (?, ?, 'initial', ?, ?, '{}', ?)""",
            (
                student_id, row["academic_year"], row["programme_code"],
                actor_id or "admissions", regulation_version,
            ),
        )
    else:
        registration = conn.execute(
            """INSERT INTO student_registrations
                 (student_id, academic_year, registration_type,
                  programme_code, registered_by, declarations_json)
               VALUES (?, ?, 'initial', ?, ?, '{}')""",
            (
                student_id, row["academic_year"], row["programme_code"],
                actor_id or "admissions",
            ),
        )
    if regulation_version is not None:
        programme = conn.execute(
            "SELECT programme_id FROM programme_versions WHERE version_id=?",
            (regulation_version,),
        ).fetchone()
        conn.execute(
            """INSERT INTO student_regulation_assignments
                 (student_id, programme_id, version_id, assigned_by, reason)
               VALUES (?, ?, ?, ?, ?)""",
            (
                student_id, programme["programme_id"], regulation_version,
                actor_id or "admissions", f"Initial registration {application_id}",
            ),
        )
    return registration


def _project_conversion(row, student_id: str, application_id: int, actor_id: str) -> None:
    """After the commit: the linked-learner identity, sixth-form medical
    import and degree-apprenticeship snapshot. A failure here is logged and
    never undoes the conversion."""
    journey_id = row["journey_id"]
    if not journey_id:
        return
    try:
        from education_system.platform.cross_system import identity_service
        identity_service.link_system(
            journey_id, "university", student_id=student_id, set_current=True
        )
        source_system = (
            "apprenticeships"
            if row["application_type"] == "degree_apprenticeship"
            else "sixth_form"
        )
        identity_service.record_transition(
            journey_id, from_system=source_system, to_system="university",
            reason="Admissions conversion completed",
        )
    except Exception:
        # The committed outbox event is the retry source for this external
        # identity projection; conversion itself remains successful.
        logger.exception(
            "Identity projection deferred for converted application %s",
            application_id,
        )
    if row["application_type"] != "degree_apprenticeship":
        _import_sixth_form_medical(journey_id, student_id, application_id,
                                   actor_id)
    if row["application_type"] == "degree_apprenticeship":
        try:
            from education_system.systems.university.services.bus import (
                degree_apprenticeship_events,
            )
            with get_connection() as conn:
                degree = conn.execute(
                    """SELECT program_id FROM degree_programs
                         WHERE program_code=? AND is_active=1
                         ORDER BY program_id LIMIT 1""",
                    (row["programme_code"],),
                ).fetchone()
            if degree:
                degree_apprenticeship_events.publish_current_snapshot(
                    journey_id=journey_id,
                    university_student_id=student_id,
                    university_degree_program_id=int(degree["program_id"]),
                    reason="registration",
                )
        except Exception:
            logger.exception(
                "Degree-apprenticeship registration projection deferred "
                "for application %s", application_id,
            )


def attach_direct_enrolment(application_id: int, student_id: str, *,
                            actor_id: str = "", reason: str = "") -> bool:
    """Bind a student who was created outside this lifecycle to their
    application.

    :func:`convert_to_student` is the supported route and does the checks.
    This is the reconciliation for the route that does not: the students
    GUI's sixth-form import creates an active student directly, and if
    the bus had already staged that learner as an applicant, the two
    records sat side by side with nothing joining them — one person, two
    canonical rows, and an application that would sit in
    ``documents_pending`` forever against somebody already enrolled.

    Attaching is strictly better than leaving the orphan, and strictly
    worse than converting properly, so it says so in the audit trail: the
    status history records that the enrolment bypassed the gates rather
    than passing them.

    Returns True if this call did the attaching. False if the application
    is already bound — to this student (nothing to do) or, more
    importantly, to a *different* one, which is a genuine conflict and is
    logged rather than silently overwritten.
    """
    _ensure()
    with transaction() as conn:
        app = _application(conn, application_id)
        current_student = app["converted_student_id"]
        if current_student:
            if str(current_student) == str(student_id):
                return False
            logger.error(
                "Application %s is already enrolled as student %s; refusing "
                "to re-point it at %s. Two university records now exist for "
                "one applicant and need manual reconciliation.",
                application_id, current_student, student_id)
            return False
        from_status = (app["status"] or SUBMITTED).strip().lower()
        conn.execute(
            """UPDATE admission_applications
                  SET converted_student_id = ?, enrollment_confirmed = 1,
                      status = ?, lifecycle_updated_at = ?
                WHERE application_id = ?""",
            (student_id, ENROLLED, datetime.now().isoformat(),
             application_id),
        )
        conn.execute(
            """INSERT INTO admission_status_history
                   (application_id, from_status, to_status, reason, actor_id)
               VALUES (?, ?, ?, ?, ?)""",
            (application_id, from_status, ENROLLED,
             reason or "Enrolled directly outside the admissions lifecycle "
                       "— readiness gates were not evaluated",
             actor_id),
        )
    logger.warning(
        "Application %s attached to directly-created student %s by %s. The "
        "readiness gates (conditions, right to study, registration) were "
        "NOT evaluated for this enrolment.",
        application_id, student_id, actor_id or "unknown actor")
    return True


def _import_sixth_form_medical(journey_id: str, student_id: str,
                               application_id: int,
                               actor_id: str = "") -> None:
    """Copy a converted applicant's sixth-form medical record onto the student.

    Conversion is the earliest point this can happen at all: the import
    needs a university student id, and the bus intake deliberately creates
    an *applicant*. A helper that lived beside that intake could therefore
    never fire — one did, and never did, so every bus-driven transfer
    landed a student with no allergies, conditions or medications while
    the manual GUI import carried them.

    The sixth-form id comes from the journey rather than the application's
    ``external_reference``, which holds a UCAS number whenever there is one.

    Guarded separately from the identity projection above: a student who
    is enrolled stays enrolled even if their medical record cannot be
    copied. The failure is logged at exception level rather than shrugged
    off, because a missing allergy is a safety matter, not untidy data.

    No lawful basis is asserted here. Conversion is a planned, routine
    step with a real applicant record behind it, so if the learner never
    consented to their health data crossing, the answer is that it does
    not cross — a refusal is logged and enrolment continues. Vital
    interests exist for the emergency, and an emergency is not what a
    scheduled admissions conversion is.
    """
    try:
        from education_system.platform.cross_system import identity_service
        journey = identity_service.get(journey_id) or {}
        _pk_col, sf_id_col = identity_service.SYSTEM_SLOTS["sixth_form"]
        sf_student_id = journey.get(sf_id_col)
        if not sf_student_id:
            return
        # Admissions reaching into Pastoral. Allow-listed, and the target
        # design is still a port Pastoral owns — see the admissions slice
        # boundary ratchet.
        from education_system.systems.university.domains.health.domain.health.records import (
            sixth_form_import,
        )
        try:
            summary = sixth_form_import.import_from_sixth_form(
                uni_student_id=student_id, sf_student_id=sf_student_id,
                actor=actor_id or "admissions",
                received_by="university admissions")
        except sixth_form_import.MedicalHandoverRefused as refused:
            logger.warning(
                "Sixth-form medical record NOT copied for %s -> %s: %s. "
                "The student is enrolled; wellbeing must collect their "
                "health record directly or obtain the consent.",
                sf_student_id, student_id, refused)
            return
        logger.info(
            "Imported sixth-form medical record for %s -> %s "
            "(basis=%s, %d conditions, %d medications, %d allergies)",
            sf_student_id, student_id, summary.basis,
            summary.conditions_written, summary.medications_written,
            summary.allergies_written)
    except Exception:
        logger.exception(
            "Sixth-form medical import failed for converted application %s "
            "(student %s is enrolled regardless)", application_id, student_id)


__all__ = [
    "ALLOWED_TRANSITIONS", "READY_TO_ENROL", "ENROLLED",
    "transition", "get_application", "add_choice", "accept_choice",
    "add_requirement", "verify_requirement", "schedule_activity",
    "add_condition", "satisfy_condition", "readiness_issues",
    "convert_to_student", "attach_direct_enrolment",
]
