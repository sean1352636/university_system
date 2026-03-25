"""Assets API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.facilities.assets.services.asset_service import AssetService

assets_bp = Blueprint("assets", __name__, url_prefix="/api/assets")

_db_path = None


def init_assets_routes(db_path=None):
    global _db_path
    _db_path = db_path


@assets_bp.route("", methods=["POST"])
@token_required
@role_required("admin")
def add_asset():
    data = get_json_body()
    require_fields(data, "name", "category")
    svc = AssetService(_db_path)
    result = svc.add_asset(name=data["name"], category=data["category"], location=data.get("location", ""), serial_number=data.get("serial_number", ""))
    return jsonify({"message": "Created.", "data": result}), 201


@assets_bp.route("", methods=["GET"])
@token_required
def list_assets():
    svc = AssetService(_db_path)
    result = svc.list_assets()
    return jsonify({"data": result})


@assets_bp.route("/<int:asset_id>", methods=["PUT"])
@token_required
@role_required("admin")
def update_asset(asset_id):
    data = get_json_body()
    svc = AssetService(_db_path)
    result = svc.update_asset(asset_id, **{k: v for k, v in data.items() if k != 'asset_id'})
    return jsonify({"message": "Updated.", "data": result})


@assets_bp.route("/<int:asset_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_asset(asset_id):
    svc = AssetService(_db_path)
    result = svc.delete_asset(asset_id)
    return jsonify({"message": "Deleted.", "data": result})


@assets_bp.route("/summary", methods=["GET"])
@token_required
@role_required("admin")
def asset_summary():
    svc = AssetService(_db_path)
    result = svc.asset_summary()
    return jsonify({"data": result})

