"""Policies API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.primary.auth import token_required, role_required
from education_system.shared.api.primary.validators import get_json_body, require_fields
from education_system.shared.api.primary.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.admin.policies.services.policy_service import PolicyService

policies_bp = Blueprint("policies", __name__, url_prefix="/api/policies")

_db_path = None


def init_policies_routes(db_path=None):
    global _db_path
    _db_path = db_path


@policies_bp.route("", methods=["GET"])
@token_required
def list_policies():
    svc = PolicyService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_policies()
    total = len(items)
    return jsonify(paginated_response(items, total))


@policies_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_policy(pk):
    svc = PolicyService(_db_path)
    item = svc.get_policy(pk)
    if not item:
        return jsonify({"error": "Policy not found."}), 404
    return jsonify({"data": dict(item) if hasattr(item, "keys") else item})


@policies_bp.route("", methods=["POST"])
@token_required
@role_required("admin")
def create_policy():
    data = get_json_body()
    require_fields(data, "title", "content")
    svc = PolicyService(_db_path)
    result = svc.create_policy(**data)
    return jsonify({"message": "Policy created.", "data": result}), 201


@policies_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin")
def update_policy(pk):
    data = get_json_body()
    svc = PolicyService(_db_path)
    result = svc.update_policy(pk, **data)
    return jsonify({"message": "Policy updated.", "data": result})

@policies_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_policy(pk):
    svc = PolicyService(_db_path)
    svc.delete_policy(pk)
    return jsonify({"message": "Policy deleted."})