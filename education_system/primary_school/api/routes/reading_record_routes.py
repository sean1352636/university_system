"""Reading Records API routes."""

from flask import Blueprint, jsonify, request

from education_system.primary_school.api.auth import token_required, role_required
from education_system.primary_school.api.validators import get_json_body, require_fields
from education_system.primary_school.api.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.academics.reading_records.services.reading_record_service import ReadingRecordService

reading_records_bp = Blueprint("reading_records", __name__, url_prefix="/api/reading-records")

_db_path = None


def init_reading_records_routes(db_path=None):
    global _db_path
    _db_path = db_path


@reading_records_bp.route("", methods=["GET"])
@token_required
def list_records():
    svc = ReadingRecordService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_records(pupil_id=request.args.get("pupil_id"))
    total = len(items)
    return jsonify(paginated_response(items, total))


@reading_records_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_record(pk):
    svc = ReadingRecordService(_db_path)
    item = svc.get_record(pk)
    if not item:
        return jsonify({"error": "Record not found."}), 404
    return jsonify({"data": dict(item) if hasattr(item, "keys") else item})


@reading_records_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_record():
    data = get_json_body()
    require_fields(data, "pupil_id", "book_title", "reading_level")
    svc = ReadingRecordService(_db_path)
    result = svc.create_record(**data)
    return jsonify({"message": "Record created.", "data": result}), 201


@reading_records_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def update_record(pk):
    data = get_json_body()
    svc = ReadingRecordService(_db_path)
    result = svc.update_record(pk, **data)
    return jsonify({"message": "Record updated.", "data": result})

@reading_records_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_record(pk):
    svc = ReadingRecordService(_db_path)
    svc.delete_record(pk)
    return jsonify({"message": "Record deleted."})