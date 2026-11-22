"""Attendance Report screen.

Filters: From / To (default this school year to date), Year, Form and an
optional pupil (admission number) - Run works the figures out in the
background. Tabs: Summary (the DfE-style measures), Pupils, Persistent
absence, Severe absence, By code, Weekday & session, Trend by week (with a
chart), Groups, Year groups and Forms. Every tab exports to CSV; pupil
tabs open the pupil's profile or a detail window. The rules are in
:mod:`modules.reporting.domain.attendance_report`.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from education_system.systems.secondary.modules.reporting.domain import attendance_report as AR
from education_system.systems.secondary.modules.reporting.gui import report_widgets as RW
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log


class AttendanceReportPage(RW.ReportPage):
    TITLE = "Attendance Report"
    LOG = "attendance_report"
    TABS = {"Summary": "summary", "Pupils": "pupils", "Persistent absence": "persistent",
            "Severe absence": "severe", "By code": "codes", "Weekday & session": "weekdays",
            "Trend by week": "weeks", "Groups": "groups", "Year groups": "years",
            "Forms": "forms"}
    PUPIL_TABS = frozenset({"Pupils", "Persistent absence", "Severe absence"})

    def __init__(self, parent, **kw) -> None:
        activity_log.record("attendance_report.view")
        super().__init__(parent, **kw)

    def build_filters(self, parent: ttk.Frame) -> None:
        self.filters = RW.FilterBar(parent, self.state, self.run)
        ttk.Label(self.filters.bar, text="Pupil:").pack(side="left", padx=(8, 0))
        self.pupil = tk.StringVar(value=self.state.get("pupil", ""))
        ttk.Entry(self.filters.bar, textvariable=self.pupil, width=12).pack(side="left",
                                                                           padx=(2, 4))
        ttk.Label(self.filters.bar, text="(blank dates: this school year to date)",
                  foreground="#777").pack(side="left", padx=6)

    def gather(self) -> dict[str, str]:
        f = self.filters.get()
        f["pupil"] = self.state["pupil"] = self.pupil.get().strip()
        return f

    def compute(self, f: dict[str, str]) -> AR.Report:
        ref = f.get("pupil", "")
        pid = None
        if ref:
            p = P.find_by_reference(ref)
            if p is None:
                raise AR.NotFound(f"No pupil '{ref}'")
            pid = p.pupil_id
        return AR.build(self.principal, f.get("from") or None, f.get("to") or None,
                        year_group=f.get("year") or None, form=f.get("form") or None,
                        pupil_id=pid)

    def describe(self) -> str:
        r: AR.Report = self.report
        o = r.overall
        return (f"{r.scope}, {r.start} to {r.end}: attendance {RW.RC.show(o.attendance_pct)}%, "
                f"authorised {o.authorised}, unauthorised {o.unauthorised} sessions; "
                f"{len(r.persistent)} persistent, {len(r.severe)} severe absentee(s).")

    def table(self, section: str):
        return AR.table(self.report, section)

    def export(self, path: str, section: str) -> int:
        return AR.export_csv(path, self.report, section, actor=self.principal)

    def row_tags(self, name: str, row: list[Any]) -> tuple[str, ...]:
        if name in self.PUPIL_TABS:
            return {"severe": ("bad",), "persistent": ("warn",)}.get(row[-1], ())
        return ()

    def extra_buttons(self, name: str, bar: ttk.Frame) -> None:
        if name == "Trend by week":
            ttk.Button(bar, text="Chart", command=self.chart_weeks).pack(side="left", padx=2)
        if name == "Groups":
            ttk.Button(bar, text="Chart", command=self.chart_groups).pack(side="left", padx=2)

    def pupil_text(self, pupil_id: int) -> str:
        f = self.filters.get()
        d = AR.pupil_detail(self.principal, pupil_id, f.get("from") or None,
                            f.get("to") or None)
        return AR.pupil_text(d)

    def chart_weeks(self) -> None:
        if self.report is None or not self.report.by_week:
            return
        w = self.report.by_week
        RW.bar_chart(self.parent, "Attendance by week", [x["week"][5:] for x in w],
                     {"Attendance %": [x["attendance_pct"] for x in w]}, line=True,
                     ylabel="%")

    def chart_groups(self) -> None:
        if self.report is None:
            return
        g = self.report.groups
        RW.bar_chart(self.parent, "Attendance by group", [x.group for x in g],
                     {"Attendance %": [x.summary.attendance_pct for x in g]}, ylabel="%")


def draw_attendance_report(parent: ttk.Frame, *, principal: Principal, state: dict,
                           open_pupil: Callable[[int], None] | None = None
                           ) -> AttendanceReportPage:
    return AttendanceReportPage(parent, principal=principal, state=state,
                                open_pupil=open_pupil)
