"""Safeguarding API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.primary.auth import token_required, role_required
from education_system.shared.api.primary.validators import get_json_body, require_fields
from education_system.shared.api.primary.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.pastoral_care.safeguarding.services.safeguarding_service import SafeguardingService

safeguarding_bp = Blueprint("safeguarding", __name__, url_prefix="/api/safeguarding")

_db_path = None


def init_safeguarding_routes(db_path=None):
    global _db_path
    _db_path = db_path


@safeguarding_bp.route("", methods=["GET"])
@token_required
def list_concerns():
    svc = SafeguardingService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_concerns(pupil_id=request.args.get("pupil_id"))
    total = len(items)
    return jsonify(paginated_response(items, total))


@safeguarding_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_concern(pk):
    svc = SafeguardingService(_db_path)
    item = svc.get_concern(pk)
    if not item:
        return jsonify({"error": "Concern not found."}), 404
    return jsonify({"data": dict(item) if hasattr(item, "keys") else item})


@safeguarding_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_concern():
    data = get_json_body()
    require_fields(data, "pupil_id", "concern_type", "description")
    svc = SafeguardingService(_db_path)
    result = svc.create_concern(**data)
    return jsonify({"message": "Concern created.", "data": result}), 201


@safeguarding_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def update_concern(pk):
    data = get_json_body()
    svc = SafeguardingService(_db_path)
    result = svc.update_concern(pk, **data)
    return jsonify({"message": "Concern updated.", "data": result})