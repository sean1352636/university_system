"""Meals API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.student_life.meals.services.meals_service import MealsService

meals_bp = Blueprint("meals", __name__, url_prefix="/api/meals")

_db_path = None


def init_meals_routes(db_path=None):
    global _db_path
    _db_path = db_path


@meals_bp.route("/register", methods=["POST"])
@token_required
def register_student():
    data = get_json_body()
    require_fields(data, "student_id", "meal_type")
    svc = MealsService(_db_path)
    result = svc.register_student(data["student_id"], data["meal_type"], data.get("dietary_requirements", ""))
    return jsonify({"message": "Created.", "data": result}), 201


@meals_bp.route("/registrations", methods=["GET"])
@token_required
def list_registrations():
    svc = MealsService(_db_path)
    result = svc.list_registrations()
    return jsonify({"data": result})


@meals_bp.route("/registrations/<int:reg_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_registration(reg_id):
    svc = MealsService(_db_path)
    result = svc.delete_registration(reg_id)
    return jsonify({"message": "Deleted.", "data": result})


@meals_bp.route("/bookings", methods=["POST"])
@token_required
def book_meal():
    data = get_json_body()
    require_fields(data, "student_id", "date", "meal_choice")
    svc = MealsService(_db_path)
    result = svc.book_meal(data["student_id"], data["date"], data["meal_choice"])
    return jsonify({"message": "Created.", "data": result}), 201


@meals_bp.route("/bookings", methods=["GET"])
@token_required
def list_bookings():
    svc = MealsService(_db_path)
    result = svc.list_bookings()
    return jsonify({"data": result})


@meals_bp.route("/bookings/<int:booking_id>", methods=["DELETE"])
@token_required
def cancel_booking(booking_id):
    svc = MealsService(_db_path)
    result = svc.cancel_booking(booking_id)
    return jsonify({"message": "Deleted.", "data": result})


@meals_bp.route("/fsm-count", methods=["GET"])
@token_required
@role_required("admin")
def fsm_count():
    svc = MealsService(_db_path)
    result = svc.fsm_count()
    return jsonify({"data": result})

