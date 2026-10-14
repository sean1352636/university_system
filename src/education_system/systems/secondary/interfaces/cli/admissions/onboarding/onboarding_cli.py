"""CLI handlers for onboarding in the Secondary School System."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.secondary.domain.admissions.onboarding import (
    onboarding as data,
)
from education_system.systems.secondary.domain.admissions.onboarding.onboarding import (
    STEPS, STEP_KEYS, STEP_LABELS,
)
from education_system.systems.secondary.domain.learners.pupils.pupils import (
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
    s = data.progress_summary()
    print(f"  Total: {s['total']}   "
          f"Complete: {s['complete']}   "
          f"Started: {s['started']}   "
          f"Pending: {s['pending']}")


def _print_table(rows: list[tuple]) -> None:
    if not rows:
        print("  (no pupils)")
        return
    print(f"  {'Pupil ID':<10} {'Name':<28} {'Year':<4} "
          f"{'Progress':<10} {'Status':<10}")
    print(f"  {'-'*10} {'-'*28} {'-'*4} {'-'*10} {'-'*10}")
    for pupil, rec in rows:
        progress = f"{rec.done_count}/{rec.total}"
        status = "complete" if rec.complete else (
            "started" if rec.done_count > 0 else "pending"
        )
        print(f"  {pupil.pupil_id:<10} {pupil.full_name[:28]:<28} "
              f"{pupil.year_group:<4} {progress:<10} {status:<10}")


def _print_checklist(pupil, record) -> None:
    print(f"\n  ── Onboarding: {pupil.full_name} ({pupil.pupil_id}) ──")
    print(f"  Year group:   {pupil.year_group}")
    print(f"  Last updated: {record.updated_at or '-'}")
    print(f"  Progress:     {record.done_count}/{record.total} "
          f"({'complete' if record.complete else 'pending'})")
    print("")
    for i, (key, label) in enumerate(STEPS, 1):
        mark = "[x]" if record.steps[key] else "[ ]"
        print(f"   {i}) {mark} {label}")


@_safe
def open_onboarding() -> None:
    logger.debug("CLI: open_onboarding")
    while True:
        print("\n  ── Onboarding ──")
        _print_summary()
        print("\n   1) List pending pupils")
        print("   2) List all pupils")
        print("   3) Filter by year group")
        print("   4) View / edit pupil checklist")
        print("   5) Mark pupil fully onboarded")
        print("   6) Reset pupil onboarding")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice == "0" or choice == "":
            return
        actions = {
            "1": _list_pending,
            "2": _list_all,
            "3": _list_by_year,
            "4": _edit_checklist,
            "5": _mark_all_done,
            "6": _reset_pupil,
        }
        action = actions.get(choice)
        if action is None:
            print("  Invalid selection.")
            continue
        action()


@_safe
def _list_pending() -> None:
    rows = data.list_records(pending_only=True)
    print(f"\n  {len(rows)} pupil(s) with pending onboarding:")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _list_all() -> None:
    rows = data.list_records()
    print(f"\n  {len(rows)} pupil(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _list_by_year() -> None:
    print(f"  Year groups: {', '.join(YEAR_GROUPS)}")
    yg = _prompt("  Year: ")
    if not yg:
        return
    if yg not in YEAR_GROUPS:
        print("  Invalid year group.")
        return
    rows = data.list_records(year_group=yg)
    print(f"\n  Year {yg}: {len(rows)} pupil(s)")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


def _select_pupil_record():
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return None
    rec = data.get_record(pid)
    # get_record raises if pupil missing — but we also need the Pupil obj
    from education_system.systems.secondary.domain.learners.pupils import pupils as pupils_data
    pupil = pupils_data.get_pupil(pid)
    return pupil, rec


@_safe
def _edit_checklist() -> None:
    selected = _select_pupil_record()
    if selected is None:
        return
    pupil, record = selected
    while True:
        _print_checklist(pupil, record)
        print("\n   Toggle step (1-{n}), A) all done, R) reset, 0) back".format(
            n=len(STEPS)))
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            record = data.mark_all(pupil.pupil_id, True)
            continue
        if choice == "r":
            record = data.mark_all(pupil.pupil_id, False)
            continue
        if not choice.isdigit():
            print("  Invalid selection.")
            continue
        idx = int(choice)
        if not (1 <= idx <= len(STEPS)):
            print("  Invalid selection.")
            continue
        step_key, _ = STEPS[idx - 1]
        new_value = not record.steps[step_key]
        record = data.set_step(pupil.pupil_id, step_key, new_value)


@_safe
def _mark_all_done() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    record = data.mark_all(pid, True)
    print(f"  Marked all {record.total} step(s) done for pupil {pid}.")


@_safe
def _reset_pupil() -> None:
    pid = _prompt("  Pupil ID to reset: ")
    if not pid:
        return
    confirm = _prompt(f"  Reset onboarding for {pid}? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.mark_all(pid, False)
    print(f"  Onboarding reset for pupil {pid}.")


_DISPATCH = {"Onboarding": open_onboarding}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching onboarding CLI label: %s", label)
    handler()
    return True
