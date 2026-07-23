"""Split from equality_diversity/gui.py — assembled in package __init__.py."""
from __future__ import annotations

import csv
import json
import os
import secrets
import shutil
import sqlite3
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import (
    Button, Checkbutton, END, Entry, Frame, IntVar, Label, OptionMenu,
    Scrollbar, StringVar, Text, Tk, Toplevel, filedialog, messagebox, ttk,
)

from education_system.post_18.university_system.modules.domain.student_affairs.equality_diversity import (
    access, integrations, reports_engine,
)
from education_system.post_18.university_system.modules.domain.student_affairs.equality_diversity.schema import (
    DEMOGRAPHIC_FIELDS, SORTABLE_RECORD_COLUMNS, get_connection, migrate,
)

from .._constants import (
    PERSON_TYPES, DEPARTMENTS, AGE_GROUPS, GENDERS, ETHNICITIES,
    DISABILITY_STATUS, RELIGIONS, SEXUAL_ORIENTATIONS,
    INCIDENT_CATEGORIES, INCIDENT_STATUS, SEVERITIES, SLA_DAYS,
    FIELD_OPTIONS, THEMES, PAGE_SIZE,
)
from .._helpers import _t, _prompt_string, _render_bar_table, _embed_chart
from .._dialogs import RecordEditor, MergeDialog, IncidentDetail, ScheduleEditor


class _ReportsMixin:
    """Methods extracted from EqualityDiversityGUI (reports)."""

    def _build_reports_tab(self, root):
        t = self.theme
        top = Frame(root, bg=t["panel"], pady=12)
        top.pack(fill="x", padx=16)
        Label(top, text=_t("ed.reports", "Reports & Analytics"),
              font=("Helvetica", 14, "bold"),
              bg=t["panel"], fg=t["accent"]).pack(anchor="w")
        Label(top, text=_t(
            "ed.reports_note",
            "Cells with n<5 are suppressed to protect privacy."),
              bg=t["panel"], fg=t["muted"],
              font=("Helvetica", 9, "italic")
              ).pack(anchor="w", pady=(2, 10))

        # row of quick-reports
        quick = Frame(top, bg=t["panel"])
        quick.pack(anchor="w")
        for lbl, f in [("Gender", "gender"), ("Ethnicity", "ethnicity"),
                       ("Age", "age_group"), ("Disability", "disability"),
                       ("Religion", "religion"), ("Department", "department")]:
            Button(quick, text=lbl,
                   command=lambda x=f: self._render_field_report(x),
                   bg=t["accent"], fg=t["header_fg"],
                   relief="flat", padx=10, pady=4).pack(side="left", padx=3)
        Button(quick, text="Incidents",
               command=self._render_incidents_report,
               bg=t["accent"], fg=t["header_fg"], relief="flat",
               padx=10, pady=4).pack(side="left", padx=3)

        # advanced buttons
        adv = Frame(top, bg=t["panel"])
        adv.pack(anchor="w", pady=(10, 0))
        Button(adv, text="Cross-tab…", command=self._open_crosstab,
               bg="#27ae60", fg="white", relief="flat", padx=10
               ).pack(side="left", padx=3)
        Button(adv, text="Trends…", command=self._open_trends,
               bg="#27ae60", fg="white", relief="flat", padx=10
               ).pack(side="left", padx=3)
        Button(adv, text="Benchmark vs baseline",
               command=self._open_benchmarks,
               bg="#27ae60", fg="white", relief="flat", padx=10
               ).pack(side="left", padx=3)
        Button(adv, text="Pay-gap", command=self._show_pay_gap,
               bg="#27ae60", fg="white", relief="flat", padx=10
               ).pack(side="left", padx=3)
        Button(adv, text="Export PDF", command=self._export_last_pdf,
               bg="#1e3a5f", fg="white", relief="flat", padx=10
               ).pack(side="left", padx=3)

        # Segment-by row — break the quick reports down by course /
        # year_of_study / programme_level. Pulls from columns
        # auto-synced by integrations.sync_from_students.
        seg = Frame(top, bg=t["panel"])
        seg.pack(anchor="w", pady=(10, 0))
        Label(seg, text="Segment by:",
              bg=t["panel"], fg=t["text"],
              font=("Helvetica", 9, "bold")
              ).pack(side="left", padx=(0, 6))
        for axis_label, axis in [("Course", "course"),
                                  ("Year", "year_of_study"),
                                  ("Level", "programme_level")]:
            Button(seg, text=axis_label,
                   command=lambda a=axis: self._open_segment_picker(a),
                   bg="#7c3aed", fg="white", relief="flat", padx=10
                   ).pack(side="left", padx=3)

        # Cross-domain intersections — joins ed_people against
        # attendance, disciplinary records, the risk feed, and grades
        # to surface "are we serving all students equally?" disparities.
        Label(top, text=_t("ed.intersections",
                           "Cross-domain intersections"),
              font=("Helvetica", 11, "bold"),
              bg=t["panel"], fg=t["text"]
              ).pack(anchor="w", pady=(14, 0))
        cross = Frame(top, bg=t["panel"])
        cross.pack(anchor="w", pady=(4, 0))
        Button(cross, text="Attendance × demographic",
               command=lambda: self._open_intersection('attendance'),
               bg="#dc2626", fg="white", relief="flat", padx=10
               ).pack(side="left", padx=3)
        Button(cross, text="Discipline × demographic",
               command=lambda: self._open_intersection('discipline'),
               bg="#dc2626", fg="white", relief="flat", padx=10
               ).pack(side="left", padx=3)
        Button(cross, text="Risk feed × demographic",
               command=lambda: self._open_intersection('risk'),
               bg="#dc2626", fg="white", relief="flat", padx=10
               ).pack(side="left", padx=3)
        Button(cross, text="Attainment gap",
               command=lambda: self._open_intersection('attainment'),
               bg="#dc2626", fg="white", relief="flat", padx=10
               ).pack(side="left", padx=3)

        self.report_frame = Frame(root, bg=t["panel"], padx=16, pady=10)
        self.report_frame.pack(fill="both", expand=True)
        self._last_report: tuple[str, list[tuple[str, int]]] | None = None
        Label(self.report_frame,
              text=_t("ed.pick_report", "Pick a report above."),
              bg=t["panel"], fg=t["muted"],
              font=("Helvetica", 11, "italic")).pack(pady=40)

    def _clear_report(self):
        for w in self.report_frame.winfo_children():
            w.destroy()

    def _render_field_report(self, field: str):
        self._clear_report()
        data = reports_engine._field_counts(field)
        self._last_report = (f"Breakdown by {field}", data)
        _render_bar_table(self.report_frame, f"Breakdown by {field}", data,
                          self.theme,
                          drill=lambda cat: self._drill_down(field, cat))
        if reports_engine.charts_available():
            _embed_chart(self.report_frame, field, self.theme)

    def _render_incidents_report(self):
        self._clear_report()
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT category, COUNT(*) FROM ed_incidents "
                "GROUP BY category ORDER BY COUNT(*) DESC"
            ).fetchall()
        finally:
            conn.close()
        self._last_report = ("Incidents by category", rows)
        _render_bar_table(self.report_frame, "Incidents by category",
                          rows, self.theme)

    # ---- university segmentation + cross-domain intersections ----

    def _open_segment_picker(self, axis: str):
        """Pick a demographic field, then render its breakdown
        segmented by the given axis (course / year / programme_level).
        Two-step so the UI doesn't need 6×4 buttons.
        """
        win = Toplevel(self.root)
        win.title(f"Segment by {axis.replace('_', ' ').title()}")
        win.configure(bg=self.theme["panel"])
        Label(win, text=f"Pick a demographic to segment by "
                        f"{axis.replace('_', ' ')}:",
              bg=self.theme["panel"],
              fg=self.theme["text"]).pack(padx=12, pady=(10, 6))
        for label, field in [("Gender", "gender"),
                             ("Ethnicity", "ethnicity"),
                             ("Age", "age_group"),
                             ("Disability", "disability"),
                             ("Religion", "religion"),
                             ("Sexual Orientation", "sexual_orientation")]:
            Button(win, text=label,
                   command=lambda f=field, a=axis:
                       (self._render_segmented_report(f, a),
                        win.destroy()),
                   bg=self.theme["accent"],
                   fg=self.theme["header_fg"],
                   relief="flat", padx=10, pady=4
                   ).pack(fill="x", padx=12, pady=2)

    def _render_segmented_report(self, field: str, segment: str):
        self._clear_report()
        try:
            triples = reports_engine.field_by_segment(field, segment)
        except ValueError as e:
            Label(self.report_frame, text=str(e),
                  bg=self.theme["panel"],
                  fg=self.theme["danger"]).pack(pady=20)
            return
        title = (f"{field.replace('_',' ').title()} by "
                 f"{segment.replace('_',' ').title()}")
        Label(self.report_frame, text=title,
              font=("Helvetica", 12, "bold"),
              bg=self.theme["panel"],
              fg=self.theme["accent"]).pack(anchor="w", pady=(0, 8))
        if not triples:
            Label(self.report_frame,
                  text="No data — sync the roster from the Admin tab "
                       "to populate course / year on records.",
                  bg=self.theme["panel"],
                  fg=self.theme["muted"]).pack(pady=20)
            return
        # Render as a treeview with three columns for clarity.
        from tkinter import ttk as _ttk
        tree = _ttk.Treeview(self.report_frame,
                             columns=("seg", "value", "n"),
                             show="headings", height=14)
        tree.heading("seg", text=segment.replace('_', ' ').title())
        tree.heading("value", text=field.replace('_', ' ').title())
        tree.heading("n", text="Count")
        tree.column("seg", width=180)
        tree.column("value", width=180)
        tree.column("n", width=80, anchor="e")
        for s, v, n in triples:
            tree.insert("", "end", values=(s, v, n))
        tree.pack(fill="both", expand=True, pady=(0, 8))
        self._last_report = (
            title, [(f"{s} / {v}", n) for s, v, n in triples])

    def _open_intersection(self, kind: str):
        """Pick the demographic field, then render the cross-domain
        join. Lets one button drive four different analyses.
        """
        win = Toplevel(self.root)
        win.title(f"Intersection — {kind}")
        win.configure(bg=self.theme["panel"])
        Label(win, text="Break down by:",
              bg=self.theme["panel"],
              fg=self.theme["text"]).pack(padx=12, pady=(10, 6))
        for label, field in [("Gender", "gender"),
                             ("Ethnicity", "ethnicity"),
                             ("Disability", "disability"),
                             ("Age group", "age_group"),
                             ("Religion", "religion")]:
            Button(win, text=label,
                   command=lambda f=field, k=kind:
                       (self._render_intersection(k, f),
                        win.destroy()),
                   bg=self.theme["accent"],
                   fg=self.theme["header_fg"],
                   relief="flat", padx=10, pady=4
                   ).pack(fill="x", padx=12, pady=2)

    def _render_intersection(self, kind: str, field: str):
        self._clear_report()
        from tkinter import ttk as _ttk
        title_map = {
            'attendance': f"Mean attendance % by {field}",
            'discipline': f"Disciplinary rate by {field}",
            'risk':       f"Risk-feed level by {field}",
            'attainment': f"Mean grade score by {field}",
        }
        title = title_map.get(kind, f"{kind} by {field}")
        Label(self.report_frame, text=title,
              font=("Helvetica", 12, "bold"),
              bg=self.theme["panel"],
              fg=self.theme["accent"]).pack(anchor="w", pady=(0, 4))
        Label(self.report_frame,
              text="Joins ed_people → central tables. Categories with "
                   "n<5 are suppressed.",
              bg=self.theme["panel"], fg=self.theme["muted"],
              font=("Helvetica", 9, "italic")
              ).pack(anchor="w", pady=(0, 10))

        if kind == 'attendance':
            data = reports_engine.attendance_by_demographic(field)
            cols = (("cat", field, 200), ("pct", "Mean %", 100),
                    ("n", "n", 80))
            rows = [(c, f"{p:.1f}%", n) for c, p, n in data]
            self._last_report = (title, [(c, int(p)) for c, p, _n in data])
        elif kind == 'discipline':
            data = reports_engine.disciplinary_overrep(field)
            cols = (("cat", field, 200),
                    ("act", "With action", 110),
                    ("tot", "Total", 80),
                    ("rate", "Rate %", 90))
            rows = [(c, a, t, f"{r:.1f}%") for c, a, t, r in data]
            self._last_report = (title, [(c, a) for c, a, _t, _r in data])
        elif kind == 'risk':
            data = reports_engine.risk_feed_distribution(field)
            cols = (("cat", field, 200),
                    ("h", "High", 70), ("m", "Medium", 80),
                    ("l", "Low", 70), ("t", "Total", 80))
            rows = data
            self._last_report = (title,
                                 [(c, h) for c, h, _m, _l, _t in data])
        elif kind == 'attainment':
            data = reports_engine.attainment_gap(field)
            cols = (("cat", field, 200),
                    ("avg", "Mean score", 110),
                    ("n", "n", 80))
            rows = [(c, f"{m:.1f}", n) for c, m, n in data]
            self._last_report = (title,
                                 [(c, int(m)) for c, m, _n in data])
        else:
            Label(self.report_frame, text=f"Unknown intersection: {kind}",
                  bg=self.theme["panel"],
                  fg=self.theme["danger"]).pack(pady=20)
            return

        if not rows:
            Label(self.report_frame,
                  text="No data — either no rows match or the "
                       "underlying tables aren't present in this DB.",
                  bg=self.theme["panel"],
                  fg=self.theme["muted"]).pack(pady=20)
            return
        tree = _ttk.Treeview(
            self.report_frame,
            columns=tuple(c[0] for c in cols),
            show="headings", height=14)
        for cid, ctext, width in cols:
            tree.heading(cid, text=ctext)
            tree.column(cid, width=width,
                        anchor=("e" if cid != "cat" else "w"))
        for r in rows:
            tree.insert("", "end", values=r)
        tree.pack(fill="both", expand=True)

    def _open_crosstab(self):
        win = Toplevel(self.root)
        win.title("Cross-tab")
        win.configure(bg=self.theme["panel"])
        row_v = StringVar(value="gender")
        col_v = StringVar(value="department")
        OptionMenu(win, row_v, *DEMOGRAPHIC_FIELDS).grid(row=0, column=0, padx=6, pady=6)
        Label(win, text="×", bg=self.theme["panel"], fg=self.theme["text"]
              ).grid(row=0, column=1)
        OptionMenu(win, col_v, *DEMOGRAPHIC_FIELDS).grid(row=0, column=2, padx=6, pady=6)
        out = Frame(win, bg=self.theme["panel"])
        out.grid(row=1, column=0, columnspan=3, padx=6, pady=6)

        def run():
            for w in out.winfo_children():
                w.destroy()
            try:
                ct = reports_engine.cross_tab(row_v.get(), col_v.get())
            except ValueError as e:
                messagebox.showerror("Cross-tab", str(e))
                return
            Label(out, text="", bg=self.theme["panel"]
                  ).grid(row=0, column=0)
            for j, c in enumerate(ct["col_keys"], 1):
                Label(out, text=c, bg=self.theme["accent"],
                      fg=self.theme["header_fg"], padx=4
                      ).grid(row=0, column=j, sticky="ew")
            for i, r in enumerate(ct["row_keys"], 1):
                Label(out, text=r, bg=self.theme["accent"],
                      fg=self.theme["header_fg"], padx=4
                      ).grid(row=i, column=0, sticky="ew")
                for j, c in enumerate(ct["col_keys"], 1):
                    v = ct["cells"].get((r, c), 0)
                    Label(out, text=str(v) if v else "·",
                          bg=self.theme["panel"], fg=self.theme["text"],
                          borderwidth=1, relief="solid", padx=6
                          ).grid(row=i, column=j, sticky="ew")

        Button(win, text="Run", command=run,
               bg=self.theme["accent"], fg=self.theme["header_fg"],
               relief="flat", padx=10).grid(row=2, column=0, columnspan=3, pady=6)

    def _open_trends(self):
        win = Toplevel(self.root)
        win.title("Yearly trends")
        win.configure(bg=self.theme["panel"])
        var = StringVar(value="gender")
        OptionMenu(win, var, *DEMOGRAPHIC_FIELDS).pack(padx=8, pady=8)
        tree = ttk.Treeview(win, columns=("Year", "Value", "Count"),
                            show="headings", height=12)
        for c in ("Year", "Value", "Count"):
            tree.heading(c, text=c)
        tree.pack(padx=8, pady=8, fill="both", expand=True)

        def run():
            for r in tree.get_children():
                tree.delete(r)
            for row in reports_engine.yearly_trend(var.get()):
                tree.insert("", END, values=row)

        Button(win, text="Show", command=run,
               bg=self.theme["accent"], fg=self.theme["header_fg"],
               relief="flat", padx=10).pack(pady=6)

    def _open_benchmarks(self):
        win = Toplevel(self.root)
        win.title("Benchmarks")
        win.configure(bg=self.theme["panel"])
        var = StringVar(value="gender")
        OptionMenu(win, var, *["gender", "ethnicity", "disability"]
                   ).pack(padx=8, pady=8)
        tree = ttk.Treeview(win, columns=("Cat", "Observed %", "Baseline %", "Δpp"),
                            show="headings", height=12)
        for c in ("Cat", "Observed %", "Baseline %", "Δpp"):
            tree.heading(c, text=c)
        tree.pack(padx=8, pady=8, fill="both", expand=True)

        def run():
            for r in tree.get_children():
                tree.delete(r)
            for cat, obs, base, delta in reports_engine.benchmark_comparison(var.get()):
                tree.insert("", END, values=(cat, f"{obs:.1f}",
                                             f"{base:.1f}", f"{delta:+.1f}"))

        Button(win, text="Compare", command=run,
               bg=self.theme["accent"], fg=self.theme["header_fg"],
               relief="flat", padx=10).pack(pady=6)

    def _show_pay_gap(self):
        win = Toplevel(self.root)
        win.title("Pay gap (staff)")
        win.configure(bg=self.theme["panel"])
        tree = ttk.Treeview(win, columns=("Group", "Mean salary", "N"),
                            show="headings", height=8)
        for c in ("Group", "Mean salary", "N"):
            tree.heading(c, text=c)
        tree.pack(padx=8, pady=8, fill="both", expand=True)
        for row in reports_engine.pay_gap("gender"):
            tree.insert("", END, values=(row[0], f"£{row[1]:,.0f}", row[2]))

    def _drill_down(self, field: str, value: str):
        rows = reports_engine.drill_down(field, value)
        win = Toplevel(self.root)
        win.title(f"Drill-down: {field}={value}")
        win.configure(bg=self.theme["panel"])
        tree = ttk.Treeview(
            win, columns=("ID", "Ref", "Type", "Dept", "Added"),
            show="headings", height=16)
        for c in ("ID", "Ref", "Type", "Dept", "Added"):
            tree.heading(c, text=c)
        for r in rows:
            tree.insert("", END, values=r)
        tree.pack(fill="both", expand=True, padx=8, pady=8)

    def _export_last_pdf(self):
        if not self._last_report:
            messagebox.showinfo("PDF", "Pick a report first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"ed_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf")
        if not path:
            return
        title, data = self._last_report
        reports_engine.export_pdf(title, data, path)
        messagebox.showinfo("PDF", f"Saved to {path}")

    # ============================================================== My Data

