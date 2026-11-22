"""Induction sessions tab: sessions, booking and the register.

Left: the sessions (:func:`induction.list_sessions`); right: the selected
session's register. Writers create / edit / cancel sessions (cancelling
needs a reason), book learners or the whole cohort (each learner who
could not be booked is listed with the reason) and mark the register
Present / Absent / Excused (:func:`induction.mark_register` — Present
ticks the session's onboarding task).
"""

from __future__ import annotations

import logging
import re
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.sixth_form.domain.admissions.onboarding import (
    induction,
)
from education_system.systems.sixth_form.domain.admissions.onboarding import (
    onboarding as data,
)
from education_system.systems.sixth_form.domain.admissions.onboarding import (
    templates as tpl,
)
from education_system.systems.sixth_form.interfaces.gui.admissions import (
    _admissions_ui as ui,
)
from education_system.systems.sixth_form.interfaces.gui.admissions.onboarding import (
    checklist_extras as extras,
)
from education_system.systems.sixth_form.interfaces.gui.admissions.onboarding import (
    onboarding_actions as actions,
)

logger = logging.getLogger(__name__)


def _task_keys() -> list[str]:
    """Template task keys a session can satisfy (not ID / consent ones)."""
    keys: set[str] = set()
    try:
        for t in tpl.list_templates(include_inactive=False):
            keys.update(i.key for i in t.items)
    except Exception:  # noqa: BLE001 — the field still takes typing
        logger.exception("Template keys failed to load")
    return [""] + sorted(k for k in keys if k not in data.ID_ITEMS
                         and k not in data.CONSENT_ITEMS)


SESSION_FIELDS = [
    ("title", "Title", "entry", None),
    ("session_date", "Date (YYYY-MM-DD)", "entry", None),
    ("start_time", "Start (HH:MM)", "entry", None),
    ("end_time", "End (HH:MM, optional)", "entry", None),
    ("room", "Room", "entry", None),
    ("capacity", "Capacity (blank = no limit)", "entry", None),
    ("academic_year", "Academic year (blank = from the date)", "entry", None),
    ("year_group", "For year group", "readonly", ("", "12", "13")),
    ("task_key", "Onboarding task it satisfies", "combo", None),
    ("notes", "Notes", "text", None),
]


class InductionTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Induction")
        self._writable = actions.can_write()
        self._write_buttons: list[ttk.Button] = []
        self._sessions: dict[str, induction.Session] = {}
        self._build()
        self.refresh()

    def _wbtn(self, parent: tk.Misc, text: str,
              command: Callable[[], None]) -> ttk.Button:
        b = ttk.Button(parent, text=text, command=command)
        self._write_buttons.append(b)
        return b

    def _parent(self) -> tk.Misc:
        return self.frame.winfo_toplevel()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Academic year:").pack(side="left")
        self.year_e = ttk.Entry(bar, width=10)
        self.year_e.pack(side="left", padx=(2, 8))
        self.year_e.bind("<Return>", lambda _e: self.refresh())
        self.upcoming_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Upcoming only", variable=self.upcoming_var,
                        command=self.refresh).pack(side="left")
        self.cancelled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Show cancelled",
                        variable=self.cancelled_var,
                        command=self.refresh).pack(side="left", padx=6)
        ttk.Button(bar, text="Refresh",
                   command=self.refresh).pack(side="left", padx=6)
        if not self._writable:
            ttk.Label(bar, foreground="#a33",
                      text="Read-only").pack(side="right")

        pane = ttk.Panedwindow(self.frame, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        left, right = ttk.Frame(pane), ttk.Frame(pane)
        pane.add(left, weight=3)
        pane.add(right, weight=2)

        sacts = ttk.Frame(left)
        sacts.pack(side="bottom", fill="x", pady=(4, 0))
        self._wbtn(sacts, "New session…", self._new).pack(side="left")
        self._wbtn(sacts, "Edit…", self._edit).pack(side="left", padx=4)
        self._wbtn(sacts, "Cancel session…",
                   self._cancel).pack(side="left", padx=4)
        self._wbtn(sacts, "Book learners…",
                   self._book).pack(side="left", padx=(12, 4))
        self._wbtn(sacts, "Book whole cohort",
                   self._book_cohort).pack(side="left", padx=4)
        holder = ttk.Frame(left)
        holder.pack(fill="both", expand=True)
        self.tree = ui.make_tree(holder, [
            ("id", "ID", 40), ("date", "Date", 90), ("time", "Time", 95),
            ("title", "Title", 200), ("room", "Room", 80),
            ("yg", "Year", 45), ("task", "Task it ticks", 180),
            ("booked", "Booked", 70), ("present", "Present", 60),
            ("status", "Status", 160)], height=22)
        self.tree.tag_configure("Cancelled", foreground="#999")
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._register())

        self.reg_title = tk.StringVar(value="Select a session.")
        ttk.Label(right, textvariable=self.reg_title, font=("", 10, "bold"),
                  wraplength=480, justify="left").pack(fill="x")
        racts = ttk.Frame(right)
        racts.pack(side="bottom", fill="x", pady=(4, 0))
        racts2 = ttk.Frame(right)
        racts2.pack(side="bottom", fill="x", pady=(4, 0))
        for mark in induction.MARKS:
            self._wbtn(racts, mark,
                       lambda m=mark: self._mark(m)).pack(side="left",
                                                          padx=(0, 4))
        self._wbtn(racts, "All present",
                   self._all_present).pack(side="left", padx=(8, 4))
        self._wbtn(racts2, "Unbook selected",
                   self._unbook).pack(side="left")
        ttk.Label(racts2, text="Note:").pack(side="left", padx=(12, 2))
        self.note_e = ttk.Entry(racts2, width=30)
        self.note_e.pack(side="left")
        rholder = ttk.Frame(right)
        rholder.pack(fill="both", expand=True)
        self.reg = ui.make_tree(rholder, [
            ("sid", "Student", 80), ("name", "Name", 150),
            ("status", "Mark", 70), ("by", "Marked by", 90),
            ("at", "Marked at", 130), ("note", "Note", 160)], height=22,
            selectmode="extended")
        for tag, colour in (("Present", "#d8f4d8"), ("Absent", "#ffd0d0"),
                            ("Excused", "#fff2c4")):
            self.reg.tag_configure(tag, background=colour)
        actions.set_write_state(self._write_buttons, self._writable)

    # ── data ────────────────────────────────────────────────────────
    def refresh(self) -> None:
        keep = ui.selected_iid(self.tree)
        ui.clear(self.tree)
        try:
            rows = induction.list_sessions(
                academic_year=self.year_e.get().strip() or None,
                upcoming_only=self.upcoming_var.get(),
                include_cancelled=self.cancelled_var.get())
        except Exception as e:  # noqa: BLE001
            logger.exception("Induction sessions failed to load")
            messagebox.showerror("Induction", str(e), parent=self._parent())
            return
        self._sessions = {str(s.session_id): s for s in rows}
        for s in rows:
            cap = f"{s.booked}/{s.capacity}" if s.capacity else str(s.booked)
            status = s.status + (f": {s.status_reason}"
                                 if s.status_reason else "")
            self.tree.insert("", "end", iid=str(s.session_id),
                             tags=(s.status,), values=(
                s.session_id, s.session_date,
                s.start_time + (f"–{s.end_time}" if s.end_time else ""),
                s.title, s.room or "", s.year_group or "all",
                s.task_key or "—", cap, s.present, status))
        if keep and self.tree.exists(keep):
            self.tree.selection_set(keep)
        self._register()

    def _selected_session(self, title: str) -> induction.Session | None:
        iid = ui.require_iid(self.tree, title)
        return self._sessions.get(iid) if iid else None

    def _register(self) -> None:
        ui.clear(self.reg)
        iid = ui.selected_iid(self.tree)
        s = self._sessions.get(iid) if iid else None
        if s is None:
            self.reg_title.set("Select a session.")
            return
        left = s.places_left
        self.reg_title.set(
            f"#{s.session_id} {s.title} — {s.session_date} {s.start_time}"
            f"\n{s.booked} booked"
            + (f", {left} place(s) left" if left is not None else "")
            + f", {s.present} present"
            + (f"\nTicks: {s.task_key}" if s.task_key else ""))
        for a in induction.register(s.session_id):
            self.reg.insert("", "end", iid=a.student_id, tags=(a.status,),
                            values=(a.student_id, a.student_name, a.status,
                                    a.marked_by or "", a.marked_at or "",
                                    a.note or ""))

    # ── sessions ────────────────────────────────────────────────────
    def _fields(self) -> list:
        keys = _task_keys()
        return [(k, label, kind, keys if k == "task_key" else opts)
                for k, label, kind, opts in SESSION_FIELDS]

    def _new(self) -> None:
        holder: dict[str, Any] = {}
        v = ui.ask_form(self._parent(), "New induction session",
                        self._fields(), {"start_time": "09:00"},
                        on_submit=lambda v: holder.update(
                            s=induction.create_session(v)))
        if v is not None:
            self.refresh()
            s = holder.get("s")
            if s is not None and self.tree.exists(str(s.session_id)):
                self.tree.selection_set(str(s.session_id))

    def _edit(self) -> None:
        s = self._selected_session("Edit session")
        if s is None:
            return
        initial = {k: getattr(s, k) for k, *_ in SESSION_FIELDS}
        if ui.ask_form(self._parent(), f"Edit session #{s.session_id}",
                       self._fields(), initial,
                       on_submit=lambda v: induction.update_session(
                           s.session_id, v)) is not None:
            self.refresh()

    def _cancel(self) -> None:
        s = self._selected_session("Cancel session")
        if s is None:
            return
        if actions.prompt_text(
                self._parent(), "Cancel session",
                f"Cancel '{s.title}' on {s.session_date}? It is kept, with "
                f"its register ({s.booked} booked).", label="Reason:",
                min_chars=5, on_submit=lambda r: induction.cancel_session(
                    s.session_id, reason=r)) is not None:
            self.refresh()

    def _show_booking(self, res: induction.BookingResult) -> None:
        lines = res.lines()
        extras.show_lines(self._parent(), "Booking", lines[0], lines[1:])
        self.refresh()

    def _book(self) -> None:
        s = self._selected_session("Book learners")
        if s is None:
            return
        holder: dict[str, Any] = {}

        def run(v: dict[str, Any]) -> None:
            ids = [x for x in re.split(r"[\s,;]+", v["ids"]) if x]
            if not ids:
                raise data.ValidationError("Give at least one student id")
            holder["res"] = induction.book(s.session_id, ids)

        if ui.ask_form(self._parent(), f"Book learners — {s.title}", [
                ("ids", "Student ids (one per line, or separated by "
                 "commas)", "text", None)], on_submit=run) is None:
            return
        self._show_booking(holder["res"])

    def _book_cohort(self) -> None:
        s = self._selected_session("Book cohort")
        if s is None:
            return
        who = f"Year {s.year_group}" if s.year_group else "every year group"
        if not messagebox.askyesno(
                "Book whole cohort", f"Book every learner enrolled in {who} "
                f"in {s.academic_year} on '{s.title}'?",
                parent=self._parent()):
            return
        try:
            res = induction.book_cohort(s.session_id)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Book cohort", str(e), parent=self._parent())
            return
        self._show_booking(res)

    # ── register ────────────────────────────────────────────────────
    def _save_marks(self, marks: dict[str, str]) -> None:
        s = self._selected_session("Register")
        if s is None or not marks:
            return
        try:
            res = induction.mark_register(
                s.session_id, marks, note=self.note_e.get().strip() or None)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Register", str(e), parent=self._parent())
            return
        lines = res.lines()
        extras.show_lines(self._parent(), "Register", lines[0], lines[1:])
        self.note_e.delete(0, "end")
        self.refresh()

    def _mark(self, mark: str) -> None:
        sel = self.reg.selection()
        if not sel:
            messagebox.showinfo("Register", "Select one or more learners on "
                                "the register.", parent=self._parent())
            return
        self._save_marks({sid: mark for sid in sel})

    def _all_present(self) -> None:
        rows = [i for i in self.reg.get_children()
                if self.reg.item(i, "values")[2] == induction.BOOKED]
        if not rows:
            messagebox.showinfo("Register", "Nobody is waiting to be "
                                "marked.", parent=self._parent())
            return
        if messagebox.askyesno("All present", f"Mark the {len(rows)} "
                               "unmarked learner(s) Present?",
                               parent=self._parent()):
            self._save_marks({sid: "Present" for sid in rows})

    def _unbook(self) -> None:
        s = self._selected_session("Unbook")
        sel = self.reg.selection()
        if s is None or not sel:
            return
        if not messagebox.askyesno("Unbook", f"Take {len(sel)} learner(s) "
                                   f"off '{s.title}'?", parent=self._parent()):
            return
        problems = []
        for sid in sel:
            try:
                induction.unbook(s.session_id, sid)
            except Exception as e:  # noqa: BLE001
                problems.append(f"{sid}: {e}")
        if problems:
            messagebox.showwarning("Unbook", "\n".join(problems),
                                   parent=self._parent())
        self.refresh()
