"""Activity feed API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.primary.auth import token_required, role_required
from education_system.shared.api.primary.validators import get_json_body, require_fields
from education_system.shared.api.primary.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.communication.activity_feed.services.activity_feed_service import ActivityFeedService

activity_feed_bp = Blueprint("activity-feed", __name__, url_prefix="/api/activity-feed")

_db_path = None


def init_activity_feed_routes(db_path=None):
    global _db_path
    _db_path = db_path


@activity_feed_bp.route("", methods=["GET"])
@token_required
def list_activity_feed():
    svc = ActivityFeedService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_all(limit=limit, offset=offset)
    total = len(items)
    return jsonify(paginated_response(items, total))


@activity_feed_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_activity_feed_item(pk):
    svc = ActivityFeedService(_db_path)
    item = svc.get(pk)
    if not item:
        return jsonify({"error": "Not found."}), 404
    return jsonify({"data": item})


@activity_feed_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_activity_feed_item():
    data = get_json_body()
    svc = ActivityFeedService(_db_path)
    result = svc.create(**data)
    return jsonify({"message": "Created.", "data": result}), 201


@activity_feed_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_activity_feed_item(pk):
    data = get_json_body()
    svc = ActivityFeedService(_db_path)
    result = svc.update(pk, **data)
    return jsonify({"message": "Updated.", "data": result})


@activity_feed_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_activity_feed_item(pk):
    svc = ActivityFeedService(_db_path)
    svc.delete(pk)
    return jsonify({"message": "Deleted."})
