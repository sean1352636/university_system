"""API routes for cover."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.cover.services.cover_service import CoverService
from education_system.college_system.core.i18n import t

cover_bp = Blueprint("cover", __name__, url_prefix="/api/cover")

_db_path = None


def init_cover_routes(db_path=None):
    global _db_path
    _db_path = db_path


@cover_bp.route("", methods=["GET"])
@token_required
def list_arrangements():
    svc = CoverService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_arrangements(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@cover_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_arrangement(pk):
    svc = CoverService(_db_path)
    item = svc.get_arrangement(pk)
    if not item:
        return jsonify({"error": t("api.cover.not_found")}), 404
    return jsonify({"data": item})
@cover_bp.route("", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_arrangement():
    data = get_json_body()
    svc = CoverService(_db_path)
    result = svc.create_arrangement(**data)
    return jsonify({"message": t("api.cover.created"), "data": result}), 201
@cover_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin', 'staff')
def update_arrangement(pk):
    data = get_json_body()
    svc = CoverService(_db_path)
    result = svc.update_arrangement(pk, **data)
    return jsonify({"message": t("api.cover.updated"), "data": result})
@cover_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required('admin')
def delete_arrangement(pk):
    svc = CoverService(_db_path)
    svc.delete_arrangement(pk)
    return jsonify({"message": t("api.cover.deleted")})
@cover_bp.route("/today", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_today_cover():
    svc = CoverService(_db_path)
    result = svc.get_today_cover()
    return jsonify({"data": result})
