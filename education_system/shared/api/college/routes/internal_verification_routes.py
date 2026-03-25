"""API routes for internal verification."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.internal_verification.services.internal_verification_service import InternalVerificationService
from education_system.college_system.core.i18n import t

internal_verification_bp = Blueprint("internal-verification", __name__, url_prefix="/api/internal-verification")

_db_path = None


def init_internal_verification_routes(db_path=None):
    global _db_path
    _db_path = db_path


@internal_verification_bp.route("/plans", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_plans():
    svc = InternalVerificationService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_plans(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@internal_verification_bp.route("/plans/<int:pk>", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_plan(pk):
    svc = InternalVerificationService(_db_path)
    item = svc.get_plan(pk)
    if not item:
        return jsonify({"error": t("api.internal_verification.not_found")}), 404
    return jsonify({"data": item})
@internal_verification_bp.route("/plans", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_plan():
    data = get_json_body()
    svc = InternalVerificationService(_db_path)
    result = svc.create_plan(**data)
    return jsonify({"message": t("api.internal_verification.created"), "data": result}), 201
@internal_verification_bp.route("/plans/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin', 'staff')
def update_plan(pk):
    data = get_json_body()
    svc = InternalVerificationService(_db_path)
    result = svc.update_plan(pk, **data)
    return jsonify({"message": t("api.internal_verification.updated"), "data": result})
@internal_verification_bp.route("/samples", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_samples():
    svc = InternalVerificationService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_samples(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@internal_verification_bp.route("/samples", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_sample():
    data = get_json_body()
    svc = InternalVerificationService(_db_path)
    result = svc.create_sample(**data)
    return jsonify({"message": t("api.internal_verification.created"), "data": result}), 201
@internal_verification_bp.route("/observations", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_observations():
    svc = InternalVerificationService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_observations(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@internal_verification_bp.route("/observations", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_observation():
    data = get_json_body()
    svc = InternalVerificationService(_db_path)
    result = svc.create_observation(**data)
    return jsonify({"message": t("api.internal_verification.created"), "data": result}), 201
@internal_verification_bp.route("/stats", methods=["GET"])
@token_required
@role_required('admin')
def get_stats():
    svc = InternalVerificationService(_db_path)
    result = svc.get_stats()
    return jsonify({"data": result})
