"""API routes for settings."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.settings.services.settings_service import SettingsService
from education_system.college_system.core.i18n import t

settings_bp = Blueprint("settings", __name__, url_prefix="/api/settings")

_db_path = None


def init_settings_routes(db_path=None):
    global _db_path
    _db_path = db_path


@settings_bp.route("/user", methods=["GET"])
@token_required
def get_all_user_settings():
    svc = SettingsService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.get_all_user_settings(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@settings_bp.route("/user/<key>", methods=["GET"])
@token_required
def get_user_setting(key):
    svc = SettingsService(_db_path)
    item = svc.get_user_setting(key)
    if not item:
        return jsonify({"error": t("api.settings.not_found")}), 404
    return jsonify({"data": item})
@settings_bp.route("/user/<key>", methods=["PUT"])
@token_required
def set_user_setting(key):
    data = get_json_body()
    svc = SettingsService(_db_path)
    result = svc.set_user_setting(key, **data)
    return jsonify({"message": t("api.settings.updated"), "data": result})
@settings_bp.route("/system", methods=["GET"])
@token_required
@role_required('admin')
def get_all_system_settings():
    svc = SettingsService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.get_all_system_settings(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@settings_bp.route("/system/<key>", methods=["GET"])
@token_required
@role_required('admin')
def get_system_setting(key):
    svc = SettingsService(_db_path)
    item = svc.get_system_setting(key)
    if not item:
        return jsonify({"error": t("api.settings.not_found")}), 404
    return jsonify({"data": item})
@settings_bp.route("/system/<key>", methods=["PUT"])
@token_required
@role_required('admin')
def set_system_setting(key):
    data = get_json_body()
    svc = SettingsService(_db_path)
    result = svc.set_system_setting(key, **data)
    return jsonify({"message": t("api.settings.updated"), "data": result})
