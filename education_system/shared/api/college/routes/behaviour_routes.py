"""API routes for behaviour."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.behaviour.services.behaviour_service import BehaviourService
from education_system.college_system.core.i18n import t

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
    items = svc.list_records(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@behaviour_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_record(pk):
    svc = BehaviourService(_db_path)
    item = svc.get_record(pk)
    if not item:
        return jsonify({"error": t("api.behaviour.not_found")}), 404
    return jsonify({"data": item})
@behaviour_bp.route("", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def record_incident():
    data = get_json_body()
    svc = BehaviourService(_db_path)
    result = svc.record_incident(**data)
    return jsonify({"message": t("api.behaviour.created"), "data": result}), 201
@behaviour_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin', 'staff')
def update_record(pk):
    data = get_json_body()
    svc = BehaviourService(_db_path)
    result = svc.update_record(pk, **data)
    return jsonify({"message": t("api.behaviour.updated"), "data": result})
@behaviour_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required('admin')
def delete_incident(pk):
    svc = BehaviourService(_db_path)
    svc.delete_incident(pk)
    return jsonify({"message": t("api.behaviour.deleted")})
@behaviour_bp.route("/student/<student_id>", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_student_records(student_id):
    svc = BehaviourService(_db_path)
    item = svc.get_student_records(student_id)
    if not item:
        return jsonify({"error": t("api.behaviour.not_found")}), 404
    return jsonify({"data": item})
