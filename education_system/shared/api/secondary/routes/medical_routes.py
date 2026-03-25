"""Medical API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.student_life.medical.services.medical_service import MedicalService

medical_bp = Blueprint("medical", __name__, url_prefix="/api/medical")

_db_path = None


def init_medical_routes(db_path=None):
    global _db_path
    _db_path = db_path


@medical_bp.route("/conditions", methods=["POST"])
@token_required
def add_condition():
    data = get_json_body()
    require_fields(data, "student_id", "condition")
    svc = MedicalService(_db_path)
    result = svc.add_condition(student_id=data["student_id"], condition=data["condition"], details=data.get("details", ""), medication=data.get("medication", ""))
    return jsonify({"message": "Created.", "data": result}), 201


@medical_bp.route("/conditions", methods=["GET"])
@token_required
def list_conditions():
    svc = MedicalService(_db_path)
    result = svc.list_conditions()
    return jsonify({"data": result})


@medical_bp.route("/conditions/<int:cond_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_condition(cond_id):
    svc = MedicalService(_db_path)
    result = svc.delete_condition(cond_id)
    return jsonify({"message": "Deleted.", "data": result})


@medical_bp.route("/incidents", methods=["POST"])
@token_required
def log_incident():
    data = get_json_body()
    require_fields(data, "student_id", "description")
    svc = MedicalService(_db_path)
    result = svc.log_incident(student_id=data["student_id"], description=data["description"], treatment=data.get("treatment", ""), staff_member=data.get("staff_member", ""))
    return jsonify({"message": "Created.", "data": result}), 201


@medical_bp.route("/incidents", methods=["GET"])
@token_required
def list_incidents():
    svc = MedicalService(_db_path)
    result = svc.list_incidents()
    return jsonify({"data": result})


@medical_bp.route("/incidents/<int:inc_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_incident(inc_id):
    svc = MedicalService(_db_path)
    result = svc.delete_incident(inc_id)
    return jsonify({"message": "Deleted.", "data": result})

