"""
My Finances — interactive CLI.

The command-line twin of the student finance account view: the "My Finances"
window (``shell/gui/main/features/finance_gui.py::show_student_finance_account``)
and the tabbed student finance dialog in ``finance/interfaces/gui/finance/
finance_gui.py`` (tabs Overview, Finance Account, Fees, Payments, Account
History, Refunds).

Scoped to the logged-in user's own account — the login's ``student_id`` or,
failing that, its username — and read-only except for the actions the GUI
offers on the Finance Account tab (top up, use balance, withdraw, export CSV).
All reads and writes go through ``domain.student_account`` and
``finance_integration``, the same services the GUI uses.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from education_system.systems.university.domains.finance.domain.student_account import (
    MAX_TOPUP,
    QUICK_TOPUP_AMOUNTS,
    TOPUP_METHODS,
    USE_PURPOSES,
    WITHDRAWAL_METHODS,
    ensure_account,
    export_account_transactions_csv,
    get_account_balance,
    get_account_overview,
    get_fee_summary,
    list_account_transactions,
    list_fees,
    list_payments,
    list_refunds,
    use_account_balance,
    withdraw_from_account,
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

_K = "cli.finance.my_finances"
_FILTERS = ("all", "deposit", "spend")


def _no_rows(key: str, default: str) -> None:
    print(f"\n{tr(f'{_K}.{key}', default)}")


# --------------------------------------------------------------------------- #
# Session
# --------------------------------------------------------------------------- #
def _open_session(auth: Any) -> Optional[Dict[str, Any]]:
    student_id = account_owner(auth)
    if not student_id:
        print(tr("finance_gui.errors.login_required", "Please log in to view your finances."))
        return None
    ensure_account(student_id)
    user = current_user(auth)
    return {
        "student_id": student_id,
        "name": display_name(user, student_id),
        "username": (user or {}).get("username") or student_id,
    }


# --------------------------------------------------------------------------- #
# 1. Overview
# --------------------------------------------------------------------------- #
def _overview(session: Dict[str, Any]) -> None:
    student_id = session["student_id"]
    header(tr("finance.labels.financial_summary", "Financial Summary"))
    print(tr("finance.dialogs.student_financial_details", "{name} (ID: {id})",
             name=session["name"], id=student_id))
    fees = get_fee_summary(student_id)
    rows = (
        (tr("finance.labels.total_fees", "Total Fees"), money(fees["total_fees"])),
        (tr("finance.labels.paid", "Paid"), money(fees["paid"])),
        (tr("finance.labels.outstanding", "Outstanding"), money(fees["outstanding"])),
        (tr("finance.labels.account_balance", "Account Balance"), money(get_account_balance(student_id))),
    )
    print()
    for label, value in rows:
        print(f"  {label:<22}{value:>14}")


# --------------------------------------------------------------------------- #
# 2. Finance account (balance, statistics, recent activity, actions)
# --------------------------------------------------------------------------- #
def _print_account_cards(student_id: str) -> None:
    overview = get_account_overview(student_id)
    print(f"\n  {tr('finance_gui.account.current_balance', 'Current Balance'):<22}"
          f"{money(overview['balance']):>14}")
    print(f"  {tr('finance_gui.account.total_deposited', 'Total Deposited'):<22}"
          f"{money(overview['total_deposited']):>14}")
    print(f"  {tr('finance_gui.account.total_spent', 'Total Spent'):<22}"
          f"{money(overview['total_spent']):>14}")
    print(f"  {tr('finance_gui.account.transactions', 'Transactions'):<22}"
          f"{overview['transaction_count']:>14}")


def _recent(session: Dict[str, Any]) -> None:
    print(tr(f"{_K}.filter_prompt", "Show: all / deposit (money in) / spend (money out)"))
    chosen = prompt_choice(tr(f"{_K}.filter", "Filter"), _FILTERS, "all")
    print(f"\n{tr('gui.shell.main.features.finance.labels.recent_transactions_last_20', 'Recent Transactions (Last 20)')}")
    print_transactions(list_account_transactions(session["student_id"], chosen, limit=20),
                       tr(f"{_K}.no_transactions", "No transactions yet."))


def _top_up(session: Dict[str, Any]) -> None:
    student_id = session["student_id"]
    print(tr("finance.labels.current_balance", "Current balance: £{balance}",
             balance=f"{get_account_balance(student_id):,.2f}"))
    quick = ", ".join(f"£{a}" for a in QUICK_TOPUP_AMOUNTS)
    print(tr("finance_gui.account.quick_top_up_amounts", "Quick top-up amounts").rstrip(": ") + f": {quick}")
    amount = prompt_amount(tr("finance.labels.top_up_amount", "Top-up amount (£)"))
    if amount is None:
        print(tr(f"{_K}.cancelled", "Cancelled."))
        return
    if amount > MAX_TOPUP:
        print(tr(f"{_K}.max_topup", "Maximum top-up is £{limit:,.2f}", limit=MAX_TOPUP))
        return
    print(tr("finance.labels.payment_method", "Payment method"))
    method = prompt_choice(tr(f"{_K}.choose_method", "Method"), TOPUP_METHODS, "card")
    from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
        top_up_student_finance_account,
    )

    result = top_up_student_finance_account(
        student_id=student_id, amount=amount, payment_method=method,
        processed_by=session["username"],
    )
    if result.get("success"):
        print("\n" + tr("finance_gui.account.top_up_success",
                        "✓ £{amount:,.2f} added. New balance: £{balance:,.2f}",
                        amount=amount, balance=result.get("new_balance") or 0))
    else:
        print("\n✗ " + (result.get("message") or tr(f"{_K}.topup_failed", "Top-up failed")))


def _use_balance(session: Dict[str, Any]) -> None:
    student_id = session["student_id"]
    balance = get_account_balance(student_id)
    print(tr("finance.labels.current_balance", "Current balance: £{balance}",
             balance=f"{balance:,.2f}"))
    amount = prompt_amount(tr("finance.labels.amount_to_use", "Amount to use (£)"))
    if amount is None:
        print(tr(f"{_K}.cancelled", "Cancelled."))
        return
    if amount > balance:
        print(tr("finance.errors.insufficient_balance", "Insufficient balance"))
        return
    print(tr("finance.labels.purpose", "Purpose"))
    purpose = prompt_choice(tr(f"{_K}.choose_purpose", "Purpose"), USE_PURPOSES, "fee_payment")
    description = prompt(tr("finance.labels.description_optional", "Description (optional)"))
    result = use_account_balance(student_id, amount, purpose=purpose, description=description,
                                 processed_by=session["username"])
    if result["success"]:
        print("\n✓ " + tr("finance.messages.use_balance_success",
                              "£{amount:,.2f} used. New balance: £{balance:,.2f}",
                              amount=amount, balance=result["new_balance"]))
    else:
        print("\n✗ " + result["message"])


def _withdraw(session: Dict[str, Any]) -> None:
    student_id = session["student_id"]
    balance = get_account_balance(student_id)
    print(tr("finance.labels.current_balance", "Current balance: £{balance}",
             balance=f"{balance:,.2f}"))
    amount = prompt_amount(tr("finance.labels.withdrawal_amount", "Withdrawal amount (£)"))
    if amount is None:
        print(tr(f"{_K}.cancelled", "Cancelled."))
        return
    if amount > balance:
        print(tr("finance.errors.insufficient_balance", "Insufficient balance"))
        return
    print(tr("finance.labels.withdrawal_method", "Withdrawal method"))
    method = prompt_choice(tr(f"{_K}.choose_method", "Method"), WITHDRAWAL_METHODS, "bank_transfer")
    reason = prompt(tr("finance.labels.reason_optional", "Reason (optional)"))
    if not confirm(tr("finance.dialogs.confirm_withdrawal_message",
                      "Withdraw £{amount:,.2f} via {method}?", amount=amount, method=method)):
        print(tr(f"{_K}.cancelled", "Cancelled."))
        return
    result = withdraw_from_account(student_id, amount, method=method, reason=reason,
                                   processed_by=session["username"])
    if result["success"]:
        print("\n✓ " + tr("finance.messages.withdrawal_success",
                              "£{amount:,.2f} withdrawn. New balance: £{balance:,.2f}",
                              amount=amount, balance=result["new_balance"]))
    else:
        print("\n✗ " + result["message"])


def _export_csv(session: Dict[str, Any]) -> None:
    student_id = session["student_id"]
    path = prompt(tr(f"{_K}.export_path", "CSV file path"), f"finance_account_{student_id}.csv")
    rows = export_account_transactions_csv(student_id, path)
    print("\n✓ " + tr("finance_gui.account.export_success",
                          "Exported {rows} transaction(s) to {filename}", rows=rows, filename=path))


_ACCOUNT_ACTIONS = (
    ("1", "gui.shell.main.features.finance.buttons.refresh", "Refresh balance and statistics",
     lambda s: _print_account_cards(s["student_id"])),
    ("2", "gui.shell.main.features.finance.labels.recent_transactions_last_20",
     "Recent transactions (filter all / deposits / spending)", _recent),
    ("3", "student_dashboard.buttons.top_up", "Top up", _top_up),
    ("4", "student_dashboard.buttons.use_balance", "Use balance", _use_balance),
    ("5", "student_dashboard.buttons.withdraw", "Withdraw", _withdraw),
    ("6", "gui.shell.main.features.finance.buttons.export_csv", "Export transactions (CSV)", _export_csv),
)


def _finance_account(session: Dict[str, Any]) -> None:
    """The Finance Account tab as a sub-menu."""
    actions = {key: action for key, _k, _d, action in _ACCOUNT_ACTIONS}
    while True:
        header(tr("finance.tabs.finance_account", "Finance Account"))
        _print_account_cards(session["student_id"])
        print()
        for key, text_key, default, _action in _ACCOUNT_ACTIONS:
            print(f"{key}. {tr(text_key, default)}")
        print(f"0. {tr(f'{_K}.back', 'Back')}")
        choice = input("\n" + tr(f"{_K}.enter_choice", "Enter your choice") + " (0-6): ").strip()
        if choice == "0":
            return
        action = actions.get(choice)
        if action is None:
            print(tr(f"{_K}.invalid_choice", "Invalid choice."))
            continue
        action(session)
        pause()


# --------------------------------------------------------------------------- #
# 3. Fees
# --------------------------------------------------------------------------- #
def _fees(session: Dict[str, Any]) -> None:
    header(tr("finance.tabs.fees", "Fees"))
    fees = list_fees(session["student_id"])
    if not fees:
        _no_rows("no_fees", "No fees recorded.")
        return
    print(f"\n{'ID':<7}{'Description':<32}{'Amount':>12}  {'Due Date':<12}Status")
    print("-" * 80)
    for fee in fees:
        status = (tr("finance.status.paid", "Paid") if fee["status"] == "paid"
                  else tr("finance.status.outstanding", "Outstanding"))
        print(f"{fee['fee_id']:<7}{fee['fee_name'][:31]:<32}{money(fee['amount']):>12}  "
              f"{fee['due_date'][:10]:<12}{status}")


# --------------------------------------------------------------------------- #
# 4. Payments
# --------------------------------------------------------------------------- #
def _payments(session: Dict[str, Any]) -> None:
    header(tr("finance.tabs.payments", "Payments"))
    payments = list_payments(session["student_id"])
    if not payments:
        _no_rows("no_payments", "No payments recorded.")
        return
    print(f"\n{'ID':<7}{'Amount':>12}  {'Date':<12}{'Method':<16}Reference")
    print("-" * 80)
    for payment in payments:
        print(f"{payment['payment_id']:<7}{money(payment['amount']):>12}  "
              f"{payment['payment_date'][:10]:<12}{payment['method'][:15]:<16}{payment['reference']}")


# --------------------------------------------------------------------------- #
# 5. Account history
# --------------------------------------------------------------------------- #
def _history(session: Dict[str, Any]) -> None:
    header(tr("finance.tabs.account_history", "Account History"))
    print_transactions(list_account_transactions(session["student_id"], limit=100),
                       tr(f"{_K}.no_transactions", "No transactions yet."))


# --------------------------------------------------------------------------- #
# 6. Refunds
# --------------------------------------------------------------------------- #
def _refunds(session: Dict[str, Any]) -> None:
    header(tr("finance.tabs.refunds", "Refunds"))
    search = prompt(tr("common.search", "Search") + " (" + tr(f"{_K}.optional", "optional") + ")")
    refunds = list_refunds(session["student_id"], search or None)
    if not refunds:
        _no_rows("no_refunds", "No refunds recorded.")
        return
    print(f"\n{'ID':<6}{'Reference':<16}{'Department':<14}{'Amount':>10}  {'Method':<16}{'Date':<12}By")
    print("-" * 90)
    for refund in refunds:
        print(f"{refund['refund_id']:<6}{refund['reference'][:15]:<16}{refund['department'][:13]:<14}"
              f"{money(refund['amount']):>10}  {refund['method'][:15]:<16}"
              f"{refund['refund_date'][:10]:<12}{refund['processed_by']}")
        if refund["notes"]:
            print(f"      {refund['notes'][:80]}")


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
_VIEWS = (
    ("1", "finance.tabs.overview", "Overview", _overview),
    ("2", "finance.tabs.finance_account", "Finance Account", _finance_account),
    ("3", "finance.tabs.fees", "Fees", _fees),
    ("4", "finance.tabs.payments", "Payments", _payments),
    ("5", "finance.tabs.account_history", "Account History", _history),
    ("6", "finance.tabs.refunds", "Refunds", _refunds),
)


def run_my_finances_menu(auth: Any) -> None:
    """Run the My Finances loop for the logged-in user's own account."""
    session = _open_session(auth)
    if session is None:
        return
    views = {key: view for key, _k, _d, view in _VIEWS}
    while True:
        print("\n" + "=" * 50)
        print(f"       {tr('finance_gui.account.title', 'MY FINANCES')}")
        print("=" * 50)
        print(f"{session['name']}  ({session['student_id']})  "
              f"{money(get_account_balance(session['student_id']))}")
        print("-" * 50)
        for key, text_key, default, _view in _VIEWS:
            print(f"{key}. {tr(text_key, default)}")
        print(f"0. {tr(f'{_K}.return', 'Return')}")
        print("=" * 50)

        try:
            choice = input("\n" + tr(f"{_K}.enter_choice", "Enter your choice") + " (0-6): ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return
        if choice == "0":
            return
        view = views.get(choice)
        if view is None:
            print(tr(f"{_K}.invalid_choice", "Invalid choice."))
            continue
        try:
            view(session)
        except KeyboardInterrupt:
            print("\n" + tr(f"{_K}.cancelled", "Cancelled."))
        except Exception as exc:  # keep the menu resilient
            logger.debug("My Finances view failed", exc_info=True)
            print(f"❌ {tr(f'{_K}.error', 'Error')}: {exc}")
        if view is not _finance_account:
            pause()
