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
    if any(c["status"] != "satisfied" for c in app["conditions"]):
        issues.append("offer, deposit or sponsorship conditions remain outstanding")
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
            """SELECT p.*, c.programme_code, a.academic_year, a.journey_id
                 FROM admission_applications a
                 JOIN admission_prospects p ON p.prospect_id = a.prospect_id
                 JOIN admission_application_choices c
                   ON c.choice_id = a.accepted_choice_id
                WHERE a.application_id = ?""",
            (application_id,),
        ).fetchone()
        if row is None:
            raise AdmissionsBoundaryError("Applicant or accepted choice is missing")
        for _ in range(20):
            student_id = str(secrets.randbelow(9_000_000) + 1_000_000)
            exists = conn.execute(
                "SELECT 1 FROM students WHERE student_id = ?", (student_id,)
            ).fetchone()
            if exists is None:
                break
        else:
            raise AdmissionsBoundaryError("Could not allocate a university student ID")

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
        from education_system.systems.university.domain.learners.student_lifecycle import (
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

    journey_id = row["journey_id"]
    if journey_id:
        try:
            from education_system.platform.cross_system import identity_service
            identity_service.link_system(
                journey_id, "university", student_id=student_id, set_current=True
            )
            identity_service.record_transition(
                journey_id, from_system="sixth_form", to_system="university",
                reason="Admissions conversion completed",
            )
        except Exception:
            # The committed outbox event is the retry source for this external
            # identity projection; conversion itself remains successful.
            logger.exception(
                "Identity projection deferred for converted application %s",
                application_id,
            )
    return student_id


__all__ = [
    "ALLOWED_TRANSITIONS", "READY_TO_ENROL", "ENROLLED",
    "transition", "get_application", "add_choice", "accept_choice",
    "add_requirement", "verify_requirement", "schedule_activity",
    "add_condition", "satisfy_condition", "readiness_issues",
    "convert_to_student",
]
