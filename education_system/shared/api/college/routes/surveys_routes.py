"""API routes for surveys."""

from flask import Blueprint, jsonify, request
from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.surveys.services.surveys_service import SurveyService
from education_system.college_system.core.i18n import t

survey_bp = Blueprint("surveys", __name__, url_prefix="/api/surveys")

_db_path = None


def init_survey_routes(db_path=None):
    global _db_path
    _db_path = db_path


@survey_bp.route("", methods=["GET"])
@token_required
def list_surveys():
    svc = SurveyService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_surveys(limit=limit, offset=offset)
    total = svc.count_surveys()
    return jsonify(paginated_response(items, total))


@survey_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_survey(pk):
    svc = SurveyService(_db_path)
    item = svc.get_survey(pk)
    if not item:
        return jsonify({"error": t("api.surveys.not_found")}), 404
    return jsonify({"data": item})


@survey_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff", "instructor")
def create_survey():
    data = get_json_body()
    require_fields(data, "title", "created_by")
    svc = SurveyService(_db_path)
    item = svc.create_survey(**data)
    return jsonify({"message": t("api.surveys.created"), "data": item}), 201


@survey_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff", "instructor")
def update_survey(pk):
    data = get_json_body()
    svc = SurveyService(_db_path)
    item = svc.update_survey(pk, **data)
    return jsonify({"message": t("api.surveys.updated"), "data": item})


@survey_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_survey(pk):
    svc = SurveyService(_db_path)
    svc.delete_survey(pk)
    return jsonify({"message": t("api.surveys.deleted")})
