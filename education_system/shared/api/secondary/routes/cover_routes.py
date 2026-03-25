"""Cover API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.staff.cover.services.cover_service import CoverService

cover_bp = Blueprint("cover", __name__, url_prefix="/api/cover")

_db_path = None


def init_cover_routes(db_path=None):
    global _db_path
    _db_path = db_path


@cover_bp.route("", methods=["POST"])
@token_required
@role_required("admin")
def create_cover():
    data = get_json_body()
    require_fields(data, "absent_staff", "date", "period")
    svc = CoverService(_db_path)
    result = svc.create_cover(absent_staff=data["absent_staff"], date=data["date"], period=data["period"], subject=data.get("subject", ""), room=data.get("room", ""))
    return jsonify({"message": "Created.", "data": result}), 201


@cover_bp.route("", methods=["GET"])
@token_required
def list_covers():
    svc = CoverService(_db_path)
    result = svc.list_covers()
    return jsonify({"data": result})


@cover_bp.route("/<int:cover_id>/assign", methods=["PUT"])
@token_required
@role_required("admin")
def assign_cover(cover_id):
    data = get_json_body()
    require_fields(data, "cover_staff")
    svc = CoverService(_db_path)
    result = svc.assign_cover(cover_id, data["cover_staff"])
    return jsonify({"message": "Updated.", "data": result})


@cover_bp.route("/<int:cover_id>/complete", methods=["PUT"])
@token_required
@role_required("admin")
def complete_cover(cover_id):
    svc = CoverService(_db_path)
    result = svc.complete_cover(cover_id)
    return jsonify({"message": "Updated.", "data": result})


@cover_bp.route("/<int:cover_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_cover(cover_id):
    svc = CoverService(_db_path)
    result = svc.delete_cover(cover_id)
    return jsonify({"message": "Deleted.", "data": result})

