"""API routes for parents evening."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.parents_evening.services.parents_evening_service import ParentsEveningService
from education_system.college_system.core.i18n import t

parents_evening_bp = Blueprint("parents-evening", __name__, url_prefix="/api/parents-evening")

_db_path = None


def init_parents_evening_routes(db_path=None):
    global _db_path
    _db_path = db_path


@parents_evening_bp.route("", methods=["GET"])
@token_required
def list_evenings():
    svc = ParentsEveningService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_evenings(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@parents_evening_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_evening(pk):
    svc = ParentsEveningService(_db_path)
    item = svc.get_evening(pk)
    if not item:
        return jsonify({"error": t("api.parents_evening.not_found")}), 404
    return jsonify({"data": item})
@parents_evening_bp.route("", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_evening():
    data = get_json_body()
    svc = ParentsEveningService(_db_path)
    result = svc.create_evening(**data)
    return jsonify({"message": t("api.parents_evening.created"), "data": result}), 201
@parents_evening_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin', 'staff')
def update_evening(pk):
    data = get_json_body()
    svc = ParentsEveningService(_db_path)
    result = svc.update_evening(pk, **data)
    return jsonify({"message": t("api.parents_evening.updated"), "data": result})
@parents_evening_bp.route("/<int:pk>/slots", methods=["GET"])
@token_required
def list_slots(pk):
    svc = ParentsEveningService(_db_path)
    result = svc.list_slots(pk)
    return jsonify({"data": result})
@parents_evening_bp.route("/<int:pk>/slots", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_slot(pk):
    data = get_json_body()
    svc = ParentsEveningService(_db_path)
    result = svc.create_slot(pk, **data)
    return jsonify({"message": t("api.parents_evening.success"), "data": result}), 201
@parents_evening_bp.route("/slots/<int:pk>/book", methods=["POST"])
@token_required
def book_slot(pk):
    data = get_json_body()
    svc = ParentsEveningService(_db_path)
    result = svc.book_slot(pk, **data)
    return jsonify({"message": t("api.parents_evening.success"), "data": result}), 201
@parents_evening_bp.route("/slots/<int:pk>/cancel", methods=["POST"])
@token_required
def cancel_slot(pk):
    data = get_json_body()
    svc = ParentsEveningService(_db_path)
    result = svc.cancel_slot(pk, **data)
    return jsonify({"message": t("api.parents_evening.success"), "data": result}), 201
