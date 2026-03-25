"""Homework API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.primary.auth import token_required, role_required
from education_system.shared.api.primary.validators import get_json_body, require_fields
from education_system.shared.api.primary.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.academics.homework.services.homework_service import HomeworkService

homework_bp = Blueprint("homework", __name__, url_prefix="/api/homework")

_db_path = None


def init_homework_routes(db_path=None):
    global _db_path
    _db_path = db_path


@homework_bp.route("", methods=["GET"])
@token_required
def list_homework():
    svc = HomeworkService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_homework(class_name=request.args.get("class_name"))
    total = len(items)
    return jsonify(paginated_response(items, total))


@homework_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_homework(pk):
    svc = HomeworkService(_db_path)
    item = svc.get_homework(pk)
    if not item:
        return jsonify({"error": "Homework not found."}), 404
    return jsonify({"data": dict(item) if hasattr(item, "keys") else item})


@homework_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_homework():
    data = get_json_body()
    require_fields(data, "title", "class_name", "subject_code", "due_date")
    svc = HomeworkService(_db_path)
    result = svc.create_homework(**data)
    return jsonify({"message": "Homework created.", "data": result}), 201


@homework_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def update_homework(pk):
    data = get_json_body()
    svc = HomeworkService(_db_path)
    result = svc.update_homework(pk, **data)
    return jsonify({"message": "Homework updated.", "data": result})

@homework_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_homework(pk):
    svc = HomeworkService(_db_path)
    svc.delete_homework(pk)
    return jsonify({"message": "Homework deleted."})