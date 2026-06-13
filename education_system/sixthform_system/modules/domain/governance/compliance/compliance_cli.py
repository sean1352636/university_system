"""CLI flows for the Sixth Form Compliance register."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable

from education_system.sixthform_system.modules.domain.governance.compliance import compliance as data
from education_system.sixthform_system.modules.domain.governance.compliance.compliance import (
    CATEGORIES,
    DEFAULT_FREQUENCY,
    DEFAULT_STATUS,
    DERIVED_STATUSES,
    FREQUENCIES,
    STATUSES,
    Item,
    ItemView,
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


def _pick(label: str, options: list[str],
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
            print("    Enter a number (or 'cancel').")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


# ── Print helpers ──────────────────────────────────────────────────

def _print_views(views: list[ItemView]) -> None:
    if not views:
        print("\n  (no items)")
        return
    print()
    print(f"  {'#':>4}  {'Category':<14}  {'Title':<32}  "
          f"{'Owner':<14}  {'Next':<10}  {'Status':<12}")
    print("  " + "-" * 92)
    for v in views:
        it = v.item
        nxt = it.next_review or it.due_date or "—"
        title = (it.title or "")[:32]
        owner = (it.owner or "—")[:14]
        print(f"  {it.item_id:>4}  {it.category:<14}  {title:<32}  "
              f"{owner:<14}  {nxt:<10}  {v.derived_status:<12}")
    print(f"\n  {len(views)} item(s).")


def _print_summary() -> None:
    try:
        s = data.summary()
    except Exception as e:
        logger.exception("compliance summary failed")
        print(f"  ✗ {e}")
        return
    print(f"\n  Total items     : {s.total}")
    print(f"  Overdue         : {s.overdue}")
    print(f"  Due within 30d  : {s.due_soon}")
    print(f"  Without a date  : {s.no_review_date}")
    print("\n  By category:")
    for cat in CATEGORIES:
        print(f"    {cat:<16}  {s.by_category.get(cat, 0):>4}")
    print("\n  By status:")
    for st in DERIVED_STATUSES:
        print(f"    {st:<16}  {s.by_status.get(st, 0):>4}")


# ── Flows ──────────────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ Compliance Register ═══")
    views = data.list_views()
    _print_views(views)
    _pause()


def list_overdue() -> None:
    print("\n═══ Compliance — Overdue ═══")
    views = data.list_views(overdue_only=True)
    _print_views(views)
    _pause()


def filter_items() -> None:
    print("\n═══ Filter Compliance Items ═══")
    print("  (blank = skip filter)")
    try:
        cat_raw = _input(f"Category ({'/'.join(CATEGORIES)})")
        status_raw = _input(f"Status ({'/'.join(STATUSES)})")
        owner = _input("Owner contains")
        query = _input("Title/notes contains")
        overdue = _input("Overdue only? (y/n)", default="n").lower() in ("y", "yes")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    kwargs: dict[str, Any] = {"overdue_only": overdue}
    if cat_raw:
        if cat_raw not in CATEGORIES:
            print(f"  ✗ Category must be one of {', '.join(CATEGORIES)}.")
            _pause()
            return
        kwargs["category"] = cat_raw
    if status_raw:
        if status_raw not in STATUSES:
            print(f"  ✗ Status must be one of {', '.join(STATUSES)}.")
            _pause()
            return
        kwargs["status"] = status_raw
    if owner:
        kwargs["owner"] = owner
    if query:
        kwargs["query"] = query
    try:
        views = data.list_views(**kwargs)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_views(views)
    _pause()


def view_item_flow() -> None:
    print("\n═══ View Compliance Item ═══")
    try:
        rid = int(_input("Item ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("  ✗ Item ID must be a number.")
        _pause()
        return
    v = data.view_item(rid)
    if v is None:
        print(f"  ✗ No item #{rid}")
        _pause()
        return
    it = v.item
    print(f"\n  #{it.item_id}  {it.category} — {it.title}")
    print(f"  Owner         : {it.owner or '—'}")
    print(f"  Stored status : {it.status}")
    print(f"  Derived status: {v.derived_status}")
    print(f"  Frequency     : {it.frequency}")
    print(f"  Due date      : {it.due_date or '—'}")
    print(f"  Last review   : {it.last_review or '—'}")
    print(f"  Next review   : {it.next_review or '—'}")
    if v.days_until_due is not None:
        if v.days_until_due < 0:
            print(f"  Overdue by    : {-v.days_until_due} day(s)")
        else:
            print(f"  Due in        : {v.days_until_due} day(s)")
    print(f"  Created       : {it.created_at}")
    print(f"  Updated       : {it.updated_at}")
    if it.notes:
        print(f"\n  Notes:\n    {it.notes}")
    _pause()


def new_item() -> None:
    print("\n═══ New Compliance Item ═══")
    try:
        category = _pick("Category", list(CATEGORIES), default="Policy")
        title = _input("Title", allow_empty=False)
        owner = _input("Owner (optional)")
        status = _pick("Status", list(STATUSES), default=DEFAULT_STATUS)
        frequency = _pick("Frequency", list(FREQUENCIES),
                           default=DEFAULT_FREQUENCY)
        due_date = _input("Due date YYYY-MM-DD (optional)")
        last_review = _input("Last review YYYY-MM-DD (optional)")
        next_review = _input("Next review YYYY-MM-DD (optional)")
        notes = _input("Notes (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        item = data.create_item({
            "category": category, "title": title, "owner": owner,
            "status": status, "frequency": frequency,
            "due_date": due_date or None,
            "last_review": last_review or None,
            "next_review": next_review or None,
            "notes": notes or None,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created #{item.item_id} — {item.title}")
    _pause()


def edit_item_flow() -> None:
    print("\n═══ Edit Compliance Item ═══")
    try:
        rid = int(_input("Item ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("  ✗ Item ID must be a number.")
        _pause()
        return
    existing = data.get_item(rid)
    if existing is None:
        print(f"  ✗ No item #{rid}")
        _pause()
        return
    print(f"\n  Editing #{existing.item_id} — {existing.title}")
    print("  (press Enter to keep existing)")
    try:
        category = _pick("Category", list(CATEGORIES), default=existing.category)
        title = _input("Title", default=existing.title)
        owner = _input("Owner", default=existing.owner or "")
        status = _pick("Status", list(STATUSES), default=existing.status)
        frequency = _pick("Frequency", list(FREQUENCIES),
                           default=existing.frequency)
        due_date = _input("Due date YYYY-MM-DD", default=existing.due_date or "")
        last_review = _input("Last review YYYY-MM-DD",
                              default=existing.last_review or "")
        next_review = _input("Next review YYYY-MM-DD",
                              default=existing.next_review or "")
        notes = _input("Notes", default=existing.notes or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        item = data.update_item(rid, {
            "category": category, "title": title, "owner": owner,
            "status": status, "frequency": frequency,
            "due_date": due_date or None,
            "last_review": last_review or None,
            "next_review": next_review or None,
            "notes": notes or None,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{item.item_id}")
    _pause()


def mark_reviewed_flow() -> None:
    print("\n═══ Mark Compliance Item Reviewed ═══")
    try:
        rid = int(_input("Item ID", allow_empty=False))
        when = _input("Reviewed on YYYY-MM-DD",
                       default=_date.today().isoformat())
        notes = _input("Notes (optional)")
    except (ValueError, _UserAbort):
        print("  ✗ Cancelled or invalid input.")
        _pause()
        return
    try:
        item = data.mark_reviewed(rid, reviewed_on=when,
                                    notes=notes or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    nxt = item.next_review or "—"
    print(f"\n  ✓ Marked #{item.item_id} reviewed. Next review: {nxt}")
    _pause()


def delete_item_flow() -> None:
    print("\n═══ Delete Compliance Item ═══")
    try:
        rid = int(_input("Item ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("  ✗ Item ID must be a number.")
        _pause()
        return
    existing = data.get_item(rid)
    if existing is None:
        print(f"  ✗ No item #{rid}")
        _pause()
        return
    confirm = _input(
        f"Delete '#{rid} — {existing.title}'? Type 'yes' to confirm",
        default="no")
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_item(rid):
        print(f"\n  ✓ Deleted #{rid}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Compliance Summary ═══")
    _print_summary()
    _pause()


# ── Submenu dispatch ───────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List All",          list_all),
    ("List Overdue",      list_overdue),
    ("Filter / Search",   filter_items),
    ("View Item",         view_item_flow),
    ("New Item",          new_item),
    ("Edit Item",         edit_item_flow),
    ("Mark Reviewed",     mark_reviewed_flow),
    ("Delete Item",       delete_item_flow),
    ("Summary",           summary_flow),
]


def run() -> None:
    while True:
        print("\n── Compliance ──")
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
            logger.exception("Compliance CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Compliance":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Compliance CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
