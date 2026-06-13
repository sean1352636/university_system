"""CLI flow for Next Steps Planning (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.nursery_system.modules.domain.next_steps import (
    next_steps as data,
)
from education_system.nursery_system.modules.domain.next_steps.next_steps import (
    AREAS,
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


def _print_steps(rows: list[data.NextStep]) -> None:
    if not rows:
        print("  (no next steps)")
        return
    print(f"  {'ID':<8} {'Child':<22} {'Area':<20} {'Status':<12} "
          f"{'Target':<12} {'Description'}")
    print(f"  {'-'*8} {'-'*22} {'-'*20} {'-'*12} {'-'*12} {'-'*30}")
    for s in rows:
        desc = (s.description or "")[:30]
        print(f"  {s.step_id:<8} {(s.child_name or '-')[:22]:<22} "
              f"{(s.area or '-')[:20]:<20} {(s.status or '-'):<12} "
              f"{(s.target_date or '-'):<12} {desc}")


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
        return
    if choices:
        print("  Staff: " + ", ".join(label for _id, label in choices))


def _collect_fields(existing: data.NextStep | None = None,
                    *, pupil_id: str | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    if pupil_id is not None:
        fields["pupil_id"] = pupil_id
    fields["description"]   = ask("Description (required)",
                                  existing.description if existing else None)
    fields["area"]          = ask(f"Area ({'/'.join(AREAS)})",
                                  existing.area if existing else None)
    fields["status"]        = ask(f"Status ({'/'.join(STATUSES)})",
                                  existing.status if existing else None)
    fields["planned_date"]  = ask("Planned date (YYYY-MM-DD)",
                                  existing.planned_date if existing else None)
    fields["target_date"]   = ask("Target date (YYYY-MM-DD)",
                                  existing.target_date if existing else None)
    fields["achieved_date"] = ask("Achieved date (YYYY-MM-DD)",
                                  existing.achieved_date if existing else None)
    _show_staff()
    fields["staff_id"]      = ask("Staff ID",
                                  existing.staff_id if existing else None)
    fields["notes"]         = ask("Notes", existing.notes if existing else None)
    return fields


def _print_detail(s: data.NextStep) -> None:
    print(f"\n  ── Next Step {s.step_id} ──")
    print(f"  Child:         {s.child_name or '-'} ({s.pupil_id})")
    print(f"  Area:          {s.area or '-'}")
    print(f"  Description:   {s.description}")
    print(f"  Status:        {s.status}")
    print(f"  Planned date:  {s.planned_date or '-'}")
    print(f"  Target date:   {s.target_date or '-'}")
    print(f"  Achieved date: {s.achieved_date or '-'}")
    print(f"  Staff:         {s.staff_name or s.staff_id or '-'}")
    print(f"  Notes:         {s.notes or '-'}")


@_safe
def open_manager() -> None:
    logger.debug("CLI: next_steps open_manager")
    while True:
        print("\n  ── Next Steps Planning ──")
        _print_steps(data.list_steps())
        print("\n   A) Add    V) View    E) Edit    D) Delete")
        print("   F) Filter by child    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add()
        elif choice == "v":
            sid = _prompt("  Step ID: ")
            s = data.get_step(sid)
            if s is None:
                print("  No step with that ID.")
            else:
                _print_detail(s)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        elif choice == "f":
            pid = _prompt("  Child ID: ")
            _print_steps(data.list_steps(pupil_id=pid))
            _prompt("  Press Enter to continue...")
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    print("\n  ── Add Next Step ──")
    _show_children()
    pid = _prompt("  Child ID: ")
    if not pid:
        print("  Cancelled.")
        return
    fields = _collect_fields(pupil_id=pid)
    s = data.create_step(fields)
    print(f"\n  Created next step {s.step_id} for {s.child_name}.")


@_safe
def open_edit() -> None:
    sid = _prompt("  Step ID: ")
    if not sid:
        print("  Cancelled.")
        return
    existing = data.get_step(sid)
    if existing is None:
        print("  No step with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    s = data.update_step(sid, fields)
    print(f"\n  Updated next step {s.step_id}.")


@_safe
def open_delete() -> None:
    sid = _prompt("  Step ID to delete: ")
    if not sid:
        print("  Cancelled.")
        return
    if data.get_step(sid) is None:
        print("  No step with that ID.")
        return
    if _prompt(f"  Delete step {sid}? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_step(sid):
        print(f"  Deleted step {sid}.")
    else:
        print("  Could not delete (already removed?).")


_DISPATCH = {"Next Steps Planning": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching next_steps CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
