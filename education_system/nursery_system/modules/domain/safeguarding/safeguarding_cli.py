"""CLI flow for Safeguarding / Child Protection (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.nursery_system.modules.domain.safeguarding import (
    safeguarding as data,
)
from education_system.nursery_system.modules.domain.safeguarding.safeguarding import (
    CATEGORIES,
    SEVERITIES,
    STATUSES,
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


def _print_table(rows: list[data.Concern]) -> None:
    if not rows:
        print("  (no safeguarding concerns)")
        return
    print(f"  {'ID':<8} {'Date':<12} {'Child':<18} {'Category':<20} "
          f"{'Sev':<7} {'Status'}")
    print(f"  {'-'*8} {'-'*12} {'-'*18} {'-'*20} {'-'*7} {'-'*10}")
    for c in rows:
        ref = " *REF" if c.referral_made else ""
        print(f"  {c.concern_id:<8} {(c.date_raised or '-'):<12} "
              f"{(c.child_name or '-')[:18]:<18} {(c.category or '-')[:20]:<20} "
              f"{c.severity:<7} {c.status}{ref}")


def _print_detail(c: data.Concern) -> None:
    print(f"\n  ── Safeguarding concern {c.concern_id} ──")
    print(f"  Child:         {c.child_name or '(not linked)'} ({c.pupil_id or '-'})")
    print(f"  Category:      {c.category or '-'}")
    print(f"  Severity:      {c.severity}")
    print(f"  Date raised:   {c.date_raised or '-'}")
    print(f"  Raised by:     {c.raised_by or '-'}")
    print(f"  Description:   {c.description or '-'}")
    print(f"  DSL reviewer:  {c.dsl_name or c.dsl_reviewer or '-'}")
    print(f"  Action taken:  {c.action_taken or '-'}")
    print(f"  Referral made: {'Yes' if c.referral_made else 'No'}")
    print(f"  Status:        {c.status}")
    print(f"  Notes:         {c.notes or '-'}")


def _show_children() -> None:
    try:
        choices = data.list_pupil_choices()
    except Exception:
        return
    if choices:
        print("  Children: " + ", ".join(f"{i}={lbl.split(' (')[0]}"
                                         for i, lbl in choices))


def _show_staff() -> None:
    try:
        choices = data.list_staff_choices()
    except Exception:
        return
    if choices:
        print("  Staff: " + ", ".join(label for _id, label in choices))


def _collect_fields(existing: data.Concern | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    if existing is None:
        _show_children()
    fields["pupil_id"]      = ask("Child ID (blank if not child-specific)",
                                  existing.pupil_id if existing else None)
    fields["category"]      = ask(f"Category ({'/'.join(CATEGORIES)})",
                                  existing.category if existing else None)
    fields["severity"]      = ask(f"Severity ({'/'.join(SEVERITIES)})",
                                  existing.severity if existing else "medium")
    fields["date_raised"]   = ask("Date raised (YYYY-MM-DD)",
                                  existing.date_raised if existing else None)
    fields["raised_by"]     = ask("Raised by",
                                  existing.raised_by if existing else None)
    fields["description"]   = ask("Description",
                                  existing.description if existing else None)
    if existing is None:
        _show_staff()
    fields["dsl_reviewer"]  = ask("DSL reviewer (staff ID)",
                                  existing.dsl_reviewer if existing else None)
    fields["action_taken"]  = ask("Action taken",
                                  existing.action_taken if existing else None)
    fields["referral_made"] = ask("Referral made? (y/n)",
                                  ("y" if existing.referral_made else "n")
                                  if existing else None)
    fields["status"]        = ask(f"Status ({'/'.join(STATUSES)})",
                                  existing.status if existing else "open")
    fields["notes"]         = ask("Notes", existing.notes if existing else None)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: safeguarding open_manager")
    while True:
        s = data.summary()
        print("\n  ── Safeguarding / Child Protection ──")
        print(f"  Concerns: {s['total']}   Open: {s['open']}   "
              f"Referred: {s['referred']}   High & open: {s['high_open']}")
        _print_table(data.list_concerns())
        print("\n   A) Add    V) View    E) Edit    D) Delete    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add()
        elif choice == "v":
            cid = _prompt("  Concern ID: ")
            c = data.get_concern(cid)
            if c is None:
                print("  No concern with that ID.")
            else:
                _print_detail(c)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    print("\n  ── Log Safeguarding Concern ──")
    fields = _collect_fields()
    c = data.create_concern(fields)
    print(f"\n  Logged concern {c.concern_id} ({c.severity} severity).")


@_safe
def open_edit() -> None:
    cid = _prompt("  Concern ID: ")
    if not cid:
        print("  Cancelled.")
        return
    existing = data.get_concern(cid)
    if existing is None:
        print("  No concern with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    c = data.update_concern(cid, fields)
    print(f"\n  Updated concern {c.concern_id}.")


@_safe
def open_delete() -> None:
    cid = _prompt("  Concern ID to delete: ")
    if not cid:
        print("  Cancelled.")
        return
    if data.get_concern(cid) is None:
        print("  No concern with that ID.")
        return
    if _prompt(f"  Delete concern {cid}? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_concern(cid):
        print(f"  Deleted concern {cid}.")
    else:
        print("  Could not delete (already removed?).")


_DISPATCH = {"Safeguarding / Child Protection": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching safeguarding CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
