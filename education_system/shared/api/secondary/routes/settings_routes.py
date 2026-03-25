"""Settings API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.admin.settings.services.settings_service import SettingsService

settings_bp = Blueprint("settings", __name__, url_prefix="/api/settings")

_db_path = None


def init_settings_routes(db_path=None):
    global _db_path
    _db_path = db_path


@settings_bp.route("", methods=["GET"])
@token_required
@role_required("admin")
def list_settings():
    svc = SettingsService(_db_path)
    result = svc.list_settings()
    return jsonify({"data": result})


@settings_bp.route("/<key>", methods=["GET"])
@token_required
@role_required("admin")
def get_setting(key):
    svc = SettingsService(_db_path)
    result = svc.get(key)
    return jsonify({"data": result})


@settings_bp.route("/<key>", methods=["PUT"])
@token_required
@role_required("admin")
def set_setting(key):
    data = get_json_body()
    require_fields(data, "value")
    svc = SettingsService(_db_path)
    result = svc.set(key, data["value"])
    return jsonify({"message": "Updated.", "data": result})

