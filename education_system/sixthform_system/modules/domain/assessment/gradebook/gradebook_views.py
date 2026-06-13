"""GUI panels for the Sixth Form Gradebook.

Three-tab Notebook:

  * Class summary — pick a group → per-student row (marked / avg% /
    best / worst).
  * Detail (per student) — pick group + student → list every
    assignment with marks, pct, letter.
  * Boundaries — pick an assignment → set / clear per-letter raw mark
    thresholds. Blank means "use percentage default".
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any
from education_system.sixthform_system.modules.domain.academics.class_groups import class_groups
from education_system.sixthform_system.modules.domain.academics.courses import courses
from education_system.sixthform_system.modules.domain.assessment.gradebook import gradebook
from education_system.sixthform_system.modules.domain.academics.homework import homework
from education_system.sixthform_system.modules.domain.academics.class_groups import class_groups as cg_data
from education_system.sixthform_system.modules.domain.academics.courses import courses as course_data
from education_system.sixthform_system.modules.domain.assessment.gradebook import gradebook as data
from education_system.sixthform_system.modules.domain.academics.homework import homework as hw_data
from education_system.sixthform_system.modules.domain.students.students import students as student_data
from education_system.sixthform_system.modules.domain.assessment.gradebook.gradebook import (
    LETTER_GRADES,
    GradedSubmission,
    StudentGradebookSummary,
    ValidationError,
)
from education_system.sixthform_system.modules.domain.academics.homework.homework import ASSIGNMENT_TYPES

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


# ── Top-level tabbed view ───────────────────────────────────────────

def open_directory(gui) -> None:
    frame = _clear(gui)
    _heading(frame, "Gradebook")

    nb = ttk.Notebook(frame)
    nb.pack(fill="both", expand=True)

    summary_tab = ttk.Frame(nb, padding=8)
    detail_tab = ttk.Frame(nb, padding=8)
    bounds_tab = ttk.Frame(nb, padding=8)
    nb.add(summary_tab, text="Class summary")
    nb.add(detail_tab,  text="Per-student detail")
    nb.add(bounds_tab,  text="Boundaries")

    _build_summary_tab(gui, summary_tab)
    _build_detail_tab(gui, detail_tab)
    _build_boundaries_tab(gui, bounds_tab)


# ─── Class summary tab ──────────────────────────────────────────────

def _build_summary_tab(gui, parent: ttk.Frame) -> None:
    groups = cg_data.list_groups()
    courses_by_id = {c.course_id: c for c in course_data.list_courses()}
    group_labels = [_group_label(g, courses_by_id.get(g.course_id))
                    for g in groups]
    group_by_label = {lbl: g.group_id for lbl, g in zip(group_labels, groups)}

    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))

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

    table_holder = ttk.Frame(parent)
    table_holder.pack(fill="both", expand=True)
    info_label = ttk.Label(parent, text="", foreground="#555")
    info_label.pack(anchor="w", pady=(8, 0))

    def render() -> None:
        for w in table_holder.winfo_children():
            w.destroy()
        gid = group_by_label.get(group_var.get())
        if gid is None:
            ttk.Label(table_holder, text="Pick a group.",
                      foreground="#a33").pack(anchor="w")
            return
        try:
            _assns, sts, _cells = data.group_matrix(
                gid,
                type=type_var.get().strip() or None,
                due_from=from_var.get().strip() or None,
                due_to=to_var.get().strip() or None,
            )
        except ValidationError as e:
            ttk.Label(table_holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return
        except Exception as e:
            logger.exception("group_matrix failed")
            ttk.Label(table_holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        cols = ("student_id", "name", "total", "marked",
                "avg", "best", "worst")
        headings = {
            "student_id": ("Student ID", 110),
            "name":       ("Name",       240),
            "total":      ("Total",       60),
            "marked":     ("Marked",      60),
            "avg":        ("Avg %",       70),
            "best":       ("Best",        60),
            "worst":      ("Worst",       60),
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

        # Use student_summary per row so the avg/best/worst respect the
        # type / due filters (group_matrix() already filters but we
        # recompute here so the row figures match what the user sees).
        for student in sts:
            summ = data.student_summary(student.student_id, group_id=gid)
            tree.insert("", "end", iid=student.student_id, values=(
                student.student_id, student.full_name,
                summ.total_assignments, summ.marked,
                f"{summ.avg_pct}%" if summ.avg_pct is not None else "—",
                summ.best_letter or "—",
                summ.worst_letter or "—",
            ))
        info_label.configure(
            text=f"{len(sts)} student(s) — double-click a row for per-student detail."
        )
        gui.status_var.set("Gradebook summary loaded")

        def _open_detail(_evt=None) -> None:
            sel = tree.selection()
            if not sel:
                return
            open_student_detail(gui, gid, sel[0])

        tree.bind("<Double-1>", _open_detail)

    ttk.Button(bar, text="Show", command=render
               ).pack(side="left", padx=(8, 0))
    if group_labels:
        render()
    else:
        ttk.Label(table_holder, text="No class groups yet.",
                  foreground="#a33").pack(anchor="w")


# ─── Per-student detail tab ────────────────────────────────────────

def _build_detail_tab(gui, parent: ttk.Frame) -> None:
    groups = cg_data.list_groups()
    courses_by_id = {c.course_id: c for c in course_data.list_courses()}
    group_labels = [""] + [_group_label(g, courses_by_id.get(g.course_id))
                           for g in groups]
    group_by_label = {_group_label(g, courses_by_id.get(g.course_id)): g.group_id
                      for g in groups}

    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))

    group_var = tk.StringVar()
    student_var = tk.StringVar()

    ttk.Label(bar, text="Group (optional):").pack(side="left")
    group_combo = ttk.Combobox(bar, textvariable=group_var,
                                values=group_labels, state="readonly",
                                width=40)
    group_combo.pack(side="left", padx=(4, 12))

    ttk.Label(bar, text="Student:").pack(side="left")
    student_combo = ttk.Combobox(bar, textvariable=student_var,
                                  state="readonly", width=42)
    student_combo.pack(side="left", padx=(4, 4))

    student_by_label: dict[str, str] = {}

    def _refresh_student_list(*_a) -> None:
        nonlocal student_by_label
        gid = group_by_label.get(group_var.get())
        if gid is None:
            all_students = student_data.list_students()
        else:
            members = cg_data.list_members(gid)
            mset = set(members)
            all_students = [s for s in student_data.list_students()
                            if s.student_id in mset]
        labels = [f"{s.student_id} — {s.full_name}" for s in all_students]
        student_by_label = {lbl: s.student_id
                            for lbl, s in zip(labels, all_students)}
        student_combo.configure(values=labels)
        student_var.set("")

    group_var.trace_add("write", _refresh_student_list)
    _refresh_student_list()

    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)
    summary_label = ttk.Label(parent, text="", foreground="#333")
    summary_label.pack(anchor="w", pady=(8, 0))

    def render() -> None:
        for w in holder.winfo_children():
            w.destroy()
        sid = student_by_label.get(student_var.get())
        if not sid:
            ttk.Label(holder, text="Pick a student.",
                      foreground="#a33").pack(anchor="w")
            summary_label.configure(text="")
            return

        gid = group_by_label.get(group_var.get())
        try:
            rows = data.graded_submissions_for_student(sid)
            if gid is not None:
                rows = [r for r in rows
                        if r.assignment_id in
                        {a.assignment_id for a in hw_data.list_assignments(
                            group_id=gid)}]
            summ = data.student_summary(sid, group_id=gid)
        except Exception as e:
            logger.exception("student detail load failed")
            ttk.Label(holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        cols = ("assignment_id", "title", "type", "due_date",
                "marks", "pct", "letter")
        headings = {
            "assignment_id": ("#",        50),
            "title":         ("Title",   240),
            "type":          ("Type",    110),
            "due_date":      ("Due",     100),
            "marks":         ("Marks",    80),
            "pct":           ("%",        70),
            "letter":        ("Letter",   70),
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

        for r in rows:
            mark_disp = (f"{r.marks}/{r.max_marks}"
                         if r.marks is not None and r.max_marks else
                         (str(r.marks) if r.marks is not None else "—"))
            tree.insert("", "end", iid=str(r.assignment_id), values=(
                r.assignment_id, r.title, r.type, r.due_date,
                mark_disp,
                f"{r.percentage}%" if r.percentage is not None else "—",
                r.letter or "—",
            ))

        summary_label.configure(text=(
            f"Total assignments: {summ.total_assignments}  ·  "
            f"Marked: {summ.marked}  ·  "
            f"Avg: {summ.avg_pct}%" if summ.avg_pct is not None else
            f"Total assignments: {summ.total_assignments}  ·  "
            f"Marked: {summ.marked}  ·  Avg: —"
        ) + (
            f"  ·  Best: {summ.best_letter}  ·  Worst: {summ.worst_letter}"
            if summ.best_letter else ""
        ))
        gui.status_var.set(f"Gradebook detail: {sid}")

    ttk.Button(bar, text="Show", command=render
               ).pack(side="left", padx=(8, 0))


def open_student_detail(gui, group_id: int | None, student_id: str) -> None:
    """Open the detail tab pre-filled. Convenience for double-click flows."""
    frame = _clear(gui)
    _heading(frame, f"Gradebook — {student_id}")

    student = student_data.get_student(student_id)
    if student is None:
        ttk.Label(frame, text=f"No such student: {student_id}",
                  foreground="#a33").pack(anchor="w")
        return

    try:
        rows = data.graded_submissions_for_student(student_id)
        if group_id is not None:
            ids = {a.assignment_id for a in hw_data.list_assignments(
                group_id=group_id)}
            rows = [r for r in rows if r.assignment_id in ids]
        summ = data.student_summary(student_id, group_id=group_id)
    except Exception as e:
        logger.exception("student detail failed")
        ttk.Label(frame, text=f"Error: {e}",
                  foreground="#a33").pack(anchor="w")
        return

    ttk.Label(frame,
              text=f"{student.full_name} ({student.student_id})",
              font=("", 12, "bold")).pack(anchor="w")
    avg = f"{summ.avg_pct}%" if summ.avg_pct is not None else "—"
    extras = (f"  ·  Best: {summ.best_letter}  ·  Worst: {summ.worst_letter}"
              if summ.best_letter else "")
    ttk.Label(
        frame,
        text=(f"Marked {summ.marked}/{summ.total_assignments}  ·  "
              f"Average: {avg}{extras}"),
        foreground="#555",
    ).pack(anchor="w", pady=(0, 8))

    holder = ttk.Frame(frame)
    holder.pack(fill="both", expand=True)

    cols = ("assignment_id", "title", "type", "due_date",
            "marks", "pct", "letter")
    headings = {
        "assignment_id": ("#",        50),
        "title":         ("Title",   240),
        "type":          ("Type",    110),
        "due_date":      ("Due",     100),
        "marks":         ("Marks",    80),
        "pct":           ("%",        70),
        "letter":        ("Letter",   70),
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

    for r in rows:
        mark_disp = (f"{r.marks}/{r.max_marks}"
                     if r.marks is not None and r.max_marks else
                     (str(r.marks) if r.marks is not None else "—"))
        tree.insert("", "end", iid=str(r.assignment_id), values=(
            r.assignment_id, r.title, r.type, r.due_date,
            mark_disp,
            f"{r.percentage}%" if r.percentage is not None else "—",
            r.letter or "—",
        ))

    ttk.Button(frame, text="Back to Gradebook",
               command=lambda: open_directory(gui)
               ).pack(anchor="w", pady=(12, 0))


# ─── Boundaries tab ─────────────────────────────────────────────────

def _build_boundaries_tab(gui, parent: ttk.Frame) -> None:
    assns = hw_data.list_assignments()
    courses_by_id = {c.course_id: c for c in course_data.list_courses()}
    groups_by_id = {g.group_id: g for g in cg_data.list_groups()}

    def _assn_label(a) -> str:
        g = groups_by_id.get(a.group_id)
        code = (courses_by_id.get(g.course_id).course_code
                if g and g.course_id in courses_by_id else "—")
        return (f"#{a.assignment_id}  {a.title[:36]}  "
                f"({code}, max {a.max_marks if a.max_marks is not None else '—'})")

    assn_labels = [_assn_label(a) for a in assns]
    assn_by_label = {lbl: a.assignment_id for lbl, a in zip(assn_labels, assns)}

    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))
    assn_var = tk.StringVar(value=assn_labels[0] if assn_labels else "")
    ttk.Label(bar, text="Assignment:").pack(side="left")
    ttk.Combobox(bar, textvariable=assn_var, values=assn_labels,
                 state="readonly", width=58
                 ).pack(side="left", padx=(4, 12))

    body = ttk.Frame(parent)
    body.pack(anchor="w", fill="x", pady=(0, 8))
    status = ttk.Label(parent, text="", foreground="#555")
    status.pack(anchor="w", pady=(8, 0))

    vars_: dict[str, tk.StringVar] = {
        "A*": tk.StringVar(), "A": tk.StringVar(), "B": tk.StringVar(),
        "C": tk.StringVar(),  "D": tk.StringVar(), "E": tk.StringVar(),
    }

    def _render_form() -> None:
        for w in body.winfo_children():
            w.destroy()
        aid = assn_by_label.get(assn_var.get())
        if aid is None:
            ttk.Label(body, text="Pick an assignment.",
                      foreground="#a33").pack(anchor="w")
            return
        a = hw_data.get_assignment(aid)
        if a is None:
            return
        bounds = data.get_boundaries(aid)
        bdict = bounds.as_dict() if bounds else {l: None for l in LETTER_GRADES[:-1]}
        for letter, var in vars_.items():
            var.set(str(bdict.get(letter)) if bdict.get(letter) is not None else "")

        ttk.Label(
            body,
            text=(f"Max marks: {a.max_marks if a.max_marks is not None else '—'}  ·  "
                  f"Defaults: A*≥90% A≥80% B≥70% C≥60% D≥50% E≥40% (else U)"),
            foreground="#555",
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))
        ttk.Label(
            body,
            text="Leave any cell blank to use the percentage default.",
            foreground="#555",
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(0, 6))

        row = 2
        for i, letter in enumerate(("A*", "A", "B", "C", "D", "E")):
            col = (i % 3) * 2
            r = row + (i // 3)
            ttk.Label(body, text=f"{letter} ≥").grid(
                row=r, column=col, sticky="e", padx=(0, 4), pady=2)
            ttk.Entry(body, textvariable=vars_[letter], width=8).grid(
                row=r, column=col + 1, sticky="w", padx=(0, 12), pady=2)

        actions = ttk.Frame(body)
        actions.grid(row=row + 2, column=0, columnspan=6, sticky="w",
                     pady=(10, 0))

        def save() -> None:
            payload = {k: vars_[k].get() for k in vars_}
            try:
                gb = data.set_boundaries(aid, payload)
            except ValidationError as e:
                logger.warning("set_boundaries rejected: %s", e)
                messagebox.showerror("Cannot save", str(e), parent=gui.root)
                return
            except Exception as e:
                logger.exception("set_boundaries crashed")
                messagebox.showerror("Error", f"Unexpected: {e}",
                                     parent=gui.root)
                return
            gui.status_var.set(
                f"Boundaries saved for assignment #{aid}")
            status.configure(
                text=("Saved: " +
                      "  ".join(f"{k}={v}" if v is not None else f"{k}=default"
                                for k, v in gb.as_dict().items())))

        def clear() -> None:
            if not messagebox.askyesno(
                    "Clear boundaries",
                    "Revert to the default percentage thresholds?",
                    parent=gui.root):
                return
            try:
                data.clear_boundaries(aid)
            except Exception as e:
                logger.exception("clear_boundaries crashed")
                messagebox.showerror("Error", f"Unexpected: {e}",
                                     parent=gui.root)
                return
            for v in vars_.values():
                v.set("")
            gui.status_var.set("Boundaries cleared")
            status.configure(text="Reverted to percentage defaults.")

        ttk.Button(actions, text="Save",  command=save
                   ).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Clear to default", command=clear
                   ).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Reload",
                   command=_render_form).pack(side="left")

    assn_var.trace_add("write", lambda *_a: _render_form())
    if assn_labels:
        _render_form()
    else:
        ttk.Label(body, text="No assignments yet — create one first.",
                  foreground="#a33").pack(anchor="w")
