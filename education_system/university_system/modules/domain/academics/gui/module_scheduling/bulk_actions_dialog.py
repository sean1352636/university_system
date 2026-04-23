"""Bulk-actions dialog for the schedules tab.

Operates on the rows the user has multi-selected in the schedules tree.
Three actions share one dialog:

  - Reassign instructor : every selected row gets the chosen instructor.
  - Cancel              : every selected row is deleted (force=True).
  - Shift time by ±N    : every selected row's start_time / end_time moves
                          by N minutes (positive = later, negative = earlier).

Each action runs through the service layer so schedule_history captures the
change and the same validation/notifications fire.
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.shared.constants import paths

DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH
logger = logging.getLogger(__name__)


def _shift_time(hhmm: str, minutes: int) -> str | None:
    """Add `minutes` (may be negative) to an 'HH:MM' string. None on bad input."""
    try:
        base = datetime.strptime(hhmm, "%H:%M")
    except (TypeError, ValueError):
        return None
    shifted = base + timedelta(minutes=minutes)
    # Don't roll over midnight — that would silently move sessions to the
    # wrong day. Reject instead.
    if shifted.date() != base.date():
        return None
    return shifted.strftime("%H:%M")


class BulkActionsDialog:
    """Pick an action + parameters, then apply it to every selected row."""

    def __init__(self, parent, scheduler, gui, schedule_ids: list[int]):
        if not schedule_ids:
            raise ValueError("BulkActionsDialog needs at least one schedule_id")

        self.parent = parent
        self.scheduler = scheduler
        self.gui = gui
        self.schedule_ids = list(schedule_ids)

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Bulk Actions — {len(schedule_ids)} selected")
        self.dialog.geometry("520x340")
        self.dialog.transient(parent)
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass

        self._build_ui()

    def _build_ui(self):
        f = ttk.Frame(self.dialog, padding=15)
        f.pack(fill=tk.BOTH, expand=True)

        ttk.Label(f, text=f"{len(self.schedule_ids)} schedule(s) selected.",
                  font=("Arial", 11, "bold")).pack(anchor=tk.W)

        # Action picker
        action_frame = ttk.LabelFrame(f, text="Action", padding=10)
        action_frame.pack(fill=tk.X, pady=(10, 8))
        self.action_var = tk.StringVar(value="reassign_instructor")
        ttk.Radiobutton(action_frame, text="Reassign instructor",
                        variable=self.action_var, value="reassign_instructor",
                        command=self._render_params).pack(anchor=tk.W)
        ttk.Radiobutton(action_frame, text="Cancel (delete)",
                        variable=self.action_var, value="cancel",
                        command=self._render_params).pack(anchor=tk.W)
        ttk.Radiobutton(action_frame, text="Shift time by N minutes",
                        variable=self.action_var, value="shift",
                        command=self._render_params).pack(anchor=tk.W)

        # Param area, swapped per action
        self.param_frame = ttk.LabelFrame(f, text="Parameters", padding=10)
        self.param_frame.pack(fill=tk.X)
        self._render_params()

        # Buttons
        btn = ttk.Frame(f)
        btn.pack(fill=tk.X, pady=(15, 0))
        ttk.Button(btn, text="Apply",
                   command=self._apply).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn, text="Cancel",
                   command=self.dialog.destroy).pack(side=tk.RIGHT)

    def _render_params(self):
        for w in self.param_frame.winfo_children():
            w.destroy()
        action = self.action_var.get()
        if action == "reassign_instructor":
            ttk.Label(self.param_frame, text="New instructor:"
                      ).grid(row=0, column=0, sticky=tk.W)
            self.instructor_var = tk.StringVar()
            self.instructor_combo = ttk.Combobox(
                self.param_frame, textvariable=self.instructor_var,
                width=40, state="readonly")
            self.instructor_combo.grid(row=0, column=1, padx=8, sticky=tk.W)
            self._load_instructors()
        elif action == "cancel":
            ttk.Label(
                self.param_frame,
                text="All selected schedules will be deleted. "
                     "Schedule history retains a snapshot, but the rows "
                     "themselves cannot be recovered from the UI.",
                wraplength=440, justify=tk.LEFT, foreground="#a00",
            ).grid(row=0, column=0, sticky=tk.W)
        elif action == "shift":
            ttk.Label(self.param_frame, text="Shift by (minutes, ±):"
                      ).grid(row=0, column=0, sticky=tk.W)
            self.shift_var = tk.StringVar(value="15")
            ttk.Entry(self.param_frame, textvariable=self.shift_var,
                      width=8).grid(row=0, column=1, padx=8, sticky=tk.W)
            ttk.Label(
                self.param_frame,
                text="Negative = earlier. Rows that would roll past midnight "
                     "are skipped.",
                wraplength=440, justify=tk.LEFT, foreground="#666",
            ).grid(row=1, column=0, columnspan=2, pady=(8, 0), sticky=tk.W)

    def _load_instructors(self):
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH), timeout=15.0) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, first_name, last_name FROM instructors "
                    "WHERE CASE WHEN status='Active' THEN 1 ELSE COALESCE(is_active, 1) END = 1 "
                    "ORDER BY last_name, first_name"
                )
                rows = cur.fetchall()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load instructors: {e}",
                                 parent=self.dialog)
            return
        self.instructor_combo["values"] = [
            f"{r[0]} - {r[1]} {r[2]}" for r in rows
        ]

    def _changed_by(self):
        try:
            if self.gui and hasattr(self.gui, "_resolve_changed_by"):
                return self.gui._resolve_changed_by()
        except Exception:
            pass
        return "gui"

    def _apply(self):
        action = self.action_var.get()
        if action == "reassign_instructor":
            self._do_reassign()
        elif action == "cancel":
            self._do_cancel()
        elif action == "shift":
            self._do_shift()

    def _do_reassign(self):
        sel = (self.instructor_var.get() or "").strip()
        if not sel:
            messagebox.showerror("Error", "Pick an instructor.",
                                 parent=self.dialog)
            return
        try:
            new_instructor_id = int(sel.split(" - ")[0])
        except (ValueError, IndexError):
            messagebox.showerror("Error", "Could not parse instructor.",
                                 parent=self.dialog)
            return
        if not messagebox.askyesno(
                "Confirm",
                f"Reassign {len(self.schedule_ids)} schedule(s) to "
                f"{sel.split(' - ', 1)[1]}?",
                parent=self.dialog):
            return

        changed_by = self._changed_by()
        ok, fail = 0, []
        for sid in self.schedule_ids:
            try:
                if self.scheduler.update_module_schedule(
                        sid, instructor_id=new_instructor_id,
                        changed_by=changed_by):
                    ok += 1
                else:
                    fail.append(sid)
            except Exception as e:
                fail.append(f"{sid} ({e})")
        self._finish(ok, fail, "reassigned")

    def _do_cancel(self):
        if not messagebox.askyesno(
                "Confirm",
                f"Delete {len(self.schedule_ids)} schedule(s)? "
                "This cannot be undone from the UI.",
                parent=self.dialog,
                icon="warning"):
            return

        changed_by = self._changed_by()
        ok, fail = 0, []
        for sid in self.schedule_ids:
            try:
                if self.scheduler.delete_module_schedule(
                        sid, force=True, changed_by=changed_by):
                    ok += 1
                else:
                    fail.append(sid)
            except Exception as e:
                fail.append(f"{sid} ({e})")
        self._finish(ok, fail, "deleted")

    def _do_shift(self):
        try:
            mins = int(self.shift_var.get())
        except (TypeError, ValueError):
            messagebox.showerror("Error",
                                 "Shift amount must be a whole number of minutes.",
                                 parent=self.dialog)
            return
        if mins == 0:
            messagebox.showinfo("No change", "Shift of 0 minutes — nothing to do.",
                                parent=self.dialog)
            return
        if not messagebox.askyesno(
                "Confirm",
                f"Shift {len(self.schedule_ids)} schedule(s) by {mins} minute(s)?",
                parent=self.dialog):
            return

        # Read current start/end for each row up front so we can compute
        # the shift then push each one through the service.
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                cur = conn.cursor()
                placeholders = ",".join("?" * len(self.schedule_ids))
                cur.execute(
                    f"SELECT id, start_time, end_time FROM module_schedule "
                    f"WHERE id IN ({placeholders})",
                    self.schedule_ids,
                )
                rows = cur.fetchall()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to read schedules: {e}",
                                 parent=self.dialog)
            return

        changed_by = self._changed_by()
        ok, fail = 0, []
        for sid, start, end in rows:
            new_start = _shift_time(start, mins)
            new_end = _shift_time(end, mins)
            if not new_start or not new_end:
                fail.append(f"{sid} (would cross midnight)")
                continue
            try:
                if self.scheduler.update_module_schedule(
                        sid, start_time=new_start, end_time=new_end,
                        changed_by=changed_by):
                    ok += 1
                else:
                    fail.append(str(sid))
            except Exception as e:
                fail.append(f"{sid} ({e})")
        self._finish(ok, fail, "shifted")

    def _finish(self, ok: int, fail: list, verb: str):
        msg = f"{verb.capitalize()} {ok} schedule(s)."
        if fail:
            shown = ", ".join(str(x) for x in fail[:5])
            more = f", … (+{len(fail) - 5} more)" if len(fail) > 5 else ""
            msg += f"\n\nFailed: {shown}{more}"
        messagebox.showinfo("Bulk action complete", msg, parent=self.dialog)
        if self.gui and hasattr(self.gui, "refresh_schedules"):
            self.gui.refresh_schedules()
        self.dialog.destroy()
