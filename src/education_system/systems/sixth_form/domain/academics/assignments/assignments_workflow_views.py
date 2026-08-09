"""Tkinter views for release, appeals and assessment instruments.

Adds a **Workflow** tab to the Assignments window, itself a notebook:

* Release — what is marked but held back, plus acknowledgement and the
  marking-turnaround SLA.
* Appeals — the remark queue and its outcomes.
* Questions — objective questions, auto-marking and per-question
  facility.
* Groups — group membership, per-member adjustment and group marking.
* Peer & Self — peer review scores and self-assessment calibration.
* Components — multi-part assignments and the weighted rollup.

An assignment picker at the top drives every sub-tab, so switching
between them keeps the same class in view.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from education_system.systems.sixth_form.domain.academics.assignments import (
    assignments as data,
    assignments_assessment as assess,
    assignments_feedback as feedback,
    assignments_marking as marking,
)
from education_system.systems.sixth_form.domain.academics.assignments.assignments_assessment import (
    GROUP_ROLES,
    PEER_SCORE_MODES,
    QUESTION_TYPES,
)
from education_system.systems.sixth_form.domain.academics.assignments.assignments_feedback import (
    APPEAL_TYPES,
    CLOSED_APPEAL_STATUSES,
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
    """Build a Treeview from (key, heading, width) triples."""
    cols = [key for key, _, _ in spec]
    tree = ttk.Treeview(parent, columns=cols, show="headings",
                          height=height)
    for key, heading, width in spec:
        tree.heading(key, text=heading)
        tree.column(key, width=width,
                     anchor="e" if width <= 70 else "w")
    return tree


# ══ Workflow tab ══════════════════════════════════════════════════

class WorkflowTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Workflow")
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
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

        self.policy_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.policy_var,
                   foreground="#555",
                   anchor="w").pack(fill="x", padx=10, pady=(0, 4))

        self.nb = ttk.Notebook(self.frame)
        self.nb.pack(fill="both", expand=True, padx=8, pady=4)
        self.release = ReleasePane(self.nb, self)
        self.appeals = AppealsPane(self.nb, self)
        self.questions = QuestionsPane(self.nb, self)
        self.groups = GroupsPane(self.nb, self)
        self.peer = PeerPane(self.nb, self)
        self.components = ComponentsPane(self.nb, self)
        self.nb.bind("<<NotebookTabChanged>>",
                      lambda _e: self.refresh_panes())

    # ── Shared state ──────────────────────────────────────────────
    def refresh(self) -> None:
        try:
            rows = data.list_assignments()
        except Exception as e:
            messagebox.showerror("Workflow", str(e))
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
        return data.get_assignment(self._selected_id)

    def need_assignment(self, action: str):
        a = self.assignment()
        if a is None:
            messagebox.showinfo(action, "Select an assignment first.")
        return a

    def refresh_panes(self) -> None:
        a = self.assignment()
        if a is None:
            self.policy_var.set("")
        else:
            bits = [f"Release: {a.release_policy}"]
            if a.release_policy == "On date":
                bits[-1] += f" ({a.release_on or 'no date set'})"
            bits.append("Anonymous marking: "
                        + ("on" if a.anonymous_marking else "off"))
            bits.append(f"Marking target: "
                        f"{feedback.sla_target(a)} day(s)")
            bits.append(f"Appeal window: "
                        f"{feedback.appeal_window_days(a)} day(s)")
            if a.is_group_assignment:
                bits.append("Group assignment")
            if a.peer_assessment_weight:
                bits.append(f"Peer weight "
                            f"{a.peer_assessment_weight:g}%")
            if a.parent_assignment_id:
                bits.append(f"Component of #{a.parent_assignment_id}")
            self.policy_var.set("   ·   ".join(bits))
        for pane in (self.release, self.appeals, self.questions,
                      self.groups, self.peer, self.components):
            try:
                pane.refresh()
            except Exception:
                logger.exception("Workflow pane refresh failed")


# ══ Release, acknowledgement and SLA ══════════════════════════════

class ReleasePane:
    def __init__(self, nb: ttk.Notebook, owner: WorkflowTab) -> None:
        self.owner = owner
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Release")
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", pady=(6, 4))
        ttk.Button(bar, text="Release this class",
                    command=self._release_all).pack(side="left")
        ttk.Button(bar, text="Release selected",
                    command=self._release_one).pack(side="left", padx=4)
        ttk.Button(bar, text="Withdraw selected",
                    command=self._withdraw).pack(side="left", padx=4)
        ttk.Button(bar, text="Record acknowledgement",
                    command=self._acknowledge).pack(side="left",
                                                      padx=(16, 4))
        ttk.Button(bar, text="Release policy...",
                    command=self._policy).pack(side="left", padx=4)
        ttk.Button(bar, text="Run scheduled releases",
                    command=self._release_due).pack(side="right")

        self.tree = _tree(self.frame, [
            ("id", "Sub", 45), ("student", "Student", 80),
            ("name", "Name", 150), ("marks", "Marks", 60),
            ("grade", "Gr", 45), ("released", "Released", 95),
            ("ack", "Acknowledged", 105),
            ("submitted", "Submitted", 95), ("marked", "Marked", 95),
            ("turnaround", "Turnaround", 210),
        ])
        self.tree.tag_configure("held",     background="#fff7d0")
        self.tree.tag_configure("overdue",  background="#ffd0d0")
        self.tree.tag_configure("acked",    background="#d8f4d8")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda _e: self._acknowledge())

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
        report = feedback.turnaround_report(assignment_id=a.assignment_id)
        by_id = {r.submission.submission_id: r for r in report.rows}
        for sub in data.list_submissions(assignment_id=a.assignment_id):
            row = by_id.get(sub.submission_id)
            tags: list[str] = []
            visible = feedback.is_visible_to_student(sub, a)
            if sub.marks is not None and not visible:
                tags.append("held")
            if row is not None and row.is_overdue:
                tags.append("overdue")
            if sub.acknowledged_on:
                tags.append("acked")
            self.tree.insert("", "end", iid=str(sub.submission_id),
                              values=(
                sub.submission_id,
                feedback.display_student_id(sub, a),
                feedback.display_name(sub, a, names=names),
                _fmt(sub.marks), sub.grade or "—",
                sub.feedback_released_on
                or ("visible" if visible else "held"),
                sub.acknowledged_on or "—",
                sub.submitted_on or "—", sub.marked_on or "—",
                row.message if row else "—",
            ), tags=tuple(tags))
        acknowledged, visible_count = feedback.acknowledgement_rate(
            assignment_id=a.assignment_id)
        held = len(feedback.list_pending_release(
            assignment_id=a.assignment_id))
        self.summary_var.set(
            f"{held} held back  ·  {acknowledged}/{visible_count} "
            f"acknowledged  ·  {report.message}")

    def _selected(self, action: str):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo(action, "Select a student first.")
            return None
        return data.get_submission(int(sel[0]))

    def _release_all(self) -> None:
        a = self.owner.need_assignment("Release")
        if a is None:
            return
        held = feedback.list_pending_release(
            assignment_id=a.assignment_id)
        if not held:
            messagebox.showinfo("Release",
                                  "Nothing is being held back.")
            return
        if not messagebox.askyesno(
                "Release",
                f"Make {len(held)} result(s) visible to students?\n\n"
                "They will be emailed."):
            return
        result = feedback.release_assignment(a.assignment_id)
        messagebox.showinfo("Release", result.message)
        self.owner.refresh_panes()

    def _release_one(self) -> None:
        sub = self._selected("Release")
        if sub is None:
            return
        try:
            feedback.release_submission(sub.submission_id)
        except Exception as e:
            messagebox.showerror("Release failed", str(e))
            return
        self.owner.refresh_panes()

    def _withdraw(self) -> None:
        sub = self._selected("Withdraw")
        if sub is None:
            return
        if not sub.feedback_released:
            messagebox.showinfo("Withdraw",
                                  "That result is not released.")
            return
        if not messagebox.askyesno(
                "Withdraw",
                "Take this result back from the student?"):
            return
        feedback.unrelease_submission(sub.submission_id)
        self.owner.refresh_panes()

    def _acknowledge(self) -> None:
        sub = self._selected("Acknowledge")
        if sub is None:
            return
        AcknowledgeDialog(self.frame.winfo_toplevel(), submission=sub,
                           on_save=self.owner.refresh_panes)

    def _release_due(self) -> None:
        result = feedback.release_due()
        messagebox.showinfo("Scheduled releases", result.message)
        self.owner.refresh_panes()

    def _policy(self) -> None:
        a = self.owner.need_assignment("Release policy")
        if a is None:
            return
        ReleasePolicyDialog(self.frame.winfo_toplevel(), assignment=a,
                             on_save=self.owner.refresh)


class AcknowledgeDialog:
    def __init__(self, parent: tk.Misc, *, submission,
                 on_save: Callable[[], None]) -> None:
        self.submission = submission
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Acknowledge — {submission.student_id}")
        self.win.geometry("560x360")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        outer = ttk.Frame(self.win, padding=12)
        outer.pack(fill="both", expand=True)
        ttk.Label(
            outer,
            text="Recording that the student has read their feedback,\n"
                 "and what they said about it.",
            foreground="#555").pack(anchor="w", pady=(0, 8))
        if submission.acknowledged_on:
            ttk.Label(outer,
                       text=f"Already acknowledged "
                            f"{submission.acknowledged_on}",
                       foreground="#553").pack(anchor="w")
        ttk.Label(outer, text="Student response:").pack(anchor="w",
                                                          pady=(6, 2))
        self.response = tk.Text(outer, height=8, wrap="word")
        if submission.student_response:
            self.response.insert("1.0", submission.student_response)
        self.response.pack(fill="both", expand=True)
        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=(8, 0))
        ttk.Button(bar, text="Record",
                    command=self._save).pack(side="left")
        if submission.acknowledged_on:
            ttk.Button(bar, text="Clear",
                        command=self._clear).pack(side="left", padx=6)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            feedback.acknowledge(
                self.submission.submission_id,
                response=self.response.get("1.0", "end").strip() or None)
        except Exception as e:
            messagebox.showerror("Acknowledge failed", str(e))
            return
        self.win.destroy()
        self.on_save()

    def _clear(self) -> None:
        feedback.clear_acknowledgement(self.submission.submission_id)
        self.win.destroy()
        self.on_save()


class ReleasePolicyDialog:
    def __init__(self, parent: tk.Misc, *, assignment,
                 on_save: Callable[[], None]) -> None:
        self.assignment = assignment
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Release policy — #{assignment.assignment_id}")
        self.win.geometry("560x340")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)

        ttk.Label(form, text="Policy:").grid(row=0, column=0, sticky="e",
                                                pady=4)
        self.policy_cb = ttk.Combobox(form, values=data.RELEASE_POLICIES,
                                        state="readonly", width=14)
        self.policy_cb.set(assignment.release_policy)
        self.policy_cb.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Release on:").grid(row=1, column=0,
                                                    sticky="e", pady=4)
        self.date_e = ttk.Entry(form, width=14)
        if assignment.release_on:
            self.date_e.insert(0, assignment.release_on)
        self.date_e.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Marking target (days):").grid(
            row=2, column=0, sticky="e", pady=4)
        self.sla_e = ttk.Entry(form, width=10)
        if assignment.marking_sla_days is not None:
            self.sla_e.insert(0, str(assignment.marking_sla_days))
        self.sla_e.grid(row=2, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Appeal window (days):").grid(
            row=3, column=0, sticky="e", pady=4)
        self.appeal_e = ttk.Entry(form, width=10)
        if assignment.appeal_window_days is not None:
            self.appeal_e.insert(0, str(assignment.appeal_window_days))
        self.appeal_e.grid(row=3, column=1, sticky="w", padx=6)

        self.anon_var = tk.BooleanVar(value=assignment.anonymous_marking)
        ttk.Checkbutton(
            form,
            text="Anonymous marking (names hidden until release)",
            variable=self.anon_var).grid(row=4, column=0, columnspan=2,
                                           sticky="w", pady=(8, 0))
        ttk.Label(
            form,
            text="'Immediate' publishes as soon as a piece is marked.\n"
                 "'On date' holds the class until the date. 'Manual'\n"
                 "holds until someone presses Release.",
            foreground="#555").grid(row=5, column=0, columnspan=2,
                                      sticky="w", pady=(10, 0))

        bar = ttk.Frame(form)
        bar.grid(row=6, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.update_assignment(self.assignment.assignment_id, {
                "release_policy": self.policy_cb.get(),
                "release_on": self.date_e.get().strip() or None,
                "marking_sla_days": self.sla_e.get().strip() or None,
                "appeal_window_days": self.appeal_e.get().strip() or None,
                "anonymous_marking": self.anon_var.get()})
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


# ══ Appeals ═══════════════════════════════════════════════════════

class AppealsPane:
    def __init__(self, nb: ttk.Notebook, owner: WorkflowTab) -> None:
        self.owner = owner
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Appeals")
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", pady=(6, 4))
        self.scope_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Whole college",
                          variable=self.scope_var,
                          command=self.refresh).pack(side="left")
        self.open_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Open only",
                          variable=self.open_var,
                          command=self.refresh).pack(side="left", padx=8)
        ttk.Button(bar, text="Raise appeal",
                    command=self._raise).pack(side="left", padx=(16, 4))
        ttk.Button(bar, text="Assign reviewer",
                    command=self._assign).pack(side="left", padx=4)
        ttk.Button(bar, text="Resolve",
                    command=self._resolve).pack(side="left", padx=4)
        ttk.Button(bar, text="View",
                    command=self._view).pack(side="left", padx=4)

        self.tree = _tree(self.frame, [
            ("id", "#", 45), ("sub", "Sub", 45),
            ("student", "Student", 80), ("name", "Name", 150),
            ("type", "Type", 150), ("status", "Status", 110),
            ("raised", "Raised", 95), ("mark", "At appeal", 75),
            ("after", "After", 65), ("reviewer", "Reviewer", 130),
        ])
        self.tree.tag_configure("open",   background="#fff7d0")
        self.tree.tag_configure("upheld", background="#d8f4d8")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda _e: self._view())

        self.summary_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.summary_var,
                   anchor="w").pack(fill="x", pady=(6, 4))

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        a = self.owner.assignment()
        scope = None if self.scope_var.get() or a is None \
            else a.assignment_id
        rows = feedback.list_appeals(assignment_id=scope,
                                      open_only=self.open_var.get())
        names = _names()
        for appeal in rows:
            sub = data.get_submission(appeal.submission_id)
            sid = sub.student_id if sub else "?"
            tags = ["open"] if appeal.is_open else []
            if appeal.status in ("Upheld", "Partly upheld"):
                tags = ["upheld"]
            self.tree.insert("", "end", iid=str(appeal.appeal_id),
                              values=(
                appeal.appeal_id, appeal.submission_id, sid,
                names.get(sid, "?"), appeal.appeal_type,
                appeal.status, appeal.raised_on,
                _fmt(appeal.marks_at_appeal),
                _fmt(appeal.marks_after),
                appeal.reviewer or "—",
            ), tags=tuple(tags))
        summary = feedback.appeal_summary(assignment_id=scope)
        self.summary_var.set(
            f"{summary['_total']} appeal(s)  ·  {summary['_open']} open"
            f"  ·  {summary['_upheld']} upheld")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Appeals", "Select an appeal first.")
            return None
        return int(sel[0])

    def _raise(self) -> None:
        a = self.owner.need_assignment("Appeals")
        if a is None:
            return
        RaiseAppealDialog(self.frame.winfo_toplevel(), assignment=a,
                           on_save=self.owner.refresh_panes)

    def _assign(self) -> None:
        appeal_id = self._selected_id()
        if appeal_id is None:
            return
        AssignReviewerDialog(self.frame.winfo_toplevel(),
                              appeal_id=appeal_id,
                              on_save=self.owner.refresh_panes)

    def _resolve(self) -> None:
        appeal_id = self._selected_id()
        if appeal_id is None:
            return
        ResolveAppealDialog(self.frame.winfo_toplevel(),
                             appeal_id=appeal_id,
                             on_save=self.owner.refresh_panes)

    def _view(self) -> None:
        appeal_id = self._selected_id()
        if appeal_id is None:
            return
        appeal = feedback.get_appeal(appeal_id)
        if appeal is None:
            return
        lines = [
            f"Appeal #{appeal.appeal_id}  [{appeal.status}]",
            f"Type: {appeal.appeal_type}",
            f"Raised {appeal.raised_on} by {appeal.raised_by or '—'}",
            f"Mark at appeal: {_fmt(appeal.marks_at_appeal)} "
            f"({appeal.grade_at_appeal or '—'})",
            "", "Grounds:", appeal.grounds,
        ]
        if appeal.outcome:
            lines += ["", f"Outcome ({appeal.outcome_on}):",
                      appeal.outcome]
            if appeal.mark_changed is not None:
                lines.append(f"Mark changed by {appeal.mark_changed:+g} "
                             f"to {_fmt(appeal.marks_after)}")
        messagebox.showinfo("Appeal", "\n".join(lines))


class RaiseAppealDialog:
    def __init__(self, parent: tk.Misc, *, assignment,
                 on_save: Callable[[], None]) -> None:
        self.assignment = assignment
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Raise an appeal")
        self.win.geometry("620x460")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        outer = ttk.Frame(self.win, padding=12)
        outer.pack(fill="both", expand=True)

        self._subs = [s for s in data.list_submissions(
            assignment_id=assignment.assignment_id)
            if feedback.is_visible_to_student(s, assignment)]
        names = _names()
        ttk.Label(outer, text="Student:").grid(row=0, column=0,
                                                  sticky="e", pady=4)
        self.student_cb = ttk.Combobox(
            outer, state="readonly", width=44,
            values=[f"{s.student_id} — {names.get(s.student_id, '?')} "
                    f"({_fmt(s.marks)})" for s in self._subs])
        if self._subs:
            self.student_cb.current(0)
        self.student_cb.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(outer, text="Type:").grid(row=1, column=0, sticky="e",
                                               pady=4)
        self.type_cb = ttk.Combobox(outer, values=APPEAL_TYPES,
                                      state="readonly", width=26)
        self.type_cb.set(feedback.DEFAULT_APPEAL_TYPE)
        self.type_cb.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(outer, text="Grounds:").grid(row=2, column=0,
                                                  sticky="ne", pady=4)
        self.grounds = tk.Text(outer, width=52, height=12, wrap="word")
        self.grounds.grid(row=2, column=1, sticky="w", padx=6)

        self.late_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(outer, text="Accept even if the window has closed",
                          variable=self.late_var).grid(
            row=3, column=1, sticky="w", padx=6, pady=(6, 0))

        if not self._subs:
            ttk.Label(
                outer,
                text="No results on this assignment have been released "
                     "yet.\nA mark can only be appealed once the student "
                     "can see it.",
                foreground="#553").grid(row=4, column=1, sticky="w",
                                          padx=6, pady=(8, 0))

        bar = ttk.Frame(outer)
        bar.grid(row=5, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Raise",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        idx = self.student_cb.current()
        if idx < 0 or idx >= len(self._subs):
            messagebox.showerror("Appeal", "Pick a student.")
            return
        sub = self._subs[idx]
        try:
            feedback.raise_appeal(
                sub.submission_id,
                grounds=self.grounds.get("1.0", "end").strip(),
                appeal_type=self.type_cb.get(),
                raised_by=sub.student_id,
                allow_out_of_window=self.late_var.get())
        except Exception as e:
            messagebox.showerror("Appeal failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class AssignReviewerDialog:
    def __init__(self, parent: tk.Misc, *, appeal_id: int,
                 on_save: Callable[[], None]) -> None:
        self.appeal_id = appeal_id
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Assign reviewer — appeal #{appeal_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="Reviewer:").grid(row=0, column=0,
                                                  sticky="e", pady=4)
        self.reviewer_cb = ttk.Combobox(
            form, values=("",) + tuple(_teachers()), width=30)
        self.reviewer_cb.grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Notes:").grid(row=1, column=0, sticky="e",
                                               pady=4)
        self.notes_e = ttk.Entry(form, width=44)
        self.notes_e.grid(row=1, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=2, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Assign",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            feedback.start_review(
                self.appeal_id,
                reviewer=self.reviewer_cb.get().strip(),
                notes=self.notes_e.get().strip() or None)
        except Exception as e:
            messagebox.showerror("Assign failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class ResolveAppealDialog:
    def __init__(self, parent: tk.Misc, *, appeal_id: int,
                 on_save: Callable[[], None]) -> None:
        self.appeal_id = appeal_id
        self.on_save = on_save
        self.appeal = feedback.get_appeal(appeal_id)
        self.win = tk.Toplevel(parent)
        self.win.title(f"Resolve appeal #{appeal_id}")
        self.win.geometry("600x440")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        outer = ttk.Frame(self.win, padding=12)
        outer.pack(fill="both", expand=True)
        if self.appeal is None:
            ttk.Label(outer, text="Appeal not found.").pack()
            return
        ttk.Label(outer,
                   text=f"Mark at appeal: "
                        f"{_fmt(self.appeal.marks_at_appeal)}",
                   font=("", 10, "bold")).grid(row=0, column=0,
                                                 columnspan=2,
                                                 sticky="w",
                                                 pady=(0, 8))
        ttk.Label(outer, text="Outcome:").grid(row=1, column=0,
                                                  sticky="e", pady=4)
        self.status_cb = ttk.Combobox(outer,
                                        values=CLOSED_APPEAL_STATUSES,
                                        state="readonly", width=18)
        self.status_cb.set("Rejected")
        self.status_cb.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(outer, text="New mark:").grid(row=2, column=0,
                                                   sticky="e", pady=4)
        self.marks_e = ttk.Entry(outer, width=10)
        self.marks_e.grid(row=2, column=1, sticky="w", padx=6)
        ttk.Label(outer, text="(blank leaves the mark unchanged)",
                   foreground="#555").grid(row=2, column=2, sticky="w")

        ttk.Label(outer, text="Resolved by:").grid(row=3, column=0,
                                                      sticky="e", pady=4)
        self.by_cb = ttk.Combobox(outer,
                                    values=("",) + tuple(_teachers()),
                                    width=28)
        self.by_cb.grid(row=3, column=1, columnspan=2, sticky="w",
                          padx=6)

        ttk.Label(outer, text="Reasoning:").grid(row=4, column=0,
                                                    sticky="ne", pady=4)
        self.outcome = tk.Text(outer, width=48, height=10, wrap="word")
        self.outcome.grid(row=4, column=1, columnspan=2, sticky="w",
                            padx=6)

        bar = ttk.Frame(outer)
        bar.grid(row=5, column=0, columnspan=3, pady=(12, 0))
        ttk.Button(bar, text="Resolve",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        raw = self.marks_e.get().strip()
        new_marks = None
        if raw:
            try:
                new_marks = float(raw)
            except ValueError:
                messagebox.showerror("Resolve",
                                       "New mark must be a number.")
                return
        try:
            feedback.resolve_appeal(
                self.appeal_id, status=self.status_cb.get(),
                outcome=self.outcome.get("1.0", "end").strip(),
                new_marks=new_marks,
                resolved_by=self.by_cb.get().strip() or None)
        except Exception as e:
            messagebox.showerror("Resolve failed", str(e))
            return
        self.win.destroy()
        self.on_save()


# ══ Objective questions ═══════════════════════════════════════════

class QuestionsPane:
    def __init__(self, nb: ttk.Notebook, owner: WorkflowTab) -> None:
        self.owner = owner
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Questions")
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", pady=(6, 4))
        ttk.Button(bar, text="Add question",
                    command=self._add).pack(side="left")
        ttk.Button(bar, text="Delete question",
                    command=self._delete).pack(side="left", padx=4)
        ttk.Button(bar, text="Enter answers",
                    command=self._answers).pack(side="left", padx=(16, 4))
        ttk.Button(bar, text="Auto-mark class",
                    command=self._auto_mark).pack(side="left", padx=4)

        self.tree = _tree(self.frame, [
            ("id", "#", 45), ("pos", "Q", 40),
            ("type", "Type", 130), ("marks", "Marks", 60),
            ("answered", "Answered", 75), ("correct", "Correct", 65),
            ("facility", "Facility", 70), ("prompt", "Prompt", 300),
            ("key", "Key", 180),
        ], height=14)
        self.tree.tag_configure("hard", background="#ffd0d0")
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
        stats = {row["question_id"]: row
                 for row in assess.question_analysis(a.assignment_id)}
        for q in assess.list_questions(a.assignment_id):
            row = stats.get(q.question_id, {})
            facility = row.get("facility")
            self.tree.insert("", "end", iid=str(q.question_id), values=(
                q.question_id, q.position, q.question_type,
                _fmt(q.marks), row.get("answered", 0),
                row.get("correct", 0),
                f"{facility:g}%" if facility is not None else "—",
                q.prompt, " or ".join(q.key_list),
            ), tags=("hard",) if (facility is not None
                                   and facility < 50) else ())
        total = assess.questions_total(a.assignment_id)
        self.summary_var.set(
            f"{len(assess.list_questions(a.assignment_id))} question(s), "
            f"{total:g} marks. Rows in red were answered correctly by "
            f"fewer than half the cohort.")

    def _add(self) -> None:
        a = self.owner.need_assignment("Questions")
        if a is None:
            return
        QuestionDialog(self.frame.winfo_toplevel(), assignment=a,
                        on_save=self.owner.refresh_panes)

    def _delete(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Questions",
                                  "Select a question first.")
            return
        if not messagebox.askyesno(
                "Delete",
                "Delete this question and every answer to it?"):
            return
        assess.delete_question(int(sel[0]))
        self.owner.refresh_panes()

    def _answers(self) -> None:
        a = self.owner.need_assignment("Answers")
        if a is None:
            return
        if not assess.list_questions(a.assignment_id):
            messagebox.showinfo("Answers",
                                  "Add some questions first.")
            return
        AnswerEntryDialog(self.frame.winfo_toplevel(), assignment=a,
                           on_save=self.owner.refresh_panes)

    def _auto_mark(self) -> None:
        a = self.owner.need_assignment("Auto-mark")
        if a is None:
            return
        result = assess.auto_mark_assignment(a.assignment_id)
        messagebox.showinfo(
            "Auto-mark",
            f"Marked {result['submissions_marked']} submission(s).\n"
            f"Average: {_fmt(result['average_marks'])} marks.")
        self.owner.refresh_panes()


class QuestionDialog:
    def __init__(self, parent: tk.Misc, *, assignment,
                 on_save: Callable[[], None]) -> None:
        self.assignment = assignment
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Add question")
        self.win.geometry("640x480")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)

        ttk.Label(form, text="Type:").grid(row=0, column=0, sticky="e",
                                              pady=4)
        self.type_cb = ttk.Combobox(form, values=QUESTION_TYPES,
                                      state="readonly", width=20)
        self.type_cb.set(assess.DEFAULT_QUESTION_TYPE)
        self.type_cb.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Marks:").grid(row=0, column=2, sticky="e",
                                               pady=4)
        self.marks_e = ttk.Entry(form, width=8)
        self.marks_e.insert(0, "1")
        self.marks_e.grid(row=0, column=3, sticky="w", padx=6)

        ttk.Label(form, text="Prompt:").grid(row=1, column=0,
                                                sticky="ne", pady=4)
        self.prompt = tk.Text(form, width=54, height=4, wrap="word")
        self.prompt.grid(row=1, column=1, columnspan=3, sticky="w",
                           padx=6)

        ttk.Label(form, text="Options:").grid(row=2, column=0,
                                                 sticky="e", pady=4)
        self.options_e = ttk.Entry(form, width=54)
        self.options_e.grid(row=2, column=1, columnspan=3, sticky="w",
                              padx=6)

        ttk.Label(form, text="Answer key:").grid(row=3, column=0,
                                                    sticky="e", pady=4)
        self.key_e = ttk.Entry(form, width=54)
        self.key_e.grid(row=3, column=1, columnspan=3, sticky="w",
                          padx=6)

        ttk.Label(form, text="Tolerance:").grid(row=4, column=0,
                                                   sticky="e", pady=4)
        self.tolerance_e = ttk.Entry(form, width=8)
        self.tolerance_e.grid(row=4, column=1, sticky="w", padx=6)
        self.case_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(form, text="Case sensitive",
                          variable=self.case_var).grid(row=4, column=2,
                                                         columnspan=2,
                                                         sticky="w")

        ttk.Label(
            form,
            text="Options and keys are pipe-separated:\n"
                 "  options 'London|Paris|Rome', key 'Paris'\n"
                 "  key 'photosynthesis|photo-synthesis' accepts either\n"
                 "Short answers ignore case, spacing and punctuation.\n"
                 "Tolerance applies to numeric answers only.",
            foreground="#555").grid(row=5, column=1, columnspan=3,
                                      sticky="w", padx=6, pady=(10, 0))

        bar = ttk.Frame(form)
        bar.grid(row=6, column=0, columnspan=4, pady=(12, 0))
        ttk.Button(bar, text="Add",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            assess.add_question(self.assignment.assignment_id, {
                "question_type": self.type_cb.get(),
                "prompt": self.prompt.get("1.0", "end").strip(),
                "options": self.options_e.get().strip(),
                "answer_key": self.key_e.get().strip(),
                "marks": self.marks_e.get().strip() or 1,
                "tolerance": self.tolerance_e.get().strip() or None,
                "case_sensitive": self.case_var.get()})
        except Exception as e:
            messagebox.showerror("Add failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class AnswerEntryDialog:
    """Enter one student's answers, marked as you go."""

    def __init__(self, parent: tk.Misc, *, assignment,
                 on_save: Callable[[], None]) -> None:
        self.assignment = assignment
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Enter answers")
        self.win.geometry("760x600")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._entries: dict[int, ttk.Entry] = {}
        self._subs = data.list_submissions(
            assignment_id=assignment.assignment_id)
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self.win, padding=12)
        outer.pack(fill="both", expand=True)
        names = _names()
        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, text="Student:").pack(side="left")
        self.student_cb = ttk.Combobox(
            bar, state="readonly", width=40,
            values=[f"{s.student_id} — {names.get(s.student_id, '?')}"
                    for s in self._subs])
        if self._subs:
            self.student_cb.current(0)
        self.student_cb.pack(side="left", padx=(4, 8))
        self.student_cb.bind("<<ComboboxSelected>>",
                              lambda _e: self._load())

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

        for row, q in enumerate(
                assess.list_questions(self.assignment.assignment_id)):
            box = ttk.LabelFrame(
                body, text=f"Q{q.position}  [{q.question_type}]  "
                             f"{q.marks:g} mark(s)", padding=8)
            box.grid(row=row, column=0, sticky="ew", pady=4, padx=2)
            ttk.Label(box, text=q.prompt, wraplength=620,
                       justify="left").grid(row=0, column=0,
                                              columnspan=2, sticky="w")
            if q.option_list:
                ttk.Label(box,
                           text="Options: " + " / ".join(q.option_list),
                           foreground="#555").grid(row=1, column=0,
                                                     columnspan=2,
                                                     sticky="w")
            entry = ttk.Entry(box, width=44)
            entry.grid(row=2, column=0, sticky="w", pady=(6, 0))
            self._entries[q.question_id] = entry

        foot = ttk.Frame(self.win, padding=(12, 0, 12, 12))
        foot.pack(fill="x")
        self.result_var = tk.StringVar(value="")
        ttk.Label(foot, textvariable=self.result_var,
                   font=("", 10, "bold")).pack(anchor="w", pady=(0, 6))
        ttk.Button(foot, text="Save and mark",
                    command=self._save).pack(side="left")
        ttk.Button(foot, text="Close",
                    command=self._close).pack(side="left", padx=8)
        self._load()

    def _current(self):
        idx = self.student_cb.current()
        if 0 <= idx < len(self._subs):
            return self._subs[idx]
        return None

    def _load(self) -> None:
        sub = self._current()
        for entry in self._entries.values():
            entry.delete(0, "end")
        if sub is None:
            return
        for answer in assess.list_answers(sub.submission_id):
            entry = self._entries.get(answer.question_id)
            if entry is not None and answer.response:
                entry.insert(0, answer.response)
        self.result_var.set(
            assess.auto_mark(sub.submission_id, store=False).message)

    def _save(self) -> None:
        sub = self._current()
        if sub is None:
            messagebox.showerror("Answers", "Pick a student.")
            return
        try:
            for question_id, entry in self._entries.items():
                raw = entry.get().strip()
                if not raw:
                    continue
                assess.record_answer(sub.submission_id, question_id,
                                      response=raw)
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        result = assess.auto_mark(sub.submission_id)
        self.result_var.set(result.message)
        messagebox.showinfo("Marked", result.message)

    def _close(self) -> None:
        self.win.destroy()
        self.on_save()


# ══ Groups ════════════════════════════════════════════════════════

class GroupsPane:
    def __init__(self, nb: ttk.Notebook, owner: WorkflowTab) -> None:
        self.owner = owner
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Groups")
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", pady=(6, 4))
        ttk.Button(bar, text="Create group",
                    command=self._create).pack(side="left")
        ttk.Button(bar, text="Add member",
                    command=self._add_member).pack(side="left", padx=4)
        ttk.Button(bar, text="Remove member",
                    command=self._remove_member).pack(side="left", padx=4)
        ttk.Button(bar, text="Adjustment",
                    command=self._adjust).pack(side="left", padx=(16, 4))
        ttk.Button(bar, text="Mark group",
                    command=self._mark).pack(side="left", padx=4)
        ttk.Button(bar, text="Disband",
                    command=self._delete).pack(side="left", padx=4)

        self.tree = ttk.Treeview(
            self.frame,
            columns=("student", "name", "role", "adjust", "effective",
                     "marks", "reason"),
            show="tree headings", height=14)
        self.tree.heading("#0", text="Group / member")
        self.tree.column("#0", width=200)
        for key, heading, width in (
                ("student", "Student", 80), ("name", "Name", 150),
                ("role", "Role", 90), ("adjust", "Adj", 55),
                ("effective", "Effective", 75), ("marks", "Mark", 60),
                ("reason", "Reason", 220)):
            self.tree.heading(key, text=heading)
            self.tree.column(key, width=width,
                              anchor="e" if width <= 75 else "w")
        self.tree.tag_configure("adjusted", background="#fff7d0")
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
        for group in assess.list_groups(a.assignment_id):
            detail = assess.get_group_detail(group.group_id)
            if detail is None:
                continue
            node = self.tree.insert(
                "", "end", iid=f"g{group.group_id}",
                text=f"{group.name}", open=True,
                values=("", "", "", "", "",
                        _fmt(group.group_marks), detail.message))
            for member in detail.members:
                effective = member.effective_marks(group.group_marks)
                sub = data.get_submission(member.submission_id)
                self.tree.insert(
                    node, "end", iid=f"m{member.submission_id}",
                    text="", values=(
                        member.student_id, member.student_name,
                        member.role,
                        f"{member.adjustment:+g}" if member.adjustment
                        else "—",
                        _fmt(effective),
                        _fmt(sub.marks if sub else None),
                        member.adjustment_reason or "—"),
                    tags=("adjusted",) if member.adjustment else ())
        ungrouped = assess.ungrouped_submissions(a.assignment_id)
        self.summary_var.set(
            f"{len(assess.list_groups(a.assignment_id))} group(s)  ·  "
            f"{len(ungrouped)} student(s) not in a group"
            + (": " + ", ".join(s.student_id for s in ungrouped[:10])
                if ungrouped else ""))

    def _selected_group_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        iid = sel[0]
        if iid.startswith("g"):
            return int(iid[1:])
        sub = data.get_submission(int(iid[1:]))
        return sub.group_id if sub else None

    def _selected_submission_id(self) -> int | None:
        sel = self.tree.selection()
        if sel and sel[0].startswith("m"):
            return int(sel[0][1:])
        return None

    def _create(self) -> None:
        a = self.owner.need_assignment("Groups")
        if a is None:
            return
        GroupDialog(self.frame.winfo_toplevel(), assignment=a,
                     on_save=self.owner.refresh_panes)

    def _add_member(self) -> None:
        a = self.owner.need_assignment("Groups")
        if a is None:
            return
        group_id = self._selected_group_id()
        if group_id is None:
            messagebox.showinfo("Groups", "Select a group first.")
            return
        AddMemberDialog(self.frame.winfo_toplevel(), assignment=a,
                         group_id=group_id,
                         on_save=self.owner.refresh_panes)

    def _remove_member(self) -> None:
        submission_id = self._selected_submission_id()
        if submission_id is None:
            messagebox.showinfo("Groups", "Select a member first.")
            return
        assess.remove_group_member(submission_id)
        self.owner.refresh_panes()

    def _adjust(self) -> None:
        submission_id = self._selected_submission_id()
        if submission_id is None:
            messagebox.showinfo("Groups", "Select a member first.")
            return
        AdjustmentDialog(self.frame.winfo_toplevel(),
                          submission_id=submission_id,
                          on_save=self.owner.refresh_panes)

    def _mark(self) -> None:
        group_id = self._selected_group_id()
        if group_id is None:
            messagebox.showinfo("Groups", "Select a group first.")
            return
        MarkGroupDialog(self.frame.winfo_toplevel(), group_id=group_id,
                         on_save=self.owner.refresh_panes)

    def _delete(self) -> None:
        group_id = self._selected_group_id()
        if group_id is None:
            messagebox.showinfo("Groups", "Select a group first.")
            return
        if not messagebox.askyesno(
                "Disband",
                "Disband this group?\n\nMembers keep their submissions "
                "and any marks already applied."):
            return
        assess.delete_group(group_id)
        self.owner.refresh_panes()


class GroupDialog:
    def __init__(self, parent: tk.Misc, *, assignment,
                 on_save: Callable[[], None]) -> None:
        self.assignment = assignment
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Create group")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="Name:").grid(row=0, column=0, sticky="e",
                                              pady=4)
        self.name_e = ttk.Entry(form, width=30)
        self.name_e.grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Notes:").grid(row=1, column=0, sticky="e",
                                               pady=4)
        self.notes_e = ttk.Entry(form, width=44)
        self.notes_e.grid(row=1, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=2, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Create",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            assess.create_group(self.assignment.assignment_id,
                                 self.name_e.get().strip(),
                                 notes=self.notes_e.get().strip()
                                 or None)
        except Exception as e:
            messagebox.showerror("Create failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class AddMemberDialog:
    def __init__(self, parent: tk.Misc, *, assignment, group_id: int,
                 on_save: Callable[[], None]) -> None:
        self.group_id = group_id
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Add group member")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        names = _names()
        self._subs = assess.ungrouped_submissions(
            assignment.assignment_id)
        ttk.Label(form, text="Student:").grid(row=0, column=0,
                                                 sticky="e", pady=4)
        self.student_cb = ttk.Combobox(
            form, state="readonly", width=40,
            values=[f"{s.student_id} — {names.get(s.student_id, '?')}"
                    for s in self._subs])
        if self._subs:
            self.student_cb.current(0)
        self.student_cb.grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Role:").grid(row=1, column=0, sticky="e",
                                              pady=4)
        self.role_cb = ttk.Combobox(form, values=GROUP_ROLES,
                                      state="readonly", width=16)
        self.role_cb.set(assess.DEFAULT_GROUP_ROLE)
        self.role_cb.grid(row=1, column=1, sticky="w", padx=6)
        if not self._subs:
            ttk.Label(form,
                       text="Everyone on this assignment is already in "
                            "a group.",
                       foreground="#553").grid(row=2, column=1,
                                                 sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=3, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Add",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        idx = self.student_cb.current()
        if idx < 0 or idx >= len(self._subs):
            messagebox.showerror("Add", "Pick a student.")
            return
        try:
            assess.add_group_member(self.group_id,
                                     self._subs[idx].submission_id,
                                     role=self.role_cb.get())
        except Exception as e:
            messagebox.showerror("Add failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class AdjustmentDialog:
    def __init__(self, parent: tk.Misc, *, submission_id: int,
                 on_save: Callable[[], None]) -> None:
        self.submission_id = submission_id
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Per-member adjustment")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        sub = data.get_submission(submission_id)
        ttk.Label(
            form,
            text="Three students who did the work and one who didn't\n"
                 "cannot all take the same mark.",
            foreground="#555").grid(row=0, column=0, columnspan=2,
                                      sticky="w", pady=(0, 8))
        ttk.Label(form, text="Adjustment:").grid(row=1, column=0,
                                                    sticky="e", pady=4)
        self.adjust_e = ttk.Entry(form, width=10)
        if sub and sub.group_adjustment:
            self.adjust_e.insert(0, f"{sub.group_adjustment:g}")
        self.adjust_e.grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(form, text="marks, e.g. -5 or +3",
                   foreground="#555").grid(row=1, column=2, sticky="w")
        ttk.Label(form, text="Reason:").grid(row=2, column=0, sticky="e",
                                                pady=4)
        self.reason_e = ttk.Entry(form, width=44)
        self.reason_e.grid(row=2, column=1, columnspan=2, sticky="w",
                             padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=3, column=0, columnspan=3, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            assess.set_member_adjustment(
                self.submission_id,
                adjustment=float(self.adjust_e.get().strip() or 0),
                reason=self.reason_e.get().strip() or None)
        except (ValueError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class MarkGroupDialog:
    def __init__(self, parent: tk.Misc, *, group_id: int,
                 on_save: Callable[[], None]) -> None:
        self.group_id = group_id
        self.on_save = on_save
        self.detail = assess.get_group_detail(group_id)
        self.win = tk.Toplevel(parent)
        self.win.title("Mark group")
        self.win.geometry("520x360")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        outer = ttk.Frame(self.win, padding=12)
        outer.pack(fill="both", expand=True)
        if self.detail is None:
            ttk.Label(outer, text="Group not found.").pack()
            return
        ttk.Label(outer, text=self.detail.group.name,
                   font=("", 11, "bold")).pack(anchor="w")
        ttk.Label(outer, text=self.detail.message,
                   foreground="#555").pack(anchor="w", pady=(0, 8))

        form = ttk.Frame(outer)
        form.pack(fill="x")
        ttk.Label(form, text="Group mark:").grid(row=0, column=0,
                                                    sticky="e", pady=4)
        self.marks_e = ttk.Entry(form, width=10)
        if self.detail.group.group_marks is not None:
            self.marks_e.insert(0,
                                  _fmt(self.detail.group.group_marks, ""))
        self.marks_e.grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Marked by:").grid(row=1, column=0,
                                                   sticky="e", pady=4)
        self.by_cb = ttk.Combobox(form,
                                    values=("",) + tuple(_teachers()),
                                    width=26)
        self.by_cb.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(outer,
                   text="Each member's adjustment is applied on top, and "
                        "the\nresult goes through the marking pipeline — "
                        "so a member\nwho handed in late still takes the "
                        "late penalty.",
                   foreground="#555").pack(anchor="w", pady=(10, 0))

        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=(12, 0))
        ttk.Button(bar, text="Apply to members",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            marks = float(self.marks_e.get().strip())
        except ValueError:
            messagebox.showerror("Mark group",
                                   "Group mark must be a number.")
            return
        by = self.by_cb.get().strip() or None
        try:
            assess.set_group_marks(self.group_id, marks, marked_by=by)
            applied = assess.apply_group_marks(self.group_id,
                                                marked_by=by)
        except Exception as e:
            messagebox.showerror("Mark failed", str(e))
            return
        messagebox.showinfo(
            "Marked",
            "\n".join(f"{s.student_id}: {_fmt(s.marks)}"
                      for s in applied))
        self.win.destroy()
        self.on_save()


# ══ Peer and self assessment ══════════════════════════════════════

class PeerPane:
    def __init__(self, nb: ttk.Notebook, owner: WorkflowTab) -> None:
        self.owner = owner
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Peer & Self")
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", pady=(6, 4))
        ttk.Label(bar, text="Combine peers by:").pack(side="left")
        self.mode_cb = ttk.Combobox(bar, values=PEER_SCORE_MODES,
                                      state="readonly", width=14)
        self.mode_cb.set(assess.DEFAULT_PEER_SCORE_MODE)
        self.mode_cb.pack(side="left", padx=(2, 8))
        self.mode_cb.bind("<<ComboboxSelected>>",
                           lambda _e: self.refresh())
        ttk.Button(bar, text="Record peer review",
                    command=self._record_peer).pack(side="left", padx=4)
        ttk.Button(bar, text="Record self-assessment",
                    command=self._record_self).pack(side="left", padx=4)
        ttk.Button(bar, text="Blend teacher + peer",
                    command=self._blend).pack(side="left", padx=4)

        self.tree = _tree(self.frame, [
            ("id", "Sub", 45), ("student", "Student", 80),
            ("name", "Name", 150), ("reviewers", "Reviewers", 75),
            ("peer", "Peer", 60), ("spread", "Spread", 65),
            ("predicted", "Predicted", 75), ("marks", "Actual", 65),
            ("gap", "Gap", 55), ("judgement", "Judgement", 120),
        ], height=14)
        self.tree.tag_configure("over",  background="#ffd0d0")
        self.tree.tag_configure("under", background="#d8f4d8")
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
        mode = self.mode_cb.get() or assess.DEFAULT_PEER_SCORE_MODE
        for sub in data.list_submissions(assignment_id=a.assignment_id):
            peer = assess.peer_summary(sub.submission_id, mode=mode,
                                        store=False)
            self_row = assess.get_self_assessment(sub.submission_id)
            tags = []
            if self_row.accuracy == "Overestimated":
                tags.append("over")
            elif self_row.accuracy == "Underestimated":
                tags.append("under")
            self.tree.insert("", "end", iid=str(sub.submission_id),
                              values=(
                sub.submission_id, sub.student_id,
                names.get(sub.student_id, "?"),
                peer.reviewer_count or "—", _fmt(peer.score),
                _fmt(peer.spread), _fmt(self_row.predicted),
                _fmt(self_row.actual),
                f"{self_row.gap:+g}" if self_row.gap is not None else "—",
                self_row.accuracy or "—",
            ), tags=tuple(tags))
        coverage = assess.peer_review_coverage(a.assignment_id)
        calibration = assess.calibration_summary(a.assignment_id)
        weight = (f"{a.peer_assessment_weight:g}%"
                  if a.peer_assessment_weight else "not set")
        self.summary_var.set(
            f"Peer weight {weight}  ·  {coverage['reviewed']}"
            f"/{coverage['submissions']} reviewed  ·  "
            f"{calibration['assessed']} predicted-and-marked, "
            f"average gap {_fmt(calibration['average_gap'])} "
            f"({calibration['over']} over, {calibration['under']} under)")

    def _selected(self, action: str):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo(action, "Select a student first.")
            return None
        return data.get_submission(int(sel[0]))

    def _record_peer(self) -> None:
        a = self.owner.need_assignment("Peer review")
        if a is None:
            return
        sub = self._selected("Peer review")
        if sub is None:
            return
        PeerReviewDialog(self.frame.winfo_toplevel(), submission=sub,
                          assignment=a,
                          on_save=self.owner.refresh_panes)

    def _record_self(self) -> None:
        a = self.owner.need_assignment("Self-assessment")
        if a is None:
            return
        sub = self._selected("Self-assessment")
        if sub is None:
            return
        SelfAssessmentDialog(self.frame.winfo_toplevel(),
                              submission=sub, assignment=a,
                              on_save=self.owner.refresh_panes)

    def _blend(self) -> None:
        a = self.owner.need_assignment("Blend")
        if a is None:
            return
        if not a.peer_assessment_weight:
            messagebox.showinfo(
                "Blend",
                "This assignment has no peer weighting.\n\n"
                "Set 'Peer assessment weight' on the assignment first.")
            return
        sub = self._selected("Blend")
        if sub is None:
            return
        BlendDialog(self.frame.winfo_toplevel(), submission=sub,
                     assignment=a, mode=self.mode_cb.get(),
                     on_save=self.owner.refresh_panes)


class PeerReviewDialog:
    def __init__(self, parent: tk.Misc, *, submission, assignment,
                 on_save: Callable[[], None]) -> None:
        self.submission = submission
        self.assignment = assignment
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Peer review — {submission.student_id}")
        self.win.geometry("560x420")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        names = _names()

        peers = [s for s in data.list_submissions(
            assignment_id=assignment.assignment_id)
            if s.student_id != submission.student_id]
        self._peer_ids = [s.student_id for s in peers]
        ttk.Label(form, text="Reviewer:").grid(row=0, column=0,
                                                  sticky="e", pady=4)
        self.reviewer_cb = ttk.Combobox(
            form, state="readonly", width=40,
            values=[f"{s.student_id} — {names.get(s.student_id, '?')}"
                    for s in peers])
        if peers:
            self.reviewer_cb.current(0)
        self.reviewer_cb.grid(row=0, column=1, sticky="w", padx=6)

        self._criteria = marking.list_criteria(assignment.assignment_id)
        ttk.Label(form, text="Score against:").grid(row=1, column=0,
                                                       sticky="e", pady=4)
        self.criterion_cb = ttk.Combobox(
            form, state="readonly", width=40,
            values=["Overall"] + [f"#{c.criterion_id} {c.label}"
                                   for c in self._criteria])
        self.criterion_cb.current(0)
        self.criterion_cb.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Marks:").grid(row=2, column=0, sticky="e",
                                               pady=4)
        self.marks_e = ttk.Entry(form, width=10)
        self.marks_e.grid(row=2, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Comment:").grid(row=3, column=0,
                                                 sticky="ne", pady=4)
        self.comment = tk.Text(form, width=44, height=8, wrap="word")
        self.comment.grid(row=3, column=1, sticky="w", padx=6)

        bar = ttk.Frame(form)
        bar.grid(row=4, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Record",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        idx = self.reviewer_cb.current()
        if idx < 0 or idx >= len(self._peer_ids):
            messagebox.showerror("Peer review", "Pick a reviewer.")
            return
        criterion_id = None
        if self.criterion_cb.current() > 0:
            criterion_id = self._criteria[
                self.criterion_cb.current() - 1].criterion_id
        try:
            assess.record_peer_review(
                self.submission.submission_id,
                reviewer_student=self._peer_ids[idx],
                marks=float(self.marks_e.get().strip()),
                criterion_id=criterion_id,
                comment=self.comment.get("1.0", "end").strip() or None)
        except (ValueError, Exception) as e:
            messagebox.showerror("Record failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class SelfAssessmentDialog:
    def __init__(self, parent: tk.Misc, *, submission, assignment,
                 on_save: Callable[[], None]) -> None:
        self.submission = submission
        self.assignment = assignment
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Self-assessment — {submission.student_id}")
        self.win.geometry("540x360")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(
            form,
            text="The student's own prediction, recorded before the\n"
                 "mark is released. A prediction made afterwards\n"
                 "measures nothing, so this is refused once released.",
            foreground="#555").grid(row=0, column=0, columnspan=2,
                                      sticky="w", pady=(0, 8))
        ttk.Label(form, text="Predicted mark:").grid(row=1, column=0,
                                                        sticky="e",
                                                        pady=4)
        self.marks_e = ttk.Entry(form, width=10)
        if submission.self_predicted_marks is not None:
            self.marks_e.insert(
                0, _fmt(submission.self_predicted_marks, ""))
        self.marks_e.grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(form, text=f"out of {assignment.max_marks or '?'}",
                   foreground="#555").grid(row=1, column=2, sticky="w")
        ttk.Label(form, text="Note:").grid(row=2, column=0, sticky="ne",
                                              pady=4)
        self.note = tk.Text(form, width=44, height=8, wrap="word")
        if submission.self_assessment_note:
            self.note.insert("1.0", submission.self_assessment_note)
        self.note.grid(row=2, column=1, columnspan=2, sticky="w",
                         padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=3, column=0, columnspan=3, pady=(12, 0))
        ttk.Button(bar, text="Record",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            assess.record_self_assessment(
                self.submission.submission_id,
                predicted_marks=float(self.marks_e.get().strip()),
                note=self.note.get("1.0", "end").strip() or None)
        except (ValueError, Exception) as e:
            messagebox.showerror("Record failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class BlendDialog:
    def __init__(self, parent: tk.Misc, *, submission, assignment,
                 mode: str, on_save: Callable[[], None]) -> None:
        self.submission = submission
        self.assignment = assignment
        self.mode = mode or assess.DEFAULT_PEER_SCORE_MODE
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Blend — {submission.student_id}")
        self.win.geometry("520x300")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        outer = ttk.Frame(self.win, padding=12)
        outer.pack(fill="both", expand=True)
        summary = assess.peer_summary(submission.submission_id,
                                       mode=self.mode, store=False)
        ttk.Label(outer, text=summary.message,
                   font=("", 10, "bold")).pack(anchor="w")
        ttk.Label(outer,
                   text=f"Peer weight "
                        f"{assignment.peer_assessment_weight:g}%, "
                        f"combined by {self.mode}",
                   foreground="#555").pack(anchor="w", pady=(0, 8))

        form = ttk.Frame(outer)
        form.pack(fill="x")
        ttk.Label(form, text="Teacher's mark:").grid(row=0, column=0,
                                                        sticky="e",
                                                        pady=4)
        self.marks_e = ttk.Entry(form, width=10)
        if submission.raw_marks is not None:
            self.marks_e.insert(0, _fmt(submission.raw_marks, ""))
        self.marks_e.grid(row=0, column=1, sticky="w", padx=6)
        self.marks_e.bind("<KeyRelease>", lambda _e: self._preview())
        ttk.Label(form, text="Marked by:").grid(row=1, column=0,
                                                   sticky="e", pady=4)
        self.by_cb = ttk.Combobox(form,
                                    values=("",) + tuple(_teachers()),
                                    width=26)
        self.by_cb.set(assignment.teacher or "")
        self.by_cb.grid(row=1, column=1, sticky="w", padx=6)

        self.preview_var = tk.StringVar(value="")
        ttk.Label(outer, textvariable=self.preview_var,
                   font=("", 10, "bold")).pack(anchor="w", pady=(10, 0))
        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=(12, 0))
        ttk.Button(bar, text="Apply",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)
        self._preview()

    def _preview(self) -> None:
        raw = self.marks_e.get().strip()
        try:
            teacher = float(raw)
        except ValueError:
            self.preview_var.set("")
            return
        blended = assess.blended_marks(self.submission.submission_id,
                                        teacher_marks=teacher,
                                        mode=self.mode)
        self.preview_var.set(
            f"Blended: {_fmt(blended)}" if blended is not None
            else "No peer reviews — the teacher's mark stands")

    def _save(self) -> None:
        try:
            out = assess.apply_peer_blend(
                self.submission.submission_id,
                teacher_marks=float(self.marks_e.get().strip()),
                marked_by=self.by_cb.get().strip() or None,
                mode=self.mode)
        except (ValueError, Exception) as e:
            messagebox.showerror("Apply failed", str(e))
            return
        messagebox.showinfo(
            "Blended",
            f"{out.student_id} marked {_fmt(out.marks)} "
            f"(grade {out.grade or '—'})")
        self.win.destroy()
        self.on_save()


# ══ Components ════════════════════════════════════════════════════

class ComponentsPane:
    def __init__(self, nb: ttk.Notebook, owner: WorkflowTab) -> None:
        self.owner = owner
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Components")
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", pady=(6, 4))
        ttk.Button(bar, text="Link a component...",
                    command=self._link).pack(side="left")
        ttk.Button(bar, text="Unlink selected",
                    command=self._unlink).pack(side="left", padx=4)
        ttk.Button(bar, text="Roll up onto parent",
                    command=self._rollup).pack(side="left", padx=(16, 4))

        self.structure_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.structure_var,
                   anchor="w",
                   foreground="#555").pack(fill="x", pady=(0, 4))

        self.tree = _tree(self.frame, [
            ("student", "Student", 80), ("name", "Name", 150),
            ("weighted", "Weighted", 80), ("overall", "Overall", 70),
            ("grade", "Grade", 55), ("detail", "Components", 420),
        ], height=14)
        self.tree.tag_configure("incomplete", background="#fff7d0")
        self.tree.pack(fill="both", expand=True)

        self.summary_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.summary_var,
                   anchor="w").pack(fill="x", pady=(6, 4))

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        a = self.owner.assignment()
        if a is None:
            self.structure_var.set("")
            self.summary_var.set("")
            return
        components = data.list_components(a.assignment_id)
        if not components:
            if a.parent_assignment_id:
                parent = data.get_assignment(a.parent_assignment_id)
                self.structure_var.set(
                    f"This is a component of #{a.parent_assignment_id} "
                    f"{parent.title if parent else ''} "
                    f"({_fmt(a.component_weight)}% weight)")
            else:
                self.structure_var.set(
                    "Standalone assignment — no components")
            self.summary_var.set("")
            return

        weights = data.component_weights(a.assignment_id)
        parts = ", ".join(
            f"#{c.assignment_id} {c.title} "
            f"({weights.get(c.assignment_id, 0):g}%)"
            for c in components)
        total = sum(weights.values())
        warning = ("" if abs(total - 100.0) < 0.001
                   else f"   ⚠ weights total {total:g}%")
        self.structure_var.set(f"{len(components)} component(s): "
                                f"{parts}{warning}")

        names = _names()
        complete = 0
        for sub in data.list_submissions(assignment_id=a.assignment_id):
            roll = data.component_rollup(a.assignment_id,
                                          sub.student_id)
            if roll.complete:
                complete += 1
            detail = "  ".join(
                f"{c.assignment.title[:14]} {_fmt(c.percent)}%"
                for c in roll.components)
            self.tree.insert("", "end", iid=str(sub.submission_id),
                              values=(
                sub.student_id, names.get(sub.student_id, "?"),
                (f"{roll.weighted_percent:g}%"
                 if roll.weighted_percent is not None else "—"),
                _fmt(roll.overall_marks), roll.grade or "—", detail,
            ), tags=() if roll.complete else ("incomplete",))
        self.summary_var.set(
            f"{complete} student(s) have every component marked. "
            f"Rows in amber are still partial — their weighted figure "
            f"is rescaled to what has been marked so far.")

    def _link(self) -> None:
        a = self.owner.need_assignment("Components")
        if a is None:
            return
        LinkComponentDialog(self.frame.winfo_toplevel(), parent_a=a,
                             on_save=self.owner.refresh)

    def _unlink(self) -> None:
        a = self.owner.need_assignment("Components")
        if a is None:
            return
        components = data.list_components(a.assignment_id)
        if not components:
            messagebox.showinfo("Components",
                                  "This assignment has no components.")
            return
        names = [f"#{c.assignment_id} {c.title}" for c in components]
        UnlinkDialog(self.frame.winfo_toplevel(),
                      components=components, labels=names,
                      on_save=self.owner.refresh)

    def _rollup(self) -> None:
        a = self.owner.need_assignment("Rollup")
        if a is None:
            return
        if not data.list_components(a.assignment_id):
            messagebox.showinfo("Rollup",
                                  "This assignment has no components.")
            return
        if not messagebox.askyesno(
                "Rollup",
                "Write each student's weighted component result onto "
                "this assignment?\n\nStudents with unmarked components "
                "are skipped."):
            return
        result = data.rollup_all(a.assignment_id)
        messagebox.showinfo(
            "Rollup",
            f"Applied to {result['applied']} student(s).\n"
            f"{result['skipped']} skipped (no submission row on the "
            f"parent, or nothing marked yet).")
        self.owner.refresh_panes()


class LinkComponentDialog:
    def __init__(self, parent: tk.Misc, *, parent_a,
                 on_save: Callable[[], None]) -> None:
        self.parent_a = parent_a
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Link a component")
        self.win.geometry("620x300")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form,
                   text=f"Parent: #{parent_a.assignment_id} "
                        f"{parent_a.title}",
                   font=("", 10, "bold")).grid(row=0, column=0,
                                                 columnspan=2,
                                                 sticky="w",
                                                 pady=(0, 8))
        self._candidates = [
            a for a in data.list_assignments()
            if a.assignment_id != parent_a.assignment_id
            and a.parent_assignment_id is None
            and not data.list_components(a.assignment_id)]
        ttk.Label(form, text="Component:").grid(row=1, column=0,
                                                   sticky="e", pady=4)
        self.child_cb = ttk.Combobox(
            form, state="readonly", width=52,
            values=[f"#{a.assignment_id} {a.title} "
                    f"({a.subject_name}, max {_fmt(a.max_marks)})"
                    for a in self._candidates])
        if self._candidates:
            self.child_cb.current(0)
        self.child_cb.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Weight %:").grid(row=2, column=0,
                                                  sticky="e", pady=4)
        self.weight_e = ttk.Entry(form, width=10)
        self.weight_e.grid(row=2, column=1, sticky="w", padx=6)
        ttk.Label(
            form,
            text="Blank means an even split with the other components.\n"
                 "Composition is one level deep: a component cannot\n"
                 "itself have components.",
            foreground="#555").grid(row=3, column=1, sticky="w", padx=6,
                                      pady=(8, 0))

        bar = ttk.Frame(form)
        bar.grid(row=4, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Link",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        idx = self.child_cb.current()
        if idx < 0 or idx >= len(self._candidates):
            messagebox.showerror("Link", "Pick a component.")
            return
        try:
            data.update_assignment(
                self._candidates[idx].assignment_id, {
                    "parent_assignment_id":
                        self.parent_a.assignment_id,
                    "component_weight":
                        self.weight_e.get().strip() or None})
        except Exception as e:
            messagebox.showerror("Link failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class UnlinkDialog:
    def __init__(self, parent: tk.Misc, *, components,
                 labels: list[str],
                 on_save: Callable[[], None]) -> None:
        self.components = components
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Unlink a component")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="Component:").grid(row=0, column=0,
                                                   sticky="e", pady=4)
        self.cb = ttk.Combobox(form, values=labels, state="readonly",
                                 width=44)
        if labels:
            self.cb.current(0)
        self.cb.grid(row=0, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=1, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Unlink",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        idx = self.cb.current()
        if idx < 0:
            return
        data.update_assignment(
            self.components[idx].assignment_id,
            {"parent_assignment_id": None, "component_weight": None})
        self.win.destroy()
        self.on_save()
