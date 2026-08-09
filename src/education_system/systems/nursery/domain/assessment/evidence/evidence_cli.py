"""CLI flow for Photos & Evidence (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.nursery.domain.assessment.evidence import (
    evidence as data,
)
from education_system.systems.nursery.domain.assessment.evidence.evidence import (
    AREAS,
    EVIDENCE_TYPES,
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


def _print_table(rows: list[data.Evidence]) -> None:
    if not rows:
        print("  (no evidence records)")
        return
    print(f"  {'ID':<8} {'Child':<20} {'Date':<12} {'Type':<14} "
          f"{'Area':<32} {'Title':<22} {'Shared'}")
    print(f"  {'-'*8} {'-'*20} {'-'*12} {'-'*14} {'-'*32} {'-'*22} {'-'*6}")
    for ev in rows:
        shared = "Yes" if ev.shared_with_parent else ""
        print(f"  {ev.evidence_id:<8} {(ev.child_name or '-')[:20]:<20} "
              f"{(ev.capture_date or '-')[:12]:<12} "
              f"{(ev.evidence_type or '-')[:14]:<14} "
              f"{(ev.area or '-')[:32]:<32} "
              f"{ev.title[:22]:<22} {shared}")


def _print_detail(ev: data.Evidence) -> None:
    print(f"\n  ── Evidence {ev.evidence_id} ──")
    print(f"  Child:              {ev.child_name or '-'} ({ev.pupil_id})")
    print(f"  Title:              {ev.title}")
    print(f"  Capture date:       {ev.capture_date or '-'}")
    print(f"  Type:               {ev.evidence_type or '-'}")
    print(f"  Area:               {ev.area or '-'}")
    print(f"  File ref:           {ev.file_ref or '-'}")
    print(f"  Description:        {ev.description or '-'}")
    print(f"  Shared with parent: {'Yes' if ev.shared_with_parent else 'No'}")
    print(f"  Staff:              {ev.staff_name or ev.staff_id or '-'}")


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


def _collect_fields(existing: data.Evidence | None = None,
                    *, pupil_id: str | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    if pupil_id is not None:
        fields["pupil_id"] = pupil_id
    fields["title"]         = ask("Title", existing.title if existing else None)
    fields["capture_date"]  = ask("Capture date (YYYY-MM-DD)",
                                  existing.capture_date if existing else None)
    fields["evidence_type"] = ask(f"Type ({'/'.join(EVIDENCE_TYPES)})",
                                  existing.evidence_type if existing else None)
    fields["area"]          = ask(f"Area ({'/'.join(AREAS)})",
                                  existing.area if existing else None)
    fields["file_ref"]      = ask("File ref", existing.file_ref if existing else None)
    fields["description"]   = ask("Description",
                                  existing.description if existing else None)
    fields["shared_with_parent"] = _ask_bool(
        "Shared with parent?",
        existing.shared_with_parent if existing else False)
    fields["staff_id"]      = ask("Staff ID", existing.staff_id if existing else None)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: evidence open_manager")
    while True:
        print("\n  ── Photos & Evidence ──")
        _print_table(data.list_evidence())
        print("\n   A) Add    V) View    E) Edit    D) Delete    F) Filter by child")
        print("   0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add()
        elif choice == "v":
            eid = _prompt("  Evidence ID: ")
            ev = data.get_evidence(eid)
            if ev is None:
                print("  No evidence with that ID.")
            else:
                _print_detail(ev)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        elif choice == "f":
            pid = _prompt("  Child ID: ")
            _print_table(data.list_evidence(pupil_id=pid))
            _prompt("  Press Enter to continue...")
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    print("\n  ── Add Evidence ──")
    _show_children()
    pid = _prompt("  Child ID: ")
    if not pid:
        print("  Cancelled.")
        return
    fields = _collect_fields(pupil_id=pid)
    ev = data.create_evidence(fields)
    print(f"\n  Added evidence {ev.evidence_id} ('{ev.title}') for "
          f"{ev.child_name or pid}.")


@_safe
def open_edit() -> None:
    eid = _prompt("  Evidence ID: ")
    if not eid:
        print("  Cancelled.")
        return
    existing = data.get_evidence(eid)
    if existing is None:
        print("  No evidence with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    ev = data.update_evidence(eid, fields)
    print(f"\n  Updated evidence {ev.evidence_id}.")


@_safe
def open_delete() -> None:
    eid = _prompt("  Evidence ID to delete: ")
    if not eid:
        print("  Cancelled.")
        return
    existing = data.get_evidence(eid)
    if existing is None:
        print("  No evidence with that ID.")
        return
    if _prompt(f"  Delete '{existing.title}' ({eid})? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_evidence(eid):
        print(f"  Deleted evidence {eid}.")
    else:
        print("  Could not delete (already removed?).")


_DISPATCH = {"Photos & Evidence": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching evidence CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
