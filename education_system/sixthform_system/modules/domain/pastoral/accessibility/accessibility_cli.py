"""CLI flows for Sixth Form Accessibility (SEND + accommodations)."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.pastoral.accessibility import (
    accessibility as data,
)
from education_system.sixthform_system.modules.domain.students.students import (
    students as student_data,
)
from education_system.sixthform_system.modules.domain.pastoral.accessibility.accessibility import (
    Accommodation,
    ACCOMMODATION_CATEGORIES,
    ACCOMMODATION_STATUSES,
    COMMON_ACCOMMODATIONS,
    DEFAULT_ACCOMMODATION_CATEGORY,
    DEFAULT_ACCOMMODATION_STATUS,
    DEFAULT_SEND_STATUS,
    PRIMARY_NEEDS,
    Profile,
    SEND_STATUSES,
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


def _yes_no(prompt: str, *, default: bool = False) -> bool:
    raw = _input(f"{prompt} (y/n)",
                  default="y" if default else "n").strip().lower()
    return raw in ("y", "yes")


def _pick_from(label: str, options: list[str],
                default: str | None = None,
                allow_custom: bool = False) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    if allow_custom:
        print("        (or type a custom value)")
    while True:
        raw = _input(f"  Pick #1..{len(options)}",
                      default=default or "")
        if default and raw == default:
            return default
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(options):
                return options[n - 1]
            print("    Out of range.")
            continue
        if allow_custom and raw:
            return raw
        print("    Enter a number (or 'cancel' to abort).")


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


def _pick_profile() -> Profile:
    profiles = data.list_profiles()
    if not profiles:
        print("    No accessibility profiles yet.")
        raise _UserAbort
    names = {s.student_id: s.full_name
              for s in student_data.list_students()}
    print("\n  Profiles:")
    for i, p in enumerate(profiles, 1):
        print(f"    {i:>3}) #{p.profile_id}  {p.student_id}  "
              f"{names.get(p.student_id, '?')[:24]:<24}  "
              f"[{p.send_status}]")
    while True:
        raw = _input(f"  Pick #1..{len(profiles)} (or profile id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(profiles):
                return profiles[n - 1]
            match = next((p for p in profiles
                           if p.profile_id == n), None)
            if match:
                return match
        print("    No matching profile.")


# ── Print helpers ──────────────────────────────────────────────────

def _print_profiles(rows: list[Profile]) -> None:
    if not rows:
        print("\n  (no profiles)")
        return
    names = {s.student_id: s.full_name
              for s in student_data.list_students()}
    print()
    print(f"  {'#':>4}  {'Student':<10}  {'Name':<22}  "
          f"{'Status':<12}  {'Need':<28}  {'Review due':<12}")
    print("  " + "-" * 100)
    for p in rows:
        print(f"  {p.profile_id:>4}  {p.student_id:<10}  "
              f"{names.get(p.student_id, '?')[:22]:<22}  "
              f"{p.send_status:<12}  "
              f"{(p.primary_need or '—')[:28]:<28}  "
              f"{p.next_review_due or '—':<12}")
    print(f"\n  {len(rows)} profile(s).")


def _print_accomms(rows: list[Accommodation]) -> None:
    if not rows:
        print("\n  (no accommodations)")
        return
    names = {s.student_id: s.full_name
              for s in student_data.list_students()}
    print()
    print(f"  {'#':>4}  {'Student':<10}  {'Name':<26}  "
          f"{'Category':<22}  {'Status':<10}  Range")
    print("  " + "-" * 100)
    for a in rows:
        rng = f"{a.start_date or '—'}..{a.end_date or '—'}"
        print(f"  {a.accommodation_id:>4}  {a.student_id:<10}  "
              f"{a.name[:26]:<26}  {a.category[:22]:<22}  "
              f"{a.status:<10}  {rng}")
        _ = names  # quieter linters
    print(f"\n  {len(rows)} accommodation(s).")


# ── Profile flows ──────────────────────────────────────────────────

def list_all_profiles() -> None:
    print("\n═══ Accessibility Profiles ═══")
    _print_profiles(data.list_profiles())
    _pause()


def list_ehcp() -> None:
    print("\n═══ EHCP Students ═══")
    _print_profiles(data.list_profiles(ehcp_only=True))
    _pause()


def review_overdue() -> None:
    print("\n═══ Review Overdue ═══")
    rows = data.list_profiles(review_overdue=True)
    _print_profiles(rows)
    _pause()


def view_profile() -> None:
    print("\n═══ View Profile ═══")
    try:
        p = _pick_profile()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    student = student_data.get_student(p.student_id)
    name = student.full_name if student else "(unknown)"
    accs = data.accommodations_for_student(p.student_id)

    print()
    print(f"    Profile        : #{p.profile_id}")
    print(f"    Student        : {p.student_id}  {name}")
    print(f"    SEND status    : {p.send_status}")
    print(f"    EHCP           : "
          f"{'yes' if p.has_ehcp else 'no'}"
          f"{f'  ({p.ehcp_reference})' if p.ehcp_reference else ''}")
    print(f"    Primary need   : {p.primary_need or '—'}")
    if p.secondary_needs:
        print(f"    Secondary      : {p.secondary_needs}")
    if p.diagnoses:
        print(f"    Diagnoses      : {p.diagnoses}")
    if p.mobility_aids:
        print(f"    Mobility aids  : {p.mobility_aids}")
    print(f"    PEEP required  : "
          f"{'yes' if p.requires_pep else 'no'}")
    if p.fire_evac_notes:
        print(f"    Fire/evac      : {p.fire_evac_notes}")
    print(f"    Last reviewed  : {p.last_reviewed or '—'}")
    print(f"    Next review    : {p.next_review_due or '—'}")
    print(f"    Reviewer       : {p.reviewer or '—'}")
    if p.notes:
        print("\n    Notes:")
        for line in p.notes.splitlines():
            print(f"      {line}")
    print()
    print(f"    Accommodations: {len(accs)} "
          f"(active: {sum(1 for a in accs if a.is_current)})")
    for a in accs:
        flag = "●" if a.is_current else "○"
        print(f"      {flag} #{a.accommodation_id} "
              f"[{a.category}] {a.name}  ({a.status})")
    _pause()


def _collect_profile_form(student_id: str | None,
                           existing: Profile | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    if is_edit:
        payload["student_id"] = existing.student_id
        print(f"\n  Editing profile for {existing.student_id}")
    else:
        payload["student_id"] = student_id or _pick_student()

    payload["send_status"] = _pick_from(
        "SEND status", list(SEND_STATUSES),
        default=(existing.send_status if is_edit else DEFAULT_SEND_STATUS))
    if payload["send_status"] == "EHCP":
        payload["has_ehcp"] = True
    else:
        payload["has_ehcp"] = _yes_no(
            "Has EHCP?",
            default=(existing.has_ehcp if is_edit else False))
    payload["ehcp_reference"] = _input(
        "EHCP reference",
        default=(existing.ehcp_reference or "") if is_edit else "")
    payload["primary_need"] = _pick_from(
        "Primary area of need", [""] + list(PRIMARY_NEEDS),
        default=(existing.primary_need if is_edit else ""),
        allow_custom=False)
    payload["secondary_needs"] = _input(
        "Secondary needs",
        default=(existing.secondary_needs or "") if is_edit else "")
    payload["diagnoses"] = _input(
        "Diagnoses",
        default=(existing.diagnoses or "") if is_edit else "")
    payload["mobility_aids"] = _input(
        "Mobility aids",
        default=(existing.mobility_aids or "") if is_edit else "")
    payload["requires_pep"] = _yes_no(
        "Requires PEEP (personal emergency evacuation plan)?",
        default=(existing.requires_pep if is_edit else False))
    payload["fire_evac_notes"] = _input(
        "Fire / evac notes",
        default=(existing.fire_evac_notes or "") if is_edit else "")
    payload["last_reviewed"] = _input(
        "Last reviewed (YYYY-MM-DD)",
        default=(existing.last_reviewed
                  if is_edit and existing.last_reviewed
                  else _date.today().isoformat()))
    payload["next_review_due"] = _input(
        "Next review due (YYYY-MM-DD)",
        default=(existing.next_review_due
                  if is_edit and existing.next_review_due else ""))
    payload["reviewer"] = _input(
        "Reviewer",
        default=(existing.reviewer or "") if is_edit else "")
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_profile() -> None:
    print("\n═══ New Accessibility Profile ═══")
    try:
        sid = _pick_student()
        if data.get_profile_for_student(sid):
            print(f"\n  {sid} already has a profile — editing instead.")
            existing = data.get_profile_for_student(sid)
            assert existing is not None
            payload = _collect_profile_form(sid, existing)
            data.update_profile(existing.profile_id, payload)
            print(f"\n  ✓ Updated profile #{existing.profile_id}")
            _pause()
            return
        payload = _collect_profile_form(sid, None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        p = data.create_profile(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created profile #{p.profile_id} for {p.student_id}")
    _pause()


def edit_profile() -> None:
    print("\n═══ Edit Profile ═══")
    try:
        p = _pick_profile()
        payload = _collect_profile_form(p.student_id, p)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_profile(p.profile_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated profile #{p.profile_id}")
    _pause()


def mark_reviewed_flow() -> None:
    print("\n═══ Mark Reviewed ═══")
    try:
        p = _pick_profile()
        reviewer = _input("Reviewer",
                            default=(p.reviewer or ""))
        date_str = _input("Review date",
                           default=_date.today().isoformat())
        next_due = _input("Next review due (optional)",
                            default=(p.next_review_due or ""))
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.mark_reviewed(p.profile_id,
                            reviewer=reviewer or None,
                            review_date=date_str,
                            next_review_due=next_due or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{p.profile_id} reviewed.")
    _pause()


def delete_profile_flow() -> None:
    print("\n═══ Delete Profile ═══")
    try:
        p = _pick_profile()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete profile #{p.profile_id} for {p.student_id}? "
              f"Accommodations are kept. Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_profile(p.profile_id):
        print(f"\n  ✓ Deleted profile #{p.profile_id}")
    _pause()


# ── Accommodation flows ────────────────────────────────────────────

def list_all_accomms() -> None:
    print("\n═══ Accommodations ═══")
    _print_accomms(data.list_accommodations())
    _pause()


def list_active_accomms() -> None:
    print("\n═══ Active Accommodations ═══")
    _print_accomms(data.list_accommodations(active_only=True))
    _pause()


def exam_access_list() -> None:
    print("\n═══ Exam Access Arrangements (JCQ) ═══")
    rows = data.exam_access_arrangements(active_only=True)
    if not rows:
        print("\n  (none active)")
        _pause()
        return
    print()
    print(f"  {'Student':<10}  {'Name':<24}  {'Arrangement':<32}  "
          f"{'Approved by':<18}  {'Approved':<10}")
    print("  " + "-" * 100)
    for r in rows:
        a = r.accommodation
        print(f"  {a.student_id:<10}  "
              f"{r.student_name[:24]:<24}  "
              f"{a.name[:32]:<32}  "
              f"{(a.approved_by or '—')[:18]:<18}  "
              f"{a.approved_date or '—':<10}")
    print(f"\n  {len(rows)} active exam-access arrangement(s).")
    _pause()


def per_student_accomms() -> None:
    print("\n═══ Per-Student Accommodations ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    student = student_data.get_student(sid)
    print(f"\n  {sid}  {student.full_name}")
    _print_accomms(data.accommodations_for_student(sid))
    _pause()


def filter_accomms() -> None:
    print("\n═══ Filter Accommodations ═══")
    print("  (blank to skip; 'cancel' to abort)\n")
    try:
        sid = _input("Student ID") or None
        cat = _input(f"Category ({'/'.join(ACCOMMODATION_CATEGORIES)})") or None
        status = _input(f"Status ({'/'.join(ACCOMMODATION_STATUSES)})") or None
        name = _input("Name contains") or None
        active_raw = _input("Active only? (y/n)", default="n")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    active_only = active_raw.lower() in ("y", "yes")
    try:
        rows = data.list_accommodations(
            student_id=sid, category=cat, status=status,
            name_like=name, active_only=active_only)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_accomms(rows)
    _pause()


def _collect_accomm_form(student_id: str | None,
                          existing: Accommodation | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    if is_edit:
        payload["student_id"] = existing.student_id
        print(f"\n  Editing accommodation #{existing.accommodation_id} "
              f"for {existing.student_id}")
    else:
        payload["student_id"] = student_id or _pick_student()

    payload["category"] = _pick_from(
        "Category", list(ACCOMMODATION_CATEGORIES),
        default=(existing.category if is_edit
                  else DEFAULT_ACCOMMODATION_CATEGORY))
    payload["name"] = _pick_from(
        "Name", list(COMMON_ACCOMMODATIONS),
        default=(existing.name if is_edit else COMMON_ACCOMMODATIONS[0]),
        allow_custom=True)
    payload["description"] = _input(
        "Description",
        default=(existing.description or "") if is_edit else "")
    payload["status"] = _pick_from(
        "Status", list(ACCOMMODATION_STATUSES),
        default=(existing.status if is_edit
                  else DEFAULT_ACCOMMODATION_STATUS))
    payload["start_date"] = _input(
        "Start date",
        default=(existing.start_date if is_edit and existing.start_date
                  else _date.today().isoformat()))
    payload["end_date"] = _input(
        "End date (optional)",
        default=(existing.end_date or "") if is_edit else "")
    payload["approved_by"] = _input(
        "Approved by",
        default=(existing.approved_by or "") if is_edit else "")
    payload["approved_date"] = _input(
        "Approved date",
        default=(existing.approved_date or "") if is_edit else "")
    payload["evidence"] = _input(
        "Evidence (filename / reference)",
        default=(existing.evidence or "") if is_edit else "")
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_accomm() -> None:
    print("\n═══ New Accommodation ═══")
    try:
        payload = _collect_accomm_form(None, None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        a = data.create_accommodation(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created accommodation #{a.accommodation_id} "
          f"({a.category}: {a.name})")
    _pause()


def edit_accomm() -> None:
    print("\n═══ Edit Accommodation ═══")
    try:
        aid = int(_input("Accommodation ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_accommodation(aid)
    if existing is None:
        print(f"  ✗ No accommodation #{aid}")
        _pause()
        return
    try:
        payload = _collect_accomm_form(existing.student_id, existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_accommodation(aid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated accommodation #{aid}")
    _pause()


def set_accomm_status() -> None:
    print("\n═══ Change Accommodation Status ═══")
    try:
        aid = int(_input("Accommodation ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_accommodation(aid)
    if existing is None:
        print(f"  ✗ No accommodation #{aid}")
        _pause()
        return
    try:
        new_status = _pick_from(
            "New status", list(ACCOMMODATION_STATUSES),
            default=existing.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_accommodation_status(aid, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{aid} → {new_status}")
    _pause()


def delete_accomm() -> None:
    print("\n═══ Delete Accommodation ═══")
    try:
        aid = int(_input("Accommodation ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_accommodation(aid) is None:
        print(f"  ✗ No accommodation #{aid}")
        _pause()
        return
    if _input(f"Delete accommodation #{aid}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_accommodation(aid):
        print(f"\n  ✓ Deleted accommodation #{aid}")
    _pause()


# ── Summary ────────────────────────────────────────────────────────

def summary() -> None:
    print("\n═══ Accessibility Summary ═══")
    try:
        window = int(_input("Upcoming review window (days)", default="30"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    summ = data.summary(upcoming_window_days=window)
    print(f"\n  Students with profile : {summ.student_count}")
    print(f"  EHCP                  : {summ.ehcp_count}")
    print(f"  PEEP required         : {summ.pep_count}")
    print(f"\n  Reviews:")
    print(f"    Overdue             : {summ.review_overdue}")
    print(f"    Upcoming ({window}d)      : {summ.review_upcoming}")
    print(f"\n  Accommodations        : {summ.accommodation_count} "
          f"(active: {summ.active_accommodation_count})")

    print("\n  By SEND status:")
    for s in SEND_STATUSES:
        print(f"    {s:<14} : {summ.by_send_status.get(s, 0)}")
    print("\n  By primary need:")
    for n in PRIMARY_NEEDS:
        c = summ.by_primary_need.get(n, 0)
        if c:
            print(f"    {n:<36} : {c}")
    print("\n  Accommodations by category:")
    for c in ACCOMMODATION_CATEGORIES:
        n = summ.by_category.get(c, 0)
        if n:
            print(f"    {c:<24} : {n}")
    _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List Profiles",            list_all_profiles),
    ("EHCP Students",            list_ehcp),
    ("Review Overdue",           review_overdue),
    ("View Profile",             view_profile),
    ("New Profile",              new_profile),
    ("Edit Profile",             edit_profile),
    ("Mark Reviewed",            mark_reviewed_flow),
    ("Delete Profile",           delete_profile_flow),
    ("─" * 6,                    lambda: None),
    ("List All Accommodations",  list_all_accomms),
    ("List Active",              list_active_accomms),
    ("Exam Access (JCQ)",        exam_access_list),
    ("Per-Student",              per_student_accomms),
    ("Filter Accommodations",    filter_accomms),
    ("New Accommodation",        new_accomm),
    ("Edit Accommodation",       edit_accomm),
    ("Change Accommodation Status", set_accomm_status),
    ("Delete Accommodation",     delete_accomm),
    ("─" * 6,                    lambda: None),
    ("Summary",                  summary),
]


def run() -> None:
    while True:
        print("\n── Accessibility ──")
        for i, (label, _) in enumerate(_MENU, 1):
            if label.startswith("─"):
                print(f"      {label * 3}")
            else:
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
        label, handler = _MENU[int(choice) - 1]
        if label.startswith("─"):
            continue
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Accessibility CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Accessibility":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Accessibility CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
