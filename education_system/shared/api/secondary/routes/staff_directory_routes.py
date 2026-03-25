"""Staff Directory API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.staff.staff_directory.services.staff_directory_service import StaffDirectoryService

staff_directory_bp = Blueprint("staff_directory", __name__, url_prefix="/api/staff-directory")

_db_path = None


def init_staff_directory_routes(db_path=None):
    global _db_path
    _db_path = db_path


@staff_directory_bp.route("", methods=["POST"])
@token_required
@role_required("admin")
def add_entry():
    data = get_json_body()
    require_fields(data, "name", "role")
    svc = StaffDirectoryService(_db_path)
    result = svc.add_entry(name=data["name"], role=data["role"], department=data.get("department", ""), email=data.get("email", ""), phone=data.get("phone", ""))
    return jsonify({"message": "Created.", "data": result}), 201


@staff_directory_bp.route("", methods=["GET"])
@token_required
def list_staff():
    svc = StaffDirectoryService(_db_path)
    result = svc.list_staff()
    return jsonify({"data": result})


@staff_directory_bp.route("/departments", methods=["GET"])
@token_required
def get_departments():
    svc = StaffDirectoryService(_db_path)
    result = svc.get_departments()
    return jsonify({"data": result})


@staff_directory_bp.route("/<int:entry_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_entry(entry_id):
    svc = StaffDirectoryService(_db_path)
    result = svc.delete_entry(entry_id)
    return jsonify({"message": "Deleted.", "data": result})

