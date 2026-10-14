"""GUI tabs for the Sixth Form register lifecycle.

Two panels, mounted as extra tabs on the Attendance screen:

* **Sessions** — the chase list. Every timetabled register in a date
  window that nobody has submitted, with submit/reopen to hand.
* **Bulk & range** — mark a date range for known absence, and review
  early leavers.

The register itself (rows, keyboard marking, undo) lives on the Take
register tab in :mod:`attendance_views`; this module deliberately does
not import that one, so the import graph stays one-way.
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date, timedelta as _timedelta
from tkinter import messagebox, simpledialog, ttk

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance_register as register,
)
from education_system.systems.sixth_form.domain.academics.attendance.attendance import (
    STATUSES,
    ValidationError,
)
from education_system.systems.sixth_form.domain.academics.class_groups import (
    class_groups as cg_data,
)
from education_system.systems.sixth_form.domain.academics.courses import (
    courses as course_data,
)
from education_system.systems.sixth_form.domain.academics.timetable.timetable import (
    day_name,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)

logger = logging.getLogger(__name__)


def _today() -> str:
    return _date.today().isoformat()


def _actor(gui) -> str | None:
    auth = getattr(gui, "auth", None)
    return ((getattr(auth, "current_user", None) or {}).get("username")
            if auth else None)


def _group_choices() -> tuple[list[str], dict[str, int]]:
    groups = cg_data.list_groups()
    courses = {c.course_id: c for c in course_data.list_courses()}
    labels = [
        f"#{g.group_id} {g.group_name} "
        f"({courses[g.course_id].course_code if g.course_id in courses else '?'})"
        for g in groups
    ]
    return labels, {label: g.group_id for label, g in zip(labels, groups)}


# ── Sessions tab ────────────────────────────────────────────────────

def build_sessions_tab(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))

    from_var = tk.StringVar(value=_today())
    to_var = tk.StringVar(value=_today())
    group_labels, group_by_label = _group_choices()
    group_var = tk.StringVar(value="")

    ttk.Label(bar, text="From:").pack(side="left")
    ttk.Entry(bar, textvariable=from_var, width=12).pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="To:").pack(side="left")
    ttk.Entry(bar, textvariable=to_var, width=12).pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="Group:").pack(side="left")
    ttk.Combobox(bar, textvariable=group_var,
                 values=["(all)", *group_labels], state="readonly", width=32
                 ).pack(side="left", padx=(4, 8))

    ttk.Label(
        parent,
        text=("Registers that were never submitted. A slot with no rows at "
              "all reads 'Not started' — the point is to tell that apart "
              "from a register where everyone happened to be present."),
        foreground="#666", wraplength=760, justify="left",
    ).pack(anchor="w", pady=(0, 6))

    table_holder = ttk.Frame(parent)
    table_holder.pack(fill="both", expand=True)
    summary = ttk.Label(parent, text="", foreground="#555")
    summary.pack(anchor="w", pady=(4, 6))
    actions = ttk.Frame(parent)
    actions.pack(anchor="w")

    tree = ttk.Treeview(
        table_holder,
        columns=("date", "slot", "day", "period", "room", "state", "marked"),
        show="headings", height=14)
    for col, text, width in (
        ("date",   "Date",     100),
        ("slot",   "Slot",      60),
        ("day",    "Day",       60),
        ("period", "Period",    60),
        ("room",   "Room",      80),
        ("state",  "State",    110),
        ("marked", "Marked",   100),
    ):
        tree.heading(col, text=text)
        tree.column(col, width=width, anchor="w")
    scroll = ttk.Scrollbar(table_holder, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")

    def refresh() -> None:
        tree.delete(*tree.get_children())
        label = group_var.get()
        try:
            rows = register.unsubmitted_registers(
                date_from=from_var.get().strip() or None,
                date_to=to_var.get().strip() or None,
                group_id=group_by_label.get(label),
            )
        except ValidationError as e:
            summary.configure(text=str(e), foreground="#a33")
            return
        except Exception as e:
            logger.exception("unsubmitted_registers failed")
            summary.configure(text=f"Error: {e}", foreground="#a33")
            return
        for m in rows:
            tree.insert("", "end", iid=f"{m.slot_id}|{m.date}", values=(
                m.date, m.slot_id, day_name(m.day), m.period, m.room or "—",
                m.state, f"{m.marked}/{m.expected}",
            ))
        summary.configure(
            text=(f"{len(rows)} register(s) outstanding."
                  if rows else "All timetabled registers submitted. ✓"),
            foreground="#a33" if rows else "#2a7")
        gui.status_var.set(f"Unsubmitted registers: {len(rows)}")

    def _selected() -> tuple[int, str] | None:
        selection = tree.selection()
        if not selection:
            messagebox.showinfo("No selection",
                                "Pick a register first.", parent=gui.root)
            return None
        slot_s, date_s = selection[0].split("|", 1)
        return int(slot_s), date_s

    def submit_selected() -> None:
        picked = _selected()
        if picked is None:
            return
        slot_id, date_s = picked
        try:
            register.submit_register(slot_id, date_s,
                                     submitted_by=_actor(gui))
        except ValidationError as e:
            if "unmarked" not in str(e):
                messagebox.showerror("Cannot submit", str(e), parent=gui.root)
                return
            if not messagebox.askyesno(
                    "Incomplete register", f"{e}\n\nSubmit it anyway?",
                    default="no", parent=gui.root):
                return
            try:
                register.submit_register(slot_id, date_s,
                                         allow_incomplete=True,
                                         submitted_by=_actor(gui))
            except ValidationError as e2:
                messagebox.showerror("Cannot submit", str(e2), parent=gui.root)
                return
        refresh()

    def reopen_selected() -> None:
        picked = _selected()
        if picked is None:
            return
        slot_id, date_s = picked
        reason = (simpledialog.askstring(
            "Reopen register", "Why is this register being reopened?",
            parent=gui.root) or "").strip()
        if not reason:
            return
        try:
            register.reopen_register(slot_id, date_s, reason=reason,
                                     reopened_by=_actor(gui))
        except ValidationError as e:
            messagebox.showerror("Cannot reopen", str(e), parent=gui.root)
            return
        refresh()

    ttk.Button(bar, text="Show", command=refresh).pack(side="left")
    ttk.Button(actions, text="Submit selected", command=submit_selected
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Reopen selected", command=reopen_selected
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Refresh", command=refresh
               ).pack(side="left", padx=(12, 0))
    refresh()


# ── Bulk & range tab ────────────────────────────────────────────────

def build_bulk_tab(gui, parent: ttk.Frame) -> None:
    ttk.Label(
        parent,
        text=("Mark a stretch of known absence — study leave, hospital, a "
              "trip — across every lesson the students actually had. Days "
              "with no timetabled slot are skipped, and any register that "
              "has already been submitted is left alone."),
        foreground="#666", wraplength=760, justify="left",
    ).pack(anchor="w", pady=(0, 10))

    form = ttk.Frame(parent)
    form.pack(anchor="w", pady=(0, 8))

    group_labels, group_by_label = _group_choices()
    from_var = tk.StringVar(value=_today())
    to_var = tk.StringVar(
        value=(_date.today() + _timedelta(days=4)).isoformat())
    status_var = tk.StringVar(value="Authorised")
    group_var = tk.StringVar(value=group_labels[0] if group_labels else "")
    students_var = tk.StringVar()
    notes_var = tk.StringVar()

    fields = [
        ("From (YYYY-MM-DD):", from_var, 14),
        ("To (YYYY-MM-DD):",   to_var,   14),
        ("Students (IDs, comma-separated; blank = whole group):",
         students_var, 46),
        ("Notes:", notes_var, 46),
    ]
    row = 0
    ttk.Label(form, text="Group:").grid(row=row, column=0, sticky="e",
                                        padx=(0, 6), pady=3)
    ttk.Combobox(form, textvariable=group_var, values=group_labels,
                 state="readonly", width=38
                 ).grid(row=row, column=1, sticky="w", pady=3)
    row += 1
    ttk.Label(form, text="Status:").grid(row=row, column=0, sticky="e",
                                         padx=(0, 6), pady=3)
    ttk.Combobox(form, textvariable=status_var, values=list(STATUSES),
                 state="readonly", width=18
                 ).grid(row=row, column=1, sticky="w", pady=3)
    for label, var, width in fields:
        row += 1
        ttk.Label(form, text=label).grid(row=row, column=0, sticky="e",
                                         padx=(0, 6), pady=3)
        ttk.Entry(form, textvariable=var, width=width
                  ).grid(row=row, column=1, sticky="w", pady=3)

    result_label = ttk.Label(parent, text="", foreground="#333",
                             wraplength=760, justify="left")
    result_label.pack(anchor="w", pady=(6, 10))

    def apply_range() -> None:
        group_id = group_by_label.get(group_var.get())
        if group_id is None:
            messagebox.showerror("Cannot mark", "Pick a class group.",
                                 parent=gui.root)
            return
        raw = students_var.get().strip()
        student_ids = [s.strip() for s in raw.split(",") if s.strip()] or None
        if student_ids:
            unknown = [s for s in student_ids
                       if student_data.get_student(s) is None]
            if unknown:
                messagebox.showerror(
                    "Unknown student(s)",
                    "No student with id: " + ", ".join(unknown),
                    parent=gui.root)
                return
        who = ("the whole group" if student_ids is None
               else f"{len(student_ids)} student(s)")
        if not messagebox.askyesno(
                "Mark date range",
                f"Mark {who} as {status_var.get()} from "
                f"{from_var.get()} to {to_var.get()}?", parent=gui.root):
            return
        try:
            result = register.mark_range(
                date_from=from_var.get().strip(),
                date_to=to_var.get().strip(),
                status=status_var.get(),
                group_id=group_id,
                student_ids=student_ids,
                notes=notes_var.get().strip() or None,
                actor=_actor(gui),
            )
        except ValidationError as e:
            messagebox.showerror("Cannot mark", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("mark_range crashed")
            messagebox.showerror("Error", f"Unexpected: {e}", parent=gui.root)
            return

        text = (f"Wrote {result.written} row(s) across "
                f"{len(result.dates)} teaching day(s).")
        if result.skipped_no_slot:
            text += f"  {result.skipped_no_slot} day(s) had no lessons."
        if result.skipped_locked:
            text += (f"  {result.skipped_locked} row(s) skipped — those "
                     "registers are already submitted; reopen them to "
                     "include them.")
        result_label.configure(text=text)
        gui.status_var.set(f"Range marked: {result.written} row(s)")

    ttk.Button(parent, text="Mark range", command=apply_range
               ).pack(anchor="w", pady=(0, 12))

    # ── Early leavers ──
    ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=(4, 8))
    ttk.Label(parent, text="Early leavers", font=("", 11, "bold")
              ).pack(anchor="w")

    leaver_bar = ttk.Frame(parent)
    leaver_bar.pack(anchor="w", pady=(4, 6))
    lfrom_var = tk.StringVar(
        value=(_date.today() - _timedelta(days=28)).isoformat())
    lto_var = tk.StringVar(value=_today())
    ttk.Label(leaver_bar, text="From:").pack(side="left")
    ttk.Entry(leaver_bar, textvariable=lfrom_var, width=12
              ).pack(side="left", padx=(4, 12))
    ttk.Label(leaver_bar, text="To:").pack(side="left")
    ttk.Entry(leaver_bar, textvariable=lto_var, width=12
              ).pack(side="left", padx=(4, 8))

    leaver_holder = ttk.Frame(parent)
    leaver_holder.pack(fill="both", expand=True)
    leaver_tree = ttk.Treeview(
        leaver_holder,
        columns=("date", "slot", "student", "name", "left", "missed"),
        show="headings", height=8)
    for col, text, width in (
        ("date",    "Date",     100),
        ("slot",    "Slot",      60),
        ("student", "Student",  110),
        ("name",    "Name",     200),
        ("left",    "Left at",   80),
        ("missed",  "Missed",    80),
    ):
        leaver_tree.heading(col, text=text)
        leaver_tree.column(col, width=width, anchor="w")
    leaver_tree.pack(side="left", fill="both", expand=True)

    def refresh_leavers() -> None:
        leaver_tree.delete(*leaver_tree.get_children())
        try:
            rows = register.list_early_leavers(
                date_from=lfrom_var.get().strip() or None,
                date_to=lto_var.get().strip() or None)
        except ValidationError as e:
            messagebox.showerror("Cannot list", str(e), parent=gui.root)
            return
        names = {s.student_id: s.full_name for s in student_data.list_students()}
        for r in rows:
            leaver_tree.insert("", "end", iid=str(r.record_id), values=(
                r.date, r.slot_id, r.student_id,
                names.get(r.student_id, "(deleted)"),
                r.departure_time, f"{register.minutes_missed(r)} min",
            ))
        gui.status_var.set(f"Early leavers: {len(rows)}")

    ttk.Button(leaver_bar, text="Show", command=refresh_leavers
               ).pack(side="left")
    refresh_leavers()


__all__ = ["build_sessions_tab", "build_bulk_tab"]
