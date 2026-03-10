"""API routes for announcements."""

from flask import Blueprint, jsonify, request
from education_system.college_system.api.auth import token_required, role_required
from education_system.college_system.api.validators import get_json_body, require_fields
from education_system.college_system.api.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.announcements.services.announcements_service import AnnouncementService

announcement_bp = Blueprint("announcements", __name__, url_prefix="/api/announcements")

_db_path = None


def init_announcement_routes(db_path=None):
    global _db_path
    _db_path = db_path


@announcement_bp.route("", methods=["GET"])
@token_required
def list_announcements():
    svc = AnnouncementService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_announcements(limit=limit, offset=offset)
    total = svc.count_announcements()
    return jsonify(paginated_response(items, total))


@announcement_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_announcement(pk):
    svc = AnnouncementService(_db_path)
    item = svc.get_announcement(pk)
    if not item:
        return jsonify({"error": "Announcement not found."}), 404
    return jsonify({"data": item})


@announcement_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff", "instructor")
def create_announcement():
    data = get_json_body()
    require_fields(data, "title", "content", "author_id")
    svc = AnnouncementService(_db_path)
    item = svc.create_announcement(**data)
    return jsonify({"message": "Announcement created.", "data": item}), 201


@announcement_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff", "instructor")
def update_announcement(pk):
    data = get_json_body()
    svc = AnnouncementService(_db_path)
    item = svc.update_announcement(pk, **data)
    return jsonify({"message": "Announcement updated.", "data": item})


@announcement_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_announcement(pk):
    svc = AnnouncementService(_db_path)
    svc.delete_announcement(pk)
    return jsonify({"message": "Announcement deleted."})
