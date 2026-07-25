"""CLI flows for Sixth Form Calendar."""

from __future__ import annotations

import datetime as _dt
import logging
from typing import Any, Callable
from education_system.systems.primary.domain.academics.calendar import (
    calendar as data,
)
from education_system.systems.primary.domain.academics.calendar.calendar import (
    AUDIENCES,
    DEFAULT_AUDIENCE,
    DEFAULT_EVENT_TYPE,
    DEFAULT_STATUS,
    EVENT_TYPES,
    Event,
    STATUSES,
    ValidationError,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


# ── Prompt helpers ─────────────────────────────────────────────────

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


def _yes_no(prompt: str, *, default: bool = False) -> bool:
    raw = _input(f"{prompt} (y/n)",
                  default="y" if default else "n").strip().lower()
    return raw in ("y", "yes")


def _pick_from(label: str, options: list[str],
                default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}",
                      default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number (or 'cancel' to abort).")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _pick_event() -> Event:
    rows = data.list_events(upcoming_only=False)
    if not rows:
        print("    No events.")
        raise _UserAbort
    print("\n  Events:")
    for i, e in enumerate(rows, 1):
        when = (e.start_date if not e.is_multiday
                 else f"{e.start_date}..{e.end_date}")
        print(f"    {i:>3}) #{e.event_id}  {when}  "
              f"{e.title[:34]:<34}  [{e.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or event id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((e for e in rows if e.event_id == n), None)
            if match:
                return match
        print("    No matching event.")


# ── Print helpers ──────────────────────────────────────────────────

def _print_events(rows: list[Event]) -> None:
    if not rows:
        print("\n  (no events)")
        return
    print()
    print(f"  {'#':>4}  {'Date':<23}  {'Time':<13}  "
          f"{'Type':<18}  {'Audience':<10}  Title  ·  Location")
    print("  " + "-" * 110)
    for e in rows:
        when = (e.start_date if not e.is_multiday
                 else f"{e.start_date} → {e.end_date}")
        title = e.title[:46]
        loc = (" · " + e.location) if e.location else ""
        print(f"  {e.event_id:>4}  {when:<23}  "
              f"{e.time_label:<13}  "
              f"{e.event_type[:18]:<18}  "
              f"{e.audience[:10]:<10}  {title}{loc}")
    print(f"\n  {len(rows)} event(s).")


# ── Flows ──────────────────────────────────────────────────────────

def today_view() -> None:
    print("\n═══ Today ═══")
    today = _dt.date.today().isoformat()
    _print_events(data.events_on(today))
    _pause()


def this_week() -> None:
    print("\n═══ This Week ═══")
    _print_events(data.events_in_week(_dt.date.today().isoformat()))
    _pause()


def upcoming_view() -> None:
    print("\n═══ Upcoming Events ═══")
    try:
        days = int(_input("Window (days)", default="30"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    today = _dt.date.today()
    cutoff = (today + _dt.timedelta(days=days)).isoformat()
    rows = data.list_events(
        date_from=today.isoformat(),
        date_to=cutoff,
        upcoming_only=True,
    )
    _print_events(rows)
    _pause()


def list_all() -> None:
    print("\n═══ All Events ═══")
    _print_events(data.list_events())
    _pause()


def filter_events_flow() -> None:
    print("\n═══ Filter Events ═══")
    try:
        etype = _input(f"Type ({'/'.join(EVENT_TYPES)})") or None
        audience = _input(f"Audience ({'/'.join(AUDIENCES)})") or None
        status = _input(f"Status ({'/'.join(STATUSES)})") or None
        title = _input("Title contains") or None
        location = _input("Location contains") or None
        organiser = _input("Organiser contains") or None
        date_from = _input("From (YYYY-MM-DD)") or None
        date_to = _input("To (YYYY-MM-DD)") or None
        upcoming = _yes_no("Upcoming only?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_events(
            event_type=etype, audience=audience, status=status,
            title_like=title, location_like=location,
            organiser_like=organiser,
            date_from=date_from, date_to=date_to,
            upcoming_only=upcoming,
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_events(rows)
    _pause()


def view_event_flow() -> None:
    print("\n═══ View Event ═══")
    try:
        e = _pick_event()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    print()
    print(f"    #{e.event_id}  {e.title}")
    print(f"    Type        : {e.event_type}")
    print(f"    Status      : {e.status}")
    print(f"    Audience    : {e.audience}")
    if e.is_multiday:
        print(f"    Dates       : {e.start_date} → {e.end_date}  "
              f"({e.day_count} days)")
    else:
        print(f"    Date        : {e.start_date}")
    print(f"    Time        : {e.time_label}")
    print(f"    Location    : {e.location or '—'}")
    print(f"    Organiser   : {e.organiser or '—'}")
    print(f"    Capacity    : {e.capacity if e.capacity is not None else '—'}")
    print(f"    RSVP needed : {'yes' if e.rsvp_required else 'no'}")
    if e.cost is not None:
        print(f"    Cost        : £{e.cost:.2f}")
    if e.description:
        print()
        print("    Description:")
        for line in e.description.splitlines():
            print(f"      {line}")
    if e.notes:
        print()
        print("    Notes:")
        for line in e.notes.splitlines():
            print(f"      {line}")
    _pause()


def _collect_form(existing: Event | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    payload["title"] = _input(
        "Title",
        default=(existing.title if is_edit else ""),
        allow_empty=False)
    payload["event_type"] = _pick_from(
        "Event type", list(EVENT_TYPES),
        default=(existing.event_type if is_edit
                  else DEFAULT_EVENT_TYPE))
    payload["audience"] = _pick_from(
        "Audience", list(AUDIENCES),
        default=(existing.audience if is_edit else DEFAULT_AUDIENCE))
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS))
    payload["start_date"] = _input(
        "Start date (YYYY-MM-DD)",
        default=(existing.start_date if is_edit
                  else _dt.date.today().isoformat()),
        allow_empty=False)
    payload["end_date"] = _input(
        "End date (YYYY-MM-DD)",
        default=(existing.end_date if is_edit
                  else payload["start_date"]))
    payload["all_day"] = _yes_no(
        "All-day event?",
        default=(existing.all_day if is_edit else False))
    if not payload["all_day"]:
        payload["start_time"] = _input(
            "Start time (HH:MM)",
            default=(existing.start_time[:5]
                      if is_edit and existing.start_time else ""))
        payload["end_time"] = _input(
            "End time (HH:MM)",
            default=(existing.end_time[:5]
                      if is_edit and existing.end_time else ""))
    payload["location"] = _input(
        "Location",
        default=(existing.location or "") if is_edit else "")
    payload["organiser"] = _input(
        "Organiser",
        default=(existing.organiser or "") if is_edit else "")
    payload["capacity"] = _input(
        "Capacity (optional)",
        default=(str(existing.capacity)
                  if is_edit and existing.capacity is not None else ""))
    payload["cost"] = _input(
        "Cost (optional)",
        default=(str(existing.cost)
                  if is_edit and existing.cost is not None else ""))
    payload["rsvp_required"] = _yes_no(
        "RSVP required?",
        default=(existing.rsvp_required if is_edit else False))
    payload["description"] = _input(
        "Description",
        default=(existing.description or "") if is_edit else "")
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_event() -> None:
    print("\n═══ New Event ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        e = data.create_event(payload)
    except ValidationError as ex:
        print(f"\n  ✗ {ex}")
        _pause()
        return
    print(f"\n  ✓ Created event #{e.event_id} {e.title!r}")
    _pause()


def edit_event() -> None:
    print("\n═══ Edit Event ═══")
    try:
        e = _pick_event()
        payload = _collect_form(e)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_event(e.event_id, payload)
    except ValidationError as ex:
        print(f"\n  ✗ {ex}")
        _pause()
        return
    print(f"\n  ✓ Updated #{e.event_id}")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        e = _pick_event()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=e.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(e.event_id, new_status)
    except ValidationError as ex:
        print(f"\n  ✗ {ex}")
        _pause()
        return
    print(f"\n  ✓ #{e.event_id} → {new_status}")
    _pause()


def delete_event_flow() -> None:
    print("\n═══ Delete Event ═══")
    try:
        e = _pick_event()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete event #{e.event_id} ({e.title})? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_event(e.event_id):
        print(f"\n  ✓ Deleted #{e.event_id}")
    _pause()


def lookup_date() -> None:
    print("\n═══ Events on a Date ═══")
    try:
        s = _input("Date (YYYY-MM-DD)",
                    default=_dt.date.today().isoformat(),
                    allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.events_on(s)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"\n  {len(rows)} event(s) on {s}:")
    _print_events(rows)
    _pause()


def summary_flow() -> None:
    print("\n═══ Calendar Summary ═══")
    try:
        win = int(_input("Upcoming window (days)", default="14"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    summ = data.summary(upcoming_window_days=win)
    print(f"\n  Total events       : {summ.total}")
    print(f"  Today              : {summ.today_count}")
    print(f"  This week          : {summ.this_week_count}")
    print(f"  Upcoming ({win}d)     : {summ.upcoming}")
    print("\n  By status:")
    for s in STATUSES:
        n = summ.by_status.get(s, 0)
        if n:
            print(f"    {s:<14} : {n}")
    print("\n  By type:")
    for t in EVENT_TYPES:
        n = summ.by_type.get(t, 0)
        if n:
            print(f"    {t:<20} : {n}")
    print("\n  By audience:")
    for a in AUDIENCES:
        n = summ.by_audience.get(a, 0)
        if n:
            print(f"    {a:<14} : {n}")
    _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Today",                today_view),
    ("This week",            this_week),
    ("Upcoming",             upcoming_view),
    ("List all",             list_all),
    ("Filter",               filter_events_flow),
    ("View event",           view_event_flow),
    ("New event",            new_event),
    ("Edit event",           edit_event),
    ("Change status",        set_status_flow),
    ("Delete event",         delete_event_flow),
    ("Look up a date",       lookup_date),
    ("Summary",              summary_flow),
]


def run() -> None:
    while True:
        print("\n── Calendar ──")
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
            logger.exception("Calendar CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Calendar":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Calendar CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
