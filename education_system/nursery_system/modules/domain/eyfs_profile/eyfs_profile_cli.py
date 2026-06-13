"""CLI flow for EYFS Profile (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.nursery_system.modules.domain.eyfs_profile import (
    eyfs_profile as data,
)
from education_system.nursery_system.modules.domain.eyfs_profile.eyfs_profile import (
    AREA_FIELDS,
    AREA_LABELS,
    BANDS,
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


def _print_table(rows: list[data.EyfsProfile]) -> None:
    if not rows:
        print("  (no EYFS profiles)")
        return
    print(f"  {'ID':<8} {'Child':<22} {'Date':<12} {'Term':<14} "
          f"{'Status':<10} {'Assessor'}")
    print(f"  {'-'*8} {'-'*22} {'-'*12} {'-'*14} {'-'*10} {'-'*20}")
    for p in rows:
        print(f"  {p.profile_id:<8} {(p.child_name or '-')[:22]:<22} "
              f"{(p.assessment_date or '-'):<12} {(p.term or '-')[:14]:<14} "
              f"{(p.status or '-')[:10]:<10} {p.assessor_name or '-'}")


def _print_detail(p: data.EyfsProfile) -> None:
    print(f"\n  ── EYFS Profile {p.profile_id} ──")
    print(f"  Child:                   {p.child_name or '-'} ({p.pupil_id})")
    print(f"  Assessment date:         {p.assessment_date or '-'}")
    print(f"  Term:                    {p.term or '-'}")
    print(f"  Status:                  {p.status or '-'}")
    print(f"  Assessor:                {p.assessor_name or '-'}")
    print(f"  Summary:                 {p.summary or '-'}")
    print()
    print("  EYFS Area Judgements:")
    for field in AREA_FIELDS:
        label = AREA_LABELS[field]
        value = getattr(p, field) or "-"
        print(f"    {label:<34} {value}")


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


def _collect_fields(existing: data.EyfsProfile | None = None,
                    *, pupil_id: str | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    if pupil_id is not None:
        fields["pupil_id"] = pupil_id

    fields["assessment_date"] = ask(
        "Assessment date (YYYY-MM-DD)",
        existing.assessment_date if existing else None)
    fields["term"] = ask("Term", existing.term if existing else None)

    print(f"  Bands: {', '.join(BANDS)} (leave blank to clear)")
    for field in AREA_FIELDS:
        fields[field] = ask(
            AREA_LABELS[field],
            getattr(existing, field) if existing else None)

    fields["summary"] = ask("Summary", existing.summary if existing else None)

    _show_staff()
    fields["assessor"] = ask("Assessor ID", existing.assessor if existing else None)

    fields["status"] = ask(
        f"Status ({'/'.join(STATUSES)})",
        existing.status if existing else "draft")
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: eyfs_profile open_manager")
    while True:
        print("\n  ── EYFS Profile ──")
        _print_table(data.list_profiles())
        print("\n   A) Add    V) View    E) Edit    D) Delete    C) Filter by child    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add()
        elif choice == "v":
            pid = _prompt("  Profile ID: ")
            p = data.get_profile(pid)
            if p is None:
                print("  No profile with that ID.")
            else:
                _print_detail(p)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        elif choice == "c":
            child_id = _prompt("  Child ID: ")
            _print_table(data.list_profiles(pupil_id=child_id))
            _prompt("  Press Enter to continue...")
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    print("\n  ── Add EYFS Profile ──")
    _show_children()
    child_id = _prompt("  Child ID: ")
    if not child_id:
        print("  Cancelled.")
        return
    fields = _collect_fields(pupil_id=child_id)
    p = data.create_profile(fields)
    print(f"\n  Added EYFS profile {p.profile_id} for {p.child_name or child_id}.")


@_safe
def open_edit() -> None:
    pid = _prompt("  Profile ID: ")
    if not pid:
        print("  Cancelled.")
        return
    existing = data.get_profile(pid)
    if existing is None:
        print("  No profile with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    p = data.update_profile(pid, fields)
    print(f"\n  Updated EYFS profile {p.profile_id}.")


@_safe
def open_delete() -> None:
    pid = _prompt("  Profile ID to delete: ")
    if not pid:
        print("  Cancelled.")
        return
    existing = data.get_profile(pid)
    if existing is None:
        print("  No profile with that ID.")
        return
    if _prompt(f"  Delete profile {pid} for {existing.child_name}? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_profile(pid):
        print(f"  Deleted profile {pid}.")
    else:
        print("  Could not delete (already removed?).")


_DISPATCH = {"EYFS Profile": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching eyfs_profile CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
