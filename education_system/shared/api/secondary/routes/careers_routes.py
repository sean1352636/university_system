"""Careers API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.student_life.careers.services.careers_service import CareersService

careers_bp = Blueprint("careers", __name__, url_prefix="/api/careers")

_db_path = None


def init_careers_routes(db_path=None):
    global _db_path
    _db_path = db_path


@careers_bp.route("/meetings", methods=["POST"])
@token_required
def add_meeting():
    data = get_json_body()
    require_fields(data, "student_id", "date")
    svc = CareersService(_db_path)
    result = svc.add_meeting(student_id=data["student_id"], date=data["date"], advisor=data.get("advisor", ""), notes=data.get("notes", ""))
    return jsonify({"message": "Created.", "data": result}), 201


@careers_bp.route("/meetings", methods=["GET"])
@token_required
def list_meetings():
    svc = CareersService(_db_path)
    result = svc.list_meetings()
    return jsonify({"data": result})


@careers_bp.route("/meetings/<int:meeting_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_meeting(meeting_id):
    svc = CareersService(_db_path)
    result = svc.delete_meeting(meeting_id)
    return jsonify({"message": "Deleted.", "data": result})


@careers_bp.route("/placements", methods=["POST"])
@token_required
def add_placement():
    data = get_json_body()
    require_fields(data, "student_id", "employer")
    svc = CareersService(_db_path)
    result = svc.add_placement(student_id=data["student_id"], employer=data["employer"], start_date=data.get("start_date", ""), end_date=data.get("end_date", ""))
    return jsonify({"message": "Created.", "data": result}), 201


@careers_bp.route("/placements", methods=["GET"])
@token_required
def list_placements():
    svc = CareersService(_db_path)
    result = svc.list_placements()
    return jsonify({"data": result})


@careers_bp.route("/placements/<int:placement_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_placement(placement_id):
    svc = CareersService(_db_path)
    result = svc.delete_placement(placement_id)
    return jsonify({"message": "Deleted.", "data": result})

