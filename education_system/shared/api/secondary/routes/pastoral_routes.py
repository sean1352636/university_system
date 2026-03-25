"""Pastoral API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.pastoral_care.pastoral.services.pastoral_service import PastoralService

pastoral_bp = Blueprint("pastoral", __name__, url_prefix="/api/pastoral")

_db_path = None


def init_pastoral_routes(db_path=None):
    global _db_path
    _db_path = db_path


@pastoral_bp.route("/notes", methods=["POST"])
@token_required
def add_note():
    data = get_json_body()
    require_fields(data, "student_id", "note")
    svc = PastoralService(_db_path)
    result = svc.add_note(student_id=data["student_id"], note=data["note"], category=data.get("category", "general"), staff_member=data.get("staff_member", ""))
    return jsonify({"message": "Created.", "data": result}), 201


@pastoral_bp.route("/notes", methods=["GET"])
@token_required
def list_notes():
    svc = PastoralService(_db_path)
    result = svc.list_notes()
    return jsonify({"data": result})


@pastoral_bp.route("/notes/<int:note_id>/follow-up", methods=["PUT"])
@token_required
def mark_follow_up(note_id):
    svc = PastoralService(_db_path)
    result = svc.mark_follow_up_done(note_id)
    return jsonify({"message": "Updated.", "data": result})


@pastoral_bp.route("/notes/<int:note_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_note(note_id):
    svc = PastoralService(_db_path)
    result = svc.delete_note(note_id)
    return jsonify({"message": "Deleted.", "data": result})


@pastoral_bp.route("/house-points", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def award_house_points():
    data = get_json_body()
    require_fields(data, "student_id", "points")
    svc = PastoralService(_db_path)
    result = svc.award_house_points(data["student_id"], data["points"], data.get("reason", ""))
    return jsonify({"message": "Created.", "data": result}), 201


@pastoral_bp.route("/house-points/summary", methods=["GET"])
@token_required
def house_points_summary():
    svc = PastoralService(_db_path)
    result = svc.house_points_summary()
    return jsonify({"data": result})


@pastoral_bp.route("/house-points/student/<int:student_id>", methods=["GET"])
@token_required
def student_house_points(student_id):
    svc = PastoralService(_db_path)
    result = svc.student_house_points(student_id)
    return jsonify({"data": result})

