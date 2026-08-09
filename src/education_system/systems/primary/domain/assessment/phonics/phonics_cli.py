"""CLI handlers for phonics tracking in the Primary School System."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.primary.domain.assessment.phonics import (
    phonics as data,
)
from education_system.systems.primary.domain.assessment.phonics.phonics import (
    PHASES, PHASE_LABELS, STATUSES,
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


def _print_summary() -> None:
    counts = data.phase_summary()
    total = sum(counts.values())
    print(f"  Tracked: {total}   " + "   ".join(
        f"P{ph}: {counts[ph]}" for ph in PHASES))


def _print_table(rows: list[tuple]) -> None:
    if not rows:
        print("  (no pupils)")
        return
    print(f"  {'Pupil ID':<10} {'Name':<26} {'Year':<5} "
          f"{'Phase':<6} {'Status':<8} {'Last assessed':<14}")
    print(f"  {'-'*10} {'-'*26} {'-'*5} {'-'*6} {'-'*8} {'-'*14}")
    for pupil, rec in rows:
        ph = rec.phase if rec else "-"
        st = rec.status if rec else "-"
        la = (rec.last_assessed if rec else "") or "-"
        print(f"  {pupil.pupil_id:<10} {pupil.full_name[:26]:<26} "
              f"{pupil.year_group:<5} {ph:<6} {st:<8} {la:<14}")


@_safe
def open_phonics() -> None:
    logger.debug("CLI: open_phonics")
    while True:
        print("\n  -- Phonics Tracking --")
        _print_summary()
        print("\n   1) List all pupils")
        print("   2) Filter by year / phase / status")
        print("   3) View pupil + history")
        print("   4) Record assessment")
        print("   5) Delete assessment from history")
        print("   6) Clear pupil's current record")
        print("   7) Show phase descriptions")
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
            "7": _show_phases,
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
    print(f"  Phases: {', '.join(PHASES)} (blank for any)")
    ph = _prompt("  Phase: ").strip() or None
    print(f"  Statuses: {', '.join(STATUSES)} (blank for any)")
    st = _prompt("  Status: ").strip().lower() or None
    rows = data.list_records(year_group=yg, phase=ph, status=st)
    print(f"\n  {len(rows)} pupil(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _view() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    rec = data.get_record(pid)
    from education_system.systems.primary.domain.learners.pupils import pupils as pupils_data
    pupil = pupils_data.get_pupil(pid)
    if pupil is None:
        print(f"  No pupil with id {pid}")
        return
    print(f"\n  -- Phonics: {pupil.full_name} ({pupil.pupil_id}) --")
    print(f"  Year:         {pupil.year_group}")
    if rec is None:
        print("  No phonics record yet.")
    else:
        print(f"  Current phase: {rec.phase} ({rec.status})")
        print(f"  Last assessed: {rec.last_assessed or '-'}")
        print(f"  Notes:         {rec.notes or '-'}")
        print(f"  Updated:       {rec.updated_at or '-'}")
    history = data.list_history(pid)
    print(f"\n  History ({len(history)}):")
    if not history:
        print("    (no assessments)")
    else:
        for h in history:
            print(f"    #{h.assessment_id} {h.assessed_on}  phase {h.phase} "
                  f"({h.status})  {h.notes or ''}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _record() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    print(f"  Phases: {', '.join(PHASES)}")
    phase = _prompt("  Phase: ")
    print(f"  Statuses: {', '.join(STATUSES)}")
    status = _prompt("  Status: ").lower()
    assessed_on = _prompt("  Assessed on YYYY-MM-DD (blank for today): ")
    notes = _prompt("  Notes (optional): ")
    rec = data.record_assessment(pid, {
        "phase": phase, "status": status,
        "assessed_on": assessed_on, "notes": notes,
    })
    print(f"  Recorded: pupil {pid} -> phase {rec.phase} ({rec.status})")
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
    confirm = _prompt(f"  Clear current phonics record for {pid}? "
                     f"(history is kept) (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    ok = data.clear_pupil(pid)
    print(f"  {'Cleared' if ok else 'No record to clear'}: {pid}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _show_phases() -> None:
    print("\n  -- Phonics phases --")
    for ph in PHASES:
        print(f"   {PHASE_LABELS[ph]}")
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"Phonics Tracking": open_phonics}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching phonics CLI label: %s", label)
    handler()
    return True
