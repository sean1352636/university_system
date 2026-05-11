"""GUI panels for Sixth Form Homework & Coursework.

Tabbed view:

  * Assignments — filterable directory + CRUD on assignments.
  * Mark sheet — pick an assignment, fill in each student's status /
    submitted-at / marks / feedback, save the lot at once.
  * Summary — per-student submission stats + average mark percentage.
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date
from tkinter import messagebox, ttk
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.class_groups import class_groups
from education_system.sixthform_system.modules.domain.courses import courses
from education_system.sixthform_system.modules.domain.homework import homework
from education_system.sixthform_system.modules.domain.students import students as cg_data
from education_system.sixthform_system.modules.domain.courses import courses as course_data
from education_system.sixthform_system.modules.domain.homework import homework as data
from education_system.sixthform_system.modules.domain.students import students as student_data
from education_system.sixthform_system.modules.domain.homework.homework import (
    ASSIGNMENT_TYPES,
    Assignment,
    DEFAULT_ASSIGNMENT_TYPE,
    DEFAULT_SUBMISSION_STATUS,
    SUBMISSION_STATUSES,
    StudentSummary,
    Submission,
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


def _group_label(g, course=None) -> str:
    if course is None:
        course = course_data.get_course(g.course_id)
    code = course.course_code if course else f"#{g.course_id}"
    return f"#{g.group_id} {g.group_name} ({code})"


def _today() -> str:
    return _date.today().isoformat()


# ── Top-level tabbed view ───────────────────────────────────────────

def open_directory(gui) -> None:
    frame = _clear(gui)
    _heading(frame, "Homework & Coursework")

    nb = ttk.Notebook(frame)
    nb.pack(fill="both", expand=True)

    assn_tab = ttk.Frame(nb, padding=8)
    marks_tab = ttk.Frame(nb, padding=8)
    summary_tab = ttk.Frame(nb, padding=8)
    nb.add(assn_tab,    text="Assignments")
    nb.add(marks_tab,   text="Mark sheet")
    nb.add(summary_tab, text="Summary")

    _build_assignments_tab(gui, assn_tab)
    _build_marks_tab(gui, marks_tab)
    _build_summary_tab(gui, summary_tab)


# ─── Assignments tab ────────────────────────────────────────────────

def _build_assignments_tab(gui, parent: ttk.Frame) -> None:
    filt = ttk.Frame(parent)
    filt.pack(anchor="w", fill="x", pady=(0, 8))

    groups = cg_data.list_groups()
    courses_by_id = {c.course_id: c for c in course_data.list_courses()}
    group_labels = [""] + [_group_label(g, courses_by_id.get(g.course_id))
                           for g in groups]
    group_by_label = {_group_label(g, courses_by_id.get(g.course_id)): g.group_id
                      for g in groups}

    group_var = tk.StringVar()
    type_var = tk.StringVar()
    from_var = tk.StringVar()
    to_var = tk.StringVar()
    search_var = tk.StringVar()

    ttk.Label(filt, text="Group:").pack(side="left")
    ttk.Combobox(filt, textvariable=group_var, values=group_labels,
                 state="readonly", width=42
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Type:").pack(side="left")
    ttk.Combobox(filt, textvariable=type_var,
                 values=["", *ASSIGNMENT_TYPES], state="readonly", width=14
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Due from:").pack(side="left")
    ttk.Entry(filt, textvariable=from_var, width=12
              ).pack(side="left", padx=(4, 8))
    ttk.Label(filt, text="to:").pack(side="left")
    ttk.Entry(filt, textvariable=to_var, width=12
              ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Search:").pack(side="left")
    ttk.Entry(filt, textvariable=search_var, width=14
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
            rows = data.list_assignments(
                group_id=group_by_label.get(group_var.get()),
                type=type_var.get().strip() or None,
                due_from=from_var.get().strip() or None,
                due_to=to_var.get().strip() or None,
                search=search_var.get().strip() or None,
            )
        except ValidationError as e:
            ttk.Label(table_holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return
        except Exception as e:
            logger.exception("list_assignments failed")
            ttk.Label(table_holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        cols = ("assignment_id", "title", "type", "group",
                "set_date", "due_date", "max_marks")
        headings = {
            "assignment_id": ("#",        50),
            "title":         ("Title",    300),
            "type":          ("Type",     110),
            "group":         ("Group",    160),
            "set_date":      ("Set",      100),
            "due_date":      ("Due",      100),
            "max_marks":     ("Max",       50),
        }
        tree = ttk.Treeview(table_holder, columns=cols, show="headings", height=12)
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(table_holder, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        group_index = {g.group_id: g for g in groups}
        for a in rows:
            g = group_index.get(a.group_id)
            glabel = (_group_label(g, courses_by_id.get(g.course_id))
                      if g else f"#{a.group_id}")
            tree.insert("", "end", iid=str(a.assignment_id), values=(
                a.assignment_id, a.title, a.type, glabel,
                a.set_date, a.due_date,
                a.max_marks if a.max_marks is not None else "—",
            ))

        summary.configure(text=f"{len(rows)} assignment(s).")

        def _selected() -> int | None:
            sel = tree.selection()
            return int(sel[0]) if sel else None

        def _require() -> int | None:
            aid = _selected()
            if aid is None:
                messagebox.showinfo("No selection",
                                    "Pick an assignment first.",
                                    parent=gui.root)
            return aid

        ttk.Button(actions_holder, text="View",
                   command=lambda: (_require() and open_profile(gui, _selected()))
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Edit",
                   command=lambda: (_require() and
                                    open_edit_assignment(gui, _selected()))
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Mark sheet",
                   command=lambda: (_require() and
                                    open_mark_sheet(gui, _selected()))
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Delete",
                   command=lambda: (_require() and
                                    _delete_with_confirm(gui, _selected()))
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="New",
                   command=lambda: open_add_assignment(gui)
                   ).pack(side="left", padx=(12, 6))
        ttk.Button(actions_holder, text="Refresh",
                   command=refresh).pack(side="left")
        tree.bind("<Double-1>",
                  lambda _e: (_selected() and open_profile(gui, _selected())))
        gui.status_var.set(f"Assignments: {len(rows)} match(es)")

    ttk.Button(filt, text="Apply", command=refresh
               ).pack(side="left", padx=(8, 0))
    ttk.Button(filt, text="Clear",
               command=lambda: (group_var.set(""), type_var.set(""),
                                from_var.set(""), to_var.set(""),
                                search_var.set(""), refresh())
               ).pack(side="left", padx=(4, 0))
    refresh()


# ─── Add / Edit form ────────────────────────────────────────────────

def _assignment_form(
    gui,
    *,
    title: str,
    existing: Assignment | None,
    preselect_group_id: int | None,
    on_save: Callable[[dict[str, Any]], Assignment],
) -> None:
    frame = _clear(gui)
    _heading(frame, title)
    is_edit = existing is not None

    groups = cg_data.list_groups()
    if not groups and not is_edit:
        ttk.Label(frame,
                  text="No class groups yet — create a class group first.",
                  foreground="#a33").pack(anchor="w")
        ttk.Button(frame, text="Back",
                   command=lambda: open_directory(gui)
                   ).pack(anchor="w", pady=(8, 0))
        return
    courses_by_id = {c.course_id: c for c in course_data.list_courses()}
    group_labels = [_group_label(g, courses_by_id.get(g.course_id))
                    for g in groups]
    group_by_label = {lbl: g.group_id for lbl, g in zip(group_labels, groups)}

    if is_edit:
        g = cg_data.get_group(existing.group_id)
        disp = _group_label(g, courses_by_id.get(g.course_id)) if g else \
               f"#{existing.group_id} (deleted)"
    elif preselect_group_id is not None:
        g = cg_data.get_group(preselect_group_id)
        disp = (_group_label(g, courses_by_id.get(g.course_id))
                if g else (group_labels[0] if group_labels else ""))
    else:
        disp = group_labels[0] if group_labels else ""

    group_var = tk.StringVar(value=disp)
    title_var = tk.StringVar(value=existing.title if is_edit else "")
    type_var = tk.StringVar(
        value=existing.type if is_edit else DEFAULT_ASSIGNMENT_TYPE)
    set_var = tk.StringVar(
        value=existing.set_date if is_edit else _today())
    due_var = tk.StringVar(
        value=existing.due_date if is_edit else _today())
    max_var = tk.StringVar(
        value=str(existing.max_marks) if (is_edit and existing.max_marks is not None)
              else "100")

    form = ttk.Frame(frame, padding=(0, 4))
    form.pack(anchor="w", fill="x")
    form.columnconfigure(1, weight=1, minsize=320)

    description_text = tk.Text(form, height=4, width=60)
    notes_text = tk.Text(form, height=3, width=60)

    def row(idx: int, label: str, widget: tk.Widget) -> None:
        ttk.Label(form, text=label).grid(
            row=idx, column=0, sticky="e", padx=(0, 8), pady=4)
        widget.grid(row=idx, column=1, sticky="ew", pady=4)

    row(0, "Class group *", ttk.Combobox(
        form, textvariable=group_var, values=group_labels,
        state=("readonly" if not is_edit else "disabled"), width=46))
    row(1, "Title *", ttk.Entry(form, textvariable=title_var))
    row(2, "Type *", ttk.Combobox(
        form, textvariable=type_var, values=list(ASSIGNMENT_TYPES),
        state="readonly", width=22))
    row(3, "Set date * (YYYY-MM-DD)",
        ttk.Entry(form, textvariable=set_var, width=14))
    row(4, "Due date * (YYYY-MM-DD)",
        ttk.Entry(form, textvariable=due_var, width=14))
    row(5, "Max marks", ttk.Entry(form, textvariable=max_var, width=10))
    ttk.Label(form, text="Description").grid(
        row=6, column=0, sticky="ne", padx=(0, 8), pady=4)
    description_text.grid(row=6, column=1, sticky="ew", pady=4)
    if is_edit and existing.description:
        description_text.insert("1.0", existing.description)
    ttk.Label(form, text="Notes").grid(
        row=7, column=0, sticky="ne", padx=(0, 8), pady=4)
    notes_text.grid(row=7, column=1, sticky="ew", pady=4)
    if is_edit and existing.notes:
        notes_text.insert("1.0", existing.notes)

    bar = ttk.Frame(frame)
    bar.pack(anchor="w", pady=(12, 0))

    def submit() -> None:
        if is_edit:
            gid = existing.group_id
        else:
            gid = group_by_label.get(group_var.get())
            if gid is None:
                messagebox.showerror("Cannot save",
                                     "Pick a class group.", parent=gui.root)
                return
        payload = {
            "group_id":   gid,
            "title":      title_var.get(),
            "type":       type_var.get(),
            "set_date":   set_var.get(),
            "due_date":   due_var.get(),
            "max_marks":  max_var.get(),
            "description": description_text.get("1.0", "end").strip(),
            "notes":      notes_text.get("1.0", "end").strip(),
        }
        try:
            saved = on_save(payload)
        except ValidationError as e:
            logger.warning("assignment form rejected: %s", e)
            messagebox.showerror("Cannot save", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("save assignment crashed")
            messagebox.showerror("Error", f"Unexpected: {e}", parent=gui.root)
            return
        logger.info("GUI saved assignment #%d via %s", saved.assignment_id, title)
        gui.status_var.set(f"Saved assignment #{saved.assignment_id}")
        open_profile(gui, saved.assignment_id)

    ttk.Button(bar, text="Save", command=submit
               ).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Cancel",
               command=lambda: open_directory(gui)).pack(side="left")


def open_add_assignment(gui, preselect_group_id: int | None = None) -> None:
    def on_save(payload: dict[str, Any]) -> Assignment:
        return data.create_assignment(payload)
    _assignment_form(gui, title="New Assignment", existing=None,
                     preselect_group_id=preselect_group_id, on_save=on_save)


def open_edit_assignment(gui, assignment_id: int) -> None:
    a = data.get_assignment(assignment_id)
    if a is None:
        messagebox.showerror("Not found", f"No assignment #{assignment_id}",
                             parent=gui.root)
        return

    def on_save(payload: dict[str, Any]) -> Assignment:
        return data.update_assignment(assignment_id, payload)
    _assignment_form(gui, title=f"Edit Assignment — {a.title}",
                     existing=a, preselect_group_id=a.group_id,
                     on_save=on_save)


# ─── Assignment profile (with quick links) ─────────────────────────

def open_profile(gui, assignment_id: int) -> None:
    frame = _clear(gui)
    _heading(frame, f"Assignment #{assignment_id}")

    a = data.get_assignment(assignment_id)
    if a is None:
        ttk.Label(frame, text="No such assignment.",
                  foreground="#a33").pack(anchor="w")
        return

    g = cg_data.get_group(a.group_id)
    course = course_data.get_course(g.course_id) if g else None

    grid = ttk.Frame(frame)
    grid.pack(anchor="w", pady=(8, 0))

    def field(row: int, label: str, value: str) -> None:
        ttk.Label(grid, text=label + ":", foreground="#555",
                  width=18, anchor="e").grid(row=row, column=0, sticky="e",
                                              pady=2, padx=(0, 8))
        ttk.Label(grid, text=value or "—").grid(
            row=row, column=1, sticky="w", pady=2)

    field(0, "Title", a.title)
    field(1, "Type", a.type)
    field(2, "Class group",
          (_group_label(g, course) if g else f"#{a.group_id} (deleted)"))
    field(3, "Set date", a.set_date)
    field(4, "Due date", a.due_date)
    field(5, "Max marks", str(a.max_marks) if a.max_marks is not None else "—")
    field(6, "Created", a.created_at)
    if a.description:
        ttk.Separator(grid, orient="horizontal").grid(
            row=7, column=0, columnspan=2, sticky="ew", pady=(10, 6))
        ttk.Label(grid, text="Description:", foreground="#555",
                  width=18, anchor="e").grid(row=8, column=0, sticky="ne",
                                              padx=(0, 8))
        ttk.Label(grid, text=a.description, wraplength=520, justify="left"
                  ).grid(row=8, column=1, sticky="w")
    if a.notes:
        ttk.Label(grid, text="Notes:", foreground="#555",
                  width=18, anchor="e").grid(row=9, column=0, sticky="ne",
                                              padx=(0, 8), pady=(6, 0))
        ttk.Label(grid, text=a.notes, wraplength=520, justify="left"
                  ).grid(row=9, column=1, sticky="w", pady=(6, 0))

    actions = ttk.Frame(frame)
    actions.pack(anchor="w", pady=(12, 0))
    ttk.Button(actions, text="Mark sheet",
               command=lambda: open_mark_sheet(gui, a.assignment_id)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Edit",
               command=lambda: open_edit_assignment(gui, a.assignment_id)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Delete",
               command=lambda: _delete_with_confirm(gui, a.assignment_id)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Back",
               command=lambda: open_directory(gui)).pack(side="left")
    gui.status_var.set(f"Viewing assignment #{assignment_id}")


def _delete_with_confirm(gui, assignment_id: int) -> None:
    a = data.get_assignment(assignment_id)
    if a is None:
        messagebox.showerror("Not found", f"No assignment #{assignment_id}",
                             parent=gui.root)
        return
    n_subs = len(data.list_submissions(assignment_id=assignment_id))
    msg = f"Delete assignment '{a.title}'?"
    if n_subs:
        msg += f"\n\n{n_subs} submission row(s) will be removed."
    if not messagebox.askyesno("Delete assignment", msg, parent=gui.root):
        return
    try:
        data.delete_assignment(assignment_id)
    except Exception as e:
        logger.exception("delete_assignment crashed")
        messagebox.showerror("Error", f"Could not delete: {e}",
                             parent=gui.root)
        return
    gui.status_var.set(f"Deleted assignment #{assignment_id}")
    open_directory(gui)


# ─── Mark-sheet tab ─────────────────────────────────────────────────

def _build_marks_tab(gui, parent: ttk.Frame) -> None:
    assns = data.list_assignments()
    groups = {g.group_id: g for g in cg_data.list_groups()}
    courses = {c.course_id: c for c in course_data.list_courses()}
    assn_labels = [
        f"#{a.assignment_id}  {a.title}  ({a.type}, due {a.due_date})"
        for a in assns
    ]
    assn_by_label = {lbl: a.assignment_id for lbl, a in zip(assn_labels, assns)}

    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))

    assn_var = tk.StringVar(value=assn_labels[0] if assn_labels else "")
    ttk.Label(bar, text="Assignment:").pack(side="left")
    ttk.Combobox(bar, textvariable=assn_var, values=assn_labels,
                 state="readonly", width=58
                 ).pack(side="left", padx=(4, 12))

    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True, pady=(0, 8))

    row_state: dict[str, dict[str, Any]] = {}

    def load() -> None:
        nonlocal row_state
        for w in holder.winfo_children():
            w.destroy()
        row_state = {}
        aid = assn_by_label.get(assn_var.get())
        if aid is None:
            ttk.Label(holder, text="Pick an assignment.",
                      foreground="#a33").pack(anchor="w")
            return
        try:
            view = data.submission_view(aid)
        except ValidationError as e:
            ttk.Label(holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return
        except Exception as e:
            logger.exception("submission_view failed")
            ttk.Label(holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return
        if not view:
            ttk.Label(holder,
                      text="This assignment's class group has no members.",
                      foreground="#a33").pack(anchor="w")
            return

        assn = data.get_assignment(aid)
        ttk.Label(
            holder,
            text=(f"{assn.title}  ·  Max marks: "
                  f"{assn.max_marks if assn.max_marks is not None else '—'}"),
            font=("", 11, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        header = ttk.Frame(holder)
        header.pack(fill="x")
        for text, width in [
            ("Student ID",   12),
            ("Name",         28),
            ("Status",       18),
            ("Submitted at", 18),
            ("Marks",         7),
            ("Feedback",     30),
        ]:
            ttk.Label(header, text=text, font=("", 10, "bold"),
                      width=width, anchor="w").pack(side="left", padx=2)

        for v in view:
            row = ttk.Frame(holder)
            row.pack(fill="x", pady=1)

            ttk.Label(row, text=v.student_id, width=12, anchor="w"
                      ).pack(side="left", padx=2)
            ttk.Label(row, text=v.full_name, width=28, anchor="w"
                      ).pack(side="left", padx=2)

            status_var = tk.StringVar(
                value=v.submission.status if v.submission else DEFAULT_SUBMISSION_STATUS)
            sub_at_var = tk.StringVar(
                value=v.submission.submitted_at if v.submission else "")
            marks_var = tk.StringVar(
                value=str(v.submission.marks)
                if v.submission and v.submission.marks is not None else "")
            feedback_var = tk.StringVar(
                value=(v.submission.feedback or "") if v.submission else "")

            ttk.Combobox(row, textvariable=status_var,
                         values=list(SUBMISSION_STATUSES),
                         state="readonly", width=16
                         ).pack(side="left", padx=2)
            ttk.Entry(row, textvariable=sub_at_var, width=18
                      ).pack(side="left", padx=2)
            ttk.Entry(row, textvariable=marks_var, width=7
                      ).pack(side="left", padx=2)
            ttk.Entry(row, textvariable=feedback_var, width=30
                      ).pack(side="left", padx=2)

            row_state[v.student_id] = {
                "status": status_var,
                "submitted_at": sub_at_var,
                "marks": marks_var,
                "feedback": feedback_var,
            }

        helpers = ttk.Frame(holder)
        helpers.pack(anchor="w", pady=(8, 0))

        def _mark_all_submitted() -> None:
            today = _today()
            for rs in row_state.values():
                rs["status"].set("Submitted")
                if not rs["submitted_at"].get():
                    rs["submitted_at"].set(today)

        def _mark_all_missing() -> None:
            for rs in row_state.values():
                rs["status"].set("Not Submitted")
                rs["submitted_at"].set("")

        ttk.Button(helpers, text="Mark all Submitted (today)",
                   command=_mark_all_submitted
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(helpers, text="Mark all Missing",
                   command=_mark_all_missing
                   ).pack(side="left", padx=(0, 6))

        gui.status_var.set(
            f"Mark sheet loaded: assignment #{aid} ({len(view)} student(s))")

    def submit() -> None:
        aid = assn_by_label.get(assn_var.get())
        if aid is None:
            messagebox.showerror("Cannot save",
                                 "Pick an assignment.", parent=gui.root)
            return
        if not row_state:
            messagebox.showinfo("Nothing to save",
                                "Load the mark sheet first.", parent=gui.root)
            return
        payload = {
            sid: {k: v.get() for k, v in vs.items()}
            for sid, vs in row_state.items()
        }
        try:
            n = data.save_submissions(aid, payload)
        except ValidationError as e:
            logger.warning("save_submissions rejected: %s", e)
            messagebox.showerror("Cannot save", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("save_submissions crashed")
            messagebox.showerror("Error", f"Unexpected: {e}",
                                 parent=gui.root)
            return
        gui.status_var.set(f"Saved {n} submission(s)")
        messagebox.showinfo("Mark sheet saved",
                            f"Saved {n} submission row(s).",
                            parent=gui.root)

    actions = ttk.Frame(parent)
    actions.pack(anchor="w", pady=(0, 4))
    ttk.Button(actions, text="Load", command=load
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Save mark sheet", command=submit
               ).pack(side="left", padx=(0, 6))

    if not assn_labels:
        ttk.Label(holder,
                  text="No assignments yet — create one in the Assignments tab.",
                  foreground="#a33").pack(anchor="w")
    else:
        load()


def open_mark_sheet(gui, assignment_id: int) -> None:
    """Convenience: open the parent Notebook on the Mark sheet tab with
    the given assignment pre-selected."""
    # Simplest correct behaviour: re-render the whole directory then ask
    # the user to use the dropdown — we can't easily reach into a
    # foreign Notebook to pre-pick. Just open profile + show mark sheet
    # path; the user clicks "Mark sheet" → which is *this* function.
    # To actually load it here, we render the mark sheet inline.
    frame = _clear(gui)
    _heading(frame, f"Mark sheet — assignment #{assignment_id}")

    a = data.get_assignment(assignment_id)
    if a is None:
        ttk.Label(frame, text="No such assignment.",
                  foreground="#a33").pack(anchor="w")
        return
    g = cg_data.get_group(a.group_id)
    course = course_data.get_course(g.course_id) if g else None
    ttk.Label(
        frame,
        text=(f"{a.title}  ·  {a.type}  ·  due {a.due_date}\n"
              f"Group: "
              + (_group_label(g, course) if g else f"#{a.group_id} (deleted)")
              + f"   Max marks: "
              + (str(a.max_marks) if a.max_marks is not None else '—')),
        foreground="#555",
        justify="left",
    ).pack(anchor="w", pady=(0, 8))

    holder = ttk.Frame(frame)
    holder.pack(fill="both", expand=True)
    try:
        view = data.submission_view(assignment_id)
    except Exception as e:
        logger.exception("submission_view crashed")
        ttk.Label(holder, text=f"Error: {e}", foreground="#a33").pack(anchor="w")
        return

    if not view:
        ttk.Label(holder,
                  text="Class group has no members.",
                  foreground="#a33").pack(anchor="w")
        return

    row_state: dict[str, dict[str, Any]] = {}

    header = ttk.Frame(holder)
    header.pack(fill="x")
    for text, width in [
        ("Student ID",   12), ("Name", 28), ("Status", 18),
        ("Submitted at", 18), ("Marks", 7), ("Feedback", 30),
    ]:
        ttk.Label(header, text=text, font=("", 10, "bold"),
                  width=width, anchor="w").pack(side="left", padx=2)

    for v in view:
        row = ttk.Frame(holder)
        row.pack(fill="x", pady=1)
        ttk.Label(row, text=v.student_id, width=12, anchor="w").pack(side="left", padx=2)
        ttk.Label(row, text=v.full_name, width=28, anchor="w").pack(side="left", padx=2)
        status_var = tk.StringVar(
            value=v.submission.status if v.submission else DEFAULT_SUBMISSION_STATUS)
        sub_at_var = tk.StringVar(
            value=v.submission.submitted_at if v.submission else "")
        marks_var = tk.StringVar(
            value=str(v.submission.marks) if v.submission and v.submission.marks is not None else "")
        feedback_var = tk.StringVar(
            value=(v.submission.feedback or "") if v.submission else "")
        ttk.Combobox(row, textvariable=status_var,
                     values=list(SUBMISSION_STATUSES),
                     state="readonly", width=16
                     ).pack(side="left", padx=2)
        ttk.Entry(row, textvariable=sub_at_var, width=18
                  ).pack(side="left", padx=2)
        ttk.Entry(row, textvariable=marks_var, width=7
                  ).pack(side="left", padx=2)
        ttk.Entry(row, textvariable=feedback_var, width=30
                  ).pack(side="left", padx=2)
        row_state[v.student_id] = {
            "status": status_var, "submitted_at": sub_at_var,
            "marks": marks_var, "feedback": feedback_var,
        }

    def save() -> None:
        payload = {sid: {k: v.get() for k, v in vs.items()}
                   for sid, vs in row_state.items()}
        try:
            n = data.save_submissions(assignment_id, payload)
        except ValidationError as e:
            messagebox.showerror("Cannot save", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("save_submissions crashed")
            messagebox.showerror("Error", f"Unexpected: {e}", parent=gui.root)
            return
        gui.status_var.set(f"Saved {n} submission(s)")
        messagebox.showinfo("Saved", f"Saved {n} row(s).", parent=gui.root)

    actions = ttk.Frame(frame)
    actions.pack(anchor="w", pady=(12, 0))
    ttk.Button(actions, text="Save", command=save).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Back", command=lambda: open_directory(gui)
               ).pack(side="left")


# ─── Summary tab ────────────────────────────────────────────────────

def _build_summary_tab(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))

    groups = cg_data.list_groups()
    courses_by_id = {c.course_id: c for c in course_data.list_courses()}
    group_labels = [_group_label(g, courses_by_id.get(g.course_id))
                    for g in groups]
    group_by_label = {lbl: g.group_id for lbl, g in zip(group_labels, groups)}

    group_var = tk.StringVar(value=group_labels[0] if group_labels else "")
    type_var = tk.StringVar()
    from_var = tk.StringVar()
    to_var = tk.StringVar()

    ttk.Label(bar, text="Group:").pack(side="left")
    ttk.Combobox(bar, textvariable=group_var, values=group_labels,
                 state="readonly", width=40).pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="Type:").pack(side="left")
    ttk.Combobox(bar, textvariable=type_var,
                 values=["", *ASSIGNMENT_TYPES], state="readonly", width=14
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="Due from:").pack(side="left")
    ttk.Entry(bar, textvariable=from_var, width=12).pack(side="left", padx=(4, 8))
    ttk.Label(bar, text="to:").pack(side="left")
    ttk.Entry(bar, textvariable=to_var, width=12).pack(side="left", padx=(4, 12))

    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)

    def render() -> None:
        for w in holder.winfo_children():
            w.destroy()
        gid = group_by_label.get(group_var.get())
        if gid is None:
            ttk.Label(holder, text="Pick a group.",
                      foreground="#a33").pack(anchor="w")
            return
        try:
            per_student = data.per_student_summary_for_group(
                gid,
                type=type_var.get().strip() or None,
                due_from=from_var.get().strip() or None,
                due_to=to_var.get().strip() or None,
            )
        except ValidationError as e:
            ttk.Label(holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return
        except Exception as e:
            logger.exception("summary failed")
            ttk.Label(holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        students_index = {s.student_id: s for s in student_data.list_students()}

        cols = ("student_id", "name", "total", "submitted", "late",
                "missing", "excused", "rate", "avg")
        headings = {
            "student_id": ("Student ID", 110),
            "name":       ("Name",       220),
            "total":      ("Total",       60),
            "submitted":  ("Subm.",       60),
            "late":       ("Late",        50),
            "missing":    ("Missing",     70),
            "excused":    ("Excused",     70),
            "rate":       ("Rate %",      70),
            "avg":        ("Avg mark %",  90),
        }
        tree = ttk.Treeview(holder, columns=cols, show="headings", height=14)
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        for sid, s in sorted(per_student.items()):
            student = students_index.get(sid)
            name = student.full_name if student else "(deleted)"
            tree.insert("", "end", iid=sid, values=(
                sid, name, s.total, s.submitted, s.late,
                s.not_submitted, s.excused,
                f"{s.submission_rate}%" if s.submission_rate is not None else "—",
                f"{s.avg_pct}%" if s.avg_pct is not None else "—",
            ))
        gui.status_var.set("Homework summary loaded")

    ttk.Button(bar, text="Show", command=render
               ).pack(side="left", padx=(8, 0))
    if group_labels:
        render()
    else:
        ttk.Label(holder, text="No class groups yet.",
                  foreground="#a33").pack(anchor="w")
