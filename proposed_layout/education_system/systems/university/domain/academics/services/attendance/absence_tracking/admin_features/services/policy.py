"""PolicyService — features #14–#18.

Sliced verbatim from the original admin_features.py during the package split.
"""
from __future__ import annotations

import csv
import json
import sqlite3
import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Optional

from ..context import AdminContext, audit, logger, safe
from ..export_email import (
    _email_admin,
    _export_rows_to_csv,
    _report_window,
    _rows_to_pdf,
    _rows_to_txt,
)
from ..support_tables import _get_setting, _set_setting
from ..ui_dialogs import (
    ModulePicker,
    Prompt,
    StudentPicker,
    _combo_dialog,
    _pick_module,
    _pick_student,
    _show_table,
    pick_date,
    pick_date_range,
)


class PolicyService:
    """Per-module / default policy, status vocab, auto-excuse, grace."""

    def __init__(self, ctx: AdminContext, module_picker: ModulePicker
                 ) -> None:
        self.ctx = ctx
        self.module_picker = module_picker

    # --- #14 ----------------------------------------------------------
    @safe("Module policy")
    def edit_module_policy(self) -> None:
        mc = self.module_picker.pick("Policy for which module?")
        if not mc:
            return
        try:
            row = self.ctx.db.cur.execute(
                """SELECT min_percent, late_as_absent, grace_minutes, notes
                   FROM abs_tracker_module_policy WHERE module_code=?""",
                (mc,)).fetchone()
        except sqlite3.Error:
            logger.exception("policy fetch failed mc=%s", mc)
            row = None
        cur_pct, cur_lta, cur_grace, cur_notes = row or (80.0, 0, 5, "")
        pct = simpledialog.askfloat(
            "Min %", f"Minimum attendance % (current {cur_pct})",
            parent=self.ctx.parent, minvalue=0, maxvalue=100)
        lta = simpledialog.askinteger(
            "Late=Absent",
            f"1 to count late as absent (current {cur_lta}):",
            parent=self.ctx.parent, minvalue=0, maxvalue=1)
        grace = simpledialog.askinteger(
            "Grace",
            f"Grace minutes before 'late' (current {cur_grace}):",
            parent=self.ctx.parent, minvalue=0, maxvalue=120)
        notes = simpledialog.askstring("Notes", "Notes:",
                                       parent=self.ctx.parent) or cur_notes
        try:
            self.ctx.db.cur.execute(
                """INSERT OR REPLACE INTO abs_tracker_module_policy
                   (module_code, min_percent, late_as_absent,
                    grace_minutes, notes)
                   VALUES (?, ?, ?, ?, ?)""",
                (mc, pct if pct is not None else cur_pct,
                 lta if lta is not None else cur_lta,
                 grace if grace is not None else cur_grace, notes))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("policy save failed mc=%s", mc)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "module_policy", "abs_tracker_module_policy", mc,
              f"pct={pct} lta={lta} grace={grace}")
        messagebox.showinfo("Saved", f"Policy for {mc} saved.",
                            parent=self.ctx.parent)

    # --- #15 ----------------------------------------------------------
    @safe("Default policy")
    def set_default_min_percent(self) -> None:
        current = _get_setting(self.ctx.db, "default_min_pct", "80")
        pct = simpledialog.askfloat(
            "Default min %",
            f"Default attendance min % (now {current}):",
            parent=self.ctx.parent, minvalue=0, maxvalue=100)
        if pct is None:
            return
        try:
            _set_setting(self.ctx.db, "default_min_pct", pct)
        except sqlite3.Error as e:
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "default_policy", "settings",
              "default_min_pct", str(pct))
        messagebox.showinfo("Saved", f"Default min % = {pct}",
                            parent=self.ctx.parent)

    # --- #16 ----------------------------------------------------------
    @safe("Status vocabulary")
    def manage_status_vocabulary(self) -> None:
        win = tk.Toplevel(self.ctx.parent)
        win.title("Status vocabulary")
        win.geometry("560x420")
        tree = ttk.Treeview(win, columns=("code", "label", "counts_as"),
                            show="headings")
        for c, w in zip(("code", "label", "counts_as"), (120, 200, 140)):
            tree.heading(c, text=c)
            tree.column(c, width=w)
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        def refresh():
            try:
                tree.delete(*tree.get_children())
                for row in self.ctx.db.cur.execute(
                        """SELECT code, label, counts_as
                           FROM abs_tracker_statuses ORDER BY code"""):
                    tree.insert("", "end", values=row)
            except sqlite3.Error:
                logger.exception("status refresh failed")

        def add():
            code = Prompt.non_empty(win, "Code", "Status code:", min_len=1)
            if not code:
                return
            label = simpledialog.askstring("Label", "Display label:",
                                           parent=win) or code
            counts = _combo_dialog(
                win, "Counts as", "Counts as:",
                ["present", "absent", "late", "excused"]) or "absent"
            try:
                self.ctx.db.cur.execute(
                    """INSERT OR REPLACE INTO abs_tracker_statuses
                       (code, label, counts_as) VALUES (?,?,?)""",
                    (code, label, counts))
                self.ctx.db.conn.commit()
            except sqlite3.Error as e:
                self.ctx.db.conn.rollback()
                logger.exception("status insert failed")
                messagebox.showerror("Failed", str(e), parent=win)
                return
            audit(self.ctx, "status_add", "abs_tracker_statuses",
                  code, label)
            refresh()

        tk.Button(win, text="➕ Add", command=add, bg="#16a34a",
                  fg="white", relief="flat").pack(pady=6)
        refresh()

    # --- #17 ----------------------------------------------------------
    @safe("Auto-excuse rules")
    def add_auto_excuse_rule(self) -> None:
        ev_type = Prompt.non_empty(
            self.ctx.parent, "Event type",
            "Academic-calendar event_type to auto-excuse "
            "(e.g. 'holiday','exam'):",
            min_len=2)
        if not ev_type:
            return
        try:
            self.ctx.db.cur.execute(
                "INSERT INTO abs_tracker_auto_excuse_rules (event_type) "
                "VALUES (?)", (ev_type,))
            events = self.ctx.db.cur.execute(
                """SELECT date FROM academic_calendar_events
                   WHERE event_type=?""", (ev_type,)).fetchall()
            updated = 0
            for (d,) in events:
                cur = self.ctx.db.cur.execute(
                    """UPDATE attendance
                       SET status='excused',
                           reason='auto: '||?
                       WHERE date=? AND status='absent'""",
                    (ev_type, d))
                updated += cur.rowcount
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("auto-excuse failed ev=%s", ev_type)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "auto_excuse", "attendance", ev_type,
              f"updated={updated}")
        messagebox.showinfo(
            "Applied",
            f"Auto-excused {updated} absence(s) for '{ev_type}'.",
            parent=self.ctx.parent)

    # --- #18 ----------------------------------------------------------
    @safe("Grace period")
    def set_global_grace_minutes(self) -> None:
        current = _get_setting(self.ctx.db, "global_grace", "0")
        mins = simpledialog.askinteger(
            "Grace minutes",
            f"Global grace (current {current}):",
            parent=self.ctx.parent, minvalue=0, maxvalue=120)
        if mins is None:
            return
        try:
            _set_setting(self.ctx.db, "global_grace", mins)
        except sqlite3.Error as e:
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "grace_period", "settings",
              "global_grace", str(mins))
        messagebox.showinfo("Saved", f"Global grace = {mins} min",
                            parent=self.ctx.parent)


# ===========================================================================
# ReportingService — features #19–#26
# ===========================================================================
