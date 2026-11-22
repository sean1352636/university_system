"""CLI for department budget lines and budget-vs-spend.
Entries are added to ``departments_cli._MENU``."""

from __future__ import annotations

from education_system.systems.sixth_form.domains.finance.domain import (
    finance_calendar as fc,
)
from education_system.systems.sixth_form.domain.staff.departments import (
    department_budgets as db,
)
from education_system.systems.sixth_form.domains.finance.interfaces.cli import (
    _prompts as ui,
)


def _who() -> str:
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return access.current().username or ui.ask("Your name", required=True)


def _pick_department() -> tuple[int, str]:
    depts = db.list_departments()
    if not depts:
        print("    No departments.")
        raise ui.Abort
    name = ui.pick("Department", [n for _i, n in depts])
    return next((i, n) for i, n in depts if n == name)


def _year() -> str:
    return fc.normalise_year(ui.ask("Academic year",
                                    default=fc.normalise_year(None)))


def _print_lines(rows: list[db.BudgetLine]) -> None:
    ui.table(("#", "Year", "Category", "Amount", "Description", "By"),
             [(l.line_id, l.academic_year, l.category, ui.money(l.amount),
               l.description or "", l.created_by or "") for l in rows],
             empty="(no budget lines)")


@ui.handler
def budget_lines() -> None:
    did, name = _pick_department()
    year = _year()
    _print_lines(db.list_lines(department_id=did, academic_year=year))
    action = ui.pick("Action", ["Add line", "Edit line", "Delete line",
                                "Copy lines from another year", "Nothing"])
    if action == "Add line":
        db.add_line(did, academic_year=year,
                    category=ui.pick("Category", list(db.BUDGET_CATEGORIES)),
                    amount=ui.ask_money("Amount"),
                    description=ui.ask("Description") or None,
                    created_by=_who())
        print("\n  ✓ Line added.")
    elif action == "Edit line":
        lid = ui.ask_int("Line #")
        cur = next((l for l in db.list_lines(department_id=did)
                    if l.line_id == lid), None)
        if cur is None:
            raise db.ValidationError(f"No line #{lid} for {name}")
        db.update_line(lid, amount=ui.ask_money("Amount", default=cur.amount),
                       category=ui.pick("Category",
                                        list(db.BUDGET_CATEGORIES),
                                        default=cur.category),
                       description=ui.ask("Description",
                                          default=cur.description or "")
                       or None)
        print("\n  ✓ Updated.")
    elif action == "Delete line":
        if db.delete_line(ui.ask_int("Line #")):
            print("\n  ✓ Deleted.")
    elif action.startswith("Copy"):
        src = fc.normalise_year(ui.ask("Copy from year", required=True))
        uplift = float(ui.ask("Uplift %", default="0"))
        made = db.copy_year(did, from_year=src, to_year=year,
                            uplift_pct=uplift, created_by=_who())
        print(f"\n  ✓ {len(made)} line(s) copied into {year}.")


@ui.handler
def budget_report() -> None:
    did, _name = _pick_department()
    rep = db.budget_report(did, _year())
    print(f"\n  {rep.department_name} — {rep.academic_year}")
    ui.table(("Category", "Budget", "Spend", "Income", "Net", "Remaining",
              "Used"),
             [(l.category, ui.money(l.budget), ui.money(l.spend),
               ui.money(l.income), ui.money(l.net), ui.money(l.remaining),
               "—" if l.utilisation_pct is None
               else f"{l.utilisation_pct:.0f}%{' !' if l.over else ''}")
              for l in rep.lines])
    used = ("—" if rep.utilisation_pct is None
            else f"{rep.utilisation_pct:.1f}%")
    print(f"\n  Budget {ui.money(rep.total_budget)} · net spend "
          f"{ui.money(rep.net_spend)} · remaining {ui.money(rep.remaining)}"
          f" · {used}")
    for w in rep.warnings:
        print(f"  ! {w}")
    for u in rep.uncosted_trips:
        print(f"  ? Trip without a running cost: {u}")
    if rep.items and ui.yes_no("Show the spend items?", default=False):
        ui.table(("Source", "Ref", "Date", "Category", "Description",
                  "Amount"),
                 [(i.source, i.ref, i.date or "", i.category,
                   i.description[:36], ui.money(i.amount))
                  for i in rep.items])


@ui.handler
def all_departments() -> None:
    year = _year()
    rows = db.all_departments(year)
    ui.table(("Department", "Budget", "Net spend", "Remaining", "Used",
              "Warnings"),
             [(r.name, ui.money(r.budget), ui.money(r.net_spend),
               ui.money(r.remaining),
               "—" if r.utilisation_pct is None
               else f"{r.utilisation_pct:.0f}%"
               + (" OVER" if r.overspent else ""), r.warnings)
              for r in rows], empty="(no budgets or spend for that year)")
    for w in db.overspend_warnings(year):
        print(f"  ! {w}")


@ui.handler
def sync_totals() -> None:
    year = _year()
    if ui.yes_no(f"Copy {year} line totals and net spend into each "
                 "department's budget figures?", default=True):
        print(f"\n  ✓ {db.sync_department_totals(year)} department(s) "
              "updated.")


@ui.handler
def attribute_receipt() -> None:
    lid = ui.ask_int("Receipt line #")
    did, name = _pick_department()
    db.attribute_receipt_line(lid, did)
    print(f"\n  ✓ Receipt line #{lid} filed against {name}.")


MENU = [
    ("── Budgets ──", lambda: None),
    ("Budget lines", budget_lines),
    ("Budget vs spend", budget_report),
    ("All departments (overspend)", all_departments),
    ("Sync budget totals", sync_totals),
    ("File receipt income to department", attribute_receipt),
]
