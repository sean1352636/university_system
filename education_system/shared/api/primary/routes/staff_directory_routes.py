"""Staff Directory API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.primary.auth import token_required
from education_system.shared.api.primary.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.staff.staff_directory.services.staff_directory_service import StaffDirectoryService

staff_directory_bp = Blueprint("staff_directory", __name__, url_prefix="/api/staff-directory")

_db_path = None


def init_staff_directory_routes(db_path=None):
    global _db_path
    _db_path = db_path


@staff_directory_bp.route("", methods=["GET"])
@token_required
def list_staff():
    svc = StaffDirectoryService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_staff(search=request.args.get('search'))
    total = len(items)
    return jsonify(paginated_response(items, total))


@staff_directory_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_staff(pk):
    svc = StaffDirectoryService(_db_path)
    item = svc.get_staff(pk)
    if not item:
        return jsonify({"error": "Staff not found."}), 404
    return jsonify({"data": dict(item) if hasattr(item, "keys") else item})
