"""API routes for admissions."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.admissions.services.admissions_service import AdmissionsService
from education_system.college_system.core.i18n import t

admissions_bp = Blueprint("admissions", __name__, url_prefix="/api/admissions")

_db_path = None


def init_admissions_routes(db_path=None):
    global _db_path
    _db_path = db_path


@admissions_bp.route("", methods=["GET"])
@token_required
def list_applications():
    svc = AdmissionsService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_applications(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@admissions_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_application(pk):
    svc = AdmissionsService(_db_path)
    item = svc.get_application(pk)
    if not item:
        return jsonify({"error": t("api.admissions.not_found")}), 404
    return jsonify({"data": item})
@admissions_bp.route("", methods=["POST"])
@token_required
def create_application():
    data = get_json_body()
    svc = AdmissionsService(_db_path)
    result = svc.create_application(**data)
    return jsonify({"message": t("api.admissions.created"), "data": result}), 201
@admissions_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin', 'staff')
def update_application(pk):
    data = get_json_body()
    svc = AdmissionsService(_db_path)
    result = svc.update_application(pk, **data)
    return jsonify({"message": t("api.admissions.updated"), "data": result})
@admissions_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required('admin')
def delete_application(pk):
    svc = AdmissionsService(_db_path)
    svc.delete_application(pk)
    return jsonify({"message": t("api.admissions.deleted")})
@admissions_bp.route("/inductions", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_inductions():
    svc = AdmissionsService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_inductions(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@admissions_bp.route("/inductions", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_induction():
    data = get_json_body()
    svc = AdmissionsService(_db_path)
    result = svc.create_induction(**data)
    return jsonify({"message": t("api.admissions.created"), "data": result}), 201
