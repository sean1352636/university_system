"""GUI panels for Sixth Form Student CRUD.

Rendered into ``SixthFormMainGUI.content_frame``. Each public function
takes the main-GUI instance so it can access ``content_frame``,
``status_var``, and the navigation helpers.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.students.students import students as data
from education_system.sixthform_system.modules.domain.academics.subjects import subjects as subjects_data
from education_system.sixthform_system.modules.domain.students.students.students import (
    A_LEVEL_SUBJECTS,
    Student,
    ValidationError,
    generate_sixthform_email,
)


def _active_subjects() -> list[str]:
    """Live list of subjects students can choose from. Falls back to the
    seed list if the subjects module hasn't initialised yet."""
    try:
        names = subjects_data.get_active_names()
        return names or list(A_LEVEL_SUBJECTS)
    except Exception:
        logger.exception("Falling back to seed subject list")
        return list(A_LEVEL_SUBJECTS)

logger = logging.getLogger(__name__)


# ── Internal helpers ────────────────────────────────────────────────

def _clear(gui) -> ttk.Frame:
    for w in gui.content_frame.winfo_children():
        w.destroy()
    return gui.content_frame


def _heading(parent, text: str) -> None:
    ttk.Label(parent, text=text, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))


# ── Add / Edit form ─────────────────────────────────────────────────

def _student_form(
    gui,
    *,
    title: str,
    existing: Student | None,
    on_save: Callable[[dict[str, Any]], Student],
    after_save_message: Callable[[Student], str],
) -> None:
    frame = _clear(gui)
    _heading(frame, title)

    vars_: dict[str, tk.StringVar] = {
        k: tk.StringVar() for k in (
            "first_name", "middle_name", "last_name",
            "phone", "personal_email",
            "emergency_contact_name", "emergency_contact_phone",
            "emergency_contact_relation",
            "subject_1", "subject_2", "subject_3",
        )
    }
    if existing is not None:
        vars_["first_name"].set(existing.first_name)
        vars_["middle_name"].set(existing.middle_name or "")
        vars_["last_name"].set(existing.last_name)
        vars_["phone"].set(existing.phone or "")
        vars_["emergency_contact_name"].set(existing.emergency_contact_name or "")
        vars_["emergency_contact_phone"].set(existing.emergency_contact_phone or "")
        vars_["emergency_contact_relation"].set(existing.emergency_contact_relation or "")
        vars_["subject_1"].set(existing.subject_1 or "")
        vars_["subject_2"].set(existing.subject_2 or "")
        vars_["subject_3"].set(existing.subject_3 or "")

    form = ttk.Frame(frame, padding=(0, 4))
    form.pack(anchor="w", fill="x")
    for col in range(2):
        form.columnconfigure(col, weight=0)
    form.columnconfigure(1, weight=1, minsize=320)

    def row(idx: int, label: str, widget: tk.Widget) -> None:
        ttk.Label(form, text=label).grid(row=idx, column=0, sticky="e", padx=(0, 8), pady=4)
        widget.grid(row=idx, column=1, sticky="ew", pady=4)

    def entry(var: tk.StringVar, *, show: str | None = None) -> ttk.Entry:
        return ttk.Entry(form, textvariable=var, show=show or "")

    subject_choices = _active_subjects()

    def subject_combo(var: tk.StringVar) -> ttk.Combobox:
        return ttk.Combobox(
            form, textvariable=var, values=subject_choices,
            state="readonly", width=30,
        )

    # Identity section
    ttk.Label(form, text="Identity", font=("", 11, "bold")).grid(
        row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
    row(1, "First name *", entry(vars_["first_name"]))
    row(2, "Middle name", entry(vars_["middle_name"]))
    row(3, "Last name *", entry(vars_["last_name"]))

    # Contact
    ttk.Separator(form, orient="horizontal").grid(
        row=4, column=0, columnspan=2, sticky="ew", pady=(10, 4))
    ttk.Label(form, text="Contact", font=("", 11, "bold")).grid(
        row=5, column=0, columnspan=2, sticky="w", pady=(0, 4))
    row(6, "Phone number", entry(vars_["phone"]))

    # Sixth-form email (auto-generated, read-only)
    sf_email_var = tk.StringVar(
        value=existing.email if existing else "(auto-generated on save)")
    row(7, "Sixth-form email", ttk.Entry(
        form, textvariable=sf_email_var, state="readonly", foreground="#555"))

    # Emergency contact
    ttk.Separator(form, orient="horizontal").grid(
        row=8, column=0, columnspan=2, sticky="ew", pady=(10, 4))
    ttk.Label(form, text="Emergency Contact", font=("", 11, "bold")).grid(
        row=9, column=0, columnspan=2, sticky="w", pady=(0, 4))
    row(10, "Name", entry(vars_["emergency_contact_name"]))
    row(11, "Phone number", entry(vars_["emergency_contact_phone"]))
    row(12, "Relation", entry(vars_["emergency_contact_relation"]))

    # A-Levels
    ttk.Separator(form, orient="horizontal").grid(
        row=13, column=0, columnspan=2, sticky="ew", pady=(10, 4))
    ttk.Label(form, text="A-Level Subjects (pick three)", font=("", 11, "bold")).grid(
        row=14, column=0, columnspan=2, sticky="w", pady=(0, 4))
    row(15, "Subject 1 *", subject_combo(vars_["subject_1"]))
    row(16, "Subject 2 *", subject_combo(vars_["subject_2"]))
    row(17, "Subject 3 *", subject_combo(vars_["subject_3"]))

    # ── Buttons ──
    button_row = ttk.Frame(frame)
    button_row.pack(anchor="w", pady=(12, 0))

    def submit() -> None:
        payload = {k: v.get() for k, v in vars_.items()}
        try:
            saved = on_save(payload)
        except ValidationError as e:
            logger.warning("Student form rejected: %s", e)
            messagebox.showerror("Cannot save", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("Unexpected error saving student form")
            messagebox.showerror("Error", f"Unexpected error: {e}", parent=gui.root)
            return
        logger.info("GUI saved student %s via %s", saved.student_id, title)
        messagebox.showinfo("Saved", after_save_message(saved), parent=gui.root)
        gui.status_var.set(f"Saved student {saved.student_id}")
        open_directory(gui)

    ttk.Button(button_row, text="Save", command=submit).pack(side="left", padx=(0, 8))
    ttk.Button(
        button_row, text="Cancel", command=lambda: open_directory(gui)
    ).pack(side="left")


def open_add_student(gui) -> None:
    def on_save(payload: dict[str, Any]) -> Student:
        return data.create_student(payload)

    def msg(s: Student) -> str:
        password = data._derive_password(s.first_name)
        return (
            f"Created student:\n\n"
            f"  ID:       {s.student_id}\n"
            f"  Name:     {s.full_name}\n"
            f"  Email:    {s.email}\n\n"
            f"Login created in the shared auth database:\n"
            f"  Username: {s.student_id}\n"
            f"  Password: {password}"
        )

    _student_form(
        gui, title="Add Student", existing=None,
        on_save=on_save, after_save_message=msg,
    )
    gui.status_var.set("Adding new student")


def open_edit_student(gui, student_id: str) -> None:
    student = data.get_student(student_id)
    if student is None:
        messagebox.showerror("Not found", f"No student with id {student_id}",
                             parent=gui.root)
        return

    def on_save(payload: dict[str, Any]) -> Student:
        return data.update_student(student_id, payload)

    def msg(s: Student) -> str:
        return f"Updated student {s.student_id} ({s.full_name})."

    _student_form(
        gui, title=f"Edit Student — {student.student_id}",
        existing=student, on_save=on_save, after_save_message=msg,
    )
    gui.status_var.set(f"Editing {student_id}")


# ── Directory (list + actions) ──────────────────────────────────────

def _build_directory_table(
    gui,
    parent: ttk.Frame,
    rows: list[Student],
    on_view: Callable[[str], None],
    on_edit: Callable[[str], None],
    on_delete: Callable[[str], None],
) -> None:
    cols = ("student_id", "name", "email", "phone", "subjects")
    headings = {
        "student_id": ("Student ID", 110),
        "name":       ("Name", 220),
        "email":      ("Sixth-form Email", 240),
        "phone":      ("Phone", 130),
        "subjects":   ("A-Levels", 340),
    }
    table_frame = ttk.Frame(parent)
    table_frame.pack(fill="both", expand=True, pady=(8, 8))

    tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=14)
    for col in cols:
        text, width = headings[col]
        tree.heading(col, text=text)
        tree.column(col, width=width, anchor="w")
    vs = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vs.set)
    tree.pack(side="left", fill="both", expand=True)
    vs.pack(side="right", fill="y")

    for s in rows:
        tree.insert("", "end", iid=s.student_id, values=(
            s.student_id, s.full_name, s.email, s.phone or "—",
            ", ".join(s.subjects) or "—",
        ))

    def _selected() -> str | None:
        sel = tree.selection()
        return sel[0] if sel else None

    actions = ttk.Frame(parent)
    actions.pack(anchor="w", pady=(0, 4))

    def _require_selection() -> str | None:
        sid = _selected()
        if sid is None:
            messagebox.showinfo(
                "No selection", "Select a student first.", parent=gui.root)
        return sid

    ttk.Button(
        actions, text="View",
        command=lambda: (_require_selection() and on_view(_selected())),
    ).pack(side="left", padx=(0, 6))
    ttk.Button(
        actions, text="Edit",
        command=lambda: (_require_selection() and on_edit(_selected())),
    ).pack(side="left", padx=(0, 6))
    ttk.Button(
        actions, text="Delete",
        command=lambda: (_require_selection() and on_delete(_selected())),
    ).pack(side="left", padx=(0, 6))
    ttk.Button(
        actions, text="Add New",
        command=lambda: open_add_student(gui),
    ).pack(side="left", padx=(12, 6))
    ttk.Button(
        actions, text="Refresh",
        command=lambda: open_directory(gui),
    ).pack(side="left")

    tree.bind("<Double-1>", lambda _e: (_selected() and on_view(_selected())))


def open_directory(gui) -> None:
    frame = _clear(gui)
    _heading(frame, "Student Directory")

    rows = data.list_students()
    ttk.Label(
        frame,
        text=f"{len(rows)} student(s) on roll." if rows else
             "No students yet — click 'Add New' to enrol one.",
        foreground="#555",
    ).pack(anchor="w")

    _build_directory_table(
        gui, frame, rows,
        on_view=lambda sid: open_profile(gui, sid),
        on_edit=lambda sid: open_edit_student(gui, sid),
        on_delete=lambda sid: _delete_with_confirm(gui, sid),
    )
    gui.status_var.set(f"Directory: {len(rows)} student(s)")


def open_search(gui) -> None:
    frame = _clear(gui)
    _heading(frame, "Search Students")

    query_var = tk.StringVar()
    bar = ttk.Frame(frame)
    bar.pack(anchor="w", fill="x", pady=(0, 8))
    ttk.Label(bar, text="Search:").pack(side="left", padx=(0, 6))
    entry = ttk.Entry(bar, textvariable=query_var, width=40)
    entry.pack(side="left", padx=(0, 6))
    entry.focus_set()
    ttk.Label(
        bar,
        text="(matches student ID, name, or sixth-form email)",
        foreground="#777",
    ).pack(side="left")

    results_frame = ttk.Frame(frame)
    results_frame.pack(fill="both", expand=True)

    def render(rows: list[Student]) -> None:
        for w in results_frame.winfo_children():
            w.destroy()
        ttk.Label(
            results_frame,
            text=f"{len(rows)} match(es).",
            foreground="#555",
        ).pack(anchor="w")
        _build_directory_table(
            gui, results_frame, rows,
            on_view=lambda sid: open_profile(gui, sid),
            on_edit=lambda sid: open_edit_student(gui, sid),
            on_delete=lambda sid: _delete_with_confirm(gui, sid),
        )

    def run_search(_evt: object = None) -> None:
        q = query_var.get().strip()
        rows = data.search_students(q) if q else data.list_students()
        render(rows)
        gui.status_var.set(f"Search: '{q}' → {len(rows)} match(es)")

    ttk.Button(bar, text="Search", command=run_search).pack(side="left", padx=(8, 0))
    entry.bind("<Return>", run_search)
    render(data.list_students())


# ── Profile (read-only detail) ──────────────────────────────────────

def open_profile(gui, student_id: str | None = None) -> None:
    frame = _clear(gui)
    _heading(frame, "Student Profile")

    if student_id is None:
        ttk.Label(
            frame,
            text="Open a profile from the Student Directory or via Search.",
            foreground="#555",
        ).pack(anchor="w")
        return

    student = data.get_student(student_id)
    if student is None:
        ttk.Label(
            frame, text=f"No student found with id {student_id}",
            foreground="#a33",
        ).pack(anchor="w")
        return

    grid = ttk.Frame(frame)
    grid.pack(anchor="w", pady=(8, 0))

    def field(row: int, label: str, value: str) -> None:
        ttk.Label(grid, text=label + ":", foreground="#555",
                  width=22, anchor="e").grid(row=row, column=0, sticky="e", pady=2, padx=(0, 8))
        ttk.Label(grid, text=value or "—").grid(row=row, column=1, sticky="w", pady=2)

    field(0, "Student ID", student.student_id)
    field(1, "Name", student.full_name)
    field(2, "Sixth-form email", student.email)
    field(3, "Phone", student.phone or "—")

    ttk.Separator(grid, orient="horizontal").grid(
        row=4, column=0, columnspan=2, sticky="ew", pady=(10, 6))
    ttk.Label(grid, text="Emergency Contact",
              font=("", 11, "bold")).grid(row=5, column=0, columnspan=2, sticky="w", pady=(0, 4))
    field(6, "Name", student.emergency_contact_name or "—")
    field(7, "Phone", student.emergency_contact_phone or "—")
    field(8, "Relation", student.emergency_contact_relation or "—")

    ttk.Separator(grid, orient="horizontal").grid(
        row=9, column=0, columnspan=2, sticky="ew", pady=(10, 6))
    ttk.Label(grid, text="A-Level Subjects",
              font=("", 11, "bold")).grid(row=10, column=0, columnspan=2, sticky="w", pady=(0, 4))
    for i, subj in enumerate(student.subjects, start=11):
        field(i, f"Subject {i - 10}", subj)

    actions = ttk.Frame(frame)
    actions.pack(anchor="w", pady=(12, 0))
    ttk.Button(actions, text="Edit",
               command=lambda: open_edit_student(gui, student.student_id)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Delete",
               command=lambda: _delete_with_confirm(gui, student.student_id)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Back to Directory",
               command=lambda: open_directory(gui)).pack(side="left")
    gui.status_var.set(f"Viewing {student.student_id}")


def _delete_with_confirm(gui, student_id: str) -> None:
    student = data.get_student(student_id)
    if student is None:
        logger.warning("GUI delete: no student with id %s", student_id)
        messagebox.showerror(
            "Not found", f"No student with id {student_id}", parent=gui.root)
        return
    ok = messagebox.askyesno(
        "Delete student",
        f"Permanently delete {student.full_name} ({student.student_id})?",
        parent=gui.root,
    )
    if not ok:
        logger.debug("GUI delete cancelled for %s", student_id)
        return
    try:
        deleted = data.delete_student(student_id)
    except Exception as e:
        logger.exception("GUI delete failed for %s", student_id)
        messagebox.showerror("Error", f"Could not delete student: {e}",
                             parent=gui.root)
        return
    if deleted:
        gui.status_var.set(f"Deleted {student_id}")
        open_directory(gui)
    else:
        messagebox.showerror(
            "Error", "Could not delete student.", parent=gui.root)
