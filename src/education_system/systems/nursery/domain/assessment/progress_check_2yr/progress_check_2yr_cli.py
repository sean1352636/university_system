"""CLI flow for 2-Year-Old Progress Check (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.nursery.domain.assessment.progress_check_2yr import (
    progress_check_2yr as data,
)
from education_system.systems.nursery.domain.assessment.progress_check_2yr.progress_check_2yr import (
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


def _yn(flag: bool) -> str:
    return "Yes" if flag else "No"


def _print_table(rows: list[data.ProgressCheck]) -> None:
    if not rows:
        print("  (no progress checks)")
        return
    print(f"  {'ID':<8} {'Child':<20} {'Date':<12} {'Age(mo)':<8} "
          f"{'Status':<12} {'Shared(P/HV)'}")
    print(f"  {'-'*8} {'-'*20} {'-'*12} {'-'*8} {'-'*12} {'-'*12}")
    for c in rows:
        shared = f"{_yn(c.shared_with_parents)[0]}/{_yn(c.shared_with_hv)[0]}"
        print(f"  {c.check_id:<8} {(c.child_name or '-')[:20]:<20} "
              f"{(c.check_date or '-'):<12} {str(c.age_months or '-'):<8} "
              f"{(c.status or '-'):<12} {shared}")


def _print_detail(c: data.ProgressCheck) -> None:
    print(f"\n  ── Progress Check {c.check_id} ──")
    print(f"  Child:                    {c.child_name or '-'} ({c.pupil_id})")
    print(f"  Check date:               {c.check_date or '-'}")
    print(f"  Age (months):             {c.age_months if c.age_months is not None else '-'}")
    print(f"  Status:                   {c.status or '-'}")
    print(f"  Staff:                    {c.staff_name or '-'}")
    print("\n  ── Prime Areas ──")
    print(f"  Communication & language: {c.comm_language or '-'}")
    print(f"  Physical development:     {c.physical_development or '-'}")
    print(f"  PSE development:          {c.pse_development or '-'}")
    print(f"\n  Summary:                  {c.summary or '-'}")
    print(f"  Strengths:                {c.strengths or '-'}")
    print(f"  Areas of concern:         {c.areas_of_concern or '-'}")
    print(f"\n  Shared with parents:      {_yn(c.shared_with_parents)}")
    print(f"  Shared with health visitor: {_yn(c.shared_with_hv)}")


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


def _collect_fields(existing: data.ProgressCheck | None = None,
                    *, pupil_id: str | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    if pupil_id is not None:
        fields["pupil_id"] = pupil_id
    fields["check_date"] = ask("Check date (YYYY-MM-DD)",
                               existing.check_date if existing else None)
    fields["age_months"] = ask("Age (months)",
                               existing.age_months if existing else None)
    fields["comm_language"] = ask("Communication & language",
                                  existing.comm_language if existing else None)
    fields["physical_development"] = ask("Physical development",
                                         existing.physical_development if existing else None)
    fields["pse_development"] = ask("Personal-social-emotional development",
                                    existing.pse_development if existing else None)
    fields["summary"] = ask("Summary", existing.summary if existing else None)
    fields["strengths"] = ask("Strengths", existing.strengths if existing else None)
    fields["areas_of_concern"] = ask("Areas of concern",
                                     existing.areas_of_concern if existing else None)
    fields["shared_with_parents"] = _ask_bool(
        "Shared with parents?",
        existing.shared_with_parents if existing else False)
    fields["shared_with_hv"] = _ask_bool(
        "Shared with health visitor?",
        existing.shared_with_hv if existing else False)
    fields["staff_id"] = ask("Staff ID", existing.staff_id if existing else None)
    fields["status"] = ask(f"Status ({'/'.join(STATUSES)})",
                           existing.status if existing else "draft")
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: progress_check_2yr open_manager")
    while True:
        print("\n  ── 2-Year-Old Progress Check ──")
        _print_table(data.list_checks())
        print("\n   A) Add    V) View    E) Edit    D) Delete    F) Filter by child    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add()
        elif choice == "v":
            cid = _prompt("  Check ID: ")
            c = data.get_check(cid)
            if c is None:
                print("  No check with that ID.")
            else:
                _print_detail(c)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        elif choice == "f":
            pid = _prompt("  Child ID: ")
            _print_table(data.list_checks(pupil_id=pid))
            _prompt("  Press Enter to continue...")
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    print("\n  ── Add 2-Year-Old Progress Check ──")
    _show_children()
    pid = _prompt("  Child ID: ")
    if not pid:
        print("  Cancelled.")
        return
    fields = _collect_fields(pupil_id=pid)
    c = data.create_check(fields)
    print(f"\n  Added progress check {c.check_id} for "
          f"{c.child_name or pid}.")


@_safe
def open_edit() -> None:
    cid = _prompt("  Check ID: ")
    if not cid:
        print("  Cancelled.")
        return
    existing = data.get_check(cid)
    if existing is None:
        print("  No check with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    c = data.update_check(cid, fields)
    print(f"\n  Updated progress check {c.check_id}.")


@_safe
def open_delete() -> None:
    cid = _prompt("  Check ID to delete: ")
    if not cid:
        print("  Cancelled.")
        return
    existing = data.get_check(cid)
    if existing is None:
        print("  No check with that ID.")
        return
    if _prompt(f"  Delete check {cid} for {existing.child_name or existing.pupil_id}? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_check(cid):
        print(f"  Deleted progress check {cid}.")
    else:
        print("  Could not delete (already removed?).")


_DISPATCH = {"2-Year-Old Progress Check": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching progress_check_2yr CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
