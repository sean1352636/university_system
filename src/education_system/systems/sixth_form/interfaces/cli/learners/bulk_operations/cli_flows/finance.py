"""CLI flows for finance bulk operations.

Split out of ``bulk_operations_cli.py``, which re-exports every name here.
"""

from __future__ import annotations

from datetime import date as _date

from education_system.systems.sixth_form.domain.learners.bulk_operations import ops_finance as bulk_ops_finance
from education_system.systems.sixth_form.domain.learners.bulk_operations.base import ValidationError

from education_system.systems.sixth_form.interfaces.cli.learners.bulk_operations.cli_flows.prompts import (
    _input,
    _pause,
    _pick_from,
    _pick_students,
    _print_result,
    _UserAbort,
    _yes_no,
)


def bulk_bursary_flow() -> None:
    print("\n═══ Bulk Bursary Award ═══")
    from education_system.systems.sixth_form.domains.finance.domain.bursaries.bursaries import (
        BURSARY_TYPES, ELIGIBILITY_BASES, DEFAULT_TYPE,
    )
    try:
        sids = _pick_students()
        btype = _pick_from("Bursary type", list(BURSARY_TYPES),
                              default=DEFAULT_TYPE)
        amount = float(_input("Amount awarded (£)", allow_empty=False))
        year = _input("Academic year (e.g. 2025/26)") or None
        basis = _pick_from(
            "Eligibility basis", [""] + list(ELIGIBILITY_BASES),
            default="")
        note = _input("Decision note") or None
        by = _input("Assessed by") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except (_UserAbort, ValueError):
        print("\n  Cancelled / bad input.")
        return
    try:
        r = bulk_ops_finance.bulk_bursary_award(
            sids, bursary_type=btype, amount_awarded=amount,
            academic_year=year, eligibility_basis=basis or None,
            decision_note=note, assessed_by=by, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_invoices_flow() -> None:
    print("\n═══ Bulk Raise Invoices ═══")
    from education_system.systems.sixth_form.domains.finance.domain.fees.fees import (
        CATEGORIES, DEFAULT_CATEGORY,
    )
    try:
        sids = _pick_students()
        desc = _input("Description", allow_empty=False)
        cat = _pick_from("Category", list(CATEGORIES),
                            default=DEFAULT_CATEGORY)
        amount = float(_input("Amount (£)", allow_empty=False))
        issued = _input("Issued date",
                           default=_date.today().isoformat())
        due = _input("Due date (optional)") or None
        year = _input("Academic year (optional)") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except (_UserAbort, ValueError):
        print("\n  Cancelled / bad input.")
        return
    try:
        r = bulk_ops_finance.bulk_raise_invoices(
            sids, description=desc, category=cat, amount=amount,
            issued_date=issued, due_date=due, academic_year=year,
            dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_discount_flow() -> None:
    print("\n═══ Bulk Fee Discount / Waiver ═══")
    from education_system.systems.sixth_form.domains.finance.domain.fees.fees import (
        CATEGORIES, DEFAULT_CATEGORY,
    )
    try:
        sids = _pick_students()
        desc = _input("Description", allow_empty=False)
        amount = float(_input("Discount amount (£, positive)",
                                 allow_empty=False))
        cat = _pick_from("Category", list(CATEGORIES),
                            default=DEFAULT_CATEGORY)
        issued = _input("Issued date",
                           default=_date.today().isoformat())
        year = _input("Academic year (optional)") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except (_UserAbort, ValueError):
        print("\n  Cancelled / bad input.")
        return
    try:
        r = bulk_ops_finance.bulk_fee_discount(
            sids, description=desc, amount=amount, category=cat,
            issued_date=issued, academic_year=year, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_payments_csv_flow() -> None:
    print("\n═══ Bulk Import Payments CSV ═══")
    print("  Required: fee_id, amount, paid_on, method")
    print("  Optional: reference, notes")
    try:
        path = _input("CSV path", allow_empty=False)
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_finance.bulk_import_payments(path, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_statements_flow() -> None:
    print("\n═══ Bulk Financial Statements ═══")
    try:
        sids = _pick_students()
        out_dir = _input("Output directory", allow_empty=False)
        year = _input("Academic year filter (optional)") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_finance.bulk_financial_statements(
            sids, output_dir=out_dir, academic_year=year, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)
