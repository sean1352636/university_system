"""API routes for gdpr & data protection."""

from flask import Blueprint, jsonify, request
from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.gdpr.services.gdpr_service import GDPRService
from education_system.college_system.core.i18n import t

gdpr_bp = Blueprint("gdpr", __name__, url_prefix="/api/gdpr")

_db_path = None


def init_gdpr_routes(db_path=None):
    global _db_path
    _db_path = db_path


@gdpr_bp.route("", methods=["GET"])
@token_required
def list_subjects():
    svc = GDPRService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_subjects(limit=limit, offset=offset)
    total = svc.count_subjects()
    return jsonify(paginated_response(items, total))


@gdpr_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_subject(pk):
    svc = GDPRService(_db_path)
    item = svc.get_subject(pk)
    if not item:
        return jsonify({"error": t("api.gdpr.not_found")}), 404
    return jsonify({"data": item})


@gdpr_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_subject():
    data = get_json_body()
    require_fields(data, "user_id")
    svc = GDPRService(_db_path)
    item = svc.create_subject(**data)
    return jsonify({"message": t("api.gdpr.created"), "data": item}), 201


@gdpr_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_subject(pk):
    data = get_json_body()
    svc = GDPRService(_db_path)
    item = svc.update_subject(pk, **data)
    return jsonify({"message": t("api.gdpr.updated"), "data": item})


@gdpr_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_subject(pk):
    svc = GDPRService(_db_path)
    svc.delete_subject(pk)
    return jsonify({"message": t("api.gdpr.deleted")})
