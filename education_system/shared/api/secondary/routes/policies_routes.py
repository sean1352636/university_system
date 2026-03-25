"""Policies API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.admin.policies.services.policy_service import PolicyService

policies_bp = Blueprint("policies", __name__, url_prefix="/api/policies")

_db_path = None


def init_policies_routes(db_path=None):
    global _db_path
    _db_path = db_path


@policies_bp.route("", methods=["POST"])
@token_required
@role_required("admin")
def add_policy():
    data = get_json_body()
    require_fields(data, "title", "category")
    svc = PolicyService(_db_path)
    result = svc.add_policy(title=data["title"], category=data["category"], content=data.get("content", ""), version=data.get("version", "1.0"))
    return jsonify({"message": "Created.", "data": result}), 201


@policies_bp.route("", methods=["GET"])
@token_required
def list_policies():
    svc = PolicyService(_db_path)
    result = svc.list_policies()
    return jsonify({"data": result})


@policies_bp.route("/<int:policy_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_policy(policy_id):
    svc = PolicyService(_db_path)
    result = svc.delete_policy(policy_id)
    return jsonify({"message": "Deleted.", "data": result})


@policies_bp.route("/<int:policy_id>/acknowledge", methods=["POST"])
@token_required
def acknowledge(policy_id):
    data = get_json_body()
    require_fields(data, "user_id")
    svc = PolicyService(_db_path)
    result = svc.acknowledge(policy_id, data["user_id"])
    return jsonify({"message": "Created.", "data": result}), 201


@policies_bp.route("/<int:policy_id>/acknowledgements", methods=["GET"])
@token_required
@role_required("admin")
def list_acknowledgements(policy_id):
    svc = PolicyService(_db_path)
    result = svc.list_acknowledgements(policy_id)
    return jsonify({"data": result})

