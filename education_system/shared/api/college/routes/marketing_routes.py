"""API routes for marketing."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.marketing.services.marketing_service import MarketingService
from education_system.college_system.core.i18n import t

marketing_bp = Blueprint("marketing", __name__, url_prefix="/api/marketing")

_db_path = None


def init_marketing_routes(db_path=None):
    global _db_path
    _db_path = db_path


@marketing_bp.route("/events", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_events():
    svc = MarketingService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_events(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@marketing_bp.route("/events/<int:pk>", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_event(pk):
    svc = MarketingService(_db_path)
    item = svc.get_event(pk)
    if not item:
        return jsonify({"error": t("api.marketing.not_found")}), 404
    return jsonify({"data": item})
@marketing_bp.route("/events", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_event():
    data = get_json_body()
    svc = MarketingService(_db_path)
    result = svc.create_event(**data)
    return jsonify({"message": t("api.marketing.created"), "data": result}), 201
@marketing_bp.route("/events/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin', 'staff')
def update_event(pk):
    data = get_json_body()
    svc = MarketingService(_db_path)
    result = svc.update_event(pk, **data)
    return jsonify({"message": t("api.marketing.updated"), "data": result})
@marketing_bp.route("/events/<int:pk>", methods=["DELETE"])
@token_required
@role_required('admin')
def delete_event(pk):
    svc = MarketingService(_db_path)
    svc.delete_event(pk)
    return jsonify({"message": t("api.marketing.deleted")})
@marketing_bp.route("/campaigns", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_campaigns():
    svc = MarketingService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_campaigns(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@marketing_bp.route("/campaigns", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_campaign():
    data = get_json_body()
    svc = MarketingService(_db_path)
    result = svc.create_campaign(**data)
    return jsonify({"message": t("api.marketing.created"), "data": result}), 201
@marketing_bp.route("/stats", methods=["GET"])
@token_required
@role_required('admin')
def get_stats():
    svc = MarketingService(_db_path)
    result = svc.get_stats()
    return jsonify({"data": result})
