"""A learner's own weekly timetable."""

from __future__ import annotations

import logging
from datetime import datetime
from tkinter import ttk

from education_system.systems.fe_college.interfaces.gui import timetable_grid
from education_system.systems.fe_college.interfaces.gui import widgets as w

logger = logging.getLogger(__name__)

TITLE = "My timetable"


def open_window(host) -> None:
    Screen(host)


class Screen:
    def __init__(self, host):
        self.host = host
        self.ctl = host.ctl
        host.clear_content()
        parent = host.content_frame

        w.page_header(
            parent, TITLE,
            "Every class on the courses you are enrolled on. Today is "
            "highlighted.",
            actions=[
                ("Printable version", self.export),
                ("↻ Refresh", self.refresh),
            ],
        )

        if not self.ctl.student_id:
            w.empty_state(parent, "Your account is not linked to a learner record.")
            return

        self.today_holder = ttk.Frame(parent)
        self.today_holder.pack(fill="x", pady=(0, 8))
        self.grid_holder = ttk.Frame(parent)
        self.grid_holder.pack(fill="both", expand=True)
        self.refresh()

    def refresh(self) -> None:
        try:
            self.timetable = self.ctl.timetable.for_student(self.ctl.student_id)
        except Exception as exc:
            logger.exception("Could not load the FE College learner timetable")
            w.error(self.host, TITLE, f"Could not load your timetable: {exc}")
            return

        today = datetime.now().strftime("%A")
        today_count = sum(
            len(self.timetable.at(today, code))
            for code, _s, _e in self.ctl.timetable.periods()
        )

        w.clear(self.today_holder)
        w.kpi_row(self.today_holder, [
            ("Classes this week", str(self.timetable.total_sessions),
             f"{self.timetable.hours:g} taught hours", "plain"),
            (f"Classes today ({today})", str(today_count),
             "nothing today" if not today_count else "check the grid below",
             "muted" if not today_count else "plain"),
        ])

        w.clear(self.grid_holder)
        if self.timetable.total_sessions == 0:
            w.empty_state(
                self.grid_holder,
                "Nothing is timetabled for your courses yet. Timetables are "
                "usually published shortly before term starts.",
            )
            self.host.set_status("No timetabled classes")
            return

        timetable_grid.render(
            self.grid_holder, self.timetable, self.ctl, highlight_day=today,
        )
        self.host.set_status(
            f"{self.timetable.total_sessions} class(es) · "
            f"{self.timetable.hours:g} hours per week"
        )

    def export(self) -> None:
        w.show_text(
            self.host, "My timetable",
            self.ctl.timetable.as_text(self.timetable),
            width=100, height=24,
        )


__all__ = ["TITLE", "Screen", "open_window"]
