"""DBS checks API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.primary.auth import token_required, role_required
from education_system.shared.api.primary.validators import get_json_body, require_fields
from education_system.shared.api.primary.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.staff.dbs_checks.services.dbs_checks_service import DbsChecksService

dbs_checks_bp = Blueprint("dbs-checks", __name__, url_prefix="/api/dbs-checks")

_db_path = None


def init_dbs_checks_routes(db_path=None):
    global _db_path
    _db_path = db_path


@dbs_checks_bp.route("", methods=["GET"])
@token_required
def list_dbs_checks():
    svc = DbsChecksService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_all(limit=limit, offset=offset)
    total = len(items)
    return jsonify(paginated_response(items, total))


@dbs_checks_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_dbs_checks_item(pk):
    svc = DbsChecksService(_db_path)
    item = svc.get(pk)
    if not item:
        return jsonify({"error": "Not found."}), 404
    return jsonify({"data": item})


@dbs_checks_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_dbs_checks_item():
    data = get_json_body()
    svc = DbsChecksService(_db_path)
    result = svc.create(**data)
    return jsonify({"message": "Created.", "data": result}), 201


@dbs_checks_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_dbs_checks_item(pk):
    data = get_json_body()
    svc = DbsChecksService(_db_path)
    result = svc.update(pk, **data)
    return jsonify({"message": "Updated.", "data": result})


@dbs_checks_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_dbs_checks_item(pk):
    svc = DbsChecksService(_db_path)
    svc.delete(pk)
    return jsonify({"message": "Deleted."})
