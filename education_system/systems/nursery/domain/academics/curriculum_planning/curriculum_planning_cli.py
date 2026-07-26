"""CLI flow for Activity & Curriculum Planning (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.nursery.domain.academics.curriculum_planning import (
    curriculum_planning as data,
)
from education_system.systems.nursery.domain.academics.curriculum_planning.curriculum_planning import (
    AREAS,
    ROOMS,
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


def _print_table(rows: list[data.CurriculumPlan]) -> None:
    if not rows:
        print("  (no plans)")
        return
    print(f"  {'ID':<8} {'Title':<30} {'Date':<12} {'Room':<18} {'Area':<30} {'Status':<10}")
    print(f"  {'-'*8} {'-'*30} {'-'*12} {'-'*18} {'-'*30} {'-'*10}")
    for p in rows:
        print(f"  {p.plan_id:<8} {p.title[:30]:<30} "
              f"{(p.plan_date or '-'):<12} "
              f"{(p.room or '-')[:18]:<18} "
              f"{(p.area or '-')[:30]:<30} "
              f"{p.status:<10}")


def _print_detail(p: data.CurriculumPlan) -> None:
    print(f"\n  ── Plan {p.plan_id} ──")
    print(f"  Title:              {p.title}")
    print(f"  Date:               {p.plan_date or '-'}")
    print(f"  Room:               {p.room or '-'}")
    print(f"  Area:               {p.area or '-'}")
    print(f"  Theme:              {p.theme or '-'}")
    print(f"  Learning intention: {p.learning_intention or '-'}")
    print(f"  Activities:         {p.activities or '-'}")
    print(f"  Resources:          {p.resources or '-'}")
    print(f"  Planned by:         {p.staff_name or p.staff_id or '-'}")
    print(f"  Status:             {p.status}")


def _collect_fields(existing: data.CurriculumPlan | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    fields["title"]              = ask("Title",
                                       existing.title if existing else None)
    fields["plan_date"]          = ask("Plan date (YYYY-MM-DD, optional)",
                                       existing.plan_date if existing else None)
    print(f"  Rooms: {', '.join(ROOMS)}")
    fields["room"]               = ask("Room (optional)",
                                       existing.room if existing else None)
    print(f"  Areas: {', '.join(AREAS)}")
    fields["area"]               = ask("Area (optional)",
                                       existing.area if existing else None)
    fields["theme"]              = ask("Theme (optional)",
                                       existing.theme if existing else None)
    fields["learning_intention"] = ask("Learning intention (optional)",
                                       existing.learning_intention if existing else None)
    fields["activities"]         = ask("Activities (optional)",
                                       existing.activities if existing else None)
    fields["resources"]          = ask("Resources (optional)",
                                       existing.resources if existing else None)
    # Staff — show list then ask for ID
    try:
        staff = data.list_staff_choices()
    except Exception:
        staff = []
    if staff:
        print("  Staff:")
        for sid, lbl in staff:
            print(f"    {lbl}")
    fields["staff_id"] = ask("Planned by (staff ID, optional)",
                             existing.staff_id if existing else None)
    print(f"  Statuses: {', '.join(STATUSES)}")
    fields["status"] = ask("Status",
                           existing.status if existing else "planned")
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: curriculum_planning open_manager")
    while True:
        print("\n  ── Activity & Curriculum Planning ──")
        _print_table(data.list_plans())
        print("\n   A) Add    V) View    E) Edit    D) Delete    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add()
        elif choice == "v":
            pid = _prompt("  Plan ID: ")
            p = data.get_plan(pid)
            if p is None:
                print("  No plan with that ID.")
            else:
                _print_detail(p)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    print("\n  ── Add Plan ──")
    fields = _collect_fields()
    p = data.create_plan(fields)
    print(f"\n  Added plan {p.plan_id} — {p.title}.")


@_safe
def open_edit() -> None:
    pid = _prompt("  Plan ID: ")
    if not pid:
        print("  Cancelled.")
        return
    existing = data.get_plan(pid)
    if existing is None:
        print("  No plan with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    p = data.update_plan(pid, fields)
    print(f"\n  Updated plan {p.plan_id}.")


@_safe
def open_delete() -> None:
    pid = _prompt("  Plan ID to delete: ")
    if not pid:
        print("  Cancelled.")
        return
    existing = data.get_plan(pid)
    if existing is None:
        print("  No plan with that ID.")
        return
    if _prompt(f"  Delete '{existing.title}' ({pid})? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_plan(pid):
        print(f"  Deleted plan {pid}.")
    else:
        print("  Could not delete (already removed?).")


_DISPATCH = {"Activity & Curriculum Planning": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching curriculum_planning CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
