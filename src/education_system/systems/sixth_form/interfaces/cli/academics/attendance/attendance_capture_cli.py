"""CLI flows for how attendance marks get captured.

Submenu hung off Attendance, covering the four routes a mark can take
into the system other than a teacher typing it:

* **Kiosk** — terminals, cards and QR badges (:mod:`attendance_kiosk`).
* **Offline** — bundles taken away and batches synced back
  (:mod:`attendance_offline`).
* **Cover** — lessons somebody else is taking (:mod:`attendance_cover`).
* **Import** — history arriving as a file (:mod:`attendance_import`).
"""

from __future__ import annotations

import logging
from datetime import date as _date, timedelta as _timedelta
from pathlib import Path
from typing import Callable

from education_system.systems.sixth_form.domain.academics.attendance.attendance import (
    ValidationError,
)
from education_system.systems.sixth_form.interfaces.cli.academics.attendance.attendance_cli import (
    lazy_domain,
    _input,
    _pause,
    _pick_from,
    _pick_slot,
    _UserAbort,
)

# Domain modules load on first use (see attendance_cli.lazy_domain).
cover = lazy_domain("attendance_cover")
importer = lazy_domain("attendance_import")
kiosk = lazy_domain("attendance_kiosk")
offline = lazy_domain("attendance_offline")
signout = lazy_domain("attendance_signout")
signout_requests = lazy_domain("attendance_signout_requests")
from education_system.systems.sixth_form.domain.academics.timetable.timetable import (
    day_name,
)

logger = logging.getLogger(__name__)


def _today() -> str:
    return _date.today().isoformat()


def _week_ago() -> str:
    return (_date.today() - _timedelta(days=7)).isoformat()


def _yes(prompt: str, *, default: str = "n") -> bool:
    return _input(prompt, default=default).lower().startswith("y")


# ═══ Kiosk ══════════════════════════════════════════════════════════

def kiosk_devices() -> None:
    print("\n═══ Kiosk Devices ═══")
    devices = kiosk.list_devices()
    if not devices:
        print("\n  No terminals registered yet.")
        _pause()
        return
    print(f"\n    {'#':>3}  {'Name':<20}{'Mode':<10}{'Room':<10}"
          f"{'Active':<8}Last seen")
    for device in devices:
        print(f"    {device.device_id:>3}  {device.name[:19]:<20}"
              f"{device.mode:<10}{(device.room or '—')[:9]:<10}"
              f"{('yes' if device.active else 'no'):<8}"
              f"{device.last_seen_at or 'never'}")
    _pause()


def kiosk_register() -> None:
    print("\n═══ Register a Terminal ═══")
    print("\n  The key is shown once, here. Losing it means rotating it.")
    try:
        name = _input("Device name", allow_empty=False)
        mode = _pick_from("Mode", list(kiosk.DEVICE_MODES),
                          default=kiosk.ROOM)
        room = (_input("Room") or None) if mode == kiosk.ROOM else None
        location = _input("Location description (optional)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        device = kiosk.register_device(name, room=room, mode=mode,
                                       location=location)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Registered #{device.device_id} — {device.label}")
    print(f"\n    API key: {device.api_key}")
    print("    Copy it now; it is not shown again.")
    _pause()


def kiosk_health() -> None:
    print("\n═══ Terminal Health ═══")
    print("\n  A quiet terminal usually means an empty register.")
    rows = kiosk.device_health()
    if not rows:
        print("\n  No terminals registered.")
        _pause()
        return
    print(f"\n    {'Name':<20}{'Taps today':>11}  {'Last seen':>12}  Status")
    for row in rows:
        seen = ("never" if row.hours_since_seen is None
                else f"{row.hours_since_seen:.1f}h ago")
        flag = "⚠ stale" if row.stale else "ok"
        print(f"    {row.device.name[:19]:<20}{row.taps_today:>11}  "
              f"{seen:>12}  {flag}")
    _pause()


def kiosk_tokens() -> None:
    print("\n═══ Cards & Badges ═══")
    try:
        student_id = _input("Student ID", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    tokens = kiosk.list_tokens(student_id=student_id)
    if tokens:
        print(f"\n    {'Token':<20}{'Kind':<8}{'Expires':<12}Status")
        for token in tokens:
            status = "revoked" if token.revoked else (
                "valid" if token.is_valid() else "expired")
            print(f"    {token.token[:18]:<20}{token.kind:<8}"
                  f"{(token.expires_on or '—'):<12}{status}")
    else:
        print("\n  No tokens issued to that learner.")

    print("\n  Actions:  I) Issue a new one   R) Revoke one   (Enter to go back)")
    try:
        choice = _input("Action", default="")
    except _UserAbort:
        return
    if choice.lower() == "i":
        try:
            kind = _pick_from("Kind", list(kiosk.TOKEN_KINDS),
                              default=kiosk.KIND_CARD)
            label = _input("Label (optional)") or None
            expires = _input("Expires on (YYYY-MM-DD, optional)") or None
            existing = _input("Existing card number (blank to generate)") or None
            token = kiosk.issue_token(student_id, kind=kind, label=label,
                                      expires_on=expires, token=existing)
            print(f"\n  ✓ Issued {token.token}")
        except (ValidationError, _UserAbort) as e:
            print(f"\n  ✗ {e}" if isinstance(e, ValidationError)
                  else "\n  Cancelled.")
    elif choice.lower() == "r":
        try:
            value = _input("Token to revoke", allow_empty=False)
        except _UserAbort:
            return
        print("\n  ✓ Revoked." if kiosk.revoke_token(value)
              else "\n  ✗ No live token with that value.")
    _pause()


def kiosk_check_in() -> None:
    print("\n═══ Check In ═══")
    print("\n  What a terminal does when a card is tapped. Useful from a")
    print("  desk when somebody has forgotten theirs.")
    try:
        by_card = _yes("Check in by card? (y/N)")
        device_name = _input("Device name (optional)") or None
        at_time = _input("Time (HH:MM)", default="") or None
        if by_card:
            token = _input("Card / token", allow_empty=False)
            result = kiosk.check_in(token, device=device_name, at_time=at_time)
        else:
            student_id = _input("Student ID", allow_empty=False)
            result = kiosk.check_in_student(student_id, device=device_name,
                                            at_time=at_time)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    print(f"\n  [{result.outcome}] {result.message}")
    if result.slot_id:
        print(f"    Slot #{result.slot_id}"
              + (f", {result.minutes_late} min late" if result.minutes_late
                 else ""))
    _pause()


def kiosk_events() -> None:
    print("\n═══ Recent Taps ═══")
    try:
        date_s = _input("Date (YYYY-MM-DD)", default=_today())
    except _UserAbort:
        return
    breakdown = kiosk.outcome_breakdown(date=date_s)
    if breakdown:
        print("\n  " + "   ".join(f"{k}: {v}" for k, v in breakdown.items()))
    events = kiosk.list_events(date=date_s, limit=40)
    if not events:
        print("\n  (no taps)")
        _pause()
        return
    print(f"\n    {'Time':<7}{'Student':<10}{'Device':<16}{'Slot':>5}  Outcome")
    for event in events:
        print(f"    {event.time:<7}{(event.student_id or '—')[:9]:<10}"
              f"{(event.device_name or '—')[:15]:<16}"
              f"{(event.slot_id or '—'):>5}  {event.outcome}")
    _pause()


_KIOSK_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Devices",              kiosk_devices),
    ("Register a terminal",  kiosk_register),
    ("Terminal health",      kiosk_health),
    ("Cards & badges",       kiosk_tokens),
    ("Check in",             kiosk_check_in),
    ("Recent taps",          kiosk_events),
]


# ═══ Offline ════════════════════════════════════════════════════════

def offline_pack() -> None:
    print("\n═══ Pack Registers for Offline ═══")
    print("\n  What a device takes away: the roster, the marks so far, and")
    print("  a digest so conflicts can be spotted on the way back.")
    try:
        date_s = _input("Date (YYYY-MM-DD)", default=_today())
    except _UserAbort:
        return
    bundles = offline.pack_day(date=date_s)
    if not bundles:
        print("\n  Nothing timetabled that day.")
        _pause()
        return
    print(f"\n  {len(bundles)} bundle(s):\n")
    print(f"    {'Slot':>5}  {'Period':>6}  {'Room':<8}{'Roster':>7}  "
          f"{'Locked':<8}Digest")
    for bundle in bundles:
        print(f"    {bundle.slot_id:>5}  {bundle.period or '—':>6}  "
              f"{(bundle.room or '—')[:7]:<8}{len(bundle.students):>7}  "
              f"{('yes' if bundle.locked else 'no'):<8}{bundle.digest}")
    _pause()


def offline_queue() -> None:
    print("\n═══ Offline Queue ═══")
    batches = offline.list_batches(open_only=True)
    if not batches:
        print("\n  ✓ Nothing waiting to sync.")
        _pause()
        return
    print(f"\n    {'#':>4}  {'Slot':>5}  {'Date':<12}{'Marks':>6}  "
          f"{'Device':<16}{'State':<10}Captured")
    for batch in batches:
        print(f"    {batch.queue_id:>4}  {batch.slot_id:>5}  "
              f"{batch.date:<12}{batch.size:>6}  "
              f"{(batch.device_name or '—')[:15]:<16}{batch.state:<10}"
              f"{batch.captured_at}")
    backlog = offline.device_backlog()
    if backlog:
        print("\n  By device:")
        for row in backlog:
            print(f"    {row.device_name or '—':<20}{row.pending} pending, "
                  f"{row.conflicts} held (oldest {row.oldest_capture})")
    _pause()


def offline_sync() -> None:
    print("\n═══ Sync Offline Batches ═══")
    print("\n  server-wins  keep the office's mark where they disagree")
    print("  device-wins  keep the teacher's")
    print("  hold         apply nothing contested; park it for a person")
    try:
        policy = _pick_from("Policy", list(offline.POLICIES),
                            default=offline.DEFAULT_POLICY)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        report = offline.sync(policy=policy)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  {report.summary}")
    for result in report.results:
        if result.state != offline.APPLIED or result.conflicts:
            print(f"    #{result.queue_id}: {result.state}"
                  + (f" — {result.detail}" if result.detail else ""))
            for conflict in result.conflicts:
                print(f"        {conflict.label}")
    _pause()


def offline_conflicts() -> None:
    print("\n═══ Held Batches ═══")
    held = offline.conflicts()
    if not held:
        print("\n  ✓ Nothing waiting on a decision.")
        _pause()
        return
    for batch in held:
        print(f"\n  {batch.label}  device={batch.device_name or '?'}")
        for conflict in batch.conflicts:
            print(f"      {conflict.label}")
    print("\n  Actions:  R) Resolve one   D) Discard one   (Enter to go back)")
    try:
        choice = _input("Action", default="")
        if choice.lower() not in ("r", "d"):
            return
        queue_id = int(_input("Batch #", allow_empty=False))
        if choice.lower() == "r":
            policy = _pick_from("Keep which side?",
                                [offline.SERVER_WINS, offline.DEVICE_WINS],
                                default=offline.SERVER_WINS)
            result = offline.resolve(queue_id, policy=policy)
            print(f"\n  ✓ {result.state}: {result.written} written, "
                  f"{result.skipped} skipped")
        else:
            reason = _input("Reason", allow_empty=False)
            offline.discard(queue_id, reason=reason)
            print("\n  ✓ Discarded.")
    except ValueError:
        print("\n  ✗ Batch # must be a number.")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        print("\n  Cancelled.")
    _pause()


_OFFLINE_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Pack registers for a device", offline_pack),
    ("Queue",                       offline_queue),
    ("Sync now",                    offline_sync),
    ("Held batches (conflicts)",    offline_conflicts),
]


# ═══ Cover ══════════════════════════════════════════════════════════

def cover_arrange() -> None:
    print("\n═══ Arrange Cover ═══")
    try:
        slot_id = _pick_slot()
        date_s = _input("Date (YYYY-MM-DD)", default=_today())
        usual = cover.usual_teacher(slot_id)
        if usual:
            print(f"\n  Usually taught by {usual}.")
        absent = _input("Teacher out", default=usual or "") or None
        reason = _pick_from("Reason", list(cover.REASONS),
                            default=cover.DEFAULT_REASON)
        covering = _input("Covering teacher (blank = unallocated)") or None
        room = _input("Room override (optional)") or None
        notes = _input("Notes (optional)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        arranged = cover.arrange(slot_id, date_s, absent_teacher=absent,
                                 cover_teacher=covering, reason=reason,
                                 room=room, notes=notes)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{arranged.cover_id}: {arranged.label}")
    _pause()


def cover_sheet() -> None:
    print("\n═══ Today's Cover ═══")
    try:
        date_s = _input("Date (YYYY-MM-DD)", default=_today())
    except _UserAbort:
        return
    rows = cover.today_sheet(date_s)
    if not rows:
        print("\n  Nothing being covered.")
        _pause()
        return
    print(f"\n    {'#':>4}  {'P':>2}  {'Group':<14}{'Room':<8}"
          f"{'Out':<14}{'Covering':<14}{'Register':<12}Marked")
    for row in rows:
        print(f"    {row.cover.cover_id:>4}  {row.period:>2}  "
              f"{row.group_name[:13]:<14}{(row.room or '—')[:7]:<8}"
              f"{(row.cover.absent_teacher or '—')[:13]:<14}"
              f"{(row.cover.cover_teacher or 'UNALLOCATED')[:13]:<14}"
              f"{row.register_state:<12}{row.marked}/{row.expected}")
    unmarked = [r for r in rows if r.cover.is_live and not r.is_marked]
    if unmarked:
        print(f"\n  ⚠ {len(unmarked)} covered lesson(s) not fully marked.")
    _pause()


def cover_unallocated() -> None:
    print("\n═══ Unallocated Cover ═══")
    print("\n  Lessons with nobody in front of them.")
    rows = cover.unallocated()
    if not rows:
        print("\n  ✓ Everything is allocated.")
        _pause()
        return
    for row in rows:
        print(f"    #{row.cover_id:<4} {row.label}")
    print("\n  Allocate one?")
    try:
        if not _yes("Allocate now? (y/N)"):
            return
        cover_id = int(_input("Cover #", allow_empty=False))
        teacher = _input("Covering teacher", allow_empty=False)
        allocated = cover.allocate(cover_id, teacher)
        print(f"\n  ✓ {allocated.label}")
    except ValueError:
        print("\n  ✗ Cover # must be a number.")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        print("\n  Cancelled.")
    _pause()


def cover_load() -> None:
    print("\n═══ Cover Load ═══")
    print("\n  Cover is shared fairly or it is not; this is how you know.")
    try:
        date_from = _input("From (YYYY-MM-DD)", default=_week_ago())
        date_to = _input("To (YYYY-MM-DD)", default=_today())
    except _UserAbort:
        return
    doing = cover.cover_load(date_from=date_from, date_to=date_to)
    out = cover.absence_load(date_from=date_from, date_to=date_to)
    if doing:
        print(f"\n  Covering:\n    {'Teacher':<24}{'Lessons':>8}{'Days':>6}")
        for row in doing:
            print(f"    {row.teacher[:23]:<24}{row.lessons:>8}{row.dates:>6}")
    if out:
        print(f"\n  Covered for:\n    {'Teacher':<24}{'Lessons':>8}{'Days':>6}")
        for row in out:
            print(f"    {row.teacher[:23]:<24}{row.lessons:>8}{row.dates:>6}")
    breakdown = cover.reason_breakdown(date_from=date_from, date_to=date_to)
    if breakdown:
        print("\n  Reasons: "
              + ", ".join(f"{k} {v}" for k, v in breakdown.items()))
    if not (doing or out):
        print("\n  No cover in that window.")
    _pause()


_COVER_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Arrange cover",       cover_arrange),
    ("Today's cover sheet", cover_sheet),
    ("Unallocated",         cover_unallocated),
    ("Cover load",          cover_load),
]


# ═══ Import ═════════════════════════════════════════════════════════

def import_preview() -> None:
    print("\n═══ Preview an Import ═══")
    print("\n  Nothing is written. This is what applying the file would do.")
    try:
        path = _input("CSV path", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = importer.parse_file(path)
        plan = importer.plan(rows)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return

    print(f"\n  {plan.summary}")
    if plan.date_from:
        print(f"  Dates: {plan.date_from} → {plan.date_to}")
    if plan.unknown_students:
        shown = ", ".join(sorted(plan.unknown_students)[:8])
        print(f"  Unknown learners ({len(plan.unknown_students)}): {shown}")
    if plan.unknown_slots:
        print(f"  Unknown slots: {sorted(plan.unknown_slots)[:8]}")
    if plan.locked_registers:
        print(f"  Submitted registers skipped: {len(plan.locked_registers)}")
    if plan.duplicates:
        print(f"  Duplicate lines in the file: {plan.duplicates}")
    for row in plan.errors[:10]:
        print(f"    ✗ {row.label} — {row.detail}")

    if not plan.writable:
        print("\n  Nothing would be written.")
        _pause()
        return
    try:
        if not _yes(f"\n  Apply {len(plan.writable)} row(s)? (y/N)"):
            print("\n  Not applied.")
            _pause()
            return
        label = _input("Label for this import", default=Path(path).name)
        skip = _yes("Keep existing marks where they clash? (y/N)")
        batch = importer.apply_plan(plan, label=label, source=str(path),
                                    skip_overwrites=skip)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    print(f"\n  ✓ Batch #{batch.batch_id}: {batch.rows_written} written, "
          f"{batch.rows_skipped} skipped, {batch.rows_errored} errored.")
    print("    Undo it from Import Batches if it looks wrong.")
    _pause()


def import_batches() -> None:
    print("\n═══ Import Batches ═══")
    batches = importer.list_batches()
    if not batches:
        print("\n  Nothing imported yet.")
        _pause()
        return
    print(f"\n    {'#':>4}  {'Label':<24}{'State':<12}{'Written':>8}"
          f"{'Skipped':>8}  Dates")
    for batch in batches:
        print(f"    {batch.batch_id:>4}  {batch.label[:23]:<24}"
              f"{batch.state:<12}{batch.rows_written:>8}"
              f"{batch.rows_skipped:>8}  "
              f"{batch.date_from or '—'} → {batch.date_to or '—'}")
    try:
        if not _yes("\n  Roll one back? (y/N)"):
            return
        batch_id = int(_input("Batch #", allow_empty=False))
        if not _yes(f"  Undo every mark batch #{batch_id} wrote? (y/N)"):
            print("\n  Cancelled.")
            return
        result = importer.rollback(batch_id)
        print(f"\n  ✓ {result.restored} row(s) restored, "
              f"{result.deleted} removed.")
    except ValueError:
        print("\n  ✗ Batch # must be a number.")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        print("\n  Cancelled.")
    _pause()


def import_template() -> None:
    print("\n═══ Import File Format ═══")
    print("\n  Columns are matched by name, and most aliases are accepted:")
    for ours, aliases in importer.COLUMN_ALIASES.items():
        print(f"    {ours:<14}{', '.join(aliases[:5])}")
    print("\n  A file needs a learner column, a date column, and a mark")
    print("  (code or status). Name the slot outright, or give a group and")
    print("  a period and it will be resolved against the timetable.\n")
    print("  " + importer.template_csv().replace("\n", "\n  "))
    _pause()


_IMPORT_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Preview & apply a CSV", import_preview),
    ("Batches / rollback",    import_batches),
    ("File format",           import_template),
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
            logger.exception("Capture CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


# ═══ Signing in and out of site ═════════════════════════════════════

def signout_out() -> None:
    print("\n═══ Sign Out of Site ═══")
    try:
        student_id = _input("Student ID", allow_empty=False)
        reason = _pick_from("Reason", list(signout.REASONS),
                            default=signout.FREE_PERIOD)
        detail = None
        if reason in signout.DETAIL_REQUIRED:
            detail = _input("Detail (who / why)", allow_empty=False)
        expected = None
        if reason not in signout.NO_RETURN:
            expected = _input("Expected back (HH:MM, blank if unknown)") or None
        permission = _yes("Parent permission given? (y/N)")
        permission_from = (_input("Permission from (name)") or None
                           if permission else None)
        authorised = None
        if reason == signout.EARLY_LEAVE and not permission:
            authorised = _input("Authorised by (staff)", allow_empty=False)
        trip = signout.sign_out(
            student_id, reason, detail=detail, expected_back=expected,
            parent_permission=permission, permission_from=permission_from,
            authorised_by=authorised, via="Desk",
            recorded_by=_input("Recorded by") or None)
        print(f"\n  ✓ {trip.label}")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        print("\n  Cancelled.")
    _pause()


def signout_in() -> None:
    print("\n═══ Sign Back In ═══")
    try:
        trip = signout.sign_in(_input("Student ID", allow_empty=False),
                               via="Desk")
        print(f"\n  ✓ Back at {trip.in_time} (out since {trip.out_time}).")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        print("\n  Cancelled.")
    _pause()


def signout_off_site() -> None:
    print("\n═══ Currently Off Site ═══")
    print("\n  The list a fire marshal needs: signed out and not back.")
    rows = signout.currently_off_site()
    if not rows:
        print("\n  ✓ Nobody is signed out.")
    else:
        for trip in rows:
            flag = ""
            if trip.minutes_overdue():
                flag = f"  ⚠ {trip.minutes_overdue()} min overdue"
            perm = "parent ✓" if trip.parent_permission else "no parent permission"
            print(f"    {trip.label}  [{perm}]{flag}")
    _pause()


def signout_late() -> None:
    print("\n═══ Late Returns ═══")
    rows = signout.late_returns()
    if not rows:
        print("\n  ✓ Nobody is overdue.")
        _pause()
        return
    for trip in rows:
        chased = " (alert raised)" if trip.late_alert_at else ""
        print(f"    {trip.label} — {trip.minutes_overdue()} min overdue"
              f"{chased}")
    try:
        if _yes("\n  Raise alerts for the new ones? (y/N)"):
            result = signout.raise_late_alerts(
                raised_by=_input("Raised by") or None,
                notify_guardian=_yes("  Queue a message home too? (y/N)"))
            print(f"\n  ✓ {result.summary}")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        print("\n  Cancelled.")
    _pause()


def signout_log() -> None:
    print("\n═══ Sign-out Log ═══")
    try:
        date = _input("Date (YYYY-MM-DD)", default=_today())
        rows = signout.list_signouts(date=date)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        return
    if not rows:
        print("\n  No sign-outs that day.")
    for trip in rows:
        back = trip.in_time or ("—" if trip.returning else "left")
        print(f"    #{trip.signout_id:<5}{trip.out_time} → {back:<6} "
              f"{(trip.student_name or trip.student_id)[:22]:<23}"
              f"{trip.reason:<22}{trip.state}")
    summary = signout.day_summary(date=date)
    if summary:
        print("\n  " + ", ".join(f"{k}: {v}" for k, v in summary.items()))
    _pause()


def signout_requests_review() -> None:
    print("\n═══ Sign-out Requests ═══")
    print("\n  Learners ask ahead from the student portal. Approving does not")
    print("  sign them out — use \"Sign out an approved request\" when they leave.")
    rows = signout_requests.pending()
    if not rows:
        print("\n  ✓ Nothing waiting for a decision.")
        _pause()
        return
    for i, r in enumerate(rows, 1):
        aware = "parent aware" if r.parent_aware else "parent not told"
        print(f"  {i:>2}. #{r.request_id:<5}{(r.student_name or r.student_id)[:22]:<23}"
              f"{r.describe()}  [{aware}]")
    try:
        pick = _input("Decide which (number, blank to go back)")
        if not pick:
            return
        if not (pick.isdigit() and 1 <= int(pick) <= len(rows)):
            print("  ✗ Pick a number from the list.")
            _pause()
            return
        req = rows[int(pick) - 1]
        by = _input("Your name", allow_empty=False)
        if _yes("  Approve? (y = approve, N = decline)"):
            out = signout_requests.approve(req.request_id, by=by,
                                           note=_input("Note (optional)") or None)
        else:
            out = signout_requests.decline(
                req.request_id, by=by,
                note=_input("Why (the learner sees this)", allow_empty=False))
        print(f"\n  ✓ Request #{out.request_id} {out.state.lower()}.")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        print("\n  Cancelled.")
    _pause()


def signout_use_request() -> None:
    print("\n═══ Sign Out an Approved Request ═══")
    rows = signout_requests.approved_for_today()
    if not rows:
        print("\n  No approved requests for today.")
        _pause()
        return
    for i, r in enumerate(rows, 1):
        print(f"  {i:>2}. {(r.student_name or r.student_id)[:22]:<23}{r.describe()}"
              f" (approved by {r.decided_by})")
    try:
        pick = _input("Sign out which (number)", allow_empty=False)
        if not (pick.isdigit() and 1 <= int(pick) <= len(rows)):
            print("  ✗ Pick a number from the list.")
            _pause()
            return
        permission = _yes("Parent permission given? (y/N)")
        trip = signout_requests.use_request(
            rows[int(pick) - 1].request_id,
            recorded_by=_input("Recorded by", allow_empty=False),
            parent_permission=permission,
            permission_from=(_input("Permission from (name)") or None
                             if permission else None))
        print(f"\n  ✓ {trip.label}")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        print("\n  Cancelled.")
    _pause()


_SIGNOUT_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Sign out",          signout_out),
    ("Sign back in",      signout_in),
    ("Currently off site", signout_off_site),
    ("Late returns & alerts", signout_late),
    ("Day's log",         signout_log),
    ("Sign-out requests (approve / decline)", signout_requests_review),
    ("Sign out an approved request", signout_use_request),
]


def kiosk_menu() -> None:
    _run_menu("Kiosk & Check-in", _KIOSK_MENU)


def signout_menu() -> None:
    _run_menu("Signing In & Out of Site", _SIGNOUT_MENU)


def offline_menu() -> None:
    _run_menu("Offline Registers", _OFFLINE_MENU)


def cover_menu() -> None:
    _run_menu("Cover", _COVER_MENU)


def import_menu() -> None:
    _run_menu("Bulk Import", _IMPORT_MENU)


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Kiosk & Check-in",   kiosk_menu),
    ("Offline Registers",  offline_menu),
    ("Cover",              cover_menu),
    ("Bulk Import",        import_menu),
    ("Signing In & Out of Site", signout_menu),
]


def run() -> None:
    _run_menu("Capture (kiosk / offline / cover / import)", _MENU)
