"""API routes for transport."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.transport.services.transport_service import TransportService
from education_system.college_system.core.i18n import t

transport_bp = Blueprint("transport", __name__, url_prefix="/api/transport")

_db_path = None


def init_transport_routes(db_path=None):
    global _db_path
    _db_path = db_path


@transport_bp.route("", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_records():
    svc = TransportService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_records(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@transport_bp.route("/<int:pk>", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_record(pk):
    svc = TransportService(_db_path)
    item = svc.get_record(pk)
    if not item:
        return jsonify({"error": t("api.transport.not_found")}), 404
    return jsonify({"data": item})
@transport_bp.route("", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_record():
    data = get_json_body()
    svc = TransportService(_db_path)
    result = svc.create_record(**data)
    return jsonify({"message": t("api.transport.created"), "data": result}), 201
@transport_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin', 'staff')
def update_record(pk):
    data = get_json_body()
    svc = TransportService(_db_path)
    result = svc.update_record(pk, **data)
    return jsonify({"message": t("api.transport.updated"), "data": result})
@transport_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required('admin')
def delete_record(pk):
    svc = TransportService(_db_path)
    svc.delete_record(pk)
    return jsonify({"message": t("api.transport.deleted")})
@transport_bp.route("/student/<student_id>", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_student_transport(student_id):
    svc = TransportService(_db_path)
    item = svc.get_student_transport(student_id)
    if not item:
        return jsonify({"error": t("api.transport.not_found")}), 404
    return jsonify({"data": item})
