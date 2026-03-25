"""API routes for parent portal."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.parent_portal.services.parent_service import ParentService
from education_system.college_system.core.i18n import t

parent_portal_bp = Blueprint("parent-portal", __name__, url_prefix="/api/parent-portal")

_db_path = None


def init_parent_portal_routes(db_path=None):
    global _db_path
    _db_path = db_path


@parent_portal_bp.route("/linked-students", methods=["GET"])
@token_required
def get_linked_students():
    svc = ParentService(_db_path)
    result = svc.get_linked_students()
    return jsonify({"data": result})
@parent_portal_bp.route("/link", methods=["POST"])
@token_required
def link_parent():
    data = get_json_body()
    svc = ParentService(_db_path)
    result = svc.link_parent(**data)
    return jsonify({"message": t("api.parent_portal.created"), "data": result}), 201
@parent_portal_bp.route("/link/<int:pk>", methods=["DELETE"])
@token_required
def unlink_parent(pk):
    svc = ParentService(_db_path)
    svc.unlink_parent(pk)
    return jsonify({"message": t("api.parent_portal.deleted")})
@parent_portal_bp.route("/child/<student_id>/grades", methods=["GET"])
@token_required
def get_child_grades(student_id):
    svc = ParentService(_db_path)
    item = svc.get_child_grades(student_id)
    if not item:
        return jsonify({"error": t("api.parent_portal.not_found")}), 404
    return jsonify({"data": item})
@parent_portal_bp.route("/child/<student_id>/attendance", methods=["GET"])
@token_required
def get_child_attendance(student_id):
    svc = ParentService(_db_path)
    item = svc.get_child_attendance(student_id)
    if not item:
        return jsonify({"error": t("api.parent_portal.not_found")}), 404
    return jsonify({"data": item})
@parent_portal_bp.route("/child/<student_id>/timetable", methods=["GET"])
@token_required
def get_child_timetable(student_id):
    svc = ParentService(_db_path)
    item = svc.get_child_timetable(student_id)
    if not item:
        return jsonify({"error": t("api.parent_portal.not_found")}), 404
    return jsonify({"data": item})
@parent_portal_bp.route("/all", methods=["GET"])
@token_required
@role_required('admin')
def get_all_parents():
    svc = ParentService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.get_all_parents(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
