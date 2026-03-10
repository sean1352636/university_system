"""API routes for bulk operations."""

from flask import Blueprint, jsonify, request
from education_system.college_system.api.auth import token_required, role_required
from education_system.college_system.api.validators import get_json_body, require_fields
from education_system.college_system.api.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.bulk_operations.services.bulk_operations_service import BulkOperationService

bulk_operation_bp = Blueprint("bulk-operations", __name__, url_prefix="/api/bulk-operations")

_db_path = None


def init_bulk_operation_routes(db_path=None):
    global _db_path
    _db_path = db_path


@bulk_operation_bp.route("", methods=["GET"])
@token_required
def list_jobs():
    svc = BulkOperationService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_jobs(limit=limit, offset=offset)
    total = svc.count_jobs()
    return jsonify(paginated_response(items, total))


@bulk_operation_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_job(pk):
    svc = BulkOperationService(_db_path)
    item = svc.get_job(pk)
    if not item:
        return jsonify({"error": "Job not found."}), 404
    return jsonify({"data": item})


@bulk_operation_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_job():
    data = get_json_body()
    require_fields(data, "job_type", "initiated_by")
    svc = BulkOperationService(_db_path)
    item = svc.create_job(**data)
    return jsonify({"message": "Job created.", "data": item}), 201


@bulk_operation_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_job(pk):
    data = get_json_body()
    svc = BulkOperationService(_db_path)
    item = svc.update_job(pk, **data)
    return jsonify({"message": "Job updated.", "data": item})


@bulk_operation_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_job(pk):
    svc = BulkOperationService(_db_path)
    svc.delete_job(pk)
    return jsonify({"message": "Job deleted."})
