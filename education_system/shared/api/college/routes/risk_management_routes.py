"""API routes for risk management."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.risk_management.services.risk_management_service import RiskManagementService
from education_system.college_system.core.i18n import t

risk_management_bp = Blueprint("risk-management", __name__, url_prefix="/api/risk-management")

_db_path = None


def init_risk_management_routes(db_path=None):
    global _db_path
    _db_path = db_path


@risk_management_bp.route("", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_risks():
    svc = RiskManagementService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_risks(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@risk_management_bp.route("/<int:pk>", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_risk(pk):
    svc = RiskManagementService(_db_path)
    item = svc.get_risk(pk)
    if not item:
        return jsonify({"error": t("api.risk_management.not_found")}), 404
    return jsonify({"data": item})
@risk_management_bp.route("", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_risk():
    data = get_json_body()
    svc = RiskManagementService(_db_path)
    result = svc.create_risk(**data)
    return jsonify({"message": t("api.risk_management.created"), "data": result}), 201
@risk_management_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin', 'staff')
def update_risk(pk):
    data = get_json_body()
    svc = RiskManagementService(_db_path)
    result = svc.update_risk(pk, **data)
    return jsonify({"message": t("api.risk_management.updated"), "data": result})
@risk_management_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required('admin')
def delete_risk(pk):
    svc = RiskManagementService(_db_path)
    svc.delete_risk(pk)
    return jsonify({"message": t("api.risk_management.deleted")})
@risk_management_bp.route("/reviews", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_reviews():
    svc = RiskManagementService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_reviews(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@risk_management_bp.route("/reviews", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_review():
    data = get_json_body()
    svc = RiskManagementService(_db_path)
    result = svc.create_review(**data)
    return jsonify({"message": t("api.risk_management.created"), "data": result}), 201
@risk_management_bp.route("/stats", methods=["GET"])
@token_required
@role_required('admin')
def get_stats():
    svc = RiskManagementService(_db_path)
    result = svc.get_stats()
    return jsonify({"data": result})
