"""Treasury sub-menus: cash flow, tax & VAT, fixed assets.

Same ``FinanceOperationsService`` calls as the Finance GUI's operations tabs
(``interfaces/gui/finance/layout/_operations.py``), so both views share data.
"""

from __future__ import annotations

from datetime import date

from education_system.systems.university.domains.finance.interfaces.cli.operations._shared import (
    OpsContext,
    money,
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

CASH_COLUMNS = ("id", "movement_date", "kind", "category", "amount", "status", "description")
VAT_COLUMNS = ("id", "tax_date", "source_type", "tax_code", "net_amount", "vat_amount", "direction")
ASSET_COLUMNS = (
    "id",
    "asset_tag",
    "description",
    "cost",
    "acquired_date",
    "useful_life_years",
    "residual_value",
    "location",
    "status",
)
CASH_KINDS = ("inflow", "outflow")
CASH_STATUSES = ("forecast", "actual")
VAT_DIRECTIONS = ("input", "output")


def _iso_date(label: str, default: str) -> str:
    """Prompt for a YYYY-MM-DD date, re-asking until it parses."""
    while True:
        raw = prompt_text(label, default=default)
        try:
            return date.fromisoformat(raw).isoformat()
        except ValueError:
            print(t("bad_date", default="Please enter a date as YYYY-MM-DD."))


# --------------------------------------------------------------------------- #
# Cash flow
# --------------------------------------------------------------------------- #
def _cash_position(ctx: OpsContext) -> None:
    s = ctx.service.cash_summary()
    print("\n" + t("cash.position_title", default="Cash position"))
    print(f"  {t('cash.balance', default='Position'):<22}: {money(s['balance'])}")
    print(f"  {t('cash.expected_in', default='Expected receipts'):<22}: {money(s['expected_in'])}")
    print(f"  {t('cash.expected_out', default='Scheduled payments'):<22}: {money(s['expected_out'])}")


def _list_cash(ctx: OpsContext) -> None:
    print_table(
        ctx.service.rows("finance_cash_movements"),
        CASH_COLUMNS,
        t("cash.none", default="No cash movements yet."),
    )


def _record_cash(ctx: OpsContext) -> None:
    kind = prompt_choice(t("cash.kind", default="Type"), CASH_KINDS)
    category = prompt_text(t("cash.category", default="Category"))
    amount = prompt_float(t("amount", default="Amount"))
    movement_date = _iso_date(t("cash.date", default="Movement date"), date.today().isoformat())
    status = prompt_choice(t("status", default="Status"), CASH_STATUSES, default="forecast")
    description = prompt_text(t("description", default="Description"))
    new_id = ctx.service.record_cash(
        kind, category, amount, movement_date=movement_date, status=status, description=description
    )
    ok(t("cash.recorded", default="Cash movement {id} recorded.", id=new_id))
    _cash_position(ctx)


def cash_flow_menu(ctx: OpsContext) -> None:
    run_menu(
        t("cash.title", default="CASH FLOW CONTROL CENTRE"),
        [
            (t("cash.refresh", default="Show cash position"), lambda: _cash_position(ctx)),
            (t("cash.list", default="List cash movements"), lambda: _list_cash(ctx)),
            (t("cash.record", default="Record cash movement"), lambda: _record_cash(ctx)),
        ],
    )


# --------------------------------------------------------------------------- #
# Tax & VAT
# --------------------------------------------------------------------------- #
def _vat_position(ctx: OpsContext) -> None:
    s = ctx.service.vat_summary()
    print("\n" + t("vat.position_title", default="VAT position"))
    print(f"  {t('vat.output', default='Output VAT'):<22}: {money(s['output_vat'])}")
    print(f"  {t('vat.input', default='Input VAT'):<22}: {money(s['input_vat'])}")
    print(f"  {t('vat.net_payable', default='Net payable'):<22}: {money(s['net_payable'])}")


def _list_vat(ctx: OpsContext) -> None:
    print_table(
        ctx.service.rows("finance_vat_entries"),
        VAT_COLUMNS,
        t("vat.none", default="No VAT entries yet."),
    )


def _record_vat(ctx: OpsContext) -> None:
    code = prompt_text(t("vat.code", default="Tax code"), required=True)
    net = prompt_float(t("net_amount", default="Net amount"))
    vat = prompt_float(t("vat_amount", default="VAT amount"))
    direction = prompt_choice(t("vat.direction", default="Direction"), VAT_DIRECTIONS)
    tax_date = _iso_date(t("vat.date", default="Tax date"), date.today().isoformat())
    new_id = ctx.service.record_vat("manual", None, code, net, vat, direction, tax_date=tax_date)
    ok(t("vat.recorded", default="VAT entry {id} recorded.", id=new_id))
    _vat_position(ctx)


def tax_vat_menu(ctx: OpsContext) -> None:
    run_menu(
        t("vat.title", default="TAX & VAT MANAGEMENT"),
        [
            (t("vat.refresh", default="Show VAT position"), lambda: _vat_position(ctx)),
            (t("vat.list", default="List VAT entries"), lambda: _list_vat(ctx)),
            (t("vat.record", default="Record VAT entry"), lambda: _record_vat(ctx)),
        ],
    )


# --------------------------------------------------------------------------- #
# Fixed assets
# --------------------------------------------------------------------------- #
def _list_assets(ctx: OpsContext) -> None:
    print_table(
        ctx.service.rows("finance_fixed_assets"),
        ASSET_COLUMNS,
        t("assets.none", default="No fixed assets yet."),
    )


def _view_asset(ctx: OpsContext) -> None:
    asset_id = prompt_int(t("assets.id", default="Asset ID"))
    record = ctx.service.row("finance_fixed_assets", asset_id)
    print_record(
        record,
        t("assets.title_one", default="Asset {id}", id=asset_id),
        t("assets.not_found", default="Asset not found."),
    )
    if record:
        book_value = ctx.service.asset_book_value(asset_id)
        print(f"  {t('assets.book_value', default='Book value today'):<20}: {money(book_value)}")


def _add_asset(ctx: OpsContext) -> None:
    tag = prompt_text(t("assets.tag", default="Asset tag"), required=True)
    description = prompt_text(t("description", default="Description"), required=True)
    cost = prompt_float(t("assets.cost", default="Cost"))
    life = prompt_int(t("assets.life", default="Useful life (years)"))
    acquired = _iso_date(t("assets.acquired", default="Acquired date"), date.today().isoformat())
    residual = prompt_float(t("assets.residual", default="Residual value"), default=0.0)
    location = prompt_text(t("assets.location", default="Location"))
    new_id = ctx.service.add_asset(
        tag, description, cost, life, acquired=acquired, residual=residual, location=location
    )
    ok(t("assets.added", default="Asset {tag} registered (id {id}).", tag=tag, id=new_id))


def fixed_assets_menu(ctx: OpsContext) -> None:
    run_menu(
        t("assets.title", default="FIXED ASSET REGISTER"),
        [
            (t("assets.list", default="List assets"), lambda: _list_assets(ctx)),
            (t("assets.view", default="View asset (with book value)"), lambda: _view_asset(ctx)),
            (t("assets.add", default="Add asset"), lambda: _add_asset(ctx)),
        ],
    )
