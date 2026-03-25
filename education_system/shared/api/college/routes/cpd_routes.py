"""API routes for cpd records."""

from flask import Blueprint, jsonify, request
from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.cpd.services.cpd_service import CPDService
from education_system.college_system.core.i18n import t

cpd_bp = Blueprint("cpd", __name__, url_prefix="/api/cpd")

_db_path = None


def init_cpd_routes(db_path=None):
    global _db_path
    _db_path = db_path


@cpd_bp.route("", methods=["GET"])
@token_required
def list_records():
    svc = CPDService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_records(limit=limit, offset=offset)
    total = svc.count_records()
    return jsonify(paginated_response(items, total))


@cpd_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_record(pk):
    svc = CPDService(_db_path)
    item = svc.get_record(pk)
    if not item:
        return jsonify({"error": t("api.cpd.not_found")}), 404
    return jsonify({"data": item})


@cpd_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_record():
    data = get_json_body()
    require_fields(data, "title", "cpd_type")
    svc = CPDService(_db_path)
    item = svc.create_record(**data)
    return jsonify({"message": t("api.cpd.created"), "data": item}), 201


@cpd_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_record(pk):
    data = get_json_body()
    svc = CPDService(_db_path)
    item = svc.update_record(pk, **data)
    return jsonify({"message": t("api.cpd.updated"), "data": item})


@cpd_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_record(pk):
    svc = CPDService(_db_path)
    svc.delete_record(pk)
    return jsonify({"message": t("api.cpd.deleted")})
