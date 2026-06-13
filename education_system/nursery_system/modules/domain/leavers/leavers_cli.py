"""CLI flow for Leavers (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.nursery_system.modules.domain.leavers import leavers as data
from education_system.nursery_system.modules.domain.leavers.leavers import (
    REASONS,
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


def _print_table(rows: list[data.Leaver]) -> None:
    if not rows:
        print("  (no leavers recorded)")
        return
    print(f"  {'ID':<8} {'Child':<22} {'Left on':<12} {'Reason':<22} "
          f"{'Destination'}")
    print(f"  {'-'*8} {'-'*22} {'-'*12} {'-'*22} {'-'*20}")
    for lv in rows:
        print(f"  {lv.leaver_id:<8} {(lv.child_name or '-')[:22]:<22} "
              f"{(lv.leaving_date or '-'):<12} {(lv.reason or '-')[:22]:<22} "
              f"{lv.destination or '-'}")


def _print_detail(lv: data.Leaver) -> None:
    print(f"\n  ── Leaver {lv.leaver_id} ──")
    print(f"  Child:               {lv.child_name or '-'} ({lv.pupil_id})")
    print(f"  Room:                {lv.room or '-'}")
    print(f"  Leaving date:        {lv.leaving_date or '-'}")
    print(f"  Last day attended:   {lv.last_day_attended or '-'}")
    print(f"  Reason:              {lv.reason or '-'}")
    print(f"  Destination:         {lv.destination or '-'}")
    print(f"  Records transferred: {'Yes' if lv.records_transferred else 'No'}")
    print(f"  Roll status:         {lv.pupil_status or '-'}")
    print(f"  Notes:               {lv.notes or '-'}")


def _show_children() -> None:
    try:
        choices = data.list_active_pupil_choices()
    except Exception:
        logger.exception("Could not load child choices")
        return
    if choices:
        print("  Children on roll:")
        for _id, label in choices:
            print(f"    {label}")


def _collect_fields(existing: data.Leaver | None = None,
                    *, pupil_id: str | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    if pupil_id is not None:
        fields["pupil_id"] = pupil_id
    fields["leaving_date"]      = ask("Leaving date (YYYY-MM-DD)",
                                      existing.leaving_date if existing else None)
    fields["last_day_attended"] = ask("Last day attended (YYYY-MM-DD)",
                                      existing.last_day_attended if existing else None)
    fields["reason"]            = ask(f"Reason ({'/'.join(REASONS)})",
                                      existing.reason if existing else None)
    fields["destination"]       = ask("Destination (school / provider)",
                                      existing.destination if existing else None)
    rt_cur = ("y" if existing.records_transferred else "n") if existing else None
    fields["records_transferred"] = ask("Records transferred? (y/n)", rt_cur)
    fields["notes"]             = ask("Notes", existing.notes if existing else None)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: leavers open_manager")
    while True:
        print("\n  ── Leavers ──")
        _print_table(data.list_leavers())
        print("\n   A) Record a leaver    V) View    E) Edit")
        print("   R) Reinstate (back on roll)    D) Delete record    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add()
        elif choice == "v":
            lid = _prompt("  Leaver ID: ")
            lv = data.get_leaver(lid)
            if lv is None:
                print("  No leaver with that ID.")
            else:
                _print_detail(lv)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "r":
            open_reinstate()
        elif choice == "d":
            open_delete()
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    print("\n  ── Record a Leaver ──")
    _show_children()
    pid = _prompt("  Child ID: ")
    if not pid:
        print("  Cancelled.")
        return
    fields = _collect_fields(pupil_id=pid)
    lv = data.record_leaver(fields)
    print(f"\n  Recorded {lv.child_name} as a leaver ({lv.leaver_id}); "
          "child taken off the active roll.")


@_safe
def open_edit() -> None:
    lid = _prompt("  Leaver ID: ")
    if not lid:
        print("  Cancelled.")
        return
    existing = data.get_leaver(lid)
    if existing is None:
        print("  No leaver with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    lv = data.update_leaver(lid, fields)
    print(f"\n  Updated leaver {lv.leaver_id}.")


@_safe
def open_reinstate() -> None:
    lid = _prompt("  Leaver ID to reinstate: ")
    if not lid:
        print("  Cancelled.")
        return
    existing = data.get_leaver(lid)
    if existing is None:
        print("  No leaver with that ID.")
        return
    confirm = _prompt(
        f"  Put {existing.child_name} back on the active roll and remove the "
        f"leaver record? (y/N): ").lower()
    if confirm != "y":
        print("  Cancelled.")
        return
    pid = data.reinstate(lid)
    print(f"  Child {pid} is back on the active roll.")


@_safe
def open_delete() -> None:
    lid = _prompt("  Leaver ID to delete: ")
    if not lid:
        print("  Cancelled.")
        return
    if data.get_leaver(lid) is None:
        print("  No leaver with that ID.")
        return
    print("  Note: this removes the leaver record only; the child stays off roll.")
    if _prompt(f"  Delete leaver record {lid}? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_leaver(lid):
        print(f"  Deleted leaver record {lid}.")
    else:
        print("  Could not delete (already removed?).")


_DISPATCH = {"Leavers": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching leavers CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
