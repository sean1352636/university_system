"""API routes for onboarding."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.onboarding.services.onboarding_service import OnboardingService
from education_system.college_system.core.i18n import t

onboarding_bp = Blueprint("onboarding", __name__, url_prefix="/api/onboarding")

_db_path = None


def init_onboarding_routes(db_path=None):
    global _db_path
    _db_path = db_path


@onboarding_bp.route("/checklists", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_checklists():
    svc = OnboardingService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_checklists(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@onboarding_bp.route("/checklists/<int:pk>", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_checklist(pk):
    svc = OnboardingService(_db_path)
    item = svc.get_checklist(pk)
    if not item:
        return jsonify({"error": t("api.onboarding.not_found")}), 404
    return jsonify({"data": item})
@onboarding_bp.route("/checklists", methods=["POST"])
@token_required
@role_required('admin')
def create_checklist():
    data = get_json_body()
    svc = OnboardingService(_db_path)
    result = svc.create_checklist(**data)
    return jsonify({"message": t("api.onboarding.created"), "data": result}), 201
@onboarding_bp.route("/checklists/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin')
def update_checklist(pk):
    data = get_json_body()
    svc = OnboardingService(_db_path)
    result = svc.update_checklist(pk, **data)
    return jsonify({"message": t("api.onboarding.updated"), "data": result})
@onboarding_bp.route("/tasks", methods=["GET"])
@token_required
def list_tasks():
    svc = OnboardingService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_tasks(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@onboarding_bp.route("/tasks", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_task():
    data = get_json_body()
    svc = OnboardingService(_db_path)
    result = svc.create_task(**data)
    return jsonify({"message": t("api.onboarding.created"), "data": result}), 201
@onboarding_bp.route("/tasks/<int:pk>/complete", methods=["POST"])
@token_required
def complete_task(pk):
    data = get_json_body()
    svc = OnboardingService(_db_path)
    result = svc.complete_task(pk, **data)
    return jsonify({"message": t("api.onboarding.success"), "data": result}), 201
@onboarding_bp.route("/stats", methods=["GET"])
@token_required
@role_required('admin')
def get_stats():
    svc = OnboardingService(_db_path)
    result = svc.get_stats()
    return jsonify({"data": result})
