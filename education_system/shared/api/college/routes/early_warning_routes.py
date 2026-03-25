"""API routes for early warning."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.early_warning.services.early_warning_service import EarlyWarningService
from education_system.college_system.core.i18n import t

early_warning_bp = Blueprint("early-warning", __name__, url_prefix="/api/early-warning")

_db_path = None


def init_early_warning_routes(db_path=None):
    global _db_path
    _db_path = db_path


@early_warning_bp.route("/alerts", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_alerts():
    svc = EarlyWarningService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_alerts(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@early_warning_bp.route("/alerts/<int:pk>", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_alert(pk):
    svc = EarlyWarningService(_db_path)
    item = svc.get_alert(pk)
    if not item:
        return jsonify({"error": t("api.early_warning.not_found")}), 404
    return jsonify({"data": item})
@early_warning_bp.route("/alerts", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_alert():
    data = get_json_body()
    svc = EarlyWarningService(_db_path)
    result = svc.create_alert(**data)
    return jsonify({"message": t("api.early_warning.created"), "data": result}), 201
@early_warning_bp.route("/alerts/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin', 'staff')
def update_alert(pk):
    data = get_json_body()
    svc = EarlyWarningService(_db_path)
    result = svc.update_alert(pk, **data)
    return jsonify({"message": t("api.early_warning.updated"), "data": result})
@early_warning_bp.route("/alerts/<int:pk>", methods=["DELETE"])
@token_required
@role_required('admin')
def delete_alert(pk):
    svc = EarlyWarningService(_db_path)
    svc.delete_alert(pk)
    return jsonify({"message": t("api.early_warning.deleted")})
@early_warning_bp.route("/alerts/<int:pk>/resolve", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def resolve_alert(pk):
    data = get_json_body()
    svc = EarlyWarningService(_db_path)
    result = svc.resolve_alert(pk, **data)
    return jsonify({"message": t("api.early_warning.success"), "data": result}), 201
@early_warning_bp.route("/rules", methods=["GET"])
@token_required
@role_required('admin')
def list_rules():
    svc = EarlyWarningService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_rules(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@early_warning_bp.route("/rules", methods=["POST"])
@token_required
@role_required('admin')
def create_rule():
    data = get_json_body()
    svc = EarlyWarningService(_db_path)
    result = svc.create_rule(**data)
    return jsonify({"message": t("api.early_warning.created"), "data": result}), 201
@early_warning_bp.route("/stats", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_stats():
    svc = EarlyWarningService(_db_path)
    result = svc.get_stats()
    return jsonify({"data": result})
