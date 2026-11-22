"""Tkinter views for authoring, reusing and scheduling coursework.

Adds a **Planning** tab to the Assignments window, itself a notebook:

* Library — the department bank, templates and cloning.
* Variants — differentiated briefs and who is on which.
* Workload — estimated hours per student per week, across subjects.
* Schedule — publishing, reminders, chasers and the calendar.
* Parents — exactly what a guardian sees.

Sibling to :mod:`assignments_workflow_views`.
"""

from __future__ import annotations
from education_system.systems.sixth_form.interfaces.gui._ui import grab_when_viewable

import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from typing import Callable

from education_system.systems.sixth_form.domain.academics.assignments import (
    assignments_catalogue as cat,
    assignments_scheduling as sched,
)
from education_system.systems.sixth_form.domain.academics.assignments import (
    store as assignments_store,
    submissions as assignments_submissions,
)
import datetime as _dt
from education_system.systems.sixth_form.domain.academics.assignments.assignments_catalogue import (
    EXAM_BOARDS,
    QUALIFICATIONS,
    VARIANT_TIERS,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)

logger = logging.getLogger(__name__)


def _names() -> dict[str, str]:
    try:
        return {s.student_id: s.full_name
                 for s in student_data.list_students()}
    except Exception:
        logger.debug("Student names unavailable", exc_info=True)
        return {}


def _teachers() -> list[str]:
    try:
        from education_system.systems.sixth_form.domain.staff import (
            staff as staff_data,
        )
        return sorted({s.full_name for s in staff_data.list_staff()
                        if s.is_active})
    except Exception:
        return []


def _fmt(value: float | None, dash: str = "—") -> str:
    return f"{value:g}" if value is not None else dash


def _tree(parent: tk.Misc, spec: list[tuple[str, str, int]],
           height: int = 12) -> ttk.Treeview:
    cols = [key for key, _, _ in spec]
    tree = ttk.Treeview(parent, columns=cols, show="headings",
                          height=height)
    for key, heading, width in spec:
        tree.heading(key, text=heading)
        tree.column(key, width=width,
                     anchor="e" if width <= 70 else "w")
    return tree


# ══ Planning tab ══════════════════════════════════════════════════

class PlanningTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Planning")
        self._selected_id: int | None = None
        self._assignments: list = []
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Assignment:").pack(side="left")
        self.assign_cb = ttk.Combobox(bar, state="readonly", width=60)
        self.assign_cb.pack(side="left", padx=(2, 8))
        self.assign_cb.bind("<<ComboboxSelected>>",
                             lambda _e: self._on_pick())
        ttk.Button(bar, text="Specification...",
                    command=self._spec).pack(side="left", padx=4)
        ttk.Button(bar, text="Run daily job",
                    command=self._daily).pack(side="right")
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right", padx=4)

        self.spec_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.spec_var,
                   foreground="#555",
                   anchor="w").pack(fill="x", padx=10, pady=(0, 4))

        self.nb = ttk.Notebook(self.frame)
        self.nb.pack(fill="both", expand=True, padx=8, pady=4)
        self.library = LibraryPane(self.nb, self)
        self.variants = VariantsPane(self.nb, self)
        self.workload = WorkloadPane(self.nb, self)
        self.schedule = SchedulePane(self.nb, self)
        self.parents = ParentsPane(self.nb, self)

    def refresh(self) -> None:
        try:
            rows = assignments_store.list_assignments()
        except Exception as e:
            messagebox.showerror("Planning", str(e))
            return
        self._assignments = rows
        labels = [f"#{a.assignment_id}  {a.title} "
                  f"({a.subject_name}, due {a.due_date or '—'})"
                  for a in rows]
        self.assign_cb.configure(values=labels)
        if rows:
            index = 0
            if self._selected_id is not None:
                index = next((i for i, a in enumerate(rows)
                               if a.assignment_id == self._selected_id),
                              0)
            self.assign_cb.current(index)
            self._selected_id = rows[index].assignment_id
        else:
            self.assign_cb.set("")
            self._selected_id = None
        self.refresh_panes()

    def _on_pick(self) -> None:
        idx = self.assign_cb.current()
        if 0 <= idx < len(self._assignments):
            self._selected_id = self._assignments[idx].assignment_id
        self.refresh_panes()

    def assignment(self):
        if self._selected_id is None:
            return None
        return assignments_store.get_assignment(self._selected_id)

    def need_assignment(self, action: str):
        a = self.assignment()
        if a is None:
            messagebox.showinfo(action, "Select an assignment first.")
        return a

    def refresh_panes(self) -> None:
        a = self.assignment()
        if a is None:
            self.spec_var.set("")
        else:
            bits = [a.spec_reference or "no specification recorded"]
            if a.objective_list:
                bits.append("AOs: " + ", ".join(a.objective_list))
            if a.qualification:
                bits.append(a.qualification)
            if a.estimated_hours:
                bits.append(f"{a.estimated_hours:g}h expected")
            bits.append("published " + (a.published_on or "not yet"))
            bits.append("reminders " + (a.reminder_days
                                         or "college default"))
            if not a.parent_visible:
                bits.append("hidden from parents")
            self.spec_var.set("   ·   ".join(bits))
        for pane in (self.library, self.variants, self.workload,
                      self.schedule, self.parents):
            try:
                pane.refresh()
            except Exception:
                logger.exception("Planning pane refresh failed")

    def _spec(self) -> None:
        a = self.need_assignment("Specification")
        if a is None:
            return
        SpecificationDialog(self.frame.winfo_toplevel(), assignment=a,
                             on_save=self.refresh)

    def _daily(self) -> None:
        if not messagebox.askyesno(
                "Daily job",
                "Publish what is due, mark missing work, send reminders "
                "and chasers, and sync the calendar?\n\n"
                "Safe to run more than once — nothing is sent twice."):
            return
        results = sched.run_daily()
        messagebox.showinfo(
            "Daily job",
            "\n".join(f"{name}: {result.message}"
                      for name, result in results.items()))
        self.refresh_panes()


# ══ Library and templates ═════════════════════════════════════════

class LibraryPane:
    def __init__(self, nb: ttk.Notebook, owner: PlanningTab) -> None:
        self.owner = owner
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Library")
        self._entries: list = []
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", pady=(6, 4))
        ttk.Label(bar, text="Subject:").pack(side="left")
        self.subject_e = ttk.Entry(bar, width=16)
        self.subject_e.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Contains:").pack(side="left")
        self.query_e = ttk.Entry(bar, width=18)
        self.query_e.pack(side="left", padx=(2, 8))
        self.templates_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Templates only",
                          variable=self.templates_var,
                          command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="Clone selected...",
                    command=self._clone).pack(side="left", padx=(16, 4))
        ttk.Button(bar, text="Save current as template",
                    command=self._save_template).pack(side="left",
                                                        padx=4)
        ttk.Button(bar, text="Share / unshare current",
                    command=self._share).pack(side="left", padx=4)

        self.tree = _tree(self.frame, [
            ("id", "#", 45), ("name", "Name", 240),
            ("subject", "Subject", 130), ("type", "Type", 110),
            ("spec", "Specification", 190),
            ("criteria", "Crit", 50), ("questions", "Qs", 45),
            ("variants", "Var", 45), ("reused", "Reused", 60),
        ], height=13)
        self.tree.tag_configure("template", background="#d8e8ff")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda _e: self._clone())

        self.summary_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.summary_var,
                   anchor="w").pack(fill="x", pady=(6, 4))

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        self._entries = cat.list_library(
            subject_name=self.subject_e.get().strip() or None,
            query=self.query_e.get().strip() or None,
            templates_only=self.templates_var.get())
        for entry in self._entries:
            a = entry.assignment
            self.tree.insert("", "end", iid=str(a.assignment_id),
                              values=(
                a.assignment_id, entry.label, a.subject_name,
                a.assignment_type, a.spec_reference or "—",
                entry.criteria or "—", entry.questions or "—",
                entry.variants or "—", a.times_reused or "—",
            ), tags=("template",) if a.is_template else ())
        self.summary_var.set(
            f"{len(self._entries)} shared assignment(s), most-reused "
            f"first. Cloning copies the design — never students, "
            f"submissions or marks.")

    def _selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Library",
                                  "Select a library entry first.")
            return None
        return assignments_store.get_assignment(int(sel[0]))

    def _clone(self) -> None:
        source = self._selected()
        if source is None:
            return
        CloneDialog(self.frame.winfo_toplevel(), source=source,
                     on_save=self.owner.refresh)

    def _save_template(self) -> None:
        a = self.owner.need_assignment("Template")
        if a is None:
            return
        TemplateDialog(self.frame.winfo_toplevel(), assignment=a,
                        on_save=self.owner.refresh)

    def _share(self) -> None:
        a = self.owner.need_assignment("Share")
        if a is None:
            return
        now = a.shared_with_department
        if not messagebox.askyesno(
                "Share",
                f"#{a.assignment_id} is currently "
                f"{'shared' if now else 'not shared'} with the "
                f"department.\n\nTurn sharing {'off' if now else 'on'}?"):
            return
        cat.share_with_department(a.assignment_id, shared=not now)
        self.owner.refresh()


class SpecificationDialog:
    def __init__(self, parent: tk.Misc, *, assignment,
                 on_save: Callable[[], None]) -> None:
        self.assignment = assignment
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Specification — #{assignment.assignment_id}")
        self.win.geometry("620x400")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        a = assignment

        ttk.Label(form, text="Qualification:").grid(row=0, column=0,
                                                       sticky="e",
                                                       pady=4)
        self.qual_cb = ttk.Combobox(form, values=("",) + QUALIFICATIONS,
                                      width=24)
        self.qual_cb.set(a.qualification or "")
        self.qual_cb.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Exam board:").grid(row=1, column=0,
                                                    sticky="e", pady=4)
        self.board_cb = ttk.Combobox(form, values=("",) + EXAM_BOARDS,
                                       width=24)
        self.board_cb.set(a.exam_board or "")
        self.board_cb.grid(row=1, column=1, sticky="w", padx=6)

        for row, (label, attr) in enumerate(
                (("Spec code:", "spec_code"),
                 ("Unit code:", "unit_code"),
                 ("Component code:", "component_code")), start=2):
            ttk.Label(form, text=label).grid(row=row, column=0,
                                                sticky="e", pady=4)
            entry = ttk.Entry(form, width=20)
            value = getattr(a, attr)
            if value:
                entry.insert(0, value)
            entry.grid(row=row, column=1, sticky="w", padx=6)
            setattr(self, f"{attr}_e", entry)

        ttk.Label(form, text="Objectives:").grid(row=5, column=0,
                                                    sticky="e", pady=4)
        self.objectives_e = ttk.Entry(form, width=40)
        if a.assessment_objectives:
            self.objectives_e.insert(0, a.assessment_objectives)
        self.objectives_e.grid(row=5, column=1, sticky="w", padx=6)
        ttk.Label(form,
                   text="comma separated, e.g. AO1,AO2",
                   foreground="#555").grid(row=5, column=2, sticky="w")

        ttk.Label(form, text="Estimated hours:").grid(row=6, column=0,
                                                         sticky="e",
                                                         pady=4)
        self.hours_e = ttk.Entry(form, width=10)
        if a.estimated_hours is not None:
            self.hours_e.insert(0, _fmt(a.estimated_hours, ""))
        self.hours_e.grid(row=6, column=1, sticky="w", padx=6)

        ttk.Label(
            form,
            text="Recording the specification is what lets you ask\n"
                 "later which assessment objectives the cohort has\n"
                 "never actually been assessed on.",
            foreground="#555").grid(row=7, column=1, columnspan=2,
                                      sticky="w", pady=(10, 0))

        bar = ttk.Frame(form)
        bar.grid(row=8, column=0, columnspan=3, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            cat.set_specification(
                self.assignment.assignment_id,
                qualification=self.qual_cb.get().strip() or None,
                exam_board=self.board_cb.get().strip() or None,
                spec_code=self.spec_code_e.get().strip() or None,
                unit_code=self.unit_code_e.get().strip() or None,
                component_code=(self.component_code_e.get().strip()
                                 or None),
                objectives=self.objectives_e.get().strip() or None)
            assignments_store.update_assignment(
                self.assignment.assignment_id,
                {"estimated_hours": self.hours_e.get().strip() or None})
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class TemplateDialog:
    def __init__(self, parent: tk.Misc, *, assignment,
                 on_save: Callable[[], None]) -> None:
        self.assignment = assignment
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Save as template")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="Template name:").grid(row=0, column=0,
                                                       sticky="e",
                                                       pady=4)
        self.name_e = ttk.Entry(form, width=40)
        self.name_e.insert(0, assignment.template_name
                            or assignment.title)
        self.name_e.grid(row=0, column=1, sticky="w", padx=6)
        self.share_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(form, text="Share with the department",
                          variable=self.share_var).grid(
            row=1, column=1, sticky="w", padx=6, pady=(6, 0))
        ttk.Label(
            form,
            text="The original keeps its students and marks — this only\n"
                 "says the design is worth using again.",
            foreground="#555").grid(row=2, column=1, sticky="w", padx=6,
                                      pady=(8, 0))
        bar = ttk.Frame(form)
        bar.grid(row=3, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            cat.save_as_template(self.assignment.assignment_id,
                                  template_name=self.name_e.get().strip(),
                                  share=self.share_var.get())
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class CloneDialog:
    def __init__(self, parent: tk.Misc, *, source,
                 on_save: Callable[[], None]) -> None:
        self.source = source
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Clone #{source.assignment_id}")
        self.win.geometry("620x440")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)

        ttk.Label(form, text=f"From: {source.title}",
                   font=("", 10, "bold")).grid(row=0, column=0,
                                                 columnspan=2,
                                                 sticky="w",
                                                 pady=(0, 8))
        ttk.Label(form, text="New title:").grid(row=1, column=0,
                                                   sticky="e", pady=4)
        self.title_e = ttk.Entry(form, width=44)
        self.title_e.insert(0, f"{source.title} (copy)")
        self.title_e.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Set date:").grid(row=2, column=0,
                                                  sticky="e", pady=4)
        self.set_e = ttk.Entry(form, width=14)
        self.set_e.insert(0, _dt.date.today().isoformat())
        self.set_e.grid(row=2, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Due date:").grid(row=3, column=0,
                                                  sticky="e", pady=4)
        self.due_e = ttk.Entry(form, width=14)
        self.due_e.grid(row=3, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Teacher:").grid(row=4, column=0,
                                                 sticky="e", pady=4)
        self.teacher_cb = ttk.Combobox(
            form, values=("",) + tuple(_teachers()), width=28)
        self.teacher_cb.set(source.teacher or "")
        self.teacher_cb.grid(row=4, column=1, sticky="w", padx=6)

        self.rubric_var = tk.BooleanVar(value=True)
        self.questions_var = tk.BooleanVar(value=True)
        self.variants_var = tk.BooleanVar(value=True)
        self.files_var = tk.BooleanVar(value=True)
        for row, (text, var) in enumerate(
                (("Copy the rubric and grade boundaries",
                  self.rubric_var),
                 ("Copy objective questions", self.questions_var),
                 ("Copy differentiated variants", self.variants_var),
                 ("Copy teaching material (files)", self.files_var)),
                start=5):
            ttk.Checkbutton(form, text=text, variable=var).grid(
                row=row, column=1, sticky="w", padx=6)

        ttk.Label(
            form,
            text="Students, submissions, marks and files handed in are\n"
                 "never copied — a new run starts empty.",
            foreground="#555").grid(row=9, column=1, sticky="w", padx=6,
                                      pady=(10, 0))

        bar = ttk.Frame(form)
        bar.grid(row=10, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Clone",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            result = cat.clone_assignment(
                self.source.assignment_id,
                title=self.title_e.get().strip(),
                set_date=self.set_e.get().strip() or None,
                due_date=self.due_e.get().strip() or None,
                teacher=self.teacher_cb.get().strip() or None,
                copy_rubric=self.rubric_var.get(),
                copy_questions=self.questions_var.get(),
                copy_variants=self.variants_var.get(),
                copy_attachments=self.files_var.get())
        except Exception as e:
            messagebox.showerror("Clone failed", str(e))
            return
        messagebox.showinfo("Cloned", result.message)
        self.win.destroy()
        self.on_save()


# ══ Variants ══════════════════════════════════════════════════════

class VariantsPane:
    def __init__(self, nb: ttk.Notebook, owner: PlanningTab) -> None:
        self.owner = owner
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Variants")
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", pady=(6, 4))
        ttk.Button(bar, text="Add variant",
                    command=self._add).pack(side="left")
        ttk.Button(bar, text="Delete variant",
                    command=self._delete).pack(side="left", padx=4)
        ttk.Button(bar, text="Issue to student...",
                    command=self._issue).pack(side="left", padx=(16, 4))
        ttk.Button(bar, text="Apply default to all",
                    command=self._defaults).pack(side="left", padx=4)

        panes = ttk.Panedwindow(self.frame, orient="horizontal")
        panes.pack(fill="both", expand=True)
        left = ttk.Frame(panes)
        panes.add(left, weight=2)
        right = ttk.Frame(panes)
        panes.add(right, weight=3)

        self.tree = _tree(left, [
            ("id", "#", 45), ("name", "Variant", 150),
            ("tier", "Tier", 100), ("max", "Max", 55),
            ("hours", "Hours", 55), ("default", "Default", 60),
        ], height=12)
        self.tree.pack(fill="both", expand=True)

        self.students = _tree(right, [
            ("id", "Sub", 45), ("student", "Student", 80),
            ("name", "Name", 150), ("variant", "Variant", 160),
            ("hours", "Hours", 55),
        ], height=12)
        self.students.pack(fill="both", expand=True)

        self.summary_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.summary_var,
                   anchor="w").pack(fill="x", pady=(6, 4))

    def refresh(self) -> None:
        for tree in (self.tree, self.students):
            for i in tree.get_children():
                tree.delete(i)
        a = self.owner.assignment()
        if a is None:
            self.summary_var.set("")
            return
        variants = {v.variant_id: v
                    for v in cat.list_variants(a.assignment_id)}
        for v in variants.values():
            self.tree.insert("", "end", iid=str(v.variant_id), values=(
                v.variant_id, v.name, v.tier, _fmt(v.max_marks),
                _fmt(v.estimated_hours),
                "yes" if v.is_default else "—"))
        names = _names()
        for sub in assignments_store.list_submissions(assignment_id=a.assignment_id):
            v = variants.get(sub.variant_id or -1)
            self.students.insert("", "end", iid=str(sub.submission_id),
                                  values=(
                sub.submission_id, sub.student_id,
                names.get(sub.student_id, "?"),
                v.label if v else "(base brief)",
                _fmt(cat.submission_hours(sub, a)),
            ))
        self.summary_var.set(
            f"{len(variants)} variant(s)  ·  spread "
            f"{cat.variant_spread(a.assignment_id)}")

    def _add(self) -> None:
        a = self.owner.need_assignment("Variants")
        if a is None:
            return
        VariantDialog(self.frame.winfo_toplevel(), assignment=a,
                       on_save=self.owner.refresh_panes)

    def _delete(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Variants", "Select a variant first.")
            return
        if not messagebox.askyesno(
                "Delete",
                "Delete this variant?\n\nStudents on it fall back to "
                "the base brief."):
            return
        cat.delete_variant(int(sel[0]))
        self.owner.refresh_panes()

    def _issue(self) -> None:
        a = self.owner.need_assignment("Variants")
        if a is None:
            return
        sel = self.students.selection()
        if not sel:
            messagebox.showinfo("Variants", "Select a student first.")
            return
        IssueVariantDialog(self.frame.winfo_toplevel(), assignment=a,
                            submission_id=int(sel[0]),
                            on_save=self.owner.refresh_panes)

    def _defaults(self) -> None:
        a = self.owner.need_assignment("Variants")
        if a is None:
            return
        n = cat.assign_default_variants(a.assignment_id)
        messagebox.showinfo(
            "Variants",
            f"{n} student(s) put on the default variant."
            if n else "Nothing to do — no default variant, or "
                      "everyone already has one.")
        self.owner.refresh_panes()


class VariantDialog:
    def __init__(self, parent: tk.Misc, *, assignment,
                 on_save: Callable[[], None]) -> None:
        self.assignment = assignment
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Add variant")
        self.win.geometry("600x440")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)

        ttk.Label(form, text="Name:").grid(row=0, column=0, sticky="e",
                                              pady=4)
        self.name_e = ttk.Entry(form, width=28)
        self.name_e.grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Tier:").grid(row=0, column=2, sticky="e",
                                              pady=4)
        self.tier_cb = ttk.Combobox(form, values=VARIANT_TIERS,
                                      state="readonly", width=14)
        self.tier_cb.set(cat.DEFAULT_VARIANT_TIER)
        self.tier_cb.grid(row=0, column=3, sticky="w", padx=6)

        ttk.Label(form, text="Max marks:").grid(row=1, column=0,
                                                   sticky="e", pady=4)
        self.max_e = ttk.Entry(form, width=10)
        self.max_e.grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Hours:").grid(row=1, column=2, sticky="e",
                                               pady=4)
        self.hours_e = ttk.Entry(form, width=10)
        self.hours_e.grid(row=1, column=3, sticky="w", padx=6)

        self.default_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(form, text="Make this the default variant",
                          variable=self.default_var).grid(
            row=2, column=1, columnspan=3, sticky="w", padx=6)

        ttk.Label(form, text="Brief:").grid(row=3, column=0, sticky="ne",
                                               pady=4)
        self.brief = tk.Text(form, width=56, height=12, wrap="word")
        self.brief.grid(row=3, column=1, columnspan=3, sticky="w",
                          padx=6)
        ttk.Label(
            form,
            text="Leave the brief blank to use the assignment's own.",
            foreground="#555").grid(row=4, column=1, columnspan=3,
                                      sticky="w", padx=6, pady=(6, 0))

        bar = ttk.Frame(form)
        bar.grid(row=5, column=0, columnspan=4, pady=(12, 0))
        ttk.Button(bar, text="Add",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            cat.add_variant(self.assignment.assignment_id, {
                "name": self.name_e.get().strip(),
                "tier": self.tier_cb.get(),
                "brief": self.brief.get("1.0", "end").strip(),
                "max_marks": self.max_e.get().strip() or None,
                "estimated_hours": self.hours_e.get().strip() or None,
                "is_default": self.default_var.get()})
        except Exception as e:
            messagebox.showerror("Add failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class IssueVariantDialog:
    def __init__(self, parent: tk.Misc, *, assignment,
                 submission_id: int,
                 on_save: Callable[[], None]) -> None:
        self.submission_id = submission_id
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Issue a variant")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        self._variants = cat.list_variants(assignment.assignment_id)
        ttk.Label(form, text="Variant:").grid(row=0, column=0,
                                                 sticky="e", pady=4)
        self.cb = ttk.Combobox(
            form, state="readonly", width=36,
            values=["(base brief)"] + [v.label
                                        for v in self._variants])
        self.cb.current(0)
        self.cb.grid(row=0, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=1, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Issue",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        idx = self.cb.current()
        variant_id = (None if idx <= 0
                      else self._variants[idx - 1].variant_id)
        try:
            cat.assign_variant(self.submission_id, variant_id)
        except Exception as e:
            messagebox.showerror("Issue failed", str(e))
            return
        self.win.destroy()
        self.on_save()


# ══ Workload ══════════════════════════════════════════════════════

class WorkloadPane:
    def __init__(self, nb: ttk.Notebook, owner: PlanningTab) -> None:
        self.owner = owner
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Workload")
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", pady=(6, 4))
        ttk.Label(bar, text="Year group:").pack(side="left")
        self.year_e = ttk.Entry(bar, width=12)
        self.year_e.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Heavy above (h):").pack(side="left")
        self.threshold_e = ttk.Entry(bar, width=6)
        self.threshold_e.insert(0, f"{cat.WEEKLY_HOURS_WARNING:g}")
        self.threshold_e.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left")

        self.tree = _tree(self.frame, [
            ("student", "Student", 80), ("name", "Name", 160),
            ("total", "Total h", 65), ("weeks", "Weeks", 55),
            ("heaviest", "Heaviest week", 120),
            ("peak", "Peak h", 60), ("detail", "That week", 340),
        ], height=14)
        self.tree.tag_configure("heavy", background="#ffd0d0")
        self.tree.pack(fill="both", expand=True)

        self.summary_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.summary_var,
                   anchor="w").pack(fill="x", pady=(6, 4))

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            threshold = float(self.threshold_e.get().strip() or
                               cat.WEEKLY_HOURS_WARNING)
        except ValueError:
            threshold = cat.WEEKLY_HOURS_WARNING
        names = _names()
        reports = cat.cohort_workload(
            year_group=self.year_e.get().strip() or None)
        heavy = 0
        for student_id, report in reports.items():
            if not report.weeks:
                continue
            peak = report.heaviest
            assert peak is not None
            is_heavy = peak.hours > threshold
            if is_heavy:
                heavy += 1
            detail = ", ".join(f"{t[:18]} {h:g}h"
                                for _a, t, h in peak.assignments)
            self.tree.insert("", "end", iid=student_id, values=(
                student_id, names.get(student_id, "?"),
                f"{report.total_hours:g}", len(report.weeks),
                peak.week_start, f"{peak.hours:g}", detail,
            ), tags=("heavy",) if is_heavy else ())
        self.summary_var.set(
            f"{len(reports)} student(s) with estimated hours  ·  "
            f"{heavy} over {threshold:g}h in a single week. Hours land "
            f"in the week the work is due.")


# ══ Schedule ══════════════════════════════════════════════════════

class SchedulePane:
    def __init__(self, nb: ttk.Notebook, owner: PlanningTab) -> None:
        self.owner = owner
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Schedule")
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", pady=(6, 4))
        ttk.Button(bar, text="Publish now",
                    command=self._publish).pack(side="left")
        ttk.Button(bar, text="Run scheduled publishing",
                    command=self._publish_due).pack(side="left", padx=4)
        ttk.Button(bar, text="Send reminders",
                    command=self._reminders).pack(side="left", padx=(16, 4))
        ttk.Button(bar, text="Chase missing work",
                    command=self._chase).pack(side="left", padx=4)
        ttk.Button(bar, text="Sync calendar",
                    command=self._calendar).pack(side="left", padx=(16, 4))
        ttk.Button(bar, text="Deadline clashes",
                    command=self._clashes).pack(side="left", padx=4)

        self.tree = _tree(self.frame, [
            ("id", "Sub", 45), ("student", "Student", 80),
            ("name", "Name", 150), ("status", "Status", 95),
            ("due", "Due", 95), ("reminders", "Reminded", 90),
            ("chase", "Chase", 90), ("chased", "Last chased", 95),
        ], height=13)
        self.tree.tag_configure("chased",  background="#ffe0b0")
        self.tree.tag_configure("escalated", background="#ffd0d0")
        self.tree.pack(fill="both", expand=True)

        self.summary_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.summary_var,
                   anchor="w").pack(fill="x", pady=(6, 4))

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        a = self.owner.assignment()
        if a is None:
            self.summary_var.set("")
            return
        names = _names()
        for sub in assignments_store.list_submissions(assignment_id=a.assignment_id):
            tags = []
            if sub.chase_level >= sched.MAX_CHASE_LEVEL:
                tags.append("escalated")
            elif sub.chase_level:
                tags.append("chased")
            self.tree.insert("", "end", iid=str(sub.submission_id),
                              values=(
                sub.submission_id, sub.student_id,
                names.get(sub.student_id, "?"), sub.status,
                assignments_submissions.effective_due_date(sub, a) or "—",
                sub.reminders_sent or "—",
                (sched.chase_level_name(sub.chase_level)
                 if sub.chase_level else "—"),
                sub.last_chased_on or "—",
            ), tags=tuple(tags))
        offsets = ", ".join(f"T-{o}"
                             for o in sched.reminder_offsets(a))
        self.summary_var.set(
            f"Published {a.published_on or 'not yet'}  ·  reminders at "
            f"{offsets}  ·  chasing "
            f"{'on' if a.chase_enabled else 'off'}  ·  calendar "
            f"{'linked' if a.calendar_event_id else 'not linked'}")

    def _publish(self) -> None:
        a = self.owner.need_assignment("Publish")
        if a is None:
            return
        if a.published_on:
            messagebox.showinfo("Publish",
                                  f"Already published on "
                                  f"{a.published_on}.")
            return
        if not messagebox.askyesno(
                "Publish",
                f"Publish #{a.assignment_id} and email the students?"):
            return
        out = sched.publish_assignment(a.assignment_id)
        messagebox.showinfo("Publish",
                              f"Published on {out.published_on} "
                              f"(status {out.status}).")
        self.owner.refresh()

    def _publish_due(self) -> None:
        result = sched.publish_due()
        messagebox.showinfo("Scheduled publishing", result.message)
        self.owner.refresh()

    def _reminders(self) -> None:
        a = self.owner.assignment()
        scope = a.assignment_id if a else None
        preview = sched.sweep_reminders(assignment_id=scope,
                                         dry_run=True)
        if not preview.scanned:
            messagebox.showinfo("Reminders",
                                  "No reminders are due right now.")
            return
        if not messagebox.askyesno(
                "Reminders",
                f"{preview.scanned} reminder(s) would go out:\n\n"
                + "\n".join(preview.detail[:10])):
            return
        result = sched.sweep_reminders(assignment_id=scope)
        messagebox.showinfo("Reminders", result.message)
        self.owner.refresh_panes()

    def _chase(self) -> None:
        a = self.owner.assignment()
        scope = a.assignment_id if a else None
        preview = sched.sweep_chasers(assignment_id=scope, dry_run=True)
        if not preview.detail:
            messagebox.showinfo(
                "Chasers",
                "Nothing to escalate right now.\n\n"
                f"({preview.scanned} scanned; escalations wait "
                f"{sched.CHASE_INTERVAL_DAYS} days between steps.)")
            return
        if not messagebox.askyesno(
                "Chasers",
                "Escalate the following?\n\n"
                + "\n".join(preview.detail[:10])):
            return
        result = sched.sweep_chasers(assignment_id=scope)
        messagebox.showinfo("Chasers", result.message)
        self.owner.refresh_panes()

    def _calendar(self) -> None:
        result = sched.sync_calendar()
        messagebox.showinfo(
            "Calendar",
            result.message
            + ("\n\n" + "\n".join(result.detail[:8])
                if result.detail else ""))
        self.owner.refresh()

    def _clashes(self) -> None:
        rows = sched.deadline_clashes()
        if not rows:
            messagebox.showinfo(
                "Clashes", "No week has more than one deadline.")
            return
        lines = []
        for clash in rows[:10]:
            lines.append(f"Week of {clash['week_start']}: "
                         f"{clash['count']} across "
                         f"{', '.join(clash['subjects'])}")
        messagebox.showinfo("Deadline clashes", "\n".join(lines))


# ══ Parents ═══════════════════════════════════════════════════════

class ParentsPane:
    def __init__(self, nb: ttk.Notebook, owner: PlanningTab) -> None:
        self.owner = owner
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Parents")
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", pady=(6, 4))
        ttk.Label(bar, text="Student:").pack(side="left")
        self.student_cb = ttk.Combobox(bar, state="readonly", width=40)
        self.student_cb.pack(side="left", padx=(2, 8))
        self.student_cb.bind("<<ComboboxSelected>>",
                              lambda _e: self._load())
        ttk.Button(bar, text="Toggle visibility of current assignment",
                    command=self._toggle).pack(side="left", padx=8)

        self.tree = _tree(self.frame, [
            ("due", "Due", 95), ("subject", "Subject", 130),
            ("title", "Title", 240), ("state", "State", 120),
            ("marks", "Marks", 90), ("grade", "Grade", 55),
            ("feedback", "Feedback", 80),
        ], height=13)
        self.tree.tag_configure("missing", background="#ffd0d0")
        self.tree.tag_configure("marked",  background="#d8f4d8")
        self.tree.pack(fill="both", expand=True)

        self.summary_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.summary_var,
                   anchor="w").pack(fill="x", pady=(6, 4))

    def refresh(self) -> None:
        names = _names()
        self._ids = sorted(names)
        self.student_cb.configure(
            values=[f"{sid} — {names[sid]}" for sid in self._ids])
        if self._ids and not self.student_cb.get():
            self.student_cb.current(0)
        self._load()

    def _load(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        idx = self.student_cb.current()
        if idx < 0 or idx >= len(getattr(self, "_ids", [])):
            self.summary_var.set("")
            return
        student_id = self._ids[idx]
        for view in sched.parent_view(student_id):
            tags = []
            if view.is_missing:
                tags.append("missing")
            elif view.marks is not None:
                tags.append("marked")
            marks = ("—" if view.marks is None
                     else f"{view.marks:g}/{_fmt(view.max_marks)}")
            self.tree.insert("", "end", values=(
                view.due_date or "—", view.subject_name, view.title,
                view.state, marks, view.grade or "—",
                "yes" if view.feedback_available else "—",
            ), tags=tuple(tags))
        summary = sched.parent_summary(student_id)
        self.summary_var.set(
            f"{summary['total']} visible  ·  {summary['handed_in']} in  "
            f"·  {summary['missing']} missing  ·  {summary['marked']} "
            f"marked. Marks appear only once released to the student.")

    def _toggle(self) -> None:
        a = self.owner.need_assignment("Parent visibility")
        if a is None:
            return
        now = a.parent_visible
        if not messagebox.askyesno(
                "Parent visibility",
                f"#{a.assignment_id} is currently "
                f"{'visible' if now else 'hidden'} to guardians.\n\n"
                f"{'Hide' if now else 'Show'} it?"):
            return
        sched.set_parent_visibility(a.assignment_id, visible=not now)
        self.owner.refresh()
