"""CLI flow for Registration & Enrolment (Nursery System).

Provides the interactive manager behind the "Registration & Enrolment" menu
label and a :func:`dispatch` hook the launcher calls for it. The manager lists
current enrolments and offers: register a brand-new child, enrol an accepted
admission, edit / withdraw an enrolment.

It also exposes :func:`enrol_from_application_cli`, which the Admissions screen
calls to convert an accepted application into an on-roll child.

Every handler is wrapped by :func:`_safe` so a domain or DB error is logged and
reported without tearing down the surrounding menu loop.
"""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.nursery.domain.admissions.enrolment import enrolment as data
from education_system.systems.nursery.domain.admissions.enrolment.enrolment import (
    CONSENT_FIELDS,
    STATUSES,
    ValidationError,
)

logger = logging.getLogger(__name__)


def _prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _ask_yes_no(label: str, current: bool | None = None) -> str:
    cur = "" if current is None else ("y" if current else "n")
    suffix = f" [{cur}]" if cur else " (y/N)"
    v = _prompt(f"  {label}{suffix}: ").lower()
    if not v:
        return cur
    return "y" if v in ("y", "yes", "1", "true") else "n"


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
        from education_system.systems.nursery.domain.operations.rooms import rooms
        return rooms.list_room_choices()
    except Exception:
        logger.exception("Could not load room choices for enrolment")
        return []


def _funded_options() -> list[str]:
    from education_system.systems.nursery.domain.learners.children.children import (
        FUNDED_HOURS_OPTIONS,
    )
    return [o for o in FUNDED_HOURS_OPTIONS if o]


def _print_table(rows: list[data.Enrolment]) -> None:
    if not rows:
        print("  (no enrolments)")
        return
    print(f"  {'ID':<8} {'Child':<24} {'Pupil':<8} {'Room':<16} "
          f"{'Start':<12} {'Status'}")
    print(f"  {'-'*8} {'-'*24} {'-'*8} {'-'*16} {'-'*12} {'-'*9}")
    for e in rows:
        name = e.child_name or "-"
        print(f"  {e.enrolment_id:<8} {name[:24]:<24} {e.pupil_id:<8} "
              f"{(e.room or '-')[:16]:<16} {(e.start_date or '-'):<12} {e.status}")


def _consent_line(e: data.Enrolment) -> str:
    bits = []
    for key, label in CONSENT_FIELDS:
        bits.append(f"{label.split(' ')[0]}={'Y' if getattr(e, key) else 'N'}")
    return ", ".join(bits)


def _print_detail(e: data.Enrolment) -> None:
    print(f"\n  ── Enrolment {e.enrolment_id} ──")
    print(f"  Child:              {e.child_name or '-'} ({e.pupil_id})")
    print(f"  From application:   {e.application_id or '-'}")
    print(f"  Room:               {e.room or '-'}")
    print(f"  Start date:         {e.start_date or '-'}")
    print(f"  Funded hours:       {e.funded_hours or '-'}")
    print(f"  Weekly sessions:    {e.weekly_sessions or '-'}")
    print(f"  Registration date:  {e.registration_date or '-'}")
    print(f"  Contract signed:    {'Yes' if e.contract_signed else 'No'}")
    print(f"  Consents:           {_consent_line(e)}")
    print(f"  Emergency contact:  {e.emergency_contact_name or '-'} "
          f"({e.emergency_contact_phone or '-'})")
    print(f"  Status:             {e.status}")
    print(f"  Notes:              {e.notes or '-'}")


def _collect_registration(existing: data.Enrolment | None = None,
                          *, with_room: bool = True) -> dict[str, str]:
    """Collect the registration / consent fields shared by all enrol flows."""
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    if with_room:
        rooms = _room_choices()
        if rooms:
            print("  Rooms: " + ", ".join(rooms))
        fields["room"] = ask("Room", existing.room if existing else None)
        funded = _funded_options()
        fields["funded_hours"] = ask(f"Funded hours ({'/'.join(funded)})",
                                     existing.funded_hours if existing else None)
        fields["start_date"] = ask("Start date (YYYY-MM-DD)",
                                   existing.start_date if existing else None)
    fields["weekly_sessions"] = ask("Weekly sessions (e.g. Mon,Tue,Wed)",
                                    existing.weekly_sessions if existing else None)
    fields["registration_date"] = ask("Registration date (YYYY-MM-DD)",
                                      existing.registration_date if existing else None)
    fields["contract_signed"] = _ask_yes_no(
        "Contract signed?", existing.contract_signed if existing else None)
    for key, label in CONSENT_FIELDS:
        fields[key] = _ask_yes_no(
            label, getattr(existing, key) if existing else None)
    fields["emergency_contact_name"] = ask(
        "Emergency contact name",
        existing.emergency_contact_name if existing else None)
    fields["emergency_contact_phone"] = ask(
        "Emergency contact phone",
        existing.emergency_contact_phone if existing else None)
    fields["notes"] = ask("Notes", existing.notes if existing else None)
    if existing is not None:
        fields["status"] = ask(f"Status ({'/'.join(STATUSES)})", existing.status)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: enrolment open_manager")
    show_withdrawn = True
    while True:
        scope = "all" if show_withdrawn else "current only"
        print(f"\n  ── Registration & Enrolment ({scope}) ──")
        try:
            rows = data.list_enrolments(include_withdrawn=show_withdrawn)
        except Exception as e:  # noqa: BLE001
            logger.exception("Failed to load enrolments")
            print(f"  Could not load enrolments: {e}")
            return
        _print_table(rows)
        print("\n   R) Register new child    F) Enrol accepted application")
        print("   V) View    E) Edit    W) Withdraw    D) Delete")
        print("   T) Toggle withdrawn    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "r":
            open_register_new()
        elif choice == "f":
            open_enrol_application()
        elif choice == "v":
            eid = _prompt("  Enrolment ID: ")
            e = data.get_enrolment(eid)
            if e is None:
                print("  No enrolment with that ID.")
            else:
                _print_detail(e)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "w":
            open_withdraw()
        elif choice == "d":
            open_delete()
        elif choice == "t":
            show_withdrawn = not show_withdrawn
        else:
            print("  Invalid selection.")


@_safe
def open_register_new() -> None:
    """Register a brand-new child: collect child details + registration."""
    logger.debug("CLI: enrolment open_register_new")
    print("\n  ── Register New Child ──")
    print("  Child details:")

    def ask(label: str) -> str:
        return _prompt(f"  {label}: ")

    child = {
        "first_name": ask("First name"),
        "last_name": ask("Last name"),
        "date_of_birth": ask("Date of birth (YYYY-MM-DD)"),
        "parent_name": ask("Parent / carer name"),
        "parent_phone": ask("Parent phone"),
        "parent_email": ask("Parent email"),
    }
    print("\n  Registration details:")
    reg = _collect_registration()
    # Child inherits room / funded hours / start from the registration block.
    child["room"] = reg.get("room", "")
    child["funded_hours"] = reg.get("funded_hours", "")
    child["start_date"] = reg.get("start_date", "")

    enr = data.enrol_child(child, reg)
    print(f"\n  Registered {enr.child_name} as child {enr.pupil_id} "
          f"(enrolment {enr.enrolment_id}).")


@_safe
def open_enrol_application() -> None:
    aid = _prompt("  Accepted application ID to enrol: ")
    if not aid:
        print("  Cancelled.")
        return
    enrol_from_application_cli(aid)


@_safe
def enrol_from_application_cli(application_id: str) -> None:
    """Convert an accepted admission — invoked here or from the Admissions screen."""
    logger.debug("CLI: enrol_from_application_cli(%s)", application_id)
    from education_system.systems.nursery.domain.admissions import admissions
    app = admissions.get_application(application_id)
    if app is None:
        print("  No application with that ID.")
        return
    print(f"\n  Enrolling {app.child_name} (application {application_id}).")
    print("  The child record will be created from the application details.")
    print("  Add the registration / consent details (Enter to skip):")
    reg = _collect_registration(with_room=True)
    overrides = {k: v for k, v in reg.items() if v != ""}
    enr = data.enrol_from_application(application_id, overrides)
    print(f"\n  Enrolled {enr.child_name} as child {enr.pupil_id} "
          f"(enrolment {enr.enrolment_id}). Application marked enrolled.")


@_safe
def open_edit() -> None:
    logger.debug("CLI: enrolment open_edit")
    eid = _prompt("  Enrolment ID: ")
    if not eid:
        print("  Cancelled.")
        return
    existing = data.get_enrolment(eid)
    if existing is None:
        print("  No enrolment with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_registration(existing)
    enr = data.update_enrolment(eid, fields)
    print(f"\n  Updated enrolment {enr.enrolment_id}.")


@_safe
def open_withdraw() -> None:
    logger.debug("CLI: enrolment open_withdraw")
    eid = _prompt("  Enrolment ID to withdraw: ")
    if not eid:
        print("  Cancelled.")
        return
    existing = data.get_enrolment(eid)
    if existing is None:
        print("  No enrolment with that ID.")
        return
    off = _prompt(
        f"  Withdraw {existing.child_name or existing.pupil_id} and take them "
        "off roll? (y/N): ").lower()
    if off not in ("y", "n", ""):
        print("  Cancelled.")
        return
    take_off = off == "y"
    enr = data.withdraw(eid, take_off_roll=take_off)
    print(f"  Enrolment {enr.enrolment_id} withdrawn"
          + (" and child taken off roll." if take_off else "."))


@_safe
def open_delete() -> None:
    logger.debug("CLI: enrolment open_delete")
    eid = _prompt("  Enrolment ID to delete: ")
    if not eid:
        print("  Cancelled.")
        return
    existing = data.get_enrolment(eid)
    if existing is None:
        print("  No enrolment with that ID.")
        return
    print("  Note: this removes the registration record only, not the child.")
    confirm = _prompt(
        f"  Permanently delete enrolment {eid}? (y/N): ").lower()
    if confirm != "y":
        print("  Cancelled.")
        return
    if data.delete_enrolment(eid):
        print(f"  Deleted enrolment {eid}.")
    else:
        print("  Could not delete (already removed?).")


# Maps the launcher menu label (from ``menu.py``) to the manager handler.
_DISPATCH = {
    "Registration & Enrolment": open_manager,
}


def dispatch(label: str) -> bool:
    """Run the handler for ``label`` if this module owns it; else return False."""
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching enrolment CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    """Backwards-compatible entry point — opens the enrolment manager."""
    open_manager()
