"""API routes for recruitment."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.recruitment.services.recruitment_service import RecruitmentService
from education_system.college_system.core.i18n import t

recruitment_bp = Blueprint("recruitment", __name__, url_prefix="/api/recruitment")

_db_path = None


def init_recruitment_routes(db_path=None):
    global _db_path
    _db_path = db_path


@recruitment_bp.route("/vacancies", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_vacancies():
    svc = RecruitmentService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_vacancies(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@recruitment_bp.route("/vacancies/<int:pk>", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_vacancy(pk):
    svc = RecruitmentService(_db_path)
    item = svc.get_vacancy(pk)
    if not item:
        return jsonify({"error": t("api.recruitment.not_found")}), 404
    return jsonify({"data": item})
@recruitment_bp.route("/vacancies", methods=["POST"])
@token_required
@role_required('admin')
def create_vacancy():
    data = get_json_body()
    svc = RecruitmentService(_db_path)
    result = svc.create_vacancy(**data)
    return jsonify({"message": t("api.recruitment.created"), "data": result}), 201
@recruitment_bp.route("/vacancies/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin')
def update_vacancy(pk):
    data = get_json_body()
    svc = RecruitmentService(_db_path)
    result = svc.update_vacancy(pk, **data)
    return jsonify({"message": t("api.recruitment.updated"), "data": result})
@recruitment_bp.route("/applications", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_applications():
    svc = RecruitmentService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_applications(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@recruitment_bp.route("/applications/<int:pk>", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_application(pk):
    svc = RecruitmentService(_db_path)
    item = svc.get_application(pk)
    if not item:
        return jsonify({"error": t("api.recruitment.not_found")}), 404
    return jsonify({"data": item})
@recruitment_bp.route("/applications", methods=["POST"])
@token_required
def create_application():
    data = get_json_body()
    svc = RecruitmentService(_db_path)
    result = svc.create_application(**data)
    return jsonify({"message": t("api.recruitment.created"), "data": result}), 201
@recruitment_bp.route("/stats", methods=["GET"])
@token_required
@role_required('admin')
def get_stats():
    svc = RecruitmentService(_db_path)
    result = svc.get_stats()
    return jsonify({"data": result})
