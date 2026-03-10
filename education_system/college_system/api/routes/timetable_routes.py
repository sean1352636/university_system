"""Timetable API routes."""

from flask import Blueprint, jsonify, request, g

from education_system.college_system.api.auth import token_required, role_required
from education_system.college_system.api.validators import get_json_body, require_fields
from education_system.college_system.modules.domain.timetable.services.timetable_service import TimetableService

timetable_bp = Blueprint("timetable", __name__, url_prefix="/api/timetable")

_db_path = None


def init_timetable_routes(db_path=None):
    global _db_path
    _db_path = db_path


@timetable_bp.route("/slots", methods=["POST"])
@token_required
@role_required("admin", "staff", "instructor")
def add_slot():
    data = get_json_body()
    require_fields(data, "course_id", "day_of_week", "start_time", "end_time")

    svc = TimetableService(_db_path)
    slot = svc.add_slot(
        data["course_id"], data["day_of_week"],
        data["start_time"], data["end_time"],
        room=data.get("room"), instructor=data.get("instructor_name"),
    )
    return jsonify({"message": "Slot added.", "data": slot}), 201


@timetable_bp.route("/slots/<int:slot_id>", methods=["PUT"])
@token_required
@role_required("admin", "staff", "instructor")
def update_slot(slot_id):
    data = get_json_body()
    svc = TimetableService(_db_path)
    slot = svc.update_slot(slot_id, **data)
    return jsonify({"message": "Slot updated.", "data": slot})


@timetable_bp.route("/slots/<int:slot_id>", methods=["DELETE"])
@token_required
@role_required("admin", "staff", "instructor")
def delete_slot(slot_id):
    svc = TimetableService(_db_path)
    svc.delete_slot(slot_id)
    return jsonify({"message": "Slot deleted."})


@timetable_bp.route("/course/<int:course_id>", methods=["GET"])
@token_required
def get_course_timetable(course_id):
    svc = TimetableService(_db_path)
    slots = svc.get_course_timetable(course_id)
    return jsonify({"data": slots, "count": len(slots)})


@timetable_bp.route("/student/<int:student_id>", methods=["GET"])
@token_required
def get_student_timetable(student_id):
    svc = TimetableService(_db_path)
    slots = svc.get_student_timetable(student_id)
    return jsonify({"data": slots, "count": len(slots)})


@timetable_bp.route("/room/<room>", methods=["GET"])
@token_required
def get_room_schedule(room):
    svc = TimetableService(_db_path)
    slots = svc.get_room_schedule(room)
    return jsonify({"data": slots, "count": len(slots)})


@timetable_bp.route("/conflicts", methods=["POST"])
@token_required
def check_conflicts():
    data = get_json_body()
    require_fields(data, "day_of_week", "start_time", "end_time")

    svc = TimetableService(_db_path)
    conflicts = svc.check_conflicts(
        data["day_of_week"], data["start_time"], data["end_time"],
        room=data.get("room"), instructor=data.get("instructor_name"),
        exclude_id=data.get("exclude_id"),
    )
    return jsonify({"data": conflicts, "count": len(conflicts)})


@timetable_bp.route("/student/<int:student_id>/clashes", methods=["GET"])
@token_required
def get_student_clashes(student_id):
    svc = TimetableService(_db_path)
    clashes = svc.check_student_clashes(student_id)
    return jsonify({"data": clashes, "count": len(clashes)})


@timetable_bp.route("/instructor/<instructor_name>", methods=["GET"])
@token_required
def get_instructor_schedule(instructor_name):
    svc = TimetableService(_db_path)
    slots = svc.get_instructor_schedule(instructor_name)
    return jsonify({"data": slots, "count": len(slots)})
