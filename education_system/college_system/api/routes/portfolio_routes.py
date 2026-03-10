"""API routes for student portfolio."""

from flask import Blueprint, jsonify, request
from education_system.college_system.api.auth import token_required, role_required
from education_system.college_system.api.validators import get_json_body, require_fields
from education_system.college_system.api.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.portfolio.services.portfolio_service import PortfolioService

portfolio_bp = Blueprint("portfolio", __name__, url_prefix="/api/portfolio")

_db_path = None


def init_portfolio_routes(db_path=None):
    global _db_path
    _db_path = db_path


@portfolio_bp.route("", methods=["GET"])
@token_required
def list_items():
    svc = PortfolioService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_items(limit=limit, offset=offset)
    total = svc.count_items()
    return jsonify(paginated_response(items, total))


@portfolio_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_item(pk):
    svc = PortfolioService(_db_path)
    item = svc.get_item(pk)
    if not item:
        return jsonify({"error": "Item not found."}), 404
    return jsonify({"data": item})


@portfolio_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff", "instructor")
def create_item():
    data = get_json_body()
    require_fields(data, "student_id", "title")
    svc = PortfolioService(_db_path)
    item = svc.create_item(**data)
    return jsonify({"message": "Item created.", "data": item}), 201


@portfolio_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff", "instructor")
def update_item(pk):
    data = get_json_body()
    svc = PortfolioService(_db_path)
    item = svc.update_item(pk, **data)
    return jsonify({"message": "Item updated.", "data": item})


@portfolio_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_item(pk):
    svc = PortfolioService(_db_path)
    svc.delete_item(pk)
    return jsonify({"message": "Item deleted."})
