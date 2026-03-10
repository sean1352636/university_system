"""Pastoral API routes."""

from flask import Blueprint, jsonify, request

from education_system.primary_school.api.auth import token_required, role_required
from education_system.primary_school.api.validators import get_json_body, require_fields
from education_system.primary_school.api.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.pastoral_care.pastoral.services.pastoral_service import PastoralService

pastoral_bp = Blueprint("pastoral", __name__, url_prefix="/api/pastoral")

_db_path = None


def init_pastoral_routes(db_path=None):
    global _db_path
    _db_path = db_path


@pastoral_bp.route("", methods=["GET"])
@token_required
def list_notes():
    svc = PastoralService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_notes(pupil_id=request.args.get("pupil_id"))
    total = len(items)
    return jsonify(paginated_response(items, total))


@pastoral_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_note(pk):
    svc = PastoralService(_db_path)
    item = svc.get_note(pk)
    if not item:
        return jsonify({"error": "Note not found."}), 404
    return jsonify({"data": dict(item) if hasattr(item, "keys") else item})


@pastoral_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_note():
    data = get_json_body()
    require_fields(data, "pupil_id", "note")
    svc = PastoralService(_db_path)
    result = svc.create_note(**data)
    return jsonify({"message": "Note created.", "data": result}), 201


@pastoral_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def update_note(pk):
    data = get_json_body()
    svc = PastoralService(_db_path)
    result = svc.update_note(pk, **data)
    return jsonify({"message": "Note updated.", "data": result})

@pastoral_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_note(pk):
    svc = PastoralService(_db_path)
    svc.delete_note(pk)
    return jsonify({"message": "Note deleted."})