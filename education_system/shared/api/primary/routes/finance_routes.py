"""Finance API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.primary.auth import token_required, role_required
from education_system.shared.api.primary.validators import get_json_body, require_fields
from education_system.shared.api.primary.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.admin.finance.services.finance_service import FinanceService

finance_bp = Blueprint("finance", __name__, url_prefix="/api/finance")

_db_path = None


def init_finance_routes(db_path=None):
    global _db_path
    _db_path = db_path


@finance_bp.route("/transactions", methods=["GET"])
@token_required
@role_required("admin")
def list_transactions():
    svc = FinanceService(_db_path)
    items = svc.list_transactions()
    return jsonify({"data": items})


@finance_bp.route("/transactions", methods=["POST"])
@token_required
@role_required("admin")
def create_transaction():
    data = get_json_body()
    require_fields(data, "description", "amount", "category")
    svc = FinanceService(_db_path)
    result = svc.create_transaction(**data)
    return jsonify({"message": "Transaction created.", "data": result}), 201


@finance_bp.route("/budgets", methods=["GET"])
@token_required
@role_required("admin")
def list_budgets():
    svc = FinanceService(_db_path)
    items = svc.list_budgets()
    return jsonify({"data": items})


@finance_bp.route("/budgets", methods=["POST"])
@token_required
@role_required("admin")
def create_budget():
    data = get_json_body()
    require_fields(data, "category", "allocated_amount")
    svc = FinanceService(_db_path)
    result = svc.create_budget(**data)
    return jsonify({"message": "Budget created.", "data": result}), 201
