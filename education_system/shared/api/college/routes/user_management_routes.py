"""API routes for user management."""

from flask import Blueprint, jsonify, request
from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.user_management.services.user_management_service import UserManagementService
from education_system.college_system.core.i18n import t

user_management_bp = Blueprint("user-management", __name__, url_prefix="/api/user-management")

_db_path = None


def init_user_management_routes(db_path=None):
    global _db_path
    _db_path = db_path


@user_management_bp.route("", methods=["GET"])
@token_required
def list_templates():
    svc = UserManagementService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_templates(limit=limit, offset=offset)
    total = svc.count_templates()
    return jsonify(paginated_response(items, total))


@user_management_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_template(pk):
    svc = UserManagementService(_db_path)
    item = svc.get_template(pk)
    if not item:
        return jsonify({"error": t("api.user_management.not_found")}), 404
    return jsonify({"data": item})


@user_management_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_template():
    data = get_json_body()
    require_fields(data, "template_name", "role")
    svc = UserManagementService(_db_path)
    item = svc.create_template(**data)
    return jsonify({"message": t("api.user_management.created"), "data": item}), 201


@user_management_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_template(pk):
    data = get_json_body()
    svc = UserManagementService(_db_path)
    item = svc.update_template(pk, **data)
    return jsonify({"message": t("api.user_management.updated"), "data": item})


@user_management_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_template(pk):
    svc = UserManagementService(_db_path)
    svc.delete_template(pk)
    return jsonify({"message": t("api.user_management.deleted")})
