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


class _Add_recordMixin:
    """Methods extracted from EqualityDiversityGUI (add_record)."""

    def _build_add_tab(self, root):
        t = self.theme
        container = Frame(root, bg=t["panel"], padx=24, pady=18)
        container.pack(fill="both", expand=True)
        Label(container, text=_t("ed.add_record", "Add monitoring record"),
              font=("Helvetica", 14, "bold"),
              bg=t["panel"], fg=t["accent"]
              ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 12))

        fields = [
            ("Reference Code *", "ref_code", None),
            ("Person Type *", "person_type", PERSON_TYPES),
            ("Department", "department", DEPARTMENTS),
            ("Age Group", "age_group", AGE_GROUPS),
            ("Gender", "gender", GENDERS),
            ("Ethnicity", "ethnicity", ETHNICITIES),
            ("Disability", "disability", DISABILITY_STATUS),
            ("Religion", "religion", RELIGIONS),
            ("Sexual Orientation", "sexual_orientation", SEXUAL_ORIENTATIONS),
            ("Nationality", "nationality", None),
            ("Salary (staff)", "salary", None),
            ("Accommodations", "accommodations", None),
        ]
        self.form_vars: dict[str, StringVar] = {}
        for i, (lbl, key, opts) in enumerate(fields):
            r = (i // 2) + 1
            c = (i % 2) * 2
            Label(container, text=lbl, bg=t["panel"], fg=t["text"]
                  ).grid(row=r, column=c, sticky="w", pady=6, padx=4)
            if opts:
                v = StringVar(value=opts[0])
                OptionMenu(container, v, *opts).grid(
                    row=r, column=c + 1, sticky="ew", pady=6, padx=4)
            else:
                v = StringVar()
                Entry(container, textvariable=v, width=25
                      ).grid(row=r, column=c + 1, sticky="ew", pady=6, padx=4)
            self.form_vars[key] = v
        container.columnconfigure(1, weight=1)
        container.columnconfigure(3, weight=1)

        btn = Frame(container, bg=t["panel"])
        btn.grid(row=10, column=0, columnspan=4, pady=16)
        Button(btn, text=_t("ed.save", "Save"), command=self._save_record,
               bg="#27ae60", fg="white", relief="flat", padx=16, pady=6
               ).pack(side="left", padx=4)
        Button(btn, text=_t("ed.clear", "Clear"),
               command=lambda: [v.set("") for v in self.form_vars.values()],
               bg="#6c757d", fg="white", relief="flat", padx=16, pady=6
               ).pack(side="left", padx=4)

    def _save_record(self):
        ref = self.form_vars["ref_code"].get().strip()
        ptype = self.form_vars["person_type"].get().strip()
        if not ref or not ptype:
            messagebox.showerror("Validation", "Reference code + person type required.")
            return
        # feature 3 duplicate detection
        conn = get_connection()
        try:
            dup = conn.execute(
                "SELECT id FROM ed_people WHERE ref_code=?", (ref,)
            ).fetchone()
        finally:
            conn.close()
        if dup:
            if not messagebox.askyesno(
                "Duplicate",
                f"Ref '{ref}' already exists (id {dup[0]}). "
                "Open merge dialog?"):
                return
            MergeDialog(self, dup[0], self.form_vars)
            return

        salary_raw = self.form_vars["salary"].get().strip()
        try:
            salary = float(salary_raw) if salary_raw else None
        except ValueError:
            salary = None

        conn = get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO ed_people (ref_code, person_type, department, "
                "age_group, gender, ethnicity, disability, religion, "
                "sexual_orientation, nationality, salary, accommodations, "
                "date_added) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (ref, ptype,
                 self.form_vars["department"].get(),
                 self.form_vars["age_group"].get(),
                 self.form_vars["gender"].get(),
                 self.form_vars["ethnicity"].get(),
                 self.form_vars["disability"].get(),
                 self.form_vars["religion"].get(),
                 self.form_vars["sexual_orientation"].get(),
                 self.form_vars["nationality"].get(),
                 salary,
                 self.form_vars["accommodations"].get(),
                 datetime.now().strftime("%Y-%m-%d %H:%M")),
            )
            new_id = cur.lastrowid
            conn.commit()
        finally:
            conn.close()
        integrations.audit(self.principal.username, "create", "person", new_id,
                           {"ref_code": ref})
        hit = integrations.sync_link(new_id, ref)   # feature 10/29
        messagebox.showinfo(
            "Saved",
            "Record created." + (f"\nLinked to {hit['kind']} {hit.get('name','')}."
                                  if hit else ""))
        for v in self.form_vars.values():
            v.set("")
        if "Records" in self.tabs:
            self._load_records()

    # ================================================================= Incidents

