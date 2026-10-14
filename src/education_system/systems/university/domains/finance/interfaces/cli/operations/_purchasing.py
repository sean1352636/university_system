"""Purchase-to-pay sub-menus: suppliers, purchase orders, accounts payable.

Same ``FinanceOperationsService`` calls as the Finance GUI's operations tabs
(``interfaces/gui/finance/layout/_operations.py``), so both views share data.
"""

from __future__ import annotations

from education_system.systems.university.domains.finance.domain.operations_service import (
    PURCHASE_ORDER_STATUSES,
)
from education_system.systems.university.domains.finance.interfaces.cli.operations._shared import (
    OpsContext,
    ok,
    print_record,
    print_table,
    prompt_choice,
    prompt_float,
    prompt_int,
    prompt_text,
    run_menu,
    t,
)

SUPPLIER_COLUMNS = ("id", "name", "email", "bank_verified", "risk_rating", "status")
PO_COLUMNS = ("id", "po_number", "supplier_id", "description", "net_amount", "status")
INVOICE_COLUMNS = (
    "id",
    "invoice_number",
    "supplier_id",
    "net_amount",
    "vat_amount",
    "due_date",
    "status",
)
RISK_RATINGS = ("low", "medium", "high")
SUPPLIER_STATUSES = ("active", "on_hold", "inactive")
PO_STATUS_CHOICES = tuple(
    s for s in ("submitted", "approved", "ordered", "received", "closed", "cancelled")
    if s in PURCHASE_ORDER_STATUSES
)


# --------------------------------------------------------------------------- #
# Suppliers
# --------------------------------------------------------------------------- #
def _list_suppliers(ctx: OpsContext) -> None:
    print_table(
        ctx.service.list_suppliers(),
        SUPPLIER_COLUMNS,
        t("suppliers.none", default="No suppliers yet."),
    )


def _add_supplier(ctx: OpsContext) -> None:
    name = prompt_text(t("suppliers.name", default="Name"), required=True)
    email = prompt_text(t("suppliers.email", default="Email"))
    risk = prompt_choice(t("suppliers.risk", default="Risk rating"), RISK_RATINGS, default="low")
    new_id = ctx.service.add_supplier(name, email, risk)
    ok(t("suppliers.added", default="Supplier {id} added.", id=new_id))


def _find_supplier(ctx: OpsContext, supplier_id: int) -> dict | None:
    return next((s for s in ctx.service.list_suppliers() if s["id"] == supplier_id), None)


def _verify_supplier_bank(ctx: OpsContext) -> None:
    supplier_id = prompt_int(t("suppliers.id", default="Supplier ID"))
    if not _find_supplier(ctx, supplier_id):
        raise ValueError(t("suppliers.not_found", default="Supplier not found"))
    ctx.service.update_supplier_controls(supplier_id, bank_verified=True)
    ok(t("suppliers.verified", default="Bank details verified for supplier {id}.", id=supplier_id))


def _update_supplier_controls(ctx: OpsContext) -> None:
    supplier_id = prompt_int(t("suppliers.id", default="Supplier ID"))
    current = _find_supplier(ctx, supplier_id)
    if not current:
        raise ValueError(t("suppliers.not_found", default="Supplier not found"))
    print_record(current, t("suppliers.title_one", default="Supplier"), "")
    status = prompt_choice(
        t("suppliers.status", default="Status"), SUPPLIER_STATUSES, default=current["status"]
    )
    risk = prompt_choice(
        t("suppliers.risk", default="Risk rating"), RISK_RATINGS, default=current["risk_rating"]
    )
    ctx.service.update_supplier_controls(supplier_id, status=status, risk=risk)
    ok(t("suppliers.updated", default="Supplier {id} updated.", id=supplier_id))


def suppliers_menu(ctx: OpsContext) -> None:
    run_menu(
        t("suppliers.title", default="SUPPLIER MANAGEMENT"),
        [
            (t("suppliers.list", default="List suppliers"), lambda: _list_suppliers(ctx)),
            (t("suppliers.add", default="Add supplier"), lambda: _add_supplier(ctx)),
            (
                t("suppliers.verify", default="Verify bank details"),
                lambda: _verify_supplier_bank(ctx),
            ),
            (
                t("suppliers.controls", default="Update status / risk rating"),
                lambda: _update_supplier_controls(ctx),
            ),
        ],
    )


# --------------------------------------------------------------------------- #
# Purchase orders
# --------------------------------------------------------------------------- #
def _list_pos(ctx: OpsContext) -> None:
    print_table(
        ctx.service.rows("finance_purchase_orders"),
        PO_COLUMNS,
        t("po.none", default="No purchase orders yet."),
    )


def _view_po(ctx: OpsContext) -> None:
    po_id = prompt_int(t("po.id", default="Purchase order ID"))
    print_record(
        ctx.service.row("finance_purchase_orders", po_id),
        t("po.title_one", default="Purchase order {id}", id=po_id),
        t("po.not_found", default="Purchase order not found."),
    )


def _create_po(ctx: OpsContext) -> None:
    supplier_id = prompt_int(t("suppliers.id", default="Supplier ID"))
    description = prompt_text(t("po.description", default="Description"), required=True)
    amount = prompt_float(t("net_amount", default="Net amount"))
    new_id = ctx.service.create_po(supplier_id, description, amount)
    number = (ctx.service.row("finance_purchase_orders", new_id) or {}).get("po_number", new_id)
    ok(t("po.created", default="Purchase order {number} created (id {id}).", number=number, id=new_id))


def _advance_po(ctx: OpsContext) -> None:
    po_id = prompt_int(t("po.id", default="Purchase order ID"))
    if not ctx.service.row("finance_purchase_orders", po_id):
        raise ValueError(t("po.not_found", default="Purchase order not found."))
    status = prompt_choice(t("po.new_status", default="New status"), PO_STATUS_CHOICES)
    ctx.service.advance_po(po_id, status)
    ok(t("po.advanced", default="Purchase order {id} is now '{status}'.", id=po_id, status=status))


def purchase_orders_menu(ctx: OpsContext) -> None:
    run_menu(
        t("po.title", default="PURCHASE ORDERS"),
        [
            (t("po.list", default="List purchase orders"), lambda: _list_pos(ctx)),
            (t("po.view", default="View purchase order"), lambda: _view_po(ctx)),
            (t("po.create", default="Create purchase order"), lambda: _create_po(ctx)),
            (t("po.advance", default="Advance status"), lambda: _advance_po(ctx)),
        ],
    )


# --------------------------------------------------------------------------- #
# Accounts payable
# --------------------------------------------------------------------------- #
def _list_invoices(ctx: OpsContext) -> None:
    print_table(
        ctx.service.rows("finance_ap_invoices"),
        INVOICE_COLUMNS,
        t("ap.none", default="No supplier invoices yet."),
    )


def _view_invoice(ctx: OpsContext) -> None:
    invoice_id = prompt_int(t("ap.id", default="Invoice ID"))
    print_record(
        ctx.service.row("finance_ap_invoices", invoice_id),
        t("ap.title_one", default="Invoice {id}", id=invoice_id),
        t("ap.not_found", default="Invoice not found."),
    )


def _add_invoice(ctx: OpsContext) -> None:
    supplier_id = prompt_int(t("suppliers.id", default="Supplier ID"))
    number = prompt_text(t("ap.number", default="Invoice number"), required=True)
    net = prompt_float(t("net_amount", default="Net amount"))
    vat = prompt_float(t("vat_amount", default="VAT amount"), default=0.0)
    due_date = prompt_text(t("ap.due_date", default="Due date (YYYY-MM-DD, blank = none)"))
    po_id = prompt_int(
        t("ap.po_id", default="Purchase order ID for three-way match (blank = none)"),
        required=False,
    )
    new_id = ctx.service.add_invoice(
        supplier_id, number, net, vat=vat, due_date=due_date or None, po_id=po_id
    )
    ok(t("ap.added", default="Invoice {number} recorded (id {id}).", number=number, id=new_id))


def _approve_invoice(ctx: OpsContext) -> None:
    invoice_id = prompt_int(t("ap.id", default="Invoice ID"))
    ctx.service.approve_invoice(invoice_id)
    ok(t("ap.approved", default="Invoice {id} approved.", id=invoice_id))


def accounts_payable_menu(ctx: OpsContext) -> None:
    run_menu(
        t("ap.title", default="ACCOUNTS PAYABLE"),
        [
            (t("ap.list", default="List invoices"), lambda: _list_invoices(ctx)),
            (t("ap.view", default="View invoice"), lambda: _view_invoice(ctx)),
            (t("ap.add", default="Add invoice"), lambda: _add_invoice(ctx)),
            (t("ap.approve", default="Approve invoice"), lambda: _approve_invoice(ctx)),
        ],
    )
