"""
Library Finance — interactive CLI.

Command-line twin of the Finance GUI Library Finance manager
(``interfaces/gui/finance/library_finance_manager.py``).  Both call
``domain/reporting/library_finance`` against the shared ``student_records.db``.

Covers: overview metrics; fines (list, search, create, edit, waive, process a
payment); fine revenue (date-range report, CSV export); and book costs (list,
add/update, cost analysis).
"""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from education_system.systems.university.domains.finance.domain.reporting import (
    library_finance as lib,
)
from education_system.systems.university.domains.finance.interfaces.cli.support import (
    header,
    money,
    offer_chart,
    print_table,
    prompt,
    prompt_bool,
    prompt_choice,
    prompt_date,
    prompt_float,
    prompt_int,
    require_finance_access,
    run_menu,
    text,
)

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Overview
# --------------------------------------------------------------------------- #
def _overview() -> None:
    stats = lib.library_overview()
    header(text("finance_cli.library.overview_title", "LIBRARY FINANCE OVERVIEW"))
    labels = [
        text("finance_cli.library.outstanding_fines", "Outstanding fines"),
        text("finance_cli.library.collected_this_month", "Collected this month"),
        text("finance_cli.library.revenue_ytd", "Fine revenue (YTD)"),
        text("finance_cli.library.book_investment", "Book investment"),
    ]
    values = [stats["outstanding_fines"], stats["collected_this_month"],
              stats["revenue_ytd"], stats["book_investment"]]
    print_table(("Metric", "Amount"), list(zip(labels, (money(v) for v in values))),
                align=("<", ">"))
    offer_chart("library_overview.png", "bar", labels, values, "Library Finance Overview",
                "Amount (£)")


# --------------------------------------------------------------------------- #
# Fines
# --------------------------------------------------------------------------- #
def _print_fines(fines: list[dict], title: str) -> None:
    header(title, 100)
    if not fines:
        print(text("finance_cli.library.no_fines", "No outstanding fines."))
        return
    print_table(
        ("Loan", "User", "Name", "Book", "Title", "Days overdue", "Fine", "Status"),
        [(f["loan_id"], f["user_id"], f["name"][:25], f["book_id"], f["title"][:30],
          f["days_overdue"], money(f["fine_amount"]), f["status"]) for f in fines],
        align=(">", "<", "<", ">", "<", ">", ">", "<"),
    )
    print("-" * 100)
    print(text("finance_cli.library.fines_summary",
               "Total outstanding fines: {total} | Items: {count}",
               total=money(sum(f["fine_amount"] for f in fines)), count=len(fines)))


def _list_fines() -> None:
    _print_fines(lib.list_fines(), text("finance_cli.library.fines_title", "OUTSTANDING FINES"))


def _search_fines() -> None:
    term = prompt(text("finance_cli.library.search", "Search by user id or name"))
    _print_fines(lib.list_fines(term),
                 text("finance_cli.library.search_title", "SEARCH RESULTS: {term}", term=term))


def _loan_id() -> int | None:
    loan_id = prompt_int(text("finance_cli.library.loan_id", "Loan ID"))
    if loan_id is None:
        print(text("finance_cli.library.loan_required", "Loan ID is required."))
    return loan_id


def _email_note(result: dict) -> str:
    if result.get("email_sent"):
        return text("finance_cli.library.email_sent", "Email notification sent to {email}.",
                    email=result["email"])
    if result.get("email"):
        return text("finance_cli.library.email_failed", "Note: email notification could not be sent.")
    return text("finance_cli.library.email_missing", "Note: user email not found.")


def _create_fine() -> None:
    loan_id = _loan_id()
    if loan_id is None:
        return
    amount = prompt_float(text("finance_cli.library.fine_amount", "Fine amount (£)"))
    if amount is None or amount <= 0:
        print(text("finance_cli.library.fine_positive", "Fine amount must be greater than 0."))
        return
    notify = prompt_bool(text("finance_cli.library.notify", "Email the borrower?"), True)
    result = lib.create_fine(loan_id, amount, notify=notify)
    print(text("finance_cli.library.fine_created", "Fine of {amount} created for loan {loan}.",
               amount=money(amount), loan=loan_id))
    if notify:
        print(_email_note(result))


def _edit_fine() -> None:
    loan_id = _loan_id()
    if loan_id is None:
        return
    fine = lib.get_fine(loan_id)
    if fine is None:
        print(text("finance_cli.library.loan_not_found", "Loan ID {loan} not found.", loan=loan_id))
        return
    print(text("finance_cli.library.current_fine", "Current fine: {amount}",
               amount=money(fine["fine_amount"])))
    amount = prompt_float(text("finance_cli.library.new_fine", "New fine amount (£)"),
                          fine["fine_amount"])
    if amount is None or amount < 0:
        print(text("finance_cli.library.fine_negative", "Fine amount cannot be negative."))
        return
    lib.update_fine(loan_id, amount)
    print(text("finance_cli.library.fine_updated", "Fine updated to {amount}.", amount=money(amount)))


def _waive_fine() -> None:
    loan_id = _loan_id()
    if loan_id is None:
        return
    fine = lib.get_fine(loan_id)
    if fine is None:
        print(text("finance_cli.library.loan_not_found", "Loan ID {loan} not found.", loan=loan_id))
        return
    if not prompt_bool(text("finance_cli.library.confirm_waive",
                            "Waive the {amount} fine on loan {loan}?",
                            amount=money(fine["fine_amount"]), loan=loan_id)):
        print(text("finance_cli.common.cancelled", "Cancelled."))
        return
    notify = prompt_bool(text("finance_cli.library.notify", "Email the borrower?"), True)
    result = lib.waive_fine(loan_id, notify=notify)
    print(text("finance_cli.library.fine_waived", "Fine waived successfully."))
    if notify:
        print(_email_note(result))


def _process_payment() -> None:
    loan_id = _loan_id()
    if loan_id is None:
        return
    fine = lib.get_fine(loan_id)
    if fine is None:
        print(text("finance_cli.library.loan_not_found", "Loan ID {loan} not found.", loan=loan_id))
        return
    print(text("finance_cli.library.payment_context", "User {user} | Fine: {amount}",
               user=fine["user_id"], amount=money(fine["fine_amount"])))
    amount = prompt_float(text("finance_cli.library.payment_amount", "Payment amount (£)"),
                          fine["fine_amount"])
    method = prompt_choice(text("finance_cli.library.payment_method", "Payment method"),
                           lib.FINE_PAYMENT_METHODS, lib.FINE_PAYMENT_METHODS[0])
    notify = prompt_bool(text("finance_cli.library.send_receipt", "Email a receipt?"), True)
    result = lib.process_fine_payment(loan_id, amount, method, notify=notify)
    print(text("finance_cli.library.payment_done",
               "Payment of {paid} processed (payment id {id}). Remaining fine: {remaining}",
               paid=money(result["paid"]), id=result["payment_id"],
               remaining=money(result["remaining_fine"])))
    if notify:
        print(_email_note(result))


# --------------------------------------------------------------------------- #
# Revenue
# --------------------------------------------------------------------------- #
def _ask_range() -> tuple[str, str]:
    today = datetime.now()
    start = prompt_date(text("finance_cli.library.start_date", "Start date (YYYY-MM-DD)"),
                        (today - timedelta(days=365)).strftime("%Y-%m-%d"))
    end = prompt_date(text("finance_cli.library.end_date", "End date (YYYY-MM-DD)"),
                      today.strftime("%Y-%m-%d"))
    return start, end


def _revenue_report() -> None:
    start, end = _ask_range()
    report = lib.revenue_report(start, end)
    print(lib.revenue_report_text(report))
    monthly = list(reversed(report["monthly"]))
    offer_chart("library_revenue.png", "bar", [m for m, _, _ in monthly],
                [rev for _, _, rev in monthly], "Library Fine Revenue by Month", "Revenue (£)")


def _export_revenue() -> None:
    start, end = _ask_range()
    filename = prompt(text("finance_cli.library.csv_filename", "CSV filename"),
                      f"library_revenue_{datetime.now():%Y%m%d}.csv")
    count = lib.export_revenue_csv(filename, start, end)
    print(text("finance_cli.library.export_done", "{count} row(s) exported to {filename}",
               count=count, filename=filename))


# --------------------------------------------------------------------------- #
# Book costs
# --------------------------------------------------------------------------- #
def _list_book_costs() -> None:
    books = lib.list_book_costs()
    header(text("finance_cli.library.costs_title", "BOOK COSTS"), 110)
    if not books:
        print(text("finance_cli.library.no_books", "No books found."))
        return
    print_table(
        ("ID", "Title", "Author", "ISBN", "Price", "Purchased", "Supplier", "Qty"),
        [(b["book_id"], b["title"][:35], b["author"][:20], b["isbn"], money(b["purchase_price"]),
          b["purchase_date"], b["supplier"][:18], b["quantity"]) for b in books],
        align=(">", "<", "<", "<", ">", "<", "<", ">"),
    )
    total_cost = sum(b["purchase_price"] * b["quantity"] for b in books)
    print("-" * 110)
    print(text("finance_cli.library.costs_summary",
               "Total book investment: {total} | Total books: {count}",
               total=money(total_cost), count=sum(b["quantity"] for b in books)))


def _set_book_cost() -> None:
    book_id = prompt(text("finance_cli.library.book_id", "Book ID"))
    if not book_id:
        print(text("finance_cli.library.book_required", "Book ID is required."))
        return
    price = prompt_float(text("finance_cli.library.purchase_price", "Purchase price (£)"))
    if price is None or price < 0:
        print(text("finance_cli.library.price_positive", "Price must be zero or more."))
        return
    date_str = prompt_date(text("finance_cli.library.purchase_date", "Purchase date (YYYY-MM-DD)"),
                           datetime.now().strftime("%Y-%m-%d"))
    supplier = prompt(text("finance_cli.library.supplier", "Supplier"))
    quantity = prompt_int(text("finance_cli.library.quantity", "Quantity"), 1, minimum=1)
    lib.set_book_cost(book_id, price, date_str, supplier, quantity)
    print(text("finance_cli.library.cost_saved", "Book cost information saved."))


def _cost_analysis() -> None:
    print(lib.cost_analysis_text())


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def run_library_finance_menu(auth) -> None:
    """Run the Library Finance CLI loop (admin and staff)."""
    if not require_finance_access(auth):
        return
    run_menu(
        text("finance_cli.library.title", "LIBRARY FINANCE"),
        (
            (text("finance_cli.library.opt_overview", "Overview metrics"), _overview),
            (text("finance_cli.library.opt_fines", "List outstanding fines"), _list_fines),
            (text("finance_cli.library.opt_search", "Search fines by user"), _search_fines),
            (text("finance_cli.library.opt_create", "Create fine"), _create_fine),
            (text("finance_cli.library.opt_edit", "Edit fine"), _edit_fine),
            (text("finance_cli.library.opt_waive", "Waive (delete) fine"), _waive_fine),
            (text("finance_cli.library.opt_pay", "Process fine payment"), _process_payment),
            (text("finance_cli.library.opt_revenue", "Fine revenue report"), _revenue_report),
            (text("finance_cli.library.opt_export", "Export fine revenue to CSV"), _export_revenue),
            (text("finance_cli.library.opt_costs", "List book costs"), _list_book_costs),
            (text("finance_cli.library.opt_set_cost", "Add / update book cost"), _set_book_cost),
            (text("finance_cli.library.opt_analysis", "Book cost analysis"), _cost_analysis),
        ),
    )


__all__ = ["run_library_finance_menu"]
