"""CLI flow for Admissions & Waiting List (Nursery System).

Provides the interactive manager behind the "Admissions & Waiting List" menu
label and a :func:`dispatch` hook the launcher calls for it. The manager shows
the live waiting list in priority order and offers the offer/accept/decline/
withdraw transitions plus a hand-off to Registration & Enrolment.

Every handler is wrapped by :func:`_safe` so a domain or DB error is logged and
reported without tearing down the surrounding menu loop.
"""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.nursery_system.modules.domain.admissions import admissions as data
from education_system.nursery_system.modules.domain.admissions.admissions import (
    FUNDED_HOURS_OPTIONS,
    PRIORITIES,
    ValidationError,
)

logger = logging.getLogger(__name__)


def _prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _safe(func: Callable[..., None]) -> Callable[..., None]:
    """Catch unexpected errors in a CLI handler — log and keep the menu alive."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            print(f"  Validation error: {e}")
        except Exception as e:  # noqa: BLE001 - last-resort guard for the menu
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _room_choices() -> list[str]:
    try:
        from education_system.nursery_system.modules.domain.rooms import rooms
        return rooms.list_room_choices()
    except Exception:
        logger.exception("Could not load room choices for admissions")
        return []


def _print_table(rows: list[data.Application]) -> None:
    if not rows:
        print("  (no applications)")
        return
    print(f"  {'ID':<9} {'Child':<24} {'Room':<16} {'Priority':<13} "
          f"{'Applied':<12} {'Status'}")
    print(f"  {'-'*9} {'-'*24} {'-'*16} {'-'*13} {'-'*12} {'-'*9}")
    for a in rows:
        print(f"  {a.application_id:<9} {a.child_name[:24]:<24} "
              f"{(a.requested_room or '-')[:16]:<16} {a.priority:<13} "
              f"{(a.date_applied or '-'):<12} {a.status}")


def _print_detail(a: data.Application) -> None:
    print(f"\n  ── Application {a.application_id} ──")
    print(f"  Child:           {a.child_name}")
    print(f"  Date of birth:   {a.date_of_birth or '-'}")
    print(f"  Parent / carer:  {a.parent_name or '-'}")
    print(f"  Parent phone:    {a.parent_phone or '-'}")
    print(f"  Parent email:    {a.parent_email or '-'}")
    print(f"  Requested room:  {a.requested_room or '-'}")
    print(f"  Requested start: {a.requested_start or '-'}")
    print(f"  Funded hours:    {a.funded_hours or '-'}")
    print(f"  Days required:   {a.days_required or '-'}")
    print(f"  Priority:        {a.priority}")
    print(f"  Applied:         {a.date_applied or '-'}")
    print(f"  Status:          {a.status}")
    print(f"  Offer date:      {a.offer_date or '-'}")
    print(f"  Linked child:    {a.pupil_id or '-'}")
    print(f"  Notes:           {a.notes or '-'}")


def _collect_fields(existing: data.Application | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    rooms = _room_choices()
    fields: dict[str, str] = {}
    fields["child_first_name"] = ask("Child first name",
                                     existing.child_first_name if existing else None)
    fields["child_last_name"]  = ask("Child last name",
                                     existing.child_last_name if existing else None)
    fields["date_of_birth"]    = ask("Date of birth (YYYY-MM-DD)",
                                     existing.date_of_birth if existing else None)
    fields["parent_name"]      = ask("Parent / carer name",
                                     existing.parent_name if existing else None)
    fields["parent_phone"]     = ask("Parent phone",
                                     existing.parent_phone if existing else None)
    fields["parent_email"]     = ask("Parent email",
                                     existing.parent_email if existing else None)
    if rooms:
        print("  Rooms: " + ", ".join(rooms))
    fields["requested_room"]   = ask("Requested room",
                                     existing.requested_room if existing else None)
    fields["requested_start"]  = ask("Requested start date (YYYY-MM-DD)",
                                     existing.requested_start if existing else None)
    funded = [o for o in FUNDED_HOURS_OPTIONS if o]
    fields["funded_hours"]     = ask(f"Funded hours ({'/'.join(funded)})",
                                     existing.funded_hours if existing else None)
    fields["days_required"]    = ask("Days required (e.g. Mon,Tue,Wed)",
                                     existing.days_required if existing else None)
    fields["date_applied"]     = ask("Application date (YYYY-MM-DD)",
                                     existing.date_applied if existing else None)
    fields["priority"]         = ask(f"Priority ({'/'.join(PRIORITIES)})",
                                     existing.priority if existing else "standard")
    fields["notes"]            = ask("Notes", existing.notes if existing else None)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: admissions open_manager")
    show_all = False
    while True:
        scope = "all applications" if show_all else "waiting list (live)"
        print(f"\n  ── Admissions & Waiting List ({scope}) ──")
        try:
            rows = (data.list_applications() if show_all
                    else data.list_waiting_list())
            counts = data.counts_by_status()
        except Exception as e:  # noqa: BLE001
            logger.exception("Failed to load applications")
            print(f"  Could not load applications: {e}")
            return
        _print_table(rows)
        if counts:
            print("\n  Totals: " + "  ".join(
                f"{k}={v}" for k, v in sorted(counts.items())))
        print("\n   A) Add    V) View    E) Edit    D) Delete")
        print("   O) Offer place    K) Accept offer    X) Decline    W) Withdraw")
        print("   N) Enrol accepted child    T) Toggle all/waiting    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add()
        elif choice == "v":
            aid = _prompt("  Application ID: ")
            a = data.get_application(aid)
            if a is None:
                print("  No application with that ID.")
            else:
                _print_detail(a)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        elif choice == "o":
            _transition("offer a place to", lambda aid: data.offer_place(aid))
        elif choice == "k":
            _transition("accept the offer for", lambda aid: data.accept_offer(aid))
        elif choice == "x":
            _transition("decline", lambda aid: data.decline(aid))
        elif choice == "w":
            _transition("withdraw", lambda aid: data.withdraw(aid))
        elif choice == "n":
            open_enrol()
        elif choice == "t":
            show_all = not show_all
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    logger.debug("CLI: admissions open_add")
    print("\n  ── New Application ──")
    fields = _collect_fields()
    a = data.create_application(fields)
    print(f"\n  Created application {a.application_id} for {a.child_name} "
          f"(priority {a.priority}).")


@_safe
def open_edit() -> None:
    logger.debug("CLI: admissions open_edit")
    print("\n  ── Edit Application ──")
    aid = _prompt("  Application ID: ")
    if not aid:
        print("  Cancelled.")
        return
    existing = data.get_application(aid)
    if existing is None:
        print("  No application with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    a = data.update_application(aid, fields)
    print(f"\n  Updated application {a.application_id} ({a.child_name}).")


@_safe
def open_delete() -> None:
    logger.debug("CLI: admissions open_delete")
    aid = _prompt("  Application ID to delete: ")
    if not aid:
        print("  Cancelled.")
        return
    existing = data.get_application(aid)
    if existing is None:
        print("  No application with that ID.")
        return
    confirm = _prompt(
        f"  Permanently delete the application for {existing.child_name} "
        f"({aid})? (y/N): ").lower()
    if confirm != "y":
        print("  Cancelled.")
        return
    if data.delete_application(aid):
        print(f"  Deleted application {aid}.")
    else:
        print("  Could not delete (already removed?).")


@_safe
def _transition(verb: str, action: Callable[[str], data.Application]) -> None:
    aid = _prompt(f"  Application ID to {verb}: ")
    if not aid:
        print("  Cancelled.")
        return
    existing = data.get_application(aid)
    if existing is None:
        print("  No application with that ID.")
        return
    a = action(aid)
    print(f"  {a.child_name} ({a.application_id}) is now '{a.status}'.")


@_safe
def open_enrol() -> None:
    """Hand an accepted application off to Registration & Enrolment."""
    logger.debug("CLI: admissions open_enrol")
    aid = _prompt("  Accepted application ID to enrol: ")
    if not aid:
        print("  Cancelled.")
        return
    existing = data.get_application(aid)
    if existing is None:
        print("  No application with that ID.")
        return
    if existing.status not in ("accepted", "offered", "waiting"):
        print(f"  Application is '{existing.status}' — cannot enrol it.")
        return
    if existing.status != "accepted":
        cont = _prompt("  Offer not accepted yet — enrol anyway? (y/N): ").lower()
        if cont != "y":
            print("  Cancelled.")
            return
    from education_system.nursery_system.modules.domain.enrolment import enrolment_cli
    enrolment_cli.enrol_from_application_cli(aid)


# Maps the launcher menu label (from ``menu.py``) to the manager handler.
_DISPATCH = {
    "Admissions & Waiting List": open_manager,
}


def dispatch(label: str) -> bool:
    """Run the handler for ``label`` if this module owns it; else return False."""
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching admissions CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    """Backwards-compatible entry point — opens the admissions manager."""
    open_manager()
