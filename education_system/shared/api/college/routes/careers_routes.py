"""API routes for careers."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.careers.services.careers_service import CareersService
from education_system.college_system.core.i18n import t

careers_bp = Blueprint("careers", __name__, url_prefix="/api/careers")

_db_path = None


def init_careers_routes(db_path=None):
    global _db_path
    _db_path = db_path


@careers_bp.route("/activities", methods=["GET"])
@token_required
def list_activities():
    svc = CareersService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_activities(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@careers_bp.route("/activities", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_activity():
    data = get_json_body()
    svc = CareersService(_db_path)
    result = svc.create_activity(**data)
    return jsonify({"message": t("api.careers.created"), "data": result}), 201
@careers_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required('admin')
def delete_record(pk):
    svc = CareersService(_db_path)
    svc.delete_record(pk)
    return jsonify({"message": t("api.careers.deleted")})
@careers_bp.route("/work-experience", methods=["GET"])
@token_required
def list_work_experience():
    svc = CareersService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_work_experience(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@careers_bp.route("/work-experience", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_work_experience():
    data = get_json_body()
    svc = CareersService(_db_path)
    result = svc.create_work_experience(**data)
    return jsonify({"message": t("api.careers.created"), "data": result}), 201
