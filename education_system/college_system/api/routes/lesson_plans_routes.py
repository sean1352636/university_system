"""API routes for lesson plans."""

from flask import Blueprint, jsonify, request
from education_system.college_system.api.auth import token_required, role_required
from education_system.college_system.api.validators import get_json_body, require_fields
from education_system.college_system.api.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.lesson_plans.services.lesson_plans_service import LessonPlanService

lesson_plan_bp = Blueprint("lesson-plans", __name__, url_prefix="/api/lesson-plans")

_db_path = None


def init_lesson_plan_routes(db_path=None):
    global _db_path
    _db_path = db_path


@lesson_plan_bp.route("", methods=["GET"])
@token_required
def list_plans():
    svc = LessonPlanService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_plans(limit=limit, offset=offset)
    total = svc.count_plans()
    return jsonify(paginated_response(items, total))


@lesson_plan_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_plan(pk):
    svc = LessonPlanService(_db_path)
    item = svc.get_plan(pk)
    if not item:
        return jsonify({"error": "Plan not found."}), 404
    return jsonify({"data": item})


@lesson_plan_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_plan():
    data = get_json_body()
    require_fields(data, "course_id", "teacher_id", "lesson_date", "topic")
    svc = LessonPlanService(_db_path)
    item = svc.create_plan(**data)
    return jsonify({"message": "Plan created.", "data": item}), 201


@lesson_plan_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_plan(pk):
    data = get_json_body()
    svc = LessonPlanService(_db_path)
    item = svc.update_plan(pk, **data)
    return jsonify({"message": "Plan updated.", "data": item})


@lesson_plan_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_plan(pk):
    svc = LessonPlanService(_db_path)
    svc.delete_plan(pk)
    return jsonify({"message": "Plan deleted."})
