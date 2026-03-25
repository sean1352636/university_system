"""Send API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.pastoral_care.send.services.send_service import SENDService

send_bp = Blueprint("send", __name__, url_prefix="/api/send")

_db_path = None


def init_send_routes(db_path=None):
    global _db_path
    _db_path = db_path


@send_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_record():
    data = get_json_body()
    require_fields(data, "student_id", "need_type")
    svc = SENDService(_db_path)
    result = svc.create_record(student_id=data["student_id"], need_type=data["need_type"], description=data.get("description", ""), ehcp=data.get("ehcp", False))
    return jsonify({"message": "Created.", "data": result}), 201


@send_bp.route("", methods=["GET"])
@token_required
def list_records():
    svc = SENDService(_db_path)
    result = svc.list_records()
    return jsonify({"data": result})


@send_bp.route("/<int:record_id>", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def update_record(record_id):
    data = get_json_body()
    svc = SENDService(_db_path)
    result = svc.update_record(record_id, **{k: v for k, v in data.items() if k != 'record_id'})
    return jsonify({"message": "Updated.", "data": result})


@send_bp.route("/<int:record_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_record(record_id):
    svc = SENDService(_db_path)
    result = svc.delete_record(record_id)
    return jsonify({"message": "Deleted.", "data": result})


@send_bp.route("/<int:record_id>/provisions", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def add_provision(record_id):
    data = get_json_body()
    require_fields(data, "provision_type")
    svc = SENDService(_db_path)
    result = svc.add_provision(record_id, data["provision_type"], data.get("details", ""))
    return jsonify({"message": "Created.", "data": result}), 201


@send_bp.route("/<int:record_id>/provisions", methods=["GET"])
@token_required
def list_provisions(record_id):
    svc = SENDService(_db_path)
    result = svc.list_provisions(record_id)
    return jsonify({"data": result})

