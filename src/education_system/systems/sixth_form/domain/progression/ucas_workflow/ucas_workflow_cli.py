"""CLI flows for the Sixth Form UCAS Workflow.

Submenu: cohort overview / per-student pipeline / sign off a stage.
"""

from __future__ import annotations

import logging
from typing import Callable

from education_system.systems.sixth_form.domain.progression.ucas_workflow import (
    ucas_workflow as data,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


def _input(prompt: str, *, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    s = raw.strip()
    if s.lower() == "cancel":
        raise _UserAbort
    return s or default


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


_MARK = {"Complete": "✓", "In Progress": "~", "Pending": " ", "N/A": "–"}


def _cycle() -> int:
    raw = _input("Cycle year", default=str(data.default_cycle_year()))
    return int(raw) if raw.isdigit() else data.default_cycle_year()


def _overview() -> None:
    year = _cycle()
    rows = data.overview(year)
    if not rows:
        print("\n  No applicants for that cycle yet.")
        return _pause()
    print(f"\n  UCAS {year} cohort — {len(rows)} applicants")
    print(f"  {'Student':<26}{'Progress':>9}   Next stage")
    print("  " + "-" * 60)
    for r in rows:
        bar = f"{r['complete']}/{r['total']} ({r['percent']}%)"
        print(f"  {r['full_name'][:24]:<26}{bar:>9}   {r['next_stage']}")
    _pause()


def _pipeline() -> None:
    sid = _input("Student ID")
    if not sid:
        return
    year = _cycle()
    try:
        p = data.get_pipeline(sid, year)
    except ValueError as e:
        print(f"  ✗ {e}")
        return _pause()
    print(f"\n  {p['full_name']} — UCAS {p['cycle_year']}  "
          f"({p['complete']}/{p['total']}, {p['percent']}%)")
    print("  " + "-" * 58)
    for s in p["stages"]:
        mark = _MARK.get(s["status"], " ")
        kind = "auto" if s["auto"] else "manual"
        due = f"  due {s['due_date']}" if s["due_date"] else ""
        sign = f"  ✎ {s['signed_off_by']}" if s["signed_off_by"] else ""
        print(f"   [{mark}] {s['label']:<34}{s['status']:<12}({kind}){due}{sign}")
    _pause()


def _signoff() -> None:
    sid = _input("Student ID")
    if not sid:
        return
    year = _cycle()
    try:
        p = data.get_pipeline(sid, year)
    except ValueError as e:
        print(f"  ✗ {e}")
        return _pause()
    manual = [s for s in p["stages"] if not s["auto"]]
    print("\n  Manual stages:")
    for i, s in enumerate(manual, 1):
        print(f"    {i}) {s['label']} [{s['status']}]")
    choice = _input("Stage number (or 'cancel')")
    if not choice.isdigit() or not (1 <= int(choice) <= len(manual)):
        print("  Invalid.")
        return _pause()
    stage = manual[int(choice) - 1]
    status = _input(f"New status ({'/'.join(data.STATUSES)})", default="Complete")
    by = _input("Signed off by", default="")
    due = _input("Due date (YYYY-MM-DD, optional)", default="")
    notes = _input("Notes (optional)", default="")
    try:
        data.set_stage(sid, stage["key"], cycle_year=year, status=status,
                       signed_off_by=by or None, due_date=due or None,
                       notes=notes or None)
    except data.ValidationError as e:
        print(f"  ✗ {e}")
        return _pause()
    print("  ✓ Updated.")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Cohort overview", _overview),
    ("Student pipeline", _pipeline),
    ("Sign off a stage", _signoff),
]


def run() -> None:
    while True:
        print("\n── UCAS Workflow ──")
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
            logger.exception("UCAS-workflow CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "UCAS Workflow":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("UCAS-workflow CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
