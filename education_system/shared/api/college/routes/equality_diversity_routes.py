"""API routes for equality diversity."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.equality_diversity.services.equality_diversity_service import EqualityDiversityService
from education_system.college_system.core.i18n import t

equality_diversity_bp = Blueprint("equality-diversity", __name__, url_prefix="/api/equality-diversity")

_db_path = None


def init_equality_diversity_routes(db_path=None):
    global _db_path
    _db_path = db_path


@equality_diversity_bp.route("/characteristics", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_characteristics():
    svc = EqualityDiversityService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_characteristics(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@equality_diversity_bp.route("/characteristics", methods=["POST"])
@token_required
@role_required('admin')
def create_characteristic():
    data = get_json_body()
    svc = EqualityDiversityService(_db_path)
    result = svc.create_characteristic(**data)
    return jsonify({"message": t("api.equality_diversity.created"), "data": result}), 201
@equality_diversity_bp.route("/assessments", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_assessments():
    svc = EqualityDiversityService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_assessments(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@equality_diversity_bp.route("/assessments", methods=["POST"])
@token_required
@role_required('admin')
def create_assessment():
    data = get_json_body()
    svc = EqualityDiversityService(_db_path)
    result = svc.create_assessment(**data)
    return jsonify({"message": t("api.equality_diversity.created"), "data": result}), 201
@equality_diversity_bp.route("/objectives", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_objectives():
    svc = EqualityDiversityService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_objectives(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@equality_diversity_bp.route("/objectives", methods=["POST"])
@token_required
@role_required('admin')
def create_objective():
    data = get_json_body()
    svc = EqualityDiversityService(_db_path)
    result = svc.create_objective(**data)
    return jsonify({"message": t("api.equality_diversity.created"), "data": result}), 201
@equality_diversity_bp.route("/stats", methods=["GET"])
@token_required
@role_required('admin')
def get_stats():
    svc = EqualityDiversityService(_db_path)
    result = svc.get_stats()
    return jsonify({"data": result})
