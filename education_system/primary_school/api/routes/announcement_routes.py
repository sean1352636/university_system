"""Announcements API routes."""

from flask import Blueprint, jsonify, request

from education_system.primary_school.api.auth import token_required, role_required
from education_system.primary_school.api.validators import get_json_body, require_fields
from education_system.primary_school.api.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.communication.announcements.services.announcement_service import AnnouncementService

announcements_bp = Blueprint("announcements", __name__, url_prefix="/api/announcements")

_db_path = None


def init_announcements_routes(db_path=None):
    global _db_path
    _db_path = db_path


@announcements_bp.route("", methods=["GET"])
@token_required
def list_announcements():
    svc = AnnouncementService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_announcements()
    total = len(items)
    return jsonify(paginated_response(items, total))


@announcements_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_announcement(pk):
    svc = AnnouncementService(_db_path)
    item = svc.get_announcement(pk)
    if not item:
        return jsonify({"error": "Announcement not found."}), 404
    return jsonify({"data": dict(item) if hasattr(item, "keys") else item})


@announcements_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_announcement():
    data = get_json_body()
    require_fields(data, "title", "content")
    svc = AnnouncementService(_db_path)
    result = svc.create_announcement(**data)
    return jsonify({"message": "Announcement created.", "data": result}), 201


@announcements_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def update_announcement(pk):
    data = get_json_body()
    svc = AnnouncementService(_db_path)
    result = svc.update_announcement(pk, **data)
    return jsonify({"message": "Announcement updated.", "data": result})

@announcements_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_announcement(pk):
    svc = AnnouncementService(_db_path)
    svc.delete_announcement(pk)
    return jsonify({"message": "Announcement deleted."})