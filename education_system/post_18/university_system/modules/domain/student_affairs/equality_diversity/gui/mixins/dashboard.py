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


class _DashboardMixin:
    """Methods extracted from EqualityDiversityGUI (dashboard)."""

    def _build_dashboard_tab(self, root):
        """features 30, 50, 27 — summary dashboard."""
        t = self.theme
        Label(root, text=_t("ed.dashboard", "Dashboard"),
              font=("Helvetica", 14, "bold"),
              bg=t["panel"], fg=t["accent"]).pack(anchor="w", padx=16, pady=(14, 4))

        dq = reports_engine.data_quality()
        comp = integrations.monitoring_completeness()
        acc = reports_engine.accommodations_uptake()

        stats = Frame(root, bg=t["panel"])
        stats.pack(fill="x", padx=16, pady=8)

        def tile(parent, title, value):
            f = Frame(parent, bg=t["accent"], padx=12, pady=10)
            f.pack(side="left", padx=6)
            Label(f, text=value, fg=t["header_fg"], bg=t["accent"],
                  font=("Helvetica", 18, "bold")).pack()
            Label(f, text=title, fg=t["header_fg"], bg=t["accent"],
                  font=("Helvetica", 9)).pack()

        tile(stats, _t("ed.total_records", "Total Records"), dq["total_records"])
        tile(stats, _t("ed.linked_identities", "Linked Identities"), dq["linked"])
        tile(stats, _t("ed.open_incidents", "Open Incidents"), dq["incidents_open"])
        tile(stats, _t("ed.coverage", "Coverage %"),
             f"{comp['coverage_pct']:.1f}%")
        tile(stats, _t("ed.accoms", "Accoms uptake %"), f"{acc['pct']:.0f}%")

        # feature 50 — per-field missingness
        Label(root, text=_t("ed.dq", "Data-quality — missing fields"),
              font=("Helvetica", 12, "bold"),
              bg=t["panel"], fg=t["accent"]).pack(anchor="w", padx=16, pady=(12, 4))
        grid = Frame(root, bg=t["panel"])
        grid.pack(fill="x", padx=16)
        Label(grid, text="Field", width=22, anchor="w",
              bg=t["panel"], fg=t["text"]).grid(row=0, column=0)
        Label(grid, text="Missing", bg=t["panel"], fg=t["text"]).grid(row=0, column=1)
        Label(grid, text="% missing", bg=t["panel"], fg=t["text"]).grid(row=0, column=2)
        for i, (f, (missing, tot)) in enumerate(dq["per_field_missing"].items(), 1):
            pct = (missing / tot * 100) if tot else 0.0
            for c, v in enumerate([f, f"{missing}", f"{pct:.1f}%"]):
                Label(grid, text=v, bg=t["panel"], fg=t["text"],
                      width=22 if c == 0 else 10, anchor="w"
                      ).grid(row=i, column=c, sticky="w")

    # ================================================================= Records

