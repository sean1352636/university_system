"""Group API routes (tutor groups, teaching groups, members)."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.college_system.modules.domain.departments.services.department_service import GroupService
from education_system.college_system.core.i18n import t

group_bp = Blueprint("groups", __name__, url_prefix="/api/groups")

_db_path = None


def init_group_routes(db_path=None):
    global _db_path
    _db_path = db_path


@group_bp.route("/tutor", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_tutor_group():
    data = get_json_body()
    require_fields(data, "name")
    svc = GroupService(_db_path)
    group = svc.create_tutor_group(
        data["name"],
        year_group=data.get("year_group"),
        tutor_id=data.get("tutor_id"),
        room_id=data.get("room_id"),
        max_size=data.get("max_size", 30),
    )
    return jsonify({"message": t("api.group.created"), "data": group}), 201


@group_bp.route("/tutor", methods=["GET"])
@token_required
def list_tutor_groups():
    svc = GroupService(_db_path)
    groups = svc.list_tutor_groups()
    return jsonify({"data": groups, "count": len(groups)})


@group_bp.route("/teaching", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_teaching_group():
    data = get_json_body()
    require_fields(data, "name", "course_id")
    svc = GroupService(_db_path)
    group = svc.create_teaching_group(
        data["name"], data["course_id"],
        academic_year=data.get("academic_year"),
        max_size=data.get("max_size", 30),
    )
    return jsonify({"message": t("api.group.created"), "data": group}), 201


@group_bp.route("/teaching", methods=["GET"])
@token_required
def list_teaching_groups():
    svc = GroupService(_db_path)
    course_id = request.args.get("course_id", type=int)
    groups = svc.list_teaching_groups(course_id=course_id)
    return jsonify({"data": groups, "count": len(groups)})


@group_bp.route("/<int:group_id>/members/<group_type>", methods=["GET"])
@token_required
def list_members(group_id, group_type):
    svc = GroupService(_db_path)
    members = svc.list_members(group_id, group_type)
    return jsonify({"data": members, "count": len(members)})


@group_bp.route("/<int:group_id>/members/<group_type>", methods=["POST"])
@token_required
@role_required("admin", "staff")
def add_member(group_id, group_type):
    data = get_json_body()
    require_fields(data, "student_id")
    svc = GroupService(_db_path)
    member = svc.add_member(group_id, group_type, data["student_id"])
    return jsonify({"message": t("api.group.member_added"), "data": member}), 201


@group_bp.route("/members/<int:member_id>", methods=["DELETE"])
@token_required
@role_required("admin", "staff")
def remove_member(member_id):
    svc = GroupService(_db_path)
    svc.remove_member(member_id)
    return jsonify({"message": t("api.group.member_removed")})
