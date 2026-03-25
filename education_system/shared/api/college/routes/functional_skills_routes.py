"""API routes for functional skills."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.functional_skills.services.functional_skills_service import FunctionalSkillsService
from education_system.college_system.core.i18n import t

functional_skills_bp = Blueprint("functional-skills", __name__, url_prefix="/api/functional-skills")

_db_path = None


def init_functional_skills_routes(db_path=None):
    global _db_path
    _db_path = db_path


@functional_skills_bp.route("/enrollments", methods=["GET"])
@token_required
def list_enrollments():
    svc = FunctionalSkillsService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_enrollments(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@functional_skills_bp.route("/enrollments/<int:pk>", methods=["GET"])
@token_required
def get_enrollment(pk):
    svc = FunctionalSkillsService(_db_path)
    item = svc.get_enrollment(pk)
    if not item:
        return jsonify({"error": t("api.functional_skills.not_found")}), 404
    return jsonify({"data": item})
@functional_skills_bp.route("/enrollments", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_enrollment():
    data = get_json_body()
    svc = FunctionalSkillsService(_db_path)
    result = svc.create_enrollment(**data)
    return jsonify({"message": t("api.functional_skills.created"), "data": result}), 201
@functional_skills_bp.route("/enrollments/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin', 'staff')
def update_enrollment(pk):
    data = get_json_body()
    svc = FunctionalSkillsService(_db_path)
    result = svc.update_enrollment(pk, **data)
    return jsonify({"message": t("api.functional_skills.updated"), "data": result})
@functional_skills_bp.route("/assessments", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_assessments():
    svc = FunctionalSkillsService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_assessments(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@functional_skills_bp.route("/assessments", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_assessment():
    data = get_json_body()
    svc = FunctionalSkillsService(_db_path)
    result = svc.create_assessment(**data)
    return jsonify({"message": t("api.functional_skills.created"), "data": result}), 201
@functional_skills_bp.route("/stats", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_stats():
    svc = FunctionalSkillsService(_db_path)
    result = svc.get_stats()
    return jsonify({"data": result})
