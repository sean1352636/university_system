"""CLI flow for Child Directory (Nursery System).

Provides the interactive screens behind the four "Children & Admissions"
menu labels handled here — Child Directory, Add Child, Search Children and
Child Profile — and a :func:`dispatch` hook the launcher calls for each
selected label.

Every handler is wrapped by :func:`_safe` so a domain or DB error is logged
and reported without tearing down the surrounding menu loop.
"""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.nursery.domain.learners.children import children as data
from education_system.systems.nursery.domain.learners.children import primary_transfer
from education_system.systems.nursery.domain.learners.children.children import (
    FUNDED_HOURS_OPTIONS,
    ROOMS,
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


def _print_table(rows: list[data.Child]) -> None:
    if not rows:
        print("  (no children on roll)")
        return
    print(f"  {'ID':<8} {'Name':<26} {'Room':<16} {'Funded':<20} {'Key person'}")
    print(f"  {'-'*8} {'-'*26} {'-'*16} {'-'*20} {'-'*20}")
    for c in rows:
        print(f"  {c.pupil_id:<8} {c.full_name[:26]:<26} "
              f"{(c.room or '-')[:16]:<16} {(c.funded_hours or '-')[:20]:<20} "
              f"{c.key_person_name or '-'}")


def _print_profile(c: data.Child) -> None:
    sen = f"{c.sen_status} – {c.sen_label}" if c.sen_status else "Not recorded"
    address = ", ".join(x for x in (c.address_line1, c.address_line2, c.town,
                                    c.postcode) if x)
    print(f"\n  ── Child {c.pupil_id} ──")
    print("  Identity")
    print(f"  Name:           {c.full_name}")
    print(f"  Legal name:     {c.legal_name}")
    print(f"  Preferred name: {c.preferred_name or '-'}")
    print(f"  Date of birth:  {c.date_of_birth or '-'}")
    print(f"  Gender:         {c.gender or '-'}")
    print(f"  UPN:            {c.upn or 'Not recorded'}")
    print("  Admission")
    print(f"  Start date:     {c.start_date or '-'}")
    print(f"  Roll status:    {c.roll_status_label}")
    print(f"  Status:         {c.status}")
    if c.status == "left":
        print(f"  Leaving date:   {c.left_date or '-'}")
        print(f"  Leaving reason: {c.exit_reason or '-'}")
    print("  Address")
    print(f"  Address:        {address or '-'}")
    print("  Needs")
    print(f"  SEN:            {sen}")
    print(f"  Free meals:     {'Eligible' if c.fsm_eligible else 'Not eligible'}")
    print(f"  EAL:            {'Yes' if c.eal else 'No'}")
    print(f"  Notes:          {c.notes or '-'}")
    print("  Parent / carer")
    print(f"  Parent:         {c.parent_name or '-'}")
    print(f"  Relationship:   {c.parent_relationship or '-'}")
    print(f"  Parent phone:   {c.parent_phone or '-'}")
    print(f"  Parent email:   {c.parent_email or '-'}")
    print("  Medical")
    print(f"  Medical notes:  {c.medical_notes or '-'}")
    print("  Nursery")
    print(f"  Room:           {c.room or '-'}")
    print(f"  Key person:     {c.key_person_name or c.key_person or '-'}")
    print(f"  Funded hours:   {c.funded_hours or '-'}")
    print(f"  Allergies:      {c.allergies or '-'}")


def _choose(label: str, options: list[tuple[str, str]],
            current: str | None = None, *, default: str = "") -> str:
    """A numbered choice from a fixed list. Enter keeps *current* (or takes
    *default*); '-' clears it. Returns the stored value."""
    shown = dict(options).get(current or "", current or "")
    print(f"  {label}:" + "".join(f"  {i}) {lbl}" for i, (_v, lbl) in
                                   enumerate(options, 1)))
    for _attempt in range(3):
        suffix = f" [{shown}]" if current else ""
        raw = _prompt(f"  Choose 1-{len(options)}{suffix}: ")
        if raw == "":
            return current or default
        if raw == "-":
            return ""
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1][0]
        for value, lbl in options:
            if raw.lower() in (value.lower(), lbl.lower()):
                return value
        print("  Pick a number from the list.")
    return current or default


def _yn(value: bool | None) -> str | None:
    if value is None:
        return None
    return "y" if value else "n"


def _room_options() -> list[tuple[str, str]]:
    try:
        from education_system.systems.nursery.domain.operations.rooms import rooms
        names = rooms.list_room_choices(open_only=True)
    except Exception:
        logger.exception("Could not load room choices")
        names = []
    return [(r, r) for r in dict.fromkeys([*names, *ROOMS])]


def _key_person_options() -> list[tuple[str, str]]:
    try:
        return data.list_key_person_choices()
    except Exception:
        logger.exception("Could not load key-person choices")
        return []


def _collect_fields(existing: data.Child | None = None) -> dict[str, str]:
    """The same questions as the GUI form (and the primary and secondary
    schools' Add Pupil): identity, admission, address, needs, parent/carer,
    medical — plus the nursery's room, key person, funded hours and
    allergies."""
    def cur(name: str) -> str | None:
        if existing is None:
            return None
        v = getattr(existing, name, None)
        if isinstance(v, bool):
            return _yn(v)
        return None if v is None else str(v)

    def ask(label: str, current: str | None = None) -> str:
        suffix = f" [{current}]" if current else ""
        v = _prompt(f"  {label}{suffix}: ")
        if v == "-":
            return ""
        return v if v else (current or "")

    req = "" if existing else " *"
    fields: dict[str, str] = {}
    print("  Identity")
    fields["first_name"]     = ask(f"Legal first name{req}", cur("first_name"))
    fields["middle_names"]   = ask("Middle names", cur("middle_names"))
    fields["last_name"]      = ask(f"Legal last name{req}", cur("last_name"))
    fields["preferred_name"] = ask("Preferred name", cur("preferred_name"))
    fields["date_of_birth"]  = ask(f"Date of birth (YYYY-MM-DD){req}",
                                   cur("date_of_birth"))
    fields["gender"]         = _choose(f"Gender{req}",
                                       [(g, g) for g in data.GENDERS], cur("gender"))
    fields["upn"]            = ask("UPN (13 characters, if the child has one)",
                                   cur("upn"))
    print("  Admission")
    fields["start_date"]     = ask(
        "Start (admission) date (YYYY-MM-DD"
        + (", Enter = today)" if existing is None else ")"),
        cur("start_date"))
    fields["roll_status"]    = _choose(
        "Roll status", [(k, data.ROLL_STATUS_LABELS[k]) for k in data.ROLL_STATUSES],
        cur("roll_status"), default=data.ON_ROLL)
    if fields["roll_status"] == "left":
        fields["left_date"]   = ask("Leaving date (YYYY-MM-DD)", cur("left_date"))
        fields["exit_reason"] = _choose(
            "Leaving reason", [(r, r) for r in data.LEAVING_REASONS], cur("exit_reason"))
    print("  Address")
    fields["address_line1"]  = ask("Address line 1", cur("address_line1"))
    fields["address_line2"]  = ask("Address line 2", cur("address_line2"))
    fields["town"]           = ask("Town", cur("town"))
    fields["postcode"]       = ask("Postcode", cur("postcode"))
    print("  Needs")
    fields["sen_status"]     = _choose(
        "SEN", [(k, f"{k} – {v}") for k, v in data.SEN_STATUSES.items()],
        cur("sen_status"), default="N" if existing is None else "")
    fields["fsm_eligible"]   = ask("Free school meals eligible (y/n)",
                                   cur("fsm_eligible")) or "n"
    fields["eal"]            = ask("English as an additional language (y/n)",
                                   cur("eal")) or "n"
    fields["notes"]          = ask("Notes", cur("notes"))
    print("  Parent / carer")
    fields["parent_name"]    = ask("Parent / carer name", cur("parent_name"))
    fields["parent_relationship"] = _choose(
        "Relationship", [(r, r) for r in data.PARENT_RELATIONSHIPS],
        cur("parent_relationship"))
    fields["parent_phone"]   = ask("Parent phone", cur("parent_phone"))
    fields["parent_email"]   = ask("Parent e-mail", cur("parent_email"))
    print("  Medical")
    fields["medical_notes"]  = ask("Medical / care notes", cur("medical_notes"))
    print("  Nursery")
    fields["room"]           = _choose("Room", _room_options(), cur("room"))
    people = _key_person_options()
    if people:
        fields["key_person"] = _choose("Key person", people, cur("key_person"))
    else:
        fields["key_person"] = ask("Key person (staff ID)", cur("key_person"))
    fields["funded_hours"]   = _choose(
        "Funded hours", [(o, o) for o in FUNDED_HOURS_OPTIONS if o],
        cur("funded_hours"))
    fields["allergies"]      = ask("Allergies", cur("allergies"))
    return fields


@_safe
def open_directory() -> None:
    logger.debug("CLI: open_directory")
    show_left = False
    while True:
        scope = "all (incl. leavers)" if show_left else "active"
        print(f"\n  ── Child Directory ({scope}) ──")
        try:
            rows = data.list_children(include_left=show_left)
        except Exception as e:  # noqa: BLE001
            logger.exception("Failed to load child list")
            print(f"  Could not load child list: {e}")
            return
        _print_table(rows)
        print("\n   A) Add child    V) View child    E) Edit child")
        print("   D) Delete child    T) Toggle leavers    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add_child()
        elif choice == "v":
            cid = _prompt("  Child ID: ")
            c = data.get_child(cid)
            if c is None:
                print("  No child with that ID.")
            else:
                _print_profile(c)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit_child()
        elif choice == "d":
            open_delete_child()
        elif choice == "t":
            show_left = not show_left
        else:
            print("  Invalid selection.")


@_safe
def open_add_child() -> None:
    logger.debug("CLI: open_add_child")
    print("\n  ── Add Child ──")
    print("  (* required; '-' leaves a field blank)")
    fields = _collect_fields()
    try:
        c = data.create_child(fields, complete=True, check_duplicate=True)
    except data.DuplicateChild as dup:
        answer = _prompt(f"  {dup}\n  Add this as a different child anyway? (y/N): ")
        if answer.lower() != "y":
            print("  Not saved.")
            return
        c = data.create_child(fields, complete=True)
    print(f"\n  Created child {c.pupil_id} ({c.full_name}, room {c.room or '-'}).")


@_safe
def open_edit_child() -> None:
    logger.debug("CLI: open_edit_child")
    print("\n  ── Edit Child ──")
    cid = _prompt("  Child ID: ")
    if not cid:
        print("  Cancelled.")
        return
    existing = data.get_child(cid)
    if existing is None:
        print("  No child with that ID.")
        return
    print("  Press Enter to keep the existing value, '-' to clear it.")
    fields = _collect_fields(existing)
    c = data.update_child(cid, fields)
    print(f"\n  Updated child {c.pupil_id} ({c.full_name}).")


@_safe
def open_delete_child() -> None:
    logger.debug("CLI: open_delete_child")
    print("\n  ── Delete Child ──")
    cid = _prompt("  Child ID: ")
    if not cid:
        print("  Cancelled.")
        return
    existing = data.get_child(cid)
    if existing is None:
        print("  No child with that ID.")
        return
    print("  Tip: to keep the record but take the child off roll, edit and set "
          "the roll status to Left instead.")
    confirm = _prompt(
        f"  Permanently delete {existing.full_name} ({cid})? (y/N): ").lower()
    if confirm != "y":
        print("  Cancelled.")
        return
    if data.delete_child(cid):
        print(f"  Deleted child {cid}.")
    else:
        print("  Could not delete (already removed?).")


@_safe
def open_search() -> None:
    logger.debug("CLI: open_search")
    print("\n  ── Search Children ──")
    q = _prompt("  Search (id / name / room / parent / email): ")
    rows = data.search_children(q)
    print(f"\n  {len(rows)} match(es):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def open_profile() -> None:
    logger.debug("CLI: open_profile")
    print("\n  ── Child Profile ──")
    cid = _prompt("  Child ID: ")
    if not cid:
        print("  Cancelled.")
        return
    c = data.get_child(cid)
    if c is None:
        print("  No child with that ID.")
    else:
        _print_profile(c)
    _prompt("\n  Press Enter to continue...")


@_safe
def open_move_to_primary() -> None:
    """Move a child onto the primary school roll."""
    logger.debug("CLI: open_move_to_primary")
    print("\n  ── Move to Primary School ──")
    cid = _prompt("  Child ID: ")
    if not cid:
        print("  Cancelled.")
        return
    c = data.get_child(cid)
    if c is None:
        print("  No child with that ID.")
        return
    if c.status == "left":
        print(f"  {c.full_name} ({cid}) has already left the nursery.")
        return
    groups = ", ".join(primary_transfer.primary_year_groups())
    year = _prompt(
        f"  Primary year group [{primary_transfer.DEFAULT_YEAR_GROUP}] "
        f"(one of {groups}): ") or primary_transfer.DEFAULT_YEAR_GROUP
    class_name = _prompt("  Class (optional): ")
    medical = _prompt(
        "  Parent consents to sharing allergies and medical alerts "
        "(required to move)? (y/N): ").lower() == "y"
    support = _prompt(
        "  Parent consents to sharing SEND and communication needs? (y/N): "
    ).lower() == "y"
    confirm = _prompt(
        f"  Hand {c.full_name} over to the primary school and take them off "
        f"the nursery roll? (y/N): ").lower()
    if confirm != "y":
        print("  Cancelled.")
        return
    result = primary_transfer.move_to_primary_school(
        cid, year_group=year, class_name=class_name or None,
        consent=primary_transfer.consent_for(medical=medical, support=support))
    print(f"  Moved {result.source_child_id} to primary pupil "
          f"{result.primary_pupil_id} (year {result.year_group}).")
    print(f"  School email: {result.primary_email}")
    if result.withheld:
        print("  Not shared (no consent): " + ", ".join(result.withheld))
    for warning in result.warnings:
        print(f"  ! {warning}")
    _prompt("\n  Press Enter to continue...")


# Maps the launcher menu labels (from ``menu.py``) to the handler above.
_DISPATCH = {
    "Child Directory":        open_directory,
    "Add Child":              open_add_child,
    "Search Children":        open_search,
    "Child Profile":          open_profile,
    "Move to Primary School": open_move_to_primary,
}


def dispatch(label: str) -> bool:
    """Run the handler for ``label`` if this module owns it; else return False."""
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching child CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    """Backwards-compatible entry point — opens the directory screen."""
    open_directory()
