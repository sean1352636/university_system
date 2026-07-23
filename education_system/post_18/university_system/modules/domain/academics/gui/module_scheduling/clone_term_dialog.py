"""Clone-term-plan dialog ("what-if" scenarios).

Copies every published row in module_schedule from a source term into draft
rows for a target term. Each clone carries `parent_schedule_id` pointing back
to the source row so the relationship stays queryable. Drafts skip conflict
checks and notifications, so planners can iterate freely before promoting
anything to published.
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.core import paths

DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH
logger = logging.getLogger(__name__)

_SEMESTERS = ["Fall", "Spring", "Summer", "Winter"]


class CloneTermDialog:
    """Pick (source semester, year) and (target semester, year), preview, clone."""

    def __init__(self, parent, scheduler, gui=None):
        self.parent = parent
        self.scheduler = scheduler
        self.gui = gui

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Clone Term Plan")
        self.dialog.geometry("520x340")
        self.dialog.transient(parent)
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass

        self._build_ui()

    def _build_ui(self):
        frame = ttk.Frame(self.dialog, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame,
                  text="Copy published schedules from one term into draft "
                       "rows of another term.\nDrafts skip conflict checks "
                       "and notifications until you publish them.",
                  wraplength=480, justify=tk.LEFT
                  ).grid(row=0, column=0, columnspan=4, pady=(0, 12), sticky=tk.W)

        now = datetime.now()
        default_sem = "Spring" if now.month <= 5 else ("Summer" if now.month <= 7 else "Fall")
        next_sem = {"Fall": "Spring", "Spring": "Summer",
                    "Summer": "Fall", "Winter": "Spring"}.get(default_sem, "Spring")
        next_year = now.year if next_sem != "Fall" else now.year + 1

        # Source
        ttk.Label(frame, text="From:").grid(row=1, column=0, sticky=tk.W, pady=4)
        self.src_sem_var = tk.StringVar(value=default_sem)
        ttk.Combobox(frame, textvariable=self.src_sem_var, values=_SEMESTERS,
                     width=10, state="readonly").grid(row=1, column=1, padx=4)
        self.src_year_var = tk.StringVar(value=str(now.year))
        ttk.Spinbox(frame, from_=now.year - 5, to=now.year + 5,
                    textvariable=self.src_year_var, width=6
                    ).grid(row=1, column=2, padx=4)
        ttk.Button(frame, text="Preview", command=self._refresh_preview
                   ).grid(row=1, column=3, padx=8)

        # Target
        ttk.Label(frame, text="To:").grid(row=2, column=0, sticky=tk.W, pady=4)
        self.tgt_sem_var = tk.StringVar(value=next_sem)
        ttk.Combobox(frame, textvariable=self.tgt_sem_var, values=_SEMESTERS,
                     width=10, state="readonly").grid(row=2, column=1, padx=4)
        self.tgt_year_var = tk.StringVar(value=str(next_year))
        ttk.Spinbox(frame, from_=now.year - 5, to=now.year + 5,
                    textvariable=self.tgt_year_var, width=6
                    ).grid(row=2, column=2, padx=4)

        # Preview line
        self.preview_var = tk.StringVar(value="(click Preview to see how many published rows would clone)")
        ttk.Label(frame, textvariable=self.preview_var, foreground="#444",
                  wraplength=480, justify=tk.LEFT
                  ).grid(row=3, column=0, columnspan=4, pady=(12, 0), sticky=tk.W)

        # Action buttons
        btn = ttk.Frame(frame)
        btn.grid(row=4, column=0, columnspan=4, pady=20, sticky=tk.E)
        ttk.Button(btn, text="Clone as drafts",
                   command=self._do_clone).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn, text="Cancel",
                   command=self.dialog.destroy).pack(side=tk.LEFT, padx=4)

    def _src_term(self):
        try:
            return self.src_sem_var.get(), int(self.src_year_var.get())
        except (TypeError, ValueError):
            return self.src_sem_var.get(), 0

    def _tgt_term(self):
        try:
            return self.tgt_sem_var.get(), int(self.tgt_year_var.get())
        except (TypeError, ValueError):
            return self.tgt_sem_var.get(), 0

    def _refresh_preview(self):
        src_sem, src_year = self._src_term()
        tgt_sem, tgt_year = self._tgt_term()
        if not src_year:
            self.preview_var.set("Source year is invalid.")
            return
        if (src_sem, src_year) == (tgt_sem, tgt_year):
            self.preview_var.set("Source and target are the same term — nothing to clone.")
            return
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                cur = conn.cursor()
                cur.execute("""
                    SELECT COUNT(*) FROM module_schedule
                    WHERE semester = ? AND year = ? AND status = 'published'
                """, (src_sem, src_year))
                src_count = cur.fetchone()[0] or 0
                cur.execute("""
                    SELECT COUNT(*) FROM module_schedule
                    WHERE semester = ? AND year = ?
                """, (tgt_sem, tgt_year))
                tgt_existing = cur.fetchone()[0] or 0
        except sqlite3.Error as e:
            self.preview_var.set(f"DB error: {e}")
            return

        self.preview_var.set(
            f"Source ({src_sem} {src_year}): {src_count} published rows "
            f"will be cloned as drafts.\n"
            f"Target ({tgt_sem} {tgt_year}): currently has {tgt_existing} row(s); "
            f"clones are added alongside, not merged.")

    def _do_clone(self):
        src_sem, src_year = self._src_term()
        tgt_sem, tgt_year = self._tgt_term()
        if not src_year or not tgt_year:
            messagebox.showerror("Error", "Year fields must be whole numbers.",
                                 parent=self.dialog)
            return
        if (src_sem, src_year) == (tgt_sem, tgt_year):
            messagebox.showerror("Error",
                                 "Source and target must be different terms.",
                                 parent=self.dialog)
            return

        # Resolve user for the audit trail.
        changed_by = "gui"
        try:
            if self.gui and hasattr(self.gui, "_resolve_changed_by"):
                changed_by = self.gui._resolve_changed_by()
        except Exception:
            pass

        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                cur = conn.cursor()
                cur.execute("""
                    SELECT id, module_code, day_of_week, start_time, end_time,
                           room_id, instructor_id, session_type,
                           recurrence, recurrence_until
                    FROM module_schedule
                    WHERE semester = ? AND year = ? AND status = 'published'
                """, (src_sem, src_year))
                source_rows = cur.fetchall()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to read source term: {e}",
                                 parent=self.dialog)
            return

        if not source_rows:
            messagebox.showinfo("Nothing to clone",
                                f"No published rows in {src_sem} {src_year}.",
                                parent=self.dialog)
            return

        if not messagebox.askyesno(
                "Confirm",
                f"Clone {len(source_rows)} published row(s) "
                f"from {src_sem} {src_year} into {tgt_sem} {tgt_year} as drafts?",
                parent=self.dialog):
            return

        # Use the service-layer add path so each clone goes through the same
        # validation + history-logging the GUI's normal flow does. Drafts
        # bypass conflict checks so cloning into an already-busy term works.
        cloned = 0
        failures = 0
        for row in source_rows:
            (parent_id, module_code, day_of_week, start_time, end_time,
             room_id, instructor_id, session_type, recurrence,
             recurrence_until) = row
            new_id = False
            try:
                new_id = self.scheduler.add_module_schedule(
                    module_code, day_of_week, start_time, end_time,
                    room_id, instructor_id, session_type,
                    semester=tgt_sem, year=tgt_year, status="draft",
                    recurrence=recurrence or "weekly",
                    recurrence_until=recurrence_until,
                    parent_schedule_id=parent_id,
                    changed_by=changed_by,
                )
            except Exception:
                logger.exception("Failed to clone schedule row %s", parent_id)
            if new_id:
                cloned += 1
            else:
                failures += 1

        messagebox.showinfo(
            "Clone complete",
            f"Cloned {cloned} row(s) into {tgt_sem} {tgt_year} as drafts."
            + (f"\n{failures} failed." if failures else ""),
            parent=self.dialog,
        )
        if self.gui and hasattr(self.gui, "refresh_schedules"):
            self.gui.refresh_schedules()
        self.dialog.destroy()
