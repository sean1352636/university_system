"""The calendar: reviews, training, assessments and deadlines by day.

Exposes: menu.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date, timedelta
from functools import partial

from education_system.systems.apprenticeships.domain.workspace.items import group_by_day
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.services import calendar_service
from education_system.systems.apprenticeships.services.access import Actor

logger = logging.getLogger(__name__)


def menu(actor: Actor) -> None:
    entries: list[tuple[str, Callable[[], None]]] = [
        ("Next 7 days", partial(_show, actor, 7)),
        ("Next 28 days", partial(_show, actor, 28)),
        ("Next 3 months", partial(_show, actor, 91)),
        ("Choose dates", partial(_choose, actor)),
        ("Export to a calendar file (.ics)", partial(_export, actor)),
    ]
    prompts.run_menu("Calendar", entries)


def _show(actor: Actor, days: int) -> None:
    start = date.today()
    _agenda(actor, start, start + timedelta(days=days - 1))


def _choose(actor: Actor) -> None:
    start, end = _ask_range()
    _agenda(actor, start, end)


def _agenda(actor: Actor, start: date, end: date) -> None:
    diary = calendar_service.events(actor, date_from=start, date_to=end)
    prompts.title(f"Calendar — {start:%a %d %b} to {end:%a %d %b %Y}")
    if not diary:
        prompts.note("  Nothing is in your diary for these dates.")
    for _day, events in group_by_day(diary):
        prompts.note(f"\n  {events[0].weekday}")
        for event in events:
            when = event.time or "all day"
            detail = f"  ({event.detail})" if event.detail else ""
            prompts.note(f"    {when:<8} {event.kind:<9} {event.title}{detail}")
    prompts.pause()


def _export(actor: Actor) -> None:
    start, end = _ask_range()
    path = calendar_service.export_ics(actor, date_from=start, date_to=end)
    prompts.ok(f"Saved to {path}")
    prompts.note("Import it into Outlook, Google Calendar or Apple Calendar.")
    prompts.pause()


def _ask_range() -> tuple[date, date]:
    today = date.today()
    start = prompts.ask("From (YYYY-MM-DD)", default=today.isoformat(), required=True)
    end = prompts.ask(
        "To (YYYY-MM-DD)", default=(today + timedelta(days=27)).isoformat(), required=True
    )
    try:
        return date.fromisoformat(start), date.fromisoformat(end)
    except ValueError:
        prompts.fail("Dates must be in YYYY-MM-DD format.")
        raise prompts.Abort from None
