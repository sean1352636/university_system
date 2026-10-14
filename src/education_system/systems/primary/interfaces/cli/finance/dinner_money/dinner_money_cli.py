"""CLI handlers for dinner money."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.primary.domain.finance.dinner_money import (
    dinner_money as data,
)
from education_system.systems.primary.domain.finance.dinner_money.dinner_money import (
    KINDS, KIND_LABELS, MEAL_TYPES, MEAL_TYPE_LABELS, format_pence,
)
from education_system.systems.primary.domain.learners.pupils.pupils import (
    ValidationError, YEAR_GROUPS,
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
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _print_entries(rows: list[tuple]) -> None:
    if not rows:
        print("  (no entries)")
        return
    print(f"  {'#':<6} {'Date':<11} {'Pupil':<10} {'Name':<22} "
          f"{'Kind':<11} {'Meal':<8} {'Amount':<8} {'Description':<24}")
    print(f"  {'-'*6} {'-'*11} {'-'*10} {'-'*22} {'-'*11} {'-'*8} "
          f"{'-'*8} {'-'*24}")
    for e, p in rows:
        name = p.full_name if p else "(unknown)"
        print(f"  {e.entry_id:<6} {e.entry_date:<11} {e.pupil_id:<10} "
              f"{name[:22]:<22} {e.kind:<11} {(e.meal_type or '-'):<8} "
              f"{e.amount_display:<8} {(e.description or '-')[:24]:<24}")


@_safe
def open_dinner_money() -> None:
    logger.debug("CLI: open_dinner_money")
    while True:
        print("\n  -- Dinner Money --")
        try:
            s = data.summary()
        except Exception:
            s = {"entries": 0, "total_credits_pence": 0,
                 "total_charges_pence": 0, "pupils_owing": 0,
                 "pupils_in_credit": 0, "total_owed_pence": 0}
        print(f"  Entries: {s['entries']}   "
              f"Credits: {format_pence(s['total_credits_pence'])}   "
              f"Charges: {format_pence(s['total_charges_pence'])}")
        print(f"  Pupils owing: {s['pupils_owing']}   "
              f"In credit: {s['pupils_in_credit']}   "
              f"Total owed: {format_pence(s['total_owed_pence'])}")
        print("\n   1) Pupil balance / statement")
        print("   2) Charge meal")
        print("   3) Credit (top-up)")
        print("   4) Record other entry (refund / adjustment)")
        print("   5) List recent entries")
        print("   6) Filter entries")
        print("   7) Pupils currently owing money")
        print("   8) Update entry")
        print("   9) Delete entry")
        print("  10) Show kinds / meal types")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice == "0" or choice == "":
            return
        actions = {
            "1": _statement,
            "2": _charge,
            "3": _credit,
            "4": _other_entry,
            "5": _list_recent,
            "6": _filter,
            "7": _owing,
            "8": _update,
            "9": _delete,
            "10": _show_help,
        }
        action = actions.get(choice)
        if action is None:
            print("  Invalid selection.")
            continue
        action()


@_safe
def _statement() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    s = data.pupil_statement(pid)
    print(f"\n  -- Statement for pupil {pid} --")
    print(f"  Total credits: {format_pence(s['total_credits_pence'])}")
    print(f"  Total charges: {format_pence(s['total_charges_pence'])}")
    print(f"  Balance:       {format_pence(s['balance_pence'])}"
          + ("   (in credit)" if s['balance_pence'] > 0
             else "   (OWING)" if s['balance_pence'] < 0 else "   (settled)"))
    print(f"\n  {len(s['entries'])} entry/entries:")
    rows = [(e, None) for e in s["entries"]]
    _print_entries(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _charge() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    print(f"  Meal types: {', '.join(MEAL_TYPES)}")
    mt = _prompt("  Meal type [hot]: ").strip().lower() or "hot"
    pounds = _prompt("  Cost in £ (blank/0 = free meal log): ")
    date = _prompt("  Date YYYY-MM-DD (blank for today): ")
    by = _prompt("  Recorded by (optional): ")
    notes = _prompt("  Notes (optional): ")
    rec = data.charge_meal(
        pid, entry_date=date or None, meal_type=mt,
        amount_pounds=pounds or 0, recorded_by=by or None, notes=notes or None,
    )
    print(f"  Recorded #{rec.entry_id}: charge {rec.amount_display} "
          f"({rec.meal_type}) on {rec.entry_date}")
    new_bal = data.pupil_balance(pid)
    print(f"  New balance: {format_pence(new_bal)}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _credit() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    pounds = _prompt("  Top-up amount in £: ")
    if not pounds:
        print("  Amount is required.")
        return
    date = _prompt("  Date YYYY-MM-DD (blank for today): ")
    by = _prompt("  Recorded by (optional): ")
    desc = _prompt("  Description (optional): ")
    rec = data.credit(
        pid, amount_pounds=pounds, entry_date=date or None,
        recorded_by=by or None, description=desc or None,
    )
    print(f"  Recorded #{rec.entry_id}: credit {rec.amount_display} "
          f"on {rec.entry_date}")
    new_bal = data.pupil_balance(pid)
    print(f"  New balance: {format_pence(new_bal)}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _other_entry() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    print(f"  Kinds: {', '.join(KINDS)}")
    kind = _prompt("  Kind (refund / adjustment): ").strip().lower()
    if not kind:
        return
    pounds = _prompt("  Amount in £ (sign matters for adjustment): ")
    date = _prompt("  Date YYYY-MM-DD (blank for today): ")
    desc = _prompt("  Description: ")
    notes = _prompt("  Notes: ")
    rec = data.record({
        "pupil_id": pid, "entry_date": date,
        "kind": kind, "amount_pounds": pounds,
        "description": desc, "notes": notes,
    })
    print(f"  Recorded #{rec.entry_id}: {rec.kind} {rec.amount_display}")
    print(f"  New balance: {format_pence(data.pupil_balance(pid))}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _list_recent() -> None:
    rows = data.list_entries(limit=50)
    print(f"\n  Last {len(rows)} entry/entries:")
    _print_entries(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _filter() -> None:
    pid = _prompt("  Pupil ID (blank for any): ").strip() or None
    print(f"  Kinds: {', '.join(KINDS)} (blank for any)")
    kind = _prompt("  Kind: ").strip().lower() or None
    print(f"  Meal types: {', '.join(MEAL_TYPES)} (blank for any)")
    mt = _prompt("  Meal type: ").strip().lower() or None
    fr = _prompt("  From date YYYY-MM-DD: ").strip() or None
    to = _prompt("  To date YYYY-MM-DD: ").strip() or None
    rows = data.list_entries(pupil_id=pid, kind=kind, meal_type=mt,
                             from_date=fr, to_date=to, limit=500)
    print(f"\n  {len(rows)} entry/entries:")
    _print_entries(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _owing() -> None:
    print(f"  Year groups: {', '.join(YEAR_GROUPS)} (blank for any)")
    yg = _prompt("  Year group: ").strip() or None
    rows = data.balances(year_group=yg, owing_only=True)
    print(f"\n  {len(rows)} pupil(s) owing money:")
    if not rows:
        print("    (none)")
    else:
        print(f"  {'Pupil ID':<10} {'Name':<26} {'Year':<5} {'Balance':<10}")
        print(f"  {'-'*10} {'-'*26} {'-'*5} {'-'*10}")
        for p, bal in rows:
            print(f"  {p.pupil_id:<10} {p.full_name[:26]:<26} "
                  f"{p.year_group:<5} {format_pence(bal):<10}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _update() -> None:
    raw = _prompt("  Entry ID to update: ")
    if not raw or not raw.isdigit():
        return
    existing = data.get(int(raw))
    if existing is None:
        print(f"  No entry #{raw}")
        return
    print(f"  Current: {existing.kind} {existing.amount_display} on "
          f"{existing.entry_date} (pupil {existing.pupil_id})")
    new_pounds = _prompt(f"  New amount £ [{existing.amount_pence/100:.2f}]: ")
    new_desc   = _prompt(f"  Description [{existing.description or ''}]: ")
    new_notes  = _prompt(f"  Notes [{existing.notes or ''}]: ")
    payload = {
        "pupil_id": existing.pupil_id,
        "entry_date": existing.entry_date,
        "kind": existing.kind,
        "meal_type": existing.meal_type or "",
    }
    if new_pounds:
        payload["amount_pounds"] = new_pounds
    else:
        payload["amount_pence"] = existing.amount_pence
    if new_desc:
        payload["description"] = new_desc
    elif existing.description is not None:
        payload["description"] = existing.description
    if new_notes:
        payload["notes"] = new_notes
    elif existing.notes is not None:
        payload["notes"] = existing.notes
    rec = data.update(int(raw), payload)
    print(f"  Updated #{rec.entry_id}: {rec.kind} {rec.amount_display}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete() -> None:
    raw = _prompt("  Entry ID to delete: ")
    if not raw or not raw.isdigit():
        return
    confirm = _prompt(f"  Delete entry #{raw}? Type 'DELETE' to confirm: ")
    if confirm != "DELETE":
        print("  Cancelled.")
        return
    ok = data.delete(int(raw))
    print(f"  {'Deleted' if ok else 'No such entry'}: #{raw}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _show_help() -> None:
    print("\n  -- Entry kinds --")
    for k in KINDS:
        print(f"   {k:<11} {KIND_LABELS[k]}")
    print("\n  -- Meal types --")
    for m in MEAL_TYPES:
        print(f"   {m:<8} {MEAL_TYPE_LABELS[m]}")
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"Dinner Money": open_dinner_money}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching dinner_money CLI label: %s", label)
    handler()
    return True
