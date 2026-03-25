"""Settings API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.primary.auth import token_required, role_required
from education_system.shared.api.primary.validators import get_json_body, require_fields
from education_system.primary_school.modules.domain.admin.settings.services.settings_service import SettingsService

settings_bp = Blueprint("settings", __name__, url_prefix="/api/settings")

_db_path = None


def init_settings_routes(db_path=None):
    global _db_path
    _db_path = db_path


@settings_bp.route("", methods=["GET"])
@token_required
def list_settings():
    svc = SettingsService(_db_path)
    items = svc.list_settings()
    return jsonify({"data": items})


@settings_bp.route("/<key>", methods=["GET"])
@token_required
def get_setting(key):
    svc = SettingsService(_db_path)
    val = svc.get_setting(key)
    return jsonify({"data": {"key": key, "value": val}})


@settings_bp.route("/<key>", methods=["PUT"])
@token_required
@role_required("admin")
def update_setting(key):
    data = get_json_body()
    require_fields(data, "value")
    svc = SettingsService(_db_path)
    svc.update_setting(key, data["value"])
    return jsonify({"message": "Setting updated."})
