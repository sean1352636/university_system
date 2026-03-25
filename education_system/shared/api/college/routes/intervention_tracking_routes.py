"""API routes for intervention tracking."""

from flask import Blueprint, jsonify, request
from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.intervention_tracking.services.intervention_tracking_service import InterventionService
from education_system.college_system.core.i18n import t

intervention_bp = Blueprint("intervention-tracking", __name__, url_prefix="/api/intervention-tracking")

_db_path = None


def init_intervention_routes(db_path=None):
    global _db_path
    _db_path = db_path


@intervention_bp.route("", methods=["GET"])
@token_required
def list_interventions():
    svc = InterventionService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_interventions(limit=limit, offset=offset)
    total = svc.count_interventions()
    return jsonify(paginated_response(items, total))


@intervention_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_intervention(pk):
    svc = InterventionService(_db_path)
    item = svc.get_intervention(pk)
    if not item:
        return jsonify({"error": t("api.intervention_tracking.not_found")}), 404
    return jsonify({"data": item})


@intervention_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_intervention():
    data = get_json_body()
    require_fields(data, "student_id", "staff_id", "intervention_type")
    svc = InterventionService(_db_path)
    item = svc.create_intervention(**data)
    return jsonify({"message": t("api.intervention_tracking.created"), "data": item}), 201


@intervention_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_intervention(pk):
    data = get_json_body()
    svc = InterventionService(_db_path)
    item = svc.update_intervention(pk, **data)
    return jsonify({"message": t("api.intervention_tracking.updated"), "data": item})


@intervention_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_intervention(pk):
    svc = InterventionService(_db_path)
    svc.delete_intervention(pk)
    return jsonify({"message": t("api.intervention_tracking.deleted")})
