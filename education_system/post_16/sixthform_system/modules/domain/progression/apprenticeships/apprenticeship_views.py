"""GUI panels for Sixth Form Apprenticeships.

Four tabs:

* Directory  — filterable list of applications.
* Editor     — add / edit form with the full field set.
* Per-student — pick a student, see all their applications.
* Summary    — counts by status / sector / level, plus the upcoming
  interviews / deadlines alerts.
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date
from tkinter import messagebox, ttk
from typing import Any, Callable
from education_system.post_16.sixthform_system.modules.domain.progression.apprenticeships import apprenticeships
from education_system.post_16.sixthform_system.modules.domain.progression.apprenticeships import apprenticeships as data
from education_system.post_16.sixthform_system.modules.domain.students.students import students as student_data
from education_system.post_16.sixthform_system.modules.domain.progression.apprenticeships.apprenticeships import (
    Application,
    DEFAULT_STATUS,
    LEVELS,
    SECTORS,
    STATUSES,
    Summary,
    ValidationError,
)

logger = logging.getLogger(__name__)


def _clear(gui) -> ttk.Frame:
    for w in gui.content_frame.winfo_children():
        w.destroy()
    return gui.content_frame


def _heading(parent, text: str) -> None:
    ttk.Label(parent, text=text, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))


# ── Top-level tabbed view ───────────────────────────────────────────

def open_directory(gui) -> None:
    frame = _clear(gui)
    _heading(frame, "Apprenticeships")

    nb = ttk.Notebook(frame)
    nb.pack(fill="both", expand=True)

    dir_tab = ttk.Frame(nb, padding=8)
    editor_tab = ttk.Frame(nb, padding=8)
    student_tab = ttk.Frame(nb, padding=8)
    summary_tab = ttk.Frame(nb, padding=8)
    nb.add(dir_tab,     text="Directory")
    nb.add(editor_tab,  text="Editor")
    nb.add(student_tab, text="Per-student")
    nb.add(summary_tab, text="Summary")

    _build_directory_tab(gui, dir_tab)
    _build_editor_tab(gui, editor_tab)
    _build_student_tab(gui, student_tab)
    _build_summary_tab(gui, summary_tab)


# ─── Directory tab ──────────────────────────────────────────────────

def _build_directory_tab(gui, parent: ttk.Frame) -> None:
    filt = ttk.Frame(parent)
    filt.pack(anchor="w", fill="x", pady=(0, 8))

    sid_var = tk.StringVar()
    employer_var = tk.StringVar()
    level_var = tk.StringVar()
    sector_var = tk.StringVar()
    status_var = tk.StringVar()

    ttk.Label(filt, text="Student:").pack(side="left")
    ttk.Entry(filt, textvariable=sid_var, width=12
              ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Employer:").pack(side="left")
    ttk.Entry(filt, textvariable=employer_var, width=18
              ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Level:").pack(side="left")
    ttk.Combobox(filt, textvariable=level_var,
                 values=["", *[str(l) for l in LEVELS]],
                 state="readonly", width=4
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Sector:").pack(side="left")
    ttk.Combobox(filt, textvariable=sector_var,
                 values=["", *SECTORS], state="readonly", width=28
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Status:").pack(side="left")
    ttk.Combobox(filt, textvariable=status_var,
                 values=["", *STATUSES], state="readonly", width=12
                 ).pack(side="left", padx=(4, 4))

    table_holder = ttk.Frame(parent)
    table_holder.pack(fill="both", expand=True)
    summary = ttk.Label(parent, text="", foreground="#555")
    summary.pack(anchor="w", pady=(4, 8))
    actions_holder = ttk.Frame(parent)
    actions_holder.pack(anchor="w", pady=(0, 4))

    def refresh() -> None:
        for w in table_holder.winfo_children():
            w.destroy()
        for w in actions_holder.winfo_children():
            w.destroy()
        try:
            level = int(level_var.get()) if level_var.get().strip() else None
        except ValueError:
            messagebox.showerror("Bad filter",
                                 "Level must be a number.", parent=gui.root)
            return
        try:
            rows = data.list_applications_with_detail(
                student_id=sid_var.get().strip() or None,
                employer_like=employer_var.get().strip() or None,
                level=level,
                sector=sector_var.get().strip() or None,
                status=status_var.get().strip() or None,
            )
        except ValidationError as e:
            ttk.Label(table_holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return
        except Exception as e:
            logger.exception("list_applications failed")
            ttk.Label(table_holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        cols = ("application_id", "student", "name", "employer",
                "title", "level", "sector", "status",
                "deadline", "interview")
        headings = {
            "application_id": ("#",         50),
            "student":        ("Student",  100),
            "name":           ("Name",     160),
            "employer":       ("Employer", 160),
            "title":          ("Title",    200),
            "level":          ("L",         30),
            "sector":         ("Sector",   180),
            "status":         ("Status",   110),
            "deadline":       ("Deadline",  90),
            "interview":      ("Interview", 90),
        }
        tree = ttk.Treeview(table_holder, columns=cols,
                            show="headings", height=14)
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(table_holder, orient="vertical",
                            command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        for r in rows:
            a = r.application
            tree.insert("", "end", iid=str(a.application_id), values=(
                a.application_id, a.student_id, r.student_name,
                a.employer, a.apprenticeship_name,
                a.level if a.level else "—",
                (a.sector or "—")[:18],
                a.status,
                a.deadline or "—",
                a.interview_date or "—",
            ))
        summary.configure(text=f"{len(rows)} application(s).")

        def _selected() -> int | None:
            sel = tree.selection()
            return int(sel[0]) if sel else None

        def _require() -> int | None:
            aid = _selected()
            if aid is None:
                messagebox.showinfo("No selection",
                                    "Pick an application first.",
                                    parent=gui.root)
            return aid

        def _edit() -> None:
            aid = _require()
            if aid is None:
                return
            open_editor(gui, application_id=aid)

        def _delete() -> None:
            aid = _require()
            if aid is None:
                return
            a = data.get_application(aid)
            if a is None:
                return
            if not messagebox.askyesno(
                "Delete application",
                f"Delete application #{aid} ({a.employer} — "
                f"{a.apprenticeship_name})?",
                parent=gui.root,
            ):
                return
            try:
                data.delete_application(aid)
            except Exception as e:
                logger.exception("delete_application crashed")
                messagebox.showerror("Error", f"Could not delete: {e}",
                                     parent=gui.root)
                return
            refresh()

        ttk.Button(actions_holder, text="Open in editor",
                   command=_edit).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Delete",
                   command=_delete).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="New",
                   command=lambda: open_editor(gui, application_id=None)
                   ).pack(side="left", padx=(12, 6))
        ttk.Button(actions_holder, text="Refresh",
                   command=refresh).pack(side="left")
        tree.bind("<Double-1>", lambda _e: _edit())
        gui.status_var.set(f"Apprenticeships: {len(rows)} match(es)")

    ttk.Button(filt, text="Apply", command=refresh
               ).pack(side="left", padx=(8, 0))
    ttk.Button(filt, text="Clear",
               command=lambda: (sid_var.set(""), employer_var.set(""),
                                level_var.set(""), sector_var.set(""),
                                status_var.set(""), refresh())
               ).pack(side="left", padx=(4, 0))
    refresh()


# ─── Editor tab ─────────────────────────────────────────────────────

def _build_editor_tab(gui, parent: ttk.Frame) -> None:
    rows = data.list_applications()
    if rows:
        _render_editor(gui, parent, rows[0].application_id)
    else:
        ttk.Label(
            parent,
            text=("No apprenticeship applications yet. "
                  "Use Directory → New to start one."),
            foreground="#555",
        ).pack(anchor="w", pady=8)


def open_editor(gui, *, application_id: int | None) -> None:
    frame = _clear(gui)
    _heading(frame,
             f"Apprenticeship #{application_id}"
             if application_id else "New Apprenticeship")
    _render_editor(gui, frame, application_id)
    ttk.Button(frame, text="Back to Apprenticeships",
               command=lambda: open_directory(gui)
               ).pack(anchor="w", pady=(12, 0))


def _render_editor(gui, parent: ttk.Frame,
                   application_id: int | None) -> None:
    existing = (data.get_application(application_id)
                if application_id else None)

    form = ttk.Frame(parent)
    form.pack(anchor="w", fill="x", pady=(0, 8))
    form.columnconfigure(1, weight=1, minsize=320)

    # Student row
    if existing:
        ttk.Label(form, text="Student:").grid(
            row=0, column=0, sticky="e", padx=(0, 8), pady=2)
        ttk.Label(form, text=existing.student_id,
                  foreground="#555").grid(
            row=0, column=1, sticky="w", pady=2)
        student_var = tk.StringVar(value=existing.student_id)
        student_by_label = {}
    else:
        students = student_data.list_students()
        student_labels = [f"{s.student_id} — {s.full_name}" for s in students]
        student_by_label = {f"{s.student_id} — {s.full_name}": s.student_id
                            for s in students}
        student_var = tk.StringVar(
            value=student_labels[0] if student_labels else "")
        ttk.Label(form, text="Student *:").grid(
            row=0, column=0, sticky="e", padx=(0, 8), pady=2)
        ttk.Combobox(form, textvariable=student_var,
                     values=student_labels,
                     state="readonly", width=42
                     ).grid(row=0, column=1, sticky="w", pady=2)

    employer_var = tk.StringVar(
        value=existing.employer if existing else "")
    title_var = tk.StringVar(
        value=existing.apprenticeship_name if existing else "")
    level_var = tk.StringVar(
        value=str(existing.level) if existing and existing.level
              else "")
    sector_var = tk.StringVar(
        value=(existing.sector or "") if existing else "")
    ref_var = tk.StringVar(
        value=(existing.reference_no or "") if existing else "")
    location_var = tk.StringVar(
        value=(existing.location or "") if existing else "")
    salary_var = tk.StringVar(
        value=(f"{existing.salary:.2f}"
               if existing and existing.salary is not None else ""))
    submitted_var = tk.StringVar(
        value=(existing.submitted_at or "") if existing else "")
    deadline_var = tk.StringVar(
        value=(existing.deadline or "") if existing else "")
    interview_var = tk.StringVar(
        value=(existing.interview_date or "") if existing else "")
    start_var = tk.StringVar(
        value=(existing.start_date or "") if existing else "")
    status_var = tk.StringVar(
        value=existing.status if existing else DEFAULT_STATUS)

    notes_text = tk.Text(form, height=4, width=60)
    if existing and existing.notes:
        notes_text.insert("1.0", existing.notes)

    def row(idx: int, label: str, widget: tk.Widget) -> None:
        ttk.Label(form, text=label).grid(
            row=idx, column=0, sticky="e", padx=(0, 8), pady=2)
        widget.grid(row=idx, column=1, sticky="w", pady=2)

    row(1, "Employer *", ttk.Entry(form, textvariable=employer_var, width=42))
    row(2, "Apprenticeship title *",
        ttk.Entry(form, textvariable=title_var, width=42))
    row(3, "Level",
        ttk.Combobox(form, textvariable=level_var,
                     values=["", *[str(l) for l in LEVELS]],
                     state="readonly", width=6))
    row(4, "Sector",
        ttk.Combobox(form, textvariable=sector_var,
                     values=["", *SECTORS],
                     state="readonly", width=42))
    row(5, "Reference number",
        ttk.Entry(form, textvariable=ref_var, width=24))
    row(6, "Location",
        ttk.Entry(form, textvariable=location_var, width=32))
    row(7, "Salary (£)",
        ttk.Entry(form, textvariable=salary_var, width=12))
    row(8, "Submitted at (YYYY-MM-DD)",
        ttk.Entry(form, textvariable=submitted_var, width=14))
    row(9, "Deadline (YYYY-MM-DD)",
        ttk.Entry(form, textvariable=deadline_var, width=14))
    row(10, "Interview date (YYYY-MM-DD)",
        ttk.Entry(form, textvariable=interview_var, width=14))
    row(11, "Start date (YYYY-MM-DD)",
        ttk.Entry(form, textvariable=start_var, width=14))
    row(12, "Status",
        ttk.Combobox(form, textvariable=status_var,
                     values=list(STATUSES), state="readonly", width=14))
    ttk.Label(form, text="Notes").grid(
        row=13, column=0, sticky="ne", padx=(0, 8), pady=2)
    notes_text.grid(row=13, column=1, sticky="ew", pady=2)

    actions = ttk.Frame(parent)
    actions.pack(anchor="w", pady=(12, 0))

    def save() -> None:
        if existing:
            sid = existing.student_id
        else:
            sid = student_by_label.get(student_var.get())
            if not sid:
                messagebox.showerror("Cannot save",
                                     "Pick a student.", parent=gui.root)
                return
        payload = {
            "student_id":          sid,
            "employer":            employer_var.get(),
            "apprenticeship_name": title_var.get(),
            "level":               level_var.get(),
            "sector":              sector_var.get(),
            "reference_no":        ref_var.get(),
            "location":            location_var.get(),
            "salary":              salary_var.get(),
            "submitted_at":        submitted_var.get(),
            "deadline":            deadline_var.get(),
            "interview_date":      interview_var.get(),
            "start_date":          start_var.get(),
            "status":              status_var.get(),
            "notes":               notes_text.get("1.0", "end-1c").strip(),
        }
        try:
            if existing:
                saved = data.update_application(
                    existing.application_id, payload)
            else:
                saved = data.create_application(payload)
        except ValidationError as e:
            logger.warning("save apprenticeship rejected: %s", e)
            messagebox.showerror("Cannot save", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("save apprenticeship crashed")
            messagebox.showerror("Error", f"Unexpected: {e}",
                                 parent=gui.root)
            return
        gui.status_var.set(f"Saved apprenticeship #{saved.application_id}")
        messagebox.showinfo(
            "Saved",
            f"Saved application #{saved.application_id}.",
            parent=gui.root,
        )
        open_editor(gui, application_id=saved.application_id)

    def delete() -> None:
        if not existing:
            return
        if not messagebox.askyesno(
            "Delete application",
            f"Delete application #{existing.application_id}?",
            parent=gui.root,
        ):
            return
        try:
            data.delete_application(existing.application_id)
        except Exception as e:
            logger.exception("delete_application crashed")
            messagebox.showerror("Error", f"Could not delete: {e}",
                                 parent=gui.root)
            return
        gui.status_var.set("Deleted application")
        open_directory(gui)

    ttk.Button(actions, text="Save",
               command=save).pack(side="left", padx=(0, 6))
    if existing:
        ttk.Button(actions, text="Delete",
                   command=delete).pack(side="left", padx=(0, 6))


# ─── Per-student tab ────────────────────────────────────────────────

def _build_student_tab(gui, parent: ttk.Frame) -> None:
    students = student_data.list_students()
    labels = [f"{s.student_id} — {s.full_name}" for s in students]
    by_label = {lbl: s.student_id for lbl, s in zip(labels, students)}

    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))
    student_var = tk.StringVar(value=labels[0] if labels else "")
    ttk.Label(bar, text="Student:").pack(side="left")
    ttk.Combobox(bar, textvariable=student_var, values=labels,
                 state="readonly", width=42
                 ).pack(side="left", padx=(4, 4))

    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)

    def render() -> None:
        for w in holder.winfo_children():
            w.destroy()
        sid = by_label.get(student_var.get())
        if not sid:
            ttk.Label(holder, text="Pick a student.",
                      foreground="#a33").pack(anchor="w")
            return
        rows = data.applications_for_student(sid)
        student = student_data.get_student(sid)
        ttk.Label(
            holder,
            text=f"{student.student_id}  {student.full_name}"
                 if student else f"{sid} (deleted)",
            font=("", 12, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        if not rows:
            ttk.Label(holder, text="(no applications)",
                      foreground="#555").pack(anchor="w")
            return

        cols = ("application_id", "employer", "title", "level",
                "sector", "status", "deadline", "interview", "salary")
        headings = {
            "application_id": ("#",         50),
            "employer":       ("Employer", 160),
            "title":          ("Title",    220),
            "level":          ("L",         40),
            "sector":         ("Sector",   180),
            "status":         ("Status",   110),
            "deadline":       ("Deadline",  90),
            "interview":      ("Interview", 90),
            "salary":         ("Salary",    80),
        }
        tree = ttk.Treeview(holder, columns=cols,
                            show="headings", height=12)
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        for a in rows:
            tree.insert("", "end", iid=str(a.application_id), values=(
                a.application_id, a.employer, a.apprenticeship_name,
                a.level if a.level else "—",
                a.sector or "—",
                a.status, a.deadline or "—",
                a.interview_date or "—",
                f"£{a.salary:,.2f}" if a.salary is not None else "—",
            ))
        tree.bind("<Double-1>", lambda _e: (
            tree.selection() and
            open_editor(gui, application_id=int(tree.selection()[0]))
        ))

        actions = ttk.Frame(parent)
        actions.pack(anchor="w", pady=(8, 0))
        ttk.Button(actions, text="Open in editor",
                   command=lambda: (tree.selection() and
                                    open_editor(gui, application_id=int(
                                        tree.selection()[0])))
                   ).pack(side="left", padx=(0, 6))
        gui.status_var.set(f"Apprenticeships for {sid}: {len(rows)} row(s)")

    ttk.Button(bar, text="Show", command=render
               ).pack(side="left", padx=(8, 0))
    if labels:
        render()
    else:
        ttk.Label(holder, text="No students yet.",
                  foreground="#a33").pack(anchor="w")


# ─── Summary tab ────────────────────────────────────────────────────

def _build_summary_tab(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))
    iv_var = tk.StringVar(value="30")
    dl_var = tk.StringVar(value="14")
    ttk.Label(bar, text="Interview window (days):").pack(side="left")
    ttk.Entry(bar, textvariable=iv_var, width=5
              ).pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="Deadline window (days):").pack(side="left")
    ttk.Entry(bar, textvariable=dl_var, width=5
              ).pack(side="left", padx=(4, 12))

    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)

    def render() -> None:
        for w in holder.winfo_children():
            w.destroy()
        try:
            iv = int(iv_var.get())
            dl = int(dl_var.get())
        except ValueError:
            ttk.Label(holder, text="Windows must be numbers.",
                      foreground="#a33").pack(anchor="w")
            return
        try:
            summ = data.summary(
                interview_window_days=iv, deadline_window_days=dl)
        except Exception as e:
            logger.exception("summary failed")
            ttk.Label(holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        ttk.Label(
            holder,
            text=f"Applications: {summ.total}  ·  "
                 f"Active: {summ.active}  ·  "
                 f"Accepted: {summ.accepted}",
            font=("", 12, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        ttk.Label(holder, text="By status:",
                  font=("", 10, "bold")).pack(anchor="w", pady=(8, 2))
        for st in STATUSES:
            n = summ.by_status.get(st, 0)
            ttk.Label(holder, text=f"   {st:<14} : {n}",
                      foreground="#444").pack(anchor="w")

        if summ.by_sector:
            ttk.Label(holder, text="By sector:",
                      font=("", 10, "bold")).pack(anchor="w", pady=(8, 2))
            for sector, n in sorted(summ.by_sector.items(),
                                     key=lambda x: -x[1]):
                ttk.Label(holder, text=f"   {sector[:36]:<36} : {n}",
                          foreground="#444").pack(anchor="w")

        if summ.by_level:
            ttk.Label(holder, text="By level:",
                      font=("", 10, "bold")).pack(anchor="w", pady=(8, 2))
            for level in sorted(summ.by_level.keys()):
                ttk.Label(holder,
                          text=f"   Level {level:<8} : {summ.by_level[level]}",
                          foreground="#444").pack(anchor="w")

        ttk.Label(holder, text="Alerts:",
                  font=("", 10, "bold")).pack(anchor="w", pady=(8, 2))
        ttk.Label(holder,
                  text=f"   Upcoming interviews ({iv}d): "
                       f"{summ.upcoming_interviews}",
                  foreground=("#a33" if summ.upcoming_interviews else "#444")
                  ).pack(anchor="w")
        ttk.Label(holder,
                  text=f"   Upcoming deadlines  ({dl}d, not yet applied): "
                       f"{summ.upcoming_deadlines}",
                  foreground=("#a33" if summ.upcoming_deadlines else "#444")
                  ).pack(anchor="w")
        gui.status_var.set("Apprenticeship summary loaded")

    ttk.Button(bar, text="Show", command=render
               ).pack(side="left", padx=(8, 0))
    render()
