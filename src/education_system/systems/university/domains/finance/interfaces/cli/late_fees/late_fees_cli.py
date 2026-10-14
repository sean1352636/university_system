"""
Late Fees — interactive CLI.

Wired to ``billing.late_fees`` (list / apply / waive / flat overdue sweep) and
the menu-driven ``billing.fee_structure`` functions (per-fee-type late-fee
rules, waive by student), all of which read/write the shared
``student_records.db`` — the same database the Late Fees tab of the Finance
GUI uses.

Covers: list late fees, view one, preview overdue fees that carry no late fee,
apply a flat percentage to all of them, apply the configured fee-type rules,
apply a late fee by hand, waive by late-fee id, and waive by student.
"""

from __future__ import annotations

import logging

from education_system.systems.university.domains.finance.domain.billing.late_fees import (
    CALCULATION_METHODS,
    DEFAULT_OVERDUE_RATE,
    apply_late_fee,
    apply_overdue_late_fees,
    get_late_fee,
    list_late_fees,
    list_overdue_fees_without_late_fee,
    waive_late_fee_by_id,
)
from education_system.systems.university.domains.finance.interfaces.cli.common import (
    bind_legacy_auth,
    current_username,
    fail,
    money,
    ok,
    print_table,
    prompt,
    prompt_bool,
    prompt_choice,
    prompt_float,
    prompt_int,
    require_permission,
    run_menu,
    t,
)

logger = logging.getLogger(__name__)


def _legacy():
    from education_system.systems.university.domains.finance.domain.billing import fee_structure
    return fee_structure


def _fee_rows(fees):
    return [[f['late_fee_id'], f['student_fee_id'], f['student_id'], money(f['fee_amount']),
             money(f['late_fee_amount']), f['days_overdue'], f['calculation_method'],
             f['applied_date'], 'yes' if f['waived'] else 'no', f['waiver_reason']] for f in fees]


_FEE_HEADERS = ['Late fee', 'Student fee', 'Student', 'Fee', 'Late amount', 'Days', 'Method',
                'Applied', 'Waived', 'Reason']


# --------------------------------------------------------------------------- #
# Views
# --------------------------------------------------------------------------- #
def _list_fees() -> None:
    include_waived = prompt_bool(t('late_fees.include_waived', "Include waived fees?"), default=True)
    fees = list_late_fees(limit=500, include_waived=include_waived)
    print_table(_FEE_HEADERS, _fee_rows(fees),
                empty=t('late_fees.none', "No late fees recorded."))


def _view_fee() -> None:
    late_fee_id = prompt_int(t('late_fees.late_fee_id', "Late fee id"), allow_blank=False)
    fee = get_late_fee(late_fee_id)
    if fee is None:
        fail(t('late_fees.not_found', "Late fee {late_fee_id} not found.", late_fee_id=late_fee_id))
        return
    print(f"\n--- {t('late_fees.heading', 'Late fee')} #{fee['late_fee_id']} ---")
    for key in ('student_fee_id', 'student_id', 'fee_amount', 'late_fee_amount', 'days_overdue',
                'calculation_method', 'applied_date', 'waived', 'waived_by', 'waived_date',
                'waiver_reason'):
        value = fee.get(key)
        if key in ('fee_amount', 'late_fee_amount'):
            value = money(value)
        elif key == 'waived':
            value = 'yes' if value else 'no'
        print(f"  {key:<20}: {value if value not in (None, '') else '-'}")


def _preview_overdue() -> None:
    overdue = list_overdue_fees_without_late_fee()
    print_table(['Student fee', 'Student', 'Amount', 'Due', 'Days overdue'],
                [[f['student_fee_id'], f['student_id'], money(f['amount']), f['due_date'],
                  f['days_overdue']] for f in overdue],
                empty=t('late_fees.no_overdue', "No overdue fees without a late fee."))
    if overdue:
        print(t('late_fees.overdue_total', "Total overdue: {total}",
                total=money(sum(float(f['amount'] or 0) for f in overdue))))


# --------------------------------------------------------------------------- #
# Apply
# --------------------------------------------------------------------------- #
def _calculate_overdue() -> None:
    overdue = list_overdue_fees_without_late_fee()
    if not overdue:
        print('\n' + t('late_fees.no_overdue', "No overdue fees without a late fee."))
        return
    percent = prompt_float(t('late_fees.rate_percent', "Late fee rate (% of the fee amount)"),
                           default=DEFAULT_OVERDUE_RATE * 100, minimum=0.01)
    if not prompt_bool(t('late_fees.confirm_sweep', "Apply {percent:g}% to {count} overdue fee(s)?",
                         percent=percent, count=len(overdue))):
        return
    result = apply_overdue_late_fees(rate=percent / 100)
    ok(t('late_fees.sweep_done', "Applied {applied} late fee(s) totalling {total}.",
         applied=result['applied'], total=money(result['total'])))


def _calculate_by_rules() -> None:
    _legacy().calculate_late_fees()


def _apply_manual() -> None:
    student_fee_id = prompt_int(t('late_fees.student_fee_id', "Student fee id"), allow_blank=False)
    amount = prompt_float(t('late_fees.amount', "Late fee amount (£)"), allow_blank=False, minimum=0.01)
    method = prompt_choice(t('late_fees.method', "Calculation method"), CALCULATION_METHODS, default='fixed')
    days = prompt_int(t('late_fees.days_overdue', "Days overdue"), allow_blank=False, minimum=0)
    late_fee_id = apply_late_fee(student_fee_id, amount, method, days)
    ok(t('late_fees.applied', "Late fee {late_fee_id} of {amount} applied to student fee {student_fee_id}.",
         late_fee_id=late_fee_id, amount=money(amount), student_fee_id=student_fee_id))


# --------------------------------------------------------------------------- #
# Waive
# --------------------------------------------------------------------------- #
def _waive_by_id(auth) -> None:
    late_fee_id = prompt_int(t('late_fees.late_fee_id', "Late fee id"), allow_blank=False)
    fee = get_late_fee(late_fee_id)
    if fee is None:
        fail(t('late_fees.not_found', "Late fee {late_fee_id} not found.", late_fee_id=late_fee_id))
        return
    if fee['waived']:
        fail(t('late_fees.already_waived', "Late fee {late_fee_id} is already waived.",
               late_fee_id=late_fee_id))
        return
    print(f"\n{t('late_fees.student', 'Student')} {fee['student_id']} — "
          f"{money(fee['late_fee_amount'])} ({fee['calculation_method']}, "
          f"{t('late_fees.applied_on', 'applied')} {fee['applied_date']})")
    reason = prompt(t('late_fees.waiver_reason', "Waiver reason"))
    if not reason:
        fail(t('late_fees.reason_required', "A waiver reason is required."))
        return
    if not prompt_bool(t('late_fees.confirm_waive', "Waive this late fee?"), default=True):
        return
    waive_late_fee_by_id(late_fee_id, reason, waived_by=current_username(auth))
    ok(t('late_fees.waived', "Late fee {late_fee_id} waived.", late_fee_id=late_fee_id))


def _waive_by_student() -> None:
    _legacy().waive_late_fee()


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def run_late_fees_menu(auth) -> None:
    """Run the Late Fees CLI loop."""
    if not require_permission(auth):
        return
    bind_legacy_auth(auth, _legacy())

    run_menu(t('late_fees.title', "LATE FEES"), [
        (t('late_fees.menu.list', "List late fees"), _list_fees),
        (t('late_fees.menu.view', "View a late fee"), _view_fee),
        (t('late_fees.menu.preview', "Preview overdue fees without a late fee"), _preview_overdue),
        (t('late_fees.menu.sweep', "Calculate overdue (flat percentage on all)"), _calculate_overdue),
        (t('late_fees.menu.rules', "Calculate late fees from fee-type rules"), _calculate_by_rules),
        (t('late_fees.menu.apply', "Apply a late fee by hand"), _apply_manual),
        (t('late_fees.menu.waive', "Waive a late fee by id"), lambda: _waive_by_id(auth)),
        (t('late_fees.menu.waive_student', "Waive late fees by student"), _waive_by_student),
    ], return_label=t('menu.return_finance', "Return to Finance Menu"))
