"""CLI flow for Emergency Contacts (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.nursery.domain.learners.emergency_contacts import (
    emergency_contacts as data,
)
from education_system.systems.nursery.domain.learners.emergency_contacts.emergency_contacts import (
    RELATIONSHIPS,
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


def _yn(flag: bool) -> str:
    return "Yes" if flag else "No"


def _print_table(rows: list[data.EmergencyContact]) -> None:
    if not rows:
        print("  (no emergency contacts)")
        return
    print(f"  {'ID':<8} {'Child':<20} {'Name':<22} {'Relationship':<14} "
          f"{'Phone':<16} {'Pri':<4} {'Collect'}")
    print(f"  {'-'*8} {'-'*20} {'-'*22} {'-'*14} {'-'*16} {'-'*4} {'-'*7}")
    for c in rows:
        print(f"  {c.contact_id:<8} {(c.child_name or '-')[:20]:<20} "
              f"{c.full_name[:22]:<22} {(c.relationship or '-')[:14]:<14} "
              f"{(c.phone_primary or '-')[:16]:<16} {str(c.priority):<4} "
              f"{_yn(c.can_collect)}")


def _print_detail(c: data.EmergencyContact) -> None:
    print(f"\n  ── Emergency contact {c.contact_id} ──")
    print(f"  Child:                 {c.child_name or '-'} ({c.pupil_id})")
    print(f"  Name:                  {c.full_name}")
    print(f"  Relationship:          {c.relationship or '-'}")
    print(f"  Phone (primary):       {c.phone_primary or '-'}")
    print(f"  Phone (alt):           {c.phone_alt or '-'}")
    print(f"  Priority:              {c.priority}")
    print(f"  Authorised to collect: {_yn(c.can_collect)}")
    print(f"  Notes:                 {c.notes or '-'}")


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


def _ask_bool(label: str, current: bool | None) -> str:
    cur = "" if current is None else ("y" if current else "n")
    suffix = f" [{cur}]" if cur else ""
    v = _prompt(f"  {label} (y/n){suffix}: ").lower()
    return v if v else cur


def _collect_fields(existing: data.EmergencyContact | None = None,
                    *, pupil_id: str | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    if pupil_id is not None:
        fields["pupil_id"] = pupil_id
    fields["full_name"]    = ask("Contact name",
                                 existing.full_name if existing else None)
    fields["relationship"] = ask(f"Relationship ({'/'.join(RELATIONSHIPS)})",
                                 existing.relationship if existing else None)
    fields["phone_primary"] = ask("Phone (primary)",
                                  existing.phone_primary if existing else None)
    fields["phone_alt"]    = ask("Phone (alt)",
                                 existing.phone_alt if existing else None)
    fields["priority"]     = ask("Priority (1 = first called)",
                                 existing.priority if existing else 1)
    fields["can_collect"]  = _ask_bool("Authorised to collect?",
                                       existing.can_collect if existing else False)
    fields["notes"]        = ask("Notes", existing.notes if existing else None)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: emergency_contacts open_manager")
    while True:
        print("\n  ── Emergency Contacts ──")
        _print_table(data.list_contacts())
        print("\n   A) Add contact    V) View    E) Edit    D) Delete")
        print("   C) Contacts for a child    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add()
        elif choice == "v":
            cid = _prompt("  Contact ID: ")
            c = data.get_contact(cid)
            if c is None:
                print("  No contact with that ID.")
            else:
                _print_detail(c)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        elif choice == "c":
            pid = _prompt("  Child ID: ")
            _print_table(data.list_contacts(pupil_id=pid))
            _prompt("  Press Enter to continue...")
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    print("\n  ── Add Emergency Contact ──")
    _show_children()
    pid = _prompt("  Child ID: ")
    if not pid:
        print("  Cancelled.")
        return
    fields = _collect_fields(pupil_id=pid)
    c = data.create_contact(fields)
    print(f"\n  Added emergency contact {c.contact_id} ({c.full_name}) for "
          f"{c.child_name or pid}.")


@_safe
def open_edit() -> None:
    cid = _prompt("  Contact ID: ")
    if not cid:
        print("  Cancelled.")
        return
    existing = data.get_contact(cid)
    if existing is None:
        print("  No contact with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    c = data.update_contact(cid, fields)
    print(f"\n  Updated emergency contact {c.contact_id}.")


@_safe
def open_delete() -> None:
    cid = _prompt("  Contact ID to delete: ")
    if not cid:
        print("  Cancelled.")
        return
    existing = data.get_contact(cid)
    if existing is None:
        print("  No contact with that ID.")
        return
    if _prompt(f"  Delete {existing.full_name} ({cid})? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_contact(cid):
        print(f"  Deleted contact {cid}.")
    else:
        print("  Could not delete (already removed?).")


_DISPATCH = {"Emergency Contacts": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching emergency_contacts CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
