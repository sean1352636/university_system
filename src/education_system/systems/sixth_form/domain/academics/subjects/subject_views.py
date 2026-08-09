"""GUI panels for Sixth Form Subjects & A-Levels.

Same shape as the other CRUD areas. Soft-delete (deactivate) is
preferred for subjects already in use by students or courses; the
data layer enforces this and surfaces a friendly error if the staff
member tries to hard-delete a referenced subject.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable
from education_system.systems.sixth_form.domain.academics.subjects import subjects as data
from education_system.systems.sixth_form.domain.academics.subjects.subjects import (
    DEFAULT_QUALIFICATION,
    EXAM_BOARDS,
    QUALIFICATIONS,
    Subject,
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


# ── Add / Edit form ─────────────────────────────────────────────────

def _subject_form(
    gui,
    *,
    title: str,
    existing: Subject | None,
    on_save: Callable[[dict[str, Any]], Subject],
) -> None:
    frame = _clear(gui)
    _heading(frame, title)

    is_edit = existing is not None

    form = ttk.Frame(frame, padding=(0, 4))
    form.pack(anchor="w", fill="x")
    form.columnconfigure(1, weight=1, minsize=320)

    description_text = tk.Text(form, height=4, width=60)

    name_var = tk.StringVar(value=existing.name if is_edit else "")
    qual_var = tk.StringVar(
        value=existing.qualification if is_edit else DEFAULT_QUALIFICATION)
    board_var = tk.StringVar(
        value=(existing.exam_board or "") if is_edit else "")
    active_var = tk.BooleanVar(value=existing.is_active if is_edit else True)

    def row(idx: int, label: str, widget: tk.Widget) -> None:
        ttk.Label(form, text=label).grid(
            row=idx, column=0, sticky="e", padx=(0, 8), pady=4)
        widget.grid(row=idx, column=1, sticky="ew", pady=4)

    row(0, "Subject name *", ttk.Entry(form, textvariable=name_var))
    row(1, "Qualification *", ttk.Combobox(
        form, textvariable=qual_var, values=list(QUALIFICATIONS),
        state="readonly", width=28))
    row(2, "Exam board", ttk.Combobox(
        form, textvariable=board_var, values=["", *EXAM_BOARDS],
        state="readonly", width=18))
    row(3, "Active", ttk.Checkbutton(form, variable=active_var))
    ttk.Label(form, text="Description").grid(
        row=4, column=0, sticky="ne", padx=(0, 8), pady=4)
    description_text.grid(row=4, column=1, sticky="ew", pady=4)
    if is_edit and existing.description:
        description_text.insert("1.0", existing.description)

    bar = ttk.Frame(frame)
    bar.pack(anchor="w", pady=(12, 0))

    def submit() -> None:
        payload = {
            "name":          name_var.get(),
            "qualification": qual_var.get(),
            "exam_board":    board_var.get(),
            "description":   description_text.get("1.0", "end").strip(),
            "is_active":     active_var.get(),
        }
        try:
            saved = on_save(payload)
        except ValidationError as e:
            logger.warning("Subject form rejected: %s", e)
            messagebox.showerror("Cannot save", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("Unexpected error saving subject form")
            messagebox.showerror("Error", f"Unexpected error: {e}",
                                 parent=gui.root)
            return
        logger.info("GUI saved subject #%d via %s", saved.subject_id, title)
        messagebox.showinfo(
            "Saved",
            f"Subject #{saved.subject_id} saved\n"
            f"  Name          : {saved.name}\n"
            f"  Qualification : {saved.qualification}\n"
            f"  Exam board    : {saved.exam_board or '—'}\n"
            f"  Active        : {'Yes' if saved.is_active else 'No'}",
            parent=gui.root,
        )
        gui.status_var.set(f"Saved subject {saved.name}")
        open_directory(gui)

    ttk.Button(bar, text="Save", command=submit).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Cancel",
               command=lambda: open_directory(gui)).pack(side="left")


def open_add_subject(gui) -> None:
    def on_save(payload: dict[str, Any]) -> Subject:
        return data.create_subject(payload)
    _subject_form(gui, title="New Subject", existing=None, on_save=on_save)
    gui.status_var.set("New subject")


def open_edit_subject(gui, subject_id: int) -> None:
    try:
        existing = data.get_subject(subject_id)
    except Exception as e:
        logger.exception("Failed to load subject %d", subject_id)
        messagebox.showerror("Error", f"Could not load subject: {e}",
                             parent=gui.root)
        return
    if existing is None:
        messagebox.showerror("Not found", f"No subject #{subject_id}",
                             parent=gui.root)
        return

    def on_save(payload: dict[str, Any]) -> Subject:
        return data.update_subject(subject_id, payload)
    _subject_form(
        gui, title=f"Edit Subject — {existing.name}",
        existing=existing, on_save=on_save,
    )
    gui.status_var.set(f"Editing subject #{subject_id}")


# ── Directory ───────────────────────────────────────────────────────

def open_directory(gui) -> None:
    frame = _clear(gui)
    _heading(frame, "Subjects & A-Levels")

    filt = ttk.Frame(frame)
    filt.pack(anchor="w", fill="x", pady=(0, 8))

    qual_var = tk.StringVar()
    board_var = tk.StringVar()
    active_var = tk.StringVar(value="All")
    search_var = tk.StringVar()

    ttk.Label(filt, text="Qualification:").pack(side="left")
    ttk.Combobox(
        filt, textvariable=qual_var,
        values=["", *QUALIFICATIONS], state="readonly", width=20,
    ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Exam board:").pack(side="left")
    ttk.Combobox(
        filt, textvariable=board_var,
        values=["", *EXAM_BOARDS], state="readonly", width=14,
    ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Show:").pack(side="left")
    ttk.Combobox(
        filt, textvariable=active_var,
        values=["All", "Active only", "Inactive only"],
        state="readonly", width=14,
    ).pack(side="left", padx=(4, 12))
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
            show = active_var.get()
            include_inactive = show != "Active only"
            rows = data.list_subjects(
                qualification=qual_var.get().strip() or None,
                exam_board=board_var.get().strip() or None,
                include_inactive=include_inactive,
                search=search_var.get().strip() or None,
            )
            if show == "Inactive only":
                rows = [r for r in rows if not r.is_active]
        except Exception as e:
            logger.exception("Failed to load subjects")
            ttk.Label(
                table_holder, text=f"Error loading subjects: {e}",
                foreground="#a33",
            ).pack(anchor="w")
            return

        cols = ("subject_id", "name", "qualification", "exam_board",
                "active", "students", "courses")
        headings = {
            "subject_id":    ("#",         50),
            "name":          ("Subject",  220),
            "qualification": ("Qual.",    150),
            "exam_board":    ("Board",    110),
            "active":        ("Active",    60),
            "students":      ("Students",  70),
            "courses":       ("Courses",   70),
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

        for s in rows:
            usage = data.is_in_use(s.name)
            tree.insert("", "end", iid=str(s.subject_id), values=(
                s.subject_id, s.name, s.qualification,
                s.exam_board or "—",
                "Yes" if s.is_active else "No",
                usage["students"], usage["courses"],
            ))

        summary.configure(text=f"{len(rows)} subject(s).")

        def _selected() -> int | None:
            sel = tree.selection()
            return int(sel[0]) if sel else None

        def _require() -> int | None:
            sid = _selected()
            if sid is None:
                messagebox.showinfo("No selection",
                                    "Pick a subject first.", parent=gui.root)
            return sid

        def _toggle_active() -> None:
            sid = _require()
            if sid is None:
                return
            existing = data.get_subject(sid)
            if existing is None:
                return
            try:
                if existing.is_active:
                    data.deactivate(sid)
                    gui.status_var.set(f"Deactivated {existing.name}")
                else:
                    data.activate(sid)
                    gui.status_var.set(f"Activated {existing.name}")
            except Exception as e:
                logger.exception("Toggle-active failed for #%d", sid)
                messagebox.showerror("Error", str(e), parent=gui.root)
                return
            refresh()

        ttk.Button(actions_holder, text="View",
                   command=lambda: (_require() and open_profile(gui, _selected()))
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Edit",
                   command=lambda: (_require() and open_edit_subject(gui, _selected()))
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Activate / Deactivate",
                   command=_toggle_active
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Delete",
                   command=lambda: (_require() and _delete_with_confirm(gui, _selected()))
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="New Subject",
                   command=lambda: open_add_subject(gui)
                   ).pack(side="left", padx=(12, 6))
        ttk.Button(actions_holder, text="Refresh", command=refresh
                   ).pack(side="left")

        tree.bind("<Double-1>",
                  lambda _e: (_selected() and open_profile(gui, _selected())))
        gui.status_var.set(f"Subjects: {len(rows)} match(es)")

    ttk.Button(filt, text="Apply", command=refresh).pack(side="left", padx=(8, 0))
    ttk.Button(
        filt, text="Clear",
        command=lambda: (qual_var.set(""), board_var.set(""),
                         active_var.set("All"), search_var.set(""), refresh()),
    ).pack(side="left", padx=(4, 0))
    refresh()


# ── Profile / delete ────────────────────────────────────────────────

def open_profile(gui, subject_id: int) -> None:
    frame = _clear(gui)
    _heading(frame, f"Subject #{subject_id}")

    try:
        s = data.get_subject(subject_id)
    except Exception as exc:
        logger.exception("Failed to load subject %d", subject_id)
        ttk.Label(frame, text=f"Error: {exc}", foreground="#a33").pack(anchor="w")
        return
    if s is None:
        ttk.Label(frame, text="No such subject.",
                  foreground="#a33").pack(anchor="w")
        return

    usage = data.is_in_use(s.name)

    grid = ttk.Frame(frame)
    grid.pack(anchor="w", pady=(8, 0))

    def field(row: int, label: str, value: str) -> None:
        ttk.Label(grid, text=label + ":", foreground="#555",
                  width=18, anchor="e").grid(row=row, column=0, sticky="e",
                                              pady=2, padx=(0, 8))
        ttk.Label(grid, text=value or "—").grid(
            row=row, column=1, sticky="w", pady=2)

    field(0, "Name", s.name)
    field(1, "Qualification", s.qualification)
    field(2, "Exam board", s.exam_board or "—")
    field(3, "Active", "Yes" if s.is_active else "No")
    field(4, "Created", s.created_at)
    field(5, "Students using", str(usage["students"]))
    field(6, "Courses using", str(usage["courses"]))
    if s.description:
        ttk.Separator(grid, orient="horizontal").grid(
            row=7, column=0, columnspan=2, sticky="ew", pady=(10, 6))
        ttk.Label(grid, text="Description:", foreground="#555",
                  width=18, anchor="e").grid(row=8, column=0, sticky="ne",
                                              padx=(0, 8))
        ttk.Label(grid, text=s.description,
                  wraplength=520, justify="left").grid(
            row=8, column=1, sticky="w")

    actions = ttk.Frame(frame)
    actions.pack(anchor="w", pady=(12, 0))
    ttk.Button(actions, text="Edit",
               command=lambda: open_edit_subject(gui, s.subject_id)
               ).pack(side="left", padx=(0, 6))
    if s.is_active:
        ttk.Button(actions, text="Deactivate",
                   command=lambda: _toggle_and_refresh(gui, s.subject_id, False)
                   ).pack(side="left", padx=(0, 6))
    else:
        ttk.Button(actions, text="Activate",
                   command=lambda: _toggle_and_refresh(gui, s.subject_id, True)
                   ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Delete",
               command=lambda: _delete_with_confirm(gui, s.subject_id)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Back to Subjects",
               command=lambda: open_directory(gui)).pack(side="left")
    gui.status_var.set(f"Viewing subject #{subject_id}")


def _toggle_and_refresh(gui, subject_id: int, activate: bool) -> None:
    try:
        if activate:
            data.activate(subject_id)
        else:
            data.deactivate(subject_id)
    except Exception as e:
        logger.exception("Toggle-active failed for #%d", subject_id)
        messagebox.showerror("Error", str(e), parent=gui.root)
        return
    open_profile(gui, subject_id)


def _delete_with_confirm(gui, subject_id: int) -> None:
    try:
        s = data.get_subject(subject_id)
    except Exception as exc:
        logger.exception("Failed to load subject %d", subject_id)
        messagebox.showerror("Error", f"Could not load subject: {exc}",
                             parent=gui.root)
        return
    if s is None:
        messagebox.showerror("Not found", f"No subject #{subject_id}",
                             parent=gui.root)
        return
    usage = data.is_in_use(s.name)
    if usage["students"] or usage["courses"]:
        if messagebox.askyesno(
            "Cannot delete — deactivate instead?",
            f"'{s.name}' is still in use by "
            f"{usage['students']} student(s) and {usage['courses']} course(s).\n\n"
            f"Hard delete is blocked. Deactivate it instead? "
            f"(it will hide from new dropdowns but existing rows are unaffected)",
            parent=gui.root,
        ):
            try:
                data.deactivate(subject_id)
            except Exception as e:
                logger.exception("Deactivate fallback failed for #%d", subject_id)
                messagebox.showerror("Error", str(e), parent=gui.root)
                return
            open_directory(gui)
        return

    if not messagebox.askyesno(
        "Delete subject",
        f"Permanently delete '{s.name}'? This cannot be undone.",
        parent=gui.root,
    ):
        return
    try:
        deleted = data.delete_subject(subject_id)
    except ValidationError as e:
        logger.warning("Hard delete rejected: %s", e)
        messagebox.showerror("Cannot delete", str(e), parent=gui.root)
        return
    except Exception as exc:
        logger.exception("Delete failed for subject %d", subject_id)
        messagebox.showerror("Error", f"Could not delete: {exc}",
                             parent=gui.root)
        return
    if deleted:
        gui.status_var.set(f"Deleted subject #{subject_id}")
        open_directory(gui)
    else:
        messagebox.showerror("Error", "Could not delete subject.",
                             parent=gui.root)
