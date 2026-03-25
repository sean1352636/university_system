"""API routes for student council."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.student_council.services.student_council_service import StudentCouncilService
from education_system.college_system.core.i18n import t

student_council_bp = Blueprint("student-council", __name__, url_prefix="/api/student-council")

_db_path = None


def init_student_council_routes(db_path=None):
    global _db_path
    _db_path = db_path


@student_council_bp.route("/members", methods=["GET"])
@token_required
def list_members():
    svc = StudentCouncilService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_members(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@student_council_bp.route("/members/<int:pk>", methods=["GET"])
@token_required
def get_member(pk):
    svc = StudentCouncilService(_db_path)
    item = svc.get_member(pk)
    if not item:
        return jsonify({"error": t("api.student_council.not_found")}), 404
    return jsonify({"data": item})
@student_council_bp.route("/members", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_member():
    data = get_json_body()
    svc = StudentCouncilService(_db_path)
    result = svc.create_member(**data)
    return jsonify({"message": t("api.student_council.created"), "data": result}), 201
@student_council_bp.route("/members/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin', 'staff')
def update_member(pk):
    data = get_json_body()
    svc = StudentCouncilService(_db_path)
    result = svc.update_member(pk, **data)
    return jsonify({"message": t("api.student_council.updated"), "data": result})
@student_council_bp.route("/meetings", methods=["GET"])
@token_required
def list_meetings():
    svc = StudentCouncilService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_meetings(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@student_council_bp.route("/meetings", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_meeting():
    data = get_json_body()
    svc = StudentCouncilService(_db_path)
    result = svc.create_meeting(**data)
    return jsonify({"message": t("api.student_council.created"), "data": result}), 201
@student_council_bp.route("/proposals", methods=["GET"])
@token_required
def list_proposals():
    svc = StudentCouncilService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_proposals(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@student_council_bp.route("/proposals", methods=["POST"])
@token_required
def create_proposal():
    data = get_json_body()
    svc = StudentCouncilService(_db_path)
    result = svc.create_proposal(**data)
    return jsonify({"message": t("api.student_council.created"), "data": result}), 201
@student_council_bp.route("/stats", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_stats():
    svc = StudentCouncilService(_db_path)
    result = svc.get_stats()
    return jsonify({"data": result})
