"""Tkinter views for coursework marking, moderation and rubrics.

Adds a **Marking** tab to the Assignments window: pick an assignment on
the left, then work the class in the grid on the right — per-criterion
marking, second marking, moderation, samples, penalties and the audit
trail all hang off that one selection.

Sibling to :mod:`assignments_views`, which owns the assignment,
submission and file views.
"""

from __future__ import annotations
from education_system.systems.sixth_form.interfaces.gui._ui import grab_when_viewable

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from education_system.systems.sixth_form.domain.academics.assignments import (
    assignments as data,
    assignments_marking as marking,
)
from education_system.systems.sixth_form.domain.academics.assignments.assignments_marking import (
    COMMENT_CATEGORIES,
    Criterion,
    MARKER_ROLES,
    SAMPLE_BANDS,
    ValidationError,
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


def _teacher_options() -> list[str]:
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


# ══ Marking tab ═══════════════════════════════════════════════════

class MarkingTab:
    """Assignment picker + class marking grid + every marking action."""

    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Marking")
        self._selected_id: int | None = None
        self._criteria: list[Criterion] = []
        self._build()
        self.refresh()

    # ── Layout ────────────────────────────────────────────────────
    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Assignment:").pack(side="left")
        self.assign_cb = ttk.Combobox(bar, state="readonly", width=56)
        self.assign_cb.pack(side="left", padx=(2, 8))
        self.assign_cb.bind("<<ComboboxSelected>>",
                             lambda _e: self._on_pick())

        ttk.Label(bar, text="Role:").pack(side="left")
        self.role_cb = ttk.Combobox(bar, values=MARKER_ROLES,
                                      state="readonly", width=10)
        self.role_cb.set(marking.DEFAULT_MARKER_ROLE)
        self.role_cb.pack(side="left", padx=(2, 8))
        self.role_cb.bind("<<ComboboxSelected>>",
                           lambda _e: self.refresh_grid())

        self.moderation_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Needs moderation only",
                          variable=self.moderation_var,
                          command=self.refresh_grid).pack(side="left",
                                                            padx=4)
        self.sample_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Sample only",
                          variable=self.sample_var,
                          command=self.refresh_grid).pack(side="left",
                                                            padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

        self.policy_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.policy_var,
                   foreground="#555",
                   anchor="w").pack(fill="x", padx=10, pady=(0, 4))

        table = ttk.Frame(self.frame)
        table.pack(fill="both", expand=True, padx=8, pady=4)
        self.tree = ttk.Treeview(table, show="headings")
        vs = ttk.Scrollbar(table, orient="vertical",
                            command=self.tree.yview)
        hs = ttk.Scrollbar(table, orient="horizontal",
                            command=self.tree.xview)
        self.tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)
        self.tree.tag_configure("moderate",  background="#ffe0b0")
        self.tree.tag_configure("penalised", background="#fff7d0")
        self.tree.tag_configure("sample",    background="#d8e8ff")
        self.tree.tag_configure("access",    background="#e6e0ff")
        self.tree.bind("<Double-1>", lambda _e: self._mark_criteria())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 2))
        ttk.Button(actions, text="Mark by criterion",
                    command=self._mark_criteria).pack(side="left")
        ttk.Button(actions, text="Bulk mark",
                    command=self._bulk_mark).pack(side="left", padx=4)
        ttk.Button(actions, text="Record mark",
                    command=self._record_mark).pack(side="left", padx=4)
        ttk.Button(actions, text="Moderate",
                    command=self._moderate).pack(side="left", padx=4)
        ttk.Button(actions, text="Sample",
                    command=self._sample).pack(side="left", padx=4)
        ttk.Button(actions, text="Penalty",
                    command=self._penalty).pack(side="left", padx=4)
        ttk.Button(actions, text="Audit",
                    command=self._audit).pack(side="left", padx=4)

        setup = ttk.Frame(self.frame)
        setup.pack(fill="x", padx=8, pady=(0, 6))
        ttk.Button(setup, text="Rubric...",
                    command=self._rubric).pack(side="left")
        ttk.Button(setup, text="Grade boundaries...",
                    command=self._boundaries).pack(side="left", padx=4)
        ttk.Button(setup, text="Auto-select sample",
                    command=self._auto_sample).pack(side="left", padx=4)
        ttk.Button(setup, text="Apply access arrangements",
                    command=self._apply_access).pack(side="left", padx=4)
        ttk.Button(setup, text="Comment bank...",
                    command=self._comment_bank).pack(side="left", padx=4)

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=10, pady=(0, 8))

    # ── Data ──────────────────────────────────────────────────────
    def refresh(self) -> None:
        try:
            rows = data.list_assignments()
        except Exception as e:
            messagebox.showerror("Marking", str(e))
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
                               if a.assignment_id == self._selected_id), 0)
            self.assign_cb.current(index)
            self._selected_id = rows[index].assignment_id
        else:
            self.assign_cb.set("")
            self._selected_id = None
        self.refresh_grid()

    def _on_pick(self) -> None:
        idx = self.assign_cb.current()
        if 0 <= idx < len(self._assignments):
            self._selected_id = self._assignments[idx].assignment_id
        self.refresh_grid()

    def _assignment(self):
        if self._selected_id is None:
            return None
        return data.get_assignment(self._selected_id)

    def _columns(self) -> tuple[list[str], dict[str, str], dict[str, int]]:
        cols = ["id", "student", "name", "status", "raw", "pen",
                "final", "grade", "second", "gap"]
        headings = {"id": "Sub", "student": "Student", "name": "Name",
                    "status": "Status", "raw": "Raw", "pen": "Pen %",
                    "final": "Final", "grade": "Gr",
                    "second": "2nd", "gap": "Gap"}
        widths = {"id": 45, "student": 75, "name": 150, "status": 95,
                  "raw": 55, "pen": 55, "final": 55, "grade": 45,
                  "second": 55, "gap": 45}
        for c in self._criteria:
            key = f"c{c.criterion_id}"
            cols.append(key)
            headings[key] = (c.code or c.title)[:8]
            widths[key] = 65
        cols.append("flags")
        headings["flags"] = "Notes"
        widths["flags"] = 220
        return cols, headings, widths

    def refresh_grid(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        a = self._assignment()
        if a is None:
            self.policy_var.set("")
            self.count_var.set("No assignments.")
            self.tree.configure(columns=())
            return

        self._criteria = marking.list_criteria(a.assignment_id)
        cols, headings, widths = self._columns()
        self.tree.configure(columns=cols)
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = "w" if c in ("student", "name", "status",
                                   "flags") else "e"
            self.tree.column(c, width=widths[c], anchor=anchor)
            # Only the notes column absorbs slack, so the numeric
            # columns keep their alignment as the window resizes.
            self.tree.column(c, stretch=(c == "flags"))

        policy = []
        if a.late_penalty_percent_per_day:
            text = f"Late: {a.late_penalty_percent_per_day:g}%/day"
            if a.late_penalty_grace_days:
                text += f" after {a.late_penalty_grace_days}d grace"
            if a.late_penalty_cap_percent:
                text += f", cap {a.late_penalty_cap_percent:g}%"
            policy.append(text)
        else:
            policy.append("Late: no penalty policy")
        policy.append(f"Moderation tolerance: "
                      f"{_fmt(a.moderation_tolerance, 'not set')}")
        boundaries = marking.get_grade_boundaries(a.assignment_id)
        policy.append("Boundaries: "
                      + ("pinned" if boundaries and boundaries.is_set
                          else "percentage defaults"))
        policy.append(marking.rubric_total(a.assignment_id).message)
        self.policy_var.set("   ·   ".join(policy))

        role = self.role_cb.get() or marking.DEFAULT_MARKER_ROLE
        grid = marking.marking_grid(a.assignment_id, role=role)
        shown = 0
        for g in grid:
            mod = g.moderation
            if self.moderation_var.get() and not (
                    mod and mod.needs_moderation):
                continue
            if self.sample_var.get() and not g.submission.sample_band:
                continue
            s = g.submission
            tags: list[str] = []
            flags: list[str] = []
            if s.penalty_percent:
                tags.append("penalised")
                flags.append(g.penalty.message)
            elif g.penalty.days_late:
                flags.append(g.penalty.message)
            if s.sample_band:
                tags.append("sample")
                flags.append(f"Sample: {s.sample_band}")
            if g.access_arrangements:
                tags.append("access")
                flags.append("; ".join(g.access_arrangements))
            if mod and mod.needs_moderation:
                tags.append("moderate")
                flags.append(mod.message)

            values = [s.submission_id, s.student_id, g.student_name,
                      s.status, _fmt(s.raw_marks),
                      _fmt(s.penalty_percent), _fmt(s.marks),
                      s.grade or "—",
                      _fmt(mod.second if mod else None),
                      _fmt(mod.discrepancy if mod else None)]
            for criterion in self._criteria:
                values.append(
                    _fmt(g.criterion_marks.get(criterion.criterion_id)))
            values.append(" | ".join(flags))
            self.tree.insert("", "end", iid=str(s.submission_id),
                              values=values, tags=tuple(tags))
            shown += 1

        needing = len(marking.list_for_moderation(
            assignment_id=a.assignment_id))
        self.count_var.set(
            f"{shown} of {len(grid)} student(s) shown  ·  "
            f"{sum(1 for g in grid if g.submission.marks is not None)} "
            f"marked  ·  {needing} awaiting moderation  ·  "
            f"{len(marking.list_samples(assignment_id=a.assignment_id))} "
            f"sampled")

    # ── Selection helpers ─────────────────────────────────────────
    def _selected_submission(self, action: str):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo(action, "Select a student first.")
            return None
        return data.get_submission(int(sel[0]))

    def _need_assignment(self, action: str):
        a = self._assignment()
        if a is None:
            messagebox.showinfo(action, "Select an assignment first.")
        return a

    # ── Actions ───────────────────────────────────────────────────
    def _mark_criteria(self) -> None:
        a = self._need_assignment("Mark by criterion")
        if a is None:
            return
        if not self._criteria:
            messagebox.showinfo(
                "Mark by criterion",
                "This assignment has no rubric criteria yet.\n\n"
                "Use Rubric... to build the mark scheme first.")
            return
        sub = self._selected_submission("Mark by criterion")
        if sub is None:
            return
        CriterionMarkDialog(self.frame.winfo_toplevel(), submission=sub,
                             assignment=a,
                             role=self.role_cb.get(),
                             on_save=self.refresh_grid)

    def _bulk_mark(self) -> None:
        a = self._need_assignment("Bulk mark")
        if a is None:
            return
        BulkMarkDialog(self.frame.winfo_toplevel(), assignment=a,
                        role=self.role_cb.get(),
                        on_save=self.refresh_grid)

    def _record_mark(self) -> None:
        a = self._need_assignment("Record mark")
        if a is None:
            return
        sub = self._selected_submission("Record mark")
        if sub is None:
            return
        RecordMarkDialog(self.frame.winfo_toplevel(), submission=sub,
                          assignment=a, role=self.role_cb.get(),
                          on_save=self.refresh_grid)

    def _moderate(self) -> None:
        a = self._need_assignment("Moderate")
        if a is None:
            return
        sub = self._selected_submission("Moderate")
        if sub is None:
            return
        ModerationDialog(self.frame.winfo_toplevel(), submission=sub,
                          assignment=a, on_save=self.refresh_grid)

    def _sample(self) -> None:
        sub = self._selected_submission("Sample")
        if sub is None:
            return
        SampleDialog(self.frame.winfo_toplevel(), submission=sub,
                      on_save=self.refresh_grid)

    def _penalty(self) -> None:
        a = self._need_assignment("Penalty")
        if a is None:
            return
        sub = self._selected_submission("Penalty")
        if sub is None:
            return
        PenaltyDialog(self.frame.winfo_toplevel(), submission=sub,
                       assignment=a, on_save=self.refresh_grid)

    def _audit(self) -> None:
        a = self._need_assignment("Audit")
        if a is None:
            return
        sel = self.tree.selection()
        AuditDialog(self.frame.winfo_toplevel(), assignment=a,
                     submission_id=int(sel[0]) if sel else None)

    def _rubric(self) -> None:
        a = self._need_assignment("Rubric")
        if a is None:
            return
        RubricDialog(self.frame.winfo_toplevel(), assignment=a,
                      on_save=self.refresh_grid)

    def _boundaries(self) -> None:
        a = self._need_assignment("Grade boundaries")
        if a is None:
            return
        BoundariesDialog(self.frame.winfo_toplevel(), assignment=a,
                          on_save=self.refresh_grid)

    def _auto_sample(self) -> None:
        a = self._need_assignment("Sample")
        if a is None:
            return
        if not messagebox.askyesno(
                "Auto-select sample",
                "Pick the highest, lowest and middle marks as the "
                "standardisation sample?\n\nAny existing sample flags "
                "on this assignment are replaced."):
            return
        try:
            rows = marking.auto_select_sample(a.assignment_id)
        except ValidationError as e:
            messagebox.showerror("Sample", str(e))
            return
        messagebox.showinfo(
            "Sample",
            f"Selected {len(rows)} script(s):\n\n"
            + "\n".join(f"  {s.sample_band:<8} {s.student_id}  "
                        f"{_fmt(s.marks)}" for s in rows))
        self.refresh_grid()

    def _apply_access(self) -> None:
        a = self._need_assignment("Access arrangements")
        if a is None:
            return
        if not a.honour_access_arrangements:
            messagebox.showinfo(
                "Access arrangements",
                "This assignment has access arrangements switched off.\n\n"
                "Turn them on in Edit assignment.")
            return
        result = marking.apply_access_arrangements(a.assignment_id)
        messagebox.showinfo(
            "Access arrangements",
            f"Eligible: {result['eligible']}\n"
            f"Extensions granted: {result['granted']}\n"
            f"Already extended: {result['skipped']}")
        self.refresh_grid()

    def _comment_bank(self) -> None:
        a = self._assignment()
        CommentBankDialog(self.frame.winfo_toplevel(),
                           subject_name=a.subject_name if a else None,
                           on_save=self.refresh_grid)


# ══ Rubric ════════════════════════════════════════════════════════

class RubricDialog:
    """Build the mark scheme as rows rather than a text blob."""

    def __init__(self, parent: tk.Misc, *, assignment,
                 on_save: Callable[[], None]) -> None:
        self.assignment = assignment
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Rubric — #{assignment.assignment_id} "
                          f"{assignment.title}")
        self.win.geometry("900x560")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        self._build()
        self.refresh()

    def _build(self) -> None:
        outer = ttk.Frame(self.win, padding=10)
        outer.pack(fill="both", expand=True)
        self.total_var = tk.StringVar(value="")
        ttk.Label(outer, textvariable=self.total_var,
                   font=("", 10, "bold")).pack(anchor="w", pady=(0, 6))

        cols = ("id", "pos", "code", "title", "max", "weight", "ao")
        headings = {"id": "ID", "pos": "#", "code": "Code",
                    "title": "Title", "max": "Max", "weight": "Weight",
                    "ao": "AO"}
        widths = {"id": 45, "pos": 40, "code": 70, "title": 320,
                  "max": 60, "weight": 70, "ao": 90}
        self.tree = ttk.Treeview(outer, columns=cols, show="headings",
                                    height=12)
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c],
                              anchor="e" if c in ("max", "weight", "pos")
                              else "w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda _e: self._edit())

        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=(8, 0))
        ttk.Button(bar, text="Add",
                    command=self._add).pack(side="left")
        ttk.Button(bar, text="Edit",
                    command=self._edit).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left", padx=4)
        ttk.Button(bar, text="Move up",
                    command=lambda: self._move(-1)).pack(side="left",
                                                           padx=(16, 2))
        ttk.Button(bar, text="Move down",
                    command=lambda: self._move(1)).pack(side="left")
        ttk.Button(bar, text="Close",
                    command=self._close).pack(side="right")

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        for c in marking.list_criteria(self.assignment.assignment_id):
            self.tree.insert(
                "", "end", iid=str(c.criterion_id),
                values=(c.criterion_id, c.position, c.code or "—",
                        c.title, _fmt(c.max_marks),
                        _fmt(c.weight_percent), c.assessment_objective
                        or "—"))
        self.total_var.set(
            marking.rubric_total(self.assignment.assignment_id).message)

    def _selected(self) -> Criterion | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Rubric", "Select a criterion first.")
            return None
        return marking.get_criterion(int(sel[0]))

    def _add(self) -> None:
        CriterionDialog(self.win, assignment=self.assignment,
                         existing=None, on_save=self.refresh)

    def _edit(self) -> None:
        c = self._selected()
        if c is None:
            return
        CriterionDialog(self.win, assignment=self.assignment,
                         existing=c, on_save=self.refresh)

    def _delete(self) -> None:
        c = self._selected()
        if c is None:
            return
        if not messagebox.askyesno(
                "Delete",
                f"Delete {c.label!r}?\n\n"
                "Every mark awarded against it is deleted too."):
            return
        marking.delete_criterion(c.criterion_id)
        self.refresh()

    def _move(self, delta: int) -> None:
        c = self._selected()
        if c is None:
            return
        order = [x.criterion_id for x in
                 marking.list_criteria(self.assignment.assignment_id)]
        idx = order.index(c.criterion_id)
        new = idx + delta
        if not (0 <= new < len(order)):
            return
        order[idx], order[new] = order[new], order[idx]
        marking.reorder_criteria(self.assignment.assignment_id, order)
        self.refresh()
        self.tree.selection_set(str(c.criterion_id))

    def _close(self) -> None:
        self.win.destroy()
        self.on_save()


class CriterionDialog:
    def __init__(self, parent: tk.Misc, *, assignment,
                 existing: Criterion | None,
                 on_save: Callable[[], None]) -> None:
        self.assignment = assignment
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit criterion" if existing else "Add criterion")
        self.win.geometry("560x420")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        e = self.existing

        ttk.Label(form, text="Code:").grid(row=0, column=0, sticky="e",
                                              pady=4)
        self.code_e = ttk.Entry(form, width=12)
        if e and e.code:
            self.code_e.insert(0, e.code)
        self.code_e.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Max marks:").grid(row=0, column=2,
                                                   sticky="e", pady=4)
        self.max_e = ttk.Entry(form, width=10)
        if e:
            self.max_e.insert(0, _fmt(e.max_marks, ""))
        self.max_e.grid(row=0, column=3, sticky="w", padx=6)

        ttk.Label(form, text="Title:").grid(row=1, column=0, sticky="e",
                                               pady=4)
        self.title_e = ttk.Entry(form, width=48)
        if e:
            self.title_e.insert(0, e.title)
        self.title_e.grid(row=1, column=1, columnspan=3, sticky="w",
                            padx=6)

        ttk.Label(form, text="Weight %:").grid(row=2, column=0,
                                                  sticky="e", pady=4)
        self.weight_e = ttk.Entry(form, width=10)
        if e and e.weight_percent is not None:
            self.weight_e.insert(0, _fmt(e.weight_percent, ""))
        self.weight_e.grid(row=2, column=1, sticky="w", padx=6)

        ttk.Label(form, text="AO:").grid(row=2, column=2, sticky="e",
                                            pady=4)
        self.ao_e = ttk.Entry(form, width=14)
        if e and e.assessment_objective:
            self.ao_e.insert(0, e.assessment_objective)
        self.ao_e.grid(row=2, column=3, sticky="w", padx=6)

        ttk.Label(form, text="Descriptor:").grid(row=3, column=0,
                                                    sticky="ne", pady=4)
        self.descriptor = tk.Text(form, width=52, height=10, wrap="word")
        if e and e.descriptor:
            self.descriptor.insert("1.0", e.descriptor)
        self.descriptor.grid(row=3, column=1, columnspan=3, sticky="w",
                               padx=6)

        bar = ttk.Frame(form)
        bar.grid(row=4, column=0, columnspan=4, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        payload = {
            "code": self.code_e.get().strip(),
            "title": self.title_e.get().strip(),
            "max_marks": self.max_e.get().strip(),
            "weight_percent": self.weight_e.get().strip() or None,
            "assessment_objective": self.ao_e.get().strip(),
            "descriptor": self.descriptor.get("1.0", "end").strip(),
        }
        try:
            if self.existing:
                marking.update_criterion(self.existing.criterion_id,
                                          payload)
            else:
                marking.add_criterion(self.assignment.assignment_id,
                                       payload)
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


# ══ Per-criterion marking ═════════════════════════════════════════

class CriterionMarkDialog:
    """Score each criterion, with the total pushed through the pipeline."""

    def __init__(self, parent: tk.Misc, *, submission, assignment,
                 role: str, on_save: Callable[[], None]) -> None:
        self.submission = submission
        self.assignment = assignment
        self.role = role or marking.DEFAULT_MARKER_ROLE
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Mark by criterion — {submission.student_id} "
            f"({self.role} marker)")
        self.win.geometry("760x620")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        self._entries: dict[int, tk.Entry] = {}
        self._comments: dict[int, tk.Entry] = {}
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self.win, padding=12)
        outer.pack(fill="both", expand=True)
        names = _names()
        ttk.Label(outer,
                   text=f"{self.submission.student_id} — "
                        f"{names.get(self.submission.student_id, '?')}",
                   font=("", 11, "bold")).pack(anchor="w")
        if self.submission.access_arrangements:
            ttk.Label(outer,
                       text=f"Access arrangements: "
                            f"{self.submission.access_arrangements}",
                       foreground="#553").pack(anchor="w", pady=(2, 0))

        canvas = tk.Canvas(outer, highlightthickness=0)
        scroll = ttk.Scrollbar(outer, orient="vertical",
                                command=canvas.yview)
        body = ttk.Frame(canvas)
        body.bind("<Configure>",
                   lambda _e: canvas.configure(
                       scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True, pady=8)
        scroll.pack(side="right", fill="y")

        existing = {m.criterion_id: m for m in
                    marking.list_criterion_marks(
                        self.submission.submission_id, role=self.role)}
        criteria = marking.list_criteria(self.assignment.assignment_id)
        for row, c in enumerate(criteria):
            box = ttk.LabelFrame(
                body, text=f"{c.label}   (max {c.max_marks:g})",
                padding=8)
            box.grid(row=row, column=0, sticky="ew", pady=4, padx=2)
            if c.descriptor:
                ttk.Label(box, text=c.descriptor, foreground="#555",
                           wraplength=620,
                           justify="left").grid(row=0, column=0,
                                                  columnspan=4,
                                                  sticky="w",
                                                  pady=(0, 6))
            ttk.Label(box, text="Marks:").grid(row=1, column=0,
                                                  sticky="e")
            entry = ttk.Entry(box, width=8)
            prior = existing.get(c.criterion_id)
            if prior and prior.marks is not None:
                entry.insert(0, _fmt(prior.marks, ""))
            entry.grid(row=1, column=1, sticky="w", padx=6)
            entry.bind("<KeyRelease>", lambda _e: self._update_total())
            self._entries[c.criterion_id] = entry

            ttk.Label(box, text="Comment:").grid(row=1, column=2,
                                                    sticky="e")
            comment = ttk.Entry(box, width=48)
            if prior and prior.comment:
                comment.insert(0, prior.comment)
            comment.grid(row=1, column=3, sticky="w", padx=6)
            self._comments[c.criterion_id] = comment

        foot = ttk.Frame(self.win, padding=(12, 0, 12, 12))
        foot.pack(fill="x")
        self.total_var = tk.StringVar(value="")
        ttk.Label(foot, textvariable=self.total_var,
                   font=("", 10, "bold")).pack(anchor="w", pady=(0, 6))
        ttk.Label(foot, text="Marked by:").pack(side="left")
        self.by_cb = ttk.Combobox(
            foot, values=("",) + tuple(_teacher_options()), width=24)
        self.by_cb.set(self.assignment.teacher or "")
        self.by_cb.pack(side="left", padx=(4, 12))
        ttk.Button(foot, text="Save scores only",
                    command=lambda: self._save(total=False)).pack(
            side="left")
        ttk.Button(foot, text="Save and total",
                    command=lambda: self._save(total=True)).pack(
            side="left", padx=6)
        ttk.Button(foot, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)
        self._update_total()

    def _entered(self) -> tuple[float, int, int]:
        total = 0.0
        scored = 0
        for entry in self._entries.values():
            raw = entry.get().strip()
            if not raw:
                continue
            try:
                total += float(raw)
                scored += 1
            except ValueError:
                pass
        return round(total, 2), scored, len(self._entries)

    def _update_total(self) -> None:
        total, scored, count = self._entered()
        max_marks = self.assignment.max_marks
        self.total_var.set(
            f"Total {total:g} / {max_marks or '?'}   ·   "
            f"{scored} of {count} criteria scored"
            + ("" if scored == count
                else "   ·   incomplete rubrics cannot be totalled"))

    def _save(self, *, total: bool) -> None:
        marked_by = self.by_cb.get().strip() or None
        try:
            for criterion_id, entry in self._entries.items():
                raw = entry.get().strip()
                if not raw:
                    continue
                marking.set_criterion_mark(
                    self.submission.submission_id, criterion_id,
                    marks=float(raw), role=self.role,
                    comment=self._comments[criterion_id].get().strip()
                    or None,
                    marked_by=marked_by)
        except (ValueError, ValidationError) as e:
            messagebox.showerror("Save failed", str(e))
            return

        if not total:
            self.win.destroy()
            self.on_save()
            return
        try:
            out = marking.apply_criterion_total(
                self.submission.submission_id, role=self.role,
                marked_by=marked_by)
        except ValidationError as e:
            messagebox.showerror("Total", str(e))
            return
        lines = [f"Raw mark: {_fmt(out.raw_marks)}"]
        if out.penalty_percent:
            lines.append(f"Late penalty: {out.penalty_percent:g}% "
                         f"({out.penalty_days} day(s) late)")
        lines.append(f"Final mark: {_fmt(out.marks)} / "
                     f"{self.assignment.max_marks or '?'}")
        lines.append(f"Grade: {out.grade or '—'}")
        messagebox.showinfo("Marked", "\n".join(lines))
        self.win.destroy()
        self.on_save()


# ══ Marks, moderation, samples, penalties ═════════════════════════

class RecordMarkDialog:
    """Record one marker's independent judgement."""

    def __init__(self, parent: tk.Misc, *, submission, assignment,
                 role: str, on_save: Callable[[], None]) -> None:
        self.submission = submission
        self.assignment = assignment
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Record mark — {submission.student_id}")
        self.win.geometry("640x520")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        self._role = role or marking.DEFAULT_MARKER_ROLE
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self.win, padding=12)
        outer.pack(fill="both", expand=True)
        names = _names()
        ttk.Label(outer,
                   text=f"{self.submission.student_id} — "
                        f"{names.get(self.submission.student_id, '?')}"
                        f"   (max {self.assignment.max_marks or '?'})",
                   font=("", 11, "bold")).pack(anchor="w", pady=(0, 8))

        form = ttk.Frame(outer)
        form.pack(fill="x")
        ttk.Label(form, text="Role:").grid(row=0, column=0, sticky="e",
                                              pady=4)
        self.role_cb = ttk.Combobox(form, values=MARKER_ROLES,
                                      state="readonly", width=12)
        self.role_cb.set(self._role)
        self.role_cb.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Marks:").grid(row=0, column=2, sticky="e",
                                               pady=4)
        self.marks_e = ttk.Entry(form, width=10)
        existing = marking.get_mark(self.submission.submission_id,
                                     self._role)
        if existing and existing.marks is not None:
            self.marks_e.insert(0, _fmt(existing.marks, ""))
        self.marks_e.grid(row=0, column=3, sticky="w", padx=6)

        ttk.Label(form, text="Marked by:").grid(row=1, column=0,
                                                   sticky="e", pady=4)
        self.by_cb = ttk.Combobox(
            form, values=("",) + tuple(_teacher_options()), width=26)
        self.by_cb.set(self.assignment.teacher or "")
        self.by_cb.grid(row=1, column=1, columnspan=3, sticky="w",
                          padx=6)

        self.apply_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            form,
            text="Also set this as the submission's mark "
                 "(first marker only)",
            variable=self.apply_var).grid(row=2, column=0, columnspan=4,
                                            sticky="w", pady=(6, 0))

        ttk.Label(outer, text="Feedback:").pack(anchor="w", pady=(10, 2))
        row = ttk.Frame(outer)
        row.pack(fill="x")
        ttk.Button(row, text="Insert from comment bank...",
                    command=self._insert_comment).pack(side="left")
        self.feedback = tk.Text(outer, height=10, wrap="word")
        if existing and existing.feedback:
            self.feedback.insert("1.0", existing.feedback)
        elif self.submission.feedback:
            self.feedback.insert("1.0", self.submission.feedback)
        self.feedback.pack(fill="both", expand=True, pady=(4, 8))

        bar = ttk.Frame(outer)
        bar.pack(fill="x")
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _insert_comment(self) -> None:
        CommentPickerDialog(
            self.win, subject_name=self.assignment.subject_name,
            submission_id=self.submission.submission_id,
            on_pick=self._append_text)

    def _append_text(self, text: str) -> None:
        current = self.feedback.get("1.0", "end").strip()
        self.feedback.delete("1.0", "end")
        self.feedback.insert("1.0",
                               (current + "\n\n" + text).strip())

    def _save(self) -> None:
        raw = self.marks_e.get().strip()
        try:
            marks = float(raw) if raw else None
        except ValueError:
            messagebox.showerror("Record mark",
                                   "Marks must be a number.")
            return
        role = self.role_cb.get()
        feedback = self.feedback.get("1.0", "end").strip() or None
        by = self.by_cb.get().strip() or None
        try:
            marking.record_mark(self.submission.submission_id, role=role,
                                 marks=marks, feedback=feedback,
                                 marked_by=by)
            if self.apply_var.get() and role == "First" \
                    and marks is not None:
                marking.apply_marks(self.submission.submission_id,
                                     raw_marks=marks, feedback=feedback,
                                     marked_by=by, source="manual")
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        state = marking.moderation_state(self.submission.submission_id)
        if state.needs_moderation:
            messagebox.showwarning(
                "Moderation needed",
                f"{state.message}\n\n"
                "This submission now needs a moderator before the mark "
                "is final.")
        self.win.destroy()
        self.on_save()


class ModerationDialog:
    """Settle a first/second disagreement."""

    def __init__(self, parent: tk.Misc, *, submission, assignment,
                 on_save: Callable[[], None]) -> None:
        self.submission = submission
        self.assignment = assignment
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Moderate — {submission.student_id}")
        self.win.geometry("560x420")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self.win, padding=12)
        outer.pack(fill="both", expand=True)
        state = marking.moderation_state(self.submission.submission_id)

        cols = ("role", "marks", "grade", "by", "on")
        tree = ttk.Treeview(outer, columns=cols, show="headings",
                              height=4)
        for c, head, width in (("role", "Role", 90),
                                ("marks", "Marks", 70),
                                ("grade", "Grade", 60),
                                ("by", "Marked by", 160),
                                ("on", "On", 100)):
            tree.heading(c, text=head)
            tree.column(c, width=width,
                         anchor="e" if c == "marks" else "w")
        for m in marking.list_marks(self.submission.submission_id):
            tree.insert("", "end", values=(m.role, _fmt(m.marks),
                                             m.grade or "—",
                                             m.marked_by or "—",
                                             m.marked_on or "—"))
        tree.pack(fill="x", pady=(0, 8))

        ttk.Label(outer, text=state.message,
                   font=("", 10, "bold")).pack(anchor="w", pady=(0, 8))

        if not state.is_double_marked:
            ttk.Label(
                outer,
                text="Moderation needs both a first and a second mark.",
                foreground="#555").pack(anchor="w")
            ttk.Button(outer, text="Close",
                        command=self.win.destroy).pack(anchor="e",
                                                         pady=(12, 0))
            return

        form = ttk.Frame(outer)
        form.pack(fill="x")
        ttk.Label(form, text="Agreed mark:").grid(row=0, column=0,
                                                     sticky="e", pady=4)
        self.marks_e = ttk.Entry(form, width=10)
        midpoint = round(((state.first or 0) + (state.second or 0)) / 2, 1)
        self.marks_e.insert(0, f"{midpoint:g}")
        self.marks_e.grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(form, text="(midpoint pre-filled — change it)",
                   foreground="#555").grid(row=0, column=2, sticky="w")

        ttk.Label(form, text="Resolved by:").grid(row=1, column=0,
                                                     sticky="e", pady=4)
        self.by_cb = ttk.Combobox(
            form, values=("",) + tuple(_teacher_options()), width=26)
        self.by_cb.grid(row=1, column=1, columnspan=2, sticky="w",
                          padx=6)

        ttk.Label(outer, text="Note:").pack(anchor="w", pady=(8, 2))
        self.note = tk.Text(outer, height=6, wrap="word")
        self.note.pack(fill="both", expand=True)

        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=(8, 0))
        ttk.Button(bar, text="Resolve",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            marks = float(self.marks_e.get().strip())
        except ValueError:
            messagebox.showerror("Moderate", "Marks must be a number.")
            return
        try:
            out = marking.resolve_moderation(
                self.submission.submission_id, marks=marks,
                resolved_by=self.by_cb.get().strip() or None,
                note=self.note.get("1.0", "end").strip() or None)
        except Exception as e:
            messagebox.showerror("Resolve failed", str(e))
            return
        messagebox.showinfo(
            "Moderated",
            f"Final mark {_fmt(out.marks)} / "
            f"{self.assignment.max_marks or '?'}  (grade "
            f"{out.grade or '—'})")
        self.win.destroy()
        self.on_save()


class SampleDialog:
    def __init__(self, parent: tk.Misc, *, submission,
                 on_save: Callable[[], None]) -> None:
        self.submission = submission
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Sample — {submission.student_id}")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)

        ttk.Label(form, text="Band:").grid(row=0, column=0, sticky="e",
                                              pady=4)
        self.band_cb = ttk.Combobox(form, values=SAMPLE_BANDS,
                                      state="readonly", width=14)
        self.band_cb.set(submission.sample_band or "Middle")
        self.band_cb.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Note:").grid(row=1, column=0, sticky="e",
                                              pady=4)
        self.note_e = ttk.Entry(form, width=44)
        if submission.sample_note:
            self.note_e.insert(0, submission.sample_note)
        self.note_e.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Flagged by:").grid(row=2, column=0,
                                                    sticky="e", pady=4)
        self.by_cb = ttk.Combobox(
            form, values=("",) + tuple(_teacher_options()), width=26)
        self.by_cb.set(submission.sample_by or "")
        self.by_cb.grid(row=2, column=1, sticky="w", padx=6)

        bar = ttk.Frame(form)
        bar.grid(row=3, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Flag",
                    command=self._save).pack(side="left")
        if submission.sample_band:
            ttk.Button(bar, text="Remove from sample",
                        command=self._remove).pack(side="left", padx=6)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            marking.flag_sample(self.submission.submission_id,
                                 band=self.band_cb.get(),
                                 note=self.note_e.get().strip() or None,
                                 flagged_by=self.by_cb.get().strip()
                                 or None)
        except Exception as e:
            messagebox.showerror("Sample", str(e))
            return
        self.win.destroy()
        self.on_save()

    def _remove(self) -> None:
        marking.unflag_sample(self.submission.submission_id)
        self.win.destroy()
        self.on_save()


class PenaltyDialog:
    """Show what the late policy costs, and waive it if warranted."""

    def __init__(self, parent: tk.Misc, *, submission, assignment,
                 on_save: Callable[[], None]) -> None:
        self.submission = submission
        self.assignment = assignment
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Late penalty — {submission.student_id}")
        self.win.geometry("560x360")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self.win, padding=12)
        outer.pack(fill="both", expand=True)
        penalty = marking.compute_late_penalty(self.assignment,
                                                self.submission)
        due = data.effective_due_date(self.submission, self.assignment)

        rows = [
            ("Deadline", due or "—"),
            ("Submitted", self.submission.submitted_on or "—"),
            ("Policy",
             (f"{self.assignment.late_penalty_percent_per_day:g}% per day"
              if self.assignment.late_penalty_percent_per_day
              else "none set")),
            ("Grace days",
             str(self.assignment.late_penalty_grace_days or 0)),
            ("Cap",
             _fmt(self.assignment.late_penalty_cap_percent, "none")),
            ("Status", penalty.message),
            ("Raw mark", _fmt(self.submission.raw_marks)),
            ("Final mark", _fmt(self.submission.marks)),
            ("Grade", self.submission.grade or "—"),
        ]
        for r, (label, value) in enumerate(rows):
            ttk.Label(outer, text=f"{label}:").grid(row=r, column=0,
                                                       sticky="e", pady=2)
            ttk.Label(outer, text=value).grid(row=r, column=1,
                                                 sticky="w", padx=8)

        bar = ttk.Frame(outer)
        bar.grid(row=len(rows), column=0, columnspan=2, pady=(14, 0))
        if self.submission.penalty_waived:
            ttk.Label(
                outer,
                text=f"Waived: "
                     f"{self.submission.penalty_waived_reason or '—'}",
                foreground="#553").grid(row=len(rows) + 1, column=0,
                                          columnspan=2, sticky="w")
            ttk.Button(bar, text="Restore penalty",
                        command=self._restore).pack(side="left")
        else:
            ttk.Button(bar, text="Waive penalty...",
                        command=self._waive).pack(side="left")
        ttk.Button(bar, text="Close",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _waive(self) -> None:
        WaiverDialog(self.win, submission=self.submission,
                      on_save=self._done)

    def _restore(self) -> None:
        if not messagebox.askyesno(
                "Restore penalty",
                "Withdraw the waiver and re-apply the late policy?"):
            return
        marking.restore_penalty(self.submission.submission_id)
        self._done()

    def _done(self) -> None:
        self.win.destroy()
        self.on_save()


class WaiverDialog:
    def __init__(self, parent: tk.Misc, *, submission,
                 on_save: Callable[[], None]) -> None:
        self.submission = submission
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Waive late penalty")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="Reason:").grid(row=0, column=0, sticky="e",
                                                pady=4)
        self.reason_e = ttk.Entry(form, width=48)
        self.reason_e.grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Waived by:").grid(row=1, column=0,
                                                   sticky="e", pady=4)
        self.by_cb = ttk.Combobox(
            form, values=("",) + tuple(_teacher_options()), width=28)
        self.by_cb.grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(form,
                   text="The mark is recalculated from the raw mark, "
                        "and\nthe waiver is recorded in the audit trail.",
                   foreground="#555").grid(row=2, column=0, columnspan=2,
                                             sticky="w", pady=(8, 0))
        bar = ttk.Frame(form)
        bar.grid(row=3, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Waive",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            marking.waive_penalty(
                self.submission.submission_id,
                reason=self.reason_e.get().strip(),
                waived_by=self.by_cb.get().strip() or None)
        except Exception as e:
            messagebox.showerror("Waive failed", str(e))
            return
        self.win.destroy()
        self.on_save()


# ══ Grade boundaries ══════════════════════════════════════════════

class BoundariesDialog:
    def __init__(self, parent: tk.Misc, *, assignment,
                 on_save: Callable[[], None]) -> None:
        self.assignment = assignment
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Grade boundaries — #{assignment.assignment_id}")
        self.win.geometry("520x420")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        self._entries: dict[str, ttk.Entry] = {}
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self.win, padding=12)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer,
                   text=f"Raw-mark thresholds out of "
                        f"{self.assignment.max_marks or '?'}",
                   font=("", 11, "bold")).pack(anchor="w")
        ttk.Label(
            outer,
            text="Leave a letter blank to use the college percentage\n"
                 "default for it. Pinning only A*/A after a "
                 "standardisation\nmeeting is normal.",
            foreground="#555").pack(anchor="w", pady=(2, 10))

        current = marking.get_grade_boundaries(
            self.assignment.assignment_id)
        grid = ttk.Frame(outer)
        grid.pack(fill="x")
        for row, (col, letter) in enumerate(marking._BOUNDARY_COLUMNS):
            ttk.Label(grid, text=f"{letter}:").grid(row=row, column=0,
                                                       sticky="e", pady=3)
            entry = ttk.Entry(grid, width=10)
            if current is not None:
                value = getattr(current, col)
                if value is not None:
                    entry.insert(0, _fmt(value, ""))
            entry.grid(row=row, column=1, sticky="w", padx=6)
            default = dict(marking.DEFAULT_BOUNDARIES_PCT).get(letter)
            if default is not None and self.assignment.max_marks:
                hint = round(self.assignment.max_marks * default / 100, 1)
                ttk.Label(grid,
                           text=f"default {default:g}%  ≈  {hint:g} marks",
                           foreground="#555").grid(row=row, column=2,
                                                     sticky="w")
            self._entries[letter] = entry

        self.regrade_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            outer,
            text="Re-grade every marked submission after saving",
            variable=self.regrade_var).pack(anchor="w", pady=(12, 0))

        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Clear overrides",
                    command=self._clear).pack(side="left", padx=6)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _regrade(self) -> int:
        n = 0
        for sub in data.list_submissions(
                assignment_id=self.assignment.assignment_id):
            if sub.raw_marks is None:
                continue
            marking.apply_marks(sub.submission_id,
                                 raw_marks=sub.raw_marks,
                                 marked_by=sub.marked_by,
                                 source="manual",
                                 reason="Grade boundaries changed")
            n += 1
        return n

    def _save(self) -> None:
        payload = {letter: entry.get().strip()
                   for letter, entry in self._entries.items()}
        try:
            marking.set_grade_boundaries(
                self.assignment.assignment_id, payload)
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        if self.regrade_var.get():
            messagebox.showinfo(
                "Boundaries",
                f"Saved. Re-graded {self._regrade()} submission(s).")
        self.win.destroy()
        self.on_save()

    def _clear(self) -> None:
        if not messagebox.askyesno(
                "Clear",
                "Remove the pinned thresholds and fall back to the "
                "percentage defaults?"):
            return
        marking.clear_grade_boundaries(self.assignment.assignment_id)
        if self.regrade_var.get():
            self._regrade()
        self.win.destroy()
        self.on_save()


# ══ Bulk marking ══════════════════════════════════════════════════

class BulkMarkDialog:
    """One row per student, tab between marks, validate then apply."""

    def __init__(self, parent: tk.Misc, *, assignment, role: str,
                 on_save: Callable[[], None]) -> None:
        self.assignment = assignment
        self.role = role or marking.DEFAULT_MARKER_ROLE
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Bulk marking — #{assignment.assignment_id} "
                          f"{assignment.title}")
        self.win.geometry("900x640")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        self._rows: list[tuple[int, ttk.Entry, ttk.Entry]] = []
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self.win, padding=10)
        outer.pack(fill="both", expand=True)
        ttk.Label(
            outer,
            text=f"Marking as {self.role} marker   ·   out of "
                 f"{self.assignment.max_marks or '?'}   ·   blank rows "
                 f"are left alone",
            font=("", 10, "bold")).pack(anchor="w", pady=(0, 6))

        canvas = tk.Canvas(outer, highlightthickness=0)
        scroll = ttk.Scrollbar(outer, orient="vertical",
                                command=canvas.yview)
        body = ttk.Frame(canvas)
        body.bind("<Configure>",
                   lambda _e: canvas.configure(
                       scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        for col, (text, width) in enumerate(
                (("Student", 12), ("Name", 24), ("Marks", 8),
                 ("Grade", 8), ("Notes", 40))):
            ttk.Label(body, text=text,
                       font=("", 9, "bold")).grid(row=0, column=col,
                                                    sticky="w", padx=4,
                                                    pady=(0, 4))

        grid = marking.marking_grid(self.assignment.assignment_id,
                                     role=self.role)
        for r, g in enumerate(grid, start=1):
            s = g.submission
            ttk.Label(body, text=s.student_id).grid(row=r, column=0,
                                                       sticky="w", padx=4)
            ttk.Label(body, text=g.student_name[:24]).grid(row=r,
                                                              column=1,
                                                              sticky="w",
                                                              padx=4)
            marks_e = ttk.Entry(body, width=8)
            if s.raw_marks is not None:
                marks_e.insert(0, _fmt(s.raw_marks, ""))
            marks_e.grid(row=r, column=2, sticky="w", padx=4)

            grade_e = ttk.Entry(body, width=8)
            if s.grade:
                grade_e.insert(0, s.grade)
            grade_e.grid(row=r, column=3, sticky="w", padx=4)

            notes = []
            if g.penalty.days_late:
                notes.append(g.penalty.message)
            if g.access_arrangements:
                notes.append("; ".join(g.access_arrangements))
            if g.moderation and g.moderation.needs_moderation:
                notes.append(g.moderation.message)
            ttk.Label(body, text=" | ".join(notes)[:60],
                       foreground="#555").grid(row=r, column=4,
                                                 sticky="w", padx=4)
            self._rows.append((s.submission_id, marks_e, grade_e))

        foot = ttk.Frame(self.win, padding=(10, 0, 10, 10))
        foot.pack(fill="x")
        ttk.Label(foot, text="Marked by:").pack(side="left")
        self.by_cb = ttk.Combobox(
            foot, values=("",) + tuple(_teacher_options()), width=24)
        self.by_cb.set(self.assignment.teacher or "")
        self.by_cb.pack(side="left", padx=(4, 12))
        ttk.Button(foot, text="Apply",
                    command=self._save).pack(side="left")
        ttk.Button(foot, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        rows = []
        for submission_id, marks_e, grade_e in self._rows:
            raw = marks_e.get().strip()
            if not raw:
                continue
            rows.append({"submission_id": submission_id,
                          "marks": raw,
                          "grade": grade_e.get().strip() or None})
        if not rows:
            messagebox.showinfo("Bulk marking", "Nothing entered.")
            return
        result = marking.bulk_mark(self.assignment.assignment_id, rows,
                                    marked_by=self.by_cb.get().strip()
                                    or None, role=self.role)
        lines = [f"Applied {result.applied}, failed {result.failed}.",
                 ""]
        lines += [f"{'✓' if o.ok else '✗'} {o.student_id}: {o.message}"
                  for o in result.outcomes if not o.ok][:12]
        if result.all_ok:
            messagebox.showinfo("Bulk marking", lines[0])
        else:
            messagebox.showwarning("Bulk marking", "\n".join(lines))
        self.win.destroy()
        self.on_save()


# ══ Audit trail ═══════════════════════════════════════════════════

class AuditDialog:
    def __init__(self, parent: tk.Misc, *, assignment,
                 submission_id: int | None = None) -> None:
        self.assignment = assignment
        self.submission_id = submission_id
        self.win = tk.Toplevel(parent)
        self.win.title(f"Mark audit — #{assignment.assignment_id} "
                          f"{assignment.title}")
        self.win.geometry("1000x520")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        self._build()
        self.refresh()

    def _build(self) -> None:
        outer = ttk.Frame(self.win, padding=10)
        outer.pack(fill="both", expand=True)
        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=(0, 6))
        self.scope_var = tk.BooleanVar(value=self.submission_id is None)
        ttk.Checkbutton(bar, text="Whole assignment",
                          variable=self.scope_var,
                          command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Close",
                    command=self.win.destroy).pack(side="right")

        cols = ("when", "sub", "field", "old", "new", "source", "by",
                "reason")
        headings = {"when": "When", "sub": "Sub", "field": "Field",
                    "old": "From", "new": "To", "source": "Source",
                    "by": "Changed by", "reason": "Reason"}
        widths = {"when": 150, "sub": 45, "field": 85, "old": 70,
                  "new": 70, "source": 85, "by": 130, "reason": 280}
        self.tree = ttk.Treeview(outer, columns=cols, show="headings")
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c],
                              anchor="e" if c in ("old", "new") else "w")
        self.tree.pack(fill="both", expand=True)
        self.count_var = tk.StringVar(value="")
        ttk.Label(outer, textvariable=self.count_var,
                   anchor="w").pack(fill="x", pady=(6, 0))

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        whole = self.scope_var.get() or self.submission_id is None
        rows = marking.list_mark_audit(
            assignment_id=(self.assignment.assignment_id
                            if whole else None),
            submission_id=(None if whole else self.submission_id),
            limit=500)
        for r in rows:
            self.tree.insert("", "end", values=(
                r.changed_at, r.submission_id, r.field,
                r.old_value or "—", r.new_value or "—", r.source,
                r.changed_by or "—", r.reason or "—"))
        self.count_var.set(f"{len(rows)} change(s), newest first.")


# ══ Comment bank ══════════════════════════════════════════════════

class CommentBankDialog:
    """Manage the department's reusable feedback."""

    def __init__(self, parent: tk.Misc, *,
                 subject_name: str | None,
                 on_save: Callable[[], None]) -> None:
        self.subject_name = subject_name
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Comment bank")
        self.win.geometry("900x560")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        self._build()
        self.refresh()

    def _build(self) -> None:
        outer = ttk.Frame(self.win, padding=10)
        outer.pack(fill="both", expand=True)
        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Subject:").pack(side="left")
        self.subject_e = ttk.Entry(bar, width=18)
        if self.subject_name:
            self.subject_e.insert(0, self.subject_name)
        self.subject_e.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Category:").pack(side="left")
        self.category_cb = ttk.Combobox(
            bar, values=("",) + COMMENT_CATEGORIES,
            state="readonly", width=14)
        self.category_cb.current(0)
        self.category_cb.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Contains:").pack(side="left")
        self.query_e = ttk.Entry(bar, width=20)
        self.query_e.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left")

        cols = ("id", "category", "subject", "used", "body")
        headings = {"id": "ID", "category": "Category",
                    "subject": "Subject", "used": "Used", "body": "Body"}
        widths = {"id": 45, "category": 110, "subject": 130,
                  "used": 55, "body": 480}
        self.tree = ttk.Treeview(outer, columns=cols, show="headings")
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c],
                              anchor="e" if c == "used" else "w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda _e: self._edit())

        foot = ttk.Frame(outer)
        foot.pack(fill="x", pady=(8, 0))
        ttk.Button(foot, text="Add",
                    command=self._add).pack(side="left")
        ttk.Button(foot, text="Edit",
                    command=self._edit).pack(side="left", padx=4)
        ttk.Button(foot, text="Delete",
                    command=self._delete).pack(side="left", padx=4)
        ttk.Button(foot, text="Close",
                    command=self._close).pack(side="right")

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        rows = marking.list_comments(
            subject_name=self.subject_e.get().strip() or None,
            category=self.category_cb.get() or None,
            query=self.query_e.get().strip() or None,
            include_inactive=True)
        for c in rows:
            body = c.body.replace("\n", " ⏎ ")
            self.tree.insert("", "end", iid=str(c.comment_id), values=(
                c.comment_id, c.category,
                c.subject_name or "(all)", c.use_count,
                body if c.is_active else f"(inactive) {body}"))

    def _selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Comment bank",
                                  "Select a comment first.")
            return None
        return marking.get_comment(int(sel[0]))

    def _add(self) -> None:
        CommentEditDialog(self.win, existing=None,
                           subject_name=self.subject_name,
                           on_save=self.refresh)

    def _edit(self) -> None:
        c = self._selected()
        if c is None:
            return
        CommentEditDialog(self.win, existing=c,
                           subject_name=self.subject_name,
                           on_save=self.refresh)

    def _delete(self) -> None:
        c = self._selected()
        if c is None:
            return
        if not messagebox.askyesno("Delete",
                                     f"Delete comment #{c.comment_id}?"):
            return
        marking.delete_comment(c.comment_id)
        self.refresh()

    def _close(self) -> None:
        self.win.destroy()
        self.on_save()


class CommentEditDialog:
    def __init__(self, parent: tk.Misc, *, existing,
                 subject_name: str | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit comment" if existing else "Add comment")
        self.win.geometry("620x420")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)

        ttk.Label(form, text="Subject:").grid(row=0, column=0,
                                                 sticky="e", pady=4)
        self.subject_e = ttk.Entry(form, width=24)
        initial = (existing.subject_name if existing else subject_name)
        if initial:
            self.subject_e.insert(0, initial)
        self.subject_e.grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(form, text="(blank = all subjects)",
                   foreground="#555").grid(row=0, column=2, sticky="w")

        ttk.Label(form, text="Category:").grid(row=1, column=0,
                                                  sticky="e", pady=4)
        self.category_cb = ttk.Combobox(form, values=COMMENT_CATEGORIES,
                                          state="readonly", width=18)
        self.category_cb.set(existing.category if existing
                              else marking.DEFAULT_COMMENT_CATEGORY)
        self.category_cb.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Code:").grid(row=2, column=0, sticky="e",
                                              pady=4)
        self.code_e = ttk.Entry(form, width=14)
        if existing and existing.code:
            self.code_e.insert(0, existing.code)
        self.code_e.grid(row=2, column=1, sticky="w", padx=6)

        self.active_var = tk.BooleanVar(
            value=existing.is_active if existing else True)
        ttk.Checkbutton(form, text="Active",
                          variable=self.active_var).grid(row=2, column=2,
                                                           sticky="w")

        ttk.Label(form, text="Body:").grid(row=3, column=0, sticky="ne",
                                              pady=4)
        self.body = tk.Text(form, width=60, height=10, wrap="word")
        if existing:
            self.body.insert("1.0", existing.body)
        self.body.grid(row=3, column=1, columnspan=2, sticky="w", padx=6)

        ttk.Label(
            form,
            text="Placeholders: {first_name} {full_name} {grade} "
                 "{marks}\n{max_marks} {title} {subject_name}",
            foreground="#555").grid(row=4, column=1, columnspan=2,
                                      sticky="w", pady=(6, 0))

        bar = ttk.Frame(form)
        bar.grid(row=5, column=0, columnspan=3, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        payload = {
            "subject_name": self.subject_e.get().strip() or None,
            "category": self.category_cb.get(),
            "code": self.code_e.get().strip() or None,
            "body": self.body.get("1.0", "end").strip(),
            "is_active": self.active_var.get(),
        }
        try:
            if self.existing:
                marking.update_comment(self.existing.comment_id, payload)
            else:
                marking.add_comment(payload)
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class CommentPickerDialog:
    """Pick a bank comment and hand the expanded text back."""

    def __init__(self, parent: tk.Misc, *, subject_name: str | None,
                 submission_id: int,
                 on_pick: Callable[[str], None]) -> None:
        self.submission_id = submission_id
        self.on_pick = on_pick
        self.win = tk.Toplevel(parent)
        self.win.title("Insert from comment bank")
        self.win.geometry("720x440")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        outer = ttk.Frame(self.win, padding=10)
        outer.pack(fill="both", expand=True)

        self.rows = marking.list_comments(subject_name=subject_name)
        cols = ("id", "category", "used", "body")
        self.tree = ttk.Treeview(outer, columns=cols, show="headings")
        for c, head, width in (("id", "ID", 45),
                                ("category", "Category", 110),
                                ("used", "Used", 55),
                                ("body", "Body", 470)):
            self.tree.heading(c, text=head)
            self.tree.column(c, width=width,
                              anchor="e" if c == "used" else "w")
        for comment in self.rows:
            self.tree.insert(
                "", "end", iid=str(comment.comment_id),
                values=(comment.comment_id, comment.category,
                        comment.use_count,
                        comment.body.replace("\n", " ⏎ ")))
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda _e: self._pick())

        if not self.rows:
            ttk.Label(outer,
                       text="The bank has no comments for this subject "
                            "yet.",
                       foreground="#555").pack(anchor="w", pady=(6, 0))

        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=(8, 0))
        ttk.Button(bar, text="Insert",
                    command=self._pick).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _pick(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Comment bank",
                                  "Select a comment first.")
            return
        text = marking.use_comment(int(sel[0]),
                                    submission_id=self.submission_id)
        self.win.destroy()
        self.on_pick(text)
