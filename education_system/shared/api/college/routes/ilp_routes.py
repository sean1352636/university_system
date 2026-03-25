"""API routes for ilp."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.ilp.services.ilp_service import ILPService
from education_system.college_system.core.i18n import t

ilp_bp = Blueprint("ilp", __name__, url_prefix="/api/ilp")

_db_path = None


def init_ilp_routes(db_path=None):
    global _db_path
    _db_path = db_path


@ilp_bp.route("", methods=["GET"])
@token_required
def list_plans():
    svc = ILPService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_plans(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@ilp_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_plan(pk):
    svc = ILPService(_db_path)
    item = svc.get_plan(pk)
    if not item:
        return jsonify({"error": t("api.ilp.not_found")}), 404
    return jsonify({"data": item})
@ilp_bp.route("", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_plan():
    data = get_json_body()
    svc = ILPService(_db_path)
    result = svc.create_plan(**data)
    return jsonify({"message": t("api.ilp.created"), "data": result}), 201
@ilp_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin', 'staff')
def update_plan(pk):
    data = get_json_body()
    svc = ILPService(_db_path)
    result = svc.update_plan(pk, **data)
    return jsonify({"message": t("api.ilp.updated"), "data": result})
@ilp_bp.route("/<int:pk>/targets", methods=["GET"])
@token_required
def list_targets(pk):
    svc = ILPService(_db_path)
    result = svc.list_targets(pk)
    return jsonify({"data": result})
@ilp_bp.route("/<int:pk>/targets", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def add_target(pk):
    data = get_json_body()
    svc = ILPService(_db_path)
    result = svc.add_target(pk, **data)
    return jsonify({"message": t("api.ilp.success"), "data": result}), 201
@ilp_bp.route("/<int:pk>/reviews", methods=["GET"])
@token_required
def list_reviews(pk):
    svc = ILPService(_db_path)
    result = svc.list_reviews(pk)
    return jsonify({"data": result})
@ilp_bp.route("/<int:pk>/reviews", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def add_review(pk):
    data = get_json_body()
    svc = ILPService(_db_path)
    result = svc.add_review(pk, **data)
    return jsonify({"message": t("api.ilp.success"), "data": result}), 201
