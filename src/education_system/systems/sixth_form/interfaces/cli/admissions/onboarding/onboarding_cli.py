"""CLI flows for Sixth Form Onboarding."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.systems.sixth_form.domain.admissions.onboarding import (
    onboarding as data,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)
from education_system.systems.sixth_form.domain.admissions.onboarding.onboarding import (
    CATEGORIES,
    CHECKLIST_STATUSES,
    Checklist,
    DEFAULT_CATEGORY,
    DEFAULT_CHECKLIST_STATUS,
    DEFAULT_ITEM_STATUS,
    DEFAULT_TEMPLATE,
    Item,
    ITEM_STATUSES,
    TEMPLATES,
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
                default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}",
                      default=default or "")
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


def _pick_student() -> str:
    rows = student_data.list_students()
    if not rows:
        print("    No students.")
        raise _UserAbort
    print("\n  Students:")
    for i, s in enumerate(rows, 1):
        print(f"    {i:>3}) {s.student_id}  {s.full_name}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or student ID)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1].student_id
            continue
        match = next((s for s in rows
                       if s.student_id.lower() == raw.lower()), None)
        if match:
            return match.student_id
        print("    No matching student.")


def _pick_checklist() -> Checklist:
    rows = data.list_checklists()
    if not rows:
        print("    No checklists.")
        raise _UserAbort
    names = {s.student_id: s.full_name
              for s in student_data.list_students()}
    print("\n  Checklists:")
    for i, c in enumerate(rows, 1):
        print(f"    {i:>3}) #{c.checklist_id}  {c.student_id}  "
              f"{names.get(c.student_id, '?')[:22]:<22}  "
              f"[{c.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((c for c in rows if c.checklist_id == n), None)
            if match:
                return match
        print("    No matching checklist.")


def _pick_item(checklist_id: int) -> Item:
    items = data.list_items(checklist_id=checklist_id)
    if not items:
        print("    Checklist has no items.")
        raise _UserAbort
    print("\n  Items:")
    for i, it in enumerate(items, 1):
        mark = "✓" if it.is_done else " "
        req = "*" if it.required else " "
        print(f"    {i:>3}) [{mark}]{req} #{it.item_id}  "
              f"{it.category[:20]:<20}  {it.task_name}")
    while True:
        raw = _input(f"  Pick #1..{len(items)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(items):
                return items[n - 1]
            match = next((it for it in items if it.item_id == n), None)
            if match:
                return match
        print("    No matching item.")


# ── Print helpers ──────────────────────────────────────────────────

def _print_checklists(rows: list[Checklist]) -> None:
    if not rows:
        print("\n  (no checklists)")
        return
    names = {s.student_id: s.full_name
              for s in student_data.list_students()}
    print()
    print(f"  {'#':>4}  {'Student':<10}  {'Name':<22}  "
          f"{'Status':<14}  {'Due':<10}  {'Assigned':<14}  "
          f"Progress")
    print("  " + "-" * 100)
    detailed = {d.checklist.checklist_id: d
                 for d in data.list_checklists_with_detail()}
    for c in rows:
        d = detailed.get(c.checklist_id)
        prog = (f"{d.done}/{d.total} (req {d.required_done}/{d.required_total})"
                if d else "—")
        print(f"  {c.checklist_id:>4}  {c.student_id:<10}  "
              f"{names.get(c.student_id, '?')[:22]:<22}  "
              f"{c.status:<14}  {c.due_date or '—':<10}  "
              f"{(c.assigned_to or '—')[:14]:<14}  {prog}")
    print(f"\n  {len(rows)} checklist(s).")


def _print_items(items: list[Item]) -> None:
    if not items:
        print("\n  (no items)")
        return
    print()
    for it in items:
        mark = "✓" if it.is_done else "·"
        req = "*" if it.required else " "
        due = f"  due {it.due_date}" if it.due_date else ""
        comp = (f"  done {it.completed_on}"
                f" by {it.completed_by or '?'}"
                if it.completed_on else "")
        print(f"    [{mark}]{req} #{it.item_id:<3}  "
              f"{it.category[:18]:<18}  "
              f"{it.task_name}  ({it.status}){due}{comp}")


# ── Checklist flows ────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Checklists ═══")
    _print_checklists(data.list_checklists())
    _pause()


def list_open() -> None:
    print("\n═══ Open Checklists ═══")
    _print_checklists(data.list_checklists(open_only=True))
    _pause()


def list_overdue() -> None:
    print("\n═══ Overdue Checklists ═══")
    _print_checklists(data.list_checklists(overdue_only=True))
    _pause()


def view_checklist() -> None:
    print("\n═══ View Checklist ═══")
    try:
        c = _pick_checklist()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    detail = data.get_checklist_detail(c.checklist_id)
    assert detail is not None
    print()
    print(f"    #{c.checklist_id}  {c.name}")
    print(f"    Student        : {c.student_id}  {detail.student_name}")
    print(f"    Template       : {c.template_name or '—'}")
    print(f"    Status         : {c.status}")
    print(f"    Assigned to    : {c.assigned_to or '—'}")
    print(f"    Started on     : {c.started_on or '—'}")
    print(f"    Due date       : {c.due_date or '—'}")
    print(f"    Completed on   : {c.completed_on or '—'}")
    print(f"    Progress       : {detail.done_items}/{detail.total_items} "
          f"({detail.percent_complete}%)  ·  "
          f"required {detail.required_done}/{detail.required_total}")
    if c.notes:
        print("\n    Notes:")
        for line in c.notes.splitlines():
            print(f"      {line}")
    _print_items(detail.items)
    _pause()


def new_checklist() -> None:
    print("\n═══ New Checklist ═══")
    try:
        sid = _pick_student()
        templates = list(TEMPLATES.keys())
        template = _pick_from("Template", templates,
                                default=DEFAULT_TEMPLATE)
        name = _input("Checklist name (blank = auto)",
                       default="")
        due = _input("Due date (YYYY-MM-DD)")
        assigned = _input("Assigned to")
        notes = _input("Notes")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        c = data.create_checklist({
            "student_id": sid,
            "template_name": template,
            "name": name or None,
            "due_date": due or None,
            "assigned_to": assigned or None,
            "notes": notes or None,
            "status": DEFAULT_CHECKLIST_STATUS,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    n = len(data.list_items(checklist_id=c.checklist_id))
    print(f"\n  ✓ Created checklist #{c.checklist_id} ({n} items seeded)")
    _pause()


def edit_checklist() -> None:
    print("\n═══ Edit Checklist ═══")
    try:
        c = _pick_checklist()
        name = _input("Name", default=c.name, allow_empty=False)
        status = _pick_from("Status", list(CHECKLIST_STATUSES),
                              default=c.status)
        due = _input("Due date", default=c.due_date or "")
        assigned = _input("Assigned to", default=c.assigned_to or "")
        notes = _input("Notes", default=c.notes or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_checklist(c.checklist_id, {
            "name": name, "status": status,
            "due_date": due or None,
            "assigned_to": assigned or None,
            "notes": notes or None,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{c.checklist_id}")
    _pause()


def set_chk_status_flow() -> None:
    print("\n═══ Change Checklist Status ═══")
    try:
        c = _pick_checklist()
        new_status = _pick_from("New status",
                                   list(CHECKLIST_STATUSES),
                                   default=c.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_checklist_status(c.checklist_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{c.checklist_id} → {new_status}")
    _pause()


def delete_checklist_flow() -> None:
    print("\n═══ Delete Checklist ═══")
    try:
        c = _pick_checklist()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete checklist #{c.checklist_id}? "
              "Removes all its items. Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_checklist(c.checklist_id):
        print(f"\n  ✓ Deleted #{c.checklist_id}")
    _pause()


# ── Item flows ────────────────────────────────────────────────────

def tick_item_flow() -> None:
    print("\n═══ Tick Off Item ═══")
    try:
        c = _pick_checklist()
        it = _pick_item(c.checklist_id)
        who = _input("Completed by")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.tick(it.item_id, completed_by=who or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Ticked #{it.item_id} ({it.task_name})")
    _pause()


def untick_item_flow() -> None:
    print("\n═══ Un-tick Item ═══")
    try:
        c = _pick_checklist()
        it = _pick_item(c.checklist_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.untick(it.item_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Re-opened #{it.item_id}")
    _pause()


def set_item_status_flow() -> None:
    print("\n═══ Change Item Status ═══")
    try:
        c = _pick_checklist()
        it = _pick_item(c.checklist_id)
        new_status = _pick_from("New status", list(ITEM_STATUSES),
                                  default=it.status)
        who = _input("Completed by", default=it.completed_by or "") \
            if new_status in ("Done", "N/A") else ""
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_item_status(it.item_id, new_status,
                                completed_by=who or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{it.item_id} → {new_status}")
    _pause()


def new_item_flow() -> None:
    print("\n═══ New Item ═══")
    try:
        c = _pick_checklist()
        task = _input("Task name", allow_empty=False)
        cat = _pick_from("Category", list(CATEGORIES),
                            default=DEFAULT_CATEGORY)
        required = _yes_no("Required for completion?", default=True)
        due = _input("Due date (YYYY-MM-DD)")
        notes = _input("Notes")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        it = data.create_item({
            "checklist_id": c.checklist_id,
            "task_name": task, "category": cat,
            "required": required, "status": DEFAULT_ITEM_STATUS,
            "due_date": due or None, "notes": notes or None,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Added item #{it.item_id} {task!r}")
    _pause()


def edit_item_flow() -> None:
    print("\n═══ Edit Item ═══")
    try:
        c = _pick_checklist()
        it = _pick_item(c.checklist_id)
        task = _input("Task name", default=it.task_name,
                        allow_empty=False)
        cat = _pick_from("Category", list(CATEGORIES),
                            default=it.category)
        required = _yes_no("Required?", default=it.required)
        status = _pick_from("Status", list(ITEM_STATUSES),
                              default=it.status)
        due = _input("Due date", default=it.due_date or "")
        notes = _input("Notes", default=it.notes or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_item(it.item_id, {
            "task_name": task, "category": cat,
            "required": required, "status": status,
            "due_date": due or None, "notes": notes or None,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{it.item_id}")
    _pause()


def delete_item_flow() -> None:
    print("\n═══ Delete Item ═══")
    try:
        c = _pick_checklist()
        it = _pick_item(c.checklist_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete item #{it.item_id} ({it.task_name})? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_item(it.item_id):
        print(f"\n  ✓ Deleted #{it.item_id}")
    _pause()


# ── Templates / Summary ───────────────────────────────────────────

def show_templates() -> None:
    print("\n═══ Templates ═══")
    for name, items in TEMPLATES.items():
        req = sum(1 for _, _, r in items if r)
        print(f"\n  {name}  ({len(items)} items, {req} required)")
        for task, cat, required in items:
            mark = "*" if required else " "
            print(f"    {mark} [{cat}] {task}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Onboarding Summary ═══")
    try:
        win = int(_input("Upcoming-due window (days)", default="14"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    summ = data.summary(upcoming_window_days=win)
    print(f"\n  Total checklists   : {summ.total_checklists}")
    print(f"  Open               : {summ.open_count}")
    print(f"  Completed          : {summ.completed_count}")
    print(f"  Overdue            : {summ.overdue}")
    print(f"  Upcoming due ({win}d) : {summ.upcoming_due}")
    print(f"\n  Items total        : {summ.items_total}")
    print(f"  Items done         : {summ.items_done}")
    print(f"  Items overdue      : {summ.items_overdue}")
    print("\n  By checklist status:")
    for s in CHECKLIST_STATUSES:
        n = summ.by_status.get(s, 0)
        if n:
            print(f"    {s:<14} : {n}")
    print("\n  Items by category:")
    for c in CATEGORIES:
        n = summ.by_category.get(c, 0)
        if n:
            print(f"    {c:<24} : {n}")
    _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List Open",              list_open),
    ("List Overdue",           list_overdue),
    ("List All",               list_all),
    ("View Checklist",         view_checklist),
    ("New Checklist",          new_checklist),
    ("Edit Checklist",         edit_checklist),
    ("Change Status",          set_chk_status_flow),
    ("Delete Checklist",       delete_checklist_flow),
    ("─" * 6,                  lambda: None),
    ("Tick Off Item",          tick_item_flow),
    ("Un-tick Item",           untick_item_flow),
    ("Change Item Status",     set_item_status_flow),
    ("New Item",               new_item_flow),
    ("Edit Item",              edit_item_flow),
    ("Delete Item",            delete_item_flow),
    ("─" * 6,                  lambda: None),
    ("Show Templates",         show_templates),
    ("Summary",                summary_flow),
]


def run() -> None:
    while True:
        print("\n── Onboarding ──")
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
            logger.exception("Onboarding CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Onboarding":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Onboarding CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
