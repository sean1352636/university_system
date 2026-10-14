"""CLI flows for calendar communications: the message queue.

Submenu hung off Calendar, fronting :mod:`calendar_notifications` —
sweep the reminders, queue RSVP requests and the week-ahead digest,
inspect what is waiting, send it, or pull something before it goes.
Borrows the prompt helpers from :mod:`calendar_cli`.
"""

from __future__ import annotations

import logging
from typing import Callable

from education_system.systems.sixth_form.domain.academics.calendar import (
    calendar_notifications as notifications,
)
from education_system.systems.sixth_form.domain.academics.calendar.calendar import (
    ValidationError,
)
from education_system.systems.sixth_form.interfaces.cli.academics.calendar.calendar_cli import (
    _input,
    _pause,
    _pick_event,
    _pick_from,
    _UserAbort,
    _yes_no,
)

logger = logging.getLogger(__name__)


def queue_view() -> None:
    print("\n═══ Message Queue ═══")
    state = _pick_from("State",
                        [""] + list(notifications.STATES),
                        default=notifications.QUEUED) or None
    rows = notifications.list_notifications(state=state or None)
    if not rows:
        print("\n  (no messages)")
        _pause()
        return
    print()
    for n in rows:
        print(f"  {n.notification_id:>4}  [{n.kind:<16}] "
              f"{n.state:<9} → {n.recipient[:26]:<26} "
              f"{n.subject[:40]}")
    print(f"\n  {len(rows)} message(s).")
    _pause()


def preview_flow() -> None:
    print("\n═══ Preview a Message ═══")
    try:
        raw = _input("Message #", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if not raw.strip().lstrip("#").isdigit():
        print("  Enter a number.")
        _pause()
        return
    n = notifications.get_notification(int(raw.strip().lstrip("#")))
    if n is None:
        print("  No such message.")
        _pause()
        return
    print(f"\n  To:      {n.recipient}")
    print(f"  Subject: {n.subject}")
    print(f"  State:   {n.state}"
          + (f" ({n.detail})" if n.detail else ""))
    print("  " + "-" * 56)
    for line in n.body.splitlines():
        print(f"  {line}")
    _pause()


def sweep_reminders_flow() -> None:
    n = notifications.sweep_reminders()
    print(f"\n  ✓ {n} reminder(s) queued.")
    _pause()


def week_ahead_flow() -> None:
    n = notifications.queue_week_ahead()
    print(f"\n  ✓ {n} week-ahead digest(s) queued.")
    _pause()


def rsvp_request_flow() -> None:
    print("\n═══ RSVP Request ═══")
    try:
        event = _pick_event()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        got = notifications.queue_rsvp_request(event.event_id)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    if got is None:
        print("  Already requested for this event.")
    else:
        print(f"  ✓ Queued to {got.recipient}.")
    _pause()


def send_flow() -> None:
    print("\n═══ Send Queued ═══")
    queued = notifications.list_notifications(
        state=notifications.QUEUED)
    direct = [n for n in queued if not n.is_broadcast]
    broadcast = len(queued) - len(direct)
    if not direct:
        print(f"\n  Nothing directly addressed to send"
              f" ({broadcast} broadcast row(s) stay queued).")
        _pause()
        return
    if not _yes_no(f"Send {len(direct)} message(s) now",
                    default=True):
        print("\n  Cancelled.")
        return
    sent, failed = notifications.send_queued()
    print(f"\n  {sent} sent, {failed} failed"
          + (f"; {broadcast} broadcast row(s) left queued."
             if broadcast else "."))
    _pause()


def cancel_flow() -> None:
    print("\n═══ Cancel a Message ═══")
    try:
        raw = _input("Message #", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if not raw.strip().lstrip("#").isdigit():
        print("  Enter a number.")
        _pause()
        return
    if notifications.cancel_notification(
            int(raw.strip().lstrip("#"))):
        print("  ✓ Cancelled.")
    else:
        print("  Only queued messages can be cancelled.")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("View queue",          queue_view),
    ("Preview a message",   preview_flow),
    ("Sweep reminders",     sweep_reminders_flow),
    ("Queue week ahead",    week_ahead_flow),
    ("RSVP request",        rsvp_request_flow),
    ("Send queued",         send_flow),
    ("Cancel a message",    cancel_flow),
]


def run() -> None:
    while True:
        print("\n── Calendar · Communications ──")
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
            logger.exception("Calendar comms CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()
