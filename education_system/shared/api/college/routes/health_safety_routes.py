"""API routes for health safety."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.health_safety.services.health_safety_service import HealthSafetyService
from education_system.college_system.core.i18n import t

health_safety_bp = Blueprint("health-safety", __name__, url_prefix="/api/health-safety")

_db_path = None


def init_health_safety_routes(db_path=None):
    global _db_path
    _db_path = db_path


@health_safety_bp.route("/incidents", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_incidents():
    svc = HealthSafetyService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_incidents(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@health_safety_bp.route("/incidents/<int:pk>", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_incident(pk):
    svc = HealthSafetyService(_db_path)
    item = svc.get_incident(pk)
    if not item:
        return jsonify({"error": t("api.health_safety.not_found")}), 404
    return jsonify({"data": item})
@health_safety_bp.route("/incidents", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_incident():
    data = get_json_body()
    svc = HealthSafetyService(_db_path)
    result = svc.create_incident(**data)
    return jsonify({"message": t("api.health_safety.created"), "data": result}), 201
@health_safety_bp.route("/incidents/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin', 'staff')
def update_incident(pk):
    data = get_json_body()
    svc = HealthSafetyService(_db_path)
    result = svc.update_incident(pk, **data)
    return jsonify({"message": t("api.health_safety.updated"), "data": result})
@health_safety_bp.route("/inspections", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_inspections():
    svc = HealthSafetyService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_inspections(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@health_safety_bp.route("/inspections", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_inspection():
    data = get_json_body()
    svc = HealthSafetyService(_db_path)
    result = svc.create_inspection(**data)
    return jsonify({"message": t("api.health_safety.created"), "data": result}), 201
@health_safety_bp.route("/risk-assessments", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_risk_assessments():
    svc = HealthSafetyService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_risk_assessments(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@health_safety_bp.route("/risk-assessments", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_risk_assessment():
    data = get_json_body()
    svc = HealthSafetyService(_db_path)
    result = svc.create_risk_assessment(**data)
    return jsonify({"message": t("api.health_safety.created"), "data": result}), 201
@health_safety_bp.route("/stats", methods=["GET"])
@token_required
@role_required('admin')
def get_stats():
    svc = HealthSafetyService(_db_path)
    result = svc.get_stats()
    return jsonify({"data": result})
