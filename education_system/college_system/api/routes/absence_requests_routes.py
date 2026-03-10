"""API routes for absence requests."""

from flask import Blueprint, jsonify, request
from education_system.college_system.api.auth import token_required, role_required
from education_system.college_system.api.validators import get_json_body, require_fields
from education_system.college_system.api.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.absence_requests.services.absence_requests_service import AbsenceRequestService

absence_request_bp = Blueprint("absence-requests", __name__, url_prefix="/api/absence-requests")

_db_path = None


def init_absence_request_routes(db_path=None):
    global _db_path
    _db_path = db_path


@absence_request_bp.route("", methods=["GET"])
@token_required
def list_requests():
    svc = AbsenceRequestService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_requests(limit=limit, offset=offset)
    total = svc.count_requests()
    return jsonify(paginated_response(items, total))


@absence_request_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_request(pk):
    svc = AbsenceRequestService(_db_path)
    item = svc.get_request(pk)
    if not item:
        return jsonify({"error": "Request not found."}), 404
    return jsonify({"data": item})


@absence_request_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_request():
    data = get_json_body()
    require_fields(data, "staff_id", "absence_type", "start_date", "end_date")
    svc = AbsenceRequestService(_db_path)
    item = svc.create_request(**data)
    return jsonify({"message": "Request created.", "data": item}), 201


@absence_request_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_request(pk):
    data = get_json_body()
    svc = AbsenceRequestService(_db_path)
    item = svc.update_request(pk, **data)
    return jsonify({"message": "Request updated.", "data": item})


@absence_request_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_request(pk):
    svc = AbsenceRequestService(_db_path)
    svc.delete_request(pk)
    return jsonify({"message": "Request deleted."})
