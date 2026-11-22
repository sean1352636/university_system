"""Student mobility routes: exchange agreements, placements, learning
agreements and credit recognition."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from education_system.platform.delivery.api.university.auth import (
    current_subject_id,
    deny_unless_owner_or_staff,
    is_staff,
    scoped_to,
    staff_required,
    token_required,
)
from education_system.systems.university.domains.curriculum.domain.student_mobility._db_init import (
    DIRECTIONS,
    FUNDING_SCHEMES,
    LEARNING_AGREEMENT_STATES,
    MOBILITY_TYPES,
    PLACEMENT_STATUSES,
    RECOGNITION_MODES,
    RECOGNITION_STATES,
)
from education_system.systems.university.domains.curriculum.domain.student_mobility.services.student_mobility_service import (
    MobilityError,
    StudentMobilityService,
)
from education_system.systems.university.infrastructure.activity_logger import log_activity

logger = logging.getLogger(__name__)

student_mobility_bp = Blueprint("student_mobility", __name__,
                                url_prefix="/api/student-mobility")


#: Placements, learning agreements and credit recognition belong to one
#: student. Any staff role may read them; the student may read their own.
#: Changing them needs ``manage_placements`` (admin, staff) - the mobility
#: office, not instructors or learners. Agreements/availability are the
#: exchange catalogue and stay open to any signed-in user.
MOBILITY_MANAGE = "manage_placements"


def _service() -> StudentMobilityService:
    return StudentMobilityService()


def _placement_owner(placement_id: int):
    """The student a placement belongs to, or ``None`` if there is none."""
    placement = _service().get_placement(placement_id)
    return placement.get("student_id") if placement else None


def _payload() -> dict:
    return request.get_json(silent=True) or {}


def _pick(data: dict, keys) -> dict:
    return {k: data[k] for k in keys if k in data}


@student_mobility_bp.route("/vocabulary", methods=["GET"])
@token_required
def vocabulary():
    return jsonify({
        "directions": list(DIRECTIONS),
        "mobility_types": list(MOBILITY_TYPES),
        "funding_schemes": list(FUNDING_SCHEMES),
        "placement_statuses": list(PLACEMENT_STATUSES),
        "learning_agreement_states": list(LEARNING_AGREEMENT_STATES),
        "recognition_modes": list(RECOGNITION_MODES),
        "recognition_states": list(RECOGNITION_STATES),
    })


@student_mobility_bp.route("/summary", methods=["GET"])
@token_required
@staff_required
def summary():
    return jsonify(_service().summary(
        academic_year=request.args.get("academic_year")))


# ---- exchange agreements ----

@student_mobility_bp.route("/agreements", methods=["GET"])
@token_required
def list_agreements():
    items = _service().list_agreements(
        active_only=request.args.get("active", "1") != "0",
        country=request.args.get("country"),
        subject_area=request.args.get("subject_area"))
    return jsonify({"items": items, "total": len(items)})


@student_mobility_bp.route("/agreements", methods=["POST"])
@token_required
@staff_required(permission=MOBILITY_MANAGE)
def create_agreement():
    data = _payload()
    if not (data.get("host_institution") or "").strip():
        return jsonify({"error": "host_institution is required"}), 400
    try:
        agreement_id = _service().add_agreement(
            data["host_institution"],
            **_pick(data, ("partner_id", "country", "mobility_type",
                           "subject_area", "level", "places_outgoing",
                           "places_incoming", "language_of_tuition",
                           "language_requirement", "valid_from", "valid_to",
                           "coordinator", "notes")))
    except MobilityError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"mobility_agreement_id": agreement_id}), 201


@student_mobility_bp.route("/agreements/<int:agreement_id>", methods=["PATCH"])
@token_required
@staff_required(permission=MOBILITY_MANAGE)
def update_agreement(agreement_id: int):
    if not _service().update_agreement(agreement_id, **_payload()):
        return jsonify({"error": "no updatable fields supplied"}), 400
    return jsonify({"updated": True})


@student_mobility_bp.route("/agreements/availability", methods=["GET"])
@token_required
def availability():
    try:
        items = _service().place_availability(
            direction=request.args.get("direction", "outgoing"))
    except MobilityError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": items, "total": len(items)})


# ---- placements ----

@student_mobility_bp.route("/placements", methods=["GET"])
@token_required
def list_placements():
    # A learner sees only their own placements: pin the student filter to
    # the caller before any caller-supplied filter can widen it.
    student_id = request.args.get("student_id")
    if not is_staff():
        student_id = current_subject_id()
        if student_id is None:
            return jsonify({"error": "Forbidden", "status": 403}), 403
    items = _service().list_placements(
        direction=request.args.get("direction"),
        status=request.args.get("status"),
        student_id=student_id,
        academic_year=request.args.get("academic_year"),
        search=request.args.get("search"))
    return jsonify({"items": items, "total": len(items)})


@student_mobility_bp.route("/placements", methods=["POST"])
@token_required
@staff_required(permission=MOBILITY_MANAGE)
def create_placement():
    data = _payload()
    if not data.get("student_id"):
        return jsonify({"error": "student_id is required"}), 400
    try:
        placement_id = _service().create_placement(
            data["student_id"],
            **_pick(data, ("host_institution", "direction",
                           "mobility_agreement_id", "host_country",
                           "mobility_type", "funding_scheme", "grant_amount",
                           "academic_year", "start_date", "end_date",
                           "home_programme", "host_programme",
                           "credits_expected", "recognition_mode",
                           "coordinator", "notes")))
    except MobilityError as exc:
        return jsonify({"error": str(exc)}), 400
    log_activity("mobility_placement_created", entity_type="mobility_placement",
                 placement_id=placement_id, student_id=data["student_id"])
    return jsonify({"placement_id": placement_id}), 201


@student_mobility_bp.route("/placements/<int:placement_id>", methods=["GET"])
@token_required
def get_placement(placement_id: int):
    placement = _service().get_placement(placement_id)
    if placement is None:
        return jsonify({"error": "not found"}), 404
    denial = deny_unless_owner_or_staff(placement.get("student_id"))
    if denial is not None:
        return denial
    return jsonify(placement)


@student_mobility_bp.route("/placements/<int:placement_id>", methods=["PATCH"])
@token_required
@staff_required(permission=MOBILITY_MANAGE)
def update_placement(placement_id: int):
    if not _service().update_placement(placement_id, **_payload()):
        return jsonify({"error": "no updatable fields supplied"}), 400
    return jsonify({"updated": True})


@student_mobility_bp.route("/placements/<int:placement_id>/status",
                           methods=["POST"])
@token_required
@staff_required(permission=MOBILITY_MANAGE)
def set_placement_status(placement_id: int):
    data = _payload()
    if not data.get("status"):
        return jsonify({"error": "status is required"}), 400
    try:
        # The actor is whoever signed in, never a name from the body.
        placement = _service().set_status(placement_id, data["status"],
                                          actor=current_subject_id())
    except MobilityError as exc:
        # Includes the "credit not recognised yet" completion guard, which
        # is a 409 rather than a 400 — the request is well-formed, the
        # record just is not ready.
        return jsonify({"error": str(exc)}), 409
    return jsonify(placement)


@student_mobility_bp.route("/placements/currently-away", methods=["GET"])
@token_required
@staff_required
def currently_away():
    items = _service().currently_away(as_of=request.args.get("as_of"))
    return jsonify({"items": items, "total": len(items)})


@student_mobility_bp.route("/students/<student_id>/history", methods=["GET"])
@token_required
@scoped_to("student_id")
def student_history(student_id: str):
    items = _service().student_history(student_id)
    return jsonify({"items": items, "total": len(items)})


# ---- learning agreements ----

@student_mobility_bp.route("/placements/<int:placement_id>/learning-agreement",
                           methods=["GET"])
@token_required
def learning_agreement(placement_id: int):
    denial = deny_unless_owner_or_staff(_placement_owner(placement_id))
    if denial is not None:
        return denial
    items = _service().list_learning_agreement(placement_id)
    return jsonify({"items": items, "total": len(items)})


@student_mobility_bp.route("/placements/<int:placement_id>/learning-agreement",
                           methods=["POST"])
@token_required
@staff_required(permission=MOBILITY_MANAGE)
def add_learning_agreement_line(placement_id: int):
    data = _payload()
    if not (data.get("host_module_title") or "").strip():
        return jsonify({"error": "host_module_title is required"}), 400
    try:
        line_id = _service().add_learning_agreement_line(
            placement_id, data["host_module_title"],
            **_pick(data, ("host_module_code", "host_credits",
                           "host_credit_system", "home_module_code",
                           "home_module_title", "home_credits", "state",
                           "notes")))
    except MobilityError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"line_id": line_id}), 201


@student_mobility_bp.route(
    "/placements/<int:placement_id>/learning-agreement/sign", methods=["POST"])
@token_required
@staff_required(permission=MOBILITY_MANAGE)
def sign_learning_agreement(placement_id: int):
    data = _payload()
    signed = _service().sign_learning_agreement(
        placement_id, approved_by_home=data.get("approved_by_home"),
        approved_by_host=data.get("approved_by_host"))
    return jsonify({"lines_signed": signed})


@student_mobility_bp.route("/monitoring/unsigned-learning-agreements",
                           methods=["GET"])
@token_required
@staff_required
def unsigned_learning_agreements():
    items = _service().unsigned_learning_agreements()
    return jsonify({"items": items, "total": len(items)})


# ---- credit recognition ----

@student_mobility_bp.route("/placements/<int:placement_id>/recognitions",
                           methods=["GET"])
@token_required
def list_recognitions(placement_id: int):
    denial = deny_unless_owner_or_staff(_placement_owner(placement_id))
    if denial is not None:
        return denial
    items = _service().list_recognitions(placement_id)
    return jsonify({"items": items, "total": len(items),
                    "shortfall": _service().credit_shortfall(placement_id)})


@student_mobility_bp.route("/placements/<int:placement_id>/recognitions",
                           methods=["POST"])
@token_required
@staff_required(permission=MOBILITY_MANAGE)
def record_recognition(placement_id: int):
    data = _payload()
    try:
        recognition_id = _service().record_recognition(
            placement_id,
            **_pick(data, ("line_id", "host_module_code", "host_grade",
                           "host_credits", "home_module_code", "home_credits",
                           "converted_mark", "mode", "outcome",
                           "recognised_by", "notes")))
    except MobilityError as exc:
        return jsonify({"error": str(exc)}), 400
    log_activity("mobility_credit_recognised", entity_type="mobility_placement",
                 placement_id=placement_id)
    return jsonify({"recognition_id": recognition_id}), 201


@student_mobility_bp.route("/monitoring/awaiting-recognition", methods=["GET"])
@token_required
@staff_required
def awaiting_recognition():
    items = _service().awaiting_recognition(
        older_than_days=request.args.get("older_than_days", default=60, type=int))
    return jsonify({"items": items, "total": len(items)})


@student_mobility_bp.route("/monitoring/preparation-gaps", methods=["GET"])
@token_required
@staff_required
def preparation_gaps():
    items = _service().preparation_gaps()
    return jsonify({"items": items, "total": len(items)})
