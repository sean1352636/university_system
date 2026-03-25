"""API routes for disciplinary."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.disciplinary.services.disciplinary_service import DisciplinaryService
from education_system.college_system.core.i18n import t

disciplinary_bp = Blueprint("disciplinary", __name__, url_prefix="/api/disciplinary")

_db_path = None


def init_disciplinary_routes(db_path=None):
    global _db_path
    _db_path = db_path


@disciplinary_bp.route("", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_cases():
    svc = DisciplinaryService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_cases(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@disciplinary_bp.route("/<int:pk>", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_case(pk):
    svc = DisciplinaryService(_db_path)
    item = svc.get_case(pk)
    if not item:
        return jsonify({"error": t("api.disciplinary.not_found")}), 404
    return jsonify({"data": item})
@disciplinary_bp.route("", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_case():
    data = get_json_body()
    svc = DisciplinaryService(_db_path)
    result = svc.create_case(**data)
    return jsonify({"message": t("api.disciplinary.created"), "data": result}), 201
@disciplinary_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin', 'staff')
def update_case(pk):
    data = get_json_body()
    svc = DisciplinaryService(_db_path)
    result = svc.update_case(pk, **data)
    return jsonify({"message": t("api.disciplinary.updated"), "data": result})
@disciplinary_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required('admin')
def delete_case(pk):
    svc = DisciplinaryService(_db_path)
    svc.delete_case(pk)
    return jsonify({"message": t("api.disciplinary.deleted")})
@disciplinary_bp.route("/appeals", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_appeals():
    svc = DisciplinaryService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_appeals(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@disciplinary_bp.route("/stats", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_stats():
    svc = DisciplinaryService(_db_path)
    result = svc.get_stats()
    return jsonify({"data": result})
