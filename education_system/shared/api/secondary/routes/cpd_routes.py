"""Cpd API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.staff.cpd.services.cpd_service import CPDService

cpd_bp = Blueprint("cpd", __name__, url_prefix="/api/cpd")

_db_path = None


def init_cpd_routes(db_path=None):
    global _db_path
    _db_path = db_path


@cpd_bp.route("", methods=["POST"])
@token_required
def add_record():
    data = get_json_body()
    require_fields(data, "staff_id", "title", "date")
    svc = CPDService(_db_path)
    result = svc.add_record(staff_id=data["staff_id"], title=data["title"], date=data["date"], provider=data.get("provider", ""), hours=data.get("hours", 0))
    return jsonify({"message": "Created.", "data": result}), 201


@cpd_bp.route("", methods=["GET"])
@token_required
def list_records():
    svc = CPDService(_db_path)
    result = svc.list_records()
    return jsonify({"data": result})


@cpd_bp.route("/<int:record_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_record(record_id):
    svc = CPDService(_db_path)
    result = svc.delete_record(record_id)
    return jsonify({"message": "Deleted.", "data": result})


@cpd_bp.route("/staff/<int:staff_id>/summary", methods=["GET"])
@token_required
def staff_summary(staff_id):
    svc = CPDService(_db_path)
    result = svc.staff_summary(staff_id)
    return jsonify({"data": result})

