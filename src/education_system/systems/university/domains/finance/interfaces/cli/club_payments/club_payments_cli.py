"""
Club Payments — interactive CLI.

Command-line twin of the Finance GUI club-payments tab
(``layout/_club_payments.py``) and the Club Payment Management window
(``shell/gui/main/features/finance_gui.py``).  Both call
``domain/core/club_payments`` against the shared ``payments`` table.

Covers: overview statistics, recording a club payment (posted to the ledger)
and the recent payment history.
"""

from __future__ import annotations

from datetime import datetime
import logging

from education_system.systems.university.domains.finance.domain.core import club_payments
from education_system.systems.university.domains.finance.interfaces.cli.support import (
    current_username,
    header,
    money,
    print_table,
    prompt,
    prompt_choice,
    prompt_date,
    prompt_float,
    prompt_int,
    require_finance_access,
    run_menu,
    text,
)

logger = logging.getLogger(__name__)


def _overview() -> None:
    days = prompt_int(text("finance_cli.club_payments.days", "Window (days)"), 30, minimum=1)
    stats = club_payments.club_payment_overview(days)
    header(text("finance_cli.club_payments.overview_title", "CLUB PAYMENT OVERVIEW (LAST {days} DAYS)",
                days=days))
    print_table(
        ("Metric", "Value"),
        [
            (text("finance_cli.club_payments.total_payments", "Total payments"),
             stats["total_payments"]),
            (text("finance_cli.club_payments.total_amount", "Total amount"),
             money(stats["total_amount"])),
            (text("finance_cli.club_payments.clubs_with_payments", "Clubs with payments"),
             stats["clubs_with_payments"]),
        ],
        align=("<", ">"),
    )


def _record_payment(auth) -> None:
    clubs = club_payments.list_clubs()
    if not clubs:
        print(text("finance_cli.club_payments.no_clubs", "No clubs found."))
        return
    labels = [f"{name} (#{cid})" for cid, name in clubs]
    chosen = prompt_choice(text("finance_cli.club_payments.club", "Club"), labels, labels[0])
    club_id, club_name = clubs[labels.index(chosen)]

    amount = prompt_float(text("finance_cli.club_payments.amount", "Amount (£)"))
    if amount is None or amount <= 0:
        print(text("finance_cli.club_payments.invalid_amount", "Amount must be a positive number."))
        return
    payment_type = prompt_choice(text("finance_cli.club_payments.payment_type", "Payment type"),
                                 club_payments.PAYMENT_TYPES, club_payments.PAYMENT_TYPES[0])
    method = prompt_choice(text("finance_cli.club_payments.method", "Payment method"),
                           club_payments.PAYMENT_METHODS, club_payments.PAYMENT_METHODS[0])
    date_str = prompt_date(text("finance_cli.club_payments.date", "Payment date (YYYY-MM-DD)"),
                           datetime.now().strftime("%Y-%m-%d"))
    notes = prompt(text("finance_cli.club_payments.notes", "Notes"))

    payment_id = club_payments.record_club_payment(
        club_id, amount, payment_type, method, date_str, notes, current_username(auth),
    )
    print(text("finance_cli.club_payments.saved",
               "Recorded £{amount:,.2f} for {club} (payment id {id}).",
               amount=amount, club=club_name, id=payment_id))


def _history() -> None:
    limit = prompt_int(text("finance_cli.club_payments.limit", "How many recent payments"), 50,
                       minimum=1)
    rows = club_payments.club_payment_history(limit)
    header(text("finance_cli.club_payments.history_title", "CLUB PAYMENT HISTORY"), 90)
    if not rows:
        print(text("finance_cli.club_payments.no_history", "No club payments recorded yet."))
        return
    print_table(
        ("ID", "Date", "Club", "Amount", "Type", "Method", "Status"),
        [(r["payment_id"], r["payment_date"], r["club"][:30], f"{r['amount']:,.2f} {r['currency']}",
          r["payment_type"], r["payment_method"], r["status"]) for r in rows],
        align=(">", "<", "<", ">", "<", "<", "<"),
    )
    print(text("finance_cli.club_payments.history_count", "{count} payment(s) shown.",
               count=len(rows)))


def run_club_payments_menu(auth) -> None:
    """Run the Club Payments CLI loop (admin and staff)."""
    if not require_finance_access(auth):
        return
    run_menu(
        text("finance_cli.club_payments.title", "CLUB PAYMENT MANAGEMENT"),
        (
            (text("finance_cli.club_payments.opt_overview", "Payment overview"), _overview),
            (text("finance_cli.club_payments.opt_record", "Record a club payment"),
             lambda: _record_payment(auth)),
            (text("finance_cli.club_payments.opt_history", "Payment history"), _history),
        ),
    )


__all__ = ["run_club_payments_menu"]
