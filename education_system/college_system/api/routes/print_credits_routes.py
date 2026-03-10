"""API routes for print credits."""

from flask import Blueprint, jsonify, request
from education_system.college_system.api.auth import token_required, role_required
from education_system.college_system.api.validators import get_json_body, require_fields
from education_system.college_system.api.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.print_credits.services.print_credits_service import PrintCreditService

print_credit_bp = Blueprint("print-credits", __name__, url_prefix="/api/print-credits")

_db_path = None


def init_print_credit_routes(db_path=None):
    global _db_path
    _db_path = db_path


@print_credit_bp.route("", methods=["GET"])
@token_required
def list_accounts():
    svc = PrintCreditService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_accounts(limit=limit, offset=offset)
    total = svc.count_accounts()
    return jsonify(paginated_response(items, total))


@print_credit_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_account(pk):
    svc = PrintCreditService(_db_path)
    item = svc.get_account(pk)
    if not item:
        return jsonify({"error": "Account not found."}), 404
    return jsonify({"data": item})


@print_credit_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff", "instructor")
def create_account():
    data = get_json_body()
    require_fields(data, "student_id")
    svc = PrintCreditService(_db_path)
    item = svc.create_account(**data)
    return jsonify({"message": "Account created.", "data": item}), 201


@print_credit_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff", "instructor")
def update_account(pk):
    data = get_json_body()
    svc = PrintCreditService(_db_path)
    item = svc.update_account(pk, **data)
    return jsonify({"message": "Account updated.", "data": item})


@print_credit_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_account(pk):
    svc = PrintCreditService(_db_path)
    svc.delete_account(pk)
    return jsonify({"message": "Account deleted."})
