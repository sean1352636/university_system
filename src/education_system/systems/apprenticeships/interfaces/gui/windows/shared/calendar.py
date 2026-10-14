"""The calendar: reviews, training, assessments and deadlines by day.

An agenda rather than a month grid: in a diary this dense, a list of
what happens when is easier to read and to act on than a grid of cells.
The same range can be exported as an .ics file for Outlook, Google
Calendar or Apple Calendar.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import date, timedelta
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.services import calendar_service

logger = logging.getLogger(__name__)

RANGES: tuple[tuple[str, int], ...] = (
    ("Next 7 days", 7),
    ("Next 14 days", 14),
    ("Next 28 days", 28),
    ("Next 3 months", 91),
)

COLUMNS = (
    ("day", "Date", 130),
    ("time", "Time", 70),
    ("kind", "What", 100),
    ("title", "Event", 380),
    ("detail", "Detail", 320),
)


def render(gui: Any, days: int = config.CALENDAR_DEFAULT_DAYS) -> None:
    frame = gui.clear()
    start = date.today()
    end = start + timedelta(days=days - 1)
    widgets.heading(
        frame, "Calendar",
        subtitle=f"{start:%a %d %b} to {end:%a %d %b %Y} — reviews, training, "
                 "assessments and deadlines you are part of.",
    )

    def export() -> None:
        ok, path = widgets.guard(
            lambda: calendar_service.export_ics(gui.actor, date_from=start, date_to=end)
        )
        if ok:
            widgets.inform(
                f"Saved to:\n{path}\n\nImport it into Outlook, Google Calendar or Apple "
                "Calendar. Importing a later export updates these events rather than "
                "duplicating them.",
                title="Calendar exported",
            )

    widgets.button_bar(frame, [
        *((label, lambda n=n: render(gui, n)) for label, n in RANGES),
        ("Export to calendar file…", export),
    ])

    ok, diary = widgets.guard(
        lambda: calendar_service.events(gui.actor, date_from=start, date_to=end)
    )
    if not ok:
        return
    kinds = Counter(e.kind for e in diary)
    widgets.kpi_row(frame, [("Events", len(diary)), *sorted(kinds.items())])
    if not diary:
        widgets.empty_state(frame, "Nothing is in your diary for these dates.")
        return

    by_index = dict(enumerate(diary))

    def open_event(ident: Any) -> None:
        event = by_index.get(int(ident))
        if event is not None and event.opens:
            gui.show(*event.opens)

    table = widgets.DataTable(frame, COLUMNS, on_activate=open_event)
    table.populate(
        list(by_index.items()),
        lambda pair: (pair[1].weekday, pair[1].time or "", pair[1].kind, pair[1].title,
                      pair[1].detail),
        identity=lambda pair: pair[0],
        tag=lambda pair: "Amber" if pair[1].day == start.isoformat() else None,
        noun="event",
    )
