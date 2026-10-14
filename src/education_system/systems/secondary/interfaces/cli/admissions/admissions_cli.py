"""CLI handlers for admissions in the Secondary School System."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.secondary.domain.admissions import (
    admissions as data,
)
from education_system.systems.secondary.domain.admissions.admissions import (
    STATUSES,
)
from education_system.systems.secondary.domain.learners.pupils.pupils import (
    ValidationError, YEAR_GROUPS,
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
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _print_table(rows: list[data.Application]) -> None:
    if not rows:
        print("  (no applications)")
        return
    print(f"  {'ID':<10} {'Date':<10} {'Year':<4} {'Name':<28} "
          f"{'Status':<10} {'Pupil':<10}")
    print(f"  {'-'*10} {'-'*10} {'-'*4} {'-'*28} {'-'*10} {'-'*10}")
    for a in rows:
        print(f"  {a.application_id:<10} {(a.application_date or '-'):<10} "
              f"{a.year_applying:<4} {a.applicant_name[:28]:<28} "
              f"{a.status:<10} {(a.pupil_id or '-'):<10}")


def _print_detail(a: data.Application) -> None:
    print(f"\n  ── Application {a.application_id} ──")
    print(f"  Applicant:       {a.applicant_name}")
    print(f"  Date of birth:   {a.date_of_birth or '-'}")
    print(f"  Year applying:   {a.year_applying}")
    print(f"  Applied on:      {a.application_date or '-'}")
    print(f"  Status:          {a.status}")
    print(f"  Pupil ID:        {a.pupil_id or '-'}")
    print(f"  Parent:          {a.parent_name or '-'}")
    print(f"  Parent phone:    {a.parent_phone or '-'}")
    print(f"  Parent email:    {a.parent_email or '-'}")
    print(f"  Notes:           {a.notes or '-'}")


def _collect_fields(existing: data.Application | None = None) -> dict[str, str]:
    def ask(label: str, current: str | None = None) -> str:
        suffix = f" [{current}]" if current else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (current or "")
    f: dict[str, str] = {}
    f["applicant_first"] = ask("First name",
                               existing.applicant_first if existing else None)
    f["applicant_last"]  = ask("Last name",
                               existing.applicant_last  if existing else None)
    f["date_of_birth"]   = ask("Date of birth (YYYY-MM-DD)",
                               existing.date_of_birth   if existing else None)
    f["year_applying"]   = ask(
        f"Year applying ({'/'.join(YEAR_GROUPS)})",
        existing.year_applying if existing else None,
    )
    f["parent_name"]  = ask("Parent name",
                            existing.parent_name  if existing else None)
    f["parent_phone"] = ask("Parent phone",
                            existing.parent_phone if existing else None)
    f["parent_email"] = ask("Parent email",
                            existing.parent_email if existing else None)
    f["notes"]        = ask("Notes",
                            existing.notes        if existing else None)
    return f


@_safe
def open_admissions() -> None:
    logger.debug("CLI: open_admissions")
    while True:
        counts = data.status_counts()
        total = sum(counts.values())
        print("\n  ── Admissions ──")
        print(f"  Total: {total}   "
              + "   ".join(f"{s}: {counts[s]}" for s in STATUSES))
        print("\n   1) New application")
        print("   2) List applications")
        print("   3) View application")
        print("   4) Edit application")
        print("   5) Set status")
        print("   6) Enrol accepted application")
        print("   7) Delete application")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice == "0" or choice == "":
            return
        actions = {
            "1": _new_application,
            "2": _list_applications,
            "3": _view_application,
            "4": _edit_application,
            "5": _set_status,
            "6": _enrol_application,
            "7": _delete_application,
        }
        action = actions.get(choice)
        if action is None:
            print("  Invalid selection.")
            continue
        action()


@_safe
def _new_application() -> None:
    logger.debug("CLI: admissions new application")
    print("\n  ── New Application ──")
    fields = _collect_fields()
    a = data.create_application(fields)
    print(f"\n  Created application {a.application_id} for "
          f"{a.applicant_name} (year {a.year_applying})")


@_safe
def _list_applications() -> None:
    logger.debug("CLI: admissions list")
    print("\n  ── List Applications ──")
    print(f"  Filter by status ({'/'.join(STATUSES)}) — blank for all.")
    status = _prompt("  Status: ") or None
    rows = data.list_applications(status=status)
    print(f"\n  {len(rows)} application(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _view_application() -> None:
    aid = _prompt("  Application ID: ")
    if not aid:
        return
    a = data.get_application(aid)
    if a is None:
        print("  No application with that ID.")
        return
    _print_detail(a)
    _prompt("\n  Press Enter to continue...")


@_safe
def _edit_application() -> None:
    aid = _prompt("  Application ID: ")
    if not aid:
        return
    existing = data.get_application(aid)
    if existing is None:
        print("  No application with that ID.")
        return
    print("  Press Enter to keep existing value.")
    fields = _collect_fields(existing)
    a = data.update_application(aid, fields)
    print(f"\n  Updated application {a.application_id} ({a.applicant_name})")


@_safe
def _set_status() -> None:
    aid = _prompt("  Application ID: ")
    if not aid:
        return
    a = data.get_application(aid)
    if a is None:
        print("  No application with that ID.")
        return
    print(f"  Current status: {a.status}")
    print(f"  Allowed: {', '.join(STATUSES)}")
    new = _prompt("  New status: ")
    if not new:
        return
    a = data.set_status(aid, new)
    print(f"  Status now: {a.status}")


@_safe
def _enrol_application() -> None:
    aid = _prompt("  Application ID to enrol: ")
    if not aid:
        return
    a, pupil = data.enrol_application(aid)
    print(f"\n  Enrolled application {a.application_id} as pupil "
          f"{pupil.pupil_id} ({pupil.full_name}, year {pupil.year_group})")
    print(f"  Auto-generated school email: {pupil.email}")


@_safe
def _delete_application() -> None:
    aid = _prompt("  Application ID: ")
    if not aid:
        return
    existing = data.get_application(aid)
    if existing is None:
        print("  No application with that ID.")
        return
    confirm = _prompt(
        f"  Delete application {aid} ({existing.applicant_name})? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_application(aid):
        print(f"  Deleted application {aid}.")
    else:
        print("  Could not delete.")


_DISPATCH = {"Admissions": open_admissions}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching admissions CLI label: %s", label)
    handler()
    return True
