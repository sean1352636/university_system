"""Admissions API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.admin.admissions.services.admissions_service import AdmissionsService

admissions_bp = Blueprint("admissions", __name__, url_prefix="/api/admissions")

_db_path = None


def init_admissions_routes(db_path=None):
    global _db_path
    _db_path = db_path


@admissions_bp.route("", methods=["POST"])
@token_required
@role_required("admin")
def create_application():
    data = get_json_body()
    require_fields(data, "student_name", "year_group")
    svc = AdmissionsService(_db_path)
    result = svc.create_application(student_name=data["student_name"], year_group=data["year_group"], dob=data.get("dob", ""), parent_name=data.get("parent_name", ""), contact_email=data.get("contact_email", ""))
    return jsonify({"message": "Created.", "data": result}), 201


@admissions_bp.route("", methods=["GET"])
@token_required
def list_applications():
    svc = AdmissionsService(_db_path)
    result = svc.list_applications()
    return jsonify({"data": result})


@admissions_bp.route("/<int:app_id>/status", methods=["PUT"])
@token_required
@role_required("admin")
def update_status(app_id):
    data = get_json_body()
    require_fields(data, "status")
    svc = AdmissionsService(_db_path)
    result = svc.update_status(app_id, data["status"])
    return jsonify({"message": "Updated.", "data": result})


@admissions_bp.route("/<int:app_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_application(app_id):
    svc = AdmissionsService(_db_path)
    result = svc.delete_application(app_id)
    return jsonify({"message": "Deleted.", "data": result})


@admissions_bp.route("/summary", methods=["GET"])
@token_required
@role_required("admin")
def status_summary():
    svc = AdmissionsService(_db_path)
    result = svc.status_summary()
    return jsonify({"data": result})

