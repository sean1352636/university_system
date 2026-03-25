"""Interventions API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.academics.interventions.services.intervention_service import InterventionService

interventions_bp = Blueprint("interventions", __name__, url_prefix="/api/interventions")

_db_path = None


def init_interventions_routes(db_path=None):
    global _db_path
    _db_path = db_path


@interventions_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_group():
    data = get_json_body()
    require_fields(data, "name", "subject_id")
    svc = InterventionService(_db_path)
    result = svc.create_group(name=data["name"], subject_id=data["subject_id"], lead_staff=data.get("lead_staff", ""))
    return jsonify({"message": "Created.", "data": result}), 201


@interventions_bp.route("", methods=["GET"])
@token_required
def list_groups():
    svc = InterventionService(_db_path)
    result = svc.list_groups()
    return jsonify({"data": result})


@interventions_bp.route("/<int:group_id>/close", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def close_group(group_id):
    svc = InterventionService(_db_path)
    result = svc.close_group(group_id)
    return jsonify({"message": "Created.", "data": result}), 201


@interventions_bp.route("/<int:group_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_group(group_id):
    svc = InterventionService(_db_path)
    result = svc.delete_group(group_id)
    return jsonify({"message": "Deleted.", "data": result})


@interventions_bp.route("/<int:group_id>/members", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def add_member(group_id):
    data = get_json_body()
    require_fields(data, "student_id")
    svc = InterventionService(_db_path)
    result = svc.add_member(group_id, data["student_id"])
    return jsonify({"message": "Created.", "data": result}), 201


@interventions_bp.route("/<int:group_id>/members", methods=["GET"])
@token_required
def list_members(group_id):
    svc = InterventionService(_db_path)
    result = svc.list_members(group_id)
    return jsonify({"data": result})


@interventions_bp.route("/<int:group_id>/members/<int:student_id>", methods=["DELETE"])
@token_required
@role_required("admin", "teacher")
def remove_member(group_id, student_id):
    svc = InterventionService(_db_path)
    result = svc.remove_member(group_id, student_id)
    return jsonify({"message": "Deleted.", "data": result})

