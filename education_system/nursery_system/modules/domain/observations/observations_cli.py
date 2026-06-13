"""CLI flow for Observations (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.nursery_system.modules.domain.observations import (
    observations as data,
)
from education_system.nursery_system.modules.domain.observations.observations import (
    AREAS,
    OBS_TYPES,
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


def _print_observations(rows: list[data.Observation]) -> None:
    if not rows:
        print("  (no observations)")
        return
    print(f"  {'ID':<8} {'Child':<22} {'Date':<12} {'Type':<14} "
          f"{'Area':<34} {'Title'}")
    print(f"  {'-'*8} {'-'*22} {'-'*12} {'-'*14} {'-'*34} {'-'*24}")
    for ob in rows:
        print(f"  {ob.observation_id:<8} {(ob.child_name or '-')[:22]:<22} "
              f"{(ob.observation_date or '-'):<12} "
              f"{(ob.observation_type or '-')[:14]:<14} "
              f"{(ob.area or '-')[:34]:<34} "
              f"{(ob.title or '-')[:24]}")


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


def _collect_fields(existing: data.Observation | None = None,
                    *, pupil_id: str | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    if pupil_id is not None:
        fields["pupil_id"] = pupil_id
    fields["title"]            = ask("Title (required)",
                                     existing.title if existing else None)
    fields["observation_date"] = ask("Observation date (YYYY-MM-DD)",
                                     existing.observation_date if existing else None)
    fields["observation_type"] = ask(f"Type ({'/'.join(OBS_TYPES)})",
                                     existing.observation_type if existing else None)
    fields["area"]             = ask(f"EYFS area ({'/'.join(AREAS)})",
                                     existing.area if existing else None)
    fields["description"]      = ask("Description",
                                     existing.description if existing else None)
    fields["context"]          = ask("Context",
                                     existing.context if existing else None)
    fields["next_step"]        = ask("Next step",
                                     existing.next_step if existing else None)
    _show_staff()
    fields["staff_id"]         = ask("Observer (staff ID)",
                                     existing.staff_id if existing else None)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: observations open_manager")
    while True:
        print("\n  ── Observations ──")
        _print_observations(data.list_observations())
        print("\n   A) Add    V) View    E) Edit    D) Delete    F) Filter by child    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add()
        elif choice == "v":
            oid = _prompt("  Observation ID: ")
            ob = data.get_observation(oid)
            if ob is None:
                print("  No observation with that ID.")
            else:
                _print_detail(ob)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        elif choice == "f":
            pid = _prompt("  Child ID: ")
            _print_observations(data.list_observations(pupil_id=pid))
            _prompt("  Press Enter to continue...")
        else:
            print("  Invalid selection.")


def _print_detail(ob: data.Observation) -> None:
    print(f"\n  ── Observation {ob.observation_id} ──")
    print(f"  Child:       {ob.child_name or '-'} ({ob.pupil_id})")
    print(f"  Date:        {ob.observation_date or '-'}")
    print(f"  Type:        {ob.observation_type or '-'}")
    print(f"  Area:        {ob.area or '-'}")
    print(f"  Title:       {ob.title or '-'}")
    print(f"  Description: {ob.description or '-'}")
    print(f"  Context:     {ob.context or '-'}")
    print(f"  Next step:   {ob.next_step or '-'}")
    print(f"  Observer:    {ob.staff_name or ob.staff_id or '-'}")


@_safe
def open_add() -> None:
    print("\n  ── Add Observation ──")
    _show_children()
    pid = _prompt("  Child ID: ")
    if not pid:
        print("  Cancelled.")
        return
    fields = _collect_fields(pupil_id=pid)
    ob = data.create_observation(fields)
    print(f"\n  Logged observation {ob.observation_id} for {ob.child_name}.")


@_safe
def open_edit() -> None:
    oid = _prompt("  Observation ID: ")
    if not oid:
        print("  Cancelled.")
        return
    existing = data.get_observation(oid)
    if existing is None:
        print("  No observation with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    ob = data.update_observation(oid, fields)
    print(f"\n  Updated observation {ob.observation_id}.")


@_safe
def open_delete() -> None:
    oid = _prompt("  Observation ID to delete: ")
    if not oid:
        print("  Cancelled.")
        return
    if data.get_observation(oid) is None:
        print("  No observation with that ID.")
        return
    if _prompt(f"  Delete observation {oid}? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_observation(oid):
        print(f"  Deleted observation {oid}.")
    else:
        print("  Could not delete (already removed?).")


_DISPATCH = {"Observations": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching observations CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
