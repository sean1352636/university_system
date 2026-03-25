"""API routes for student portal."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.student_portal.services.student_portal_service import StudentPortalService
from education_system.college_system.core.i18n import t

student_portal_bp = Blueprint("student-portal", __name__, url_prefix="/api/student-portal")

_db_path = None


def init_student_portal_routes(db_path=None):
    global _db_path
    _db_path = db_path


@student_portal_bp.route("/pages", methods=["GET"])
@token_required
def list_pages():
    svc = StudentPortalService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_pages(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@student_portal_bp.route("/pages/<int:pk>", methods=["GET"])
@token_required
def get_page(pk):
    svc = StudentPortalService(_db_path)
    item = svc.get_page(pk)
    if not item:
        return jsonify({"error": t("api.student_portal.not_found")}), 404
    return jsonify({"data": item})
@student_portal_bp.route("/pages", methods=["POST"])
@token_required
@role_required('admin')
def create_page():
    data = get_json_body()
    svc = StudentPortalService(_db_path)
    result = svc.create_page(**data)
    return jsonify({"message": t("api.student_portal.created"), "data": result}), 201
@student_portal_bp.route("/pages/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin')
def update_page(pk):
    data = get_json_body()
    svc = StudentPortalService(_db_path)
    result = svc.update_page(pk, **data)
    return jsonify({"message": t("api.student_portal.updated"), "data": result})
@student_portal_bp.route("/pages/<int:pk>", methods=["DELETE"])
@token_required
@role_required('admin')
def delete_page(pk):
    svc = StudentPortalService(_db_path)
    svc.delete_page(pk)
    return jsonify({"message": t("api.student_portal.deleted")})
@student_portal_bp.route("/links", methods=["GET"])
@token_required
def list_links():
    svc = StudentPortalService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_links(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@student_portal_bp.route("/links", methods=["POST"])
@token_required
@role_required('admin')
def create_link():
    data = get_json_body()
    svc = StudentPortalService(_db_path)
    result = svc.create_link(**data)
    return jsonify({"message": t("api.student_portal.created"), "data": result}), 201
@student_portal_bp.route("/stats", methods=["GET"])
@token_required
@role_required('admin')
def get_stats():
    svc = StudentPortalService(_db_path)
    result = svc.get_stats()
    return jsonify({"data": result})
