"""CLI handlers for cover arrangements."""

from __future__ import annotations

import datetime as _dt
import functools
import logging
from typing import Callable

from education_system.systems.primary.domain.staff.cover import (
    cover as data,
)
from education_system.systems.primary.domain.staff.cover.cover import (
    STATUSES, MIN_PERIOD, MAX_PERIOD,
)
from education_system.systems.primary.domain.academics.subjects import (
    subjects as subjects_data,
)
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


def _today() -> str:
    return _dt.date.today().isoformat()


def _print_table(rows: list[data.CoverArrangement]) -> None:
    if not rows:
        print("  (no cover arrangements)")
        return
    print(f"  {'ID':<4} {'Date':<10} {'P':<2} {'Yr':<3} {'Form':<5} "
          f"{'Subj':<6} {'Absent':<16} {'Cover':<16} "
          f"{'Room':<6} {'Status':<10}")
    print(f"  {'-'*4} {'-'*10} {'-'*2} {'-'*3} {'-'*5} {'-'*6} {'-'*16} "
          f"{'-'*16} {'-'*6} {'-'*10}")
    for c in rows:
        print(f"  {c.cover_id:<4} {c.date:<10} {c.period:<2} "
              f"{(c.year_group or '-'):<3} {(c.form_group or '-'):<5} "
              f"{(c.subject_code or '-'):<6} "
              f"{c.absent_teacher[:16]:<16} "
              f"{(c.cover_teacher or '-')[:16]:<16} "
              f"{(c.room or '-')[:6]:<6} {c.status:<10}")


@_safe
def open_cover() -> None:
    logger.debug("CLI: open_cover")
    while True:
        counts = data.status_counts()
        total = sum(counts.values())
        print("\n  ── Cover ──")
        print(f"  Total: {total}   "
              + "   ".join(f"{s}: {counts[s]}" for s in STATUSES))
        print("\n   1) New arrangement")
        print("   2) List arrangements")
        print("   3) View arrangement")
        print("   4) Edit arrangement")
        print("   5) Assign cover teacher")
        print("   6) Set status")
        print("   7) Daily load")
        print("   8) Delete arrangement")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _new,
            "2": _list,
            "3": _view,
            "4": _edit,
            "5": _assign,
            "6": _set_status,
            "7": _daily_load,
            "8": _delete,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect(existing: data.CoverArrangement | None = None) -> dict[str, str]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")

    f: dict[str, str] = {}
    f["date"]           = ask("Date (YYYY-MM-DD)",
                               existing.date if existing else _today())
    f["period"]         = ask(f"Period ({MIN_PERIOD}-{MAX_PERIOD})",
                               existing.period if existing else None)
    f["absent_teacher"] = ask("Absent teacher",
                               existing.absent_teacher if existing else None)
    f["cover_teacher"]  = ask("Cover teacher (blank if unassigned)",
                               existing.cover_teacher if existing else None)
    f["year_group"]     = ask(f"Year ({'/'.join(YEAR_GROUPS)}, blank ok)",
                               existing.year_group if existing else None)
    f["form_group"]     = ask("Form (blank ok)",
                               existing.form_group if existing else None)
    if not existing:
        print("  Active subjects (optional):")
        for s in subjects_data.list_all(active_only=True)[:20]:
            print(f"    #{s.subject_id:<4} {s.code:<8} {s.name}")
    f["subject_id"]     = ask("Subject ID (blank ok)",
                               existing.subject_id if existing else None)
    f["room"]           = ask("Room",
                               existing.room if existing else None)
    f["status"]         = ask(f"Status ({'/'.join(STATUSES)})",
                               existing.status if existing else "Pending")
    f["reason"]         = ask("Reason (e.g. sickness)",
                               existing.reason if existing else None)
    f["notes"]          = ask("Notes",
                               existing.notes if existing else None)
    return f


@_safe
def _new() -> None:
    print("\n  ── New Cover Arrangement ──")
    fields = _collect()
    c = data.create(fields)
    print(f"  Created cover #{c.cover_id}  {c.date} P{c.period} "
          f"absent={c.absent_teacher} status={c.status}")


@_safe
def _list() -> None:
    print("\n  Filter — exact date (blank for any): ")
    date = _prompt("  Date: ") or None
    df = _prompt("  From date (blank): ") or None
    dt = _prompt("  To date (blank): ") or None
    teacher = _prompt("  Absent teacher (blank): ") or None
    cover = _prompt("  Cover teacher (blank): ") or None
    print(f"  Status ({'/'.join(STATUSES)}) or blank.")
    status = _prompt("  Status: ") or None
    rows = data.list_arrangements(date=date, date_from=df, date_to=dt,
                                   teacher=teacher, cover_teacher=cover,
                                   status=status)
    print(f"\n  {len(rows)} arrangement(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


def _ask_id() -> int | None:
    cid = _prompt("  Cover ID: ")
    if not cid:
        return None
    try:
        return int(cid)
    except ValueError:
        print("  Cover ID must be a number.")
        return None


@_safe
def _view() -> None:
    cid = _ask_id()
    if cid is None:
        return
    c = data.get(cid)
    if c is None:
        print("  No arrangement with that ID.")
        return
    print(f"\n  ── Cover #{c.cover_id} ──")
    print(f"  Date/period:   {c.date}  P{c.period}")
    print(f"  Absent:        {c.absent_teacher}")
    print(f"  Cover:         {c.cover_teacher or '-'}")
    print(f"  Year/form:     {c.year_group or '-'}"
          f"{('/' + c.form_group) if c.form_group else ''}")
    print(f"  Subject:       {c.subject_code or '-'}"
          f"{(' — ' + c.subject_name) if c.subject_name else ''}")
    print(f"  Room:          {c.room or '-'}")
    print(f"  Status:        {c.status}")
    print(f"  Reason:        {c.reason or '-'}")
    print(f"  Notes:         {c.notes or '-'}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _edit() -> None:
    cid = _ask_id()
    if cid is None:
        return
    existing = data.get(cid)
    if existing is None:
        print("  No arrangement with that ID.")
        return
    print("  Press Enter to keep existing value.")
    fields = _collect(existing)
    c = data.update(cid, fields)
    print(f"  Updated cover #{c.cover_id} (status {c.status})")


@_safe
def _assign() -> None:
    cid = _ask_id()
    if cid is None:
        return
    c = data.get(cid)
    if c is None:
        print("  No arrangement with that ID.")
        return
    teacher = _prompt(f"  Cover teacher [{c.cover_teacher or ''}]: ")
    if not teacher:
        if c.cover_teacher:
            teacher = c.cover_teacher
        else:
            print("  No teacher entered.")
            return
    rec = data.assign(cid, teacher)
    print(f"  Assigned {rec.cover_teacher} (status {rec.status})")


@_safe
def _set_status() -> None:
    cid = _ask_id()
    if cid is None:
        return
    c = data.get(cid)
    if c is None:
        print("  No arrangement with that ID.")
        return
    print(f"  Current status: {c.status}")
    print(f"  Allowed: {', '.join(STATUSES)}")
    new = _prompt("  New status: ")
    if not new:
        return
    c = data.set_status(cid, new)
    print(f"  Status now: {c.status}")


@_safe
def _daily_load() -> None:
    date_s = _prompt(f"  Date (YYYY-MM-DD) [{_today()}]: ") or _today()
    load = data.daily_load(date_s)
    print(f"\n  ── Cover load: {load['date']} ──")
    print(f"  Total: {load['total']}   Unassigned: {load['unassigned']}")
    print("  By status: "
          + "   ".join(f"{s}: {load['by_status'][s]}" for s in STATUSES))
    if load["by_cover"]:
        print("\n  By cover teacher:")
        for teacher, n in sorted(load["by_cover"].items(),
                                  key=lambda kv: -kv[1]):
            print(f"    {teacher}: {n}")
    if load["records"]:
        print("\n  Detail:")
        _print_table(load["records"])
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete() -> None:
    cid = _ask_id()
    if cid is None:
        return
    c = data.get(cid)
    if c is None:
        print("  No arrangement with that ID.")
        return
    confirm = _prompt(
        f"  Delete cover #{cid} ({c.date} P{c.period} "
        f"absent={c.absent_teacher})? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    if data.delete(cid):
        print(f"  Deleted cover #{cid}.")
    else:
        print("  Could not delete.")


_DISPATCH = {"Cover": open_cover}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching cover CLI label: %s", label)
    handler()
    return True
