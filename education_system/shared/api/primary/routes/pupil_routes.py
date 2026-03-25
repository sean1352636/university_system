"""Pupils API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.primary.auth import token_required, role_required
from education_system.shared.api.primary.validators import get_json_body, require_fields
from education_system.shared.api.primary.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.academics.pupils.services.pupil_service import PupilService

pupils_bp = Blueprint("pupils", __name__, url_prefix="/api/pupils")

_db_path = None


def init_pupils_routes(db_path=None):
    global _db_path
    _db_path = db_path


@pupils_bp.route("", methods=["GET"])
@token_required
def list_pupils():
    svc = PupilService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_pupils(year_group=request.args.get("year_group"), status=request.args.get("status"), search=request.args.get("search"))
    total = len(items)
    return jsonify(paginated_response(items, total))


@pupils_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_pupil(pk):
    svc = PupilService(_db_path)
    item = svc.get_pupil(pk)
    if not item:
        return jsonify({"error": "Pupil not found."}), 404
    return jsonify({"data": dict(item) if hasattr(item, "keys") else item})


@pupils_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_pupil():
    data = get_json_body()
    require_fields(data, "first_name", "last_name")
    svc = PupilService(_db_path)
    result = svc.create_pupil(**data)
    return jsonify({"message": "Pupil created.", "data": result}), 201


@pupils_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def update_pupil(pk):
    data = get_json_body()
    svc = PupilService(_db_path)
    result = svc.update_pupil(pk, **data)
    return jsonify({"message": "Pupil updated.", "data": result})

@pupils_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_pupil(pk):
    svc = PupilService(_db_path)
    svc.delete_pupil(pk)
    return jsonify({"message": "Pupil deleted."})