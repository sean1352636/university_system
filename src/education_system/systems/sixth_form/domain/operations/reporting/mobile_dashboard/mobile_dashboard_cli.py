"""CLI flows for the Mobile Dashboard."""

from __future__ import annotations

import logging
from typing import Callable

from education_system.systems.sixth_form.domain.operations.reporting.mobile_dashboard import (
    mobile_dashboard as data,
)
from education_system.systems.sixth_form.domain.operations.reporting.mobile_dashboard.mobile_dashboard import (
    FeedItem,
    MobileDashboard,
    Tile,
)

logger = logging.getLogger(__name__)

_SEV_MARK = {"info": " ", "ok": "✓", "warn": "!", "alert": "✗"}


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _print_tile(t: Tile) -> None:
    mark = _SEV_MARK.get(t.severity, " ")
    print(f"  [{mark}] {t.title:<24} {t.value:>10}   {t.subtitle}")


def _print_feed(label: str, items: list[FeedItem], *, limit: int = 5) -> None:
    print(f"\n  ── {label} ({len(items)}) ──")
    if not items:
        print("    (nothing)")
        return
    for it in items[:limit]:
        mark = _SEV_MARK.get(it.severity, " ")
        when = (it.when or "—")[:10]
        print(f"    [{mark}] {when}  {it.title[:60]}")
        if it.detail:
            print(f"          {it.detail[:70]}")
    if len(items) > limit:
        print(f"    … and {len(items) - limit} more")


def _print_dashboard(d: MobileDashboard) -> None:
    print(f"\n╭─── Mobile Dashboard ── {d.generated_on} ───╮")
    print("│  Tiles")
    for t in d.tiles:
        _print_tile(t)
    print("╰" + "─" * 50)
    _print_feed("Today's Events", d.today_events)
    _print_feed("Upcoming (7 days)", d.upcoming_events)
    _print_feed("Announcements", d.announcements)
    _print_feed("Overdue Targets", d.overdue_targets)
    _print_feed("High/Critical Risk Students", d.high_risk_students)
    _print_feed("Open Early-Warning Alerts", d.open_alerts)


# ── Flows ─────────────────────────────────────────────────────────

def home() -> None:
    print("\n═══ Mobile Dashboard ═══")
    d = data.build_dashboard()
    _print_dashboard(d)
    _pause()


def tiles_only() -> None:
    print("\n═══ Tiles Only ═══")
    d = data.build_dashboard()
    for t in d.tiles:
        _print_tile(t)
    _pause()


def feed_today() -> None:
    print("\n═══ Today ═══")
    d = data.build_dashboard()
    _print_feed("Today's Events", d.today_events, limit=20)
    _print_feed("Announcements", d.announcements, limit=20)
    _pause()


def feed_upcoming() -> None:
    print("\n═══ Upcoming (7 days) ═══")
    d = data.build_dashboard()
    _print_feed("Upcoming Events", d.upcoming_events, limit=50)
    _pause()


def feed_actions() -> None:
    print("\n═══ Action Items ═══")
    d = data.build_dashboard()
    _print_feed("Overdue Targets", d.overdue_targets, limit=20)
    _print_feed("High/Critical Risk", d.high_risk_students, limit=20)
    _print_feed("Open Alerts", d.open_alerts, limit=20)
    _pause()


# ── Menu ──────────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Home (full view)",        home),
    ("Tiles only",              tiles_only),
    ("Today",                   feed_today),
    ("Upcoming (7 days)",       feed_upcoming),
    ("Action items",            feed_actions),
]


def run() -> None:
    while True:
        print("\n── Mobile Dashboard ──")
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
        except Exception as e:
            logger.exception("Mobile dashboard CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Mobile Dashboard":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Mobile dashboard CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
