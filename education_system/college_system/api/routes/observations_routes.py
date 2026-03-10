"""API routes for teaching observations."""

from flask import Blueprint, jsonify, request
from education_system.college_system.api.auth import token_required, role_required
from education_system.college_system.api.validators import get_json_body, require_fields
from education_system.college_system.api.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.observations.services.observations_service import ObservationService

observations_bp = Blueprint("observations", __name__, url_prefix="/api/observations")

_db_path = None


def init_observations_routes(db_path=None):
    global _db_path
    _db_path = db_path


@observations_bp.route("", methods=["GET"])
@token_required
def list_observations():
    svc = ObservationService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_observations(limit=limit, offset=offset)
    total = svc.count_observations()
    return jsonify(paginated_response(items, total))


@observations_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_observation(pk):
    svc = ObservationService(_db_path)
    item = svc.get_observation(pk)
    if not item:
        return jsonify({"error": "Observation not found."}), 404
    return jsonify({"data": item})


@observations_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_observation():
    data = get_json_body()
    require_fields(data, "teacher_id", "observation_type")
    svc = ObservationService(_db_path)
    item = svc.create_observation(**data)
    return jsonify({"message": "Observation created.", "data": item}), 201


@observations_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_observation(pk):
    data = get_json_body()
    svc = ObservationService(_db_path)
    item = svc.update_observation(pk, **data)
    return jsonify({"message": "Observation updated.", "data": item})


@observations_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_observation(pk):
    svc = ObservationService(_db_path)
    svc.delete_observation(pk)
    return jsonify({"message": "Observation deleted."})
