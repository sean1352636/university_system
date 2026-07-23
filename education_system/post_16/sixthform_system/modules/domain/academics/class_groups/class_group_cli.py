"""CLI flows for Sixth Form Class Groups."""

from __future__ import annotations

import logging
from typing import Any, Callable
from education_system.post_16.sixthform_system.modules.domain.academics.class_groups import class_groups
from education_system.post_16.sixthform_system.modules.domain.academics.courses import courses
from education_system.post_16.sixthform_system.modules.domain.academics.class_groups import class_groups as data
from education_system.post_16.sixthform_system.modules.domain.academics.courses import courses as course_data
from education_system.post_16.sixthform_system.modules.domain.students.students import students as student_data
from education_system.post_16.sixthform_system.modules.domain.academics.class_groups.class_groups import (
    ClassGroup,
    ValidationError,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    """Raised when the user hits Ctrl-C / EOF or types ``cancel``."""


# ── Prompt helpers ──────────────────────────────────────────────────

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


def _pick_course() -> int:
    try:
        courses = course_data.list_courses()
    except Exception as e:
        logger.exception("Could not load courses for picker")
        print(f"    Error: {e}")
        raise _UserAbort
    if not courses:
        print("    No courses exist. Create a course first.")
        raise _UserAbort
    print("\n  Courses:")
    for i, c in enumerate(courses, 1):
        print(f"    {i:>3}) #{c.course_id:<4}  {c.course_code:<14}  "
              f"{c.subject}  (Y{c.year_group} {c.academic_year})")
    while True:
        raw = _input(f"  Pick #1..{len(courses)} (or type a course ID)",
                     allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(courses):
                return courses[n - 1].course_id
            try:
                # Maybe they typed the actual course_id
                target = next((c for c in courses if c.course_id == int(raw)), None)
                if target:
                    return target.course_id
            except ValueError:
                pass
            print(f"    Out of range (1..{len(courses)}).")
            continue
        print("    Enter a number.")


def _pick_student_not_in(group_id: int) -> str:
    members = set(data.list_members(group_id))
    try:
        all_students = student_data.list_students()
    except Exception as e:
        logger.exception("Could not load students")
        print(f"    Error: {e}")
        raise _UserAbort
    candidates = [s for s in all_students if s.student_id not in members]
    if not candidates:
        print("    No more students to add.")
        raise _UserAbort
    print("\n  Students not in this group:")
    for i, s in enumerate(candidates, 1):
        print(f"    {i:>3}) {s.student_id}  {s.full_name}")
    while True:
        raw = _input(f"  Pick #1..{len(candidates)} "
                     f"(or type a student ID)", allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(candidates):
                return candidates[n - 1].student_id
            print(f"    Out of range (1..{len(candidates)}).")
            continue
        match = next((s for s in candidates if s.student_id.lower() == raw.lower()),
                     None)
        if match:
            return match.student_id
        print("    No matching student.")


# ── Form ────────────────────────────────────────────────────────────

def _collect_form(existing: ClassGroup | None) -> dict[str, Any]:
    is_edit = existing is not None
    payload: dict[str, Any] = {}

    if is_edit:
        print(f"\n  Editing class group #{existing.group_id} "
              f"(course #{existing.course_id})")
        payload["course_id"] = existing.course_id  # immutable in CLI flow
    else:
        print("\n  ── Course ──")
        payload["course_id"] = _pick_course()

    print("\n  ── Group details ──")
    payload["group_name"] = _input(
        "Group name (e.g. 12M-1)",
        default=(existing.group_name if is_edit else ""),
        allow_empty=False,
    )
    payload["teacher"] = _input(
        "Teacher (blank = inherit course)",
        default=(existing.teacher or "") if is_edit else "")
    payload["room"] = _input(
        "Room (blank = inherit course)",
        default=(existing.room or "") if is_edit else "")
    payload["schedule"] = _input(
        "Schedule (e.g. 'Mon P1, Wed P3, Fri P2')",
        default=(existing.schedule or "") if is_edit else "")
    payload["max_students"] = _input(
        "Max students (blank = inherit course)",
        default=(str(existing.max_students) if (is_edit and existing.max_students)
                 else ""))
    payload["notes"] = _input(
        "Notes (optional)",
        default=(existing.notes or "") if is_edit else "")
    return payload


# ── CRUD entry points ───────────────────────────────────────────────

def _print_table(rows: list[ClassGroup]) -> None:
    if not rows:
        print("\n  (no class groups)")
        return
    try:
        course_codes = {c.course_id: c.course_code for c in course_data.list_courses()}
    except Exception:
        logger.exception("Could not load course codes")
        course_codes = {}
    print()
    print(f"  {'#':>4}  {'Course':<14}  {'Group':<14}  {'Teacher':<18}  "
          f"{'Room':<6}  {'Members':>7}  {'Cap':>5}")
    print("  " + "-" * 78)
    for g in rows:
        cap = data.effective_cap(g)
        print(
            f"  {g.group_id:>4}  "
            f"{course_codes.get(g.course_id, '#'+str(g.course_id)):<14}  "
            f"{g.group_name:<14}  {(g.teacher or '—')[:18]:<18}  "
            f"{(g.room or '—'):<6}  "
            f"{data.count_members(g.group_id):>7}  "
            f"{(str(cap) if cap is not None else '—'):>5}"
        )
    print(f"\n  {len(rows)} class group(s).")


def list_all() -> None:
    print("\n═══ Class Groups ═══")
    try:
        rows = data.list_groups()
    except Exception as e:
        logger.exception("CLI list_groups failed")
        print(f"  ✗ Error: {e}")
        _pause()
        return
    _print_table(rows)
    _row_action_loop(rows)


def filter_groups() -> None:
    print("\n═══ Filter Class Groups ═══")
    print("  (leave any field blank to skip; 'cancel' to abort)\n")
    try:
        cid_raw = _input("Course ID")
        teacher = _input("Teacher (substring)") or None
        search = _input("Search (name / room / schedule)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return

    cid: int | None = None
    if cid_raw:
        try:
            cid = int(cid_raw)
        except ValueError:
            print("  ✗ Course ID must be a number.")
            _pause()
            return

    try:
        rows = data.list_groups(course_id=cid, teacher=teacher, search=search)
    except Exception as e:
        logger.exception("CLI filter_groups failed")
        print(f"  ✗ Error: {e}")
        _pause()
        return
    _print_table(rows)
    _row_action_loop(rows)


def new_group() -> None:
    print("\n═══ New Class Group ═══")
    print("  (type 'cancel' at any prompt to abort)")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        created = data.create_group(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("CLI new_group failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print()
    print(f"  ✓ Created class group #{created.group_id}")
    print(f"      Course   : #{created.course_id}")
    print(f"      Name     : {created.group_name}")
    print(f"      Teacher  : {created.teacher or '(inherits course)'}")
    print(f"      Room     : {created.room or '(inherits course)'}")
    print(f"      Schedule : {created.schedule or '—'}")
    cap = data.effective_cap(created)
    print(f"      Capacity : {cap if cap is not None else '—'}")
    _pause()


def view_group(group_id: int | None = None) -> None:
    print("\n═══ View Class Group ═══")
    try:
        gid = group_id if group_id is not None else int(
            _input("Group ID", allow_empty=False))
    except ValueError:
        print("  ✗ Group ID must be a whole number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    g = data.get_group(gid)
    if g is None:
        print(f"  ✗ No class group #{gid}")
        _pause()
        return

    course = course_data.get_course(g.course_id)
    cap = data.effective_cap(g)
    print()
    print(f"    Group ID   : #{g.group_id}")
    print(f"    Course     : {course.course_code if course else '#'+str(g.course_id)} "
          f"({course.subject if course else '?'})")
    print(f"    Group name : {g.group_name}")
    print(f"    Teacher    : {g.teacher or (course.teacher if course else None) or '—'}")
    print(f"    Room       : {g.room or (course.room if course else None) or '—'}")
    print(f"    Schedule   : {g.schedule or '—'}")
    print(f"    Capacity   : {data.count_members(gid)} "
          f"/ {cap if cap is not None else '—'}")
    if g.notes:
        print(f"    Notes      : {g.notes}")

    # Members
    members = data.list_members(gid)
    print("\n    Members:")
    if not members:
        print("      (none)")
    else:
        # Show names where possible
        try:
            names = {s.student_id: s.full_name for s in student_data.list_students()}
        except Exception:
            names = {}
        for sid in members:
            print(f"      {sid}  {names.get(sid, '(unknown)')}")
    _pause()


def edit_group(group_id: int | None = None) -> None:
    print("\n═══ Edit Class Group ═══")
    try:
        gid = group_id if group_id is not None else int(
            _input("Group ID", allow_empty=False))
    except ValueError:
        print("  ✗ Group ID must be a whole number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return

    existing = data.get_group(gid)
    if existing is None:
        print(f"  ✗ No class group #{gid}")
        _pause()
        return
    try:
        payload = _collect_form(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        updated = data.update_group(gid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("CLI update_group(%d) failed", gid)
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Updated class group #{updated.group_id} ({updated.group_name})")
    _pause()


def delete_group_flow(group_id: int | None = None) -> None:
    print("\n═══ Delete Class Group ═══")
    try:
        gid = group_id if group_id is not None else int(
            _input("Group ID", allow_empty=False))
    except ValueError:
        print("  ✗ Group ID must be a whole number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return

    existing = data.get_group(gid)
    if existing is None:
        print(f"  ✗ No class group #{gid}")
        _pause()
        return
    n = data.count_members(gid)
    extra = f" ({n} member(s) will be removed)" if n else ""
    confirm = _input(
        f"Delete '{existing.group_name}'?{extra} Type 'yes' to confirm",
        default="no",
    )
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        if data.delete_group(gid):
            print(f"\n  ✓ Deleted class group #{gid}")
        else:
            print(f"\n  ✗ Could not delete class group #{gid}")
    except Exception as e:
        logger.exception("CLI delete_group(%d) failed", gid)
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


# ── Member management ──────────────────────────────────────────────

def manage_members() -> None:
    print("\n═══ Manage Members ═══")
    try:
        gid = int(_input("Group ID", allow_empty=False))
    except ValueError:
        print("  ✗ Group ID must be a whole number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return

    g = data.get_group(gid)
    if g is None:
        print(f"  ✗ No class group #{gid}")
        _pause()
        return

    while True:
        cap = data.effective_cap(g)
        members = data.list_members(gid)
        print(f"\n  Group: #{g.group_id} {g.group_name} — "
              f"{len(members)}/{cap if cap is not None else '—'} member(s)")
        if members:
            try:
                names = {s.student_id: s.full_name for s in student_data.list_students()}
            except Exception:
                names = {}
            for sid in members:
                print(f"    · {sid}  {names.get(sid, '(unknown)')}")
        else:
            print("    (no members)")

        print("\n  1) Add member   2) Remove member   0) Back")
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
            try:
                data.add_member(gid, sid)
                print(f"\n  ✓ Added {sid}")
            except ValidationError as e:
                print(f"\n  ✗ {e}")
            except Exception as e:
                logger.exception("CLI add_member(%d, %s) failed", gid, sid)
                print(f"\n  ✗ Unexpected error: {e}")
            _pause()
        elif choice == "2":
            if not members:
                print("\n  (no members to remove)")
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
            confirm = _input(f"Remove {raw} from group? Type 'yes'",
                             default="no")
            if confirm.lower() != "yes":
                continue
            try:
                if data.remove_member(gid, raw):
                    print(f"\n  ✓ Removed {raw}")
                else:
                    print(f"\n  ✗ Could not remove {raw}")
            except Exception as e:
                logger.exception("CLI remove_member crashed")
                print(f"\n  ✗ Unexpected error: {e}")
            _pause()
        else:
            print("  Invalid selection.")


# ── Row-action loop ─────────────────────────────────────────────────

def _row_action_loop(rows: list[ClassGroup]) -> None:
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
            print("  Cancelled.")
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
            # Reuse manage_members but skip its inner prompt
            g = data.get_group(gid)
            if g is None:
                print(f"  ✗ No class group #{gid}")
                _pause()
                continue
            _manage_members_for(gid)
        elif choice == "d":
            delete_group_flow(gid)
        return


def _manage_members_for(gid: int) -> None:
    """Variant of manage_members that takes the id directly, used from
    the row-action loop so we don't double-prompt the user."""
    g = data.get_group(gid)
    if g is None:
        print(f"  ✗ No class group #{gid}")
        _pause()
        return

    while True:
        cap = data.effective_cap(g)
        members = data.list_members(gid)
        print(f"\n  Group: #{g.group_id} {g.group_name} — "
              f"{len(members)}/{cap if cap is not None else '—'} member(s)")
        if members:
            try:
                names = {s.student_id: s.full_name for s in student_data.list_students()}
            except Exception:
                names = {}
            for sid in members:
                print(f"    · {sid}  {names.get(sid, '(unknown)')}")
        else:
            print("    (no members)")

        print("\n  1) Add member   2) Remove member   0) Back")
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
            try:
                data.add_member(gid, sid)
                print(f"\n  ✓ Added {sid}")
            except ValidationError as e:
                print(f"\n  ✗ {e}")
            except Exception as e:
                logger.exception("CLI add_member crashed")
                print(f"\n  ✗ Unexpected error: {e}")
            _pause()
        elif choice == "2":
            if not members:
                print("\n  (no members to remove)")
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
            try:
                if data.remove_member(gid, raw):
                    print(f"\n  ✓ Removed {raw}")
            except Exception as e:
                logger.exception("CLI remove_member crashed")
                print(f"\n  ✗ Unexpected error: {e}")
            _pause()


# ── Submenu dispatcher ─────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List All Class Groups", list_all),
    ("Filter Class Groups",   filter_groups),
    ("New Class Group",       new_group),
    ("View Class Group",      view_group),
    ("Edit Class Group",      edit_group),
    ("Manage Members",        manage_members),
    ("Delete Class Group",    delete_group_flow),
]


def run() -> None:
    while True:
        print("\n── Class Groups ──")
        for i, (label, _) in enumerate(_MENU, 1):
            print(f"  {i}) {label}")
        print("  0) Back")
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
            logger.exception("Class-groups CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Class Groups":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Class-groups CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
