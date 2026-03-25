"""API routes for markbook."""

from flask import Blueprint, jsonify, request
from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.markbook.services.markbook_service import MarkbookService
from education_system.college_system.core.i18n import t

markbook_bp = Blueprint("markbook", __name__, url_prefix="/api/markbook")

_db_path = None


def init_markbook_routes(db_path=None):
    global _db_path
    _db_path = db_path


@markbook_bp.route("", methods=["GET"])
@token_required
def list_columns():
    svc = MarkbookService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_columns(limit=limit, offset=offset)
    total = svc.count_columns()
    return jsonify(paginated_response(items, total))


@markbook_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_column(pk):
    svc = MarkbookService(_db_path)
    item = svc.get_column(pk)
    if not item:
        return jsonify({"error": t("api.markbook.not_found")}), 404
    return jsonify({"data": item})


@markbook_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_column():
    data = get_json_body()
    require_fields(data, "course_id", "column_name")
    svc = MarkbookService(_db_path)
    item = svc.create_column(**data)
    return jsonify({"message": t("api.markbook.created"), "data": item}), 201


@markbook_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_column(pk):
    data = get_json_body()
    svc = MarkbookService(_db_path)
    item = svc.update_column(pk, **data)
    return jsonify({"message": t("api.markbook.updated"), "data": item})


@markbook_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_column(pk):
    svc = MarkbookService(_db_path)
    svc.delete_column(pk)
    return jsonify({"message": t("api.markbook.deleted")})
