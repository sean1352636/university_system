"""Seating Plans API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.facilities.seating_plans.services.seating_service import SeatingService

seating_plans_bp = Blueprint("seating_plans", __name__, url_prefix="/api/seating-plans")

_db_path = None


def init_seating_plans_routes(db_path=None):
    global _db_path
    _db_path = db_path


@seating_plans_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_plan():
    data = get_json_body()
    require_fields(data, "class_id", "room")
    svc = SeatingService(_db_path)
    result = svc.create_plan(class_id=data["class_id"], room=data["room"])
    return jsonify({"message": "Created.", "data": result}), 201


@seating_plans_bp.route("", methods=["GET"])
@token_required
def list_plans():
    svc = SeatingService(_db_path)
    result = svc.list_plans()
    return jsonify({"data": result})


@seating_plans_bp.route("/<int:plan_id>", methods=["DELETE"])
@token_required
@role_required("admin", "teacher")
def delete_plan(plan_id):
    svc = SeatingService(_db_path)
    result = svc.delete_plan(plan_id)
    return jsonify({"message": "Deleted.", "data": result})


@seating_plans_bp.route("/<int:plan_id>/assign", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def assign_seat(plan_id):
    data = get_json_body()
    require_fields(data, "student_id", "seat_label")
    svc = SeatingService(_db_path)
    result = svc.assign_seat(plan_id, data["student_id"], data["seat_label"])
    return jsonify({"message": "Created.", "data": result}), 201


@seating_plans_bp.route("/<int:plan_id>/assignments", methods=["GET"])
@token_required
def list_assignments(plan_id):
    svc = SeatingService(_db_path)
    result = svc.list_assignments(plan_id)
    return jsonify({"data": result})


@seating_plans_bp.route("/<int:plan_id>/seats/<int:student_id>", methods=["DELETE"])
@token_required
@role_required("admin", "teacher")
def remove_seat(plan_id, student_id):
    svc = SeatingService(_db_path)
    result = svc.remove_seat(plan_id, student_id)
    return jsonify({"message": "Deleted.", "data": result})

