"""API routes for baseline assessment."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.baseline_assessment.services.baseline_assessment_service import BaselineAssessmentService
from education_system.college_system.core.i18n import t

baseline_assessment_bp = Blueprint("baseline-assessment", __name__, url_prefix="/api/baseline-assessment")

_db_path = None


def init_baseline_assessment_routes(db_path=None):
    global _db_path
    _db_path = db_path


@baseline_assessment_bp.route("", methods=["GET"])
@token_required
def list_baselines():
    svc = BaselineAssessmentService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_baselines(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@baseline_assessment_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_baseline(pk):
    svc = BaselineAssessmentService(_db_path)
    item = svc.get_baseline(pk)
    if not item:
        return jsonify({"error": t("api.baseline_assessment.not_found")}), 404
    return jsonify({"data": item})
@baseline_assessment_bp.route("", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_baseline():
    data = get_json_body()
    svc = BaselineAssessmentService(_db_path)
    result = svc.create_baseline(**data)
    return jsonify({"message": t("api.baseline_assessment.created"), "data": result}), 201
@baseline_assessment_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin', 'staff')
def update_baseline(pk):
    data = get_json_body()
    svc = BaselineAssessmentService(_db_path)
    result = svc.update_baseline(pk, **data)
    return jsonify({"message": t("api.baseline_assessment.updated"), "data": result})
@baseline_assessment_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required('admin')
def delete_baseline(pk):
    svc = BaselineAssessmentService(_db_path)
    svc.delete_baseline(pk)
    return jsonify({"message": t("api.baseline_assessment.deleted")})
@baseline_assessment_bp.route("/checkpoints", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_checkpoints():
    svc = BaselineAssessmentService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_checkpoints(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@baseline_assessment_bp.route("/checkpoints", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_checkpoint():
    data = get_json_body()
    svc = BaselineAssessmentService(_db_path)
    result = svc.create_checkpoint(**data)
    return jsonify({"message": t("api.baseline_assessment.created"), "data": result}), 201
@baseline_assessment_bp.route("/stats", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_stats():
    svc = BaselineAssessmentService(_db_path)
    result = svc.get_stats()
    return jsonify({"data": result})
