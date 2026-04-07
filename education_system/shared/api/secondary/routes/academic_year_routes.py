"""Academic year API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.shared.api.secondary.pagination import get_pagination_params, paginated_response
from education_system.secondary_school.modules.domain.academics.academic_year.services.academic_year_service import AcademicYearService

academic_year_bp = Blueprint("academic-years", __name__, url_prefix="/api/academic-years")

_db_path = None


def init_academic_year_routes(db_path=None):
    global _db_path
    _db_path = db_path


@academic_year_bp.route("", methods=["GET"])
@token_required
def list_academic_years():
    svc = AcademicYearService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_all(limit=limit, offset=offset)
    total = len(items)
    return jsonify(paginated_response(items, total))


@academic_year_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_academic_years_item(pk):
    svc = AcademicYearService(_db_path)
    item = svc.get(pk)
    if not item:
        return jsonify({"error": "Not found."}), 404
    return jsonify({"data": item})


@academic_year_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_academic_years_item():
    data = get_json_body()
    svc = AcademicYearService(_db_path)
    result = svc.create(**data)
    return jsonify({"message": "Created.", "data": result}), 201


@academic_year_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_academic_years_item(pk):
    data = get_json_body()
    svc = AcademicYearService(_db_path)
    result = svc.update(pk, **data)
    return jsonify({"message": "Updated.", "data": result})


@academic_year_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_academic_years_item(pk):
    svc = AcademicYearService(_db_path)
    svc.delete(pk)
    return jsonify({"message": "Deleted."})
