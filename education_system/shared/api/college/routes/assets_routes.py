"""API routes for assets."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.assets.services.assets_service import AssetsService
from education_system.college_system.core.i18n import t

assets_bp = Blueprint("assets", __name__, url_prefix="/api/assets")

_db_path = None


def init_assets_routes(db_path=None):
    global _db_path
    _db_path = db_path


@assets_bp.route("/loans", methods=["GET"])
@token_required
def list_loans():
    svc = AssetsService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_loans(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@assets_bp.route("/loans/<int:pk>", methods=["GET"])
@token_required
def get_loan(pk):
    svc = AssetsService(_db_path)
    item = svc.get_loan(pk)
    if not item:
        return jsonify({"error": t("api.assets.not_found")}), 404
    return jsonify({"data": item})
@assets_bp.route("/loans", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_loan():
    data = get_json_body()
    svc = AssetsService(_db_path)
    result = svc.create_loan(**data)
    return jsonify({"message": t("api.assets.created"), "data": result}), 201
@assets_bp.route("/loans/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin', 'staff')
def update_loan(pk):
    data = get_json_body()
    svc = AssetsService(_db_path)
    result = svc.update_loan(pk, **data)
    return jsonify({"message": t("api.assets.updated"), "data": result})
@assets_bp.route("/loans/<int:pk>/return", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def return_asset(pk):
    data = get_json_body()
    svc = AssetsService(_db_path)
    result = svc.return_asset(pk, **data)
    return jsonify({"message": t("api.assets.success"), "data": result}), 201
@assets_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required('admin')
def delete_asset(pk):
    svc = AssetsService(_db_path)
    svc.delete_asset(pk)
    return jsonify({"message": t("api.assets.deleted")})
