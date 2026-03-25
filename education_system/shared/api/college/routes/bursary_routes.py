"""API routes for bursary."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.bursary.services.bursary_service import BursaryService
from education_system.college_system.core.i18n import t

bursary_bp = Blueprint("bursary", __name__, url_prefix="/api/bursary")

_db_path = None


def init_bursary_routes(db_path=None):
    global _db_path
    _db_path = db_path


@bursary_bp.route("", methods=["GET"])
@token_required
def list_bursaries():
    svc = BursaryService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_bursaries(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@bursary_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_bursary(pk):
    svc = BursaryService(_db_path)
    item = svc.get_bursary(pk)
    if not item:
        return jsonify({"error": t("api.bursary.not_found")}), 404
    return jsonify({"data": item})
@bursary_bp.route("", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_bursary():
    data = get_json_body()
    svc = BursaryService(_db_path)
    result = svc.create_bursary(**data)
    return jsonify({"message": t("api.bursary.created"), "data": result}), 201
@bursary_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin', 'staff')
def update_bursary(pk):
    data = get_json_body()
    svc = BursaryService(_db_path)
    result = svc.update_bursary(pk, **data)
    return jsonify({"message": t("api.bursary.updated"), "data": result})
@bursary_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required('admin')
def delete_application(pk):
    svc = BursaryService(_db_path)
    svc.delete_application(pk)
    return jsonify({"message": t("api.bursary.deleted")})
@bursary_bp.route("/meal-eligible", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_meal_eligible():
    svc = BursaryService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_meal_eligible(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
