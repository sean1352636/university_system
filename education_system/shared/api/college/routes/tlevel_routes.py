"""API routes for tlevel."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.tlevel.services.tlevel_service import TLevelService
from education_system.college_system.core.i18n import t

tlevel_bp = Blueprint("tlevel", __name__, url_prefix="/api/tlevel")

_db_path = None


def init_tlevel_routes(db_path=None):
    global _db_path
    _db_path = db_path


@tlevel_bp.route("/routes", methods=["GET"])
@token_required
def list_routes():
    svc = TLevelService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_routes(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@tlevel_bp.route("/routes", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_route():
    data = get_json_body()
    svc = TLevelService(_db_path)
    result = svc.create_route(**data)
    return jsonify({"message": t("api.tlevel.created"), "data": result}), 201
@tlevel_bp.route("/enrollments", methods=["GET"])
@token_required
def list_enrollments():
    svc = TLevelService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_enrollments(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@tlevel_bp.route("/enrollments/<int:pk>", methods=["GET"])
@token_required
def get_enrollment(pk):
    svc = TLevelService(_db_path)
    item = svc.get_enrollment(pk)
    if not item:
        return jsonify({"error": t("api.tlevel.not_found")}), 404
    return jsonify({"data": item})
@tlevel_bp.route("/enrollments", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def enroll_student():
    data = get_json_body()
    svc = TLevelService(_db_path)
    result = svc.enroll_student(**data)
    return jsonify({"message": t("api.tlevel.created"), "data": result}), 201
@tlevel_bp.route("/enrollments/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin', 'staff')
def update_enrollment(pk):
    data = get_json_body()
    svc = TLevelService(_db_path)
    result = svc.update_enrollment(pk, **data)
    return jsonify({"message": t("api.tlevel.updated"), "data": result})
@tlevel_bp.route("/placement", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def log_placement():
    data = get_json_body()
    svc = TLevelService(_db_path)
    result = svc.log_placement(**data)
    return jsonify({"message": t("api.tlevel.created"), "data": result}), 201
@tlevel_bp.route("/placement", methods=["GET"])
@token_required
def list_placement_logs():
    svc = TLevelService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_placement_logs(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
