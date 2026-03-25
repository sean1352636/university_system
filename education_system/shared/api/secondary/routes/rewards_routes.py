"""Rewards API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.pastoral_care.rewards.services.rewards_service import RewardsService

rewards_bp = Blueprint("rewards", __name__, url_prefix="/api/rewards")

_db_path = None


def init_rewards_routes(db_path=None):
    global _db_path
    _db_path = db_path


@rewards_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def award_reward():
    data = get_json_body()
    require_fields(data, "student_id", "reward_type", "reason")
    svc = RewardsService(_db_path)
    result = svc.award(student_id=data["student_id"], reward_type=data["reward_type"], reason=data["reason"], points=data.get("points", 1), awarded_by=data.get("awarded_by", ""))
    return jsonify({"message": "Created.", "data": result}), 201


@rewards_bp.route("", methods=["GET"])
@token_required
def list_rewards():
    svc = RewardsService(_db_path)
    result = svc.list_rewards()
    return jsonify({"data": result})


@rewards_bp.route("/<int:reward_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_reward(reward_id):
    svc = RewardsService(_db_path)
    result = svc.delete_reward(reward_id)
    return jsonify({"message": "Deleted.", "data": result})


@rewards_bp.route("/student/<int:student_id>/totals", methods=["GET"])
@token_required
def student_totals(student_id):
    svc = RewardsService(_db_path)
    result = svc.student_totals(student_id)
    return jsonify({"data": result})


@rewards_bp.route("/leaderboard", methods=["GET"])
@token_required
def leaderboard():
    svc = RewardsService(_db_path)
    result = svc.leaderboard()
    return jsonify({"data": result})

