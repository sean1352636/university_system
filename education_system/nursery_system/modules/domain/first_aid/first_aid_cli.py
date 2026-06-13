"""CLI flow for Paediatric First Aid (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.nursery_system.modules.domain.first_aid import first_aid as data
from education_system.nursery_system.modules.domain.first_aid.first_aid import (
    CERTIFICATE_TYPES,
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


def _print_table(rows: list[data.PFACertificate]) -> None:
    if not rows:
        print("  (no PFA certificates)")
        return
    print(f"  {'ID':<8} {'Staff':<22} {'Type':<22} {'Expiry':<12} {'Validity'}")
    print(f"  {'-'*8} {'-'*22} {'-'*22} {'-'*12} {'-'*9}")
    for c in rows:
        print(f"  {c.record_id:<8} {(c.staff_name or '-')[:22]:<22} "
              f"{(c.certificate_type or '-')[:22]:<22} "
              f"{(c.expiry_date or '-'):<12} {c.validity}")


def _print_detail(c: data.PFACertificate) -> None:
    print(f"\n  ── PFA certificate {c.record_id} ──")
    print(f"  Staff:          {c.staff_name or '-'} ({c.staff_id})")
    print(f"  Type:           {c.certificate_type or '-'}")
    print(f"  Awarding body:  {c.awarding_body or '-'}")
    print(f"  Issued:         {c.issue_date or '-'}")
    print(f"  Expiry:         {c.expiry_date or '-'}  ({c.validity})")
    print(f"  Certificate:    {c.certificate_ref or '-'}")
    print(f"  Notes:          {c.notes or '-'}")


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


def _collect_fields(existing: data.PFACertificate | None = None,
                    *, staff_id: str | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    if staff_id is not None:
        fields["staff_id"] = staff_id
    fields["certificate_type"] = ask(f"Type ({'/'.join(CERTIFICATE_TYPES)})",
                                     existing.certificate_type if existing else None)
    fields["awarding_body"]    = ask("Awarding body",
                                     existing.awarding_body if existing else None)
    fields["issue_date"]       = ask("Issue date (YYYY-MM-DD)",
                                     existing.issue_date if existing else None)
    fields["expiry_date"]      = ask("Expiry date (YYYY-MM-DD)",
                                     existing.expiry_date if existing else None)
    fields["certificate_ref"]  = ask("Certificate reference",
                                     existing.certificate_ref if existing else None)
    fields["notes"]            = ask("Notes", existing.notes if existing else None)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: first_aid open_manager")
    while True:
        s = data.summary()
        print("\n  ── Paediatric First Aid ──")
        print(f"  Certificates: {s['total']}   Valid: {s['valid']}   "
              f"Expiring: {s['expiring']}   Expired: {s['expired']}   "
              f"Staff covered: {s['staff_covered']}")
        _print_table(data.list_certificates())
        print("\n   A) Add    V) View    E) Edit    D) Delete")
        print("   C) For a staff member    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add()
        elif choice == "v":
            rid = _prompt("  Certificate ID: ")
            c = data.get_certificate(rid)
            if c is None:
                print("  No certificate with that ID.")
            else:
                _print_detail(c)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        elif choice == "c":
            sid = _prompt("  Staff ID: ")
            _print_table(data.list_certificates(staff_id=sid))
            _prompt("  Press Enter to continue...")
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    print("\n  ── Add PFA Certificate ──")
    _show_staff()
    sid = _prompt("  Staff ID: ")
    if not sid:
        print("  Cancelled.")
        return
    fields = _collect_fields(staff_id=sid)
    c = data.create_certificate(fields)
    print(f"\n  Added PFA certificate {c.record_id} for {c.staff_name} "
          f"({c.validity}).")


@_safe
def open_edit() -> None:
    rid = _prompt("  Certificate ID: ")
    if not rid:
        print("  Cancelled.")
        return
    existing = data.get_certificate(rid)
    if existing is None:
        print("  No certificate with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    c = data.update_certificate(rid, fields)
    print(f"\n  Updated PFA certificate {c.record_id}.")


@_safe
def open_delete() -> None:
    rid = _prompt("  Certificate ID to delete: ")
    if not rid:
        print("  Cancelled.")
        return
    if data.get_certificate(rid) is None:
        print("  No certificate with that ID.")
        return
    if _prompt(f"  Delete certificate {rid}? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_certificate(rid):
        print(f"  Deleted certificate {rid}.")
    else:
        print("  Could not delete (already removed?).")


_DISPATCH = {"Paediatric First Aid": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching first_aid CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
