"""Assets API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.primary.auth import token_required, role_required
from education_system.shared.api.primary.validators import get_json_body, require_fields
from education_system.shared.api.primary.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.facilities.assets.services.asset_service import AssetService

assets_bp = Blueprint("assets", __name__, url_prefix="/api/assets")

_db_path = None


def init_assets_routes(db_path=None):
    global _db_path
    _db_path = db_path


@assets_bp.route("", methods=["GET"])
@token_required
def list_assets():
    svc = AssetService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_assets()
    total = len(items)
    return jsonify(paginated_response(items, total))


@assets_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_asset(pk):
    svc = AssetService(_db_path)
    item = svc.get_asset(pk)
    if not item:
        return jsonify({"error": "Asset not found."}), 404
    return jsonify({"data": dict(item) if hasattr(item, "keys") else item})


@assets_bp.route("", methods=["POST"])
@token_required
@role_required("admin")
def create_asset():
    data = get_json_body()
    require_fields(data, "name", "asset_type")
    svc = AssetService(_db_path)
    result = svc.create_asset(**data)
    return jsonify({"message": "Asset created.", "data": result}), 201


@assets_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin")
def update_asset(pk):
    data = get_json_body()
    svc = AssetService(_db_path)
    result = svc.update_asset(pk, **data)
    return jsonify({"message": "Asset updated.", "data": result})

@assets_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_asset(pk):
    svc = AssetService(_db_path)
    svc.delete_asset(pk)
    return jsonify({"message": "Asset deleted."})