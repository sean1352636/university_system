"""Clubs API routes."""

from flask import Blueprint, jsonify, request

from education_system.primary_school.api.auth import token_required, role_required
from education_system.primary_school.api.validators import get_json_body, require_fields
from education_system.primary_school.api.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.pupil_life.clubs.services.club_service import ClubService

clubs_bp = Blueprint("clubs", __name__, url_prefix="/api/clubs")

_db_path = None


def init_clubs_routes(db_path=None):
    global _db_path
    _db_path = db_path


@clubs_bp.route("", methods=["GET"])
@token_required
def list_clubs():
    svc = ClubService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_clubs()
    total = len(items)
    return jsonify(paginated_response(items, total))


@clubs_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_club(pk):
    svc = ClubService(_db_path)
    item = svc.get_club(pk)
    if not item:
        return jsonify({"error": "Club not found."}), 404
    return jsonify({"data": dict(item) if hasattr(item, "keys") else item})


@clubs_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_club():
    data = get_json_body()
    require_fields(data, "name")
    svc = ClubService(_db_path)
    result = svc.create_club(**data)
    return jsonify({"message": "Club created.", "data": result}), 201


@clubs_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def update_club(pk):
    data = get_json_body()
    svc = ClubService(_db_path)
    result = svc.update_club(pk, **data)
    return jsonify({"message": "Club updated.", "data": result})

@clubs_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_club(pk):
    svc = ClubService(_db_path)
    svc.delete_club(pk)
    return jsonify({"message": "Club deleted."})