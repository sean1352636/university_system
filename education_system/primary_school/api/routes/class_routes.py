"""Classes API routes."""

from flask import Blueprint, jsonify, request

from education_system.primary_school.api.auth import token_required, role_required
from education_system.primary_school.api.validators import get_json_body, require_fields
from education_system.primary_school.api.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.academics.classes.services.class_service import ClassService

classes_bp = Blueprint("classes", __name__, url_prefix="/api/classes")

_db_path = None


def init_classes_routes(db_path=None):
    global _db_path
    _db_path = db_path


@classes_bp.route("", methods=["GET"])
@token_required
def list_classes():
    svc = ClassService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_classes(year_group=request.args.get("year_group"))
    total = len(items)
    return jsonify(paginated_response(items, total))


@classes_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_class_record(pk):
    svc = ClassService(_db_path)
    item = svc.get_class_record(pk)
    if not item:
        return jsonify({"error": "Class Record not found."}), 404
    return jsonify({"data": dict(item) if hasattr(item, "keys") else item})


@classes_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_class_record():
    data = get_json_body()
    require_fields(data, "name", "year_group")
    svc = ClassService(_db_path)
    result = svc.create_class_record(**data)
    return jsonify({"message": "Class Record created.", "data": result}), 201


@classes_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def update_class_record(pk):
    data = get_json_body()
    svc = ClassService(_db_path)
    result = svc.update_class_record(pk, **data)
    return jsonify({"message": "Class Record updated.", "data": result})

@classes_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_class_record(pk):
    svc = ClassService(_db_path)
    svc.delete_class_record(pk)
    return jsonify({"message": "Class Record deleted."})