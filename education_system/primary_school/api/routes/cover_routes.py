"""Cover API routes."""

from flask import Blueprint, jsonify, request

from education_system.primary_school.api.auth import token_required, role_required
from education_system.primary_school.api.validators import get_json_body, require_fields
from education_system.primary_school.api.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.staff.cover.services.cover_service import CoverService

cover_bp = Blueprint("cover", __name__, url_prefix="/api/cover")

_db_path = None


def init_cover_routes(db_path=None):
    global _db_path
    _db_path = db_path


@cover_bp.route("", methods=["GET"])
@token_required
def list_lessons():
    svc = CoverService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_lessons(date=request.args.get("date"))
    total = len(items)
    return jsonify(paginated_response(items, total))


@cover_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_lesson(pk):
    svc = CoverService(_db_path)
    item = svc.get_lesson(pk)
    if not item:
        return jsonify({"error": "Lesson not found."}), 404
    return jsonify({"data": dict(item) if hasattr(item, "keys") else item})


@cover_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_lesson():
    data = get_json_body()
    require_fields(data, "date", "period", "class_name", "cover_staff_id")
    svc = CoverService(_db_path)
    result = svc.create_lesson(**data)
    return jsonify({"message": "Lesson created.", "data": result}), 201


@cover_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def update_lesson(pk):
    data = get_json_body()
    svc = CoverService(_db_path)
    result = svc.update_lesson(pk, **data)
    return jsonify({"message": "Lesson updated.", "data": result})

@cover_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_lesson(pk):
    svc = CoverService(_db_path)
    svc.delete_lesson(pk)
    return jsonify({"message": "Lesson deleted."})