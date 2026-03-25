"""API routes for policies."""

from flask import Blueprint, jsonify, request
from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.policies.services.policies_service import PolicyService
from education_system.college_system.core.i18n import t

policy_bp = Blueprint("policies", __name__, url_prefix="/api/policies")

_db_path = None


def init_policy_routes(db_path=None):
    global _db_path
    _db_path = db_path


@policy_bp.route("", methods=["GET"])
@token_required
def list_policies():
    svc = PolicyService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_policies(limit=limit, offset=offset)
    total = svc.count_policies()
    return jsonify(paginated_response(items, total))


@policy_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_policy(pk):
    svc = PolicyService(_db_path)
    item = svc.get_policy(pk)
    if not item:
        return jsonify({"error": t("api.policies.not_found")}), 404
    return jsonify({"data": item})


@policy_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_policy():
    data = get_json_body()
    require_fields(data, "title", "category")
    svc = PolicyService(_db_path)
    item = svc.create_policy(**data)
    return jsonify({"message": t("api.policies.created"), "data": item}), 201


@policy_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_policy(pk):
    data = get_json_body()
    svc = PolicyService(_db_path)
    item = svc.update_policy(pk, **data)
    return jsonify({"message": t("api.policies.updated"), "data": item})


@policy_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_policy(pk):
    svc = PolicyService(_db_path)
    svc.delete_policy(pk)
    return jsonify({"message": t("api.policies.deleted")})
