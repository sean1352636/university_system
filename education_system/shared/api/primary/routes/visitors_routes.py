"""Visitors API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.primary.auth import token_required, role_required
from education_system.shared.api.primary.validators import get_json_body, require_fields
from education_system.shared.api.primary.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.facilities.visitors.services.visitor_service import VisitorService

visitors_bp = Blueprint("visitors", __name__, url_prefix="/api/visitors")

_db_path = None


def init_visitors_routes(db_path=None):
    global _db_path
    _db_path = db_path


@visitors_bp.route("", methods=["GET"])
@token_required
def list_visitors():
    svc = VisitorService(_db_path)
    items = svc.list_visitors()
    return jsonify({"data": items})


@visitors_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_visitor(pk):
    svc = VisitorService(_db_path)
    item = svc.get_visitor(pk)
    if not item:
        return jsonify({"error": "Visitor not found."}), 404
    return jsonify({"data": dict(item) if hasattr(item, "keys") else item})


@visitors_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def sign_in_visitor():
    data = get_json_body()
    require_fields(data, "name", "purpose", "date")
    svc = VisitorService(_db_path)
    result = svc.sign_in_visitor(**data)
    return jsonify({"message": "Visitor signed in.", "data": result}), 201


@visitors_bp.route("/<int:pk>/sign-out", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def sign_out_visitor(pk):
    svc = VisitorService(_db_path)
    result = svc.sign_out_visitor(pk)
    return jsonify({"message": "Visitor signed out.", "data": result})
