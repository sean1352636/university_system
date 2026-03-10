"""API routes for study planner."""

from flask import Blueprint, jsonify, request
from education_system.college_system.api.auth import token_required, role_required
from education_system.college_system.api.validators import get_json_body, require_fields
from education_system.college_system.api.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.study_planner.services.study_planner_service import StudyPlannerService

study_planner_bp = Blueprint("study-planner", __name__, url_prefix="/api/study-planner")

_db_path = None


def init_study_planner_routes(db_path=None):
    global _db_path
    _db_path = db_path


@study_planner_bp.route("", methods=["GET"])
@token_required
def list_sessions():
    svc = StudyPlannerService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_sessions(limit=limit, offset=offset)
    total = svc.count_sessions()
    return jsonify(paginated_response(items, total))


@study_planner_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_session(pk):
    svc = StudyPlannerService(_db_path)
    item = svc.get_session(pk)
    if not item:
        return jsonify({"error": "Session not found."}), 404
    return jsonify({"data": item})


@study_planner_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff", "instructor")
def create_session():
    data = get_json_body()
    require_fields(data, "student_id", "subject", "planned_date")
    svc = StudyPlannerService(_db_path)
    item = svc.create_session(**data)
    return jsonify({"message": "Session created.", "data": item}), 201


@study_planner_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff", "instructor")
def update_session(pk):
    data = get_json_body()
    svc = StudyPlannerService(_db_path)
    item = svc.update_session(pk, **data)
    return jsonify({"message": "Session updated.", "data": item})


@study_planner_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_session(pk):
    svc = StudyPlannerService(_db_path)
    svc.delete_session(pk)
    return jsonify({"message": "Session deleted."})
