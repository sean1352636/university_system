"""API routes for apprenticeships."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.apprenticeships.services.apprenticeships_service import ApprenticeshipService
from education_system.college_system.core.i18n import t

apprenticeships_bp = Blueprint("apprenticeships", __name__, url_prefix="/api/apprenticeships")

_db_path = None


def init_apprenticeships_routes(db_path=None):
    global _db_path
    _db_path = db_path


@apprenticeships_bp.route("/standards", methods=["GET"])
@token_required
def list_standards():
    svc = ApprenticeshipService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_standards(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@apprenticeships_bp.route("/standards", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_standard():
    data = get_json_body()
    svc = ApprenticeshipService(_db_path)
    result = svc.create_standard(**data)
    return jsonify({"message": t("api.apprenticeships.created"), "data": result}), 201
@apprenticeships_bp.route("/enrollments", methods=["GET"])
@token_required
def list_enrollments():
    svc = ApprenticeshipService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_enrollments(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@apprenticeships_bp.route("/enrollments/<int:pk>", methods=["GET"])
@token_required
def get_enrollment(pk):
    svc = ApprenticeshipService(_db_path)
    item = svc.get_enrollment(pk)
    if not item:
        return jsonify({"error": t("api.apprenticeships.not_found")}), 404
    return jsonify({"data": item})
@apprenticeships_bp.route("/enrollments", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def enroll():
    data = get_json_body()
    svc = ApprenticeshipService(_db_path)
    result = svc.enroll(**data)
    return jsonify({"message": t("api.apprenticeships.created"), "data": result}), 201
@apprenticeships_bp.route("/enrollments/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin', 'staff')
def update_enrollment(pk):
    data = get_json_body()
    svc = ApprenticeshipService(_db_path)
    result = svc.update_enrollment(pk, **data)
    return jsonify({"message": t("api.apprenticeships.updated"), "data": result})
@apprenticeships_bp.route("/otj", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def log_otj():
    data = get_json_body()
    svc = ApprenticeshipService(_db_path)
    result = svc.log_otj(**data)
    return jsonify({"message": t("api.apprenticeships.created"), "data": result}), 201
@apprenticeships_bp.route("/otj", methods=["GET"])
@token_required
def list_otj_logs():
    svc = ApprenticeshipService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_otj_logs(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
