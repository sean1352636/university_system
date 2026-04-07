"""Pupil support API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.primary.auth import token_required, role_required
from education_system.shared.api.primary.validators import get_json_body, require_fields
from education_system.shared.api.primary.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.pupil_life.pupil_support.services.pupil_support_service import PupilSupportService

pupil_support_bp = Blueprint("pupil-support", __name__, url_prefix="/api/pupil-support")

_db_path = None


def init_pupil_support_routes(db_path=None):
    global _db_path
    _db_path = db_path


@pupil_support_bp.route("", methods=["GET"])
@token_required
def list_pupil_support():
    svc = PupilSupportService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_all(limit=limit, offset=offset)
    total = len(items)
    return jsonify(paginated_response(items, total))


@pupil_support_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_pupil_support_item(pk):
    svc = PupilSupportService(_db_path)
    item = svc.get(pk)
    if not item:
        return jsonify({"error": "Not found."}), 404
    return jsonify({"data": item})


@pupil_support_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_pupil_support_item():
    data = get_json_body()
    svc = PupilSupportService(_db_path)
    result = svc.create(**data)
    return jsonify({"message": "Created.", "data": result}), 201


@pupil_support_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_pupil_support_item(pk):
    data = get_json_body()
    svc = PupilSupportService(_db_path)
    result = svc.update(pk, **data)
    return jsonify({"message": "Updated.", "data": result})


@pupil_support_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_pupil_support_item(pk):
    svc = PupilSupportService(_db_path)
    svc.delete(pk)
    return jsonify({"message": "Deleted."})
