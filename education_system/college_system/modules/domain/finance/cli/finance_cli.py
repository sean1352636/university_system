"""Finance CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.finance.services.finance_service import FinanceService
from education_system.college_system.infrastructure.auth.core import UserAuth


def finance_menu(auth: UserAuth):
    """Finance management menu."""
    svc = FinanceService(auth._db_path)

    while True:
        print_header("Finance Management")
        options = [
            ("1", "Fee Items"),
            ("2", "New Fee Item"),
            ("3", "Invoices"),
            ("4", "Generate Invoice"),
            ("5", "Record Payment"),
            ("6", "Student Balance"),
            ("7", "Overdue Invoices"),
            ("8", "Payroll Records"),
            ("9", "New Payroll Record"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_fees(svc)
        elif choice == "2":
            _new_fee(svc)
        elif choice == "3":
            _list_invoices(svc)
        elif choice == "4":
            _generate_invoice(svc)
        elif choice == "5":
            _record_payment(svc, auth)
        elif choice == "6":
            _student_balance(svc)
        elif choice == "7":
            _overdue(svc)
        elif choice == "8":
            _list_payroll(svc)
        elif choice == "9":
            _new_payroll(svc)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_fees(svc):
    print_header("Fee Items")
    try:
        fees = svc.list_fee_items()
        if not fees:
            print("\n  No fee items found.")
            return
        print(f"\n  {'ID':<5} {'Title':<25} {'Type':<12} {'Amount':<10} {'Mandatory'}")
        print(f"  {'-'*60}")
        for f in fees:
            mand = "Yes" if f["mandatory"] else "No"
            print(f"  {f['id']:<5} {f['title']:<25} {f['fee_type']:<12} "
                  f"{f['amount']:<10.2f} {mand}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_fee(svc):
    print_header("New Fee Item")
    try:
        title = input("  Title: ").strip()
        fee_type = input("  Type (tuition/exam/trip/materials/other) [tuition]: ").strip() or "tuition"
        amount = float(input("  Amount: ").strip())
        academic_year = input("  Academic Year (optional): ").strip() or None

        fee = svc.create_fee_item(title, fee_type, amount, academic_year=academic_year)
        print(f"\n  Fee item created (ID: {fee['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _list_invoices(svc):
    print_header("Invoices")
    try:
        invoices = svc.list_invoices()
        if not invoices:
            print("\n  No invoices found.")
            return
        print(f"\n  {'ID':<5} {'Student':<10} {'Amount':<10} {'Paid':<10} {'Status':<10} {'Due'}")
        print(f"  {'-'*60}")
        for inv in invoices:
            print(f"  {inv['id']:<5} {inv['student_id']:<10} {inv['amount']:<10.2f} "
                  f"{inv['paid_amount']:<10.2f} {inv['status']:<10} {inv.get('due_date') or '-'}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _generate_invoice(svc):
    print_header("Generate Invoice")
    try:
        student_id = int(input("  Student PK: ").strip())
        fee_item_id = int(input("  Fee Item ID: ").strip())
        due_date = input("  Due Date (YYYY-MM-DD, optional): ").strip() or None

        inv = svc.create_invoice(student_id, fee_item_id, due_date=due_date)
        print(f"\n  Invoice created (ID: {inv['id']}, Amount: {inv['amount']:.2f}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _record_payment(svc, auth):
    print_header("Record Payment")
    try:
        invoice_id = int(input("  Invoice ID: ").strip())
        amount = float(input("  Amount: ").strip())
        method = input("  Method (cash/card/bank_transfer/bursary_offset) [cash]: ").strip() or "cash"
        reference = input("  Reference (optional): ").strip() or None

        user_id = auth.current_user.get("user_id", 0)
        payment = svc.record_payment(invoice_id, amount, method, reference, user_id)
        print(f"\n  Payment recorded (ID: {payment['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _student_balance(svc):
    print_header("Student Balance")
    try:
        student_id = int(input("  Student PK: ").strip())
        balance = svc.get_student_balance(student_id)
        print(f"\n  Total Invoiced: {balance['total_invoiced']:.2f}")
        print(f"  Total Paid: {balance['total_paid']:.2f}")
        print(f"  Balance Due: {balance['balance_due']:.2f}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _overdue(svc):
    print_header("Overdue Invoices")
    try:
        invoices = svc.get_overdue_invoices()
        if not invoices:
            print("\n  No overdue invoices.")
            return
        print(f"\n  {'ID':<5} {'Student':<20} {'Amount':<10} {'Due':<12} {'Status'}")
        print(f"  {'-'*55}")
        for inv in invoices:
            name = f"{inv.get('first_name', '')} {inv.get('last_name', '')}"
            print(f"  {inv['id']:<5} {name:<20} {inv['amount']:<10.2f} "
                  f"{inv.get('due_date', '-'):<12} {inv['status']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _list_payroll(svc):
    print_header("Payroll Records")
    try:
        records = svc.list_payroll()
        if not records:
            print("\n  No payroll records found.")
            return
        print(f"\n  {'ID':<5} {'Staff':<8} {'Period':<12} {'Gross':<10} {'Net':<10} {'Status'}")
        print(f"  {'-'*55}")
        for r in records:
            print(f"  {r['id']:<5} {r['staff_id']:<8} {r['pay_period']:<12} "
                  f"{r['gross_pay']:<10.2f} {r['net_pay']:<10.2f} {r['status']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_payroll(svc):
    print_header("New Payroll Record")
    try:
        staff_id = int(input("  Staff ID: ").strip())
        pay_period = input("  Pay Period (e.g. 2025-01): ").strip()
        gross_pay = float(input("  Gross Pay: ").strip())
        deductions = float(input("  Deductions [0]: ").strip() or "0")

        record = svc.create_payroll_record(staff_id, pay_period, gross_pay, deductions)
        print(f"\n  Payroll record created (ID: {record['id']}, Net: {record['net_pay']:.2f}).")
    except Exception as e:
        print(f"\n  Error: {e}")
