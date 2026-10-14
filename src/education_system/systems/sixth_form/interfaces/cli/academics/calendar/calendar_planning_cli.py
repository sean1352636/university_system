"""CLI flows for calendar planning: series, clashes, terms and slots.

Submenu hung off Calendar, covering the scheduling-intelligence
modules: :mod:`calendar_recurrence` (repeating events),
:mod:`calendar_clashes` (what a proposed event would collide with),
and :mod:`calendar_terms` (closed days, exam windows, lead time,
week labels). Borrows the prompt helpers from :mod:`calendar_cli`.
"""

from __future__ import annotations

import datetime as _dt
import logging
from typing import Callable

from education_system.systems.sixth_form.domain.academics.calendar import (
    calendar as data,
    calendar_clashes as clashes,
    calendar_recurrence as recurrence,
    calendar_terms as terms,
)
from education_system.systems.sixth_form.domain.academics.calendar.calendar import (
    ValidationError,
)
from education_system.systems.sixth_form.interfaces.cli.academics.calendar.calendar_cli import (
    _input,
    _pause,
    _pick_from,
    _UserAbort,
    _yes_no,
)

logger = logging.getLogger(__name__)


def _today() -> str:
    return _dt.date.today().isoformat()


# ── Series flows ───────────────────────────────────────────────────

def list_series_flow() -> None:
    print("\n═══ Recurring Series ═══")
    rows = recurrence.list_series(active_only=False)
    if not rows:
        print("\n  (no series)")
        _pause()
        return
    print()
    for s in rows:
        flag = "" if s.active else "  [retired]"
        print(f"  {s.series_id:>3}) {s.title[:38]:<38} "
              f"{s.rule_label}{flag}")
    _pause()


def _pick_series() -> recurrence.Series:
    rows = recurrence.list_series(active_only=False)
    if not rows:
        print("    No series defined.")
        raise _UserAbort
    for i, s in enumerate(rows, 1):
        print(f"    {i:>2}) #{s.series_id}  {s.title[:36]:<36} "
              f"{s.rule_label}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)}", allow_empty=False)
        if raw.isdigit() and 1 <= int(raw) <= len(rows):
            return rows[int(raw) - 1]
        print("    Out of range.")


def new_series_flow() -> None:
    print("\n═══ New Series ═══")
    try:
        title = _input("Title", allow_empty=False)
        freq = _pick_from("Frequency",
                           list(recurrence.FREQUENCIES),
                           default=recurrence.DEFAULT_FREQUENCY)
        start = _input("Start date (YYYY-MM-DD)",
                        default=_today(), allow_empty=False)
        until = _input("Until date (blank = open-ended)") or None
        byday = None
        if freq in (recurrence.WEEKLY, recurrence.FORTNIGHTLY):
            byday = _input("Days (e.g. Mon,Wed — blank = start's "
                            "weekday)") or None
        etype = _pick_from("Event type", list(data.EVENT_TYPES),
                            default="Tutor Time")
        stime = _input("Start time (HH:MM, blank = all day)") or None
        etime = (_input("End time (HH:MM)") or None) if stime else None
        location = _input("Location") or None
        audience = _pick_from("Audience", list(data.AUDIENCES),
                               default=data.DEFAULT_AUDIENCE)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        series = recurrence.create_series({
            "title": title, "frequency": freq, "byday": byday,
            "start_date": start, "until_date": until,
            "template": {
                "event_type": etype, "start_time": stime,
                "end_time": etime, "location": location,
                "audience": audience,
                "all_day": stime is None,
            },
        })
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Series #{series.series_id} — {series.rule_label}")
    if _yes_no("Materialise occurrences now", default=True):
        got = recurrence.sync(series.series_id)
        print(f"  {got.summary}")
    _pause()


def sync_series_flow() -> None:
    print("\n═══ Sync a Series ═══")
    try:
        series = _pick_series()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    got = recurrence.sync(series.series_id)
    print(f"\n  {got.summary}")
    _pause()


def sweep_flow() -> None:
    got = recurrence.sweep()
    print(f"\n  Sweep: {got.summary}")
    _pause()


def skip_date_flow() -> None:
    print("\n═══ Skip a Date ═══")
    try:
        series = _pick_series()
        date = _input("Date to skip (YYYY-MM-DD)",
                       allow_empty=False)
        reason = _input("Reason") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        recurrence.add_exception(series.series_id, date,
                                  reason=reason)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print("  ✓ Skipped (any materialised occurrence archived).")
    _pause()


def deactivate_series_flow() -> None:
    print("\n═══ Retire a Series ═══")
    try:
        series = _pick_series()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if not _yes_no(f"Retire '{series.title}' and archive its "
                    "future occurrences", default=False):
        print("\n  Cancelled.")
        return
    n = recurrence.deactivate_series(series.series_id)
    print(f"  ✓ Retired; {n} future occurrence(s) archived.")
    _pause()


# ── Clash / term flows ─────────────────────────────────────────────

def clash_check_flow() -> None:
    print("\n═══ Clash Check ═══")
    try:
        title = _input("Title", default="(proposed)")
        date = _input("Date (YYYY-MM-DD)", allow_empty=False)
        stime = _input("Start time (HH:MM, blank = all day)") or None
        etime = (_input("End time (HH:MM)") or None) if stime else None
        location = _input("Location") or None
        organiser = _input("Organiser") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    payload = {"title": title, "start_date": date,
                "start_time": stime, "end_time": etime,
                "all_day": stime is None, "location": location,
                "organiser": organiser}
    try:
        report = clashes.check(payload)
        term_report = terms.check(payload)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print()
    if report.clean and term_report.clean:
        print("  ✓ Clear — no clashes, no term-calendar concerns.")
    else:
        for c in report.clashes:
            print(f"  ✗ {c.label}")
        for w in term_report.warnings:
            print(f"  ⚠ {w.label}")
    _pause()


def suggest_slot_flow() -> None:
    print("\n═══ Suggest a Slot ═══")
    try:
        minutes = int(_input("Duration (minutes)", default="60"))
        location = _input("Location (blank = anywhere)") or None
        organiser = _input("Organiser (blank = anyone)") or None
    except (_UserAbort, ValueError):
        print("\n  Cancelled / bad input.")
        return
    try:
        slots = clashes.suggest_slots(duration_minutes=minutes,
                                       location=location,
                                       organiser=organiser)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    if not slots:
        print("\n  Nothing free in the search window.")
    else:
        print()
        for s in slots:
            week = terms.week_label(s.date)
            tail = f"  ({week})" if week else ""
            print(f"  · {s.label}{tail}")
    _pause()


def week_label_flow() -> None:
    print("\n═══ Week Label ═══")
    try:
        date = _input("Date (YYYY-MM-DD)", default=_today())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        label = terms.week_label(date)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"\n  {label or 'Outside any term.'}")
    if not terms.is_open(date):
        print(f"  College closed: "
              f"{terms.closure_reason(date) or 'closed'}")
    _pause()


# ── Submenu ────────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List series",          list_series_flow),
    ("New series",           new_series_flow),
    ("Sync a series",        sync_series_flow),
    ("Sweep all series",     sweep_flow),
    ("Skip a date",          skip_date_flow),
    ("Retire a series",      deactivate_series_flow),
    ("Clash check",          clash_check_flow),
    ("Suggest a slot",       suggest_slot_flow),
    ("Week label / closure", week_label_flow),
]


def run() -> None:
    while True:
        print("\n── Calendar · Planning ──")
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
            logger.exception("Calendar planning CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()
