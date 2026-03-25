"""Hr API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.staff.hr.services.hr_service import HRService

hr_bp = Blueprint("hr", __name__, url_prefix="/api/hr")

_db_path = None


def init_hr_routes(db_path=None):
    global _db_path
    _db_path = db_path


@hr_bp.route("/staff", methods=["POST"])
@token_required
@role_required("admin")
def create_staff():
    data = get_json_body()
    require_fields(data, "name", "role")
    svc = HRService(_db_path)
    result = svc.create_staff(name=data["name"], role=data["role"], department=data.get("department", ""), email=data.get("email", ""))
    return jsonify({"message": "Created.", "data": result}), 201


@hr_bp.route("/staff", methods=["GET"])
@token_required
def list_staff():
    svc = HRService(_db_path)
    result = svc.list_staff()
    return jsonify({"data": result})


@hr_bp.route("/staff/<int:staff_id>", methods=["GET"])
@token_required
def get_staff(staff_id):
    svc = HRService(_db_path)
    result = svc.get_staff(staff_id)
    return jsonify({"data": result})


@hr_bp.route("/staff/<int:staff_id>", methods=["PUT"])
@token_required
@role_required("admin")
def update_staff(staff_id):
    data = get_json_body()
    svc = HRService(_db_path)
    result = svc.update_staff(staff_id, **{k: v for k, v in data.items() if k != 'staff_id'})
    return jsonify({"message": "Updated.", "data": result})


@hr_bp.route("/staff/<int:staff_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_staff(staff_id):
    svc = HRService(_db_path)
    result = svc.delete_staff(staff_id)
    return jsonify({"message": "Deleted.", "data": result})


@hr_bp.route("/leave", methods=["POST"])
@token_required
def request_leave():
    data = get_json_body()
    require_fields(data, "staff_id", "leave_type", "start_date", "end_date")
    svc = HRService(_db_path)
    result = svc.request_leave(staff_id=data["staff_id"], leave_type=data["leave_type"], start_date=data["start_date"], end_date=data["end_date"], reason=data.get("reason", ""))
    return jsonify({"message": "Created.", "data": result}), 201


@hr_bp.route("/leave", methods=["GET"])
@token_required
@role_required("admin")
def list_leave():
    svc = HRService(_db_path)
    result = svc.list_leave()
    return jsonify({"data": result})


@hr_bp.route("/leave/<int:leave_id>/approve", methods=["PUT"])
@token_required
@role_required("admin")
def approve_leave(leave_id):
    svc = HRService(_db_path)
    result = svc.approve_leave(leave_id)
    return jsonify({"message": "Updated.", "data": result})


@hr_bp.route("/leave/<int:leave_id>/reject", methods=["PUT"])
@token_required
@role_required("admin")
def reject_leave(leave_id):
    svc = HRService(_db_path)
    result = svc.reject_leave(leave_id)
    return jsonify({"message": "Updated.", "data": result})

