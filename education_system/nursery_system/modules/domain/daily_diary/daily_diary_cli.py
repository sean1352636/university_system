"""CLI flow for Daily Diary (Nursery System)."""

from __future__ import annotations

import datetime as _dt
import functools
import logging
from typing import Callable

from education_system.nursery_system.modules.domain.daily_diary import (
    daily_diary as data,
)
from education_system.nursery_system.modules.domain.daily_diary.daily_diary import (
    MOODS,
    ValidationError,
)

logger = logging.getLogger(__name__)


def _prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _safe(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            print(f"  ✗ {e}")
        except Exception as e:  # noqa: BLE001
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _print_table(rows: list[data.DiaryEntry]) -> None:
    if not rows:
        print("  (no diary entries)")
        return
    print(f"  {'ID':<8} {'Date':<12} {'Child':<22} {'Mood':<10} {'Highlights'}")
    print(f"  {'-'*8} {'-'*12} {'-'*22} {'-'*10} {'-'*24}")
    for r in rows:
        print(f"  {r.entry_id:<8} {r.entry_date:<12} "
              f"{(r.child_name or '-')[:22]:<22} {(r.mood or '-')[:10]:<10} "
              f"{(r.highlights or '-')[:24]}")


def _print_detail(r: data.DiaryEntry) -> None:
    print(f"\n  ── Diary entry {r.entry_id} ──")
    print(f"  Child:       {r.child_name or '-'} ({r.pupil_id})")
    print(f"  Date:        {r.entry_date}")
    print(f"  Mood:        {r.mood or '-'}")
    print(f"  Activities:  {r.activities or '-'}")
    print(f"  Highlights:  {r.highlights or '-'}")
    print(f"  Notes:       {r.notes or '-'}")
    staff = f"{r.staff_name} ({r.staff_id})" if r.staff_id else "-"
    print(f"  Staff:       {staff}")


def _pick(choices: list[tuple[str, str]], label: str) -> str | None:
    """Numbered picker; returns selected id, or None if cancelled/empty."""
    if not choices:
        print(f"  (no {label} available)")
        return None
    print(f"  {label.capitalize()}:")
    for i, (_id, text) in enumerate(choices, 1):
        print(f"    {i}) {text}")
    raw = _prompt(f"  Select {label} (number): ")
    if not raw:
        return None
    try:
        idx = int(raw)
    except ValueError:
        print("  Invalid selection.")
        return None
    if 1 <= idx <= len(choices):
        return choices[idx - 1][0]
    print("  Invalid selection.")
    return None


def _ask_mood(current: str | None = None) -> str:
    print("  Moods: " + ", ".join(MOODS) + " (or type your own)")
    cur = f" [{current}]" if current else ""
    v = _prompt(f"  Mood{cur}: ")
    return v if v else (current or "")


def _collect_fields(existing: data.DiaryEntry | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    fields: dict[str, str] = {}
    today = _dt.date.today().isoformat()
    fields["entry_date"] = ask("Date (YYYY-MM-DD)",
                               existing.entry_date if existing else today)
    fields["mood"] = _ask_mood(existing.mood if existing else None)
    fields["activities"] = ask("Activities",
                               existing.activities if existing else None)
    fields["highlights"] = ask("Highlights",
                               existing.highlights if existing else None)
    fields["notes"] = ask("Notes", existing.notes if existing else None)
    staff_choices = data.list_staff_choices()
    keep = existing.staff_id if existing else None
    prompt_lbl = "staff member (Enter to keep/skip)" if existing else \
        "staff member (Enter to skip)"
    sid = _pick(staff_choices, prompt_lbl)
    fields["staff_id"] = sid if sid is not None else (keep or "")
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: daily_diary open_manager")
    date_filter: str | None = None
    while True:
        scope = f"date {date_filter}" if date_filter else "all dates"
        print(f"\n  ── Daily Diary ({scope}) ──")
        _print_table(data.list_records(entry_date=date_filter))
        print("\n   1) List entries    2) Add entry    3) View entry")
        print("   4) Edit entry      5) Delete entry  0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        if choice == "1":
            df = _prompt("  Filter by date (YYYY-MM-DD, blank for all): ")
            date_filter = df or None
        elif choice == "2":
            open_add()
        elif choice == "3":
            rid = _prompt("  Entry ID: ")
            r = data.get_record(rid)
            if r is None:
                print("  No entry with that ID.")
            else:
                _print_detail(r)
                _prompt("  Press Enter to continue...")
        elif choice == "4":
            open_edit()
        elif choice == "5":
            open_delete()
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    logger.debug("CLI: daily_diary open_add")
    print("\n  ── Add Diary Entry ──")
    pid = _pick(data.list_pupil_choices(), "child")
    if not pid:
        print("  Cancelled.")
        return
    fields = _collect_fields()
    fields["pupil_id"] = pid
    r = data.create_record(fields)
    print(f"\n  Created diary entry {r.entry_id} for {r.child_name} "
          f"({r.entry_date}).")


@_safe
def open_edit() -> None:
    logger.debug("CLI: daily_diary open_edit")
    rid = _prompt("  Entry ID: ")
    if not rid:
        print("  Cancelled.")
        return
    existing = data.get_record(rid)
    if existing is None:
        print("  No entry with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    r = data.update_record(rid, fields)
    print(f"\n  Updated diary entry {r.entry_id}.")


@_safe
def open_delete() -> None:
    logger.debug("CLI: daily_diary open_delete")
    rid = _prompt("  Entry ID to delete: ")
    if not rid:
        print("  Cancelled.")
        return
    existing = data.get_record(rid)
    if existing is None:
        print("  No entry with that ID.")
        return
    confirm = _prompt(
        f"  Delete diary entry {rid} for {existing.child_name}? (y/N): "
    ).lower()
    if confirm != "y":
        print("  Cancelled.")
        return
    if data.delete_record(rid):
        print(f"  Deleted entry {rid}.")
    else:
        print("  Could not delete (already removed?).")


_DISPATCH = {"Daily Diary": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching daily_diary CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
