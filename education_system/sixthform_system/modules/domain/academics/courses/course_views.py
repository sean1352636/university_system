"""GUI panels for Sixth Form Course CRUD.

Same shape as the enrolment views: filterable directory + form + profile.
Subject is a readonly Combobox sourced from the same A_LEVEL_SUBJECTS
list students choose from, so the two areas stay consistent.
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.academics.courses import courses as data
from education_system.sixthform_system.modules.domain.academics.courses.courses import (
    Course,
    DEFAULT_MAX_STUDENTS,
    ValidationError,
    YEAR_GROUPS,
)
from education_system.sixthform_system.modules.domain.academics.subjects import subjects as subjects_data
from education_system.sixthform_system.modules.domain.students.students.students import A_LEVEL_SUBJECTS


def _active_subjects() -> list[str]:
    try:
        names = subjects_data.get_active_names()
        return names or list(A_LEVEL_SUBJECTS)
    except Exception:
        logger.exception("Falling back to seed subject list")
        return list(A_LEVEL_SUBJECTS)

logger = logging.getLogger(__name__)


def _clear(gui) -> ttk.Frame:
    for w in gui.content_frame.winfo_children():
        w.destroy()
    return gui.content_frame


def _heading(parent, text: str) -> None:
    ttk.Label(parent, text=text, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))


def _default_academic_year() -> str:
    today = date.today()
    start = today.year if today.month >= 8 else today.year - 1
    return f"{start}/{str(start + 1)[-2:]}"


# ── Add / Edit form ─────────────────────────────────────────────────

def _course_form(
    gui,
    *,
    title: str,
    existing: Course | None,
    on_save: Callable[[dict[str, Any]], Course],
) -> None:
    frame = _clear(gui)
    _heading(frame, title)

    is_edit = existing is not None

    form = ttk.Frame(frame, padding=(0, 4))
    form.pack(anchor="w", fill="x")
    form.columnconfigure(1, weight=1, minsize=320)

    # Note: `description_text` must be parented on the grid-managed `form`
    # to avoid mixing geometry managers inside the same parent.
    description_text = tk.Text(form, height=4, width=60)

    subject_choices = _active_subjects()
    code_var = tk.StringVar(value=existing.course_code if is_edit else "")
    subject_var = tk.StringVar(
        value=existing.subject if is_edit else (
            subject_choices[0] if subject_choices else ""))
    title_var = tk.StringVar(value=existing.title if is_edit else "")
    yg_var = tk.StringVar(
        value=str(existing.year_group) if is_edit else str(YEAR_GROUPS[0]))
    year_var = tk.StringVar(
        value=existing.academic_year if is_edit else _default_academic_year())
    teacher_var = tk.StringVar(value=(existing.teacher or "") if is_edit else "")
    room_var    = tk.StringVar(value=(existing.room or "") if is_edit else "")
    max_var = tk.StringVar(
        value=str(existing.max_students) if is_edit else str(DEFAULT_MAX_STUDENTS))

    def row(idx: int, label: str, widget: tk.Widget) -> None:
        ttk.Label(form, text=label).grid(
            row=idx, column=0, sticky="e", padx=(0, 8), pady=4)
        widget.grid(row=idx, column=1, sticky="ew", pady=4)

    row(0, "Course code *", ttk.Entry(form, textvariable=code_var))
    row(1, "Subject *", ttk.Combobox(
        form, textvariable=subject_var, values=subject_choices,
        state="readonly", width=32))
    row(2, "Title *", ttk.Entry(form, textvariable=title_var))
    row(3, "Year group *", ttk.Combobox(
        form, textvariable=yg_var, values=[str(y) for y in YEAR_GROUPS],
        state="readonly", width=8))
    row(4, "Academic year * (YYYY/YY)", ttk.Entry(form, textvariable=year_var))
    row(5, "Teacher", ttk.Entry(form, textvariable=teacher_var))
    row(6, "Room", ttk.Entry(form, textvariable=room_var))
    row(7, "Max students", ttk.Entry(form, textvariable=max_var, width=10))
    ttk.Label(form, text="Description").grid(
        row=8, column=0, sticky="ne", padx=(0, 8), pady=4)
    description_text.grid(row=8, column=1, sticky="ew", pady=4)
    if is_edit and existing.description:
        description_text.insert("1.0", existing.description)

    bar = ttk.Frame(frame)
    bar.pack(anchor="w", pady=(12, 0))

    def submit() -> None:
        payload = {
            "course_code":   code_var.get(),
            "subject":       subject_var.get(),
            "title":         title_var.get(),
            "year_group":    yg_var.get(),
            "academic_year": year_var.get(),
            "teacher":       teacher_var.get(),
            "room":          room_var.get(),
            "max_students":  max_var.get(),
            "description":   description_text.get("1.0", "end").strip(),
        }
        try:
            saved = on_save(payload)
        except ValidationError as e:
            logger.warning("Course form rejected: %s", e)
            messagebox.showerror("Cannot save", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("Unexpected error saving course form")
            messagebox.showerror("Error", f"Unexpected error: {e}",
                                 parent=gui.root)
            return
        logger.info("GUI saved course #%d via %s", saved.course_id, title)
        messagebox.showinfo(
            "Saved",
            f"Course #{saved.course_id} saved\n"
            f"  Code    : {saved.course_code}\n"
            f"  Subject : {saved.subject}\n"
            f"  Year    : {saved.academic_year} · Year {saved.year_group}",
            parent=gui.root,
        )
        gui.status_var.set(f"Saved course {saved.course_code}")
        open_directory(gui)

    ttk.Button(bar, text="Save", command=submit).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Cancel",
               command=lambda: open_directory(gui)).pack(side="left")


def open_add_course(gui) -> None:
    def on_save(payload: dict[str, Any]) -> Course:
        return data.create_course(payload)
    _course_form(gui, title="New Course", existing=None, on_save=on_save)
    gui.status_var.set("New course")


def open_edit_course(gui, course_id: int) -> None:
    try:
        existing = data.get_course(course_id)
    except Exception as e:
        logger.exception("Failed to load course %d", course_id)
        messagebox.showerror("Error", f"Could not load course: {e}",
                             parent=gui.root)
        return
    if existing is None:
        messagebox.showerror("Not found", f"No course #{course_id}",
                             parent=gui.root)
        return

    def on_save(payload: dict[str, Any]) -> Course:
        return data.update_course(course_id, payload)
    _course_form(
        gui, title=f"Edit Course — {existing.course_code}",
        existing=existing, on_save=on_save,
    )
    gui.status_var.set(f"Editing course #{course_id}")


# ── Directory ───────────────────────────────────────────────────────

def open_directory(gui) -> None:
    frame = _clear(gui)
    _heading(frame, "Courses")

    filt = ttk.Frame(frame)
    filt.pack(anchor="w", fill="x", pady=(0, 8))

    subject_var = tk.StringVar()
    yg_var = tk.StringVar()
    year_var = tk.StringVar()
    search_var = tk.StringVar()

    ttk.Label(filt, text="Subject:").pack(side="left")
    ttk.Combobox(
        filt, textvariable=subject_var,
        values=["", *_active_subjects()], state="readonly", width=22,
    ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Year group:").pack(side="left")
    ttk.Combobox(
        filt, textvariable=yg_var,
        values=["", *[str(y) for y in YEAR_GROUPS]],
        state="readonly", width=6,
    ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Year:").pack(side="left")
    ttk.Entry(filt, textvariable=year_var, width=10).pack(
        side="left", padx=(4, 12))
    ttk.Label(filt, text="Search:").pack(side="left")
    ttk.Entry(filt, textvariable=search_var, width=18).pack(
        side="left", padx=(4, 4))

    table_holder = ttk.Frame(frame)
    table_holder.pack(fill="both", expand=True)
    summary = ttk.Label(frame, text="", foreground="#555")
    summary.pack(anchor="w", pady=(4, 8))
    actions_holder = ttk.Frame(frame)
    actions_holder.pack(anchor="w", pady=(0, 4))

    def refresh() -> None:
        for w in table_holder.winfo_children():
            w.destroy()
        for w in actions_holder.winfo_children():
            w.destroy()

        try:
            rows = data.list_courses(
                subject=subject_var.get().strip() or None,
                year_group=int(yg_var.get()) if yg_var.get() else None,
                academic_year=year_var.get().strip() or None,
                search=search_var.get().strip() or None,
            )
        except Exception as e:
            logger.exception("Failed to load courses")
            ttk.Label(
                table_holder, text=f"Error loading courses: {e}",
                foreground="#a33",
            ).pack(anchor="w")
            return

        cols = ("course_id", "course_code", "subject", "title",
                "year_group", "academic_year", "teacher", "room", "max_students")
        headings = {
            "course_id":     ("#",        50),
            "course_code":   ("Code",     120),
            "subject":       ("Subject",  150),
            "title":         ("Title",    220),
            "year_group":    ("YG",        40),
            "academic_year": ("Year",      80),
            "teacher":       ("Teacher",  130),
            "room":          ("Room",      60),
            "max_students":  ("Max",       50),
        }
        tree = ttk.Treeview(table_holder, columns=cols, show="headings", height=14)
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(table_holder, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        for c in rows:
            tree.insert("", "end", iid=str(c.course_id), values=(
                c.course_id, c.course_code, c.subject, c.title,
                c.year_group, c.academic_year,
                c.teacher or "—", c.room or "—", c.max_students,
            ))

        summary.configure(text=f"{len(rows)} course(s).")

        def _selected() -> int | None:
            sel = tree.selection()
            return int(sel[0]) if sel else None

        def _require() -> int | None:
            cid = _selected()
            if cid is None:
                messagebox.showinfo("No selection",
                                    "Pick a course first.", parent=gui.root)
            return cid

        ttk.Button(actions_holder, text="View",
                   command=lambda: (_require() and open_profile(gui, _selected()))
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Edit",
                   command=lambda: (_require() and open_edit_course(gui, _selected()))
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Delete",
                   command=lambda: (_require() and _delete_with_confirm(gui, _selected()))
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="New Course",
                   command=lambda: open_add_course(gui)
                   ).pack(side="left", padx=(12, 6))
        ttk.Button(actions_holder, text="Refresh", command=refresh
                   ).pack(side="left")

        tree.bind("<Double-1>",
                  lambda _e: (_selected() and open_profile(gui, _selected())))
        gui.status_var.set(f"Courses: {len(rows)} match(es)")

    ttk.Button(filt, text="Apply", command=refresh).pack(side="left", padx=(8, 0))
    ttk.Button(
        filt, text="Clear",
        command=lambda: (subject_var.set(""), yg_var.set(""),
                         year_var.set(""), search_var.set(""), refresh()),
    ).pack(side="left", padx=(4, 0))
    refresh()


# ── Profile / delete ────────────────────────────────────────────────

def open_profile(gui, course_id: int) -> None:
    frame = _clear(gui)
    _heading(frame, f"Course #{course_id}")

    try:
        c = data.get_course(course_id)
    except Exception as exc:
        logger.exception("Failed to load course %d", course_id)
        ttk.Label(frame, text=f"Error: {exc}", foreground="#a33").pack(anchor="w")
        return
    if c is None:
        ttk.Label(frame, text="No such course.", foreground="#a33").pack(anchor="w")
        return

    grid = ttk.Frame(frame)
    grid.pack(anchor="w", pady=(8, 0))

    def field(row: int, label: str, value: str) -> None:
        ttk.Label(grid, text=label + ":", foreground="#555",
                  width=18, anchor="e").grid(row=row, column=0, sticky="e",
                                              pady=2, padx=(0, 8))
        ttk.Label(grid, text=value or "—").grid(
            row=row, column=1, sticky="w", pady=2)

    field(0, "Course code",   c.course_code)
    field(1, "Subject",       c.subject)
    field(2, "Title",         c.title)
    field(3, "Year group",    f"Year {c.year_group}")
    field(4, "Academic year", c.academic_year)
    field(5, "Teacher",       c.teacher or "—")
    field(6, "Room",          c.room or "—")
    field(7, "Max students",  str(c.max_students))
    field(8, "Created",       c.created_at)
    if c.description:
        ttk.Separator(grid, orient="horizontal").grid(
            row=9, column=0, columnspan=2, sticky="ew", pady=(10, 6))
        ttk.Label(grid, text="Description:", foreground="#555",
                  width=18, anchor="e").grid(row=10, column=0, sticky="ne",
                                              padx=(0, 8))
        ttk.Label(grid, text=c.description,
                  wraplength=520, justify="left").grid(
            row=10, column=1, sticky="w")

    actions = ttk.Frame(frame)
    actions.pack(anchor="w", pady=(12, 0))
    ttk.Button(actions, text="Edit",
               command=lambda: open_edit_course(gui, c.course_id)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Delete",
               command=lambda: _delete_with_confirm(gui, c.course_id)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Back to Courses",
               command=lambda: open_directory(gui)).pack(side="left")
    gui.status_var.set(f"Viewing course #{course_id}")


def _delete_with_confirm(gui, course_id: int) -> None:
    try:
        c = data.get_course(course_id)
    except Exception as exc:
        logger.exception("Failed to load course %d", course_id)
        messagebox.showerror("Error", f"Could not load course: {exc}",
                             parent=gui.root)
        return
    if c is None:
        messagebox.showerror("Not found", f"No course #{course_id}",
                             parent=gui.root)
        return
    ok = messagebox.askyesno(
        "Delete course",
        f"Delete course {c.course_code} ({c.subject}, Year {c.year_group} "
        f"{c.academic_year})?",
        parent=gui.root,
    )
    if not ok:
        logger.debug("GUI delete cancelled for course #%d", course_id)
        return
    try:
        deleted = data.delete_course(course_id)
    except Exception as exc:
        logger.exception("GUI delete failed for course %d", course_id)
        messagebox.showerror("Error", f"Could not delete: {exc}",
                             parent=gui.root)
        return
    if deleted:
        gui.status_var.set(f"Deleted course #{course_id}")
        open_directory(gui)
    else:
        messagebox.showerror("Error", "Could not delete course.",
                             parent=gui.root)
