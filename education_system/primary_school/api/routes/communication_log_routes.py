"""Communication Log API routes."""

from flask import Blueprint, jsonify, request

from education_system.primary_school.api.auth import token_required, role_required
from education_system.primary_school.api.validators import get_json_body, require_fields
from education_system.primary_school.modules.domain.communication.communication_log.services.communication_log_service import CommunicationLogService

communication_log_bp = Blueprint("communication_log", __name__, url_prefix="/api/communication-log")

_db_path = None


def init_communication_log_routes(db_path=None):
    global _db_path
    _db_path = db_path


@communication_log_bp.route("", methods=["GET"])
@token_required
def list_entries():
    svc = CommunicationLogService(_db_path)
    pupil_id = request.args.get("pupil_id")
    items = svc.list_entries(pupil_id=pupil_id) if pupil_id else svc.list_entries()
    return jsonify({"data": items})


@communication_log_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_entry():
    data = get_json_body()
    require_fields(data, "pupil_id", "communication_type", "summary")
    svc = CommunicationLogService(_db_path)
    result = svc.create_entry(**data)
    return jsonify({"message": "Entry created.", "data": result}), 201
