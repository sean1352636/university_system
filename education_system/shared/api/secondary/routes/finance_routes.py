"""Finance API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.admin.finance.services.finance_service import FinanceService

finance_bp = Blueprint("finance", __name__, url_prefix="/api/finance")

_db_path = None


def init_finance_routes(db_path=None):
    global _db_path
    _db_path = db_path


@finance_bp.route("/transactions", methods=["POST"])
@token_required
@role_required("admin")
def add_transaction():
    data = get_json_body()
    require_fields(data, "description", "amount", "category")
    svc = FinanceService(_db_path)
    result = svc.add_transaction(description=data["description"], amount=data["amount"], category=data["category"], transaction_type=data.get("transaction_type", "expense"))
    return jsonify({"message": "Created.", "data": result}), 201


@finance_bp.route("/transactions", methods=["GET"])
@token_required
@role_required("admin")
def list_transactions():
    svc = FinanceService(_db_path)
    result = svc.list_transactions()
    return jsonify({"data": result})


@finance_bp.route("/transactions/<int:txn_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_transaction(txn_id):
    svc = FinanceService(_db_path)
    result = svc.delete_transaction(txn_id)
    return jsonify({"message": "Deleted.", "data": result})


@finance_bp.route("/summary", methods=["GET"])
@token_required
@role_required("admin")
def get_summary():
    svc = FinanceService(_db_path)
    result = svc.get_summary()
    return jsonify({"data": result})


@finance_bp.route("/budgets", methods=["POST"])
@token_required
@role_required("admin")
def set_budget():
    data = get_json_body()
    require_fields(data, "department", "amount")
    svc = FinanceService(_db_path)
    result = svc.set_budget(data["department"], data["amount"], data.get("academic_year", ""))
    return jsonify({"message": "Created.", "data": result}), 201


@finance_bp.route("/budgets", methods=["GET"])
@token_required
@role_required("admin")
def list_budgets():
    svc = FinanceService(_db_path)
    result = svc.list_budgets()
    return jsonify({"data": result})

