"""API routes for dbs checks."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.dbs_checks.services.dbs_checks_service import DBSCheckService
from education_system.college_system.core.i18n import t

dbs_checks_bp = Blueprint("dbs-checks", __name__, url_prefix="/api/dbs-checks")

_db_path = None


def init_dbs_checks_routes(db_path=None):
    global _db_path
    _db_path = db_path


@dbs_checks_bp.route("", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_checks():
    svc = DBSCheckService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_checks(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@dbs_checks_bp.route("/<int:pk>", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_check(pk):
    svc = DBSCheckService(_db_path)
    item = svc.get_check(pk)
    if not item:
        return jsonify({"error": t("api.dbs_checks.not_found")}), 404
    return jsonify({"data": item})
@dbs_checks_bp.route("", methods=["POST"])
@token_required
@role_required('admin')
def create_check():
    data = get_json_body()
    svc = DBSCheckService(_db_path)
    result = svc.create_check(**data)
    return jsonify({"message": t("api.dbs_checks.created"), "data": result}), 201
@dbs_checks_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin')
def update_check(pk):
    data = get_json_body()
    svc = DBSCheckService(_db_path)
    result = svc.update_check(pk, **data)
    return jsonify({"message": t("api.dbs_checks.updated"), "data": result})
@dbs_checks_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required('admin')
def delete_check(pk):
    svc = DBSCheckService(_db_path)
    svc.delete_check(pk)
    return jsonify({"message": t("api.dbs_checks.deleted")})
@dbs_checks_bp.route("/expiring", methods=["GET"])
@token_required
@role_required('admin')
def get_expiring():
    svc = DBSCheckService(_db_path)
    result = svc.get_expiring()
    return jsonify({"data": result})
@dbs_checks_bp.route("/stats", methods=["GET"])
@token_required
@role_required('admin')
def get_stats():
    svc = DBSCheckService(_db_path)
    result = svc.get_stats()
    return jsonify({"data": result})
