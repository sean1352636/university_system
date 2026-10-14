"""Student CRUD routes for the University system.

All writes go through :class:`StudentLifecycleService`, the same application
service the desktop GUI and the CLI use. That service owns course-catalogue
validation, curriculum enrolment, the transactional outbox event, the
editable-field whitelist and the withdraw/restore transitions, so the three
adapters cannot drift apart. Reads still go through the student repository.
"""

from __future__ import annotations

import logging
import secrets

from flask import Blueprint, g, jsonify, request

from education_system.platform.delivery.api.university.auth import (
    authorize_object,
    token_required,
)
from education_system.platform.delivery.api.university.pagination import (
    get_pagination_params,
    paginated_response,
)
from education_system.systems.university.application.student_lifecycle_service import (
    Gender,
    PurgeControlError,
    StudentCommand,
    StudentLifecycleService,
    StudentValidationError,
)
from education_system.systems.university.services.retention import has_active_hold
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.exceptions import StudentNotFoundError
from education_system.systems.university.infrastructure.repositories.student import (
    Student,
    get_student_repository,
)

_STAFF_ROLES = {"admin", "staff", "superadmin", "instructor", "teacher", "faculty"}


def _is_staff() -> bool:
    return (g.current_user or {}).get("role") in _STAFF_ROLES


def _authorize_student_access(student_id: str):
    """Return a (response, status) tuple if the caller may not access this
    student record, otherwise None. Staff/admin bypass; students may only
    access their own record (matched against JWT ``sub``)."""
    if _is_staff():
        return None
    if str((g.current_user or {}).get("sub") or "") == str(student_id):
        return None
    return jsonify({"error": "Forbidden", "status": 403}), 403


logger = logging.getLogger(__name__)

student_bp = Blueprint("students", __name__, url_prefix="/api/students")

def _lifecycle() -> StudentLifecycleService:
    """The one writer for student records, shared with the GUI and CLI."""
    return StudentLifecycleService()


def _actor_id() -> str:
    """Who is making the change, for the audit trail.

    The desktop adapters pass ``auth.current_user['id']``. The JWT's
    ``user_id`` is that same auth.db identity; ``sub`` is the fallback when a
    token predates the claim. Note the university keeps two id spaces, so
    this is deliberately not the student_records.db id.
    """
    user = g.current_user or {}
    return str(user.get("user_id") or user.get("sub") or "unknown")


def _idempotency_key(operation: str, student_id: str | None = None) -> str:
    """``api:<op>[:<student_id>]:<token>``, matching the gui:/cli: convention.

    A client may pin its own with an ``Idempotency-Key`` header; the service
    returns the original result for a repeated key rather than acting twice.
    """
    supplied = (request.headers.get("Idempotency-Key") or "").strip()
    if supplied:
        return supplied
    suffix = secrets.token_urlsafe(18)
    return (f"api:{operation}:{student_id}:{suffix}" if student_id
            else f"api:{operation}:{suffix}")


def _validation_error(exc: StudentValidationError):
    return jsonify({"error": "Validation Error",
                    "errors": exc.errors, "status": 400}), 400


def _student_to_dict(s: Student) -> dict:
    return {
        "student_id": s.student_id,
        "first_name": s.first_name,
        "middle_name": s.middle_name,
        "last_name": s.last_name,
        "full_name": s.full_name,
        "email_address": s.email_address,
        "title": s.title,
        "gender": s.gender,
        "dob": s.dob,
        "age": s.age,
        "course": s.course,
        "status": s.status,
        "enrollment_date": s.enrollment_date,
        "registration_datetime": s.registration_datetime,
    }


@student_bp.route("", methods=["GET"])
@token_required
def list_students():
    if not _is_staff():
        denied = authorize_object((g.current_user or {}).get("sub"))
        if denied is not None:
            return denied
        student = get_student_repository().get_by_id((g.current_user or {}).get("sub"))
        if not student:
            return jsonify({"items": [], "total": 0})
        return jsonify({"items": [_student_to_dict(student)], "total": 1})
    repo = get_student_repository()
    search_query = request.args.get("search")
    status_filter = request.args.get("status")
    course_filter = request.args.get("course")

    if search_query:
        students = repo.search(search_query)
    elif status_filter:
        students = repo.find_by_status(status_filter)
    elif course_filter:
        students = repo.find_by_course(course_filter)
    else:
        page, per_page, offset = get_pagination_params()
        students = repo.get_all(limit=per_page, offset=offset)
        total = repo.count()
        log_activity("view", "students", user=g.current_user.get("sub"))
        return jsonify(paginated_response(
            [_student_to_dict(s) for s in students], total, page, per_page
        ))

    log_activity("view", "students", user=g.current_user.get("sub"))
    return jsonify({"items": [_student_to_dict(s) for s in students], "total": len(students)})


@student_bp.route("/<student_id>", methods=["GET"])
@token_required
def get_student(student_id: str):
    denied = _authorize_student_access(student_id)
    if denied is not None:
        return denied
    repo = get_student_repository()
    student = repo.get_by_id(student_id)
    if not student:
        raise StudentNotFoundError(student_id)
    log_activity("view", "student", user=g.current_user.get("sub"))
    return jsonify(_student_to_dict(student))


@student_bp.route("", methods=["POST"])
@token_required
def create_student():
    """Create a student through the canonical lifecycle service.

    Deliberately the same route the GUI and CLI take
    (``StudentLifecycleService.create`` then ``.provision``), so all three
    adapters share one set of rules: active-catalogue course validation,
    curriculum enrolment, the transactional outbox event, and provisioning
    with a single-use activation link. The previous implementation wrote
    through the repository directly, which skipped every one of those and
    assigned the course at random.
    """
    denied = authorize_object("staff-boundary", permission="manage_students")
    if denied is not None:
        return denied

    data = request.get_json(silent=True) or {}
    try:
        command = StudentCommand(
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            dob=data.get("dob", ""),
            course=data.get("course", ""),
            middle_name=data.get("middle_name", "") or "",
            title=data.get("title", "") or "",
            gender=data.get("gender") or Gender.UNSPECIFIED,
            student_id=data.get("student_id"),
            email_address=data.get("email_address"),
            entry_qualifications=data.get("entry_qualifications", "") or "",
            ucas_tariff=data.get("ucas_tariff"),
        )
        created = _lifecycle().create(
            command,
            actor_id=_actor_id(),
            idempotency_key=_idempotency_key("create"),
        )
    except StudentValidationError as exc:
        return _validation_error(exc)

    # Provisioning is best-effort and retryable from the outbox, exactly as
    # in the desktop adapters: the student row is already committed.
    provisioning_error = None
    try:
        provisioned = _lifecycle().provision(created.student_id, auth=UserAuth())
        provisioning_error = provisioned.provisioning_error
    except Exception as exc:  # noqa: BLE001 - never fail a committed create
        logger.warning("Provisioning failed for %s", created.student_id, exc_info=True)
        provisioning_error = str(exc)

    log_activity("create", "student", user=g.current_user.get("sub"))
    body = {
        "student_id": created.student_id,
        "status": str(created.status),
        "event_id": created.event_id,
        "provisioning_error": provisioning_error,
    }
    if provisioning_error:
        body["message"] = (
            "Student was saved safely, but provisioning is pending. "
            "The outbox can retry it."
        )
    else:
        body["message"] = (
            "Student created and provisioned. A single-use activation link "
            "was sent to their university email address."
        )
    return jsonify(body), 201


@student_bp.route("/<student_id>", methods=["PUT"])
@token_required
def update_student(student_id: str):
    """Update a student through the lifecycle service.

    The service owns the editable-field whitelist and requires a reason for
    the audit trail, so this route does not maintain its own list. Fields the
    service refuses (``email_address``, ``age``, ``status``) are derived or
    lifecycle-owned and must not be edited directly.
    """
    denied = authorize_object("staff-boundary", permission="manage_students")
    if denied is not None:
        return denied

    data = request.get_json(silent=True) or {}
    reason = str(data.get("reason") or "").strip()
    changes = {key: value for key, value in data.items() if key != "reason"}
    if not changes:
        return jsonify({"error": "Validation Error",
                        "errors": {"changes": "no fields to update"},
                        "status": 400}), 400
    try:
        result = _lifecycle().update(
            student_id, changes,
            actor_id=_actor_id(),
            reason=reason,
            idempotency_key=_idempotency_key("update", student_id),
        )
    except StudentValidationError as exc:
        return _validation_error(exc)

    log_activity("update", "student", user=g.current_user.get("sub"))
    return jsonify({
        "student_id": result.student_id,
        "status": str(result.status),
        "event_id": result.event_id,
        "changed_fields": list(result.changed_fields),
    })


@student_bp.route("/<student_id>", methods=["DELETE"])
@token_required
def delete_student(student_id: str):
    """Withdraw a student, preserving their academic record.

    This mirrors the GUI and CLI, whose "delete student" actions both call
    ``deactivate``. A destructive erase is a separate, dual-controlled
    operation - see ``POST /<student_id>/purge``. The previous implementation
    hard-deleted the row inline, which the service forbids outright.
    """
    denied = authorize_object("staff-boundary", permission="manage_students")
    if denied is not None:
        return denied

    data = request.get_json(silent=True) or {}
    reason = str(data.get("reason") or "").strip()
    try:
        result = _lifecycle().deactivate(
            student_id,
            actor_id=_actor_id(),
            reason=reason,
            idempotency_key=_idempotency_key("deactivate", student_id),
        )
    except StudentValidationError as exc:
        return _validation_error(exc)

    log_activity("deactivate", "student", user=g.current_user.get("sub"))
    return jsonify({
        "student_id": result.student_id,
        "status": str(result.status),
        "event_id": result.event_id,
        "message": (
            f"Student {result.student_id} deactivated; "
            "academic records were preserved."
        ),
    })


@student_bp.route("/<student_id>/restore", methods=["POST"])
@token_required
def restore_student(student_id: str):
    """Reverse a withdrawal."""
    denied = authorize_object("staff-boundary", permission="manage_students")
    if denied is not None:
        return denied

    data = request.get_json(silent=True) or {}
    try:
        result = _lifecycle().restore(
            student_id,
            actor_id=_actor_id(),
            reason=str(data.get("reason") or "").strip(),
            idempotency_key=_idempotency_key("restore", student_id),
        )
    except StudentValidationError as exc:
        return _validation_error(exc)

    log_activity("restore", "student", user=g.current_user.get("sub"))
    return jsonify({"student_id": result.student_id,
                    "status": str(result.status),
                    "event_id": result.event_id})


@student_bp.route("/<student_id>/impact", methods=["GET"])
@token_required
def student_purge_impact(student_id: str):
    """Row counts an erasure would affect - read-only, no records touched.

    The confirmation evidence for ``POST /<student_id>/purge`` below.
    """
    denied = authorize_object("staff-boundary", permission="manage_students")
    if denied is not None:
        return denied
    try:
        return jsonify({"student_id": student_id,
                        "impact": _lifecycle().impact_preview(student_id)})
    except StudentValidationError as exc:
        return _validation_error(exc)


@student_bp.route("/<student_id>/purge", methods=["POST"])
@token_required
def purge_student(student_id: str):
    """Queue an erasure request under dual control.

    The service never deletes inline: it validates the controls and publishes
    a ``student.purge.requested`` event for the outbox worker. The student
    must already be withdrawn, the approver must differ from the actor, the
    caller must have re-authenticated, and the retention register must show
    no active legal hold.

    The hold check is ``services.retention.has_active_hold`` - the legal
    register, NOT ``services.bus.finance_bus.has_active_hold``, which means
    unpaid fees. Confusing the two would let a library fine block a lawful
    erasure while a litigation hold went undetected.
    """
    denied = authorize_object("staff-boundary", permission="manage_students")
    if denied is not None:
        return denied

    data = request.get_json(silent=True) or {}
    try:
        result = _lifecycle().purge(
            student_id,
            actor_id=_actor_id(),
            approved_by=str(data.get("approved_by") or ""),
            reason=str(data.get("reason") or ""),
            case_reference=str(data.get("case_reference") or ""),
            reauthenticated=bool(data.get("reauthenticated")),
            legal_hold_check=has_active_hold,
            idempotency_key=_idempotency_key("purge", student_id),
        )
    except PurgeControlError as exc:
        return jsonify({"error": "Purge control failed", "message": str(exc),
                        "status": 409}), 409
    except StudentValidationError as exc:
        return _validation_error(exc)

    log_activity("purge_requested", "student", user=g.current_user.get("sub"))
    return jsonify({
        "student_id": result.student_id,
        "status": str(result.status),
        "event_id": result.event_id,
        "message": "Purge requested; the outbox worker will carry it out.",
    }), 202
