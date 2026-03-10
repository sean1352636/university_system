"""Phonics API routes."""

from flask import Blueprint, jsonify, request

from education_system.primary_school.api.auth import token_required, role_required
from education_system.primary_school.api.validators import get_json_body, require_fields
from education_system.primary_school.api.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.academics.phonics.services.phonics_service import PhonicsService

phonics_bp = Blueprint("phonics", __name__, url_prefix="/api/phonics")

_db_path = None


def init_phonics_routes(db_path=None):
    global _db_path
    _db_path = db_path


@phonics_bp.route("", methods=["GET"])
@token_required
def list_results():
    svc = PhonicsService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_results(pupil_id=request.args.get("pupil_id"), year=request.args.get("year"))
    total = len(items)
    return jsonify(paginated_response(items, total))


@phonics_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_result(pk):
    svc = PhonicsService(_db_path)
    item = svc.get_result(pk)
    if not item:
        return jsonify({"error": "Result not found."}), 404
    return jsonify({"data": dict(item) if hasattr(item, "keys") else item})


@phonics_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_result():
    data = get_json_body()
    require_fields(data, "pupil_id", "score", "year")
    svc = PhonicsService(_db_path)
    result = svc.create_result(**data)
    return jsonify({"message": "Result created.", "data": result}), 201


@phonics_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def update_result(pk):
    data = get_json_body()
    svc = PhonicsService(_db_path)
    result = svc.update_result(pk, **data)
    return jsonify({"message": "Result updated.", "data": result})

@phonics_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_result(pk):
    svc = PhonicsService(_db_path)
    svc.delete_result(pk)
    return jsonify({"message": "Result deleted."})