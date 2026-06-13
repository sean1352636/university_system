"""CLI handlers for teaching assistants."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.primarysch_system.modules.domain.teaching_assistants import (
    teaching_assistants as data,
)
from education_system.primarysch_system.modules.domain.teaching_assistants.teaching_assistants import (
    EMPLOYMENT_TYPES, ROLES, ROLE_LABELS,
)
from education_system.primarysch_system.modules.domain.pupils.pupils import (
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
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _print_table(rows: list) -> None:
    if not rows:
        print("  (no TAs)")
        return
    print(f"  {'ID':<4} {'Name':<26} {'Role':<18} {'Class':<14} "
          f"{'Hrs':<5} {'DBS':<4} {'SG':<3} {'Active':<6}")
    print(f"  {'-'*4} {'-'*26} {'-'*18} {'-'*14} {'-'*5} {'-'*4} "
          f"{'-'*3} {'-'*6}")
    for t in rows:
        hpw = "-" if t.hours_per_week is None else f"{t.hours_per_week:g}"
        print(f"  {t.ta_id:<4} {t.full_name[:26]:<26} {t.role[:18]:<18} "
              f"{(t.assigned_class or '-')[:14]:<14} {hpw:<5} "
              f"{'yes' if t.dbs_checked else 'NO':<4} "
              f"{'y' if t.safeguarding_trained else 'N':<3} "
              f"{'yes' if t.is_active else 'no':<6}")


@_safe
def open_teaching_assistants() -> None:
    logger.debug("CLI: open_teaching_assistants")
    while True:
        print("\n  -- Teaching Assistants --")
        try:
            s = data.summary()
        except Exception:
            s = {"total": 0, "active": 0, "needs_dbs": 0,
                 "needs_safeguarding": 0, "total_hours_per_week": 0.0}
        print(f"  Active: {s['active']}/{s['total']}   "
              f"Needs DBS: {s['needs_dbs']}   "
              f"Needs safeguarding: {s['needs_safeguarding']}   "
              f"Total hours/wk: {s['total_hours_per_week']:.1f}")
        print("\n   1) List active TAs")
        print("   2) List all TAs (incl. inactive)")
        print("   3) Filter / search TAs")
        print("   4) Show compliance gaps (no DBS / no safeguarding)")
        print("   5) Create TA")
        print("   6) Update TA")
        print("   7) Toggle active")
        print("   8) Delete TA")
        print("   9) Show role meanings")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice == "0" or choice == "":
            return
        actions = {
            "1": _list_active,
            "2": _list_all,
            "3": _filter,
            "4": _compliance,
            "5": _create,
            "6": _update,
            "7": _toggle,
            "8": _delete,
            "9": _show_help,
        }
        action = actions.get(choice)
        if action is None:
            print("  Invalid selection.")
            continue
        action()


@_safe
def _list_active() -> None:
    rows = data.list_all(active_only=True)
    print(f"\n  {len(rows)} active TA(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _list_all() -> None:
    rows = data.list_all()
    print(f"\n  {len(rows)} TA(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _filter() -> None:
    print(f"  Roles: {', '.join(ROLES)} (blank for any)")
    role = _prompt("  Role: ").strip() or None
    q = _prompt("  Name/email/class contains (blank for any): ").strip() or None
    active_only = _prompt("  Active only? (y/N): ").lower() == "y"
    rows = data.list_all(role=role, search=q, active_only=active_only)
    print(f"\n  {len(rows)} TA(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _compliance() -> None:
    rows = data.list_all(active_only=True, needs_dbs=True)
    print(f"\n  Active TAs WITHOUT DBS check ({len(rows)}):")
    _print_table(rows)
    rows2 = data.list_all(active_only=True, needs_safeguarding=True)
    print(f"\n  Active TAs WITHOUT safeguarding training ({len(rows2)}):")
    _print_table(rows2)
    _prompt("\n  Press Enter to continue...")


def _collect(defaults: dict | None = None) -> dict:
    d = defaults or {}
    print(f"  (Roles: {', '.join(ROLES)})")
    print(f"  (Employment types: {', '.join(EMPLOYMENT_TYPES)})")
    out: dict = {}
    out["first_name"]      = _prompt(f"  First name [{d.get('first_name','')}]: ") or d.get("first_name", "")
    out["last_name"]       = _prompt(f"  Last name [{d.get('last_name','')}]: ") or d.get("last_name", "")
    out["email"]           = _prompt(f"  Email [{d.get('email','')}]: ") or d.get("email", "")
    out["phone"]           = _prompt(f"  Phone [{d.get('phone','')}]: ") or d.get("phone", "")
    out["role"]            = _prompt(f"  Role [{d.get('role','TA')}]: ") or d.get("role", "TA")
    out["employment_type"] = _prompt(f"  Employment type [{d.get('employment_type','permanent')}]: ") or d.get("employment_type", "permanent")
    out["assigned_class"]  = _prompt(f"  Assigned class [{d.get('assigned_class','')}]: ") or d.get("assigned_class", "")
    hpw_def = "" if d.get("hours_per_week") in (None, "") else f"{d['hours_per_week']:g}"
    out["hours_per_week"]  = _prompt(f"  Hours/week [{hpw_def}]: ") or hpw_def
    out["start_date"]      = _prompt(f"  Start date YYYY-MM-DD [{d.get('start_date','')}]: ") or d.get("start_date", "")
    out["end_date"]        = _prompt(f"  End date YYYY-MM-DD [{d.get('end_date','')}]: ") or d.get("end_date", "")
    dbs_def = "y" if d.get("dbs_checked") else "n"
    out["dbs_checked"]     = (_prompt(f"  DBS checked? (y/n) [{dbs_def}]: ") or dbs_def).lower() == "y"
    sg_def = "y" if d.get("safeguarding_trained") else "n"
    out["safeguarding_trained"] = (_prompt(f"  Safeguarding trained? (y/n) [{sg_def}]: ") or sg_def).lower() == "y"
    out["notes"]           = _prompt(f"  Notes [{d.get('notes','')}]: ") or d.get("notes", "")
    return out


@_safe
def _create() -> None:
    print("\n  -- Create Teaching Assistant --")
    payload = _collect()
    rec = data.create(payload)
    print(f"  Created TA #{rec.ta_id} {rec.full_name} ({rec.role})")
    _prompt("\n  Press Enter to continue...")


@_safe
def _update() -> None:
    raw = _prompt("  TA ID to update: ")
    if not raw or not raw.isdigit():
        return
    existing = data.get(int(raw))
    if existing is None:
        print(f"  No TA #{raw}")
        return
    defaults = {
        "first_name": existing.first_name,
        "last_name": existing.last_name,
        "email": existing.email or "",
        "phone": existing.phone or "",
        "role": existing.role,
        "employment_type": existing.employment_type,
        "assigned_class": existing.assigned_class or "",
        "hours_per_week": existing.hours_per_week,
        "start_date": existing.start_date or "",
        "end_date": existing.end_date or "",
        "dbs_checked": existing.dbs_checked,
        "safeguarding_trained": existing.safeguarding_trained,
        "notes": existing.notes or "",
    }
    payload = _collect(defaults)
    rec = data.update(int(raw), payload)
    print(f"  Updated TA #{rec.ta_id}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _toggle() -> None:
    raw = _prompt("  TA ID to toggle: ")
    if not raw or not raw.isdigit():
        return
    rec = data.toggle_active(int(raw))
    print(f"  TA #{rec.ta_id} {rec.full_name} -> "
          f"{'active' if rec.is_active else 'inactive'}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete() -> None:
    raw = _prompt("  TA ID to delete: ")
    if not raw or not raw.isdigit():
        return
    confirm = _prompt(f"  Delete TA #{raw}? Type 'DELETE' to confirm: ")
    if confirm != "DELETE":
        print("  Cancelled.")
        return
    ok = data.delete(int(raw))
    print(f"  {'Deleted' if ok else 'No such TA'}: #{raw}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _show_help() -> None:
    print("\n  -- TA roles --")
    for r in ROLES:
        print(f"   {r:<18} {ROLE_LABELS[r]}")
    print(f"\n  Employment types: {', '.join(EMPLOYMENT_TYPES)}")
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"Teaching Assistants": open_teaching_assistants}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching TA CLI label: %s", label)
    handler()
    return True
