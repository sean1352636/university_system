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


class _My_dataMixin:
    """Methods extracted from EqualityDiversityGUI (my_data)."""

    def _build_my_data_tab(self, root):
        """features 43–45 — student self-service."""
        t = self.theme
        Label(root, text=_t("ed.my_data", "Your monitoring record"),
              font=("Helvetica", 14, "bold"),
              bg=t["panel"], fg=t["accent"]
              ).pack(anchor="w", padx=16, pady=(14, 4))

        ref = str(self.principal.user_id or self.principal.username)
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM ed_people WHERE ref_code=?", (ref,)).fetchone()
            cols = [c[1] for c in conn.execute("PRAGMA table_info(ed_people)")]
        finally:
            conn.close()
        data = dict(zip(cols, row)) if row else {"ref_code": ref}

        form = Frame(root, bg=t["panel"], padx=16, pady=8)
        form.pack(fill="x")
        self.my_vars: dict[str, StringVar] = {}
        for i, key in enumerate(DEMOGRAPHIC_FIELDS):
            Label(form, text=key, bg=t["panel"], fg=t["text"]
                  ).grid(row=i, column=0, sticky="w", padx=4, pady=3)
            opts = FIELD_OPTIONS.get(key)
            v = StringVar(value=str(data.get(key) or (opts[0] if opts else "")))
            self.my_vars[key] = v
            if opts:
                OptionMenu(form, v, *opts).grid(row=i, column=1, sticky="ew", padx=4)
            else:
                Entry(form, textvariable=v).grid(row=i, column=1, sticky="ew", padx=4)
        form.columnconfigure(1, weight=1)

        # feature 45 — consent flags
        consent_box = Frame(root, bg=t["panel"], padx=16, pady=4)
        consent_box.pack(fill="x")
        Label(consent_box, text=_t("ed.consent", "Consent (you can withdraw anytime)"),
              font=("Helvetica", 11, "bold"),
              bg=t["panel"], fg=t["accent"]).pack(anchor="w", pady=(6, 2))
        self.consent_vars: dict[str, IntVar] = {}
        for k in ("share_for_reports", "share_cross_system", "allow_research"):
            v = IntVar(value=1)
            self.consent_vars[k] = v
            Checkbutton(consent_box, text=k.replace("_", " ").title(),
                        variable=v, bg=t["panel"], fg=t["text"],
                        selectcolor=t["panel"]).pack(anchor="w")

        Button(root, text=_t("ed.save", "Save"), command=self._save_my_data,
               bg="#27ae60", fg="white", relief="flat", padx=16, pady=6
               ).pack(anchor="w", padx=16, pady=8)

    def _save_my_data(self):
        ref = str(self.principal.user_id or self.principal.username)
        values = {k: v.get() for k, v in self.my_vars.items()}
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        conn = get_connection()
        try:
            exists = conn.execute(
                "SELECT id FROM ed_people WHERE ref_code=?", (ref,)).fetchone()
            if exists:
                pid = exists[0]
                sets = ", ".join(f"{k}=?" for k in values) + ", self_updated_at=?"
                conn.execute(
                    f"UPDATE ed_people SET {sets} WHERE id=?",
                    (*values.values(), now, pid),
                )
            else:
                cols = ",".join(values.keys()) + ",ref_code,person_type,date_added,self_updated_at"
                marks = ",".join("?" for _ in values) + ",?,?,?,?"
                conn.execute(
                    f"INSERT INTO ed_people ({cols}) VALUES ({marks})",
                    (*values.values(), ref, "Student", now, now),
                )
                pid = conn.execute(
                    "SELECT id FROM ed_people WHERE ref_code=?", (ref,)
                ).fetchone()[0]
            conn.execute(
                "INSERT INTO ed_consent (person_id, consent_flags, updated_at) "
                "VALUES (?, ?, ?) ON CONFLICT(person_id) DO UPDATE SET "
                "consent_flags=excluded.consent_flags, updated_at=excluded.updated_at",
                (pid,
                 json.dumps({k: bool(v.get()) for k, v in self.consent_vars.items()}),
                 now),
            )
            conn.commit()
        finally:
            conn.close()
        integrations.audit(self.principal.username, "self_update", "person", ref)
        messagebox.showinfo("Saved", "Your record and consent have been updated.")

    # ================================================================= Admin

