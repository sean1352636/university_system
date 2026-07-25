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

from education_system.systems.university.domain.pastoral.equality_diversity import (
    access, integrations, reports_engine,
)
from education_system.systems.university.domain.pastoral.equality_diversity.schema import (
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


class _LifecycleMixin:
    """Methods extracted from EqualityDiversityGUI (lifecycle)."""

    def __init__(self, parent, auth_manager):
        migrate()  # feature: idempotent schema ensure
        self.auth = auth_manager
        self.principal = access.principal_from_auth(auth_manager)
        if not self.principal:
            raise PermissionError("EqualityDiversityGUI requires an authenticated user")

        # Always open in a new Toplevel when a window is passed; only reuse
        # the parent when it is a Frame (i.e. the caller wants to embed).
        if isinstance(parent, (Tk, Toplevel)):
            self.root = Toplevel(parent)
            try:
                self.root.transient(parent)
            except Exception:
                pass
        else:
            self.root = parent
        self.theme_name = "light"
        self.theme = THEMES[self.theme_name]
        # Frames have no ``wm_title`` / accept no ``geometry`` — only set
        # window chrome on Tk/Toplevel hosts. Same shape as
        # Library/Student Records (8.117.34/8.117.38).
        if hasattr(self.root, "wm_title"):
            self.root.title(
                _t("ed.window_title",
                   "E&D System — {user} ({role})",
                   user=self.principal.username, role=self.principal.role or "user"))
            self.root.geometry("1200x720")
        try:
            self.root.configure(bg=self.theme["bg"])
        except Exception:
            pass

        # feature 9 — pagination state
        self.page = 0
        self.sort_col = "id"
        self.sort_desc = True
        self.filter_query: dict = {}      # feature 5
        self.search_var = StringVar()

        self._build_header()
        self._build_tabs()
        self._bind_shortcuts()            # feature 49
        self._start_idle_check()          # feature 39
        # feature 24 — catch up on any due scheduled reports
        try:
            reports_engine.run_due_schedules()
        except Exception:
            pass

    # ---------------------------------------------------------------- theme

    def _apply_theme(self, name: str):
        self.theme_name = name
        self.theme = THEMES[name]
        self.root.configure(bg=self.theme["bg"])
        # Rebuild everything — simplest and reliable
        for child in list(self.root.winfo_children()):
            child.destroy()
        self._build_header()
        self._build_tabs()
        self._bind_shortcuts()

    # --------------------------------------------------------------- header

    def _build_header(self):
        t = self.theme
        header = Frame(self.root, bg=t["accent"], height=60)
        header.pack(fill="x")
        Label(header,
              text=_t("ed.title", "University Equality & Diversity System"),
              bg=t["accent"], fg=t["header_fg"],
              font=("Helvetica", 16, "bold")).pack(side="left", padx=20, pady=15)
        Label(header,
              text=f"{self.principal.username} · {self.principal.role or 'user'}",
              bg=t["accent"], fg=t["header_fg"],
              font=("Helvetica", 10)).pack(side="right", padx=20)
        # theme picker — feature 48
        tf = Frame(header, bg=t["accent"])
        tf.pack(side="right", padx=10)
        for name in THEMES:
            Button(tf, text=name.title(),
                   command=lambda n=name: self._apply_theme(n),
                   bg=t["panel"], fg=t["text"], relief="flat", padx=6
                   ).pack(side="left", padx=2)

    # ------------------------------------------------------------------ tabs

    def _build_tabs(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

        wanted = self.principal.tabs()    # feature 37
        self.tabs: dict[str, Frame] = {}
        for name in wanted:
            f = Frame(self.notebook, bg=self.theme["panel"])
            self.notebook.add(f, text=f"  {name}  ")
            self.tabs[name] = f

        dispatch = {
            "Dashboard": self._build_dashboard_tab,   # features 30, 50, 27
            "Records": self._build_records_tab,
            "Add Record": self._build_add_tab,
            "Incidents": self._build_incidents_tab,
            "Reports": self._build_reports_tab,
            "My Data": self._build_my_data_tab,       # 43–45
            "Admin": self._build_admin_tab,           # 4, 24, 31, 40, 42, 45, 46
        }
        for name, frame in self.tabs.items():
            dispatch[name](frame)

    # ================================================================= Dashboard

    def _bind_shortcuts(self):
        """feature 49 — keyboard shortcuts."""
        self.root.bind_all("<Control-n>", lambda _e: self._select_tab("Add Record"))
        self.root.bind_all("<Control-f>", lambda _e: self._select_tab("Records"))
        self.root.bind_all("<Control-e>", lambda _e: self._export_csv())
        self.root.bind_all("<Control-r>", lambda _e: self._select_tab("Reports"))
        self.root.bind_all("<Control-i>", lambda _e: self._select_tab("Incidents"))
        self.root.bind_all("<Escape>", lambda _e: self._reset_query()
                                         if "Records" in self.tabs else None)

    def _select_tab(self, name: str):
        if name in self.tabs:
            self.notebook.select(self.tabs[name])

    # --------------------------------------------------------------- idle

    def _start_idle_check(self):
        def tick():
            # The window may have been destroyed (logout, close button,
            # parent shutdown) between scheduling and firing this tick.
            # Showing a messagebox in that state hits Tk's "grab" path
            # against a dead application and raises TclError.
            try:
                if not self.root.winfo_exists():
                    return
            except tk.TclError:
                return
            if self.principal.is_idle():
                try:
                    messagebox.showinfo("Session", "Session timed out (inactivity).", parent=self.root)
                except tk.TclError:
                    return
                try:
                    self.root.destroy()
                except Exception:
                    pass
                return
            self.root.after(30_000, tick)
        self.root.after(30_000, tick)


# ----------------------------------------------------------------------------
#  Dialogs
# ----------------------------------------------------------------------------

