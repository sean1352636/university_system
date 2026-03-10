"""Admissions API routes."""

from flask import Blueprint, jsonify, request

from education_system.primary_school.api.auth import token_required, role_required
from education_system.primary_school.api.validators import get_json_body, require_fields
from education_system.primary_school.api.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.admin.admissions.services.admissions_service import AdmissionsService

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
    items = svc.list_applications()
    total = len(items)
    return jsonify(paginated_response(items, total))


@admissions_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_application(pk):
    svc = AdmissionsService(_db_path)
    item = svc.get_application(pk)
    if not item:
        return jsonify({"error": "Application not found."}), 404
    return jsonify({"data": dict(item) if hasattr(item, "keys") else item})


@admissions_bp.route("", methods=["POST"])
@token_required
@role_required("admin")
def create_application():
    data = get_json_body()
    require_fields(data, "first_name", "last_name")
    svc = AdmissionsService(_db_path)
    result = svc.create_application(**data)
    return jsonify({"message": "Application created.", "data": result}), 201


@admissions_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin")
def update_application(pk):
    data = get_json_body()
    svc = AdmissionsService(_db_path)
    result = svc.update_application(pk, **data)
    return jsonify({"message": "Application updated.", "data": result})

@admissions_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_application(pk):
    svc = AdmissionsService(_db_path)
    svc.delete_application(pk)
    return jsonify({"message": "Application deleted."})