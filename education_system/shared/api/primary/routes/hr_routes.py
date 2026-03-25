"""Hr API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.primary.auth import token_required, role_required
from education_system.shared.api.primary.validators import get_json_body, require_fields
from education_system.shared.api.primary.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.staff.hr.services.hr_service import HRService

hr_bp = Blueprint("hr", __name__, url_prefix="/api/hr")

_db_path = None


def init_hr_routes(db_path=None):
    global _db_path
    _db_path = db_path


@hr_bp.route("", methods=["GET"])
@token_required
def list_records():
    svc = HRService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_records()
    total = len(items)
    return jsonify(paginated_response(items, total))


@hr_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_record(pk):
    svc = HRService(_db_path)
    item = svc.get_record(pk)
    if not item:
        return jsonify({"error": "Record not found."}), 404
    return jsonify({"data": dict(item) if hasattr(item, "keys") else item})


@hr_bp.route("", methods=["POST"])
@token_required
@role_required("admin")
def create_record():
    data = get_json_body()
    require_fields(data, "staff_id", "first_name", "last_name")
    svc = HRService(_db_path)
    result = svc.create_record(**data)
    return jsonify({"message": "Record created.", "data": result}), 201


@hr_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin")
def update_record(pk):
    data = get_json_body()
    svc = HRService(_db_path)
    result = svc.update_record(pk, **data)
    return jsonify({"message": "Record updated.", "data": result})

@hr_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_record(pk):
    svc = HRService(_db_path)
    svc.delete_record(pk)
    return jsonify({"message": "Record deleted."})