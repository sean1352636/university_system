"""Class Groups API routes."""

from flask import Blueprint, jsonify, request

from education_system.primary_school.api.auth import token_required, role_required
from education_system.primary_school.api.validators import get_json_body, require_fields
from education_system.primary_school.api.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.pupil_life.class_groups.services.class_group_service import ClassGroupService

class_groups_bp = Blueprint("class_groups", __name__, url_prefix="/api/class-groups")

_db_path = None


def init_class_groups_routes(db_path=None):
    global _db_path
    _db_path = db_path


@class_groups_bp.route("", methods=["GET"])
@token_required
def list_groups():
    svc = ClassGroupService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_groups(year_group=request.args.get("year_group"))
    total = len(items)
    return jsonify(paginated_response(items, total))


@class_groups_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_group(pk):
    svc = ClassGroupService(_db_path)
    item = svc.get_group(pk)
    if not item:
        return jsonify({"error": "Group not found."}), 404
    return jsonify({"data": dict(item) if hasattr(item, "keys") else item})


@class_groups_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_group():
    data = get_json_body()
    require_fields(data, "name", "year_group")
    svc = ClassGroupService(_db_path)
    result = svc.create_group(**data)
    return jsonify({"message": "Group created.", "data": result}), 201


@class_groups_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def update_group(pk):
    data = get_json_body()
    svc = ClassGroupService(_db_path)
    result = svc.update_group(pk, **data)
    return jsonify({"message": "Group updated.", "data": result})

@class_groups_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_group(pk):
    svc = ClassGroupService(_db_path)
    svc.delete_group(pk)
    return jsonify({"message": "Group deleted."})