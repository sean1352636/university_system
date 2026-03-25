"""Assessments API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.primary.auth import token_required, role_required
from education_system.shared.api.primary.validators import get_json_body, require_fields
from education_system.shared.api.primary.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.academics.assessment.services.assessment_service import AssessmentService

assessments_bp = Blueprint("assessments", __name__, url_prefix="/api/assessments")

_db_path = None


def init_assessments_routes(db_path=None):
    global _db_path
    _db_path = db_path


@assessments_bp.route("", methods=["GET"])
@token_required
def list_assessments():
    svc = AssessmentService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_assessments(pupil_id=request.args.get("pupil_id"), subject_code=request.args.get("subject_code"), term=request.args.get("term"))
    total = len(items)
    return jsonify(paginated_response(items, total))


@assessments_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_assessment(pk):
    svc = AssessmentService(_db_path)
    item = svc.get_assessment(pk)
    if not item:
        return jsonify({"error": "Assessment not found."}), 404
    return jsonify({"data": dict(item) if hasattr(item, "keys") else item})


@assessments_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_assessment():
    data = get_json_body()
    require_fields(data, "pupil_id", "subject_code", "level")
    svc = AssessmentService(_db_path)
    result = svc.create_assessment(**data)
    return jsonify({"message": "Assessment created.", "data": result}), 201


@assessments_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def update_assessment(pk):
    data = get_json_body()
    svc = AssessmentService(_db_path)
    result = svc.update_assessment(pk, **data)
    return jsonify({"message": "Assessment updated.", "data": result})

@assessments_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_assessment(pk):
    svc = AssessmentService(_db_path)
    svc.delete_assessment(pk)
    return jsonify({"message": "Assessment deleted."})