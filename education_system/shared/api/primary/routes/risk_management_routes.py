"""Risk management API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.primary.auth import token_required, role_required
from education_system.shared.api.primary.validators import get_json_body, require_fields
from education_system.shared.api.primary.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.admin.risk_management.services.risk_management_service import RiskManagementService

risk_management_bp = Blueprint("risk-management", __name__, url_prefix="/api/risk-management")

_db_path = None


def init_risk_management_routes(db_path=None):
    global _db_path
    _db_path = db_path


@risk_management_bp.route("", methods=["GET"])
@token_required
def list_risk_management():
    svc = RiskManagementService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_all(limit=limit, offset=offset)
    total = len(items)
    return jsonify(paginated_response(items, total))


@risk_management_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_risk_management_item(pk):
    svc = RiskManagementService(_db_path)
    item = svc.get(pk)
    if not item:
        return jsonify({"error": "Not found."}), 404
    return jsonify({"data": item})


@risk_management_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_risk_management_item():
    data = get_json_body()
    svc = RiskManagementService(_db_path)
    result = svc.create(**data)
    return jsonify({"message": "Created.", "data": result}), 201


@risk_management_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_risk_management_item(pk):
    data = get_json_body()
    svc = RiskManagementService(_db_path)
    result = svc.update(pk, **data)
    return jsonify({"message": "Updated.", "data": result})


@risk_management_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_risk_management_item(pk):
    svc = RiskManagementService(_db_path)
    svc.delete(pk)
    return jsonify({"message": "Deleted."})
