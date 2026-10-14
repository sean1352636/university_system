"""
Finance Operations — interactive CLI.

CLI twin of the Finance GUI's operations block
(``finance/interfaces/gui/finance/layout/_operations.py``). Every sub-menu
calls the same ``FinanceOperationsService`` methods as the matching GUI tab,
against the same shared university database, so work done here is visible in
the GUI and vice-versa.

Sub-menus: accounts payable, purchase orders, suppliers, cash flow, tax & VAT,
fixed assets, approval inbox, fraud investigations, month-end close checklist.
"""

from __future__ import annotations

import logging

from education_system.systems.university.domains.finance.interfaces.cli.operations._controls import (
    approval_inbox_menu,
    close_checklist_menu,
    fraud_investigations_menu,
)
from education_system.systems.university.domains.finance.interfaces.cli.operations._purchasing import (
    accounts_payable_menu,
    purchase_orders_menu,
    suppliers_menu,
)
from education_system.systems.university.domains.finance.interfaces.cli.operations._shared import (
    OpsContext,
    current_username,
    fail,
    run_menu,
    t,
)
from education_system.systems.university.domains.finance.interfaces.cli.operations._treasury import (
    cash_flow_menu,
    fixed_assets_menu,
    tax_vat_menu,
)

logger = logging.getLogger(__name__)

REQUIRED_PERMISSION = "manage_finances"


def _permitted(auth) -> bool:
    """Same gate the finance menu applies: ``auth.check_permission('manage_finances')``."""
    check = getattr(auth, "check_permission", None)
    if check is None:
        return False
    try:
        return bool(check(REQUIRED_PERMISSION))
    except Exception:
        logger.debug("Permission check failed", exc_info=True)
        return False


def _build_context(auth) -> OpsContext:
    # Imported here so the schema initialisation in the service constructor
    # only touches the database when the menu actually opens.
    from education_system.systems.university.domains.finance.domain.operations_service import (
        FinanceOperationsService,
    )

    return OpsContext(service=FinanceOperationsService(), username=current_username(auth))


def run_operations_menu(auth) -> None:
    """Run the Finance Operations CLI loop (one sub-menu per GUI operations tab)."""
    if not _permitted(auth):
        fail(t("permission_denied", default="You do not have permission to manage finances."))
        return
    ctx = _build_context(auth)
    run_menu(
        t("title", default="FINANCE OPERATIONS"),
        [
            (t("ap.title_menu", default="Accounts payable"), lambda: accounts_payable_menu(ctx)),
            (t("po.title_menu", default="Purchase orders"), lambda: purchase_orders_menu(ctx)),
            (t("suppliers.title_menu", default="Suppliers"), lambda: suppliers_menu(ctx)),
            (t("cash.title_menu", default="Cash flow control centre"), lambda: cash_flow_menu(ctx)),
            (t("vat.title_menu", default="Tax & VAT management"), lambda: tax_vat_menu(ctx)),
            (t("assets.title_menu", default="Fixed asset register"), lambda: fixed_assets_menu(ctx)),
            (t("approvals.title_menu", default="Approval inbox"), lambda: approval_inbox_menu(ctx)),
            (
                t("fraud.title_menu", default="Fraud investigations"),
                lambda: fraud_investigations_menu(ctx),
            ),
            (
                t("close.title_menu", default="Month-end close checklist"),
                lambda: close_checklist_menu(ctx),
            ),
        ],
        pause_after=False,
    )
