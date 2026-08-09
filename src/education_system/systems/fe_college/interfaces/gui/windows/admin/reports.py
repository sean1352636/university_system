"""Admin reports — pick a report, read it, export it.

Every report comes from :mod:`reporting_service`, so the figures here are the
same ones the dashboard and the CLI show. Columns are derived from the rows
rather than hard-coded per report, which is what lets one screen render all
seven without a branch per report.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from education_system.systems.fe_college.interfaces.gui import widgets as w

logger = logging.getLogger(__name__)

TITLE = "Reports"

# Column key -> (heading, width, anchor). Anything not listed falls back to a
# title-cased heading at a default width, so a new report field still renders.
_COLUMNS = {
    "course_id": ("Course", 90, "w"),
    "student_id": ("ID", 90, "w"),
    "staff_id": ("ID", 90, "w"),
    "title": ("Title", 250, "w"),
    "name": ("Name", 180, "w"),
    "qualification": ("Qualification", 140, "w"),
    "area": ("Curriculum area", 180, "w"),
    "band": ("Band", 150, "w"),
    "tutor_group": ("Group", 80, "w"),
    "personal_tutor": ("Personal tutor", 160, "w"),
    "viability": ("Viability", 110, "w"),
    "sessions": ("Sessions", 80, "e"),
    "starts": ("Starts", 70, "e"),
    "retained": ("Retained", 80, "e"),
    "completed": ("Completed", 85, "e"),
    "achieved": ("Achieved", 80, "e"),
    "enrolled": ("On", 55, "e"),
    "capacity": ("Capacity", 75, "e"),
    "unauthorised": ("Unauth.", 75, "e"),
    "contracted": ("Contracted", 90, "e"),
    "assigned": ("Assigned", 85, "e"),
    "variance": ("Variance", 85, "e"),
    "attendance_pct": ("Attendance", 95, "e"),
    "punctuality_pct": ("Punctuality", 95, "e"),
    "retention_pct": ("Retention", 90, "e"),
    "achievement_pct": ("Achievement", 100, "e"),
    "fill_pct": ("Filled", 80, "e"),
    "utilisation_pct": ("Utilisation", 95, "e"),
    "estimated_income": ("Est. income", 110, "e"),
    "lost_to_withdrawal": ("Lost to withdrawal", 140, "e"),
    "outstanding": ("Outstanding", 110, "e"),
    "overdue": ("Overdue", 100, "e"),
}

# Keys rendered as percentages and as money, so the table reads correctly
# without each report formatting its own values.
_PCT_KEYS = {k for k in _COLUMNS if k.endswith("_pct")}
_MONEY_KEYS = {"estimated_income", "lost_to_withdrawal", "outstanding", "overdue"}

# Reports whose rows carry a band worth colouring.
_TONE_KEYS = ("band", "viability")


def open_window(host, report: str | None = None) -> None:
    Screen(host, report)


class Screen:
    def __init__(self, host, report: str | None = None):
        self.host = host
        self.ctl = host.ctl
        self.rows: list[dict] = []
        host.clear_content()
        parent = host.content_frame

        w.page_header(
            parent, TITLE,
            "The same figures the dashboards show — exportable as CSV.",
            actions=[
                ("Export CSV", self.export),
                ("↻ Refresh", self.refresh),
            ],
        )

        self.names = list(self.ctl.reports.REPORTS)
        labels = [self.ctl.reports.REPORTS[n][0] for n in self.names]

        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, text="Report:").pack(side="left")
        self.report_var = tk.StringVar()
        combo = ttk.Combobox(bar, textvariable=self.report_var, values=labels,
                             state="readonly", width=32)
        combo.pack(side="left", padx=(4, 12))
        combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        index = self.names.index(report) if report in self.names else 0
        combo.current(index)

        self.count_var = tk.StringVar()
        ttk.Label(bar, textvariable=self.count_var,
                  foreground=w.TONE["muted"]).pack(side="left")

        self.table_holder = ttk.Frame(parent)
        self.table_holder.pack(fill="both", expand=True)
        self.refresh()

    @property
    def selected_report(self) -> str:
        label = self.report_var.get()
        for name in self.names:
            if self.ctl.reports.REPORTS[name][0] == label:
                return name
        return self.names[0]

    def refresh(self) -> None:
        name = self.selected_report
        try:
            self.rows = self.ctl.reports.run(name)
        except Exception as exc:
            logger.exception("FE College report %s failed", name)
            w.clear(self.table_holder)
            w.empty_state(self.table_holder, f"Could not run that report: {exc}")
            return

        w.clear(self.table_holder)
        if not self.rows:
            w.empty_state(self.table_holder,
                          "That report has no data yet — nothing matches.")
            self.count_var.set("")
            self.host.set_status(f"{name}: no rows")
            return

        keys = [k for k in self.rows[0] if not k.startswith("_")]
        columns = []
        for key in keys:
            heading, width, anchor = _COLUMNS.get(
                key, (key.replace("_", " ").title(), 120, "w")
            )
            columns.append((key, heading, width, anchor))

        table = w.DataTable(self.table_holder, columns, height=22)
        table.set_rows([self._format(row) for row in self.rows])
        self.count_var.set(f"{len(self.rows)} row(s)")
        self.host.set_status(
            f"{self.ctl.reports.REPORTS[name][0]}: {len(self.rows)} row(s)"
        )

    def _format(self, row: dict) -> dict:
        out: dict = {}
        for key, value in row.items():
            if key in _PCT_KEYS:
                out[key] = w.pct(value)
            elif key in _MONEY_KEYS:
                out[key] = w.money(value)
            else:
                out[key] = value if value not in (None, "") else "—"
        for key in _TONE_KEYS:
            if key in row:
                out["_tone"] = w.tone_for(str(row[key]))
                break
        return out

    def export(self) -> None:
        if not self.rows:
            w.info(self.host, "Export", "There is nothing to export.")
            return
        name = self.selected_report
        try:
            path = self.ctl.reports.export(name)
        except Exception as exc:
            logger.exception("Could not export FE College report %s", name)
            w.error(self.host, "Export", f"Could not write the export: {exc}")
            return
        w.info(self.host, "Exported",
               f"{len(self.rows)} row(s) written to:\n\n{path}")
        self.host.set_status(f"Exported {name} to {path}")


__all__ = ["TITLE", "Screen", "open_window"]
