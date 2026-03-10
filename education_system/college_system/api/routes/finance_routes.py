"""Finance API routes."""

from flask import Blueprint, jsonify, request, g

from education_system.college_system.api.auth import token_required, role_required
from education_system.college_system.api.validators import get_json_body, require_fields
from education_system.college_system.modules.domain.finance.services.finance_service import FinanceService

finance_bp = Blueprint("finance", __name__, url_prefix="/api/finance")

_db_path = None


def init_finance_routes(db_path=None):
    global _db_path
    _db_path = db_path


@finance_bp.route("/fees", methods=["POST"])
@token_required
@role_required("admin")
def create_fee_item():
    data = get_json_body()
    require_fields(data, "title", "amount")
    svc = FinanceService(_db_path)
    fee = svc.create_fee_item(
        data["title"], data.get("fee_type", "tuition"),
        data["amount"], academic_year=data.get("academic_year"),
        mandatory=data.get("mandatory", True),
    )
    return jsonify({"message": "Fee item created.", "data": fee}), 201


@finance_bp.route("/fees", methods=["GET"])
@token_required
def list_fee_items():
    svc = FinanceService(_db_path)
    fee_type = request.args.get("fee_type")
    fees = svc.list_fee_items(fee_type=fee_type)
    return jsonify({"data": fees, "count": len(fees)})


@finance_bp.route("/invoices", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_invoice():
    data = get_json_body()
    require_fields(data, "student_id", "fee_item_id")
    svc = FinanceService(_db_path)
    inv = svc.create_invoice(
        data["student_id"], data["fee_item_id"],
        amount=data.get("amount"), due_date=data.get("due_date"),
    )
    return jsonify({"message": "Invoice created.", "data": inv}), 201


@finance_bp.route("/invoices", methods=["GET"])
@token_required
def list_invoices():
    svc = FinanceService(_db_path)
    student_id = request.args.get("student_id", type=int)
    status = request.args.get("status")
    invoices = svc.list_invoices(student_id=student_id, status=status)
    return jsonify({"data": invoices, "count": len(invoices)})


@finance_bp.route("/invoices/<int:invoice_id>", methods=["GET"])
@token_required
def get_invoice(invoice_id):
    svc = FinanceService(_db_path)
    inv = svc.get_invoice(invoice_id)
    if not inv:
        return jsonify({"error": "Invoice not found."}), 404
    return jsonify({"data": inv})


@finance_bp.route("/payments", methods=["POST"])
@token_required
@role_required("admin", "staff")
def record_payment():
    data = get_json_body()
    require_fields(data, "invoice_id", "amount")
    svc = FinanceService(_db_path)
    payment = svc.record_payment(
        data["invoice_id"], data["amount"],
        payment_method=data.get("payment_method", "cash"),
        reference=data.get("reference"),
        recorded_by=g.current_user.get("user_id", 0),
    )
    return jsonify({"message": "Payment recorded.", "data": payment}), 201


@finance_bp.route("/payments", methods=["GET"])
@token_required
def list_payments():
    svc = FinanceService(_db_path)
    invoice_id = request.args.get("invoice_id", type=int)
    payments = svc.list_payments(invoice_id=invoice_id)
    return jsonify({"data": payments, "count": len(payments)})


@finance_bp.route("/balance/<int:student_id>", methods=["GET"])
@token_required
def student_balance(student_id):
    svc = FinanceService(_db_path)
    balance = svc.get_student_balance(student_id)
    return jsonify({"data": balance})


@finance_bp.route("/overdue", methods=["GET"])
@token_required
@role_required("admin", "staff")
def overdue_invoices():
    svc = FinanceService(_db_path)
    invoices = svc.get_overdue_invoices()
    return jsonify({"data": invoices, "count": len(invoices)})


@finance_bp.route("/payroll", methods=["POST"])
@token_required
@role_required("admin")
def create_payroll():
    data = get_json_body()
    require_fields(data, "staff_id", "pay_period", "gross_pay")
    svc = FinanceService(_db_path)
    record = svc.create_payroll_record(
        data["staff_id"], data["pay_period"], data["gross_pay"],
        deductions=data.get("deductions", 0),
        payment_date=data.get("payment_date"),
    )
    return jsonify({"message": "Payroll record created.", "data": record}), 201


@finance_bp.route("/payroll", methods=["GET"])
@token_required
@role_required("admin")
def list_payroll():
    svc = FinanceService(_db_path)
    staff_id = request.args.get("staff_id", type=int)
    status = request.args.get("status")
    records = svc.list_payroll(staff_id=staff_id, status=status)
    return jsonify({"data": records, "count": len(records)})


@finance_bp.route("/payroll/<int:payroll_id>/status", methods=["PUT"])
@token_required
@role_required("admin")
def update_payroll_status(payroll_id):
    data = get_json_body()
    require_fields(data, "status")
    svc = FinanceService(_db_path)
    record = svc.update_payroll_status(payroll_id, data["status"])
    return jsonify({"message": "Payroll status updated.", "data": record})
