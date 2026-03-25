"""Visitors API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.facilities.visitors.services.visitor_service import VisitorService

visitors_bp = Blueprint("visitors", __name__, url_prefix="/api/visitors")

_db_path = None


def init_visitors_routes(db_path=None):
    global _db_path
    _db_path = db_path


@visitors_bp.route("/sign-in", methods=["POST"])
@token_required
def sign_in():
    data = get_json_body()
    require_fields(data, "name", "purpose")
    svc = VisitorService(_db_path)
    result = svc.sign_in(name=data["name"], purpose=data["purpose"], visiting=data.get("visiting", ""), badge_number=data.get("badge_number", ""))
    return jsonify({"message": "Created.", "data": result}), 201


@visitors_bp.route("/<int:visitor_id>/sign-out", methods=["PUT"])
@token_required
def sign_out(visitor_id):
    svc = VisitorService(_db_path)
    result = svc.sign_out(visitor_id)
    return jsonify({"message": "Updated.", "data": result})


@visitors_bp.route("", methods=["GET"])
@token_required
def list_visitors():
    svc = VisitorService(_db_path)
    result = svc.list_visitors()
    return jsonify({"data": result})


@visitors_bp.route("/<int:visitor_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_visitor(visitor_id):
    svc = VisitorService(_db_path)
    result = svc.delete_visitor(visitor_id)
    return jsonify({"message": "Deleted.", "data": result})


@visitors_bp.route("/on-site", methods=["GET"])
@token_required
def on_site_count():
    svc = VisitorService(_db_path)
    result = svc.on_site_count()
    return jsonify({"data": result})

