"""CLI flows for Sixth Form Behaviour Log."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.pastoral.behaviour import behaviour
from education_system.sixthform_system.modules.domain.pastoral.behaviour import behaviour as data
from education_system.sixthform_system.modules.domain.students.students import students as student_data
from education_system.sixthform_system.modules.domain.pastoral.behaviour.behaviour import (
    ALL_CATEGORIES,
    BehaviourEntry,
    ENTRY_TYPES,
    NEGATIVE_CATEGORIES,
    POSITIVE_CATEGORIES,
    SEVERITIES,
    ValidationError,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


# ── Prompt helpers ─────────────────────────────────────────────────

def _input(prompt: str, *, default: str = "", allow_empty: bool = True) -> str:
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


def _pick_from(label: str, options: list[str], default: str | None = None) -> str:
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
            print(f"    Out of range (1..{len(options)}).")
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
            print(f"    Out of range (1..{len(students)}).")
            continue
        match = next((s for s in students
                      if s.student_id.lower() == raw.lower()), None)
        if match:
            return match.student_id
        print("    No matching student.")


# ── Print helpers ──────────────────────────────────────────────────

def _print_entries(rows: list[BehaviourEntry]) -> None:
    if not rows:
        print("\n  (no entries)")
        return
    print()
    print(f"  {'#':>4}  {'Student':<10}  {'Date':<10}  {'Type':<8}  "
          f"{'Category':<18}  {'Sev.':<6}  {'Pts':>4}  Follow-up")
    print("  " + "-" * 86)
    for e in rows:
        pts = ("+" if e.points >= 0 else "") + str(e.points)
        fu = e.follow_up_date or ("Yes" if e.follow_up_required else "—")
        print(f"  {e.entry_id:>4}  {e.student_id:<10}  "
              f"{e.entry_date:<10}  {e.entry_type:<8}  "
              f"{e.category[:18]:<18}  {(e.severity or '—'):<6}  "
              f"{pts:>4}  {fu}")
    print(f"\n  {len(rows)} entry/entries.")


# ── CRUD entry points ──────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ Behaviour Log ═══")
    rows = data.list_entries()
    _print_entries(rows)
    _row_action_loop(rows)


def filter_entries() -> None:
    print("\n═══ Filter Behaviour Entries ═══")
    print("  (leave any field blank to skip; 'cancel' to abort)\n")
    try:
        sid = _input("Student ID") or None
        etype = _input(f"Type ({'/'.join(ENTRY_TYPES)})") or None
        category = _input("Category (exact)") or None
        severity = _input(f"Severity ({'/'.join(SEVERITIES)})") or None
        date_from = _input("From (YYYY-MM-DD)") or None
        date_to = _input("To (YYYY-MM-DD)") or None
        fu_raw = _input("Follow-up required? (y/n/blank)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    fu = None
    if fu_raw:
        fu = fu_raw.lower() in ("y", "yes", "1", "true")
    try:
        rows = data.list_entries(
            student_id=sid, entry_type=etype, category=category,
            severity=severity, date_from=date_from, date_to=date_to,
            follow_up_required=fu,
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_entries(rows)
    _row_action_loop(rows)


def per_student() -> None:
    print("\n═══ Per-Student Behaviour ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    student = student_data.get_student(sid)
    rows = data.entries_for_student(sid)
    summ = data.per_student_summary(sid)
    sign = "+" if summ.net_points >= 0 else ""
    print(f"\n  {student.student_id}  {student.full_name}")
    print(f"  Total: {summ.total_entries}  Positive: {summ.positive_count}  "
          f"Negative: {summ.negative_count}  Net: {sign}{summ.net_points}  "
          f"Open follow-ups: {summ.open_follow_ups}")
    _print_entries(rows)
    _row_action_loop(rows)


def view_entry(entry_id: int | None = None) -> None:
    print("\n═══ View Entry ═══")
    try:
        eid = entry_id if entry_id is not None else int(
            _input("Entry ID", allow_empty=False))
    except ValueError:
        print("  ✗ Entry ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    e = data.get_entry(eid)
    if e is None:
        print(f"  ✗ No entry #{eid}")
        _pause()
        return
    print()
    print(f"    Entry ID         : #{e.entry_id}")
    print(f"    Student          : {e.student_id}")
    print(f"    Date             : {e.entry_date}")
    print(f"    Type             : {e.entry_type}")
    print(f"    Category         : {e.category}")
    print(f"    Severity         : {e.severity or '—'}")
    print(f"    Points           : "
          f"{('+' if e.points >= 0 else '')}{e.points}")
    print(f"    Location         : {e.location or '—'}")
    print(f"    Recorded by      : {e.recorded_by or '—'}")
    print(f"    Action taken     : {e.action_taken or '—'}")
    print(f"    Follow-up needed : {'Yes' if e.follow_up_required else 'No'}")
    print(f"    Follow-up date   : {e.follow_up_date or '—'}")
    print(f"    Parent contacted : {'Yes' if e.parent_contacted else 'No'}")
    print()
    print(f"    Description:")
    for line in e.description.splitlines() or [""]:
        print(f"      {line}")
    _pause()


def _collect_form(existing: BehaviourEntry | None) -> dict[str, Any]:
    is_edit = existing is not None
    payload: dict[str, Any] = {}

    if is_edit:
        print(f"\n  Editing entry #{existing.entry_id} "
              f"for {existing.student_id}")
        payload["student_id"] = existing.student_id
    else:
        print("\n  ── Student ──")
        payload["student_id"] = _pick_student()

    print("\n  ── Entry details ──")
    today = _date.today().isoformat()
    payload["entry_date"] = _input(
        "Date (YYYY-MM-DD)",
        default=(existing.entry_date if is_edit else today),
        allow_empty=False,
    )
    payload["entry_type"] = _pick_from(
        "Type", list(ENTRY_TYPES),
        default=(existing.entry_type if is_edit else "Positive"),
    )
    cats = (POSITIVE_CATEGORIES if payload["entry_type"] == "Positive"
            else NEGATIVE_CATEGORIES)
    payload["category"] = _pick_from(
        "Category", list(cats),
        default=(existing.category if is_edit and existing.category in cats
                 else cats[0]),
    )
    if payload["entry_type"] == "Negative":
        payload["severity"] = _pick_from(
            "Severity", list(SEVERITIES),
            default=(existing.severity if is_edit and existing.severity
                     else "Medium"),
        )
    else:
        # Positive: severity optional
        sev_raw = _input(
            f"Severity (optional: {'/'.join(SEVERITIES)})",
            default=(existing.severity or "") if is_edit else "",
        )
        payload["severity"] = sev_raw
    payload["points"] = _input(
        "Points (blank = default by type/severity)",
        default=(str(existing.points) if is_edit else ""),
    )
    payload["location"] = _input(
        "Location (optional)",
        default=(existing.location or "") if is_edit else "",
    )
    payload["recorded_by"] = _input(
        "Recorded by",
        default=(existing.recorded_by or "") if is_edit else "",
    )
    print("\n  Description (single line; for multi-line use the GUI):")
    payload["description"] = _input(
        "Description",
        default=(existing.description if is_edit else ""),
        allow_empty=False,
    )
    payload["action_taken"] = _input(
        "Action taken (optional)",
        default=(existing.action_taken or "") if is_edit else "",
    )
    payload["follow_up_required"] = _yes_no(
        "Follow-up required?",
        default=(existing.follow_up_required if is_edit else False),
    )
    if payload["follow_up_required"]:
        payload["follow_up_date"] = _input(
            "Follow-up date (YYYY-MM-DD, optional)",
            default=(existing.follow_up_date or "") if is_edit else "",
        )
    else:
        payload["follow_up_date"] = ""
    payload["parent_contacted"] = _yes_no(
        "Parent contacted?",
        default=(existing.parent_contacted if is_edit else False),
    )
    return payload


def new_entry() -> None:
    print("\n═══ New Behaviour Entry ═══")
    print("  (type 'cancel' at any prompt to abort)")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        e = data.create_entry(payload)
    except ValidationError as ex:
        print(f"\n  ✗ {ex}")
        _pause()
        return
    except Exception as ex:
        logger.exception("create_entry crashed")
        print(f"\n  ✗ Unexpected error: {ex}")
        _pause()
        return
    sign = "+" if e.points >= 0 else ""
    print(f"\n  ✓ Created entry #{e.entry_id} "
          f"({e.student_id}, {e.entry_type}, {e.category}, {sign}{e.points})")
    _pause()


def edit_entry(entry_id: int | None = None) -> None:
    print("\n═══ Edit Behaviour Entry ═══")
    try:
        eid = entry_id if entry_id is not None else int(
            _input("Entry ID", allow_empty=False))
    except ValueError:
        print("  ✗ Entry ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_entry(eid)
    if existing is None:
        print(f"  ✗ No entry #{eid}")
        _pause()
        return
    try:
        payload = _collect_form(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_entry(eid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("update_entry crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Updated entry #{eid}")
    _pause()


def delete_entry_flow(entry_id: int | None = None) -> None:
    print("\n═══ Delete Behaviour Entry ═══")
    try:
        eid = entry_id if entry_id is not None else int(
            _input("Entry ID", allow_empty=False))
    except ValueError:
        print("  ✗ Entry ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_entry(eid)
    if existing is None:
        print(f"  ✗ No entry #{eid}")
        _pause()
        return
    confirm = _input(
        f"Delete entry #{eid} ({existing.student_id}, {existing.category})? "
        f"Type 'yes'",
        default="no")
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        if data.delete_entry(eid):
            print(f"\n  ✓ Deleted #{eid}")
    except Exception as e:
        logger.exception("delete_entry crashed")
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


# ── Summary ───────────────────────────────────────────────────────

def summary() -> None:
    print("\n═══ Behaviour Summary ═══")
    try:
        upcoming = int(_input("Follow-up window in days", default="14"))
        top_n = int(_input("Top N students", default="10"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    summ = data.summary(
        upcoming_window_days=upcoming, top_n=top_n)
    sign = "+" if summ.net_points >= 0 else ""
    print(f"\n  Total entries : {summ.total}")
    print(f"  Net points    : {sign}{summ.net_points}")
    print("\n  By type:")
    for t in ENTRY_TYPES:
        print(f"    {t:<10} : {summ.by_type.get(t, 0)}")
    print("\n  By severity (negative entries):")
    for s in SEVERITIES:
        print(f"    {s:<10} : {summ.by_severity.get(s, 0)}")
    if summ.by_category:
        print("\n  Top categories:")
        for cat, n in sorted(summ.by_category.items(),
                              key=lambda kv: -kv[1])[:12]:
            print(f"    {cat[:24]:<24} : {n}")
    print(f"\n  Follow-ups open       : {summ.follow_ups_open}")
    print(f"  Upcoming ({upcoming}d)       : {summ.upcoming_follow_ups}")
    print(f"  Parents contacted     : {summ.parents_contacted}")
    if summ.top_students_by_count:
        names = {s.student_id: s.full_name
                 for s in student_data.list_students()}
        print(f"\n  Top {top_n} students by entry count:")
        for sid, n in summ.top_students_by_count:
            print(f"    {sid:<10}  "
                  f"{(names.get(sid, '(unknown)'))[:30]:<30}  : {n}")
    _pause()


# ── Row-action loop ───────────────────────────────────────────────

def _row_action_loop(rows: list[BehaviourEntry]) -> None:
    if not rows:
        _pause()
        return
    print()
    print("  Actions:  V) View   E) Edit   D) Delete   (Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in ("v", "e", "d"):
            print("    Pick V, E, D, or Enter.")
            continue
        try:
            raw = _input("Entry ID", allow_empty=False)
        except _UserAbort:
            return
        try:
            eid = int(raw)
        except ValueError:
            print("    Entry ID must be a whole number.")
            continue
        if choice == "v":
            view_entry(eid)
        elif choice == "e":
            edit_entry(eid)
        elif choice == "d":
            delete_entry_flow(eid)
        return


# ── Submenu dispatcher ────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List Entries",     list_all),
    ("Filter Entries",   filter_entries),
    ("Per-Student",      per_student),
    ("View Entry",       view_entry),
    ("New Entry",        new_entry),
    ("Edit Entry",       edit_entry),
    ("Delete Entry",     delete_entry_flow),
    ("Summary",          summary),
]


def run() -> None:
    while True:
        print("\n── Behaviour Log ──")
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
            logger.exception("Behaviour CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Behaviour Log":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Behaviour CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
