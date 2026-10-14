"""CLI flows for the Primary School Governance register."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable

from education_system.systems.primary.domain.governance import governance as data
from education_system.systems.primary.domain.governance.governance import (
    DEFAULT_GOVERNOR_ROLE,
    DEFAULT_GOVERNOR_STATUS,
    DEFAULT_MEETING_KIND,
    DEFAULT_MEETING_STATUS,
    GOVERNOR_ROLES,
    GOVERNOR_STATUSES,
    Governor,
    Meeting,
    MEETING_KINDS,
    MEETING_STATUSES,
    ValidationError,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


def _input(prompt: str, *, default: str = "",
            allow_empty: bool = True) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    s = raw.strip()
    if s.lower() == "cancel":
        raise _UserAbort
    if not s:
        if default:
            return default
        if not allow_empty:
            print("    Value is required.")
            return _input(prompt, default=default, allow_empty=False)
        return ""
    return s


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _pick(label: str, options: list[str],
           default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}", default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number (or 'cancel').")
            continue
        n = int(raw)
        if 1 <= n <= len(options):
            return options[n - 1]
        print("    Out of range.")


# ── Print helpers ──────────────────────────────────────────────────

def _print_governors(rows: list[Governor]) -> None:
    if not rows:
        print("\n  (no governors)")
        return
    print()
    print(f"  {'#':>4}  {'Name':<26}  {'Role':<16}  "
          f"{'Term end':<10}  {'Status':<10}")
    print("  " + "-" * 78)
    for g in rows:
        print(f"  {g.governor_id:>4}  {g.full_name[:26]:<26}  "
              f"{g.role[:16]:<16}  {g.term_end or '—':<10}  "
              f"{g.status:<10}")
    print(f"\n  {len(rows)} governor(s).")


def _print_meetings(rows: list[Meeting]) -> None:
    if not rows:
        print("\n  (no meetings)")
        return
    print()
    print(f"  {'#':>4}  {'Date':<10}  {'Kind':<12}  {'Title':<32}  "
          f"{'Att':>3}  {'Status':<10}")
    print("  " + "-" * 84)
    for m in rows:
        print(f"  {m.meeting_id:>4}  {m.meeting_date:<10}  "
              f"{m.kind:<12}  {m.title[:32]:<32}  "
              f"{m.attendees:>3}  {m.status:<10}")
    print(f"\n  {len(rows)} meeting(s).")


# ── Governor flows ─────────────────────────────────────────────────

def list_governors_flow() -> None:
    print("\n═══ Governors ═══")
    _print_governors(data.list_governors())
    _pause()


def filter_governors_flow() -> None:
    print("\n═══ Filter Governors ═══  (blank = skip)")
    try:
        role = _input(f"Role ({'/'.join(GOVERNOR_ROLES)})")
        status = _input(f"Status ({'/'.join(GOVERNOR_STATUSES)})")
        query = _input("Name/notes contains")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_governors(role=role or None, status=status or None,
                                     query=query or None)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_governors(rows)
    _pause()


def new_governor_flow() -> None:
    print("\n═══ New Governor ═══")
    try:
        name = _input("Full name", allow_empty=False)
        role = _pick("Role", list(GOVERNOR_ROLES), default=DEFAULT_GOVERNOR_ROLE)
        email = _input("Email (optional)")
        phone = _input("Phone (optional)")
        term_start = _input("Term start YYYY-MM-DD (optional)")
        term_end = _input("Term end YYYY-MM-DD (optional)")
        status = _pick("Status", list(GOVERNOR_STATUSES),
                        default=DEFAULT_GOVERNOR_STATUS)
        notes = _input("Notes (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        g = data.create_governor({
            "full_name": name, "role": role, "email": email,
            "phone": phone, "term_start": term_start or None,
            "term_end": term_end or None, "status": status,
            "notes": notes or None,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created governor #{g.governor_id} — {g.full_name}")
    _pause()


def edit_governor_flow() -> None:
    print("\n═══ Edit Governor ═══")
    try:
        gid = int(_input("Governor ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("  ✗ Governor ID must be a number.")
        _pause()
        return
    existing = data.get_governor(gid)
    if existing is None:
        print(f"  ✗ No governor #{gid}")
        _pause()
        return
    print(f"\n  Editing #{gid} — {existing.full_name}")
    print("  (Enter to keep existing)")
    try:
        name = _input("Full name", default=existing.full_name)
        role = _pick("Role", list(GOVERNOR_ROLES), default=existing.role)
        email = _input("Email", default=existing.email or "")
        phone = _input("Phone", default=existing.phone or "")
        term_start = _input("Term start", default=existing.term_start or "")
        term_end = _input("Term end", default=existing.term_end or "")
        status = _pick("Status", list(GOVERNOR_STATUSES),
                        default=existing.status)
        notes = _input("Notes", default=existing.notes or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        g = data.update_governor(gid, {
            "full_name": name, "role": role, "email": email,
            "phone": phone, "term_start": term_start or None,
            "term_end": term_end or None, "status": status,
            "notes": notes or None,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{g.governor_id}")
    _pause()


def delete_governor_flow() -> None:
    print("\n═══ Delete Governor ═══")
    try:
        gid = int(_input("Governor ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("  ✗ Governor ID must be a number.")
        _pause()
        return
    existing = data.get_governor(gid)
    if existing is None:
        print(f"  ✗ No governor #{gid}")
        _pause()
        return
    confirm = _input(
        f"Delete '#{gid} — {existing.full_name}'? Type 'yes'",
        default="no")
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_governor(gid):
        print(f"\n  ✓ Deleted #{gid}")
    _pause()


# ── Meeting flows ──────────────────────────────────────────────────

def list_meetings_flow() -> None:
    print("\n═══ Governance Meetings ═══")
    _print_meetings(data.list_meetings())
    _pause()


def upcoming_meetings_flow() -> None:
    print("\n═══ Upcoming Meetings ═══")
    today = _date.today().isoformat()
    rows = [m for m in data.list_meetings(status="Scheduled")
            if m.meeting_date >= today]
    rows.sort(key=lambda m: m.meeting_date)
    _print_meetings(rows)
    _pause()


def new_meeting_flow() -> None:
    print("\n═══ New Meeting ═══")
    try:
        date_s = _input("Meeting date YYYY-MM-DD", allow_empty=False)
        kind = _pick("Kind", list(MEETING_KINDS), default=DEFAULT_MEETING_KIND)
        title = _input("Title", allow_empty=False)
        chair = _input("Chair (optional)")
        attendees = _input("Attendees count", default="0")
        minutes = _input("Minutes ref (optional)")
        decisions = _input("Decisions / notes (optional)")
        status = _pick("Status", list(MEETING_STATUSES),
                        default=DEFAULT_MEETING_STATUS)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        m = data.create_meeting({
            "meeting_date": date_s, "kind": kind, "title": title,
            "chair": chair, "attendees": attendees,
            "minutes_ref": minutes or None,
            "decisions": decisions or None,
            "status": status,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created meeting #{m.meeting_id} — {m.title}")
    _pause()


def edit_meeting_flow() -> None:
    print("\n═══ Edit Meeting ═══")
    try:
        mid = int(_input("Meeting ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("  ✗ Meeting ID must be a number.")
        _pause()
        return
    existing = data.get_meeting(mid)
    if existing is None:
        print(f"  ✗ No meeting #{mid}")
        _pause()
        return
    print(f"\n  Editing #{mid} — {existing.title}")
    try:
        date_s = _input("Meeting date", default=existing.meeting_date)
        kind = _pick("Kind", list(MEETING_KINDS), default=existing.kind)
        title = _input("Title", default=existing.title)
        chair = _input("Chair", default=existing.chair or "")
        attendees = _input("Attendees", default=str(existing.attendees))
        minutes = _input("Minutes ref", default=existing.minutes_ref or "")
        decisions = _input("Decisions", default=existing.decisions or "")
        status = _pick("Status", list(MEETING_STATUSES),
                        default=existing.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        m = data.update_meeting(mid, {
            "meeting_date": date_s, "kind": kind, "title": title,
            "chair": chair, "attendees": attendees,
            "minutes_ref": minutes or None,
            "decisions": decisions or None,
            "status": status,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated meeting #{m.meeting_id}")
    _pause()


def mark_held_flow() -> None:
    print("\n═══ Mark Meeting Held ═══")
    try:
        mid = int(_input("Meeting ID", allow_empty=False))
        attendees = _input("Attendees count (optional)")
        minutes = _input("Minutes ref (optional)")
        decisions = _input("Decisions (optional)")
    except (ValueError, _UserAbort):
        print("  ✗ Cancelled or invalid input.")
        _pause()
        return
    payload: dict[str, Any] = {}
    if attendees:
        try:
            payload["attendees"] = int(attendees)
        except ValueError:
            print("  ✗ Attendees must be a whole number.")
            _pause()
            return
    if minutes:
        payload["minutes_ref"] = minutes
    if decisions:
        payload["decisions"] = decisions
    try:
        m = data.mark_held(mid, **payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Marked meeting #{m.meeting_id} held.")
    _pause()


def delete_meeting_flow() -> None:
    print("\n═══ Delete Meeting ═══")
    try:
        mid = int(_input("Meeting ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("  ✗ Meeting ID must be a number.")
        _pause()
        return
    existing = data.get_meeting(mid)
    if existing is None:
        print(f"  ✗ No meeting #{mid}")
        _pause()
        return
    confirm = _input(
        f"Delete '#{mid} — {existing.title}'? Type 'yes'",
        default="no")
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_meeting(mid):
        print(f"\n  ✓ Deleted #{mid}")
    _pause()


# ── Summary ────────────────────────────────────────────────────────

def summary_flow() -> None:
    print("\n═══ Governance Summary ═══")
    try:
        s = data.summary()
    except Exception as e:
        logger.exception("summary failed")
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"\n  Governors total          : {s.governors_total}")
    print(f"  Active                   : {s.governors_active}")
    print(f"  Term ending within 90d   : {s.term_expiring_90d}")
    print(f"\n  Meetings total           : {s.meetings_total}")
    print(f"  Scheduled / Held / Cancl.: "
          f"{s.meetings_scheduled} / {s.meetings_held} / "
          f"{s.meetings_cancelled}")
    if s.next_meeting:
        print(f"  Next meeting             : "
              f"#{s.next_meeting.meeting_id} {s.next_meeting.meeting_date} "
              f"— {s.next_meeting.title}")
    else:
        print("  Next meeting             : (none scheduled)")
    if s.last_held:
        print(f"  Last held                : "
              f"#{s.last_held.meeting_id} {s.last_held.meeting_date} "
              f"— {s.last_held.title}")
    print("\n  Governors by role:")
    for r in GOVERNOR_ROLES:
        print(f"    {r:<18}  {s.governors_by_role.get(r, 0):>3}")
    print("\n  Governors by status:")
    for st in GOVERNOR_STATUSES:
        print(f"    {st:<18}  {s.governors_by_status.get(st, 0):>3}")
    _pause()


# ── Submenu dispatch ───────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Summary",             summary_flow),
    ("List Governors",      list_governors_flow),
    ("Filter Governors",    filter_governors_flow),
    ("New Governor",        new_governor_flow),
    ("Edit Governor",       edit_governor_flow),
    ("Delete Governor",     delete_governor_flow),
    ("List Meetings",       list_meetings_flow),
    ("Upcoming Meetings",   upcoming_meetings_flow),
    ("New Meeting",         new_meeting_flow),
    ("Edit Meeting",        edit_meeting_flow),
    ("Mark Meeting Held",   mark_held_flow),
    ("Delete Meeting",      delete_meeting_flow),
]


def run() -> None:
    while True:
        print("\n── Governance ──")
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
            logger.exception("Governance CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Governance":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Governance CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
