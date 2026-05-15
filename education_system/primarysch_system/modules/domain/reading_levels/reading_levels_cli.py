"""CLI handlers for reading levels in the Primary School System."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.primarysch_system.modules.domain.reading_levels import (
    reading_levels as data,
)
from education_system.primarysch_system.modules.domain.reading_levels.reading_levels import (
    BANDS, STATUSES,
)
from education_system.primarysch_system.modules.domain.pupils.pupils import (
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


def _print_summary() -> None:
    counts = data.band_summary()
    total = sum(counts.values())
    print(f"  Tracked: {total}")
    nonzero = [(b, n) for b, n in counts.items() if n > 0]
    if nonzero:
        print("  " + "   ".join(f"{b}: {n}" for b, n in nonzero))


def _print_table(rows: list[tuple]) -> None:
    if not rows:
        print("  (no pupils)")
        return
    print(f"  {'Pupil ID':<10} {'Name':<24} {'Year':<5} "
          f"{'Band':<14} {'Status':<8} {'Last assessed':<14}")
    print(f"  {'-'*10} {'-'*24} {'-'*5} {'-'*14} {'-'*8} {'-'*14}")
    for pupil, rec in rows:
        band = rec.band if rec else "-"
        st = rec.status if rec else "-"
        la = (rec.last_assessed if rec else "") or "-"
        print(f"  {pupil.pupil_id:<10} {pupil.full_name[:24]:<24} "
              f"{pupil.year_group:<5} {band[:14]:<14} {st:<8} {la:<14}")


@_safe
def open_reading_levels() -> None:
    logger.debug("CLI: open_reading_levels")
    while True:
        print("\n  -- Reading Levels --")
        _print_summary()
        print("\n   1) List all pupils")
        print("   2) Filter by year / band / status")
        print("   3) View pupil + history")
        print("   4) Record assessment")
        print("   5) Delete assessment from history")
        print("   6) Clear pupil's current record")
        print("   7) Show band progression")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice == "0" or choice == "":
            return
        actions = {
            "1": _list_all,
            "2": _list_filtered,
            "3": _view,
            "4": _record,
            "5": _delete_assessment,
            "6": _clear_pupil,
            "7": _show_bands,
        }
        action = actions.get(choice)
        if action is None:
            print("  Invalid selection.")
            continue
        action()


@_safe
def _list_all() -> None:
    rows = data.list_records()
    print(f"\n  {len(rows)} pupil(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _list_filtered() -> None:
    print(f"  Year groups: {', '.join(YEAR_GROUPS)} (blank for any)")
    yg = _prompt("  Year: ").strip() or None
    print(f"  Bands: {', '.join(BANDS)} (blank for any)")
    band = _prompt("  Band: ").strip() or None
    print(f"  Statuses: {', '.join(STATUSES)} (blank for any)")
    st = _prompt("  Status: ").strip().lower() or None
    rows = data.list_records(year_group=yg, band=band, status=st)
    print(f"\n  {len(rows)} pupil(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _view() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    rec = data.get_record(pid)
    from education_system.primarysch_system.modules.domain.pupils import pupils as pupils_data
    pupil = pupils_data.get_pupil(pid)
    if pupil is None:
        print(f"  No pupil with id {pid}")
        return
    print(f"\n  -- Reading: {pupil.full_name} ({pupil.pupil_id}) --")
    print(f"  Year:           {pupil.year_group}")
    if rec is None:
        print("  No reading-level record yet.")
    else:
        print(f"  Current band:   {rec.band} ({rec.status})")
        print(f"  Last assessed:  {rec.last_assessed or '-'}")
        print(f"  Current book:   {rec.book_title or '-'}")
        print(f"  Notes:          {rec.notes or '-'}")
        print(f"  Updated:        {rec.updated_at or '-'}")
    history = data.list_history(pid)
    print(f"\n  History ({len(history)}):")
    if not history:
        print("    (no assessments)")
    else:
        for h in history:
            print(f"    #{h.assessment_id} {h.assessed_on}  {h.band} "
                  f"({h.status})  {h.book_title or ''}  {h.notes or ''}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _record() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    print(f"  Bands: {', '.join(BANDS)}")
    band = _prompt("  Band: ")
    print(f"  Statuses: {', '.join(STATUSES)}")
    status = _prompt("  Status: ").lower()
    assessed_on = _prompt("  Assessed on YYYY-MM-DD (blank for today): ")
    book = _prompt("  Current book title (optional): ")
    notes = _prompt("  Notes (optional): ")
    rec = data.record_assessment(pid, {
        "band": band, "status": status, "assessed_on": assessed_on,
        "book_title": book, "notes": notes,
    })
    print(f"  Recorded: pupil {pid} -> {rec.band} ({rec.status})")
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete_assessment() -> None:
    raw = _prompt("  Assessment ID to delete: ")
    if not raw or not raw.isdigit():
        return
    confirm = _prompt(f"  Delete assessment #{raw}? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    ok = data.delete_assessment(int(raw))
    print(f"  {'Deleted' if ok else 'No such assessment'}: #{raw}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _clear_pupil() -> None:
    pid = _prompt("  Pupil ID to clear: ")
    if not pid:
        return
    confirm = _prompt(f"  Clear current reading-level record for {pid}? "
                     f"(history is kept) (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    ok = data.clear_pupil(pid)
    print(f"  {'Cleared' if ok else 'No record to clear'}: {pid}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _show_bands() -> None:
    print("\n  -- Book band progression (lowest to highest) --")
    for i, b in enumerate(BANDS, 1):
        print(f"   {i:2d}) {b}")
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"Reading Levels": open_reading_levels}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching reading_levels CLI label: %s", label)
    handler()
    return True
