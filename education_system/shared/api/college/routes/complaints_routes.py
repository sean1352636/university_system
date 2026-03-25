"""API routes for complaints."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.complaints.services.complaints_service import ComplaintService
from education_system.college_system.core.i18n import t

complaints_bp = Blueprint("complaints", __name__, url_prefix="/api/complaints")

_db_path = None


def init_complaints_routes(db_path=None):
    global _db_path
    _db_path = db_path


@complaints_bp.route("", methods=["GET"])
@token_required
def list_complaints():
    svc = ComplaintService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_complaints(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@complaints_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_complaint(pk):
    svc = ComplaintService(_db_path)
    item = svc.get_complaint(pk)
    if not item:
        return jsonify({"error": t("api.complaints.not_found")}), 404
    return jsonify({"data": item})
@complaints_bp.route("", methods=["POST"])
@token_required
def create_complaint():
    data = get_json_body()
    svc = ComplaintService(_db_path)
    result = svc.create_complaint(**data)
    return jsonify({"message": t("api.complaints.created"), "data": result}), 201
@complaints_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin', 'staff')
def update_complaint(pk):
    data = get_json_body()
    svc = ComplaintService(_db_path)
    result = svc.update_complaint(pk, **data)
    return jsonify({"message": t("api.complaints.updated"), "data": result})
@complaints_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required('admin')
def delete_complaint(pk):
    svc = ComplaintService(_db_path)
    svc.delete_complaint(pk)
    return jsonify({"message": t("api.complaints.deleted")})
@complaints_bp.route("/<int:pk>/escalate", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def escalate(pk):
    data = get_json_body()
    svc = ComplaintService(_db_path)
    result = svc.escalate(pk, **data)
    return jsonify({"message": t("api.complaints.success"), "data": result}), 201
@complaints_bp.route("/<int:pk>/resolve", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def resolve(pk):
    data = get_json_body()
    svc = ComplaintService(_db_path)
    result = svc.resolve(pk, **data)
    return jsonify({"message": t("api.complaints.success"), "data": result}), 201
@complaints_bp.route("/stats", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_stats():
    svc = ComplaintService(_db_path)
    result = svc.get_stats()
    return jsonify({"data": result})
