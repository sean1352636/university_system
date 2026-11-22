"""Student Loans Company: attendance confirmation per census point and
change-of-circumstance notices. Everything goes through
``application/statutory/slc``; this screen writes the upload file into the
``slc`` connector folder but never sends it.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from education_system.systems.university.application.statutory import slc
from education_system.systems.university.domains.governance.interfaces.gui.compliance.statutory_returns.hesa_panel import (  # noqa: E501
    _fill,
    _tree,
)

TITLE = "Student Loans Company"
_DECISION_LABELS = {"confirmed": "Confirm attending", "held": "Hold",
                    "not_attending": "Not attending", "withdrawn": "Withdrawn"}


class SlcPanel(ttk.Frame):
    """``user`` is a callable returning the signed-in session dict."""

    WORK = (("student_id", "Student", 100), ("name", "Name", 200),
            ("programme", "Programme", 110), ("attendance_pct", "Attend %", 70),
            ("suggested", "Suggested", 90), ("why", "Why", 260),
            ("decision", "Decision", 100), ("reason", "Reason", 180),
            ("batch_id", "Exported in", 150))
    CHANGES = (("notification_id", "#", 50), ("student_id", "Student", 100),
               ("name", "Name", 180), ("change_type", "Change", 200),
               ("effective_date", "Effective", 90), ("details", "Details", 300),
               ("status", "Status", 90), ("slc_reference", "SLC ref", 110),
               ("batch_id", "Batch", 150))

    def __init__(self, master, user=None):
        super().__init__(master, padding=8)
        self._user = user if callable(user) else (lambda: user)
        self.points: dict[str, dict] = {}
        self.work_rows: dict = {}
        self.change_rows: dict = {}
        book = ttk.Notebook(self)
        book.pack(fill=tk.BOTH, expand=True)
        self._census_tab(book)
        self._changes_tab(book)
        self._load_points(quiet=True)

    def _run(self, fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (PermissionError, ValueError) as exc:
            messagebox.showerror(TITLE, str(exc), parent=self)
        except Exception as exc:
            messagebox.showerror(TITLE, f"That didn't work: {exc}", parent=self)
        return None

    # ------------------------------------------------------------- census
    def _census_tab(self, book):
        tab = ttk.Frame(book, padding=8)
        book.add(tab, text="Attendance confirmation")
        bar = ttk.Frame(tab)
        bar.pack(fill=tk.X)
        ttk.Label(bar, text="Census point:").pack(side=tk.LEFT)
        self.point = tk.StringVar()
        self.point_box = ttk.Combobox(bar, textvariable=self.point, state="readonly", width=48)
        self.point_box.pack(side=tk.LEFT, padx=4)
        self.point_box.bind("<<ComboboxSelected>>", lambda _e: self._load_worklist())
        ttk.Button(bar, text="Reload dates", command=self._load_points).pack(side=tk.LEFT)
        ttk.Label(bar, text="Attendance window (days):").pack(side=tk.LEFT, padx=(10, 4))
        self.window = tk.StringVar(value="28")
        ttk.Entry(bar, textvariable=self.window, width=5).pack(side=tk.LEFT)
        ttk.Button(bar, text="Show worklist", command=self._load_worklist).pack(side=tk.LEFT,
                                                                                padx=6)

        actions = ttk.Frame(tab)
        actions.pack(side=tk.BOTTOM, fill=tk.X, pady=(6, 0))
        ttk.Label(actions, text="Selected:").pack(side=tk.LEFT)
        for status, label in _DECISION_LABELS.items():
            ttk.Button(actions, text=label,
                       command=lambda s=status: self._decide_selected(s)).pack(side=tk.LEFT,
                                                                                padx=2)
        ttk.Button(actions, text="Accept all suggestions (undecided)",
                   command=self._accept_suggestions).pack(side=tk.LEFT, padx=(12, 2))
        ttk.Button(actions, text="Write SLC file…",
                   command=self._export).pack(side=tk.RIGHT)

        self.census_status = tk.StringVar(
            value="Census points are the academic calendar's SLC census key dates.")
        ttk.Label(tab, textvariable=self.census_status, wraplength=1100,
                  justify=tk.LEFT).pack(anchor="w", pady=6)
        self.work_view = _tree(tab, self.WORK, height=16)
        self.work_view.configure(selectmode="extended")

    def _load_points(self, quiet=False):
        try:
            points = slc.census_points(self._user())
        except Exception as exc:
            if not quiet:
                messagebox.showerror(TITLE, str(exc), parent=self)
            points = []
        self.points = {f"{str(p['start_date'])[:10]}  {p.get('title') or ''} "
                       f"({p.get('year_code') or '?'})": p for p in points}
        self.point_box.configure(values=list(self.points))
        if self.point.get() not in self.points:
            self.point.set(next(reversed(self.points), "") if self.points else "")
        if not self.points and not quiet:
            messagebox.showinfo(TITLE, "No SLC census dates yet. Add a 'Student Loans Company "
                                "attendance confirmation' key date in the Academic Calendar.",
                                parent=self)

    def _census_date(self) -> str | None:
        point = self.points.get(self.point.get())
        if not point:
            messagebox.showinfo(TITLE, "Pick a census point first.", parent=self)
            return None
        return str(point["start_date"])[:10]

    def _load_worklist(self):
        day = self._census_date()
        if not day:
            return
        try:
            window = int(self.window.get() or 28)
        except ValueError:
            messagebox.showerror(TITLE, "The attendance window is a number of days.", parent=self)
            return
        work = self._run(slc.worklist, self._user(), day, window_days=window)
        if work is None:
            return
        rows = work["rows"]
        self.work_rows = _fill(self.work_view, rows, self.WORK)
        undecided = sum(1 for r in rows if not r["decision"])
        held = sum(1 for r in rows if (r["decision"] or r["suggested"]) == "held")
        exported = sum(1 for r in rows if r["batch_id"])
        self.census_status.set(
            f"{work['census']['date']} {work['census'].get('title') or ''}: {len(rows)} "
            f"registered, {undecided} undecided, {held} held or suggested hold, "
            f"{exported} already exported.")

    def _selected(self) -> list[dict]:
        return [self.work_rows[i] for i in self.work_view.selection() if i in self.work_rows]

    def _decide_selected(self, status):
        rows = self._selected()
        if not rows:
            messagebox.showinfo(TITLE, "Select one or more students first.", parent=self)
            return
        reason = None
        if status == "held":
            reason = simpledialog.askstring(TITLE, "Why are these students held?", parent=self)
            if not (reason or "").strip():
                return
        day = self._census_date()
        if day and self._run(slc.decide, self._user(), day,
                             {r["student_id"]: (status, reason) for r in rows}) is not None:
            self._load_worklist()

    def _accept_suggestions(self):
        day = self._census_date()
        if not day:
            return
        decisions = {r["student_id"]: (r["suggested"], r["why"] or None)
                     for r in self.work_rows.values() if not r["decision"]}
        if not decisions:
            messagebox.showinfo(TITLE, "Every student already has a decision.", parent=self)
            return
        if not messagebox.askyesno(TITLE, f"Record the suggested decision for "
                                   f"{len(decisions)} undecided student(s)?", parent=self):
            return
        if self._run(slc.decide, self._user(), day, decisions) is not None:
            self._load_worklist()

    def _export(self):
        point = self.points.get(self.point.get())
        day = str(point["start_date"])[:10] if point else None
        include = messagebox.askyesnocancel(
            TITLE, "Include pending change-of-circumstance notices in the file too?",
            parent=self)
        if include is None:
            return
        result = self._run(slc.export, self._user(), day, include_changes=include)
        if result is None:
            return
        if not result["path"]:
            messagebox.showinfo(TITLE, "Nothing new to send: no decided confirmations (holds "
                                "stay back) and no pending notices.", parent=self)
            return
        messagebox.showinfo(TITLE, f"Batch {result['batch_id']}: {result['confirmations']} "
                            f"confirmation(s), {result['changes']} change notice(s).\n\n"
                            f"Upload this file through the SLC provider portal:\n"
                            f"{result['path']}", parent=self)
        if point:
            self._load_worklist()
        self._load_changes()

    # ------------------------------------------------------------ changes
    def _changes_tab(self, book):
        tab = ttk.Frame(book, padding=8)
        book.add(tab, text="Changes of circumstance")
        bar = ttk.Frame(tab)
        bar.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(bar, text="Show:").pack(side=tk.LEFT)
        self.change_filter = tk.StringVar(value="pending")
        box = ttk.Combobox(bar, textvariable=self.change_filter, state="readonly", width=14,
                           values=("pending", "exported", "acknowledged", "not_required",
                                   "all"))
        box.pack(side=tk.LEFT, padx=4)
        box.bind("<<ComboboxSelected>>", lambda _e: self._load_changes())
        ttk.Button(bar, text="Find new changes", command=self._sync).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Refresh", command=self._load_changes).pack(side=tk.LEFT)
        actions = ttk.Frame(tab)
        actions.pack(side=tk.BOTTOM, fill=tk.X, pady=(6, 0))
        ttk.Button(actions, text="Mark acknowledged by SLC…",
                   command=lambda: self._set_change("acknowledged")).pack(side=tk.LEFT)
        ttk.Button(actions, text="Not required (no SLC funding)",
                   command=lambda: self._set_change("not_required")).pack(side=tk.LEFT, padx=4)
        ttk.Button(actions, text="Back to pending",
                   command=lambda: self._set_change("pending")).pack(side=tk.LEFT)
        self.change_view = _tree(tab, self.CHANGES, height=16)

    def _load_changes(self):
        status = self.change_filter.get()
        rows = self._run(slc.changes, self._user(), None if status == "all" else status)
        if rows is None:
            return
        for row in rows:
            row["name"] = " ".join(p for p in (row.get("first_name"), row.get("last_name")) if p)
        self.change_rows = _fill(self.change_view, rows, self.CHANGES)

    def _sync(self):
        added = self._run(slc.sync_changes, self._user())
        if added is not None:
            messagebox.showinfo(TITLE, f"{added} new change notice(s) raised.", parent=self)
            self._load_changes()

    def _set_change(self, status):
        sel = [self.change_rows[i] for i in self.change_view.selection() if i in self.change_rows]
        if not sel:
            messagebox.showinfo(TITLE, "Select a notice first.", parent=self)
            return
        ref = None
        if status == "acknowledged":
            ref = simpledialog.askstring(TITLE, "SLC reference for the acknowledgement:",
                                         parent=self)
            if not (ref or "").strip():
                return
        for row in sel:
            if self._run(slc.set_change_status, self._user(), row["notification_id"], status,
                         ref) is None:
                break
        self._load_changes()
