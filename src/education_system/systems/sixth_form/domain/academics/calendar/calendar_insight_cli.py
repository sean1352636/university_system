"""CLI flows for calendar admin: bookings, trips, exchange, audit
and the archive.

Submenu hung off Calendar, fronting :mod:`calendar_bookings`,
:mod:`calendar_trips`, :mod:`calendar_ics` / :mod:`calendar_exchange`
(files in and out), :mod:`calendar_governance` (trail and archive)
and the :mod:`calendar_integration` bridges. Borrows the prompt
helpers from :mod:`calendar_cli`.
"""

from __future__ import annotations

import datetime as _dt
import logging
from pathlib import Path
from typing import Callable

from education_system.systems.sixth_form.domain.academics.calendar import (
    calendar as data,
    calendar_bookings as bookings,
    calendar_exchange as exchange,
    calendar_governance as governance,
    calendar_ics as ics,
    calendar_integration as integration,
    calendar_trips as trips,
)
from education_system.systems.sixth_form.domain.academics.calendar.calendar import (
    ValidationError,
)
from education_system.systems.sixth_form.domain.academics.calendar.calendar_cli import (
    _input,
    _pause,
    _pick_event,
    _pick_from,
    _print_events,
    _UserAbort,
    _yes_no,
)

logger = logging.getLogger(__name__)


def _today() -> str:
    return _dt.date.today().isoformat()


# ── Bookings ───────────────────────────────────────────────────────

def bookings_flow() -> None:
    print("\n═══ Bookings ═══")
    try:
        event = _pick_event()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    while True:
        summ = bookings.booking_summary(event.event_id)
        print(f"\n  #{event.event_id} {event.title} — {summ.label}")
        rows = bookings.attendance_list(event.event_id)
        for b in rows:
            print(f"    {b.person:<12} {b.person_name or '':<22} "
                  f"[{b.state}]")
        action = _pick_from(
            "Action", ["Book", "Cancel a booking", "Check in",
                        "Promote waitlist", "Back"], default="Back")
        try:
            if action == "Back":
                return
            if action == "Book":
                person = _input("Person ID", allow_empty=False)
                name = _input("Display name") or None
                got = bookings.book(event.event_id, person,
                                     person_name=name)
                print(f"  ✓ {got.label}")
            elif action == "Cancel a booking":
                person = _input("Person ID", allow_empty=False)
                bookings.cancel(event.event_id, person)
                print("  ✓ Cancelled (waitlist promoted).")
            elif action == "Check in":
                person = _input("Person ID", allow_empty=False)
                bookings.check_in(event.event_id, person)
                print("  ✓ Checked in.")
            elif action == "Promote waitlist":
                got = bookings.promote_waitlist(event.event_id)
                print(f"  ✓ {len(got)} promoted.")
        except (ValidationError, _UserAbort) as e:
            print(f"  ✗ {e}" if str(e) else "\n  Cancelled.")


# ── Trips ──────────────────────────────────────────────────────────

def trips_flow() -> None:
    print("\n═══ Trips ═══")
    rows = data.list_events(event_type="Trip", upcoming_only=True)
    if not rows:
        print("\n  (no upcoming trips)")
        _pause()
        return
    _print_events(rows)
    try:
        event = _pick_event()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    report = trips.readiness(event.event_id)
    print()
    for line in report.summary.splitlines():
        print(f"  {line}")
    if _yes_no("\n  Edit the trip record", default=False):
        try:
            detail = trips.get_detail(event.event_id)
            payload = {
                "risk_assessment_ref": _input(
                    "Risk assessment ref",
                    default=(detail.risk_assessment_ref or ""
                             if detail else "")) or None,
                "ratio_students": _input(
                    "Students per staff",
                    default=str(detail.ratio_students if detail
                                else trips.DEFAULT_RATIO)),
                "staff_count": _input(
                    "Staff going",
                    default=str(detail.staff_count if detail
                                else 0)),
                "transport": _pick_from(
                    "Transport", list(trips.TRANSPORT_MODES),
                    default=(detail.transport if detail
                             else trips.DEFAULT_TRANSPORT)),
                "emergency_contact": _input(
                    "Emergency contact",
                    default=(detail.emergency_contact or ""
                             if detail else "")) or None,
            }
            payload["risk_assessment_ok"] = _yes_no(
                "Risk assessment signed off", default=False)
            trips.set_detail(event.event_id, payload)
            print("  ✓ Saved.")
        except (ValidationError, _UserAbort) as e:
            print(f"  ✗ {e}" if str(e) else "\n  Cancelled.")
    _pause()


def cover_flow() -> None:
    print("\n═══ Raise Trip Cover ═══")
    try:
        event = _pick_event()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        reqs = integration.raise_cover_for_trip(event.event_id)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"  ✓ {len(reqs)} cover request(s) raised for "
          f"{event.organiser}.")
    _pause()


# ── Files in and out ───────────────────────────────────────────────

def export_ics_flow() -> None:
    print("\n═══ Export ICS ═══")
    try:
        path = _input("Write to", default="calendar.ics",
                       allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    text = ics.export_filtered()
    Path(path).write_text(text, encoding="utf-8")
    print(f"  ✓ {path} written.")
    _pause()


def import_ics_flow() -> None:
    print("\n═══ Import ICS ═══")
    try:
        path = _input("Read from", allow_empty=False)
        etype = _pick_from("Default event type",
                            list(data.EVENT_TYPES), default="Other")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    result = ics.import_ics(text, default_event_type=etype)
    print(f"  {result.summary}")
    for err in result.errors:
        print(f"    ✗ {err}")
    _pause()


def export_csv_flow() -> None:
    print("\n═══ Export CSV ═══")
    try:
        path = _input("Write to", default="calendar.csv",
                       allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    Path(path).write_text(exchange.export_filtered_csv(),
                           encoding="utf-8")
    print(f"  ✓ {path} written.")
    _pause()


def import_csv_flow() -> None:
    print("\n═══ Import CSV ═══")
    try:
        path = _input("Read from", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    report = exchange.import_csv(text, dry_run=True)
    print(f"\n  {report.summary}")
    for err in report.errors:
        print(f"    ✗ {err.label}")
    if not report.clean:
        print("  Fix the file and try again — nothing imported.")
        _pause()
        return
    if _yes_no(f"Import {report.valid} row(s)", default=True):
        report = exchange.import_csv(text, dry_run=False)
        print(f"  ✓ {report.summary}")
    _pause()


def print_sheets_flow() -> None:
    print("\n═══ Print Sheets ═══")
    which = _pick_from("Sheet", ["Day sheet", "Term sheet"],
                        default="Day sheet")
    try:
        if which == "Day sheet":
            date = _input("Date", default=_today())
            print()
            print(exchange.day_sheet(date))
        else:
            date_from = _input("From", default=_today())
            date_to = _input("To", allow_empty=False)
            print()
            print(exchange.term_sheet(date_from, date_to))
    except (ValidationError, _UserAbort) as e:
        print(f"  ✗ {e}" if str(e) else "\n  Cancelled.")
    _pause()


# ── Governance ─────────────────────────────────────────────────────

def audit_flow() -> None:
    print("\n═══ Audit Trail ═══")
    raw = _input("Event # (blank = recent activity)") or None
    if raw and raw.strip().lstrip("#").isdigit():
        rows = governance.trail(int(raw.strip().lstrip("#")))
    else:
        rows = governance.recent_activity()
    if not rows:
        print("\n  (no entries)")
    for a in rows:
        print(f"  {a.amended_at}  #{a.event_id:<5} "
              f"[{a.action:<7}] {a.summary}")
    _pause()


def archive_flow() -> None:
    print("\n═══ Archive ═══")
    rows = governance.list_archived()
    if not rows:
        print("\n  (nothing archived)")
        _pause()
        return
    for e in rows:
        print(f"  #{e.event_id:>4}  {e.start_date}  "
              f"{e.title[:40]:<40} archived {e.deleted_at}")
    action = _pick_from("Action",
                         ["Restore", "Delete forever", "Back"],
                         default="Back")
    if action == "Back":
        return
    try:
        raw = _input("Event #", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if not raw.strip().lstrip("#").isdigit():
        print("  Enter a number.")
        _pause()
        return
    event_id = int(raw.strip().lstrip("#"))
    if action == "Restore":
        print("  ✓ Restored." if governance.audited_restore(event_id)
              else "  Nothing to restore.")
    else:
        if _yes_no(f"Permanently delete #{event_id} — no undo",
                    default=False):
            reason = _input("Reason (for the audit trail)") or None
            done = governance.audited_purge(event_id, reason=reason)
            print("  ✓ Gone." if done else "  No such event.")
    _pause()


# ── Integration sweeps ─────────────────────────────────────────────

def sync_flows() -> None:
    print("\n═══ Integration Sweeps ═══")
    which = _pick_from(
        "Sweep", ["EPQ deadlines", "Enrichment series",
                   "Open days feed", "Back"], default="Back")
    if which == "Back":
        return
    try:
        if which == "EPQ deadlines":
            got = integration.sync_epq_deadlines()
            print(f"  {got.summary}")
        elif which == "Enrichment series":
            start = _input("Term start", default=_today(),
                            allow_empty=False)
            until = _input("Term end", allow_empty=False)
            got = integration.sync_enrichment_series(
                start_date=start, until_date=until)
            print(f"  {got.summary}")
        else:
            for e in integration.upcoming_open_days():
                print(f"  · {e.start_date}  {e.title}")
    except (ValidationError, _UserAbort) as e:
        print(f"  ✗ {e}" if str(e) else "\n  Cancelled.")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Bookings & waitlist",     bookings_flow),
    ("Trips & readiness",       trips_flow),
    ("Raise trip cover",        cover_flow),
    ("Export ICS",              export_ics_flow),
    ("Import ICS",              import_ics_flow),
    ("Export CSV",              export_csv_flow),
    ("Import CSV (dry run first)", import_csv_flow),
    ("Print sheets",            print_sheets_flow),
    ("Audit trail",             audit_flow),
    ("Archive (restore/purge)", archive_flow),
    ("Integration sweeps",      sync_flows),
]


def run() -> None:
    while True:
        print("\n── Calendar · Admin ──")
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
            logger.exception("Calendar insight CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()
