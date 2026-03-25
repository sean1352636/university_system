"""API routes for prevent duty."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.prevent_duty.services.prevent_duty_service import PreventDutyService
from education_system.college_system.core.i18n import t

prevent_duty_bp = Blueprint("prevent-duty", __name__, url_prefix="/api/prevent-duty")

_db_path = None


def init_prevent_duty_routes(db_path=None):
    global _db_path
    _db_path = db_path


@prevent_duty_bp.route("/referrals", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_referrals():
    svc = PreventDutyService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_referrals(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@prevent_duty_bp.route("/referrals/<int:pk>", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_referral(pk):
    svc = PreventDutyService(_db_path)
    item = svc.get_referral(pk)
    if not item:
        return jsonify({"error": t("api.prevent_duty.not_found")}), 404
    return jsonify({"data": item})
@prevent_duty_bp.route("/referrals", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_referral():
    data = get_json_body()
    svc = PreventDutyService(_db_path)
    result = svc.create_referral(**data)
    return jsonify({"message": t("api.prevent_duty.created"), "data": result}), 201
@prevent_duty_bp.route("/referrals/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin', 'staff')
def update_referral(pk):
    data = get_json_body()
    svc = PreventDutyService(_db_path)
    result = svc.update_referral(pk, **data)
    return jsonify({"message": t("api.prevent_duty.updated"), "data": result})
@prevent_duty_bp.route("/training", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_training():
    svc = PreventDutyService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_training(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@prevent_duty_bp.route("/training", methods=["POST"])
@token_required
@role_required('admin')
def create_training():
    data = get_json_body()
    svc = PreventDutyService(_db_path)
    result = svc.create_training(**data)
    return jsonify({"message": t("api.prevent_duty.created"), "data": result}), 201
@prevent_duty_bp.route("/stats", methods=["GET"])
@token_required
@role_required('admin')
def get_stats():
    svc = PreventDutyService(_db_path)
    result = svc.get_stats()
    return jsonify({"data": result})
