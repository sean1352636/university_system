"""API routes for academic year."""

from flask import Blueprint, jsonify, request
from education_system.college_system.api.auth import token_required, role_required
from education_system.college_system.api.validators import get_json_body, require_fields
from education_system.college_system.api.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.academic_year.services.academic_year_service import AcademicYearService

academic_year_bp = Blueprint("academic-year", __name__, url_prefix="/api/academic-year")

_db_path = None


def init_academic_year_routes(db_path=None):
    global _db_path
    _db_path = db_path


@academic_year_bp.route("", methods=["GET"])
@token_required
def list_years():
    svc = AcademicYearService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_years(limit=limit, offset=offset)
    total = svc.count_years()
    return jsonify(paginated_response(items, total))


@academic_year_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_year(pk):
    svc = AcademicYearService(_db_path)
    item = svc.get_year(pk)
    if not item:
        return jsonify({"error": "Year not found."}), 404
    return jsonify({"data": item})


@academic_year_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_year():
    data = get_json_body()
    require_fields(data, "name", "start_date", "end_date")
    svc = AcademicYearService(_db_path)
    item = svc.create_year(**data)
    return jsonify({"message": "Year created.", "data": item}), 201


@academic_year_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_year(pk):
    data = get_json_body()
    svc = AcademicYearService(_db_path)
    item = svc.update_year(pk, **data)
    return jsonify({"message": "Year updated.", "data": item})


@academic_year_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_year(pk):
    svc = AcademicYearService(_db_path)
    svc.delete_year(pk)
    return jsonify({"message": "Year deleted."})
