"""API routes for self assessment."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.self_assessment.services.self_assessment_service import SelfAssessmentService
from education_system.college_system.core.i18n import t

self_assessment_bp = Blueprint("self-assessment", __name__, url_prefix="/api/self-assessment")

_db_path = None


def init_self_assessment_routes(db_path=None):
    global _db_path
    _db_path = db_path


@self_assessment_bp.route("/sections", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_sections():
    svc = SelfAssessmentService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_sections(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@self_assessment_bp.route("/sections/<int:pk>", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_section(pk):
    svc = SelfAssessmentService(_db_path)
    item = svc.get_section(pk)
    if not item:
        return jsonify({"error": t("api.self_assessment.not_found")}), 404
    return jsonify({"data": item})
@self_assessment_bp.route("/sections", methods=["POST"])
@token_required
@role_required('admin')
def create_section():
    data = get_json_body()
    svc = SelfAssessmentService(_db_path)
    result = svc.create_section(**data)
    return jsonify({"message": t("api.self_assessment.created"), "data": result}), 201
@self_assessment_bp.route("/sections/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin')
def update_section(pk):
    data = get_json_body()
    svc = SelfAssessmentService(_db_path)
    result = svc.update_section(pk, **data)
    return jsonify({"message": t("api.self_assessment.updated"), "data": result})
@self_assessment_bp.route("/actions", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_actions():
    svc = SelfAssessmentService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_actions(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@self_assessment_bp.route("/actions", methods=["POST"])
@token_required
@role_required('admin')
def create_action():
    data = get_json_body()
    svc = SelfAssessmentService(_db_path)
    result = svc.create_action(**data)
    return jsonify({"message": t("api.self_assessment.created"), "data": result}), 201
@self_assessment_bp.route("/stats", methods=["GET"])
@token_required
@role_required('admin')
def get_stats():
    svc = SelfAssessmentService(_db_path)
    result = svc.get_stats()
    return jsonify({"data": result})
