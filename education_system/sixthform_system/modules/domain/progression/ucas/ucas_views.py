"""GUI panels for Sixth Form UCAS Applications.

Three tabs:

* Directory  — filterable list of applications, one row per student.
* Application — detail view: app metadata + up to 5 choices, with
  inline add / edit / delete buttons for choices.
* Summary    — cycle stats (status / decision counts).
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date
from tkinter import messagebox, ttk
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.students.students import students
from education_system.sixthform_system.modules.domain.students.students import students as student_data
from education_system.sixthform_system.modules.domain.progression.ucas import ucas as data
from education_system.sixthform_system.modules.domain.progression.ucas.ucas import (
    APP_STATUSES,
    Application,
    Choice,
    DECISION_STATUSES,
    DEFAULT_APP_STATUS,
    DEFAULT_DECISION_STATUS,
    FINAL_DECISIONS,
    MAX_CHOICES,
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


def _default_cycle_year() -> int:
    today = _date.today()
    # UCAS cycle is the *entry* year; applications open Sept of the
    # previous year. Default to next year's entry from Sept onwards.
    return today.year + 1 if today.month >= 9 else today.year


# ── Top-level tabbed view ───────────────────────────────────────────

def open_directory(gui) -> None:
    frame = _clear(gui)
    _heading(frame, "UCAS Applications")

    nb = ttk.Notebook(frame)
    nb.pack(fill="both", expand=True)

    dir_tab = ttk.Frame(nb, padding=8)
    detail_tab = ttk.Frame(nb, padding=8)
    summary_tab = ttk.Frame(nb, padding=8)
    nb.add(dir_tab,     text="Directory")
    nb.add(detail_tab,  text="Application")
    nb.add(summary_tab, text="Summary")

    _build_directory_tab(gui, dir_tab)
    _build_detail_tab(gui, detail_tab)
    _build_summary_tab(gui, summary_tab)


# ─── Directory tab ──────────────────────────────────────────────────

def _build_directory_tab(gui, parent: ttk.Frame) -> None:
    filt = ttk.Frame(parent)
    filt.pack(anchor="w", fill="x", pady=(0, 8))

    sid_var = tk.StringVar()
    cycle_var = tk.StringVar()
    status_var = tk.StringVar()

    ttk.Label(filt, text="Student ID:").pack(side="left")
    ttk.Entry(filt, textvariable=sid_var, width=12
              ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Cycle year:").pack(side="left")
    ttk.Entry(filt, textvariable=cycle_var, width=6
              ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Status:").pack(side="left")
    ttk.Combobox(filt, textvariable=status_var,
                 values=["", *APP_STATUSES], state="readonly", width=12
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
            yr = int(cycle_var.get()) if cycle_var.get().strip() else None
        except ValueError:
            messagebox.showerror("Bad filter",
                                 "Cycle year must be a number.",
                                 parent=gui.root)
            return
        try:
            rows = data.list_applications_with_detail(
                student_id=sid_var.get().strip() or None,
                cycle_year=yr,
                status=status_var.get().strip() or None,
            )
        except ValidationError as e:
            ttk.Label(table_holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return

        cols = ("application_id", "student", "name", "cycle",
                "status", "ucas_id", "submitted", "choices", "final")
        headings = {
            "application_id": ("#",        50),
            "student":        ("Student", 100),
            "name":            ("Name",   200),
            "cycle":          ("Cycle",    60),
            "status":         ("Status",   90),
            "ucas_id":        ("UCAS ID",  90),
            "submitted":      ("Submitted", 100),
            "choices":        ("Choices",   60),
            "final":          ("F / I",     80),
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

        for row in rows:
            a = row.application
            final = []
            if row.has_firm:
                final.append("F")
            if row.has_insurance:
                final.append("I")
            tree.insert("", "end", iid=str(a.application_id), values=(
                a.application_id, a.student_id, row.student_name,
                a.cycle_year, a.status,
                a.ucas_id or "—",
                a.submitted_at or "—",
                row.n_choices,
                "/".join(final) or "—",
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

        def _open() -> None:
            aid = _require()
            if aid is None:
                return
            open_application(gui, aid)

        def _delete() -> None:
            aid = _require()
            if aid is None:
                return
            a = data.get_application(aid)
            if a is None:
                return
            if not messagebox.askyesno(
                "Delete application",
                f"Delete application #{aid} ({a.student_id}, "
                f"cycle {a.cycle_year})? All {len(data.list_choices(aid))} "
                "choice(s) will go with it.",
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

        ttk.Button(actions_holder, text="Open",
                   command=_open).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Delete",
                   command=_delete).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="New",
                   command=lambda: open_new_application(gui)
                   ).pack(side="left", padx=(12, 6))
        ttk.Button(actions_holder, text="Refresh",
                   command=refresh).pack(side="left")
        tree.bind("<Double-1>", lambda _e: _open())
        gui.status_var.set(f"UCAS apps: {len(rows)} match(es)")

    ttk.Button(filt, text="Apply", command=refresh
               ).pack(side="left", padx=(8, 0))
    ttk.Button(filt, text="Clear",
               command=lambda: (sid_var.set(""), cycle_var.set(""),
                                status_var.set(""), refresh())
               ).pack(side="left", padx=(4, 0))
    refresh()


def open_new_application(gui) -> None:
    students = student_data.list_students()
    if not students:
        messagebox.showinfo("No students",
                            "Add a student first.", parent=gui.root)
        return

    win = tk.Toplevel(gui.root)
    win.title("New UCAS Application")
    win.transient(gui.root)
    win.after_idle(win.grab_set)
    frm = ttk.Frame(win, padding=12)
    frm.grid()

    student_labels = [f"{s.student_id} — {s.full_name}" for s in students]
    student_by_label = {f"{s.student_id} — {s.full_name}": s.student_id
                        for s in students}
    student_var = tk.StringVar(value=student_labels[0])
    cycle_var = tk.StringVar(value=str(_default_cycle_year()))
    ucas_var = tk.StringVar()
    status_var = tk.StringVar(value=DEFAULT_APP_STATUS)
    submitted_var = tk.StringVar()
    notes_var = tk.StringVar()

    def row(idx, label, w):
        ttk.Label(frm, text=label).grid(row=idx, column=0, sticky="e",
                                         padx=(0, 6), pady=2)
        w.grid(row=idx, column=1, sticky="w", pady=2)

    row(0, "Student:", ttk.Combobox(frm, textvariable=student_var,
                                     values=student_labels,
                                     state="readonly", width=42))
    row(1, "Cycle year:", ttk.Entry(frm, textvariable=cycle_var, width=8))
    row(2, "UCAS personal ID (10 digits):",
        ttk.Entry(frm, textvariable=ucas_var, width=16))
    row(3, "Status:", ttk.Combobox(frm, textvariable=status_var,
                                    values=list(APP_STATUSES),
                                    state="readonly", width=14))
    row(4, "Submitted at (YYYY-MM-DD):",
        ttk.Entry(frm, textvariable=submitted_var, width=14))
    row(5, "Notes:", ttk.Entry(frm, textvariable=notes_var, width=42))

    def save() -> None:
        sid = student_by_label.get(student_var.get())
        if not sid:
            messagebox.showerror("Cannot save",
                                 "Pick a student.", parent=win)
            return
        try:
            a = data.create_application({
                "student_id":   sid,
                "cycle_year":   cycle_var.get(),
                "ucas_id":      ucas_var.get(),
                "status":       status_var.get(),
                "submitted_at": submitted_var.get(),
                "notes":        notes_var.get(),
            })
        except ValidationError as e:
            messagebox.showerror("Cannot save", str(e), parent=win)
            return
        except Exception as e:
            logger.exception("create_application crashed")
            messagebox.showerror("Error", f"Unexpected: {e}", parent=win)
            return
        win.destroy()
        open_application(gui, a.application_id)

    bar = ttk.Frame(frm)
    bar.grid(row=6, column=0, columnspan=2, pady=(10, 0), sticky="e")
    ttk.Button(bar, text="Save", command=save).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left")


# ─── Application detail tab + standalone view ──────────────────────

def _build_detail_tab(gui, parent: ttk.Frame) -> None:
    apps = data.list_applications_with_detail()
    labels = [
        f"#{r.application.application_id}  {r.application.student_id}  "
        f"{r.student_name}  (cycle {r.application.cycle_year}, "
        f"{r.application.status})"
        for r in apps
    ]
    by_label = {lbl: r.application.application_id
                for lbl, r in zip(labels, apps)}

    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))
    app_var = tk.StringVar(value=labels[0] if labels else "")
    ttk.Label(bar, text="Application:").pack(side="left")
    ttk.Combobox(bar, textvariable=app_var, values=labels,
                 state="readonly", width=64
                 ).pack(side="left", padx=(4, 4))

    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)

    def render() -> None:
        for w in holder.winfo_children():
            w.destroy()
        aid = by_label.get(app_var.get())
        if aid is None:
            ttk.Label(holder, text="Pick an application.",
                      foreground="#a33").pack(anchor="w")
            return
        _render_application_detail(gui, holder, aid, on_changed=render)

    ttk.Button(bar, text="Show", command=render
               ).pack(side="left", padx=(8, 0))
    if labels:
        render()
    else:
        ttk.Label(holder, text="No applications yet.",
                  foreground="#a33").pack(anchor="w")


def open_application(gui, application_id: int) -> None:
    """Standalone view: full-page application detail."""
    frame = _clear(gui)
    _heading(frame, f"UCAS Application #{application_id}")
    holder = ttk.Frame(frame)
    holder.pack(fill="both", expand=True)
    _render_application_detail(gui, holder, application_id,
                               on_changed=lambda: open_application(
                                   gui, application_id))
    ttk.Button(frame, text="Back to UCAS Applications",
               command=lambda: open_directory(gui)
               ).pack(anchor="w", pady=(12, 0))


def _render_application_detail(gui, parent: ttk.Frame,
                               application_id: int,
                               *, on_changed: Callable[[], None]) -> None:
    a = data.get_application(application_id)
    if a is None:
        ttk.Label(parent, text="No such application.",
                  foreground="#a33").pack(anchor="w")
        return

    student = student_data.get_student(a.student_id)

    # Header — student + app metadata
    meta = ttk.Frame(parent)
    meta.pack(anchor="w", fill="x", pady=(0, 8))

    def field(row: int, label: str, value: str) -> None:
        ttk.Label(meta, text=label + ":", foreground="#555",
                  width=22, anchor="e").grid(row=row, column=0, sticky="e",
                                              pady=2, padx=(0, 8))
        ttk.Label(meta, text=value or "—").grid(
            row=row, column=1, sticky="w", pady=2)

    field(0, "Student",
          f"{a.student_id} — {student.full_name if student else '(deleted)'}")
    field(1, "Cycle year", str(a.cycle_year))
    field(2, "UCAS personal ID", a.ucas_id or "—")
    field(3, "Status", a.status)
    field(4, "Submitted", a.submitted_at or "—")
    field(5, "Created", a.created_at)
    field(6, "Last updated", a.updated_at)
    if a.personal_statement:
        ttk.Separator(meta, orient="horizontal").grid(
            row=7, column=0, columnspan=2, sticky="ew", pady=(10, 6))
        ttk.Label(meta, text="Personal statement:", foreground="#555",
                  width=22, anchor="ne").grid(row=8, column=0, sticky="ne",
                                               padx=(0, 8))
        ttk.Label(meta, text=a.personal_statement,
                  wraplength=520, justify="left").grid(
            row=8, column=1, sticky="w")
    if a.notes:
        ttk.Label(meta, text="Notes:", foreground="#555",
                  width=22, anchor="ne").grid(row=9, column=0, sticky="ne",
                                               padx=(0, 8), pady=(6, 0))
        ttk.Label(meta, text=a.notes, wraplength=520,
                  justify="left").grid(row=9, column=1, sticky="w",
                                       pady=(6, 0))

    app_actions = ttk.Frame(parent)
    app_actions.pack(anchor="w", pady=(0, 12))
    ttk.Button(app_actions, text="Edit application",
               command=lambda: _edit_application_dialog(
                   gui, a.application_id, on_saved=on_changed)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(app_actions, text="Edit personal statement",
               command=lambda: _edit_ps_dialog(
                   gui, a.application_id, on_saved=on_changed)
               ).pack(side="left", padx=(0, 6))

    # ── Choices section ──
    choices_section = ttk.LabelFrame(parent, text="Choices (max 5)",
                                      padding=8)
    choices_section.pack(fill="both", expand=True, pady=(8, 0))

    choices = data.list_choices(application_id)

    cols = ("choice_id", "slot", "university", "course_code",
            "course_name", "entry_year", "decision_status",
            "offer_terms", "final_decision")
    headings = {
        "choice_id":       ("#",        50),
        "slot":            ("Slot",     50),
        "university":      ("University", 180),
        "course_code":     ("Code",      80),
        "course_name":     ("Course",   180),
        "entry_year":      ("Year",     60),
        "decision_status": ("Status",  140),
        "offer_terms":     ("Terms",   140),
        "final_decision":  ("Final",   100),
    }
    tree = ttk.Treeview(choices_section, columns=cols,
                        show="headings", height=6)
    for col in cols:
        text, width = headings[col]
        tree.heading(col, text=text)
        tree.column(col, width=width, anchor="w")
    vs = ttk.Scrollbar(choices_section, orient="vertical",
                        command=tree.yview)
    tree.configure(yscrollcommand=vs.set)
    tree.pack(side="left", fill="both", expand=True)
    vs.pack(side="right", fill="y")

    for c in choices:
        tree.insert("", "end", iid=str(c.choice_id), values=(
            c.choice_id, c.choice_order, c.university,
            c.course_code or "—", c.course_name,
            c.entry_year if c.entry_year is not None else "—",
            c.decision_status,
            c.offer_terms or "—",
            c.final_decision or "—",
        ))

    def _selected() -> int | None:
        sel = tree.selection()
        return int(sel[0]) if sel else None

    choice_actions = ttk.Frame(parent)
    choice_actions.pack(anchor="w", pady=(8, 0))

    def _add() -> None:
        if len(data.list_choices(application_id)) >= MAX_CHOICES:
            messagebox.showinfo(
                "At capacity",
                f"This application already has {MAX_CHOICES} choices.",
                parent=gui.root,
            )
            return
        _edit_choice_dialog(gui, application_id, choice_id=None,
                            on_saved=on_changed)

    def _edit() -> None:
        cid = _selected()
        if cid is None:
            messagebox.showinfo("No selection",
                                "Pick a choice first.", parent=gui.root)
            return
        _edit_choice_dialog(gui, application_id, choice_id=cid,
                            on_saved=on_changed)

    def _delete() -> None:
        cid = _selected()
        if cid is None:
            messagebox.showinfo("No selection",
                                "Pick a choice first.", parent=gui.root)
            return
        c = data.get_choice(cid)
        if c is None:
            return
        if not messagebox.askyesno(
            "Delete choice",
            f"Delete slot {c.choice_order}: {c.university} — {c.course_name}?",
            parent=gui.root,
        ):
            return
        try:
            data.delete_choice(cid)
        except Exception as e:
            logger.exception("delete_choice crashed")
            messagebox.showerror("Error", f"Could not delete: {e}",
                                 parent=gui.root)
            return
        on_changed()

    ttk.Button(choice_actions, text="Add choice",
               command=_add).pack(side="left", padx=(0, 6))
    ttk.Button(choice_actions, text="Edit choice",
               command=_edit).pack(side="left", padx=(0, 6))
    ttk.Button(choice_actions, text="Delete choice",
               command=_delete).pack(side="left", padx=(0, 6))
    tree.bind("<Double-1>", lambda _e: _edit())

    gui.status_var.set(f"UCAS application #{application_id} loaded")


def _edit_application_dialog(gui, application_id: int, *, on_saved) -> None:
    a = data.get_application(application_id)
    if a is None:
        messagebox.showerror("Not found", f"No application #{application_id}",
                             parent=gui.root)
        return
    win = tk.Toplevel(gui.root)
    win.title(f"Edit application #{application_id}")
    win.transient(gui.root)
    win.after_idle(win.grab_set)
    frm = ttk.Frame(win, padding=12)
    frm.grid()
    ttk.Label(frm, text=f"Student: {a.student_id}",
              foreground="#555").grid(row=0, column=0, columnspan=2,
                                       sticky="w", pady=(0, 8))

    cycle_var = tk.StringVar(value=str(a.cycle_year))
    ucas_var = tk.StringVar(value=a.ucas_id or "")
    status_var = tk.StringVar(value=a.status)
    submitted_var = tk.StringVar(value=a.submitted_at or "")
    notes_var = tk.StringVar(value=a.notes or "")

    def row(idx, label, w):
        ttk.Label(frm, text=label).grid(row=idx, column=0, sticky="e",
                                         padx=(0, 6), pady=2)
        w.grid(row=idx, column=1, sticky="w", pady=2)

    row(1, "Cycle year:", ttk.Entry(frm, textvariable=cycle_var, width=8))
    row(2, "UCAS ID:", ttk.Entry(frm, textvariable=ucas_var, width=16))
    row(3, "Status:", ttk.Combobox(frm, textvariable=status_var,
                                    values=list(APP_STATUSES),
                                    state="readonly", width=14))
    row(4, "Submitted:", ttk.Entry(frm, textvariable=submitted_var,
                                    width=14))
    row(5, "Notes:", ttk.Entry(frm, textvariable=notes_var, width=42))

    def save() -> None:
        try:
            data.update_application(application_id, {
                "cycle_year":   cycle_var.get(),
                "ucas_id":      ucas_var.get(),
                "status":       status_var.get(),
                "submitted_at": submitted_var.get(),
                "notes":        notes_var.get(),
            })
        except ValidationError as e:
            messagebox.showerror("Cannot save", str(e), parent=win)
            return
        except Exception as e:
            logger.exception("update_application crashed")
            messagebox.showerror("Error", f"Unexpected: {e}", parent=win)
            return
        win.destroy()
        on_saved()

    bar = ttk.Frame(frm)
    bar.grid(row=6, column=0, columnspan=2, pady=(10, 0), sticky="e")
    ttk.Button(bar, text="Save", command=save).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left")


def _edit_ps_dialog(gui, application_id: int, *, on_saved) -> None:
    a = data.get_application(application_id)
    if a is None:
        return
    win = tk.Toplevel(gui.root)
    win.title(f"Edit personal statement — application #{application_id}")
    win.transient(gui.root)
    win.after_idle(win.grab_set)
    frm = ttk.Frame(win, padding=12)
    frm.grid()
    ttk.Label(frm, text="Personal statement:",
              foreground="#555").grid(row=0, column=0, sticky="w",
                                       pady=(0, 4))
    text = tk.Text(frm, width=70, height=16, wrap="word")
    text.grid(row=1, column=0, sticky="nsew")
    if a.personal_statement:
        text.insert("1.0", a.personal_statement)

    def save() -> None:
        try:
            data.update_application(application_id, {
                "personal_statement": text.get("1.0", "end").strip(),
            })
        except ValidationError as e:
            messagebox.showerror("Cannot save", str(e), parent=win)
            return
        except Exception as e:
            logger.exception("update_application (PS) crashed")
            messagebox.showerror("Error", f"Unexpected: {e}", parent=win)
            return
        win.destroy()
        on_saved()

    bar = ttk.Frame(frm)
    bar.grid(row=2, column=0, pady=(10, 0), sticky="e")
    ttk.Button(bar, text="Save", command=save).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left")


def _edit_choice_dialog(gui, application_id: int, *,
                         choice_id: int | None,
                         on_saved) -> None:
    existing = data.get_choice(choice_id) if choice_id else None

    win = tk.Toplevel(gui.root)
    win.title("Edit choice" if existing else "Add choice")
    win.transient(gui.root)
    win.after_idle(win.grab_set)
    frm = ttk.Frame(win, padding=12)
    frm.grid()

    # Pre-fill or sensible defaults
    used_slots = {c.choice_order for c in data.list_choices(application_id)
                  if not existing or c.choice_id != existing.choice_id}
    available = [n for n in range(1, MAX_CHOICES + 1) if n not in used_slots]
    if existing:
        # Existing slot stays at the top of the picker
        available = [existing.choice_order] + [
            n for n in available if n != existing.choice_order]

    slot_var = tk.StringVar(
        value=str(existing.choice_order) if existing
              else (str(available[0]) if available else "1"))
    uni_var = tk.StringVar(value=existing.university if existing else "")
    code_var = tk.StringVar(
        value=(existing.course_code or "") if existing else "")
    course_var = tk.StringVar(
        value=existing.course_name if existing else "")
    year_var = tk.StringVar(
        value=(str(existing.entry_year) if existing and existing.entry_year
               else str(_default_cycle_year())))
    decision_var = tk.StringVar(
        value=existing.decision_status if existing else DEFAULT_DECISION_STATUS)
    terms_var = tk.StringVar(
        value=(existing.offer_terms or "") if existing else "")
    final_var = tk.StringVar(
        value=(existing.final_decision or "") if existing else "")
    notes_var = tk.StringVar(
        value=(existing.notes or "") if existing else "")

    def row(idx, label, w):
        ttk.Label(frm, text=label).grid(row=idx, column=0, sticky="e",
                                         padx=(0, 6), pady=2)
        w.grid(row=idx, column=1, sticky="w", pady=2)

    row(0, "Slot:", ttk.Combobox(frm, textvariable=slot_var,
                                  values=[str(n) for n in available],
                                  state="readonly", width=4))
    row(1, "University:", ttk.Entry(frm, textvariable=uni_var, width=36))
    row(2, "Course code:", ttk.Entry(frm, textvariable=code_var, width=12))
    row(3, "Course name:", ttk.Entry(frm, textvariable=course_var, width=36))
    row(4, "Entry year:", ttk.Entry(frm, textvariable=year_var, width=8))
    row(5, "Decision status:", ttk.Combobox(
        frm, textvariable=decision_var, values=list(DECISION_STATUSES),
        state="readonly", width=24))
    row(6, "Offer terms:", ttk.Entry(frm, textvariable=terms_var, width=36))
    row(7, "Final decision:", ttk.Combobox(
        frm, textvariable=final_var, values=["", *FINAL_DECISIONS],
        state="readonly", width=14))
    row(8, "Notes:", ttk.Entry(frm, textvariable=notes_var, width=36))

    def save() -> None:
        # Pre-flight: catch empty required fields before they hit the
        # data layer. The data layer would reject these too — but with
        # a stack trace landing in the console because the wrapper
        # logger captures ValidationError as an exception.
        missing: list[str] = []
        if not uni_var.get().strip():
            missing.append("University")
        if not course_var.get().strip():
            missing.append("Course name")
        if missing:
            messagebox.showwarning(
                "Required fields",
                "Please fill in: " + ", ".join(missing),
                parent=win,
            )
            return

        payload = {
            "choice_order":    slot_var.get(),
            "university":      uni_var.get(),
            "course_code":     code_var.get(),
            "course_name":     course_var.get(),
            "entry_year":      year_var.get(),
            "decision_status": decision_var.get(),
            "offer_terms":     terms_var.get(),
            "final_decision":  final_var.get(),
            "notes":           notes_var.get(),
        }
        try:
            if existing:
                data.update_choice(existing.choice_id, payload)
            else:
                data.create_choice(application_id, payload)
        except ValidationError as e:
            messagebox.showerror("Cannot save", str(e), parent=win)
            return
        except Exception as e:
            logger.exception("save choice crashed")
            messagebox.showerror("Error", f"Unexpected: {e}", parent=win)
            return
        win.destroy()
        on_saved()

    bar = ttk.Frame(frm)
    bar.grid(row=9, column=0, columnspan=2, pady=(10, 0), sticky="e")
    ttk.Button(bar, text="Save", command=save).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left")


# ─── Summary tab ────────────────────────────────────────────────────

def _build_summary_tab(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))

    cycle_var = tk.StringVar(value=str(_default_cycle_year()))
    ttk.Label(bar, text="Cycle year (blank = all):").pack(side="left")
    ttk.Entry(bar, textvariable=cycle_var, width=6
              ).pack(side="left", padx=(4, 12))

    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)

    def render() -> None:
        for w in holder.winfo_children():
            w.destroy()
        try:
            yr = int(cycle_var.get()) if cycle_var.get().strip() else None
        except ValueError:
            ttk.Label(holder, text="Cycle year must be a number.",
                      foreground="#a33").pack(anchor="w")
            return
        summ = data.cycle_summary(yr)

        ttk.Label(
            holder,
            text=f"Applications: {summ.total_applications}  ·  "
                 f"Choices: {summ.total_choices}",
            font=("", 12, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        if not summ.total_applications:
            return

        ttk.Label(holder, text="Application status:",
                  font=("", 10, "bold")).pack(anchor="w", pady=(8, 2))
        for st in APP_STATUSES:
            n = summ.by_status.get(st, 0)
            ttk.Label(holder, text=f"   {st:<12} : {n}",
                      foreground="#444").pack(anchor="w")

        ttk.Label(holder, text="Choice decision status:",
                  font=("", 10, "bold")).pack(anchor="w", pady=(8, 2))
        for ds in DECISION_STATUSES:
            n = summ.by_decision_status.get(ds, 0)
            ttk.Label(holder, text=f"   {ds:<22} : {n}",
                      foreground="#444").pack(anchor="w")

        ttk.Label(holder, text="Final decisions:",
                  font=("", 10, "bold")).pack(anchor="w", pady=(8, 2))
        for fd in FINAL_DECISIONS:
            n = summ.by_final_decision.get(fd, 0)
            ttk.Label(holder, text=f"   {fd:<12} : {n}",
                      foreground="#444").pack(anchor="w")
        not_decided = summ.by_final_decision.get("", 0)
        if not_decided:
            ttk.Label(holder, text=f"   {'Not decided':<12} : {not_decided}",
                      foreground="#888").pack(anchor="w")
        gui.status_var.set("UCAS summary loaded")

    ttk.Button(bar, text="Show", command=render
               ).pack(side="left", padx=(8, 0))
    render()
