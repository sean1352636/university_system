"""API routes for lettings."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.lettings.services.lettings_service import LettingsService
from education_system.college_system.core.i18n import t

lettings_bp = Blueprint("lettings", __name__, url_prefix="/api/lettings")

_db_path = None


def init_lettings_routes(db_path=None):
    global _db_path
    _db_path = db_path


@lettings_bp.route("/bookings", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_bookings():
    svc = LettingsService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_bookings(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@lettings_bp.route("/bookings/<int:pk>", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_booking(pk):
    svc = LettingsService(_db_path)
    item = svc.get_booking(pk)
    if not item:
        return jsonify({"error": t("api.lettings.not_found")}), 404
    return jsonify({"data": item})
@lettings_bp.route("/bookings", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_booking():
    data = get_json_body()
    svc = LettingsService(_db_path)
    result = svc.create_booking(**data)
    return jsonify({"message": t("api.lettings.created"), "data": result}), 201
@lettings_bp.route("/bookings/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin', 'staff')
def update_booking(pk):
    data = get_json_body()
    svc = LettingsService(_db_path)
    result = svc.update_booking(pk, **data)
    return jsonify({"message": t("api.lettings.updated"), "data": result})
@lettings_bp.route("/bookings/<int:pk>", methods=["DELETE"])
@token_required
@role_required('admin')
def delete_booking(pk):
    svc = LettingsService(_db_path)
    svc.delete_booking(pk)
    return jsonify({"message": t("api.lettings.deleted")})
@lettings_bp.route("/contracts", methods=["GET"])
@token_required
@role_required('admin')
def list_contracts():
    svc = LettingsService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_contracts(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@lettings_bp.route("/contracts", methods=["POST"])
@token_required
@role_required('admin')
def create_contract():
    data = get_json_body()
    svc = LettingsService(_db_path)
    result = svc.create_contract(**data)
    return jsonify({"message": t("api.lettings.created"), "data": result}), 201
@lettings_bp.route("/stats", methods=["GET"])
@token_required
@role_required('admin')
def get_stats():
    svc = LettingsService(_db_path)
    result = svc.get_stats()
    return jsonify({"data": result})
