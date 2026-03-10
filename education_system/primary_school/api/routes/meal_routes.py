"""Meals API routes."""

from flask import Blueprint, jsonify, request

from education_system.primary_school.api.auth import token_required, role_required
from education_system.primary_school.api.validators import get_json_body, require_fields
from education_system.primary_school.api.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.pupil_life.meals.services.meal_service import MealService

meals_bp = Blueprint("meals", __name__, url_prefix="/api/meals")

_db_path = None


def init_meals_routes(db_path=None):
    global _db_path
    _db_path = db_path


@meals_bp.route("", methods=["GET"])
@token_required
def list_records():
    svc = MealService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_records(pupil_id=request.args.get("pupil_id"))
    total = len(items)
    return jsonify(paginated_response(items, total))


@meals_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_record(pk):
    svc = MealService(_db_path)
    item = svc.get_record(pk)
    if not item:
        return jsonify({"error": "Record not found."}), 404
    return jsonify({"data": dict(item) if hasattr(item, "keys") else item})


@meals_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_record():
    data = get_json_body()
    require_fields(data, "pupil_id", "meal_type", "date")
    svc = MealService(_db_path)
    result = svc.create_record(**data)
    return jsonify({"message": "Record created.", "data": result}), 201


@meals_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def update_record(pk):
    data = get_json_body()
    svc = MealService(_db_path)
    result = svc.update_record(pk, **data)
    return jsonify({"message": "Record updated.", "data": result})

@meals_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_record(pk):
    svc = MealService(_db_path)
    svc.delete_record(pk)
    return jsonify({"message": "Record deleted."})