"""Clubs API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.student_life.clubs.services.clubs_service import ClubsService

clubs_bp = Blueprint("clubs", __name__, url_prefix="/api/clubs")

_db_path = None


def init_clubs_routes(db_path=None):
    global _db_path
    _db_path = db_path


@clubs_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_club():
    data = get_json_body()
    require_fields(data, "name")
    svc = ClubsService(_db_path)
    result = svc.create_club(name=data["name"], description=data.get("description", ""), day=data.get("day", ""), staff_lead=data.get("staff_lead", ""))
    return jsonify({"message": "Created.", "data": result}), 201


@clubs_bp.route("", methods=["GET"])
@token_required
def list_clubs():
    svc = ClubsService(_db_path)
    result = svc.list_clubs()
    return jsonify({"data": result})


@clubs_bp.route("/<int:club_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_club(club_id):
    svc = ClubsService(_db_path)
    result = svc.delete_club(club_id)
    return jsonify({"message": "Deleted.", "data": result})


@clubs_bp.route("/<int:club_id>/members", methods=["POST"])
@token_required
def add_member(club_id):
    data = get_json_body()
    require_fields(data, "student_id")
    svc = ClubsService(_db_path)
    result = svc.add_member(club_id, data["student_id"])
    return jsonify({"message": "Created.", "data": result}), 201


@clubs_bp.route("/<int:club_id>/members", methods=["GET"])
@token_required
def list_members(club_id):
    svc = ClubsService(_db_path)
    result = svc.list_members(club_id)
    return jsonify({"data": result})


@clubs_bp.route("/<int:club_id>/members/<int:student_id>", methods=["DELETE"])
@token_required
@role_required("admin", "teacher")
def remove_member(club_id, student_id):
    svc = ClubsService(_db_path)
    result = svc.remove_member(club_id, student_id)
    return jsonify({"message": "Deleted.", "data": result})

