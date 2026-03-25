"""Announcements API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.communication.announcements.services.announcement_service import AnnouncementService

announcements_bp = Blueprint("announcements", __name__, url_prefix="/api/announcements")

_db_path = None


def init_announcements_routes(db_path=None):
    global _db_path
    _db_path = db_path


@announcements_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_announcement():
    data = get_json_body()
    require_fields(data, "title", "content")
    svc = AnnouncementService(_db_path)
    result = svc.create(title=data["title"], content=data["content"], author=data.get("author", ""), audience=data.get("audience", "all"))
    return jsonify({"message": "Created.", "data": result}), 201


@announcements_bp.route("", methods=["GET"])
@token_required
def list_announcements():
    svc = AnnouncementService(_db_path)
    result = svc.list_announcements()
    return jsonify({"data": result})


@announcements_bp.route("/<int:ann_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_announcement(ann_id):
    svc = AnnouncementService(_db_path)
    result = svc.delete(ann_id)
    return jsonify({"message": "Deleted.", "data": result})


@announcements_bp.route("/<int:ann_id>/publish", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def toggle_publish(ann_id):
    svc = AnnouncementService(_db_path)
    result = svc.toggle_publish(ann_id)
    return jsonify({"message": "Updated.", "data": result})

