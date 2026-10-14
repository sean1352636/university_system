"""Course catalogue routes: CRUD, archive/restore and delete-impact.

Every write goes through :class:`CourseLifecycleService`, which holds the
rules the GUI and CLI course-management screens implement by hand: unique
course codes, both legacy and modern column families kept in step, a version
snapshot before an edit, a ``course.changed`` event, and a destructive delete
that reports its blast radius first.

Replaces an earlier version of this module that queried a ``course_id``
column the ``courses`` table does not have, and routed ``<int:course_id>``
against a TEXT uuid primary key - so none of it could ever match a row.
"""

from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify, request

from education_system.platform.delivery.api.kernel.idempotency import idempotent
from education_system.platform.delivery.api.university.pagination import (
    get_pagination_params,
    paginated_response,
)
from education_system.platform.delivery.api.university.auth import (
    authorize_object,
    token_required,
)
from education_system.systems.university.application.course_lifecycle_service import (
    CourseCommand,
    CourseImpactError,
    CourseLifecycleService,
    CourseValidationError,
)
from education_system.systems.university.infrastructure.activity_logger import log_activity

logger = logging.getLogger(__name__)

course_bp = Blueprint("courses", __name__, url_prefix="/api/courses")

#: Capability gate. Reads are open to any authenticated principal - the
#: catalogue is not confidential - while writes require course management.
_MANAGE = "manage_courses"


def _service() -> CourseLifecycleService:
    return CourseLifecycleService()


def _actor_id() -> str:
    user = g.current_user or {}
    return str(user.get("user_id") or user.get("sub") or "unknown")


def _deny_unless_manager():
    return authorize_object("staff-boundary", permission=_MANAGE)


def _validation_error(exc: CourseValidationError):
    return jsonify({"error": "Validation Error",
                    "errors": exc.errors, "status": 400}), 400


def _body() -> dict:
    return request.get_json(silent=True) or {}


@course_bp.route("", methods=["GET"])
@token_required
def list_courses():
    """The catalogue. ``?include_archived=true`` adds retired courses."""
    include = request.args.get("include_archived", "").lower() in ("1", "true", "yes")
    courses = _service().list(include_archived=include)
    search = (request.args.get("search") or "").strip().lower()
    department = (request.args.get("department") or "").strip().lower()
    if search:
        courses = [c for c in courses
                   if search in str(c.get("course_code") or c.get("code") or "").lower()
                   or search in str(c.get("course_name") or c.get("name") or "").lower()]
    if department:
        courses = [c for c in courses
                   if str(c.get("department") or "").lower() == department]

    # Paginated: 21 courses today, but an unbounded list endpoint is a
    # problem that only shows up once the catalogue is large. ``courses``
    # is kept alongside ``items`` so existing callers keep working.
    page, per_page, _ = get_pagination_params()
    total = len(courses)
    start = (page - 1) * per_page
    window = courses[start:start + per_page]
    body = paginated_response(window, total, page, per_page, key="items")
    body["courses"] = window
    body["count"] = total
    return jsonify(body)


@course_bp.route("/<course_ref>", methods=["GET"])
@token_required
def get_course(course_ref: str):
    """Fetch by uuid id or by course code - both resolve."""
    try:
        return jsonify(_service().get(course_ref))
    except CourseValidationError as exc:
        return jsonify({"error": "Not found", "errors": exc.errors,
                        "status": 404}), 404


@course_bp.route("", methods=["POST"])
@token_required
@idempotent
def create_course():
    denied = _deny_unless_manager()
    if denied is not None:
        return denied
    data = _body()
    try:
        result = _service().create(
            CourseCommand(
                course_code=data.get("course_code", ""),
                course_name=data.get("course_name", ""),
                credit_hours=data.get("credit_hours", 3),
                description=data.get("description", "") or "",
                level=data.get("level", "") or "",
                department=data.get("department", "") or "",
                max_enrollment=data.get("max_enrollment", 30),
                course_type=data.get("course_type", "Core") or "Core",
                course_fee=data.get("course_fee", 0.0) or 0.0,
                lab_required=bool(data.get("lab_required")),
                online_available=bool(data.get("online_available")),
                min_ucas_tariff=data.get("min_ucas_tariff", 0) or 0,
            ),
            actor_id=_actor_id(),
        )
    except CourseValidationError as exc:
        return _validation_error(exc)

    log_activity("create", "course", user=g.current_user.get("sub"))
    return jsonify({"course_id": result.course_id,
                    "course_code": result.course_code,
                    "status": result.status,
                    "message": f"Course {result.course_code} created."}), 201


@course_bp.route("/<course_ref>", methods=["PUT"])
@token_required
@idempotent
def update_course(course_ref: str):
    """Edit catalogue detail. ``reason`` is required and is versioned."""
    denied = _deny_unless_manager()
    if denied is not None:
        return denied
    data = _body()
    reason = str(data.get("reason") or "").strip()
    changes = {k: v for k, v in data.items() if k != "reason"}
    try:
        result = _service().update(course_ref, changes,
                                   actor_id=_actor_id(), reason=reason)
    except CourseValidationError as exc:
        return _validation_error(exc)

    log_activity("update", "course", user=g.current_user.get("sub"))
    return jsonify({"course_id": result.course_id,
                    "course_code": result.course_code,
                    "status": result.status,
                    "changed_fields": list(result.changed_fields)})


@course_bp.route("/<course_ref>/impact", methods=["GET"])
@token_required
def course_impact(course_ref: str):
    """Counts a destructive delete would affect. Read-only."""
    denied = _deny_unless_manager()
    if denied is not None:
        return denied
    try:
        return jsonify({"course": course_ref, "impact": _service().impact(course_ref)})
    except CourseValidationError as exc:
        return jsonify({"error": "Not found", "errors": exc.errors,
                        "status": 404}), 404


@course_bp.route("/<course_ref>/archive", methods=["POST"])
@token_required
@idempotent
def archive_course(course_ref: str):
    """Retire a course: it leaves the active catalogue, records survive."""
    denied = _deny_unless_manager()
    if denied is not None:
        return denied
    try:
        result = _service().archive(course_ref, actor_id=_actor_id(),
                                    reason=str(_body().get("reason") or ""))
    except CourseValidationError as exc:
        return _validation_error(exc)

    log_activity("archive", "course", user=g.current_user.get("sub"))
    return jsonify({"course_id": result.course_id,
                    "course_code": result.course_code,
                    "status": result.status,
                    "message": (f"Course {result.course_code} archived; it is no "
                                "longer offered for enrolment.")})


@course_bp.route("/<course_ref>/restore", methods=["POST"])
@token_required
@idempotent
def restore_course(course_ref: str):
    denied = _deny_unless_manager()
    if denied is not None:
        return denied
    try:
        result = _service().restore(course_ref, actor_id=_actor_id(),
                                    reason=str(_body().get("reason") or ""))
    except CourseValidationError as exc:
        return _validation_error(exc)

    log_activity("restore", "course", user=g.current_user.get("sub"))
    return jsonify({"course_id": result.course_id,
                    "course_code": result.course_code,
                    "status": result.status})


@course_bp.route("/<course_ref>", methods=["DELETE"])
@token_required
@idempotent
def delete_course(course_ref: str):
    """Destructive delete with the GUI/CLI cascade.

    Refused with 409 and the impact counts when students are enrolled or
    other courses depend on it, unless the body carries
    ``acknowledged_impact: true`` - the equivalent of the CLI's
    ``DELETE CONFIRMED`` prompt. Archive is the right call for a live course.
    """
    denied = _deny_unless_manager()
    if denied is not None:
        return denied
    data = _body()
    try:
        result = _service().delete(
            course_ref,
            actor_id=_actor_id(),
            reason=str(data.get("reason") or ""),
            acknowledged_impact=bool(data.get("acknowledged_impact")),
        )
    except CourseImpactError as exc:
        return jsonify({"error": "Impact not acknowledged", "message": str(exc),
                        "impact": exc.impact, "status": 409}), 409
    except CourseValidationError as exc:
        return _validation_error(exc)

    log_activity("delete", "course", user=g.current_user.get("sub"))
    return jsonify({"course_code": result.course_code,
                    "status": result.status,
                    "message": f"Course {result.course_code} and its related records were deleted."})
