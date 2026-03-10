"""API routes for visitor management."""

from flask import Blueprint, jsonify, request
from education_system.college_system.api.auth import token_required, role_required
from education_system.college_system.api.validators import get_json_body, require_fields
from education_system.college_system.api.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.visitors.services.visitors_service import VisitorService

visitor_bp = Blueprint("visitors", __name__, url_prefix="/api/visitors")

_db_path = None


def init_visitor_routes(db_path=None):
    global _db_path
    _db_path = db_path


@visitor_bp.route("", methods=["GET"])
@token_required
def list_visitors():
    svc = VisitorService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_visitors(limit=limit, offset=offset)
    total = svc.count_visitors()
    return jsonify(paginated_response(items, total))


@visitor_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_visitor(pk):
    svc = VisitorService(_db_path)
    item = svc.get_visitor(pk)
    if not item:
        return jsonify({"error": "Visitor not found."}), 404
    return jsonify({"data": item})


@visitor_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_visitor():
    data = get_json_body()
    require_fields(data, "first_name", "last_name", "purpose")
    svc = VisitorService(_db_path)
    item = svc.create_visitor(**data)
    return jsonify({"message": "Visitor created.", "data": item}), 201


@visitor_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_visitor(pk):
    data = get_json_body()
    svc = VisitorService(_db_path)
    item = svc.update_visitor(pk, **data)
    return jsonify({"message": "Visitor updated.", "data": item})


@visitor_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_visitor(pk):
    svc = VisitorService(_db_path)
    svc.delete_visitor(pk)
    return jsonify({"message": "Visitor deleted."})
