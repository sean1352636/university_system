"""Timetable API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.academics.timetable.services.timetable_service import TimetableService

timetable_bp = Blueprint("timetable", __name__, url_prefix="/api/timetable")

_db_path = None


def init_timetable_routes(db_path=None):
    global _db_path
    _db_path = db_path


@timetable_bp.route("", methods=["POST"])
@token_required
@role_required("admin")
def add_slot():
    data = get_json_body()
    require_fields(data, "subject_id", "day", "period")
    svc = TimetableService(_db_path)
    result = svc.add_slot(subject_id=data["subject_id"], day=data["day"], period=data["period"], room=data.get("room", ""), teacher=data.get("teacher", ""))
    return jsonify({"message": "Created.", "data": result}), 201


@timetable_bp.route("/class/<class_id>", methods=["GET"])
@token_required
def get_timetable(class_id):
    svc = TimetableService(_db_path)
    result = svc.get_timetable(class_id)
    return jsonify({"data": result})


@timetable_bp.route("/<int:slot_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_slot(slot_id):
    svc = TimetableService(_db_path)
    result = svc.delete_slot(slot_id)
    return jsonify({"message": "Deleted.", "data": result})


@timetable_bp.route("/generate/<class_id>", methods=["POST"])
@token_required
@role_required("admin")
def generate_timetable(class_id):
    svc = TimetableService(_db_path)
    result = svc.generate_timetable(class_id)
    return jsonify({"message": "Created.", "data": result}), 201

