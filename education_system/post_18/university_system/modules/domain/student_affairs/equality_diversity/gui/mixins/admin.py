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


class _AdminMixin:
    """Methods extracted from EqualityDiversityGUI (admin)."""

    def _build_admin_tab(self, root):
        t = self.theme
        nb = ttk.Notebook(root)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        # Roster sync — auto-populate ed_people from the central
        # students/staff tables instead of re-entering demographics.
        # Lives at the front of the Admin notebook because it's the
        # action admins want first when bootstrapping the module.
        sync_tab = Frame(nb, bg=t["panel"])
        nb.add(sync_tab, text="Roster sync")
        self._build_roster_sync(sync_tab)

        # 31 — audit log viewer
        audit_tab = Frame(nb, bg=t["panel"])
        nb.add(audit_tab, text="Audit log")
        self._build_audit_viewer(audit_tab)

        # 4 + 40 — pending deletions
        del_tab = Frame(nb, bg=t["panel"])
        nb.add(del_tab, text="Pending deletions")
        self._build_deletions(del_tab)

        # 24 — scheduled reports
        sched_tab = Frame(nb, bg=t["panel"])
        nb.add(sched_tab, text="Schedules")
        self._build_schedules(sched_tab)

        # 45 — consent overview
        consent_tab = Frame(nb, bg=t["panel"])
        nb.add(consent_tab, text="Consent")
        self._build_consent_admin(consent_tab)

        # 46 — anonymous tokens
        token_tab = Frame(nb, bg=t["panel"])
        nb.add(token_tab, text="Anon tokens")
        self._build_tokens(token_tab)

        # 42 — view-log explorer
        views_tab = Frame(nb, bg=t["panel"])
        nb.add(views_tab, text="View log")
        self._build_view_log(views_tab)

        # 32/33 — GDPR
        gdpr_tab = Frame(nb, bg=t["panel"])
        nb.add(gdpr_tab, text="GDPR")
        self._build_gdpr(gdpr_tab)

    def _build_roster_sync(self, root):
        """Pull demographics + course/year from the central students
        and staff tables into ed_people. Idempotent: existing rows
        are updated in place; analyst-entered demographic values are
        preserved (we only fill blanks)."""
        t = self.theme
        Label(root, text=_t("ed.roster_sync.title",
                             "Roster sync"),
              font=("Helvetica", 13, "bold"),
              bg=t["panel"], fg=t["accent"]
              ).pack(anchor="w", padx=12, pady=(12, 4))
        Label(root,
              text=_t("ed.roster_sync.desc",
                      "Auto-populates ed_people from the central "
                      "students and staff tables. Pulls gender, age "
                      "(from DOB), course, and year_of_study where "
                      "available, then back-links student_id / "
                      "staff_id. Re-running won't overwrite "
                      "demographic values an analyst has already set "
                      "manually — it only fills blanks."),
              wraplength=720, justify="left",
              bg=t["panel"], fg=t["muted"],
              font=("Helvetica", 10)).pack(anchor="w", padx=12,
                                            pady=(0, 12))

        if not self.principal.is_admin:
            Label(root,
                  text="(admin only)",
                  bg=t["panel"], fg=t["danger"],
                  font=("Helvetica", 10, "italic")
                  ).pack(anchor="w", padx=12)
            return

        button_row = Frame(root, bg=t["panel"])
        button_row.pack(anchor="w", padx=12, pady=(0, 12))

        result_box = Frame(root, bg=t["panel"], padx=12)
        result_box.pack(fill="x", padx=12, pady=(0, 12))

        def _show(result, label):
            for w in result_box.winfo_children():
                w.destroy()
            Label(result_box, text=f"Last sync — {label}",
                  font=("Helvetica", 11, "bold"),
                  bg=t["panel"], fg=t["accent"]
                  ).pack(anchor="w", pady=(6, 4))
            for k, v in result.items():
                Label(result_box, text=f"  {k}: {v}",
                      bg=t["panel"], fg=t["text"]
                      ).pack(anchor="w")

        def _run_students():
            try:
                from education_system.post_18.university_system.modules.domain.student_affairs.equality_diversity import (  # noqa: E501
                    integrations,
                )
                r = integrations.sync_from_students()
                _show(r, "students")
            except Exception as e:
                messagebox.showerror("Roster sync",
                                      f"Sync failed:\n{e}")

        def _run_staff():
            try:
                from education_system.post_18.university_system.modules.domain.student_affairs.equality_diversity import (  # noqa: E501
                    integrations,
                )
                r = integrations.sync_from_staff()
                _show(r, "staff")
            except Exception as e:
                messagebox.showerror("Roster sync",
                                      f"Sync failed:\n{e}")

        def _run_all():
            try:
                from education_system.post_18.university_system.modules.domain.student_affairs.equality_diversity import (  # noqa: E501
                    integrations,
                )
                r = integrations.sync_all_rosters()
                _show({"created": r["total_created"],
                       "updated": r["total_updated"],
                       "students": r["students"],
                       "staff": r["staff"]}, "all rosters")
            except Exception as e:
                messagebox.showerror("Roster sync",
                                      f"Sync failed:\n{e}")

        Button(button_row, text="Sync from students",
               command=_run_students,
               bg=t["accent"], fg=t["header_fg"],
               relief="flat", padx=12, pady=6
               ).pack(side="left", padx=4)
        Button(button_row, text="Sync from staff",
               command=_run_staff,
               bg=t["accent"], fg=t["header_fg"],
               relief="flat", padx=12, pady=6
               ).pack(side="left", padx=4)
        Button(button_row, text="Sync all rosters",
               command=_run_all,
               bg="#16a34a", fg="white",
               relief="flat", padx=12, pady=6
               ).pack(side="left", padx=4)

    def _build_audit_viewer(self, root):
        tree = ttk.Treeview(
            root, columns=("ts", "actor", "action", "entity", "id", "details"),
            show="headings", height=20)
        for c in ("ts", "actor", "action", "entity", "id", "details"):
            tree.heading(c, text=c)
            tree.column(c, width=130 if c == "details" else 95, anchor="w")
        tree.pack(fill="both", expand=True, padx=8, pady=8)

        def refresh():
            for r in tree.get_children():
                tree.delete(r)
            conn = get_connection()
            try:
                rows = conn.execute(
                    "SELECT ts, actor, action, entity, entity_id, details "
                    "FROM ed_audit_log ORDER BY id DESC LIMIT 500"
                ).fetchall()
            finally:
                conn.close()
            for r in rows:
                tree.insert("", END, values=r)
        Button(root, text="Refresh", command=refresh,
               bg=self.theme["accent"], fg=self.theme["header_fg"],
               relief="flat", padx=10).pack(pady=4)
        refresh()

    def _build_deletions(self, root):
        tree = ttk.Treeview(
            root, columns=("id", "entity", "entity_id", "requested_by", "requested_at"),
            show="headings")
        for c in ("id", "entity", "entity_id", "requested_by", "requested_at"):
            tree.heading(c, text=c)
        tree.pack(fill="both", expand=True, padx=8, pady=8)

        def refresh():
            for r in tree.get_children():
                tree.delete(r)
            for r in access.list_pending_deletions():
                tree.insert("", END, values=r)
        refresh()

        def approve():
            sel = tree.selection()
            if not sel:
                return
            qid = int(tree.item(sel[0])["values"][0])
            result = access.approve_deletion(qid, self.principal.username)
            if not result:
                messagebox.showinfo(
                    "Approve",
                    "Cannot approve (already approved or self-approval).")
                return
            entity, entity_id, _snap = result
            if entity == "person":
                conn = get_connection()
                try:
                    conn.execute(
                        "UPDATE ed_deletions SET status='hard_deleted', "
                        "hard_deleted_at=? WHERE id=?",
                        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), qid))
                    conn.execute("DELETE FROM ed_people WHERE id=?", (entity_id,))
                    conn.commit()
                finally:
                    conn.close()
            integrations.audit(self.principal.username, "hard_delete", entity,
                               entity_id, {"queue_id": qid})
            refresh()

        def restore():
            sel = tree.selection()
            if not sel:
                return
            qid = int(tree.item(sel[0])["values"][0])
            conn = get_connection()
            try:
                row = conn.execute(
                    "SELECT entity, entity_id FROM ed_deletions WHERE id=?",
                    (qid,)).fetchone()
                if row and row[0] == "person":
                    conn.execute(
                        "UPDATE ed_people SET deleted_at=NULL, deleted_by=NULL "
                        "WHERE id=?", (row[1],))
                conn.execute(
                    "UPDATE ed_deletions SET status='restored' WHERE id=?", (qid,))
                conn.commit()
            finally:
                conn.close()
            integrations.audit(self.principal.username, "restore", "person",
                               row[1] if row else None)
            refresh()

        bf = Frame(root, bg=self.theme["panel"])
        bf.pack(pady=4)
        Button(bf, text="Approve & hard-delete", command=approve,
               bg="#c0392b", fg="white", relief="flat",
               padx=10).pack(side="left", padx=4)
        Button(bf, text="Restore", command=restore,
               bg="#27ae60", fg="white", relief="flat",
               padx=10).pack(side="left", padx=4)
        Button(bf, text="Refresh", command=refresh,
               bg="#6c757d", fg="white", relief="flat",
               padx=10).pack(side="left", padx=4)

    def _build_schedules(self, root):
        tree = ttk.Treeview(
            root, columns=("id", "name", "cadence", "field", "fmt", "next_run"),
            show="headings")
        for c in ("id", "name", "cadence", "field", "fmt", "next_run"):
            tree.heading(c, text=c)
        tree.pack(fill="both", expand=True, padx=8, pady=8)

        def refresh():
            for r in tree.get_children():
                tree.delete(r)
            for s in reports_engine.list_schedules():
                tree.insert("", END, values=(s.id, s.name, s.cadence, s.field,
                                              s.fmt, s.next_run_at))
        refresh()

        def new():
            ScheduleEditor(self, on_save=refresh)

        def run_now():
            paths = reports_engine.run_due_schedules()
            messagebox.showinfo("Schedules",
                                f"Ran {len(paths)} schedule(s).")
            refresh()

        bf = Frame(root, bg=self.theme["panel"])
        bf.pack(pady=4)
        Button(bf, text="New…", command=new,
               bg="#27ae60", fg="white", relief="flat",
               padx=10).pack(side="left", padx=4)
        Button(bf, text="Run due now", command=run_now,
               bg=self.theme["accent"], fg=self.theme["header_fg"],
               relief="flat", padx=10).pack(side="left", padx=4)
        Button(bf, text="Refresh", command=refresh,
               bg="#6c757d", fg="white", relief="flat",
               padx=10).pack(side="left", padx=4)

    def _build_consent_admin(self, root):
        tree = ttk.Treeview(
            root, columns=("person_id", "flags", "updated_at"),
            show="headings")
        for c in ("person_id", "flags", "updated_at"):
            tree.heading(c, text=c)
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT person_id, consent_flags, updated_at FROM ed_consent "
                "ORDER BY updated_at DESC").fetchall()
        finally:
            conn.close()
        for r in rows:
            tree.insert("", END, values=r)

    def _build_tokens(self, root):
        tree = ttk.Treeview(
            root, columns=("token", "issued_by", "issued_at", "used_at"),
            show="headings")
        for c in ("token", "issued_by", "issued_at", "used_at"):
            tree.heading(c, text=c)
            tree.column(c, width=160 if c == "token" else 120)
        tree.pack(fill="both", expand=True, padx=8, pady=8)

        def refresh():
            for r in tree.get_children():
                tree.delete(r)
            conn = get_connection()
            try:
                rows = conn.execute(
                    "SELECT token, issued_by, issued_at, used_at "
                    "FROM ed_anonymous_tokens ORDER BY issued_at DESC").fetchall()
            finally:
                conn.close()
            for r in rows:
                tree.insert("", END, values=r)
        refresh()

        def issue():
            n = _prompt_string(self.root, "How many tokens to issue?")
            try:
                n = max(1, int(n or 1))
            except ValueError:
                n = 1
            tokens = []
            conn = get_connection()
            try:
                for _ in range(n):
                    tok = secrets.token_urlsafe(12)
                    tokens.append(tok)
                    conn.execute(
                        "INSERT INTO ed_anonymous_tokens (token, issued_by, issued_at) "
                        "VALUES (?, ?, ?)",
                        (tok, self.principal.username,
                         datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
            finally:
                conn.close()
            messagebox.showinfo("Tokens issued", "\n".join(tokens))
            refresh()

        Button(root, text="Issue…", command=issue,
               bg="#27ae60", fg="white", relief="flat",
               padx=10).pack(pady=4)

    def _build_view_log(self, root):
        tree = ttk.Treeview(
            root, columns=("entity", "entity_id", "viewer", "viewed_at"),
            show="headings")
        for c in ("entity", "entity_id", "viewer", "viewed_at"):
            tree.heading(c, text=c)
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT entity, entity_id, viewer, viewed_at "
                "FROM ed_view_log ORDER BY id DESC LIMIT 500").fetchall()
        finally:
            conn.close()
        for r in rows:
            tree.insert("", END, values=r)

    def _build_gdpr(self, root):
        Label(root, text="Subject-Access Request / Right-to-Erasure",
              bg=self.theme["panel"], fg=self.theme["accent"],
              font=("Helvetica", 12, "bold")).pack(anchor="w", padx=12, pady=8)
        ref_var = StringVar()
        entry_frame = Frame(root, bg=self.theme["panel"])
        entry_frame.pack(fill="x", padx=12)
        Label(entry_frame, text="ref_code:",
              bg=self.theme["panel"], fg=self.theme["text"]
              ).pack(side="left")
        Entry(entry_frame, textvariable=ref_var, width=30).pack(side="left", padx=6)

        def sar():
            data = integrations.sar_export(ref_var.get().strip())
            path = filedialog.asksaveasfilename(
                defaultextension=".json",
                initialfile=f"sar_{ref_var.get()}.json")
            if not path:
                return
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, default=str, indent=2)
            messagebox.showinfo("SAR", f"Saved to {path}")

        def erase():
            ref = ref_var.get().strip()
            if not ref or not messagebox.askyesno(
                    "Erase", f"Permanently erase all data for '{ref}'?"):
                return
            n = integrations.erase_person(ref, self.principal.username)
            messagebox.showinfo("Erase", f"Rows removed/updated: {n}")

        bf = Frame(root, bg=self.theme["panel"])
        bf.pack(pady=8)
        Button(bf, text="Export SAR", command=sar,
               bg=self.theme["accent"], fg=self.theme["header_fg"],
               relief="flat", padx=10).pack(side="left", padx=4)
        Button(bf, text="Right-to-erasure", command=erase,
               bg="#c0392b", fg="white", relief="flat",
               padx=10).pack(side="left", padx=4)

    # --------------------------------------------------------------- shortcuts

