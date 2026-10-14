"""
Finance Administration — interactive CLI (admin only).

Command-line twin of the Finance GUI Admin tab
(``interfaces/gui/finance/layout/_admin.py``).  Both call
``domain/core/finance_admin`` against the shared ``student_records.db``.

Covers: system status, database statistics, database backup, cleanup of
old data (destructive — confirmed by typing YES), and fee-type / aid-type
creation and listing.
"""

from __future__ import annotations

import logging

from education_system.systems.university.domains.finance.domain.core import finance_admin
from education_system.systems.university.domains.finance.interfaces.cli.support import (
    confirm_destructive,
    header,
    money,
    print_table,
    prompt,
    prompt_bool,
    prompt_choice,
    prompt_float,
    prompt_int,
    require_finance_access,
    run_menu,
    text,
)

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# System
# --------------------------------------------------------------------------- #
def _system_status() -> None:
    print()
    print(finance_admin.system_status_text())


def _database_statistics() -> None:
    header(text("finance_cli.admin.stats_title", "DATABASE STATISTICS"))
    rows = []
    for table, count in finance_admin.database_statistics():
        rows.append((table, count if count is not None
                     else text("finance_cli.admin.table_missing", "Table not found")))
    print_table(("Table", "Records"), rows, align=("<", ">"))


def _backup_database() -> None:
    target = finance_admin.backup_database()
    print(text("finance_cli.admin.backup_success", "Database backed up to: {path}", path=target))


def _cleanup_old_data() -> None:
    years = prompt_int(text("finance_cli.admin.retention", "Delete records older than (years)"),
                       finance_admin.CLEANUP_RETENTION_YEARS, minimum=1)
    print(text("finance_cli.admin.cleanup_warning",
               "This permanently deletes payments and late fees older than {years} years.",
               years=years))
    if not confirm_destructive(text("finance_cli.admin.cleanup_confirm", "Proceed?")):
        print(text("finance_cli.common.cancelled", "Cancelled."))
        return
    deleted = finance_admin.cleanup_old_data(years)
    print(text("finance_cli.admin.cleanup_done",
               "Deleted {payments} payment(s) and {late_fees} late fee(s).",
               payments=deleted["payments"], late_fees=deleted["late_fees"]))


# --------------------------------------------------------------------------- #
# Fee types
# --------------------------------------------------------------------------- #
def _create_fee_type() -> None:
    name = prompt(text("finance_cli.admin.fee_name", "Fee name"))
    if not name:
        print(text("finance_cli.admin.fee_name_required", "Fee name is required."))
        return
    description = prompt(text("finance_cli.admin.description", "Description"))
    year = prompt(text("finance_cli.admin.academic_year", "Academic year"), "2024-2025")
    recurring = prompt_bool(text("finance_cli.admin.is_recurring", "Is this fee recurring?"))
    fee_type_id = finance_admin.create_fee_type(name, description, year, recurring)
    print(text("finance_cli.admin.fee_type_created", "Fee type created (id {id}).", id=fee_type_id))


def _view_fee_types() -> None:
    header(text("finance_cli.admin.fee_types_title", "FEE TYPES"), 80)
    fee_types = finance_admin.list_fee_types()
    if not fee_types:
        print(text("finance_cli.admin.no_fee_types", "No fee types found."))
        return
    yes, no = text("common.yes", "Yes"), text("common.no", "No")
    print_table(
        ("ID", "Name", "Description", "Year", "Recurring"),
        [(f["fee_type_id"], f["fee_name"], (f["description"] or "")[:40], f["academic_year"] or "",
          yes if f["is_recurring"] else no) for f in fee_types],
        align=(">", "<", "<", "<", "<"),
    )


# --------------------------------------------------------------------------- #
# Aid types
# --------------------------------------------------------------------------- #
def _create_aid_type() -> None:
    name = prompt(text("finance_cli.admin.aid_name", "Aid type name"))
    if not name:
        print(text("finance_cli.admin.aid_name_required", "Aid type name is required."))
        return
    description = prompt(text("finance_cli.admin.description", "Description"))
    max_amount = prompt_float(text("finance_cli.admin.max_amount", "Maximum amount (£)"), 0.0)
    category = prompt_choice(text("finance_cli.admin.category", "Category"),
                             finance_admin.AID_CATEGORIES, "grant")
    aid_type_id = finance_admin.create_aid_type(name, description, max_amount, category)
    print(text("finance_cli.admin.aid_type_created", "Aid type created (id {id}).", id=aid_type_id))


def _view_aid_types() -> None:
    header(text("finance_cli.admin.aid_types_title", "FINANCIAL AID TYPES"), 90)
    aid_types = finance_admin.list_aid_types()
    if not aid_types:
        print(text("finance_cli.admin.no_aid_types", "No financial aid types found."))
        return
    yes, no = text("common.yes", "Yes"), text("common.no", "No")
    print_table(
        ("ID", "Name", "Description", "Max amount", "Category", "Active"),
        [(a["aid_type_id"], a["aid_name"], (a["description"] or "")[:35], money(a["max_amount"]),
          a["aid_category"] or "", yes if a["is_active"] else no) for a in aid_types],
        align=(">", "<", "<", ">", "<", "<"),
    )


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def run_finance_admin_menu(auth) -> None:
    """Run the Finance Administration CLI loop (admin only, like the GUI tab)."""
    if not require_finance_access(auth, admin_only=True):
        return
    run_menu(
        text("finance_cli.admin.title", "FINANCE ADMINISTRATION"),
        (
            (text("finance_cli.admin.opt_status", "System status"), _system_status),
            (text("finance_cli.admin.opt_stats", "Database statistics"), _database_statistics),
            (text("finance_cli.admin.opt_backup", "Backup database"), _backup_database),
            (text("finance_cli.admin.opt_cleanup", "Cleanup old data"), _cleanup_old_data),
            (text("finance_cli.admin.opt_create_fee", "Create fee type"), _create_fee_type),
            (text("finance_cli.admin.opt_view_fees", "View fee types"), _view_fee_types),
            (text("finance_cli.admin.opt_create_aid", "Create aid type"), _create_aid_type),
            (text("finance_cli.admin.opt_view_aid", "View aid types"), _view_aid_types),
        ),
    )


__all__ = ["run_finance_admin_menu"]
