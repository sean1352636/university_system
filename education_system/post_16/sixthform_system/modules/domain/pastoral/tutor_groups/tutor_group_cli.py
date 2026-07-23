"""CLI flows for Sixth Form Tutor Groups."""

from __future__ import annotations

import logging
from typing import Any, Callable
from education_system.post_16.sixthform_system.modules.domain.students.students import students as student_data
from education_system.post_16.sixthform_system.modules.domain.pastoral.tutor_groups import tutor_groups as data
from education_system.post_16.sixthform_system.modules.domain.pastoral.tutor_groups.tutor_groups import (
    GroupRow,
    TutorGroup,
    ValidationError,
    YEAR_GROUPS,
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


def _pick_group() -> int:
    groups = data.list_groups()
    if not groups:
        print("    No tutor groups exist.")
        raise _UserAbort
    print("\n  Tutor groups:")
    for i, g in enumerate(groups, 1):
        n = data.count_members(g.tutor_group_id)
        print(f"    {i:>3}) #{g.tutor_group_id:<3}  {g.name:<8}  "
              f"Year {g.year_group}  tutor={g.tutor or '—':<14}  "
              f"({n} member(s))")
    while True:
        raw = _input(f"  Pick #1..{len(groups)} (or group ID / name)",
                     allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(groups):
                return groups[n - 1].tutor_group_id
            target = next((g for g in groups if g.tutor_group_id == n), None)
            if target:
                return target.tutor_group_id
            print(f"    Out of range (1..{len(groups)}).")
            continue
        match = next((g for g in groups
                      if g.name.lower() == raw.lower()), None)
        if match:
            return match.tutor_group_id
        print("    No matching group.")


def _pick_student() -> str:
    students = student_data.list_students()
    if not students:
        print("    No students.")
        raise _UserAbort
    print("\n  Students:")
    for i, s in enumerate(students, 1):
        cur = data.group_for_student(s.student_id)
        cur_label = f" [{cur.name}]" if cur else ""
        print(f"    {i:>3}) {s.student_id}  {s.full_name}{cur_label}")
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

def _print_groups(rows: list[GroupRow]) -> None:
    if not rows:
        print("\n  (no tutor groups)")
        return
    print()
    print(f"  {'#':>4}  {'Name':<8}  {'Year':<5}  {'Tutor':<18}  "
          f"{'Co-tutor':<14}  {'Room':<6}  Members")
    print("  " + "-" * 70)
    for r in rows:
        g = r.group
        print(f"  {g.tutor_group_id:>4}  {g.name:<8}  {g.year_group:<5}  "
              f"{(g.tutor or '—')[:18]:<18}  "
              f"{(g.co_tutor or '—')[:14]:<14}  "
              f"{(g.room or '—'):<6}  {r.member_count}")
    print(f"\n  {len(rows)} tutor group(s).")


# ── Group CRUD ─────────────────────────────────────────────────────

def list_groups() -> None:
    print("\n═══ Tutor Groups ═══")
    rows = data.list_groups_with_counts()
    _print_groups(rows)
    _row_action_loop(rows)


def filter_groups() -> None:
    print("\n═══ Filter Tutor Groups ═══")
    print("  (leave any field blank to skip; 'cancel' to abort)\n")
    try:
        year_raw = _input("Year group (12/13)")
        tutor = _input("Tutor substring") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    year = None
    if year_raw:
        try:
            year = int(year_raw)
        except ValueError:
            print("  ✗ Year must be a number.")
            _pause()
            return
    try:
        rows = data.list_groups_with_counts(
            year_group=year, tutor_like=tutor)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_groups(rows)
    _row_action_loop(rows)


def view_group(tutor_group_id: int | None = None) -> None:
    print("\n═══ View Tutor Group ═══")
    try:
        gid = tutor_group_id if tutor_group_id is not None else _pick_group()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    g = data.get_group(gid)
    if g is None:
        print(f"  ✗ No tutor group #{gid}")
        _pause()
        return
    members = data.list_members(gid)
    print()
    print(f"    Group ID  : #{g.tutor_group_id}")
    print(f"    Name      : {g.name}")
    print(f"    Year      : Year {g.year_group}")
    print(f"    Tutor     : {g.tutor or '—'}")
    print(f"    Co-tutor  : {g.co_tutor or '—'}")
    print(f"    Room      : {g.room or '—'}")
    print(f"    Members   : {len(members)}")
    if g.notes:
        print(f"    Notes     : {g.notes}")

    if members:
        names = {s.student_id: s.full_name
                 for s in student_data.list_students()}
        print("\n    Roster:")
        for sid in members:
            print(f"      {sid}  {names.get(sid, '(unknown)')}")
    _pause()


def _collect_group_form(existing: TutorGroup | None) -> dict[str, Any]:
    is_edit = existing is not None
    payload: dict[str, Any] = {}

    print("\n  ── Tutor group details ──")
    payload["name"] = _input(
        "Group name (e.g. 12A)",
        default=(existing.name if is_edit else ""),
        allow_empty=False,
    )
    payload["year_group"] = _pick_from(
        "Year group", [str(y) for y in YEAR_GROUPS],
        default=(str(existing.year_group) if is_edit else str(YEAR_GROUPS[0])),
    )
    payload["tutor"] = _input(
        "Tutor (optional)",
        default=(existing.tutor or "") if is_edit else "",
    )
    payload["co_tutor"] = _input(
        "Co-tutor (optional)",
        default=(existing.co_tutor or "") if is_edit else "",
    )
    payload["room"] = _input(
        "Room (optional)",
        default=(existing.room or "") if is_edit else "",
    )
    payload["notes"] = _input(
        "Notes (optional)",
        default=(existing.notes or "") if is_edit else "",
    )
    return payload


def new_group() -> None:
    print("\n═══ New Tutor Group ═══")
    print("  (type 'cancel' at any prompt to abort)")
    try:
        payload = _collect_group_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        g = data.create_group(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("create_group crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Created tutor group #{g.tutor_group_id} ({g.name})")
    _pause()


def edit_group(tutor_group_id: int | None = None) -> None:
    print("\n═══ Edit Tutor Group ═══")
    try:
        gid = tutor_group_id if tutor_group_id is not None else _pick_group()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_group(gid)
    if existing is None:
        print(f"  ✗ No tutor group #{gid}")
        _pause()
        return
    try:
        payload = _collect_group_form(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_group(gid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("update_group crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Updated tutor group #{gid}")
    _pause()


def delete_group_flow(tutor_group_id: int | None = None) -> None:
    print("\n═══ Delete Tutor Group ═══")
    try:
        gid = tutor_group_id if tutor_group_id is not None else _pick_group()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_group(gid)
    if existing is None:
        print(f"  ✗ No tutor group #{gid}")
        _pause()
        return
    n = data.count_members(gid)
    extra = f" ({n} member(s) will be unassigned)" if n else ""
    confirm = _input(
        f"Delete {existing.name}?{extra} Type 'yes'",
        default="no")
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        if data.delete_group(gid):
            print(f"\n  ✓ Deleted tutor group #{gid}")
    except Exception as e:
        logger.exception("delete_group crashed")
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


# ── Membership management ─────────────────────────────────────────

def manage_members() -> None:
    print("\n═══ Manage Members ═══")
    try:
        gid = _pick_group()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _manage_members_for(gid)


def _manage_members_for(gid: int) -> None:
    g = data.get_group(gid)
    if g is None:
        print(f"  ✗ No tutor group #{gid}")
        _pause()
        return

    while True:
        members = data.list_members(gid)
        names = {s.student_id: s.full_name
                 for s in student_data.list_students()}
        print(f"\n  Group: {g.name}  (Year {g.year_group})  "
              f"·  {len(members)} member(s)")
        if not members:
            print("    (no members)")
        for sid in members:
            print(f"    · {sid}  {names.get(sid, '(unknown)')}")

        print("\n  1) Add student   2) Remove student   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if choice == "1":
            try:
                sid = _pick_student_not_in(gid)
            except _UserAbort:
                continue
            # Warn if they're already in another group
            prev = data.group_for_student(sid)
            if prev is not None:
                confirm = _input(
                    f"  {sid} is currently in {prev.name}. "
                    f"Move them to {g.name}? Type 'yes'",
                    default="no")
                if confirm.lower() != "yes":
                    continue
            try:
                data.assign_student(sid, gid)
                print(f"  ✓ Added {sid} to {g.name}")
            except ValidationError as e:
                print(f"  ✗ {e}")
            except Exception as e:
                logger.exception("assign_student crashed")
                print(f"  ✗ Unexpected error: {e}")
            _pause()
        elif choice == "2":
            if not members:
                print("  (no members to remove)")
                _pause()
                continue
            try:
                raw = _input("Student ID to remove", allow_empty=False)
            except _UserAbort:
                continue
            if raw not in members:
                print(f"  ✗ {raw} is not in this group.")
                _pause()
                continue
            confirm = _input(f"Remove {raw} from {g.name}? Type 'yes'",
                             default="no")
            if confirm.lower() != "yes":
                continue
            try:
                if data.unassign_student(raw):
                    print(f"  ✓ Removed {raw}")
            except Exception as e:
                logger.exception("unassign_student crashed")
                print(f"  ✗ {e}")
            _pause()
        else:
            print("  Invalid selection.")


def _pick_student_not_in(tutor_group_id: int) -> str:
    members = set(data.list_members(tutor_group_id))
    students = student_data.list_students()
    candidates = [s for s in students if s.student_id not in members]
    if not candidates:
        print("    No more students to add.")
        raise _UserAbort
    print("\n  Students:")
    for i, s in enumerate(candidates, 1):
        cur = data.group_for_student(s.student_id)
        cur_label = f" [{cur.name}]" if cur else ""
        print(f"    {i:>3}) {s.student_id}  {s.full_name}{cur_label}")
    while True:
        raw = _input(f"  Pick #1..{len(candidates)} (or student ID)",
                     allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(candidates):
                return candidates[n - 1].student_id
            print(f"    Out of range (1..{len(candidates)}).")
            continue
        match = next((s for s in candidates
                      if s.student_id.lower() == raw.lower()), None)
        if match:
            return match.student_id
        print("    No matching student.")


# ── Per-student ───────────────────────────────────────────────────

def per_student() -> None:
    print("\n═══ Per-Student ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    student = student_data.get_student(sid)
    cur_group = data.group_for_student(sid)
    print(f"\n  {student.student_id}  {student.full_name}")
    if cur_group:
        print(f"  Tutor group: {cur_group.name} (Year {cur_group.year_group}, "
              f"tutor: {cur_group.tutor or '—'})")
    else:
        print("  Tutor group: (none assigned)")

    print("\n  1) Reassign to another group   "
          "2) Unassign   0) Back")
    try:
        choice = input("  Select: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return
    if choice == "1":
        try:
            gid = _pick_group()
        except _UserAbort:
            print("\n  Cancelled.")
            return
        try:
            data.assign_student(sid, gid)
            target = data.get_group(gid)
            print(f"\n  ✓ Assigned {sid} to {target.name}")
        except ValidationError as e:
            print(f"\n  ✗ {e}")
        except Exception as e:
            logger.exception("assign_student crashed")
            print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    elif choice == "2":
        if cur_group is None:
            print("\n  (already not assigned)")
            _pause()
            return
        confirm = _input(
            f"Remove {sid} from {cur_group.name}? Type 'yes'",
            default="no")
        if confirm.lower() != "yes":
            return
        try:
            if data.unassign_student(sid):
                print(f"\n  ✓ Unassigned {sid}")
        except Exception as e:
            logger.exception("unassign_student crashed")
            print(f"\n  ✗ {e}")
        _pause()


# ── Summary ───────────────────────────────────────────────────────

def summary() -> None:
    print("\n═══ Tutor-Group Summary ═══")
    summ = data.summary()
    print(f"\n  Tutor groups: {summ.total_groups}")
    print(f"  Students assigned: {summ.assigned_students}/{summ.total_students}")
    print("\n  By year:")
    for y in YEAR_GROUPS:
        print(f"    Year {y}  : {summ.by_year.get(y, 0)} group(s)")
    print(f"\n  Unassigned students: {summ.unassigned_students}")
    if summ.unassigned_students:
        names = {s.student_id: s.full_name
                 for s in student_data.list_students()}
        for sid in data.unassigned_students()[:30]:
            print(f"    {sid:<10}  {names.get(sid, '—')}")
        if summ.unassigned_students > 30:
            print(f"    … and {summ.unassigned_students - 30} more")
    _pause()


# ── Row-action loop ───────────────────────────────────────────────

def _row_action_loop(rows: list[GroupRow]) -> None:
    if not rows:
        _pause()
        return
    print()
    print("  Actions:  V) View   E) Edit   M) Manage members   "
          "D) Delete   (Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in ("v", "e", "m", "d"):
            print("    Pick V, E, M, D, or Enter.")
            continue
        try:
            raw = _input("Group ID", allow_empty=False)
        except _UserAbort:
            return
        try:
            gid = int(raw)
        except ValueError:
            print("    Group ID must be a whole number.")
            continue
        if choice == "v":
            view_group(gid)
        elif choice == "e":
            edit_group(gid)
        elif choice == "m":
            _manage_members_for(gid)
        elif choice == "d":
            delete_group_flow(gid)
        return


# ── Submenu dispatcher ────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List Tutor Groups",     list_groups),
    ("Filter Tutor Groups",   filter_groups),
    ("View Group",            view_group),
    ("New Group",             new_group),
    ("Edit Group",            edit_group),
    ("Manage Members",        manage_members),
    ("Delete Group",          delete_group_flow),
    ("Per-Student",           per_student),
    ("Summary",               summary),
]


def run() -> None:
    while True:
        print("\n── Tutor Groups ──")
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
            logger.exception("Tutor-groups CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Tutor Groups":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Tutor-groups CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
