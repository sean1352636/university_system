"""API routes for enrichment."""

from flask import Blueprint, jsonify, request
from education_system.college_system.api.auth import token_required, role_required
from education_system.college_system.api.validators import get_json_body, require_fields
from education_system.college_system.api.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.enrichment.services.enrichment_service import EnrichmentService

enrichment_bp = Blueprint("enrichment", __name__, url_prefix="/api/enrichment")

_db_path = None


def init_enrichment_routes(db_path=None):
    global _db_path
    _db_path = db_path


@enrichment_bp.route("", methods=["GET"])
@token_required
def list_activities():
    svc = EnrichmentService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_activities(limit=limit, offset=offset)
    total = svc.count_activities()
    return jsonify(paginated_response(items, total))


@enrichment_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_activity(pk):
    svc = EnrichmentService(_db_path)
    item = svc.get_activity(pk)
    if not item:
        return jsonify({"error": "Activity not found."}), 404
    return jsonify({"data": item})


@enrichment_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff", "instructor")
def create_activity():
    data = get_json_body()
    require_fields(data, "name", "activity_type")
    svc = EnrichmentService(_db_path)
    item = svc.create_activity(**data)
    return jsonify({"message": "Activity created.", "data": item}), 201


@enrichment_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff", "instructor")
def update_activity(pk):
    data = get_json_body()
    svc = EnrichmentService(_db_path)
    item = svc.update_activity(pk, **data)
    return jsonify({"message": "Activity updated.", "data": item})


@enrichment_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_activity(pk):
    svc = EnrichmentService(_db_path)
    svc.delete_activity(pk)
    return jsonify({"message": "Activity deleted."})
