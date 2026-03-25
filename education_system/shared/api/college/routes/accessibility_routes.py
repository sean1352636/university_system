"""API routes for accessibility."""

from flask import Blueprint, jsonify, request
from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.accessibility.services.accessibility_service import AccessibilityService
from education_system.college_system.core.i18n import t

accessibility_bp = Blueprint("accessibility", __name__, url_prefix="/api/accessibility")

_db_path = None


def init_accessibility_routes(db_path=None):
    global _db_path
    _db_path = db_path


@accessibility_bp.route("", methods=["GET"])
@token_required
def list_preferences():
    svc = AccessibilityService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_preferences(limit=limit, offset=offset)
    total = svc.count_preferences()
    return jsonify(paginated_response(items, total))


@accessibility_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_preference(pk):
    svc = AccessibilityService(_db_path)
    item = svc.get_preference(pk)
    if not item:
        return jsonify({"error": t("api.common.not_found")}), 404
    return jsonify({"data": item})


@accessibility_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff", "instructor")
def create_preference():
    data = get_json_body()
    require_fields(data, "user_id")
    svc = AccessibilityService(_db_path)
    item = svc.create_preference(**data)
    return jsonify({"message": t("api.common.created"), "data": item}), 201


@accessibility_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff", "instructor")
def update_preference(pk):
    data = get_json_body()
    svc = AccessibilityService(_db_path)
    item = svc.update_preference(pk, **data)
    return jsonify({"message": t("api.common.updated"), "data": item})


@accessibility_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_preference(pk):
    svc = AccessibilityService(_db_path)
    svc.delete_preference(pk)
    return jsonify({"message": t("api.common.deleted")})
