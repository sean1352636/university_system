"""API routes for expense claims."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.expense_claims.services.expense_claims_service import ExpenseClaimService
from education_system.college_system.core.i18n import t

expense_claims_bp = Blueprint("expense-claims", __name__, url_prefix="/api/expense-claims")

_db_path = None


def init_expense_claims_routes(db_path=None):
    global _db_path
    _db_path = db_path


@expense_claims_bp.route("", methods=["GET"])
@token_required
def list_claims():
    svc = ExpenseClaimService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_claims(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@expense_claims_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_claim(pk):
    svc = ExpenseClaimService(_db_path)
    item = svc.get_claim(pk)
    if not item:
        return jsonify({"error": t("api.expense_claims.not_found")}), 404
    return jsonify({"data": item})
@expense_claims_bp.route("", methods=["POST"])
@token_required
def create_claim():
    data = get_json_body()
    svc = ExpenseClaimService(_db_path)
    result = svc.create_claim(**data)
    return jsonify({"message": t("api.expense_claims.created"), "data": result}), 201
@expense_claims_bp.route("/<int:pk>", methods=["PUT"])
@token_required
def update_claim(pk):
    data = get_json_body()
    svc = ExpenseClaimService(_db_path)
    result = svc.update_claim(pk, **data)
    return jsonify({"message": t("api.expense_claims.updated"), "data": result})
@expense_claims_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required('admin')
def delete_claim(pk):
    svc = ExpenseClaimService(_db_path)
    svc.delete_claim(pk)
    return jsonify({"message": t("api.expense_claims.deleted")})
@expense_claims_bp.route("/<int:pk>/approve", methods=["POST"])
@token_required
@role_required('admin')
def approve_claim(pk):
    data = get_json_body()
    svc = ExpenseClaimService(_db_path)
    result = svc.approve_claim(pk, **data)
    return jsonify({"message": t("api.expense_claims.success"), "data": result}), 201
@expense_claims_bp.route("/<int:pk>/reject", methods=["POST"])
@token_required
@role_required('admin')
def reject_claim(pk):
    data = get_json_body()
    svc = ExpenseClaimService(_db_path)
    result = svc.reject_claim(pk, **data)
    return jsonify({"message": t("api.expense_claims.success"), "data": result}), 201
@expense_claims_bp.route("/stats", methods=["GET"])
@token_required
@role_required('admin')
def get_stats():
    svc = ExpenseClaimService(_db_path)
    result = svc.get_stats()
    return jsonify({"data": result})
