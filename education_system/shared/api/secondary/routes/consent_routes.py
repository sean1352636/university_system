"""Consent API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.student_life.consent.services.consent_service import ConsentService

consent_bp = Blueprint("consent", __name__, url_prefix="/api/consent")

_db_path = None


def init_consent_routes(db_path=None):
    global _db_path
    _db_path = db_path


@consent_bp.route("", methods=["POST"])
@token_required
def add_record():
    data = get_json_body()
    require_fields(data, "student_id", "consent_type")
    svc = ConsentService(_db_path)
    result = svc.add_record(student_id=data["student_id"], consent_type=data["consent_type"], granted=data.get("granted", True), parent_name=data.get("parent_name", ""))
    return jsonify({"message": "Created.", "data": result}), 201


@consent_bp.route("", methods=["GET"])
@token_required
def list_records():
    svc = ConsentService(_db_path)
    result = svc.list_records()
    return jsonify({"data": result})


@consent_bp.route("/<int:record_id>/toggle", methods=["PUT"])
@token_required
def toggle_granted(record_id):
    svc = ConsentService(_db_path)
    result = svc.toggle_granted(record_id)
    return jsonify({"message": "Updated.", "data": result})


@consent_bp.route("/<int:record_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_record(record_id):
    svc = ConsentService(_db_path)
    result = svc.delete_record(record_id)
    return jsonify({"message": "Deleted.", "data": result})


@consent_bp.route("/summary/<consent_type>", methods=["GET"])
@token_required
def summary_by_type(consent_type):
    svc = ConsentService(_db_path)
    result = svc.summary_by_type(consent_type)
    return jsonify({"data": result})

