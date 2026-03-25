"""Form Groups API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.student_life.form_groups.services.form_group_service import FormGroupService

form_groups_bp = Blueprint("form_groups", __name__, url_prefix="/api/form-groups")

_db_path = None


def init_form_groups_routes(db_path=None):
    global _db_path
    _db_path = db_path


@form_groups_bp.route("", methods=["POST"])
@token_required
@role_required("admin")
def create_group():
    data = get_json_body()
    require_fields(data, "name", "tutor")
    svc = FormGroupService(_db_path)
    result = svc.create_group(name=data["name"], tutor=data["tutor"], year_group=data.get("year_group", ""))
    return jsonify({"message": "Created.", "data": result}), 201


@form_groups_bp.route("", methods=["GET"])
@token_required
def list_groups():
    svc = FormGroupService(_db_path)
    result = svc.list_groups()
    return jsonify({"data": result})


@form_groups_bp.route("/<int:group_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_group(group_id):
    svc = FormGroupService(_db_path)
    result = svc.delete_group(group_id)
    return jsonify({"message": "Deleted.", "data": result})


@form_groups_bp.route("/<int:group_id>/students", methods=["POST"])
@token_required
@role_required("admin")
def add_student(group_id):
    data = get_json_body()
    require_fields(data, "student_id")
    svc = FormGroupService(_db_path)
    result = svc.add_student(group_id, data["student_id"])
    return jsonify({"message": "Created.", "data": result}), 201


@form_groups_bp.route("/<int:group_id>/students", methods=["GET"])
@token_required
def list_students(group_id):
    svc = FormGroupService(_db_path)
    result = svc.list_students(group_id)
    return jsonify({"data": result})


@form_groups_bp.route("/<int:group_id>/students/<int:student_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def remove_student(group_id, student_id):
    svc = FormGroupService(_db_path)
    result = svc.remove_student(group_id, student_id)
    return jsonify({"message": "Deleted.", "data": result})

