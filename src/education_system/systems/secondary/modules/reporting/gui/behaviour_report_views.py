"""Behaviour Report screen.

Filters: From / To (default this school year to date), Year and Form; Run
works the figures out in the background. Tabs: Summary (counts, points,
rates per 100 pupils, detentions, suspensions), Breakdown (by type, year,
form, subject, member of staff, weekday, hour, severity or location, with a
chart), Trend by week (chart), Pupils of concern, All pupils, Detentions and
Suspensions & exclusions. Every tab exports to CSV; pupil tabs open the
profile or the pupil's entries in the range. The rules are in
:mod:`modules.reporting.domain.behaviour_report`.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from education_system.systems.secondary.modules.reporting.domain import behaviour_report as BR
from education_system.systems.secondary.modules.reporting.gui import report_widgets as RW
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log


class BehaviourReportPage(RW.ReportPage):
    TITLE = "Behaviour Report"
    LOG = "behaviour_report"
    TABS = {"Summary": "summary", "Breakdown": "breakdown", "Trend by week": "weeks",
            "Pupils of concern": "concern", "All pupils": "pupils",
            "Detentions": "detentions", "Suspensions & exclusions": "exclusions"}
    PUPIL_TABS = frozenset({"Pupils of concern", "All pupils"})

    def __init__(self, parent, **kw) -> None:
        activity_log.record("behaviour_report.view")
        state = kw["state"]
        self.by = tk.StringVar(value=state.get("by", "type"))
        super().__init__(parent, **kw)

    def compute(self, f: dict[str, str]) -> BR.Report:
        return BR.build(self.principal, f.get("from") or None, f.get("to") or None,
                        year_group=f.get("year") or None, form=f.get("form") or None)

    def describe(self) -> str:
        t = self.report.totals()
        return (f"{self.report.scope}, {self.report.start} to {self.report.end}: "
                f"{t['positive']} positive / {t['negative']} negative entries "
                f"(net {t['net_points']} points), {t['detentions_set']} detentions, "
                f"{t['suspensions']} suspension(s), {t['permanent_exclusions']} permanent.")

    def table(self, section: str):
        return BR.table(self.report, section, self.by.get())

    def export(self, path: str, section: str) -> int:
        return BR.export_csv(path, self.report, section, actor=self.principal,
                             by=self.by.get())

    def row_tags(self, name: str, row: list[Any]) -> tuple[str, ...]:
        if name in self.PUPIL_TABS:
            if row[13] or row[11]:
                return ("bad",)
            if row[8] < 0:
                return ("warn",)
        return ()

    def extra_buttons(self, name: str, bar: ttk.Frame) -> None:
        if name == "Breakdown":
            ttk.Label(bar, text="  By:").pack(side="left")
            cb = ttk.Combobox(bar, textvariable=self.by, values=list(BR.BREAKDOWNS),
                              state="readonly", width=10)
            cb.pack(side="left", padx=4)
            cb.bind("<<ComboboxSelected>>", lambda _e: self._by_changed())
            ttk.Button(bar, text="Chart", command=self.chart_breakdown).pack(side="left",
                                                                             padx=2)
        if name == "Trend by week":
            ttk.Button(bar, text="Chart", command=self.chart_weeks).pack(side="left", padx=2)

    def _by_changed(self) -> None:
        self.state["by"] = self.by.get()
        self._fill("Breakdown")

    def pupil_text(self, pupil_id: int) -> str:
        return BR.pupil_text(self.report, pupil_id)

    def chart_breakdown(self) -> None:
        if self.report is None:
            return
        rows = self.report.breakdown(self.by.get())[:25]
        RW.bar_chart(self.parent, f"Behaviour by {BR.BREAKDOWNS[self.by.get()].lower()}",
                     [r["group"] for r in rows],
                     {"Positive": [r["positive"] for r in rows],
                      "Negative": [r["negative"] for r in rows]})

    def chart_weeks(self) -> None:
        if self.report is None:
            return
        w = self.report.weeks()
        RW.bar_chart(self.parent, "Behaviour by week", [x["week"][5:] for x in w],
                     {"Positive": [x["positive"] for x in w],
                      "Negative": [x["negative"] for x in w]}, line=True)


def draw_behaviour_report(parent: ttk.Frame, *, principal: Principal, state: dict,
                          open_pupil: Callable[[int], None] | None = None
                          ) -> BehaviourReportPage:
    return BehaviourReportPage(parent, principal=principal, state=state,
                               open_pupil=open_pupil)
