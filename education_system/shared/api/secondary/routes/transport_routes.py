"""Transport API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.student_life.transport.services.transport_service import TransportService

transport_bp = Blueprint("transport", __name__, url_prefix="/api/transport")

_db_path = None


def init_transport_routes(db_path=None):
    global _db_path
    _db_path = db_path


@transport_bp.route("/routes", methods=["POST"])
@token_required
@role_required("admin")
def create_route():
    data = get_json_body()
    require_fields(data, "route_name")
    svc = TransportService(_db_path)
    result = svc.create_route(route_name=data["route_name"], operator=data.get("operator", ""), capacity=data.get("capacity", 50))
    return jsonify({"message": "Created.", "data": result}), 201


@transport_bp.route("/routes", methods=["GET"])
@token_required
def list_routes():
    svc = TransportService(_db_path)
    result = svc.list_routes()
    return jsonify({"data": result})


@transport_bp.route("/routes/<int:route_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_route(route_id):
    svc = TransportService(_db_path)
    result = svc.delete_route(route_id)
    return jsonify({"message": "Deleted.", "data": result})


@transport_bp.route("/routes/<int:route_id>/students", methods=["POST"])
@token_required
@role_required("admin")
def assign_student(route_id):
    data = get_json_body()
    require_fields(data, "student_id")
    svc = TransportService(_db_path)
    result = svc.assign_student(route_id, data["student_id"])
    return jsonify({"message": "Created.", "data": result}), 201


@transport_bp.route("/routes/<int:route_id>/students", methods=["GET"])
@token_required
def list_route_students(route_id):
    svc = TransportService(_db_path)
    result = svc.list_route_students(route_id)
    return jsonify({"data": result})


@transport_bp.route("/routes/<int:route_id>/students/<int:student_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def remove_student(route_id, student_id):
    svc = TransportService(_db_path)
    result = svc.remove_student(route_id, student_id)
    return jsonify({"message": "Deleted.", "data": result})

