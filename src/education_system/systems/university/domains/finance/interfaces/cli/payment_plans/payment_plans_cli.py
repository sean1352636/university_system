"""
Payment Plans — interactive CLI.

Wired to ``billing.payment_plan_service`` (list / schedule / edit / delete)
and the menu-driven functions in ``billing.payment_plans`` (template-based
creation, installment payments, cancellation), all of which read/write the
shared ``student_records.db`` — the same database the Payment Plans tab of
the Finance GUI uses.

Covers: list plans (optionally by status), view a plan and its installments,
create a plan with an equal-installment schedule, create from a template,
edit (amount / next due date / status / notes), delete, record an installment
payment, and cancel.
"""

from __future__ import annotations

import logging

from education_system.systems.university.domains.finance.domain.billing.payment_plan_service import (
    FREQUENCIES,
    PLAN_STATUSES,
    create_scheduled_plan,
    delete_payment_plan,
    get_payment_plan,
    list_installments,
    list_payment_plans,
    update_payment_plan,
)
from education_system.systems.university.domains.finance.interfaces.cli.common import (
    bind_legacy_auth,
    fail,
    money,
    ok,
    print_table,
    prompt,
    prompt_bool,
    prompt_choice,
    prompt_date,
    prompt_float,
    prompt_int,
    require_permission,
    run_menu,
    t,
)

logger = logging.getLogger(__name__)


def _student_label(row) -> str:
    name = f"{row.get('first_name') or ''} {row.get('last_name') or ''}".strip()
    return f"{row.get('student_id')} ({name})" if name else str(row.get('student_id'))


def _legacy():
    from education_system.systems.university.domains.finance.domain.billing import payment_plans
    return payment_plans


# --------------------------------------------------------------------------- #
# Views
# --------------------------------------------------------------------------- #
def _list_plans() -> None:
    status = prompt_choice(t('payment_plans.filter_status', "Status filter (blank = all)"),
                           PLAN_STATUSES)
    plans = list_payment_plans(status=status, limit=500)
    print_table(
        ['Plan', 'Student', 'Total', 'Remaining', 'Instalments', 'Frequency', 'Status', 'Start', 'Next due'],
        [[p['plan_id'], _student_label(p), money(p['total_amount']), money(p['remaining_amount']),
          p['installments'], p['frequency'], p['status'], p['start_date'], p['next_due_date']]
         for p in plans],
        empty=t('payment_plans.no_plans', "No payment plans found."),
    )


def _view_plan() -> None:
    plan_id = prompt_int(t('payment_plans.plan_id', "Plan id"), allow_blank=False)
    plan = get_payment_plan(plan_id)
    if plan is None:
        fail(t('payment_plans.not_found', "Payment plan {plan_id} not found.", plan_id=plan_id))
        return
    print(f"\n--- {t('payment_plans.plan_heading', 'Payment plan')} #{plan['plan_id']} ---")
    print(f"  {'Student':<14}: {_student_label(plan)}")
    print(f"  {'Template':<14}: {plan.get('template_name') or '-'}")
    print(f"  {'Total':<14}: {money(plan['total_amount'])}")
    print(f"  {'Remaining':<14}: {money(plan['remaining_amount'])}")
    print(f"  {'Status':<14}: {plan['status']}")
    print(f"  {'Start':<14}: {plan['start_date'] or '-'}")
    print(f"  {'Next due':<14}: {plan['next_due_date'] or '-'}")
    print(f"  {'Notes':<14}: {plan.get('notes') or '-'}")
    installments = list_installments(plan_id)
    print_table(['#', 'Amount', 'Due', 'Status', 'Payment', 'Late fee'],
                [[i['installment_number'], money(i['amount']), i['due_date'], i['status'],
                  i['payment_id'], money(i['late_fee_amount'])] for i in installments],
                empty=t('payment_plans.no_installments', "No installments recorded for this plan."))


# --------------------------------------------------------------------------- #
# Create / edit / delete
# --------------------------------------------------------------------------- #
def _create_plan() -> None:
    student_id = prompt(t('payment_plans.student_id', "Student id"))
    if not student_id:
        fail(t('payment_plans.student_required', "Student id is required."))
        return
    total = prompt_float(t('payment_plans.total_amount', "Total amount (£)"),
                         allow_blank=False, minimum=0.01)
    installments = prompt_int(t('payment_plans.installments', "Number of installments"),
                              allow_blank=False, minimum=1)
    frequency = prompt_choice(t('payment_plans.frequency', "Frequency"),
                              list(FREQUENCIES), default='monthly')
    start_date = prompt_date(t('payment_plans.start_date', "Start date (blank = today)"),
                             allow_blank=True)
    notes = prompt(t('payment_plans.notes', "Notes"))
    print(f"\n{installments} x {money(total / installments)} {frequency}")
    if not prompt_bool(t('payment_plans.confirm_create', "Create this payment plan?"), default=True):
        return
    result = create_scheduled_plan(student_id, total, installments, frequency, start_date, notes)
    ok(t('payment_plans.created',
         "Plan {plan_id} created: {count} x {amount}, first due {first}, last due {last}.",
         plan_id=result['plan_id'], count=installments, amount=money(result['installment_amount']),
         first=result['first_due'], last=result['last_due']))


def _create_from_template() -> None:
    _legacy().create_payment_plan()


def _edit_plan() -> None:
    plan_id = prompt_int(t('payment_plans.plan_id', "Plan id"), allow_blank=False)
    plan = get_payment_plan(plan_id)
    if plan is None:
        fail(t('payment_plans.not_found', "Payment plan {plan_id} not found.", plan_id=plan_id))
        return
    print(f"\n{_student_label(plan)} — {money(plan['total_amount'])} "
          f"({money(plan['remaining_amount'])} {t('payment_plans.remaining', 'remaining')}) "
          f"— {plan['status']} — {t('payment_plans.next_due', 'next due')} {plan['next_due_date'] or '-'}")
    print(t('payment_plans.blank_keeps', "Leave a field blank to keep its current value."))
    total = prompt_float(t('payment_plans.total_amount', "Total amount (£)"), minimum=0.01)
    next_due = prompt_date(t('payment_plans.next_due_date', "Next due date"), allow_blank=True)
    status = prompt_choice(t('payment_plans.status', "Status"), PLAN_STATUSES)
    notes = prompt(t('payment_plans.add_note', "Add a note"))
    if total is None and next_due is None and status is None and not notes:
        print(t('payment_plans.nothing_changed', "Nothing changed."))
        return
    updated = update_payment_plan(plan_id, total_amount=total, next_due_date=next_due,
                                  status=status, notes=notes or None)
    ok(t('payment_plans.updated', "Plan {plan_id} updated: {total} total, {remaining} remaining, {status}.",
         plan_id=plan_id, total=money(updated['total_amount']),
         remaining=money(updated['remaining_amount']), status=updated['status']))


def _delete_plan() -> None:
    plan_id = prompt_int(t('payment_plans.plan_id', "Plan id"), allow_blank=False)
    plan = get_payment_plan(plan_id)
    if plan is None:
        fail(t('payment_plans.not_found', "Payment plan {plan_id} not found.", plan_id=plan_id))
        return
    print(f"\n{_student_label(plan)} — {money(plan['total_amount'])} — {plan['status']}")
    if not prompt_bool(t('payment_plans.confirm_delete',
                         "Delete plan {plan_id} and its schedule?", plan_id=plan_id)):
        return
    delete_payment_plan(plan_id)
    ok(t('payment_plans.deleted', "Plan {plan_id} deleted.", plan_id=plan_id))


def _process_payment() -> None:
    _legacy().process_payment_plan_payment()


def _cancel_plan() -> None:
    _legacy().cancel_payment_plan()


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def run_payment_plans_menu(auth) -> None:
    """Run the Payment Plans CLI loop."""
    if not require_permission(auth):
        return
    bind_legacy_auth(auth, _legacy())

    run_menu(t('payment_plans.title', "PAYMENT PLANS"), [
        (t('payment_plans.menu.list', "List payment plans"), _list_plans),
        (t('payment_plans.menu.view', "View a plan and its installments"), _view_plan),
        (t('payment_plans.menu.create', "Create a plan (equal installments)"), _create_plan),
        (t('payment_plans.menu.create_template', "Create a plan from a template"), _create_from_template),
        (t('payment_plans.menu.edit', "Edit a plan"), _edit_plan),
        (t('payment_plans.menu.delete', "Delete a plan"), _delete_plan),
        (t('payment_plans.menu.pay', "Record an installment payment"), _process_payment),
        (t('payment_plans.menu.cancel', "Cancel a plan"), _cancel_plan),
    ], return_label=t('menu.return_finance', "Return to Finance Menu"))
