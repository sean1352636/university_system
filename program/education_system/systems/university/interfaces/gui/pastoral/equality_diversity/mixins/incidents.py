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


class _IncidentsMixin:
    """Methods extracted from EqualityDiversityGUI (incidents)."""

    def _build_incidents_tab(self, root):
        t = self.theme
        left = Frame(root, bg=t["panel"], padx=16, pady=16)
        left.pack(side="left", fill="y")

        Label(left, text=_t("ed.report_incident", "Report an Incident"),
              font=("Helvetica", 13, "bold"),
              bg=t["panel"], fg=t["accent"]).pack(anchor="w", pady=(0, 10))

        Label(left, text="Category", bg=t["panel"], fg=t["text"]).pack(anchor="w")
        self.inc_category = StringVar(value=INCIDENT_CATEGORIES[0])
        OptionMenu(left, self.inc_category, *INCIDENT_CATEGORIES
                   ).pack(fill="x", pady=(0, 8))

        Label(left, text="Department", bg=t["panel"], fg=t["text"]).pack(anchor="w")
        self.inc_dept = StringVar(value=DEPARTMENTS[0])
        OptionMenu(left, self.inc_dept, *DEPARTMENTS).pack(fill="x", pady=(0, 8))

        Label(left, text="Severity (sets SLA)",
              bg=t["panel"], fg=t["text"]).pack(anchor="w")
        self.inc_sev = StringVar(value="Medium")
        OptionMenu(left, self.inc_sev, *SEVERITIES).pack(fill="x", pady=(0, 8))

        Label(left, text="Respondent (ref)", bg=t["panel"], fg=t["text"]).pack(anchor="w")
        self.inc_resp = StringVar()
        Entry(left, textvariable=self.inc_resp).pack(fill="x", pady=(0, 8))

        Label(left, text="Witnesses (comma-sep refs)",
              bg=t["panel"], fg=t["text"]).pack(anchor="w")
        self.inc_wit = StringVar()
        Entry(left, textvariable=self.inc_wit).pack(fill="x", pady=(0, 8))

        Label(left, text="Description", bg=t["panel"], fg=t["text"]).pack(anchor="w")
        self.inc_desc = Text(left, width=34, height=6, font=("Helvetica", 10))
        self.inc_desc.pack(pady=(0, 8))

        self.inc_anon = IntVar(value=0)
        Checkbutton(left, text="Report anonymously",
                    variable=self.inc_anon, bg=t["panel"], fg=t["text"],
                    selectcolor=t["panel"]).pack(anchor="w")

        Button(left, text=_t("ed.submit", "Submit report"),
               command=self._save_incident,
               bg="#c0392b", fg="white",
               font=("Helvetica", 11, "bold"), relief="flat", padx=12, pady=6
               ).pack(fill="x", pady=(8, 0))

        # right panel – list + detail
        right = Frame(root, bg=t["panel"], padx=16, pady=16)
        right.pack(side="right", fill="both", expand=True)

        Label(right, text=_t("ed.reported", "Reported Incidents"),
              font=("Helvetica", 13, "bold"),
              bg=t["panel"], fg=t["accent"]).pack(anchor="w", pady=(0, 8))

        cols = ("ID", "Date", "Category", "Dept", "Severity",
                "Status", "SLA due", "Assignee")
        self.inc_tree = ttk.Treeview(right, columns=cols, show="headings",
                                     height=14)
        for c in cols:
            self.inc_tree.heading(c, text=c)
            self.inc_tree.column(c, width=95, anchor="w")
        self.inc_tree.pack(fill="both", expand=True)
        self.inc_tree.bind("<Double-1>", self._open_incident_detail)

        br = Frame(right, bg=t["panel"])
        br.pack(fill="x", pady=8)
        Button(br, text="Refresh", command=self._load_incidents,
               bg="#6c757d", fg="white", relief="flat", padx=12
               ).pack(side="left", padx=4)
        if self.principal.can("update_incident"):
            Button(br, text="Update status",
                   command=self._update_incident_status,
                   bg=t["accent"], fg=t["header_fg"], relief="flat", padx=12
                   ).pack(side="left", padx=4)
            Button(br, text="Assign…", command=self._assign_incident,
                   bg="#27ae60", fg="white", relief="flat", padx=12
                   ).pack(side="left", padx=4)
            Button(br, text="Refer to safeguarding",
                   command=self._refer_incident,
                   bg="#c0392b", fg="white", relief="flat", padx=12
                   ).pack(side="left", padx=4)
        self._load_incidents()

    def _save_incident(self):
        desc = self.inc_desc.get("1.0", END).strip()
        if not desc:
            messagebox.showerror("Incident", "Description is required.")
            return
        sev = self.inc_sev.get()
        sla_due = (datetime.now() + timedelta(days=SLA_DAYS[sev])
                   ).strftime("%Y-%m-%d %H:%M")
        reporter = "anonymous" if self.inc_anon.get() else self.principal.username
        conn = get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO ed_incidents (date_reported, category, department, "
                "description, status, reported_by, severity, sla_deadline, "
                "respondent, witnesses, anonymous) VALUES (?, ?, ?, ?, 'Open', ?, ?, ?, ?, ?, ?)",
                (datetime.now().strftime("%Y-%m-%d %H:%M"),
                 self.inc_category.get(), self.inc_dept.get(), desc, reporter,
                 sev, sla_due, self.inc_resp.get().strip(),
                 self.inc_wit.get().strip(), int(bool(self.inc_anon.get()))),
            )
            inc_id = cur.lastrowid
            conn.commit()
        finally:
            conn.close()
        integrations.audit(reporter, "create", "incident", inc_id,
                           {"category": self.inc_category.get(), "severity": sev})
        messagebox.showinfo("Submitted", "Incident reported.")
        self.inc_desc.delete("1.0", END)
        self._load_incidents()

    def _load_incidents(self):
        for r in self.inc_tree.get_children():
            self.inc_tree.delete(r)
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT id, date_reported, category, department, severity, "
                "status, sla_deadline, assigned_to FROM ed_incidents "
                "ORDER BY id DESC"
            ).fetchall()
        finally:
            conn.close()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        for row in rows:
            tag = "overdue" if row[6] and row[6] < now and row[5] not in ("Resolved", "Closed") else ""
            self.inc_tree.insert("", END, values=row, tags=(tag,) if tag else ())
        self.inc_tree.tag_configure("overdue", background="#ffe6e6")

    def _selected_incident(self) -> int | None:
        sel = self.inc_tree.selection()
        if not sel:
            messagebox.showinfo("Incidents", "Select an incident first.")
            return None
        return int(self.inc_tree.item(sel[0])["values"][0])

    def _open_incident_detail(self, _e=None):
        iid = self._selected_incident()
        if iid is None:
            return
        access.record_view("incident", iid, self.principal.username)  # feature 42
        IncidentDetail(self, iid)

    def _update_incident_status(self):
        iid = self._selected_incident()
        if iid is None:
            return
        win = Toplevel(self.root)
        win.title("Status")
        win.configure(bg=self.theme["panel"])
        v = StringVar(value=INCIDENT_STATUS[0])
        OptionMenu(win, v, *INCIDENT_STATUS).pack(padx=14, pady=10)

        def apply():
            conn = get_connection()
            try:
                conn.execute(
                    "UPDATE ed_incidents SET status=? WHERE id=?", (v.get(), iid)
                )
                conn.commit()
            finally:
                conn.close()
            integrations.audit(self.principal.username, "status_change",
                               "incident", iid, {"status": v.get()})
            win.destroy()
            self._load_incidents()

        Button(win, text="Apply", command=apply,
               bg=self.theme["accent"], fg=self.theme["header_fg"],
               relief="flat", padx=12).pack(pady=6)

    def _assign_incident(self):
        iid = self._selected_incident()
        if iid is None:
            return
        name = _prompt_string(self.root, "Assignee username:")
        if not name:
            return
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE ed_incidents SET assigned_to=? WHERE id=?", (name, iid))
            conn.commit()
        finally:
            conn.close()
        integrations.audit(self.principal.username, "assign", "incident", iid,
                           {"assignee": name})
        self._load_incidents()

    def _refer_incident(self):
        iid = self._selected_incident()
        if iid is None:
            return
        reason = _prompt_string(self.root, "Reason for safeguarding referral:")
        if not reason:
            return
        ok = integrations.refer_to_safeguarding(iid, self.principal.username, reason)
        messagebox.showinfo("Referral",
                            "Referred." if ok else "Safeguarding module unavailable.")

    # ================================================================= Reports

