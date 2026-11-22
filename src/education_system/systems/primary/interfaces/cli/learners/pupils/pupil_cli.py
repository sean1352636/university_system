"""CLI handlers for pupil CRUD in the Primary School System."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.primary.domain.learners.pupils import pupils as data
from education_system.systems.primary.domain.learners.pupils.pupils import (
    ValidationError, YEAR_GROUPS,
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
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _print_table(rows: list[data.Pupil]) -> None:
    if not rows:
        print("  (no pupils)")
        return
    print(f"  {'ID':<10} {'Year':<4} {'Class':<8} {'Name':<28} {'Parent'}")
    print(f"  {'-'*10} {'-'*4} {'-'*8} {'-'*28} {'-'*20}")
    for p in rows:
        print(f"  {p.pupil_id:<10} {p.year_group:<4} "
              f"{(p.class_name or '-'):<8} {p.full_name[:28]:<28} "
              f"{p.parent_name or '-'}")


def _print_profile(p: data.Pupil) -> None:
    sen = f"{p.sen_status} \u2013 {p.sen_label}" if p.sen_status else "Not recorded"
    address = ", ".join(x for x in (p.address_line1, p.address_line2, p.town,
                                    p.postcode) if x)
    print(f"\n  ── Pupil {p.pupil_id} ──")
    print("  Identity")
    print(f"  Name:           {p.full_name}")
    print(f"  Legal name:     {p.legal_name}")
    print(f"  Preferred name: {p.preferred_name or '-'}")
    print(f"  Date of birth:  {p.date_of_birth or '-'}")
    print(f"  Gender:         {p.gender or '-'}")
    print(f"  UPN:            {p.upn or 'Not recorded'}")
    print(f"  Email:          {p.email}")
    print("  School")
    print(f"  Year group:     {p.year_group}")
    print(f"  Class:          {p.class_name or '-'}")
    print(f"  Admission date: {p.admission_date or '-'}")
    print(f"  Roll status:    {p.roll_status_label}")
    if p.roll_status == "left":
        print(f"  Leaving date:   {p.left_date or '-'}")
        print(f"  Leaving reason: {p.exit_reason or '-'}")
    print("  Address")
    print(f"  Address:        {address or '-'}")
    print("  Needs")
    print(f"  SEN:            {sen}")
    print(f"  SEND:           {p.send_status or '-'}")
    print(f"  Free meals:     {'Eligible' if p.fsm_eligible else 'Not eligible'}")
    print(f"  EAL:            {'Yes' if p.eal else 'No'}")
    print(f"  Notes:          {p.notes or '-'}")
    print("  Parent / carer")
    print(f"  Parent:         {p.parent_name or '-'}")
    print(f"  Relationship:   {p.parent_relationship or '-'}")
    print(f"  Parent phone:   {p.parent_phone or '-'}")
    print(f"  Parent e-mail:  {p.parent_email or '-'}")
    print("  Medical")
    print(f"  Medical notes:  {p.medical_notes or '-'}")


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


def _collect_fields(existing: data.Pupil | None = None) -> dict[str, str]:
    """The same questions as the GUI form (and the secondary school's Add
    Pupil): identity, school, address, needs, parent/carer, medical."""
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
    fields["upn"]            = ask("UPN (13 characters)", cur("upn"))
    print("  School")
    fields["year_group"]     = ask(f"Year group ({'/'.join(YEAR_GROUPS)}){req}",
                                   cur("year_group"))
    fields["class_name"]     = ask("Class", cur("class_name"))
    fields["admission_date"] = ask(
        "Admission date (YYYY-MM-DD" + (", Enter = today)" if existing is None else ")"),
        cur("admission_date"))
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
        "SEN", [(k, f"{k} \u2013 {v}") for k, v in data.SEN_STATUSES.items()],
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
    return fields


@_safe
def open_directory() -> None:
    logger.debug("CLI: open_directory")
    while True:
        print("\n  ── Pupil Directory ──")
        try:
            rows = data.list_pupils()
        except Exception as e:
            logger.exception("Failed to load pupil list")
            print(f"  Could not load pupil list: {e}")
            return
        _print_table(rows)
        print("\n   A) Add pupil   V) View pupil   E) Edit pupil   D) Delete pupil")
        print("   0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add_pupil()
        elif choice == "v":
            pid = _prompt("  Pupil ID: ")
            p = data.get_pupil(pid)
            if p is None:
                print("  No pupil with that ID.")
            else:
                _print_profile(p)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit_pupil()
        elif choice == "d":
            open_delete_pupil()
        else:
            print("  Invalid selection.")


@_safe
def open_add_pupil() -> None:
    logger.debug("CLI: open_add_pupil")
    print("\n  ── Add Pupil ──")
    print("  (* required; '-' leaves a field blank)")
    fields = _collect_fields()
    try:
        p = data.create_pupil(fields, complete=True, check_duplicate=True)
    except data.DuplicatePupil as dup:
        answer = _prompt(f"  {dup}\n  Add this as a different pupil anyway? (y/N): ")
        if answer.lower() != "y":
            print("  Not saved.")
            return
        p = data.create_pupil(fields, complete=True)
    print(f"\n  Created pupil {p.pupil_id} ({p.full_name}, year {p.year_group})")
    print(f"  Auto-generated school email: {p.email}")


@_safe
def open_edit_pupil() -> None:
    logger.debug("CLI: open_edit_pupil")
    print("\n  ── Edit Pupil ──")
    pid = _prompt("  Pupil ID: ")
    if not pid:
        print("  Cancelled.")
        return
    existing = data.get_pupil(pid)
    if existing is None:
        print("  No pupil with that ID.")
        return
    print("  Press Enter to keep existing value, '-' to clear it.")
    fields = _collect_fields(existing)
    p = data.update_pupil(pid, fields)
    print(f"\n  Updated pupil {p.pupil_id} ({p.full_name})")


@_safe
def open_delete_pupil() -> None:
    logger.debug("CLI: open_delete_pupil")
    print("\n  ── Delete Pupil ──")
    pid = _prompt("  Pupil ID: ")
    if not pid:
        print("  Cancelled.")
        return
    existing = data.get_pupil(pid)
    if existing is None:
        print("  No pupil with that ID.")
        return
    confirm = _prompt(f"  Delete {existing.full_name} ({pid})? (y/N): ").lower()
    if confirm != "y":
        print("  Cancelled.")
        return
    if data.delete_pupil(pid):
        print(f"  Deleted pupil {pid}.")
    else:
        print("  Could not delete (already removed?).")


@_safe
def open_search() -> None:
    logger.debug("CLI: open_search")
    print("\n  ── Search Pupils ──")
    q = _prompt("  Search (id / name / class / email): ")
    rows = data.search_pupils(q)
    print(f"\n  {len(rows)} match(es):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def open_profile() -> None:
    logger.debug("CLI: open_profile")
    print("\n  ── Pupil Profile ──")
    pid = _prompt("  Pupil ID: ")
    if not pid:
        print("  Cancelled.")
        return
    p = data.get_pupil(pid)
    if p is None:
        print("  No pupil with that ID.")
    else:
        _print_profile(p)
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {
    "Pupil Directory": open_directory,
    "Add Pupil":       open_add_pupil,
    "Search Pupils":   open_search,
    "Pupil Profile":   open_profile,
}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching pupil CLI label: %s", label)
    handler()
    return True
