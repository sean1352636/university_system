"""API routes for study programmes."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.study_programmes.services.study_programmes_service import StudyProgrammesService
from education_system.college_system.core.i18n import t

study_programmes_bp = Blueprint("study-programmes", __name__, url_prefix="/api/study-programmes")

_db_path = None


def init_study_programmes_routes(db_path=None):
    global _db_path
    _db_path = db_path


@study_programmes_bp.route("", methods=["GET"])
@token_required
def list_programmes():
    svc = StudyProgrammesService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_programmes(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@study_programmes_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_programme(pk):
    svc = StudyProgrammesService(_db_path)
    item = svc.get_programme(pk)
    if not item:
        return jsonify({"error": t("api.study_programmes.not_found")}), 404
    return jsonify({"data": item})
@study_programmes_bp.route("", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_programme():
    data = get_json_body()
    svc = StudyProgrammesService(_db_path)
    result = svc.create_programme(**data)
    return jsonify({"message": t("api.study_programmes.created"), "data": result}), 201
@study_programmes_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin', 'staff')
def update_programme(pk):
    data = get_json_body()
    svc = StudyProgrammesService(_db_path)
    result = svc.update_programme(pk, **data)
    return jsonify({"message": t("api.study_programmes.updated"), "data": result})
@study_programmes_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required('admin')
def delete_programme(pk):
    svc = StudyProgrammesService(_db_path)
    svc.delete_programme(pk)
    return jsonify({"message": t("api.study_programmes.deleted")})
@study_programmes_bp.route("/<int:pk>/components", methods=["GET"])
@token_required
def list_components(pk):
    svc = StudyProgrammesService(_db_path)
    result = svc.list_components(pk)
    return jsonify({"data": result})
@study_programmes_bp.route("/<int:pk>/components", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_component(pk):
    data = get_json_body()
    svc = StudyProgrammesService(_db_path)
    result = svc.create_component(pk, **data)
    return jsonify({"message": t("api.study_programmes.success"), "data": result}), 201
@study_programmes_bp.route("/stats", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_stats():
    svc = StudyProgrammesService(_db_path)
    result = svc.get_stats()
    return jsonify({"data": result})
