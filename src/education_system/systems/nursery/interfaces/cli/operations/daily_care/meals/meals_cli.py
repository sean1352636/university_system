"""CLI flow for Meals & Menus (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.nursery.domain.operations.daily_care.meals import meals as data
from education_system.systems.nursery.domain.operations.daily_care.meals.meals import (
    AMOUNTS,
    MEAL_TYPES,
    ValidationError,
)

logger = logging.getLogger(__name__)


def _prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _safe(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            print(f"  Validation error: {e}")
        except Exception as e:  # noqa: BLE001
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _pick(label: str, options: tuple[str, ...], default: str | None = None) -> str:
    print(f"  {label}:")
    for i, opt in enumerate(options, 1):
        print(f"    {i}) {opt}")
    suffix = f" [{default}]" if default else ""
    raw = _prompt(f"  Select 1-{len(options)}{suffix}: ")
    if not raw:
        return default or ""
    if raw.isdigit() and 1 <= int(raw) <= len(options):
        return options[int(raw) - 1]
    return raw


def _pick_id(label: str, choices: list[tuple[str, str]],
             current: str | None = None) -> str | None:
    if not choices:
        return current
    print(f"  {label}:")
    for i, (_cid, text) in enumerate(choices, 1):
        print(f"    {i}) {text}")
    cur_label = f" [{current}]" if current else " (Enter to skip)"
    raw = _prompt(f"  Select 1-{len(choices)}{cur_label}: ")
    if not raw:
        return current
    if raw.isdigit() and 1 <= int(raw) <= len(choices):
        return choices[int(raw) - 1][0]
    return raw


def _print_table(rows: list[data.MealRecord]) -> None:
    if not rows:
        print("  (no meal records)")
        return
    print(f"  {'ID':<8} {'Date':<12} {'Child':<22} {'Meal':<16} "
          f"{'Eaten':<7} {'Safe'}")
    print(f"  {'-'*8} {'-'*12} {'-'*22} {'-'*16} {'-'*7} {'-'*4}")
    for r in rows:
        safe = "yes" if r.allergy_safe else "NO"
        print(f"  {r.meal_id:<8} {r.meal_date:<12} {(r.child_name or '-')[:22]:<22} "
              f"{r.meal_type[:16]:<16} {(r.amount_eaten or '-'):<7} {safe}")


def _print_detail(r: data.MealRecord) -> None:
    print(f"\n  ── Meal {r.meal_id} ──")
    print(f"  Child:         {r.child_name or '-'} ({r.pupil_id})")
    print(f"  Date:          {r.meal_date}")
    print(f"  Meal:          {r.meal_type}")
    print(f"  Menu:          {r.menu or '-'}")
    print(f"  Amount eaten:  {r.amount_eaten or '-'}")
    print(f"  Drink:         {r.drink or '-'}")
    print(f"  Allergy safe:  {'Yes' if r.allergy_safe else 'NO'}")
    print(f"  Recorded by:   {r.staff_name or '-'}")
    print(f"  Notes:         {r.notes or '-'}")


def _collect_fields(existing: data.MealRecord | None = None,
                    *, pupil_id: str | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    if pupil_id is not None:
        fields["pupil_id"] = pupil_id
    fields["meal_date"]    = ask("Meal date (YYYY-MM-DD, blank=today)",
                                 existing.meal_date if existing else None)
    fields["meal_type"]    = _pick("Meal type", MEAL_TYPES,
                                   existing.meal_type if existing else "Lunch")
    fields["menu"]         = ask("Menu", existing.menu if existing else None)
    fields["amount_eaten"] = _pick("Amount eaten", AMOUNTS,
                                   existing.amount_eaten if existing else None)
    fields["drink"]        = ask("Drink", existing.drink if existing else None)
    safe_cur = ("y" if existing.allergy_safe else "n") if existing else "y"
    fields["allergy_safe"] = ask("Allergy safe? (y/n)", safe_cur)
    try:
        staff = data.list_staff_choices()
    except Exception:
        logger.exception("Could not load staff choices")
        staff = []
    fields["staff_id"]     = _pick_id("Recorded by (staff)", staff,
                                      existing.staff_id if existing else None) or ""
    fields["notes"]        = ask("Notes", existing.notes if existing else None)
    return fields


def _show_children() -> None:
    try:
        choices = data.list_pupil_choices()
    except Exception:
        logger.exception("Could not load child choices")
        return
    if choices:
        print("  Children:")
        for _id, label in choices:
            print(f"    {label}")


@_safe
def open_manager() -> None:
    logger.debug("CLI: meals open_manager")
    while True:
        print("\n  ── Meals & Menus ──")
        date = _prompt("  Filter by date (YYYY-MM-DD, blank=all): ") or None
        _print_table(data.list_records(meal_date=date))
        print("\n   A) Add    V) View    E) Edit    D) Delete    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add()
        elif choice == "v":
            rid = _prompt("  Meal ID: ")
            r = data.get_record(rid)
            if r is None:
                print("  No record with that ID.")
            else:
                _print_detail(r)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    logger.debug("CLI: meals open_add")
    print("\n  ── Add Meal Record ──")
    _show_children()
    pid = _prompt("  Child ID: ")
    if not pid:
        print("  Cancelled.")
        return
    fields = _collect_fields(pupil_id=pid)
    r = data.create_record(fields)
    print(f"\n  Created meal record {r.meal_id} for {r.child_name} "
          f"({r.meal_type}).")


@_safe
def open_edit() -> None:
    logger.debug("CLI: meals open_edit")
    rid = _prompt("  Meal ID: ")
    if not rid:
        print("  Cancelled.")
        return
    existing = data.get_record(rid)
    if existing is None:
        print("  No record with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    r = data.update_record(rid, fields)
    print(f"\n  Updated meal record {r.meal_id}.")


@_safe
def open_delete() -> None:
    logger.debug("CLI: meals open_delete")
    rid = _prompt("  Meal ID to delete: ")
    if not rid:
        print("  Cancelled.")
        return
    existing = data.get_record(rid)
    if existing is None:
        print("  No record with that ID.")
        return
    confirm = _prompt(
        f"  Delete meal record {rid} for {existing.child_name}? (y/N): "
    ).lower()
    if confirm != "y":
        print("  Cancelled.")
        return
    if data.delete_record(rid):
        print(f"  Deleted record {rid}.")
    else:
        print("  Could not delete (already removed?).")


_DISPATCH = {"Meals & Menus": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching meals CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
