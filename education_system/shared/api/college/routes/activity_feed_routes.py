"""API routes for activity feed."""

from flask import Blueprint, jsonify, request
from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.activity_feed.services.activity_feed_service import ActivityFeedService
from education_system.college_system.core.i18n import t

activity_feed_bp = Blueprint("activity-feed", __name__, url_prefix="/api/activity-feed")

_db_path = None


def init_activity_feed_routes(db_path=None):
    global _db_path
    _db_path = db_path


@activity_feed_bp.route("", methods=["GET"])
@token_required
def list_feed_items():
    svc = ActivityFeedService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_feed_items(limit=limit, offset=offset)
    total = svc.count_feed_items()
    return jsonify(paginated_response(items, total))


@activity_feed_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_feed_item(pk):
    svc = ActivityFeedService(_db_path)
    item = svc.get_feed_item(pk)
    if not item:
        return jsonify({"error": t("api.common.not_found")}), 404
    return jsonify({"data": item})


@activity_feed_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff", "instructor")
def create_feed_item():
    data = get_json_body()
    require_fields(data, "user_id", "activity_type", "title")
    svc = ActivityFeedService(_db_path)
    item = svc.create_feed_item(**data)
    return jsonify({"message": t("api.common.created"), "data": item}), 201


@activity_feed_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff", "instructor")
def update_feed_item(pk):
    data = get_json_body()
    svc = ActivityFeedService(_db_path)
    item = svc.update_feed_item(pk, **data)
    return jsonify({"message": t("api.common.updated"), "data": item})


@activity_feed_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_feed_item(pk):
    svc = ActivityFeedService(_db_path)
    svc.delete_feed_item(pk)
    return jsonify({"message": t("api.common.deleted")})
