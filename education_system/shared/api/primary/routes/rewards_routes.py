"""Rewards API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.primary.auth import token_required, role_required
from education_system.shared.api.primary.validators import get_json_body, require_fields
from education_system.shared.api.primary.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.pastoral_care.rewards.services.rewards_service import RewardsService

rewards_bp = Blueprint("rewards", __name__, url_prefix="/api/rewards")

_db_path = None


def init_rewards_routes(db_path=None):
    global _db_path
    _db_path = db_path


@rewards_bp.route("", methods=["GET"])
@token_required
def list_rewards():
    svc = RewardsService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_rewards(pupil_id=request.args.get("pupil_id"))
    total = len(items)
    return jsonify(paginated_response(items, total))


@rewards_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_reward(pk):
    svc = RewardsService(_db_path)
    item = svc.get_reward(pk)
    if not item:
        return jsonify({"error": "Reward not found."}), 404
    return jsonify({"data": dict(item) if hasattr(item, "keys") else item})


@rewards_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_reward():
    data = get_json_body()
    require_fields(data, "pupil_id", "reward_type")
    svc = RewardsService(_db_path)
    result = svc.create_reward(**data)
    return jsonify({"message": "Reward created.", "data": result}), 201


@rewards_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def update_reward(pk):
    data = get_json_body()
    svc = RewardsService(_db_path)
    result = svc.update_reward(pk, **data)
    return jsonify({"message": "Reward updated.", "data": result})

@rewards_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_reward(pk):
    svc = RewardsService(_db_path)
    svc.delete_reward(pk)
    return jsonify({"message": "Reward deleted."})