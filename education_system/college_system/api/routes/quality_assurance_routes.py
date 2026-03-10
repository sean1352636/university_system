"""API routes for quality assurance."""

from flask import Blueprint, jsonify, request
from education_system.college_system.api.auth import token_required, role_required
from education_system.college_system.api.validators import get_json_body, require_fields
from education_system.college_system.api.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.quality_assurance.services.quality_assurance_service import QualityAssuranceService

quality_assurance_bp = Blueprint("quality-assurance", __name__, url_prefix="/api/quality-assurance")

_db_path = None


def init_quality_assurance_routes(db_path=None):
    global _db_path
    _db_path = db_path


@quality_assurance_bp.route("", methods=["GET"])
@token_required
def list_reviews():
    svc = QualityAssuranceService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_reviews(limit=limit, offset=offset)
    total = svc.count_reviews()
    return jsonify(paginated_response(items, total))


@quality_assurance_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_review(pk):
    svc = QualityAssuranceService(_db_path)
    item = svc.get_review(pk)
    if not item:
        return jsonify({"error": "Review not found."}), 404
    return jsonify({"data": item})


@quality_assurance_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_review():
    data = get_json_body()
    require_fields(data, "review_type", "academic_year", "title")
    svc = QualityAssuranceService(_db_path)
    item = svc.create_review(**data)
    return jsonify({"message": "Review created.", "data": item}), 201


@quality_assurance_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_review(pk):
    data = get_json_body()
    svc = QualityAssuranceService(_db_path)
    item = svc.update_review(pk, **data)
    return jsonify({"message": "Review updated.", "data": item})


@quality_assurance_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_review(pk):
    svc = QualityAssuranceService(_db_path)
    svc.delete_review(pk)
    return jsonify({"message": "Review deleted."})
