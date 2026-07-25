"""CLI flows for Primary School To-Do."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable

from education_system.systems.primary.domain.operations.todo import todo as data
from education_system.systems.primary.domain.operations.todo.todo import (
    DEFAULT_PRIORITY,
    DEFAULT_STATUS,
    PRIORITIES,
    STATUSES,
    Todo,
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


# ── Print helpers ──────────────────────────────────────────────────

def _print_rows(rows: list[Todo]) -> None:
    if not rows:
        print("\n  (no todos)")
        return
    print()
    print(f"  {'#':>4}  {'Status':<12}  {'Pri':<7}  {'Due':<10}  "
          f"{'Owner':<14}  {'Assignee':<14}  Title")
    print("  " + "-" * 110)
    for t in rows:
        due = t.due_date or "—"
        if t.is_overdue:
            due = f"!{due}"
        print(f"  {t.todo_id:>4}  {t.status:<12}  {t.priority:<7}  "
              f"{due:<10}  {(t.owner or '—')[:14]:<14}  "
              f"{(t.assignee or '—')[:14]:<14}  {t.title[:48]}")
    print(f"\n  {len(rows)} todo(s).")


# ── Flows ──────────────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All To-Dos ═══")
    _print_rows(data.list_todos())
    _row_action_loop()


def list_open() -> None:
    print("\n═══ Open To-Dos ═══")
    _print_rows(data.list_todos(open_only=True))
    _row_action_loop()


def list_overdue() -> None:
    print("\n═══ Overdue To-Dos ═══")
    _print_rows(data.list_todos(overdue_only=True))
    _row_action_loop()


def list_due_today() -> None:
    print("\n═══ Due Today ═══")
    _print_rows(data.list_todos(due_on=_date.today().isoformat()))
    _row_action_loop()


def filter_todos() -> None:
    print("\n═══ Filter To-Dos ═══")
    print("  (blank to skip; 'cancel' to abort)\n")
    try:
        status = _input(f"Status ({'/'.join(STATUSES)})") or None
        priority = _input(f"Priority ({'/'.join(PRIORITIES)})") or None
        owner = _input("Owner") or None
        assignee = _input("Assignee") or None
        category = _input("Category") or None
        open_only = _yes_no("Open only?", default=False)
        overdue_only = _yes_no("Overdue only?", default=False)
        due_by = _input("Due by (YYYY-MM-DD)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_todos(
            status=status, priority=priority, owner=owner,
            assignee=assignee, category=category,
            open_only=open_only, overdue_only=overdue_only,
            due_by=due_by,
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_rows(rows)
    _row_action_loop()


def search_todos() -> None:
    print("\n═══ Search To-Dos ═══")
    try:
        q = _input("Query", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_rows(data.search_todos(q))
    _row_action_loop()


def view_todo(todo_id: int | None = None) -> None:
    print("\n═══ View To-Do ═══")
    try:
        tid = todo_id if todo_id is not None else int(
            _input("Todo ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    t = data.get_todo(tid)
    if t is None:
        print(f"  ✗ No todo #{tid}")
        _pause()
        return
    print()
    print(f"    Todo ID     : #{t.todo_id}")
    print(f"    Title       : {t.title}")
    print(f"    Status      : {t.status}")
    print(f"    Priority    : {t.priority}")
    print(f"    Owner       : {t.owner or '—'}")
    print(f"    Assignee    : {t.assignee or '—'}")
    print(f"    Category    : {t.category or '—'}")
    print(f"    Due date    : {t.due_date or '—'}"
          f"{'  (overdue)' if t.is_overdue else ''}")
    print(f"    Completed at: {t.completed_at or '—'}")
    print(f"    Created     : {t.created_at}")
    print(f"    Updated     : {t.updated_at}")
    if t.description:
        print()
        print("    Description:")
        for line in t.description.splitlines() or [""]:
            print(f"      {line}")
    _pause()


def _collect_form(existing: Todo | None) -> dict[str, Any]:
    is_edit = existing is not None
    p: dict[str, Any] = {}
    p["title"] = _input("Title",
                          default=existing.title if is_edit else "",
                          allow_empty=False)
    p["description"] = _input(
        "Description",
        default=(existing.description or "") if is_edit else "")
    p["owner"] = _input(
        "Owner",
        default=(existing.owner if is_edit else ""))
    p["assignee"] = _input(
        "Assignee (optional)",
        default=(existing.assignee or "") if is_edit else "")
    p["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS))
    p["priority"] = _pick_from(
        "Priority", list(PRIORITIES),
        default=(existing.priority if is_edit else DEFAULT_PRIORITY))
    p["category"] = _input(
        "Category (optional)",
        default=(existing.category or "") if is_edit else "")
    p["due_date"] = _input(
        "Due date (YYYY-MM-DD, blank=none)",
        default=(existing.due_date or "") if is_edit else "")
    return p


def new_todo() -> None:
    print("\n═══ New To-Do ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        t = data.create_todo(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created todo #{t.todo_id} ({t.title})")
    _pause()


def edit_todo(todo_id: int | None = None) -> None:
    print("\n═══ Edit To-Do ═══")
    try:
        tid = todo_id if todo_id is not None else int(
            _input("Todo ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_todo(tid)
    if existing is None:
        print(f"  ✗ No todo #{tid}")
        _pause()
        return
    try:
        payload = _collect_form(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_todo(tid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{tid}")
    _pause()


def mark_done_flow(todo_id: int | None = None) -> None:
    print("\n═══ Mark Done ═══")
    try:
        tid = todo_id if todo_id is not None else int(
            _input("Todo ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        data.mark_done(tid)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{tid} marked Done")
    _pause()


def reopen_flow(todo_id: int | None = None) -> None:
    print("\n═══ Reopen ═══")
    try:
        tid = todo_id if todo_id is not None else int(
            _input("Todo ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        data.reopen(tid)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{tid} reopened")
    _pause()


def set_status_flow(todo_id: int | None = None) -> None:
    print("\n═══ Set Status ═══")
    try:
        tid = todo_id if todo_id is not None else int(
            _input("Todo ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_todo(tid)
    if existing is None:
        print(f"  ✗ No todo #{tid}")
        _pause()
        return
    try:
        status = _pick_from("Status", list(STATUSES),
                              default=existing.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(tid, status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{tid} status = {status}")
    _pause()


def delete_todo_flow(todo_id: int | None = None) -> None:
    print("\n═══ Delete To-Do ═══")
    try:
        tid = todo_id if todo_id is not None else int(
            _input("Todo ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_todo(tid)
    if existing is None:
        print(f"  ✗ No todo #{tid}")
        _pause()
        return
    if _input(f"Delete #{tid} ({existing.title!r})? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_todo(tid):
        print(f"\n  ✓ Deleted #{tid}")
    _pause()


def clear_completed_flow() -> None:
    print("\n═══ Clear Completed ═══")
    try:
        owner = _input("Owner (blank = everyone)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if not _yes_no("Permanently remove all Done/Cancelled todos?",
                     default=False):
        print("\n  Cancelled.")
        return
    n = data.clear_completed(owner=owner or None)
    print(f"\n  ✓ Removed {n} todo(s).")
    _pause()


def summary_flow() -> None:
    print("\n═══ To-Do Summary ═══")
    try:
        owner = _input("Owner (blank = everyone)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    s = data.summary(owner=owner or None)
    print(f"\n  Total       : {s.total}")
    print(f"  Open        : {s.open}")
    print(f"  In Progress : {s.in_progress}")
    print(f"  Blocked     : {s.blocked}")
    print(f"  Done        : {s.done}")
    print(f"  Cancelled   : {s.cancelled}")
    print()
    print(f"  Overdue     : {s.overdue}")
    print(f"  Due today   : {s.due_today}")
    print(f"  Due in 7d   : {s.due_within_7d}")
    print("\n  By priority:")
    for p in PRIORITIES:
        print(f"    {p:<10} : {s.by_priority.get(p, 0)}")
    if s.by_owner:
        print("\n  By owner:")
        for o, n in sorted(s.by_owner.items(), key=lambda x: -x[1])[:10]:
            print(f"    {o[:24]:<24} : {n}")
    if s.by_category:
        print("\n  By category:")
        for c, n in sorted(s.by_category.items(), key=lambda x: -x[1])[:10]:
            print(f"    {c[:24]:<24} : {n}")
    _pause()


# ── Row-action loop ───────────────────────────────────────────────

def _row_action_loop() -> None:
    print()
    print("  Actions:  V) View   E) Edit   D) Done   R) Reopen   "
          "S) Set status   X) Delete   (Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in ("v", "e", "d", "r", "s", "x"):
            print("    Pick V, E, D, R, S, X, or Enter.")
            continue
        try:
            raw = _input("Todo ID", allow_empty=False)
        except _UserAbort:
            return
        try:
            tid = int(raw)
        except ValueError:
            print("    Todo ID must be a whole number.")
            continue
        if choice == "v":
            view_todo(tid)
        elif choice == "e":
            edit_todo(tid)
        elif choice == "d":
            mark_done_flow(tid)
        elif choice == "r":
            reopen_flow(tid)
        elif choice == "s":
            set_status_flow(tid)
        elif choice == "x":
            delete_todo_flow(tid)
        return


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Open To-Dos",       list_open),
    ("All To-Dos",        list_all),
    ("Overdue",           list_overdue),
    ("Due Today",         list_due_today),
    ("Filter",            filter_todos),
    ("Search",            search_todos),
    ("View To-Do",        view_todo),
    ("New To-Do",         new_todo),
    ("Edit To-Do",        edit_todo),
    ("Mark Done",         mark_done_flow),
    ("Reopen",            reopen_flow),
    ("Set Status",        set_status_flow),
    ("Delete To-Do",      delete_todo_flow),
    ("Clear Completed",   clear_completed_flow),
    ("Summary",           summary_flow),
]


def run() -> None:
    while True:
        print("\n── To-Do ──")
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
            logger.exception("To-do CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "To-Do":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("To-do CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
