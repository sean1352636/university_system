"""
Student Bank App — interactive CLI.

The command-line twin of the bank app GUI
(the GUI equivalent is My Finance Account,
``finance/interfaces/gui/finance_account.py``; the old ``BankApp`` window is in remove/).
Both act on the logged-in user's own finance account only — the owner is the
login's ``student_id`` or, failing that, its username — through the same
services: ``finance_integration`` for top-ups, transfers and the financial
summary, and ``domain.student_account`` for balance and history.

Covers every action on the GUI dashboard: balance with low-balance warning and
recent transactions, top up, send money, full transaction history and the
financial summary.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from education_system.systems.university.domains.finance.domain.student_account import (
    LOW_BALANCE_WARNING,
    MAX_TOPUP,
    QUICK_TOPUP_AMOUNTS,
    TOPUP_METHODS,
    ensure_account,
    get_account_balance,
    list_account_transactions,
)
from education_system.systems.university.domains.finance.interfaces.cli.account_io import (
    account_owner,
    confirm,
    current_user,
    display_name,
    header,
    money,
    pause,
    print_transactions,
    prompt,
    prompt_amount,
    prompt_choice,
    tr,
)

logger = logging.getLogger(__name__)

#: Top-up methods the GUI dialog offers (a subset of the account service's list).
_BANK_APP_TOPUP_METHODS = tuple(m for m in TOPUP_METHODS if m != "online")


def _integration():
    """The finance integration module, imported on first use (it is heavy)."""
    from education_system.systems.university.domains.finance.infrastructure import (
        finance_integration,
    )

    return finance_integration


# --------------------------------------------------------------------------- #
# Session
# --------------------------------------------------------------------------- #
def _open_session(auth: Any) -> Optional[Dict[str, Any]]:
    """Resolve the account owner the way the GUI does, creating the account."""
    student_id = account_owner(auth)
    if not student_id:
        print(tr("bank_app.error.login_required",
                       default="Please log in to use the bank app."))
        return None
    ensure_account(student_id)
    info = None
    try:
        info = _integration().get_student_info(student_id)
    except Exception:
        logger.debug("Student info lookup failed", exc_info=True)
    name = (info or {}).get("full_name") or display_name(
        current_user(auth), tr("bank_app.student.default_name", default="Student"))
    return {"student_id": student_id, "name": name.strip() or student_id}


# --------------------------------------------------------------------------- #
# 1. Dashboard
# --------------------------------------------------------------------------- #
def _show_dashboard(session: Dict[str, Any]) -> None:
    student_id = session["student_id"]
    header(tr("bank_app.dashboard.welcome", default="Welcome, {name}", name=session["name"]))
    print(tr("bank_app.dashboard.student_id", default="Student ID: {student_id}",
                   student_id=student_id))
    balance = get_account_balance(student_id)
    print(f"\n{tr('bank_app.dashboard.balance_title', default='Account Balance')}: {money(balance)}")
    if balance < LOW_BALANCE_WARNING:
        print(tr("bank_app.dashboard.low_balance_warning",
                       default="Low balance - consider topping up your account"))
    print(f"\n{tr('bank_app.transactions.recent_title', default='Recent Transactions')}")
    print_transactions(
        list_account_transactions(student_id, limit=10),
        tr("bank_app.transactions.no_transactions", default="No transactions yet"),
    )


# --------------------------------------------------------------------------- #
# 2. Top up
# --------------------------------------------------------------------------- #
def _top_up(session: Dict[str, Any]) -> None:
    student_id = session["student_id"]
    header(tr("bank_app.topup.header", default="Top Up Account"))
    print(tr("bank_app.topup.current_balance", default="Current balance: £{balance}",
                   balance=f"{get_account_balance(student_id):,.2f}"))
    quick = ", ".join(f"£{a}" for a in QUICK_TOPUP_AMOUNTS)
    print(tr("bank_app.topup.quick_topup", default="Quick top-up") + f": {quick}")
    amount = prompt_amount(tr("bank_app.topup.amount_label", default="Amount").rstrip(": £")
                           + " (£)")
    if amount is None:
        print(tr("cli.finance.account.cancelled", default="Cancelled."))
        return
    if amount > MAX_TOPUP:
        print(tr("bank_app.error.max_topup",
                       default="Maximum top-up is £{limit:,.2f}", limit=MAX_TOPUP))
        return
    print(tr("bank_app.topup.payment_method", default="Payment method"))
    method = prompt_choice(tr("cli.finance.account.choose_method", default="Method"),
                           _BANK_APP_TOPUP_METHODS, "card")
    result = _integration().top_up_student_finance_account(
        student_id=student_id, amount=amount, payment_method=method,
        processed_by=student_id,
        description=tr("bank_app.topup.description", default="Account top-up"),
    )
    if result.get("success"):
        print("\n✓ " + tr(
            "bank_app.topup.success_message",
            default="£{amount} added. New balance: £{balance}",
            amount=f"{amount:,.2f}", balance=f"{result.get('new_balance') or 0:,.2f}"))
    else:
        print("\n✗ " + (result.get("message") or tr(
            "bank_app.error.topup_failed", default="Top-up failed")))


# --------------------------------------------------------------------------- #
# 3. Send money
# --------------------------------------------------------------------------- #
def _send_money(session: Dict[str, Any]) -> None:
    student_id = session["student_id"]
    header(tr("bank_app.send_money.header", default="Send Money"))
    print(tr("bank_app.send_money.available", default="Available: £{balance}").format(
        balance=f"{get_account_balance(student_id):,.2f}"))
    recipient = prompt(tr("bank_app.send_money.recipient_label",
                                default="Recipient (Student ID or username)"))
    if not recipient:
        print(tr("bank_app.send_money.missing_recipient", default="Please enter a recipient"))
        return
    if recipient == student_id:
        print(tr("bank_app.transfer.self_transfer_error",
                       default="You cannot send money to your own account"))
        return
    amount = prompt_amount(tr("bank_app.send_money.amount_label", default="Amount: £").rstrip(": £"))
    if amount is None:
        print(tr("cli.finance.account.cancelled", default="Cancelled."))
        return
    reference = prompt(tr("bank_app.send_money.reference_label", default="Reference").rstrip(":")
                       + " (" + tr("bank_app.send_money.reference_hint",
                                         default="e.g. Meal out, money owed") + ")")
    if not reference:
        print(tr("bank_app.send_money.missing_reference",
                       default="Please enter a reference (e.g. Meal out, money owed)"))
        return
    question = tr("bank_app.send_money.confirm_message",
                        default="Send £{amount} to {recipient}?\nReference: {reference}").format(
        amount=f"{amount:,.2f}", recipient=recipient, reference=reference)
    if not confirm(question):
        print(tr("cli.finance.account.cancelled", default="Cancelled."))
        return
    result = _integration().transfer_student_finance_funds(
        from_student_id=student_id, to_student_id=recipient, amount=amount,
        reference=reference, processed_by=student_id,
    )
    if result.get("success"):
        print("\n✓ " + tr(
            "bank_app.send_money.success_message",
            default="£{amount} sent to {recipient}.\n\nReference Number: {reference_number}\nNew balance: £{balance}",
        ).format(amount=f"{amount:,.2f}",
                 recipient=result.get("recipient_name") or recipient,
                 reference_number=result.get("reference_number") or "",
                 balance=f"{result.get('new_balance') or 0:,.2f}"))
    else:
        print("\n✗ " + (result.get("message") or tr(
            "bank_app.transfer.failed", default="Transfer failed")))


# --------------------------------------------------------------------------- #
# 4. History
# --------------------------------------------------------------------------- #
def _history(session: Dict[str, Any]) -> None:
    header(tr("bank_app.history.header", default="Transaction History"))
    print(tr("bank_app.dashboard.student_id", default="Student ID: {student_id}",
                   student_id=session["student_id"]))
    print_transactions(
        list_account_transactions(session["student_id"], limit=50),
        tr("bank_app.transactions.no_transactions", default="No transactions yet"),
    )


# --------------------------------------------------------------------------- #
# 5. Financial summary
# --------------------------------------------------------------------------- #
def _summary(session: Dict[str, Any]) -> None:
    student_id = session["student_id"]
    header(tr("bank_app.summary.header", default="Financial Summary"))
    summary = _integration().get_student_financial_summary(student_id) or {}
    rows = (
        (tr("bank_app.summary.current_balance", default="Current Balance"),
         money(get_account_balance(student_id))),
        (tr("bank_app.summary.total_payments", default="Total Payments"),
         str(summary.get("total_payments", 0))),
        (tr("bank_app.summary.total_paid", default="Total Paid"),
         money(summary.get("total_paid", 0))),
        (tr("bank_app.summary.total_refunds", default="Total Refunds"),
         str(summary.get("total_refunds", 0))),
        (tr("bank_app.summary.total_refunded", default="Total Refunded"),
         money(summary.get("total_refunded", 0))),
        (tr("bank_app.summary.net_spent", default="Net Spent"),
         money(summary.get("net_paid", 0))),
    )
    print(f"\n{tr('bank_app.summary.overview_title', default='Overview')}")
    for label, value in rows:
        print(f"  {label:<24}{value:>14}")
    by_source = summary.get("payments_by_source") or {}
    if not by_source:
        return
    print(f"\n{tr('bank_app.summary.spending_by_category', default='Spending by Category')}")
    print(f"{tr('bank_app.summary.columns.category', default='Category'):<24}"
          f"{tr('bank_app.summary.columns.transactions', default='Transactions'):>14}"
          f"{tr('bank_app.summary.columns.total_spent', default='Total Spent'):>14}")
    print("-" * 52)
    for source, data in by_source.items():
        print(f"{str(source)[:23]:<24}{data.get('count', 0):>14}{money(data.get('amount', 0)):>14}")


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
_ACTIONS = (
    ("1", "bank_app.buttons.refresh", "Account dashboard", _show_dashboard),
    ("2", "bank_app.buttons.top_up", "Top up", _top_up),
    ("3", "bank_app.buttons.send_money", "Send money", _send_money),
    ("4", "bank_app.buttons.transaction_history", "Transaction history", _history),
    ("5", "bank_app.buttons.financial_summary", "Financial summary", _summary),
)


def run_bank_app_menu(auth: Any) -> None:
    """Run the student bank app loop for the logged-in user's own account."""
    session = _open_session(auth)
    if session is None:
        return
    actions = {key: action for key, _k, _d, action in _ACTIONS}
    while True:
        print("\n" + "=" * 50)
        print(f"       {tr('bank_app.window.title', default='STUDENT BANK APP')}")
        print("=" * 50)
        print(f"{session['name']}  ({session['student_id']})  "
              f"{money(get_account_balance(session['student_id']))}")
        print("-" * 50)
        for key, text_key, default, _action in _ACTIONS:
            print(f"{key}. {tr(text_key, default=default)}")
        print(f"0. {tr('cli.finance.account.return', default='Return')}")
        print("=" * 50)

        try:
            choice = input("\n" + tr("cli.finance.account.enter_choice",
                                           default="Enter your choice") + " (0-5): ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return
        if choice == "0":
            return
        action = actions.get(choice)
        if action is None:
            print(tr("cli.finance.account.invalid_choice", default="Invalid choice."))
            continue
        try:
            action(session)
        except KeyboardInterrupt:
            print("\n" + tr("cli.finance.account.cancelled", default="Cancelled."))
        except Exception as exc:  # keep the menu resilient
            logger.debug("Bank app action failed", exc_info=True)
            print(f"❌ {tr('cli.finance.account.error', default='Error')}: {exc}")
        pause()
