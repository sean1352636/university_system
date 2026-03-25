"""API routes for compliance."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.compliance.services.compliance_service import ComplianceService
from education_system.college_system.core.i18n import t

compliance_bp = Blueprint("compliance", __name__, url_prefix="/api/compliance")

_db_path = None


def init_compliance_routes(db_path=None):
    global _db_path
    _db_path = db_path


@compliance_bp.route("/funding", methods=["GET"])
@token_required
def list_funding_records():
    svc = ComplianceService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_funding_records(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@compliance_bp.route("/funding", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_funding_record():
    data = get_json_body()
    svc = ComplianceService(_db_path)
    result = svc.create_funding_record(**data)
    return jsonify({"message": t("api.compliance.created"), "data": result}), 201
@compliance_bp.route("/funding/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin', 'staff')
def update_funding_record(pk):
    data = get_json_body()
    svc = ComplianceService(_db_path)
    result = svc.update_funding_record(pk, **data)
    return jsonify({"message": t("api.compliance.updated"), "data": result})
@compliance_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required('admin')
def delete_record(pk):
    svc = ComplianceService(_db_path)
    svc.delete_record(pk)
    return jsonify({"message": t("api.compliance.deleted")})
@compliance_bp.route("/resits", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_resits():
    svc = ComplianceService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_resits(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@compliance_bp.route("/resits", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_resit():
    data = get_json_body()
    svc = ComplianceService(_db_path)
    result = svc.create_resit(**data)
    return jsonify({"message": t("api.compliance.created"), "data": result}), 201
@compliance_bp.route("/destinations", methods=["GET"])
@token_required
def list_destinations():
    svc = ComplianceService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_destinations(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@compliance_bp.route("/destinations", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_destination():
    data = get_json_body()
    svc = ComplianceService(_db_path)
    result = svc.create_destination(**data)
    return jsonify({"message": t("api.compliance.created"), "data": result}), 201
