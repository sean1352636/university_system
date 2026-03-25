"""API routes for kpi dashboard."""

from flask import Blueprint, jsonify, request
from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.kpi_dashboard.services.kpi_dashboard_service import KPIDashboardService
from education_system.college_system.core.i18n import t

kpi_bp = Blueprint("kpi", __name__, url_prefix="/api/kpi")

_db_path = None


def init_kpi_routes(db_path=None):
    global _db_path
    _db_path = db_path


@kpi_bp.route("", methods=["GET"])
@token_required
def list_targets():
    svc = KPIDashboardService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_targets(limit=limit, offset=offset)
    total = svc.count_targets()
    return jsonify(paginated_response(items, total))


@kpi_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_target(pk):
    svc = KPIDashboardService(_db_path)
    item = svc.get_target(pk)
    if not item:
        return jsonify({"error": t("api.common.not_found")}), 404
    return jsonify({"data": item})


@kpi_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_target():
    data = get_json_body()
    require_fields(data, "academic_year", "kpi_name")
    svc = KPIDashboardService(_db_path)
    item = svc.create_target(**data)
    return jsonify({"message": t("api.common.created"), "data": item}), 201


@kpi_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_target(pk):
    data = get_json_body()
    svc = KPIDashboardService(_db_path)
    item = svc.update_target(pk, **data)
    return jsonify({"message": t("api.common.updated"), "data": item})


@kpi_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_target(pk):
    svc = KPIDashboardService(_db_path)
    svc.delete_target(pk)
    return jsonify({"message": t("api.common.deleted")})
