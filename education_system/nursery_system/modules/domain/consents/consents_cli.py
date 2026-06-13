"""CLI flow for Permissions & Consents (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.nursery_system.modules.domain.consents import (
    consents as data,
)
from education_system.nursery_system.modules.domain.consents.consents import (
    CONSENT_TYPES,
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


def _print_table(rows: list[data.Consent]) -> None:
    if not rows:
        print("  (no consents)")
        return
    print(f"  {'ID':<8} {'Child':<20} {'Type':<30} {'Status':<10} "
          f"{'Recorded':<12} {'Expiry':<12} {'Recorded by'}")
    print(f"  {'-'*8} {'-'*20} {'-'*30} {'-'*10} "
          f"{'-'*12} {'-'*12} {'-'*20}")
    for c in rows:
        print(f"  {c.consent_id:<8} {(c.child_name or '-')[:20]:<20} "
              f"{c.consent_type[:30]:<30} {c.status:<10} "
              f"{(c.date_recorded or '-'):<12} {(c.expiry_date or '-'):<12} "
              f"{(c.recorded_by_name or '-')}")


def _print_detail(c: data.Consent) -> None:
    print(f"\n  ── Consent {c.consent_id} ──")
    print(f"  Child:         {c.child_name or '-'} ({c.pupil_id})")
    print(f"  Consent type:  {c.consent_type}")
    print(f"  Status:        {c.status}")
    print(f"  Date recorded: {c.date_recorded or '-'}")
    print(f"  Expiry date:   {c.expiry_date or '-'}")
    print(f"  Recorded by:   {c.recorded_by_name or (c.recorded_by or '-')}")
    print(f"  Notes:         {c.notes or '-'}")


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


def _show_staff() -> None:
    try:
        choices = data.list_staff_choices()
    except Exception:
        logger.exception("Could not load staff choices")
        return
    if choices:
        print("  Staff:")
        for _id, label in choices:
            print(f"    {label}")


def _collect_fields(existing: data.Consent | None = None,
                    *, pupil_id: str | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    if pupil_id is not None:
        fields["pupil_id"] = pupil_id

    fields["consent_type"] = ask(
        f"Consent type ({'/'.join(CONSENT_TYPES)})",
        existing.consent_type if existing else None)
    fields["status"] = ask(
        f"Status ({'/'.join(STATUSES)})",
        existing.status if existing else "granted")
    fields["date_recorded"] = ask(
        "Date recorded (YYYY-MM-DD)",
        existing.date_recorded if existing else None)
    fields["expiry_date"] = ask(
        "Expiry date (YYYY-MM-DD)",
        existing.expiry_date if existing else None)

    _show_staff()
    fields["recorded_by"] = ask(
        "Recorded by (staff ID)",
        existing.recorded_by if existing else None)
    fields["notes"] = ask("Notes", existing.notes if existing else None)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: consents open_manager")
    while True:
        print("\n  ── Permissions & Consents ──")
        _print_table(data.list_consents())
        print("\n   A) Add consent    V) View    E) Edit    D) Delete")
        print("   C) Consents for a child    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add()
        elif choice == "v":
            cid = _prompt("  Consent ID: ")
            c = data.get_consent(cid)
            if c is None:
                print("  No consent with that ID.")
            else:
                _print_detail(c)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        elif choice == "c":
            pid = _prompt("  Child ID: ")
            _print_table(data.list_consents(pupil_id=pid))
            _prompt("  Press Enter to continue...")
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    print("\n  ── Add Consent ──")
    _show_children()
    pid = _prompt("  Child ID: ")
    if not pid:
        print("  Cancelled.")
        return
    fields = _collect_fields(pupil_id=pid)
    c = data.create_consent(fields)
    print(f"\n  Added consent {c.consent_id} ({c.consent_type}) for "
          f"{c.child_name or pid}.")


@_safe
def open_edit() -> None:
    cid = _prompt("  Consent ID: ")
    if not cid:
        print("  Cancelled.")
        return
    existing = data.get_consent(cid)
    if existing is None:
        print("  No consent with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    c = data.update_consent(cid, fields)
    print(f"\n  Updated consent {c.consent_id}.")


@_safe
def open_delete() -> None:
    cid = _prompt("  Consent ID to delete: ")
    if not cid:
        print("  Cancelled.")
        return
    existing = data.get_consent(cid)
    if existing is None:
        print("  No consent with that ID.")
        return
    if _prompt(f"  Delete {existing.consent_type} consent for "
               f"{existing.child_name or existing.pupil_id} ({cid})? (y/N): "
               ).lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_consent(cid):
        print(f"  Deleted consent {cid}.")
    else:
        print("  Could not delete (already removed?).")


_DISPATCH = {"Permissions & Consents": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching consents CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
