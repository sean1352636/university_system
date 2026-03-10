"""Behaviour API routes."""

from flask import Blueprint, jsonify, request

from education_system.primary_school.api.auth import token_required, role_required
from education_system.primary_school.api.validators import get_json_body, require_fields
from education_system.primary_school.api.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.pastoral_care.behaviour.services.behaviour_service import BehaviourService

behaviour_bp = Blueprint("behaviour", __name__, url_prefix="/api/behaviour")

_db_path = None


def init_behaviour_routes(db_path=None):
    global _db_path
    _db_path = db_path


@behaviour_bp.route("", methods=["GET"])
@token_required
def list_records():
    svc = BehaviourService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_records(pupil_id=request.args.get("pupil_id"))
    total = len(items)
    return jsonify(paginated_response(items, total))


@behaviour_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_record(pk):
    svc = BehaviourService(_db_path)
    item = svc.get_record(pk)
    if not item:
        return jsonify({"error": "Record not found."}), 404
    return jsonify({"data": dict(item) if hasattr(item, "keys") else item})


@behaviour_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_record():
    data = get_json_body()
    require_fields(data, "pupil_id", "incident_type", "description")
    svc = BehaviourService(_db_path)
    result = svc.create_record(**data)
    return jsonify({"message": "Record created.", "data": result}), 201


@behaviour_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def update_record(pk):
    data = get_json_body()
    svc = BehaviourService(_db_path)
    result = svc.update_record(pk, **data)
    return jsonify({"message": "Record updated.", "data": result})

@behaviour_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_record(pk):
    svc = BehaviourService(_db_path)
    svc.delete_record(pk)
    return jsonify({"message": "Record deleted."})