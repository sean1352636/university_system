"""CLI flows for Secondary School Parent / Guardian Contacts."""

from __future__ import annotations

import logging
from typing import Any, Callable
from education_system.secondarysch_system.modules.domain.staff_comms.parent_contacts import parent_contacts
from education_system.secondarysch_system.modules.domain.staff_comms.parent_contacts import parent_contacts as data
from education_system.secondarysch_system.modules.domain.pastoral import _pupils_bridge as student_data
from education_system.secondarysch_system.modules.domain.staff_comms.parent_contacts.parent_contacts import (
    Contact,
    DEFAULT_LANGUAGE,
    DEFAULT_PREFERRED_METHOD,
    DEFAULT_RELATIONSHIP,
    LANGUAGES,
    PREFERRED_CONTACT_METHODS,
    RELATIONSHIPS,
    ValidationError,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


# ── Prompt helpers ─────────────────────────────────────────────────

def _input(prompt: str, *, default: str = "",
            allow_empty: bool = True) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    s = raw.strip()
    if s.lower() == "cancel":
        raise _UserAbort
    if not s:
        if default:
            return default
        if not allow_empty:
            print("    Value is required.")
            return _input(prompt, default=default, allow_empty=False)
        return ""
    return s


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _pick_from(label: str, options: list[str],
                default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}", default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number (or 'cancel' to abort).")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _yes_no(prompt: str, default: bool = False) -> bool:
    raw = _input(f"{prompt} (y/n)", default="y" if default else "n")
    return raw.lower() in ("y", "yes")


def _pick_student() -> str:
    students = student_data.list_students()
    if not students:
        print("    No students.")
        raise _UserAbort
    print("\n  Students:")
    for i, s in enumerate(students, 1):
        print(f"    {i:>3}) {s.student_id}  {s.full_name}")
    while True:
        raw = _input(f"  Pick #1..{len(students)} (or student ID)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(students):
                return students[n - 1].student_id
            continue
        match = next((s for s in students
                       if s.student_id.lower() == raw.lower()), None)
        if match:
            return match.student_id
        print("    No matching student.")


# ── Print helpers ──────────────────────────────────────────────────

def _print_rows(rows: list[Contact]) -> None:
    if not rows:
        print("\n  (no contacts)")
        return
    names = {s.student_id: s.full_name
              for s in student_data.list_students()}
    print()
    print(f"  {'#':>4}  {'Student':<10}  {'Student name':<22}  "
          f"{'Contact':<24}  {'Rel.':<12}  {'Flags':<8}  Phone / Email")
    print("  " + "-" * 116)
    for c in rows:
        flags = "".join([
            "P" if c.is_primary else "-",
            "E" if c.is_emergency_contact else "-",
            "C" if c.receives_communications else "-",
            "L" if c.lives_with_student else "-",
        ])
        contact_full = c.full_name[:24]
        sn = names.get(c.student_id, "?")[:22]
        contact_info = c.primary_phone or c.email or "—"
        print(f"  {c.contact_id:>4}  {c.student_id:<10}  {sn:<22}  "
              f"{contact_full:<24}  {c.relationship[:12]:<12}  "
              f"{flags:<8}  {contact_info}")
    print(f"\n  {len(rows)} contact(s). "
          f"(Flags: P=Primary E=Emergency C=Comms L=LivesWith)")


# ── Flows ──────────────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ Parent Contacts ═══")
    _print_rows(data.list_contacts())
    _row_action_loop()


def filter_contacts() -> None:
    print("\n═══ Filter Contacts ═══")
    print("  (blank to skip; 'cancel' to abort)\n")
    try:
        sid = _input("Student ID") or None
        rel = _input("Relationship") or None
        primary = _yes_no("Primary only?", default=False)
        emergency = _yes_no("Emergency only?", default=False)
        receives = _yes_no("Receives comms only?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_contacts(
            student_id=sid, relationship=rel,
            primary_only=primary, emergency_only=emergency,
            receives_only=receives,
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_rows(rows)
    _row_action_loop()


def search_contacts() -> None:
    print("\n═══ Search Contacts ═══")
    try:
        q = _input("Query", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_rows(data.search_contacts(q))
    _row_action_loop()


def per_student() -> None:
    print("\n═══ Per-Student Contacts ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    student = student_data.get_student(sid)
    print(f"\n  {student.student_id}  {student.full_name}")
    _print_rows(data.contacts_for_student(sid))
    _row_action_loop()


def view_contact(contact_id: int | None = None) -> None:
    print("\n═══ View Contact ═══")
    try:
        cid = contact_id if contact_id is not None else int(
            _input("Contact ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    c = data.get_contact(cid)
    if c is None:
        print(f"  ✗ No contact #{cid}")
        _pause()
        return
    print()
    print(f"    Contact ID     : #{c.contact_id}")
    print(f"    Student        : {c.student_id}")
    print(f"    Relationship   : {c.relationship}")
    print(f"    Name           : {c.full_name}")
    print(f"    Email          : {c.email or '—'}")
    print(f"    Primary phone  : {c.primary_phone or '—'}")
    print(f"    Secondary phone: {c.secondary_phone or '—'}")
    print(f"    Address        : {c.address or '—'}")
    print(f"    Preferred via  : {c.preferred_method}")
    print(f"    Language       : {c.preferred_language}")
    print(f"    Primary?       : {'Yes' if c.is_primary else 'No'}")
    print(f"    Emergency?     : "
          f"{'Yes' if c.is_emergency_contact else 'No'}")
    print(f"    Parental resp. : "
          f"{'Yes' if c.has_parental_responsibility else 'No'}")
    print(f"    Receives comms : "
          f"{'Yes' if c.receives_communications else 'No'}")
    print(f"    Lives with     : "
          f"{'Yes' if c.lives_with_student else 'No'}")
    if c.notes:
        print("\n    Notes:")
        for line in c.notes.splitlines() or [""]:
            print(f"      {line}")
    _pause()


def _collect_form(existing: Contact | None) -> dict[str, Any]:
    is_edit = existing is not None
    p: dict[str, Any] = {}
    if is_edit:
        print(f"\n  Editing contact #{existing.contact_id} "
              f"for {existing.student_id}")
        p["student_id"] = existing.student_id
    else:
        print("\n  ── Student ──")
        p["student_id"] = _pick_student()

    p["relationship"] = _pick_from(
        "Relationship", list(RELATIONSHIPS),
        default=(existing.relationship if is_edit else DEFAULT_RELATIONSHIP))
    p["title"] = _input(
        "Title (Mr/Mrs/Ms/Dr/…)",
        default=(existing.title or "") if is_edit else "")
    p["first_name"] = _input(
        "First name",
        default=existing.first_name if is_edit else "",
        allow_empty=False)
    p["last_name"] = _input(
        "Last name",
        default=existing.last_name if is_edit else "",
        allow_empty=False)
    p["email"] = _input(
        "Email",
        default=(existing.email or "") if is_edit else "")
    p["primary_phone"] = _input(
        "Primary phone",
        default=(existing.primary_phone or "") if is_edit else "")
    p["secondary_phone"] = _input(
        "Secondary phone",
        default=(existing.secondary_phone or "") if is_edit else "")
    p["address"] = _input(
        "Address (single line)",
        default=(existing.address or "") if is_edit else "")
    p["preferred_method"] = _pick_from(
        "Preferred contact method", list(PREFERRED_CONTACT_METHODS),
        default=(existing.preferred_method
                  if is_edit else DEFAULT_PREFERRED_METHOD))
    p["preferred_language"] = _pick_from(
        "Preferred language", list(LANGUAGES),
        default=(existing.preferred_language
                  if is_edit else DEFAULT_LANGUAGE))
    p["is_primary"] = _yes_no(
        "Primary contact?",
        default=existing.is_primary if is_edit else False)
    p["is_emergency_contact"] = _yes_no(
        "Emergency contact?",
        default=existing.is_emergency_contact if is_edit else True)
    p["has_parental_responsibility"] = _yes_no(
        "Has parental responsibility?",
        default=existing.has_parental_responsibility
                if is_edit else True)
    p["receives_communications"] = _yes_no(
        "Receives school communications?",
        default=existing.receives_communications
                if is_edit else True)
    p["lives_with_student"] = _yes_no(
        "Lives with student?",
        default=existing.lives_with_student if is_edit else True)
    p["notes"] = _input(
        "Notes (single line)",
        default=(existing.notes or "") if is_edit else "")
    return p


def new_contact() -> None:
    print("\n═══ New Contact ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        c = data.create_contact(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created contact #{c.contact_id} "
          f"({c.full_name}, {c.relationship})")
    _pause()


def edit_contact(contact_id: int | None = None) -> None:
    print("\n═══ Edit Contact ═══")
    try:
        cid = contact_id if contact_id is not None else int(
            _input("Contact ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_contact(cid)
    if existing is None:
        print(f"  ✗ No contact #{cid}")
        _pause()
        return
    try:
        payload = _collect_form(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_contact(cid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{cid}")
    _pause()


def make_primary_flow(contact_id: int | None = None) -> None:
    print("\n═══ Make Primary ═══")
    try:
        cid = contact_id if contact_id is not None else int(
            _input("Contact ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_contact(cid) is None:
        print(f"  ✗ No contact #{cid}")
        _pause()
        return
    try:
        c = data.set_primary(cid)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{cid} is now primary for {c.student_id}")
    _pause()


def delete_contact_flow(contact_id: int | None = None) -> None:
    print("\n═══ Delete Contact ═══")
    try:
        cid = contact_id if contact_id is not None else int(
            _input("Contact ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_contact(cid)
    if existing is None:
        print(f"  ✗ No contact #{cid}")
        _pause()
        return
    if _input(f"Delete contact #{cid} ({existing.full_name})? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_contact(cid):
        print(f"\n  ✓ Deleted #{cid}")
    _pause()


def summary() -> None:
    print("\n═══ Parent Contacts Summary ═══")
    summ = data.summary()
    print(f"\n  Total contacts             : {summ.total}")
    print(f"  Students with a contact    : "
          f"{summ.students_with_contact}")
    print(f"  Receives school comms      : "
          f"{summ.receives_communications}")
    print("\n  Data gaps:")
    print(f"    Students with no contact     : "
          f"{len(summ.students_without_contact)}")
    if summ.students_without_contact[:10]:
        print(f"      e.g. "
              f"{', '.join(summ.students_without_contact[:10])}")
    print(f"    Students without primary      : "
          f"{len(summ.students_without_primary)}")
    print(f"    Students without emergency    : "
          f"{len(summ.students_without_emergency)}")
    print(f"    Contacts missing email        : {summ.no_email}")
    print(f"    Contacts missing phone        : {summ.no_phone}")
    print("\n  By relationship:")
    for r in RELATIONSHIPS:
        n = summ.by_relationship.get(r, 0)
        if n:
            print(f"    {r:<18} : {n}")
    print("\n  By preferred method:")
    for m in PREFERRED_CONTACT_METHODS:
        n = summ.by_preferred_method.get(m, 0)
        if n:
            print(f"    {m:<18} : {n}")
    print("\n  By language:")
    for lang in LANGUAGES:
        n = summ.by_language.get(lang, 0)
        if n:
            print(f"    {lang:<18} : {n}")
    _pause()


# ── Row-action loop ───────────────────────────────────────────────

def _row_action_loop() -> None:
    print()
    print("  Actions:  V) View   E) Edit   P) Make Primary   "
          "D) Delete   (Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in ("v", "e", "p", "d"):
            print("    Pick V, E, P, D, or Enter.")
            continue
        try:
            raw = _input("Contact ID", allow_empty=False)
        except _UserAbort:
            return
        try:
            cid = int(raw)
        except ValueError:
            print("    Contact ID must be a whole number.")
            continue
        if choice == "v":
            view_contact(cid)
        elif choice == "e":
            edit_contact(cid)
        elif choice == "p":
            make_primary_flow(cid)
        elif choice == "d":
            delete_contact_flow(cid)
        return


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List All Contacts",   list_all),
    ("Filter Contacts",     filter_contacts),
    ("Search",              search_contacts),
    ("Per-Student",         per_student),
    ("View Contact",        view_contact),
    ("New Contact",         new_contact),
    ("Edit Contact",        edit_contact),
    ("Make Primary",        make_primary_flow),
    ("Delete Contact",      delete_contact_flow),
    ("Summary",             summary),
]


def run() -> None:
    while True:
        print("\n── Parent Contacts ──")
        for i, (label, _) in enumerate(_MENU, 1):
            print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(_MENU)):
            print("  Invalid selection.")
            continue
        _, handler = _MENU[int(choice) - 1]
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Parent-contacts CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Parent Contacts":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Parent-contacts CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
