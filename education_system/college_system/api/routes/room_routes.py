"""Room API routes."""

from flask import Blueprint, jsonify, request

from education_system.college_system.api.auth import token_required, role_required
from education_system.college_system.api.validators import get_json_body, require_fields
from education_system.college_system.modules.domain.timetable.services.room_service import RoomService

room_bp = Blueprint("rooms", __name__, url_prefix="/api/rooms")

_db_path = None


def init_room_routes(db_path=None):
    global _db_path
    _db_path = db_path


@room_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_room():
    data = get_json_body()
    require_fields(data, "room_code")
    svc = RoomService(_db_path)
    room = svc.create_room(
        data["room_code"],
        building=data.get("building"),
        floor=data.get("floor"),
        room_type=data.get("room_type", "classroom"),
        capacity=data.get("capacity", 30),
        has_projector=data.get("has_projector", False),
        has_whiteboard=data.get("has_whiteboard", True),
        has_computers=data.get("has_computers", False),
        wheelchair_accessible=data.get("wheelchair_accessible", False),
    )
    return jsonify({"message": "Room created.", "data": room}), 201


@room_bp.route("", methods=["GET"])
@token_required
def list_rooms():
    svc = RoomService(_db_path)
    room_type = request.args.get("room_type")
    status = request.args.get("status")
    rooms = svc.list_rooms(room_type=room_type, status=status)
    return jsonify({"data": rooms, "count": len(rooms)})


@room_bp.route("/<int:room_id>", methods=["GET"])
@token_required
def get_room(room_id):
    svc = RoomService(_db_path)
    room = svc.get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found."}), 404
    return jsonify({"data": room})


@room_bp.route("/<int:room_id>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_room(room_id):
    data = get_json_body()
    svc = RoomService(_db_path)
    room = svc.update_room(room_id, **data)
    return jsonify({"message": "Room updated.", "data": room})


@room_bp.route("/<int:room_id>/resources", methods=["POST"])
@token_required
@role_required("admin", "staff")
def add_resource(room_id):
    data = get_json_body()
    require_fields(data, "resource_name")
    svc = RoomService(_db_path)
    resource = svc.add_resource(
        room_id, data["resource_name"],
        resource_type=data.get("resource_type", "equipment"),
        quantity=data.get("quantity", 1),
        condition=data.get("condition", "good"),
    )
    return jsonify({"message": "Resource added.", "data": resource}), 201


@room_bp.route("/<int:room_id>/resources", methods=["GET"])
@token_required
def list_resources(room_id):
    svc = RoomService(_db_path)
    resources = svc.list_resources(room_id)
    return jsonify({"data": resources, "count": len(resources)})


@room_bp.route("/available", methods=["GET"])
@token_required
def available_rooms():
    day = request.args.get("day")
    start = request.args.get("start_time")
    end = request.args.get("end_time")
    if not day or not start or not end:
        return jsonify({"error": "day, start_time, and end_time are required."}), 400
    svc = RoomService(_db_path)
    min_capacity = request.args.get("min_capacity", type=int)
    room_type = request.args.get("room_type")
    rooms = svc.find_available_rooms(day, start, end, min_capacity, room_type)
    return jsonify({"data": rooms, "count": len(rooms)})


@room_bp.route("/utilization", methods=["GET"])
@token_required
@role_required("admin", "staff")
def room_utilization():
    svc = RoomService(_db_path)
    util = svc.get_room_utilization()
    return jsonify({"data": util, "count": len(util)})
