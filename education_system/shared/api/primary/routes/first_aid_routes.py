"""First aid API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.primary.auth import token_required, role_required
from education_system.shared.api.primary.validators import get_json_body, require_fields
from education_system.shared.api.primary.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.staff.first_aid.services.first_aid_service import FirstAidService

first_aid_bp = Blueprint("first-aid", __name__, url_prefix="/api/first-aid")

_db_path = None


def init_first_aid_routes(db_path=None):
    global _db_path
    _db_path = db_path


@first_aid_bp.route("", methods=["GET"])
@token_required
def list_first_aid():
    svc = FirstAidService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_all(limit=limit, offset=offset)
    total = len(items)
    return jsonify(paginated_response(items, total))


@first_aid_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_first_aid_item(pk):
    svc = FirstAidService(_db_path)
    item = svc.get(pk)
    if not item:
        return jsonify({"error": "Not found."}), 404
    return jsonify({"data": item})


@first_aid_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_first_aid_item():
    data = get_json_body()
    svc = FirstAidService(_db_path)
    result = svc.create(**data)
    return jsonify({"message": "Created.", "data": result}), 201


@first_aid_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_first_aid_item(pk):
    data = get_json_body()
    svc = FirstAidService(_db_path)
    result = svc.update(pk, **data)
    return jsonify({"message": "Updated.", "data": result})


@first_aid_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_first_aid_item(pk):
    svc = FirstAidService(_db_path)
    svc.delete(pk)
    return jsonify({"message": "Deleted."})
