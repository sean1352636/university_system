"""Behaviour API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.pastoral_care.behaviour.services.behaviour_service import BehaviourService

behaviour_bp = Blueprint("behaviour", __name__, url_prefix="/api/behaviour")

_db_path = None


def init_behaviour_routes(db_path=None):
    global _db_path
    _db_path = db_path


@behaviour_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def record_behaviour():
    data = get_json_body()
    require_fields(data, "student_id", "category")

    svc = BehaviourService(_db_path)
    record = svc.add_record(
        student_id=data["student_id"],
        record_type=data.get("behaviour_type", "negative"),
        category=data["category"],
        description=data.get("description"),
        points=data.get("points", 0),
        recorded_by=data.get("recorded_by"),
    )
    return jsonify({"message": "Behaviour recorded.", "data": record}), 201


@behaviour_bp.route("/student/<int:student_id>", methods=["GET"])
@token_required
def get_student_behaviour(student_id):
    svc = BehaviourService(_db_path)
    records = svc.get_student_records(student_id)
    return jsonify({"data": records})


@behaviour_bp.route("/student/<int:student_id>/summary", methods=["GET"])
@token_required
def get_student_summary(student_id):
    svc = BehaviourService(_db_path)
    summary = svc.get_student_points(student_id)
    return jsonify({"data": summary})
