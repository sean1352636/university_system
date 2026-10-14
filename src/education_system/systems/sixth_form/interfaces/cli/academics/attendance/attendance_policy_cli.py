"""CLI flows for the rules attendance runs under, and for roll call.

Submenu hung off Attendance:

* **Roll call** — who is in the building, and the drill that counts them
  out (:mod:`attendance_rollcall`).
* **Timetable weeks** — the A/B cycle and which slots run in which week
  (:mod:`attendance_weeks`).
* **Amendment window** — how long a register stays editable, and the log
  of everything written after it closed (:mod:`attendance_window`).
"""

from __future__ import annotations

import logging
from datetime import date as _date, timedelta as _timedelta
from typing import Callable

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance_rollcall as rollcall,
    attendance_weeks as weeks,
    attendance_window as window,
)
from education_system.systems.sixth_form.domain.academics.attendance.attendance import (
    ValidationError,
)
from education_system.systems.sixth_form.interfaces.cli.academics.attendance.attendance_cli import (
    _input,
    _pause,
    _pick_from,
    _pick_group,
    _pick_slot,
    _UserAbort,
)
from education_system.systems.sixth_form.domain.academics.timetable.timetable import (
    day_name,
)

logger = logging.getLogger(__name__)


def _today() -> str:
    return _date.today().isoformat()


def _yes(prompt: str, *, default: str = "n") -> bool:
    return _input(prompt, default=default).lower().startswith("y")


# ═══ Roll call ══════════════════════════════════════════════════════

def roll_on_site() -> None:
    print("\n═══ Who Is On Site ═══")
    print("\n  Built from today's marks, not from enrolment.")
    try:
        date_s = _input("Date (YYYY-MM-DD)", default=_today())
    except _UserAbort:
        return
    counts = rollcall.head_count(date=date_s)
    if not counts:
        print("\n  No learners on roll.")
        _pause()
        return
    print()
    for reason, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        flag = "  ← at the assembly point" if reason in \
            rollcall.ON_SITE_REASONS else ""
        print(f"    {reason:<24}{n:>5}{flag}")
    on_site = rollcall.on_site_list(date=date_s)
    print(f"\n  {len(on_site)} person(s) expected on site.")
    if on_site and _yes("  List them? (y/N)"):
        for presence in on_site[:60]:
            print(f"    {presence.label}")
        if len(on_site) > 60:
            print(f"    … and {len(on_site) - 60} more.")
    _pause()


def roll_start() -> None:
    print("\n═══ Start a Roll Call ═══")
    print("\n  The list is frozen the moment this starts — a register")
    print("  edited during an evacuation must not remove a name.")
    running = rollcall.current_drill()
    if running is not None:
        print(f"\n  ✗ {running.label} is still running. Close it first.")
        _pause()
        return
    try:
        kind = _pick_from("Kind", list(rollcall.KINDS),
                          default=rollcall.DRILL)
        started_by = _input("Started by") or None
        point = _input("Assembly point") or None
        drill = rollcall.start_drill(kind=kind, started_by=started_by,
                                     assembly_point=point)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    print(f"\n  ✓ {drill.label} — {drill.expected} person(s) expected.")
    print("    Use 'Account for people' as marshals report in.")
    _pause()


def roll_account() -> None:
    print("\n═══ Account For People ═══")
    drill = rollcall.current_drill()
    if drill is None:
        print("\n  No roll call is running.")
        _pause()
        return
    state = rollcall.status(drill.drill_id)
    print(f"\n  {drill.label}: {state.summary}")
    print("\n  Enter student IDs (comma separated), or 'G' for a whole")
    print("  class group. Blank to stop.")
    try:
        marked_by = _input("Marshal name") or None
        while True:
            raw = _input("IDs / G / blank", default="")
            if not raw:
                break
            if raw.lower() == "g":
                group_id = _pick_group()
                n = rollcall.account_for_group(drill.drill_id, group_id,
                                               marked_by=marked_by)
                print(f"    ✓ {n} accounted for.")
                continue
            ids = [s.strip() for s in raw.split(",") if s.strip()]
            n = rollcall.account_for(drill.drill_id, ids, marked_by=marked_by)
            print(f"    ✓ {n} accounted for.")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        pass
    state = rollcall.status(drill.drill_id)
    print(f"\n  {state.summary}")
    if state.missing:
        print("\n  Still outstanding:")
        for presence in state.missing[:30]:
            print(f"    {presence.label}")
        if len(state.missing) > 30:
            print(f"    … and {len(state.missing) - 30} more.")
    _pause()


def roll_status() -> None:
    print("\n═══ Roll Call Status ═══")
    drill = rollcall.current_drill()
    if drill is None:
        print("\n  No roll call is running.")
        _pause()
        return
    state = rollcall.status(drill.drill_id)
    print(f"\n  {drill.label}")
    print(f"  Assembly point: {drill.assembly_point or '—'}")
    print(f"  {state.summary}")
    if state.complete:
        print("\n  ✓ Everybody is accounted for.")
    else:
        print(f"\n  ⚠ {state.outstanding} NOT ACCOUNTED FOR:\n")
        for presence in state.missing:
            print(f"    {presence.student_id}  {presence.full_name:<24}"
                  f"last known: {presence.room or presence.detail or '—'}")
    _pause()


def roll_close() -> None:
    print("\n═══ Close a Roll Call ═══")
    drill = rollcall.current_drill()
    if drill is None:
        print("\n  No roll call is running.")
        _pause()
        return
    state = rollcall.status(drill.drill_id)
    print(f"\n  {state.summary}")
    try:
        closed_by = _input("Closed by") or None
        notes = _input("Notes (optional)") or None
        allow = False
        if not state.complete:
            print(f"\n  ⚠ {state.outstanding} person(s) are unaccounted for.")
            allow = _yes("  Close anyway? (y/N)")
            if not allow:
                print("\n  Not closed.")
                _pause()
                return
        closed = rollcall.close_drill(drill.drill_id, closed_by=closed_by,
                                     notes=notes, allow_incomplete=allow)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    print(f"\n  ✓ Closed in {closed.duration_seconds}s.")
    _pause()


def roll_history() -> None:
    print("\n═══ Drill History ═══")
    reports = rollcall.drill_history(limit=20)
    if not reports:
        print("\n  No completed drills.")
        _pause()
        return
    print(f"\n    {'#':>4}  {'Date':<12}{'Kind':<12}{'Expected':>9}"
          f"{'Missing':>8}{'Time':>8}")
    for report in reports:
        duration = report["duration_seconds"]
        print(f"    {report['drill_id']:>4}  {report['date']:<12}"
              f"{report['kind']:<12}{report['expected']:>9}"
              f"{len(report['missing']):>8}"
              f"{(f'{duration}s' if duration is not None else '—'):>8}")
    _pause()


_ROLL_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Who is on site",      roll_on_site),
    ("Start a roll call",   roll_start),
    ("Account for people",  roll_account),
    ("Status / who's missing", roll_status),
    ("Close",               roll_close),
    ("Drill history",       roll_history),
]


# ═══ Timetable weeks ════════════════════════════════════════════════

def weeks_show() -> None:
    print("\n═══ Timetable Cycle ═══")
    pattern = weeks.get_pattern()
    print(f"\n  {pattern.summary}")
    if pattern.is_cycling:
        print(f"\n  This week is week {weeks.week_for_date(_today())}.")
        for label in pattern.labels:
            print(f"    Week {label} next begins "
                  f"{weeks.next_date_in_week(label)}")
    summary = weeks.summary()
    print(f"\n  {summary.total_slots} slot(s): {summary.both} run every week"
          + (", " + ", ".join(f"{n} in week {w}"
                              for w, n in summary.by_week.items())
             if pattern.is_cycling else ""))
    orphans = weeks.orphaned_assignments()
    if orphans:
        print(f"\n  ⚠ {len(orphans)} slot(s) pinned to a week the cycle no")
        print("    longer has — they will never appear on a register list:")
        for entry in orphans[:10]:
            print(f"      slot #{entry.slot_id} → week {entry.week}")
    _pause()


def weeks_set_cycle() -> None:
    print("\n═══ Set the Cycle ═══")
    print("\n  1 = a plain weekly timetable. 2 = A/B weeks.")
    print("  The anchor is any date inside the first week of the cycle.")
    try:
        raw = _input("Cycle length in weeks", default="2")
        anchor = _input("Anchor date (YYYY-MM-DD, blank to keep)") or None
        pattern = weeks.set_pattern(cycle_weeks=int(raw), anchor_date=anchor)
    except ValueError:
        print("\n  ✗ That needs to be a number.")
        _pause()
        return
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    print(f"\n  ✓ {pattern.summary}")
    _pause()


def weeks_assign() -> None:
    print("\n═══ Pin Slots to a Week ═══")
    pattern = weeks.get_pattern()
    if not pattern.is_cycling:
        print("\n  The timetable is not on a cycle — every slot runs every")
        print("  week. Set a cycle first.")
        _pause()
        return
    options = [*pattern.labels, weeks.BOTH]
    try:
        whole_group = _yes("Assign a whole class group? (y/N)")
        week = _pick_from("Week", options, default=weeks.BOTH)
        if whole_group:
            group_id = _pick_group()
            n = weeks.assign_group(group_id, week)
            print(f"\n  ✓ {n} slot(s) pinned to week {week}.")
        else:
            slot_id = _pick_slot()
            weeks.set_slot_week(slot_id, week)
            print(f"\n  ✓ Slot #{slot_id} pinned to week {week}.")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        print("\n  Cancelled.")
    _pause()


def weeks_calendar() -> None:
    print("\n═══ Week Calendar ═══")
    try:
        date_from = _input("From (YYYY-MM-DD)", default=_today())
        date_to = _input(
            "To (YYYY-MM-DD)",
            default=(_date.today() + _timedelta(days=27)).isoformat())
        days = weeks.week_calendar(date_from, date_to)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        return
    current = None
    for day in days:
        if day.weekday > 5:
            continue
        if day.week != current:
            current = day.week
            print(f"\n  Week {day.week}:")
        print(f"    {day.date}  {day_name(day.weekday)}")
    _pause()


_WEEKS_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Show the cycle",      weeks_show),
    ("Set the cycle",       weeks_set_cycle),
    ("Pin slots to a week", weeks_assign),
    ("Week calendar",       weeks_calendar),
]


# ═══ Amendment window ═══════════════════════════════════════════════

def window_show() -> None:
    print("\n═══ Amendment Window ═══")
    policy = window.get_policy()
    print(f"\n  {policy.summary}")
    if policy.updated_at:
        print(f"  Last changed {policy.updated_at} by "
              f"{policy.updated_by or '?'}")
    print("\n  Open              ordinary register-taking")
    print("  Reason required   a save goes through, but has to say why")
    print("  Closed            only a retrospective correction gets in")
    print("\n  The curated amendment paths — authorising, recoding,")
    print("  voiding — reach a mark of any age, because each of them")
    print("  already records who did it and why.")
    _pause()


def window_set() -> None:
    print("\n═══ Set the Window ═══")
    policy = window.get_policy()
    try:
        enabled = _yes("Enforce a window at all? (Y/n)",
                       default="y" if policy.enabled else "n")
        open_days = _input("Days of free editing",
                           default=str(policy.open_days))
        close_days = _input("Days until amendment closes entirely",
                            default=str(policy.close_days))
        future_days = _input("Days ahead a register may be marked",
                             default=str(policy.future_days))
        updated = window.set_policy(
            enabled=enabled, open_days=int(open_days),
            close_days=int(close_days), future_days=int(future_days))
    except ValueError:
        print("\n  ✗ Those need to be numbers.")
        _pause()
        return
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    print(f"\n  ✓ {updated.summary}")
    _pause()


def window_check() -> None:
    print("\n═══ Check a Date ═══")
    try:
        date_s = _input("Date (YYYY-MM-DD)", default=_today())
        decision = window.evaluate(date_s)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        return
    print(f"\n  [{decision.state}] {decision.message}")
    print(f"\n    Free editing until : {window.closes_on(date_s)}")
    print(f"    Amendable until    : {window.final_deadline(date_s)}")
    _pause()


def window_closing() -> None:
    print("\n═══ Registers Closing Soon ═══")
    print("\n  Fix these before they need a reason and a signature.")
    try:
        days = _input("Within how many days", default="3")
        rows = window.closing_soon(within_days=int(days))
    except ValueError:
        print("\n  ✗ That needs to be a number.")
        _pause()
        return
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        return
    if not rows:
        print("\n  ✓ Nothing about to close.")
        _pause()
        return
    print(f"\n    {'Slot':>5}  {'Date':<12}{'State':<10}{'Closes':<12}Left")
    for row in rows:
        print(f"    {row.slot_id:>5}  {row.date:<12}{row.state:<10}"
              f"{row.closes_on:<12}{row.days_remaining}d")
    _pause()


def window_overrides() -> None:
    print("\n═══ Retrospective Writes ═══")
    print("\n  Everything written after the window closed, and who did it.")
    try:
        actor = _input("Filter by actor (optional)") or None
        rows = window.list_overrides(actor=actor, limit=60)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        return
    if not rows:
        print("\n  Nothing has been written retrospectively.")
        _pause()
        return
    print(f"\n    {'Date':<12}{'Age':>5}  {'State':<18}{'Actor':<14}"
          f"{'Source':<20}Reason")
    for row in rows:
        print(f"    {row.date:<12}{row.days_late:>5}  {row.state:<18}"
              f"{(row.actor or '—')[:13]:<14}{(row.source or '—')[:19]:<20}"
              f"{(row.reason or '')[:30]}")
    _pause()


_WINDOW_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Show the policy",         window_show),
    ("Set the policy",          window_set),
    ("Check a date",            window_check),
    ("Registers closing soon",  window_closing),
    ("Retrospective writes",    window_overrides),
]


# ── Submenu plumbing ────────────────────────────────────────────────

def _run_menu(title: str, menu: list[tuple[str, Callable[[], None]]]) -> None:
    while True:
        print(f"\n── {title} ──")
        for i, (label, _) in enumerate(menu, 1):
            print(f"  {i}) {label}")
        print("  0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(menu)):
            print("  Invalid selection.")
            continue
        _, handler = menu[int(choice) - 1]
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Policy CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def rollcall_menu() -> None:
    _run_menu("Roll Call", _ROLL_MENU)


def weeks_menu() -> None:
    _run_menu("Timetable Weeks", _WEEKS_MENU)


def window_menu() -> None:
    _run_menu("Amendment Window", _WINDOW_MENU)


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Roll Call (fire drill / evacuation)", rollcall_menu),
    ("Timetable Weeks (A/B)",               weeks_menu),
    ("Amendment Window",                    window_menu),
]


def run() -> None:
    _run_menu("Roll Call & Attendance Policy", _MENU)
