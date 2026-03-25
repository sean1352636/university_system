"""API routes for governance."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.governance.services.governance_service import GovernanceService
from education_system.college_system.core.i18n import t

governance_bp = Blueprint("governance", __name__, url_prefix="/api/governance")

_db_path = None


def init_governance_routes(db_path=None):
    global _db_path
    _db_path = db_path


@governance_bp.route("/governors", methods=["GET"])
@token_required
@role_required('admin')
def list_governors():
    svc = GovernanceService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_governors(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@governance_bp.route("/governors", methods=["POST"])
@token_required
@role_required('admin')
def add_governor():
    data = get_json_body()
    svc = GovernanceService(_db_path)
    result = svc.add_governor(**data)
    return jsonify({"message": t("api.governance.created"), "data": result}), 201
@governance_bp.route("/meetings", methods=["GET"])
@token_required
@role_required('admin')
def list_meetings():
    svc = GovernanceService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_meetings(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@governance_bp.route("/meetings", methods=["POST"])
@token_required
@role_required('admin')
def create_meeting():
    data = get_json_body()
    svc = GovernanceService(_db_path)
    result = svc.create_meeting(**data)
    return jsonify({"message": t("api.governance.created"), "data": result}), 201
@governance_bp.route("/actions", methods=["GET"])
@token_required
@role_required('admin')
def list_actions():
    svc = GovernanceService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_actions(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@governance_bp.route("/actions", methods=["POST"])
@token_required
@role_required('admin')
def add_action():
    data = get_json_body()
    svc = GovernanceService(_db_path)
    result = svc.add_action(**data)
    return jsonify({"message": t("api.governance.created"), "data": result}), 201
@governance_bp.route("/strategic-plans", methods=["GET"])
@token_required
@role_required('admin')
def list_strategic_plans():
    svc = GovernanceService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_strategic_plans(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@governance_bp.route("/strategic-plans", methods=["POST"])
@token_required
@role_required('admin')
def add_strategic_plan():
    data = get_json_body()
    svc = GovernanceService(_db_path)
    result = svc.add_strategic_plan(**data)
    return jsonify({"message": t("api.governance.created"), "data": result}), 201
