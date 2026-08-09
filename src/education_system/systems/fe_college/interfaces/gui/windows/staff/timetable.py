"""A lecturer's own weekly timetable.

Read-only: timetabling belongs to the admin screen, which has the clash checks
and the room finder. Here a lecturer sees where they are and can jump straight
to the register for whatever they are teaching.
"""

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
            "Click a session to take its register.",
            actions=[
                ("Export as text", self.export),
                ("↻ Refresh", self.refresh),
            ],
        )

        if not self.ctl.staff_id:
            w.empty_state(parent, "Your account is not linked to a staff record, "
                                  "so you have no timetable.")
            return

        self.summary_holder = ttk.Frame(parent)
        self.summary_holder.pack(fill="x")

        self.grid_holder = ttk.Frame(parent)
        self.grid_holder.pack(fill="both", expand=True)
        self.refresh()

    def refresh(self) -> None:
        try:
            self.timetable = self.ctl.timetable.for_staff(self.ctl.staff_id)
            workload = next(
                (wl for wl in self.ctl.staff.workloads()
                 if wl.staff_id == self.ctl.staff_id), None
            )
        except Exception as exc:
            logger.exception("Could not load the FE College staff timetable")
            w.error(self.host, TITLE, f"Could not load your timetable: {exc}")
            return

        w.clear(self.summary_holder)
        w.kpi_row(self.summary_holder, [
            ("Sessions", str(self.timetable.total_sessions), "per week", "plain"),
            ("Teaching hours", f"{self.timetable.hours:g}",
             f"of {workload.contracted_hours:g} contracted" if workload else "",
             w.tone_for(workload.band) if workload else "plain"),
            ("Load", workload.band if workload else "—",
             f"{w.pct(workload.utilisation_pct)} utilisation" if workload else "",
             w.tone_for(workload.band) if workload else "plain"),
        ])

        w.clear(self.grid_holder)
        timetable_grid.render(
            self.grid_holder, self.timetable, self.ctl,
            on_click=self._open_register,
            highlight_day=datetime.now().strftime("%A"),
        )
        self.host.set_status(
            f"{self.timetable.total_sessions} session(s) · "
            f"{self.timetable.hours:g} hours per week"
        )

    def _open_register(self, session) -> None:
        self.host.open_screen("registers")
        self.host.set_status(
            f"Take the register for {session.course_id} ({session.label})"
        )

    def export(self) -> None:
        w.show_text(
            self.host, "My timetable",
            self.ctl.timetable.as_text(self.timetable),
            width=100, height=24,
        )


__all__ = ["TITLE", "Screen", "open_window"]
