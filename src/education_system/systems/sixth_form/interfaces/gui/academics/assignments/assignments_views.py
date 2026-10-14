"""Tkinter views for Sixth Form Assignments.

Notebook with 4 tabs:

* Assignments — left = filterable list, right = full detail + submissions
                table with submit / files / history / extension actions.
* Submissions — flat list of every submission, filterable by status /
                marked / unmarked / overdue / extended / flagged.
* Marking     — the class marking grid: rubrics, per-criterion marking,
                moderation, samples, penalties and the audit trail.
                Lives in :mod:`assignments_marking_views`.
* Summary     — counts and alerts.
"""

from __future__ import annotations
from education_system.systems.sixth_form.interfaces.gui._ui import grab_when_viewable

import datetime as _dt
import logging
import os
import shutil
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable
from education_system.platform import branding
from education_system.systems.sixth_form.domain.academics.assignments import (
    assignments as data,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)
from education_system.systems.sixth_form.domain.staff import (
    staff as staff_data,
)
from education_system.systems.sixth_form.domain.academics.courses import (
    courses as course_data,
)
from education_system.systems.sixth_form.domain.academics.assignments.assignments import (
    ASSIGNMENT_ATTACHMENT_KINDS,
    ASSIGNMENT_STATUSES,
    ASSIGNMENT_TYPES,
    Assignment,
    DEFAULT_ASSIGNMENT_STATUS,
    DEFAULT_ASSIGNMENT_TYPE,
    DEFAULT_SUBMISSION_STATUS,
    SUBMISSION_ATTACHMENT_KINDS,
    SUBMISSION_STATUSES,
    Submission,
    ValidationError,
    YEAR_GROUPS,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_assignments_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Assignments — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    AssignmentsTab(nb)
    SubmissionsTab(nb)
    # Imported late so this module and the marking views don't import
    # each other at load time.
    from education_system.systems.sixth_form.domain.academics.assignments import (
        assignments_insight_views,
        assignments_marking_views,
        assignments_planning_views,
        assignments_workflow_views,
    )
    assignments_marking_views.MarkingTab(nb)
    assignments_workflow_views.WorkflowTab(nb)
    assignments_planning_views.PlanningTab(nb)
    assignments_insight_views.InsightTab(nb)
    SummaryTab(nb)


def _today() -> str:
    return _dt.date.today().isoformat()


def _subject_options() -> list[str]:
    try:
        from education_system.systems.sixth_form.domain.academics.subjects import (
            subjects as _subjects,
        )
        return [s.name for s in _subjects.list_subjects()]
    except Exception:
        return []


def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}")
            for s in rows]


def _name_lookup() -> dict[str, str]:
    return {s.student_id: s.full_name
             for s in student_data.list_students()}


def _teacher_options() -> list[str]:
    """Active staff sorted by display name. Used for the teacher dropdown."""
    try:
        staff = staff_data.list_staff()
    except Exception:
        return []
    active = [s for s in staff if s.is_active]
    return sorted({s.full_name for s in active})


def _course_options() -> list[tuple[int, str]]:
    """(course_id, label) for the course dropdown."""
    try:
        rows = course_data.list_courses()
    except Exception:
        return []
    return [(c.course_id,
              f"{c.course_code} — {c.title} "
              f"(Y{c.year_group} {c.academic_year})")
            for c in rows]


# ══ Assignments tab ═══════════════════════════════════════════════

class AssignmentsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Assignments")
        self._selected_id: int | None = None
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Subject:").pack(side="left")
        self.f_subject = ttk.Combobox(
            bar, values=("",) + tuple(_subject_options()), width=20)
        self.f_subject.set("")
        self.f_subject.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Teacher:").pack(side="left")
        self.f_teacher = ttk.Combobox(
            bar, values=("",) + tuple(_teacher_options()),
            state="readonly", width=22)
        self.f_teacher.set("")
        self.f_teacher.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar,
                                       values=("",) + ASSIGNMENT_STATUSES,
                                       state="readonly", width=12)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Type:").pack(side="left")
        self.f_type = ttk.Combobox(bar,
                                     values=("",) + ASSIGNMENT_TYPES,
                                     state="readonly", width=18)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 8))

        self.open_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Open only",
                          variable=self.open_var,
                          command=self.refresh).pack(side="left", padx=4)
        self.overdue_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Overdue only",
                          variable=self.overdue_var,
                          command=self.refresh).pack(side="left", padx=4)

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=(16, 0))

        pane = ttk.Panedwindow(self.frame, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=8, pady=4)

        # Left: assignments list
        left = ttk.Frame(pane)
        pane.add(left, weight=2)
        cols = ("id", "due", "subject", "type", "teacher",
                "status", "progress", "title")
        self.tree = ttk.Treeview(left, columns=cols, show="headings")
        widths = {"id": 50, "due": 90, "subject": 130, "type": 100,
                  "teacher": 110, "status": 90, "progress": 90,
                  "title": 230}
        headings = {"id": "ID", "due": "Due", "subject": "Subject",
                    "type": "Type", "teacher": "Teacher",
                    "status": "Status", "progress": "Subs",
                    "title": "Title"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(left, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Draft",    background="#eef7ff")
        self.tree.tag_configure("Set",      background="#fff7d0")
        self.tree.tag_configure("Closed",   background="#eeeeee")
        self.tree.tag_configure("Graded",   background="#d8f4d8")
        self.tree.tag_configure("Archived", background="#eeeeee")
        self.tree.tag_configure("Overdue",  background="#ffd0d0")
        self.tree.bind("<<TreeviewSelect>>",
                        lambda _e: self._on_select())
        self.tree.bind("<Double-1>",
                        lambda _e: self._edit_assignment())

        # Right: detail + submissions
        right = ttk.Frame(pane)
        pane.add(right, weight=3)
        self.detail_var = tk.StringVar(
            value="Select an assignment on the left.")
        ttk.Label(right, textvariable=self.detail_var,
                   font=("", 11, "bold"),
                   anchor="w").pack(fill="x", padx=2, pady=(0, 4))
        self.subdetail_var = tk.StringVar(value="")
        ttk.Label(right, textvariable=self.subdetail_var,
                   foreground="#555",
                   anchor="w").pack(fill="x", padx=2, pady=(0, 6))

        sub_cols = ("id", "student", "name", "status", "due",
                     "attempt", "files", "words", "sim",
                     "marks", "grade", "marked_on")
        self.subs_tree = ttk.Treeview(right, columns=sub_cols,
                                          show="headings")
        sub_headings = {"id": "ID", "student": "Student",
                          "name": "Name", "status": "Status",
                          "due": "Due", "attempt": "Att",
                          "files": "Files", "words": "Words",
                          "sim": "Sim %",
                          "marks": "Marks", "grade": "Grade",
                          "marked_on": "Marked on"}
        sub_widths = {"id": 45, "student": 75, "name": 150,
                       "status": 90, "due": 90, "attempt": 45,
                       "files": 45, "words": 55, "sim": 55,
                       "marks": 60, "grade": 55,
                       "marked_on": 90}
        for c in sub_cols:
            self.subs_tree.heading(c, text=sub_headings[c])
            anchor = ("e" if c in ("marks", "words", "sim", "files",
                                    "attempt") else "w")
            self.subs_tree.column(c, width=sub_widths[c],
                                     anchor=anchor)
        svs = ttk.Scrollbar(right, orient="vertical",
                              command=self.subs_tree.yview)
        self.subs_tree.configure(yscrollcommand=svs.set)
        self.subs_tree.pack(side="left", fill="both", expand=True)
        svs.pack(side="right", fill="y")
        self.subs_tree.tag_configure("Submitted",
                                          background="#d8f4d8")
        self.subs_tree.tag_configure("Late",
                                          background="#fff7d0")
        self.subs_tree.tag_configure("Returned",
                                          background="#d8f4d8")
        self.subs_tree.tag_configure("Missing",
                                          background="#ffd0d0")
        self.subs_tree.tag_configure("Excused",
                                          background="#eeeeee")
        # Applied after the status tags so they win where both apply.
        self.subs_tree.tag_configure("Extended",
                                          background="#e6e0ff")
        self.subs_tree.tag_configure("Flagged",
                                          background="#ffe0b0")
        self.subs_tree.bind("<Double-1>",
                                lambda _e: self._mark_selected_sub())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(actions, text="Edit assignment",
                    command=self._edit_assignment).pack(side="left")
        ttk.Button(actions, text="Status",
                    command=self._status_assignment).pack(side="left",
                                                            padx=4)
        ttk.Button(actions, text="Delete assignment",
                    command=self._delete_assignment).pack(side="left",
                                                            padx=4)
        ttk.Button(actions, text="Late sweep",
                    command=self._late_sweep).pack(side="left", padx=4)
        ttk.Button(actions, text="Add student",
                    command=self._add_student).pack(side="left",
                                                      padx=(16, 4))
        ttk.Button(actions, text="Submit work",
                    command=self._submit_sub).pack(side="left", padx=2)
        ttk.Button(actions, text="Files",
                    command=self._sub_files).pack(side="left", padx=2)
        ttk.Button(actions, text="History",
                    command=self._sub_history).pack(side="left", padx=2)
        ttk.Button(actions, text="Extension",
                    command=self._sub_extension).pack(side="left", padx=2)
        ttk.Button(actions, text="Similarity",
                    command=self._sub_similarity).pack(side="left", padx=2)
        ttk.Button(actions, text="Mark",
                    command=self._mark_selected_sub).pack(side="left",
                                                            padx=2)
        ttk.Button(actions, text="Sub status",
                    command=self._sub_status).pack(side="left", padx=2)
        ttk.Button(actions, text="Delete submission",
                    command=self._delete_sub).pack(side="left", padx=2)
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="right")

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8, pady=(0, 8))

    def _clear(self) -> None:
        self.f_subject.set("")
        self.f_teacher.set("")
        self.f_status.current(0)
        self.f_type.current(0)
        self.open_var.set(False)
        self.overdue_var.set(False)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_assignments_with_detail(
                subject_name=self.f_subject.get().strip() or None,
                teacher_like=self.f_teacher.get().strip() or None,
                status=self.f_status.get() or None,
                assignment_type=self.f_type.get() or None,
                open_only=self.open_var.get(),
                overdue_only=self.overdue_var.get(),
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        for r in rows:
            a = r.assignment
            tags: list[str] = []
            if a.status in ASSIGNMENT_STATUSES:
                tags.append(a.status)
            if a.is_overdue:
                tags.append("Overdue")
            prog = f"{r.submitted_count}/{r.total_submissions}"
            self.tree.insert("", "end", iid=str(a.assignment_id), values=(
                a.assignment_id, a.due_date or "—",
                a.subject_name, a.assignment_type,
                a.teacher or "—", a.status, prog,
                a.title,
            ), tags=tuple(tags))
        self.count_var.set(f"{len(rows)} assignment(s).")

        # Restore selection
        if (self._selected_id is not None
                and self.tree.exists(str(self._selected_id))):
            self.tree.selection_set(str(self._selected_id))
            self._render_detail()
        else:
            self._selected_id = None
            self._clear_detail()

    def _on_select(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        try:
            self._selected_id = int(sel[0])
        except ValueError:
            return
        self._render_detail()

    def _clear_detail(self) -> None:
        for i in self.subs_tree.get_children():
            self.subs_tree.delete(i)
        self.detail_var.set(
            "Select an assignment on the left.")
        self.subdetail_var.set("")

    def _render_detail(self) -> None:
        for i in self.subs_tree.get_children():
            self.subs_tree.delete(i)
        if self._selected_id is None:
            return
        detail = data.get_assignment_detail(self._selected_id)
        if detail is None:
            self._clear_detail()
            return
        a = detail.assignment
        material = len(
            data.list_attachments(assignment_id=a.assignment_id))
        self.detail_var.set(f"#{a.assignment_id}  {a.title}")
        self.subdetail_var.set(
            f"{a.subject_name}  ·  {a.assignment_type}  ·  "
            f"Teacher: {a.teacher or '—'}  ·  "
            f"Due: {a.due_date or '—'}  ·  "
            f"Max: {a.max_marks or '—'}  ·  "
            f"Words: {a.word_limit or '—'}  ·  "
            f"Status: {a.status}  ·  "
            f"Submitted: {detail.submitted_count}/"
            f"{detail.total_submissions} "
            f"({detail.percent_submitted}%)  ·  "
            f"Avg: {detail.average_mark or '—'}  ·  "
            f"Material: {material} file(s)"
            + ("" if a.allow_resubmission
                else "  ·  resubmission locked"))
        names = _name_lookup()
        threshold = a.effective_similarity_threshold
        for s in detail.submissions:
            marks = (f"{s.marks}" if s.marks is not None else "—")
            tags = [s.status] if s.status in SUBMISSION_STATUSES else []
            due = data.effective_due_date(s, a)
            due_label = due or "—"
            if s.extended_due_date:
                due_label = f"{due} *"
                tags.append("Extended")
            attempt = (f"{s.attempt_no}"
                       + ("d" if s.is_draft and s.attempt_no else "")
                       if s.attempt_no else "—")
            file_count = len(
                data.list_attachments(submission_id=s.submission_id))
            sim = "—"
            if s.similarity_score is not None:
                sim = f"{s.similarity_score:.0f}"
                if s.similarity_score >= threshold:
                    sim += "!"
                    tags.append("Flagged")
            self.subs_tree.insert("", "end",
                                      iid=str(s.submission_id), values=(
                s.submission_id, s.student_id,
                names.get(s.student_id, "?"),
                s.status, due_label, attempt, file_count or "—",
                s.word_count if s.word_count is not None else "—",
                sim, marks, s.grade or "—",
                s.marked_on or "—",
            ), tags=tuple(tags))

    def _selected_assignment(self) -> Assignment | None:
        if self._selected_id is None:
            return None
        return data.get_assignment(self._selected_id)

    def _selected_sub_id(self) -> int | None:
        sel = self.subs_tree.selection()
        if not sel:
            return None
        return int(sel[0])

    # ── Assignment actions ────────────────────────────────────────
    def _new(self) -> None:
        AssignmentDialog(self.frame.winfo_toplevel(),
                            existing=None, on_save=self.refresh)

    def _edit_assignment(self) -> None:
        a = self._selected_assignment()
        if a is None:
            messagebox.showinfo("Edit",
                                  "Select an assignment first.")
            return
        AssignmentDialog(self.frame.winfo_toplevel(),
                            existing=a, on_save=self.refresh)

    def _status_assignment(self) -> None:
        a = self._selected_assignment()
        if a is None:
            messagebox.showinfo("Status",
                                  "Select an assignment first.")
            return
        AssignmentStatusDialog(self.frame.winfo_toplevel(),
                                  a, on_save=self.refresh)

    def _delete_assignment(self) -> None:
        a = self._selected_assignment()
        if a is None:
            messagebox.showinfo("Delete",
                                  "Select an assignment first.")
            return
        if not messagebox.askyesno(
                "Delete",
                f"Delete assignment #{a.assignment_id}? "
                "All submissions go too."):
            return
        try:
            data.delete_assignment(a.assignment_id)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self._selected_id = None
        self.refresh()

    # ── Submission actions ────────────────────────────────────────
    def _add_student(self) -> None:
        a = self._selected_assignment()
        if a is None:
            messagebox.showinfo("Add student",
                                  "Select an assignment first.")
            return
        AddStudentDialog(self.frame.winfo_toplevel(),
                            assignment=a, on_save=self.refresh)

    def _pick_sub(self, action: str) -> Submission | None:
        sid = self._selected_sub_id()
        if sid is None:
            messagebox.showinfo(action, "Select a submission first.")
            return None
        return data.get_submission(sid)

    def _submit_sub(self) -> None:
        sub = self._pick_sub("Submit work")
        if sub is None:
            return
        SubmitWorkDialog(self.frame.winfo_toplevel(), submission=sub,
                          assignment=self._selected_assignment(),
                          on_save=self.refresh)

    def _sub_files(self) -> None:
        sub = self._pick_sub("Files")
        if sub is None:
            return
        SubmissionFilesDialog(self.frame.winfo_toplevel(),
                               submission=sub, on_save=self.refresh)

    def _sub_history(self) -> None:
        sub = self._pick_sub("History")
        if sub is None:
            return
        VersionHistoryDialog(self.frame.winfo_toplevel(),
                              submission=sub, on_save=self.refresh)

    def _sub_extension(self) -> None:
        sub = self._pick_sub("Extension")
        if sub is None:
            return
        ExtensionDialog(self.frame.winfo_toplevel(), submission=sub,
                         assignment=self._selected_assignment(),
                         on_save=self.refresh)

    def _sub_similarity(self) -> None:
        sub = self._pick_sub("Similarity")
        if sub is None:
            return
        SimilarityDialog(self.frame.winfo_toplevel(), submission=sub,
                          assignment=self._selected_assignment(),
                          on_save=self.refresh)

    def _late_sweep(self) -> None:
        a = self._selected_assignment()
        scope_id = a.assignment_id if a else None
        scope = (f"assignment #{scope_id}" if scope_id
                 else "every open assignment")
        try:
            preview = data.sweep_late_submissions(
                assignment_id=scope_id, dry_run=True)
        except Exception as e:
            messagebox.showerror("Late sweep", str(e))
            return
        if not preview["overdue"]:
            messagebox.showinfo(
                "Late sweep",
                f"Nothing overdue on {scope}.")
            return
        if not messagebox.askyesno(
                "Late sweep",
                f"{preview['overdue']} submission(s) on {scope} are "
                f"past their deadline with nothing handed in.\n\n"
                "Mark them Missing? Extensions are honoured and work "
                "already submitted is left alone."):
            return
        try:
            result = data.sweep_late_submissions(assignment_id=scope_id)
        except Exception as e:
            messagebox.showerror("Late sweep", str(e))
            return
        messagebox.showinfo(
            "Late sweep",
            f"Marked {result['marked_missing']} submission(s) Missing.")
        self.refresh()

    def _mark_selected_sub(self) -> None:
        sid = self._selected_sub_id()
        if sid is None:
            messagebox.showinfo("Mark",
                                  "Select a submission first.")
            return
        sub = data.get_submission(sid)
        if sub is None:
            return
        a = self._selected_assignment()
        MarkDialog(self.frame.winfo_toplevel(),
                     submission=sub, assignment=a,
                     on_save=self.refresh)

    def _sub_status(self) -> None:
        sid = self._selected_sub_id()
        if sid is None:
            messagebox.showinfo("Status",
                                  "Select a submission first.")
            return
        sub = data.get_submission(sid)
        if sub is None:
            return
        SubStatusDialog(self.frame.winfo_toplevel(),
                          submission=sub, on_save=self.refresh)

    def _delete_sub(self) -> None:
        sid = self._selected_sub_id()
        if sid is None:
            messagebox.showinfo("Delete",
                                  "Select a submission first.")
            return
        if not messagebox.askyesno(
                "Delete", f"Delete submission #{sid}?"):
            return
        try:
            data.delete_submission(sid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


# ══ Submissions tab ════════════════════════════════════════════════

class SubmissionsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Submissions")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar,
                                       values=("",) + SUBMISSION_STATUSES,
                                       state="readonly", width=14)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 10))

        ttk.Label(bar, text="Student id:").pack(side="left")
        self.f_student = ttk.Entry(bar, width=12)
        self.f_student.pack(side="left", padx=(2, 10))

        self.marked_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Marked only",
                          variable=self.marked_var,
                          command=self.refresh).pack(side="left", padx=4)
        self.unmarked_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Unmarked only",
                          variable=self.unmarked_var,
                          command=self.refresh).pack(side="left", padx=4)
        self.overdue_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Overdue only",
                          variable=self.overdue_var,
                          command=self.refresh).pack(side="left", padx=4)
        self.extended_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Extended only",
                          variable=self.extended_var,
                          command=self.refresh).pack(side="left", padx=4)
        self.flagged_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Flagged only",
                          variable=self.flagged_var,
                          command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Late sweep",
                    command=self._late_sweep).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "assignment", "student", "name",
                "status", "due", "attempt", "files", "sim",
                "marks", "grade", "marked_on")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings")
        widths = {"id": 45, "assignment": 75, "student": 75,
                  "name": 160, "status": 90, "due": 90,
                  "attempt": 45, "files": 45, "sim": 55,
                  "marks": 60, "grade": 55, "marked_on": 90}
        headings = {"id": "ID", "assignment": "Assignment",
                    "student": "Student", "name": "Name",
                    "status": "Status", "due": "Due",
                    "attempt": "Att", "files": "Files", "sim": "Sim %",
                    "marks": "Marks",
                    "grade": "Grade", "marked_on": "Marked on"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = ("e" if c in ("marks", "sim", "files", "attempt")
                      else "w")
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Submitted", background="#d8f4d8")
        self.tree.tag_configure("Late",      background="#fff7d0")
        self.tree.tag_configure("Missing",   background="#ffd0d0")
        self.tree.tag_configure("Returned",  background="#d8f4d8")
        self.tree.tag_configure("Extended",  background="#e6e0ff")
        self.tree.tag_configure("Flagged",   background="#ffe0b0")

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8, pady=(0, 8))

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_submissions_with_detail(
                status=self.f_status.get() or None,
                student_id=self.f_student.get().strip() or None,
                marked_only=self.marked_var.get(),
                unmarked_only=self.unmarked_var.get(),
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return

        # The cross-cutting filters below aren't expressible as simple
        # column predicates (they read the effective deadline and the
        # per-assignment threshold), so narrow by id instead.
        flagged_ids = {s.submission_id
                        for s in data.list_flagged_submissions()}
        if self.overdue_var.get():
            overdue = {s.submission_id
                        for s in data.list_overdue_submissions()}
            rows = [r for r in rows
                    if r.submission.submission_id in overdue]
        if self.extended_var.get():
            rows = [r for r in rows
                    if r.submission.extended_due_date]
        if self.flagged_var.get():
            rows = [r for r in rows
                    if r.submission.submission_id in flagged_ids]

        for r in rows:
            s = r.submission
            marks = f"{s.marks}" if s.marks is not None else "—"
            tags = [s.status] if s.status in SUBMISSION_STATUSES else []
            due = data.effective_due_date(s)
            due_label = f"{due} *" if s.extended_due_date else (due or "—")
            if s.extended_due_date:
                tags.append("Extended")
            sim = "—"
            if s.similarity_score is not None:
                sim = f"{s.similarity_score:.0f}"
                if s.submission_id in flagged_ids:
                    sim += "!"
                    tags.append("Flagged")
            attempt = (f"{s.attempt_no}"
                       + ("d" if s.is_draft and s.attempt_no else "")
                       if s.attempt_no else "—")
            file_count = len(
                data.list_attachments(submission_id=s.submission_id))
            self.tree.insert("", "end", iid=str(s.submission_id), values=(
                s.submission_id, s.assignment_id,
                s.student_id, r.student_name,
                s.status, due_label, attempt, file_count or "—",
                sim, marks, s.grade or "—",
                s.marked_on or "—",
            ), tags=tuple(tags))
        self.count_var.set(f"{len(rows)} submission(s).")

    def _late_sweep(self) -> None:
        preview = data.sweep_late_submissions(dry_run=True)
        if not preview["overdue"]:
            messagebox.showinfo("Late sweep", "Nothing overdue.")
            return
        if not messagebox.askyesno(
                "Late sweep",
                f"{preview['overdue']} submission(s) across all open "
                "assignments are past their deadline with nothing "
                "handed in.\n\nMark them Missing? Extensions are "
                "honoured and work already submitted is left alone."):
            return
        result = data.sweep_late_submissions()
        messagebox.showinfo(
            "Late sweep",
            f"Marked {result['marked_missing']} submission(s) Missing.")
        self.refresh()


# ══ Summary tab ════════════════════════════════════════════════════

class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Upcoming window (days):").pack(side="left")
        self.window_e = ttk.Entry(bar, width=6)
        self.window_e.insert(0, "14")
        self.window_e.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left")

        self.text = tk.Text(self.frame, wrap="none", height=30,
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.text.configure(state="disabled")

    def refresh(self) -> None:
        try:
            win = int(self.window_e.get().strip() or "14")
        except ValueError:
            messagebox.showerror("Summary",
                                    "Window must be a number.")
            return
        summ = data.summary(upcoming_window_days=win)
        lines = [
            f"Total assignments : {summ.total_assignments}",
            f"Open              : {summ.open_count}",
            f"Overdue           : {summ.overdue}",
            f"Upcoming due ({win}d): {summ.upcoming_due}",
            "",
            f"Submissions       : {summ.total_submissions}",
            f"Submitted         : {summ.submitted_total}",
            f"Marked            : {summ.marked_total}",
            f"Overdue, not in   : {summ.overdue_submissions}",
            f"Active extensions : {summ.active_extensions}",
            f"Similarity flags  : {summ.flagged_similarity}",
            f"Files stored      : {summ.attachment_count} "
            f"({summ.attachment_bytes / 1048576:.1f} MB)",
            "",
            "By status:",
        ]
        for s in ASSIGNMENT_STATUSES:
            n = summ.by_status.get(s, 0)
            if n:
                lines.append(f"  {s:<12} : {n}")
        lines.append("")
        lines.append("By type:")
        for t in ASSIGNMENT_TYPES:
            n = summ.by_type.get(t, 0)
            if n:
                lines.append(f"  {t:<24} : {n}")
        if summ.by_subject:
            lines.append("")
            lines.append("Top subjects:")
            for sub, n in list(summ.by_subject.items())[:10]:
                lines.append(f"  {sub:<24} : {n}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")


# ══ Attachments ═══════════════════════════════════════════════════

class AttachmentPanel:
    """Reusable file list + add/remove/open controls.

    Hangs off either an assignment (brief, mark scheme, resources) or a
    submission (the work handed in). Pass exactly one id.
    """

    def __init__(self, parent: tk.Misc, *,
                 assignment_id: int | None = None,
                 submission_id: int | None = None,
                 version_id: int | None = None,
                 uploaded_by: str | None = None) -> None:
        if (assignment_id is None) == (submission_id is None):
            raise ValueError(
                "AttachmentPanel needs exactly one owner id")
        self.assignment_id = assignment_id
        self.submission_id = submission_id
        self.version_id = version_id
        self.uploaded_by = uploaded_by
        self.for_assignment = assignment_id is not None
        self.frame = ttk.Frame(parent)
        self.frame.pack(fill="both", expand=True)
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", pady=(0, 4))
        kinds = (ASSIGNMENT_ATTACHMENT_KINDS if self.for_assignment
                  else SUBMISSION_ATTACHMENT_KINDS)
        ttk.Label(bar, text="Kind:").pack(side="left")
        self.kind_cb = ttk.Combobox(bar, values=kinds,
                                       state="readonly", width=14)
        self.kind_cb.set(data.DEFAULT_ASSIGNMENT_ATTACHMENT_KIND
                          if self.for_assignment
                          else data.DEFAULT_SUBMISSION_ATTACHMENT_KIND)
        self.kind_cb.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Add files…",
                    command=self._add).pack(side="left")
        ttk.Button(bar, text="Open",
                    command=self._open).pack(side="left", padx=4)
        ttk.Button(bar, text="Save a copy…",
                    command=self._save_copy).pack(side="left")
        ttk.Button(bar, text="Remove",
                    command=self._remove).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

        cols = ("id", "kind", "filename", "size", "uploaded",
                "by", "sha")
        headings = {"id": "ID", "kind": "Kind", "filename": "File",
                    "size": "Size", "uploaded": "Uploaded",
                    "by": "By", "sha": "SHA-256"}
        widths = {"id": 45, "kind": 90, "filename": 260, "size": 80,
                  "uploaded": 140, "by": 110, "sha": 160}
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings", height=8)
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c],
                              anchor="e" if c == "size" else "w")
        vs = ttk.Scrollbar(self.frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("missing", background="#ffd0d0")
        self.tree.bind("<Double-1>", lambda _e: self._open())

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        for att in data.list_attachments(
                assignment_id=self.assignment_id,
                submission_id=self.submission_id):
            self.tree.insert(
                "", "end", iid=str(att.attachment_id),
                values=(att.attachment_id, att.kind, att.filename,
                        att.size_label, att.uploaded_at or "—",
                        att.uploaded_by or "—",
                        (att.sha256 or "")[:16]),
                tags=() if att.exists else ("missing",))

    def _selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Attachments", "Select a file first.")
            return None
        return data.get_attachment(int(sel[0]))

    def _add(self) -> None:
        picked = filedialog.askopenfilenames(
            title="Attach files",
            parent=self.frame.winfo_toplevel())
        if not picked:
            return
        failures = []
        for path in picked:
            try:
                data.attach_file(
                    source_path=path,
                    assignment_id=self.assignment_id,
                    submission_id=self.submission_id,
                    version_id=self.version_id,
                    kind=self.kind_cb.get(),
                    uploaded_by=self.uploaded_by)
            except Exception as e:
                failures.append(f"{Path(path).name}: {e}")
        if failures:
            messagebox.showerror(
                "Some files were not attached", "\n".join(failures))
        self.refresh()

    def _open(self) -> None:
        att = self._selected()
        if att is None:
            return
        if not att.exists:
            messagebox.showerror(
                "Open", f"The stored file is missing:\n{att.path}")
            return
        try:
            _open_with_os(att.path)
        except Exception as e:
            messagebox.showerror("Open failed", str(e))

    def _save_copy(self) -> None:
        att = self._selected()
        if att is None:
            return
        if not att.exists:
            messagebox.showerror(
                "Save", f"The stored file is missing:\n{att.path}")
            return
        dest = filedialog.asksaveasfilename(
            title="Save a copy", initialfile=att.filename,
            parent=self.frame.winfo_toplevel())
        if not dest:
            return
        try:
            shutil.copyfile(att.path, dest)
        except OSError as e:
            messagebox.showerror("Save failed", str(e))
            return
        messagebox.showinfo("Save", f"Copied to {dest}")

    def _remove(self) -> None:
        att = self._selected()
        if att is None:
            return
        if not messagebox.askyesno(
                "Remove",
                f"Delete {att.filename!r}?\n\n"
                "The stored file is removed from disk too."):
            return
        try:
            data.delete_attachment(att.attachment_id)
        except Exception as e:
            messagebox.showerror("Remove failed", str(e))
            return
        self.refresh()


def _open_with_os(path: Path) -> None:
    """Hand a file to the desktop's default application."""
    if sys.platform.startswith("darwin"):
        subprocess.run(["open", str(path)], check=False)
    elif os.name == "nt":
        os.startfile(str(path))    # type: ignore[attr-defined]
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


class SubmissionFilesDialog:
    """Files for one submission, split by attempt."""

    def __init__(self, parent: tk.Misc, *, submission: Submission,
                 on_save: Callable[[], None]) -> None:
        self.submission = submission
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Files — submission #{submission.submission_id} "
            f"({submission.student_id})")
        self.win.geometry("980x520")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        latest = data.latest_version(submission.submission_id)
        outer = ttk.Frame(self.win, padding=10)
        outer.pack(fill="both", expand=True)
        note = ("New files attach to the latest attempt "
                f"({latest.label})." if latest else
                "No attempt recorded yet — files attach to the "
                "submission itself.")
        ttk.Label(outer, text=note, foreground="#555").pack(
            anchor="w", pady=(0, 6))
        AttachmentPanel(outer,
                         submission_id=submission.submission_id,
                         version_id=(latest.version_id
                                      if latest else None))
        ttk.Button(outer, text="Close",
                    command=self._close).pack(anchor="e", pady=(8, 0))

    def _close(self) -> None:
        self.win.destroy()
        self.on_save()


# ══ Dialogs ═══════════════════════════════════════════════════════

class SubmitWorkDialog:
    """Record one attempt: files, word count, draft-or-final."""

    def __init__(self, parent: tk.Misc, *, submission: Submission,
                 assignment: Assignment | None,
                 on_save: Callable[[], None]) -> None:
        self.submission = submission
        self.assignment = (assignment
                            or data.get_assignment(
                                submission.assignment_id))
        self.on_save = on_save
        self._files: list[str] = []
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Submit work — #{submission.submission_id} "
            f"({submission.student_id})")
        self.win.geometry("700x560")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self.win, padding=12)
        outer.pack(fill="both", expand=True)
        names = _name_lookup()
        due = data.effective_due_date(self.submission, self.assignment)
        header = (f"{self.submission.student_id} — "
                  f"{names.get(self.submission.student_id, '?')}")
        ttk.Label(outer, text=header,
                   font=("", 11, "bold")).pack(anchor="w")
        sub_line = f"Deadline: {due or '—'}"
        if self.submission.extended_due_date:
            sub_line += ("  (extended from "
                         f"{self.assignment.due_date or '—'})"
                         if self.assignment else "  (extended)")
        if self.submission.attempt_no:
            sub_line += (f"   ·   {self.submission.attempt_no} previous "
                         f"attempt(s)")
        ttk.Label(outer, text=sub_line,
                   foreground="#555").pack(anchor="w", pady=(0, 10))

        form = ttk.Frame(outer)
        form.pack(fill="x")
        ttk.Label(form, text="Submitted on:").grid(row=0, column=0,
                                                      sticky="e", pady=4)
        self.date_e = ttk.Entry(form, width=14)
        self.date_e.insert(0, _today())
        self.date_e.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Word count:").grid(row=0, column=2,
                                                    sticky="e", pady=4)
        self.words_e = ttk.Entry(form, width=10)
        self.words_e.grid(row=0, column=3, sticky="w", padx=6)
        limit = self.assignment.word_limit if self.assignment else None
        ttk.Label(form,
                   text=(f"limit {limit}" if limit else "no limit set"),
                   foreground="#555").grid(row=0, column=4, sticky="w")

        self.draft_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            form,
            text="This is a draft — the final piece is still owed",
            variable=self.draft_var).grid(row=1, column=0, columnspan=5,
                                            sticky="w", pady=(6, 0))

        ttk.Label(form, text="Note:").grid(row=2, column=0,
                                              sticky="e", pady=4)
        self.note_e = ttk.Entry(form, width=52)
        self.note_e.grid(row=2, column=1, columnspan=4,
                           sticky="w", padx=6)

        files_box = ttk.LabelFrame(outer, text="Files", padding=8)
        files_box.pack(fill="both", expand=True, pady=10)
        row = ttk.Frame(files_box)
        row.pack(fill="x")
        ttk.Button(row, text="Add files…",
                    command=self._add_files).pack(side="left")
        ttk.Button(row, text="Remove selected",
                    command=self._remove_file).pack(side="left", padx=6)
        self.files_lb = tk.Listbox(files_box, height=8)
        self.files_lb.pack(fill="both", expand=True, pady=(6, 0))

        bar = ttk.Frame(outer)
        bar.pack(fill="x")
        ttk.Button(bar, text="Record submission",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _add_files(self) -> None:
        picked = filedialog.askopenfilenames(
            title="Files to submit", parent=self.win)
        for path in picked:
            if path not in self._files:
                self._files.append(path)
                self.files_lb.insert("end", path)

    def _remove_file(self) -> None:
        for idx in reversed(self.files_lb.curselection()):
            self.files_lb.delete(idx)
            del self._files[idx]

    def _save(self) -> None:
        raw = self.words_e.get().strip()
        word_count: int | None = None
        if raw:
            try:
                word_count = int(raw)
            except ValueError:
                messagebox.showerror(
                    "Submit", "Word count must be a whole number.")
                return
        try:
            version = data.submit_work(
                self.submission.submission_id,
                files=list(self._files),
                word_count=word_count,
                is_draft=self.draft_var.get(),
                submitted_on=self.date_e.get().strip() or None,
                note=self.note_e.get().strip() or None)
        except Exception as e:
            messagebox.showerror("Submit failed", str(e))
            return

        lines = [f"{version.label} recorded — status {version.status}.",
                 f"Receipt: {version.receipt_ref}",
                 f"Fingerprint: {version.receipt_hash}"]
        if self.assignment:
            check = data.check_word_limit(self.assignment, word_count)
            if check.applicable:
                lines.append("")
                lines.append(("⚠ " if check.breached else "")
                             + check.message)
        messagebox.showinfo("Submission recorded", "\n".join(lines))
        self.win.destroy()
        self.on_save()


class ExtensionDialog:
    """Grant or revoke one student's later deadline."""

    def __init__(self, parent: tk.Misc, *, submission: Submission,
                 assignment: Assignment | None,
                 on_save: Callable[[], None]) -> None:
        self.submission = submission
        self.assignment = (assignment
                            or data.get_assignment(
                                submission.assignment_id))
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Extension — #{submission.submission_id} "
            f"({submission.student_id})")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        original = (self.assignment.due_date
                     if self.assignment else None)
        ttk.Label(form,
                   text=f"Assignment deadline: {original or '—'}",
                   font=("", 10, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        ttk.Label(form, text="Extend to:").grid(row=1, column=0,
                                                   sticky="e", pady=4)
        self.date_e = ttk.Entry(form, width=14)
        if self.submission.extended_due_date:
            self.date_e.insert(0, self.submission.extended_due_date)
        self.date_e.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Reason:").grid(row=2, column=0,
                                                sticky="e", pady=4)
        self.reason_e = ttk.Entry(form, width=44)
        if self.submission.extension_reason:
            self.reason_e.insert(0, self.submission.extension_reason)
        self.reason_e.grid(row=2, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Authorised by:").grid(row=3, column=0,
                                                       sticky="e", pady=4)
        self.by_cb = ttk.Combobox(
            form, values=("",) + tuple(_teacher_options()), width=30)
        self.by_cb.set(self.submission.extension_by
                        or (self.assignment.teacher
                            if self.assignment else "") or "")
        self.by_cb.grid(row=3, column=1, sticky="w", padx=6)

        if self.submission.extension_on:
            ttk.Label(form,
                       text=f"Granted {self.submission.extension_on}",
                       foreground="#555").grid(row=4, column=1,
                                                 sticky="w", padx=6)

        bar = ttk.Frame(form)
        bar.grid(row=5, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Grant",
                    command=self._save).pack(side="left")
        if self.submission.extended_due_date:
            ttk.Button(bar, text="Revoke",
                        command=self._revoke).pack(side="left", padx=6)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.grant_extension(
                self.submission.submission_id,
                self.date_e.get().strip(),
                reason=self.reason_e.get().strip(),
                authorised_by=self.by_cb.get().strip() or None)
        except Exception as e:
            messagebox.showerror("Extension failed", str(e))
            return
        self.win.destroy()
        self.on_save()

    def _revoke(self) -> None:
        if not messagebox.askyesno(
                "Revoke",
                "Revoke this extension? The student goes back to the "
                "assignment's own deadline."):
            return
        try:
            data.revoke_extension(self.submission.submission_id)
        except Exception as e:
            messagebox.showerror("Revoke failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class VersionHistoryDialog:
    """Every attempt at one submission, with its files and receipt."""

    def __init__(self, parent: tk.Misc, *, submission: Submission,
                 on_save: Callable[[], None]) -> None:
        self.submission = submission
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"History — submission #{submission.submission_id} "
            f"({submission.student_id})")
        self.win.geometry("1000x600")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        self._build()
        self.refresh()

    def _build(self) -> None:
        outer = ttk.Frame(self.win, padding=10)
        outer.pack(fill="both", expand=True)
        cols = ("attempt", "kind", "status", "submitted", "words",
                "files", "receipt", "hash")
        headings = {"attempt": "#", "kind": "Kind", "status": "Status",
                    "submitted": "Submitted", "words": "Words",
                    "files": "Files", "receipt": "Receipt",
                    "hash": "Fingerprint"}
        widths = {"attempt": 45, "kind": 60, "status": 90,
                  "submitted": 160, "words": 60, "files": 50,
                  "receipt": 170, "hash": 150}
        self.tree = ttk.Treeview(outer, columns=cols, show="headings",
                                    height=10)
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>",
                        lambda _e: self._show_receipt())

        self.receipt_text = tk.Text(outer, height=14, wrap="none",
                                      font=("TkFixedFont", 9))
        self.receipt_text.pack(fill="both", expand=True, pady=(8, 0))
        self.receipt_text.configure(state="disabled")

        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=(8, 0))
        ttk.Button(bar, text="Re-issue and email receipt",
                    command=self._reissue).pack(side="left")
        ttk.Button(bar, text="Close",
                    command=self._close).pack(side="right")

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        versions = data.list_versions(self.submission.submission_id)
        for v in versions:
            files = data.list_attachments(version_id=v.version_id)
            self.tree.insert(
                "", "end", iid=str(v.version_id),
                values=(v.attempt_no,
                        "Draft" if v.is_draft else "Final",
                        v.status, v.submitted_at or v.submitted_on,
                        v.word_count if v.word_count is not None else "—",
                        len(files), v.receipt_ref or "—",
                        v.receipt_hash or "—"))
        if versions:
            self.tree.selection_set(str(versions[-1].version_id))

    def _selected_version_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _show_receipt(self) -> None:
        vid = self._selected_version_id()
        self.receipt_text.configure(state="normal")
        self.receipt_text.delete("1.0", "end")
        if vid is not None:
            try:
                self.receipt_text.insert(
                    "1.0", data.build_receipt_text(vid))
            except Exception as e:
                self.receipt_text.insert("1.0", f"(no receipt: {e})")
        self.receipt_text.configure(state="disabled")

    def _reissue(self) -> None:
        vid = self._selected_version_id()
        if vid is None:
            messagebox.showinfo("Receipt", "Select an attempt first.")
            return
        try:
            data.issue_submission_receipt(vid, email=True)
        except Exception as e:
            messagebox.showerror("Receipt failed", str(e))
            return
        messagebox.showinfo(
            "Receipt",
            "Receipt re-issued. Delivery is best-effort — check the "
            "message log if the student says it never arrived.")
        self.refresh()
        self._show_receipt()

    def _close(self) -> None:
        self.win.destroy()
        self.on_save()


class SimilarityDialog:
    """Record a plagiarism-check result against a submission."""

    def __init__(self, parent: tk.Misc, *, submission: Submission,
                 assignment: Assignment | None,
                 on_save: Callable[[], None]) -> None:
        self.submission = submission
        self.assignment = (assignment
                            or data.get_assignment(
                                submission.assignment_id))
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Similarity — #{submission.submission_id} "
            f"({submission.student_id})")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        threshold = (self.assignment.effective_similarity_threshold
                      if self.assignment
                      else data.DEFAULT_SIMILARITY_THRESHOLD)
        ttk.Label(form,
                   text=f"Review threshold for this assignment: "
                        f"{threshold:.0f}%",
                   font=("", 10, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        ttk.Label(form, text="Score %:").grid(row=1, column=0,
                                                 sticky="e", pady=4)
        self.score_e = ttk.Entry(form, width=10)
        if self.submission.similarity_score is not None:
            self.score_e.insert(0, str(self.submission.similarity_score))
        self.score_e.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Provider:").grid(row=2, column=0,
                                                  sticky="e", pady=4)
        self.provider_e = ttk.Entry(form, width=28)
        self.provider_e.insert(
            0, self.submission.similarity_provider or "Turnitin")
        self.provider_e.grid(row=2, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Report ref:").grid(row=3, column=0,
                                                    sticky="e", pady=4)
        self.report_e = ttk.Entry(form, width=44)
        if self.submission.similarity_report:
            self.report_e.insert(0, self.submission.similarity_report)
        self.report_e.grid(row=3, column=1, sticky="w", padx=6)

        ttk.Label(
            form,
            text="A score is a prompt to look at the work, not a\n"
                 "finding of misconduct.",
            foreground="#555").grid(row=4, column=0, columnspan=2,
                                      sticky="w", pady=(8, 0))

        bar = ttk.Frame(form)
        bar.grid(row=5, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Run check now",
                    command=self._run).pack(side="left", padx=6)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        raw = self.score_e.get().strip()
        try:
            score = float(raw)
        except ValueError:
            messagebox.showerror("Similarity",
                                   "Score must be a number 0–100.")
            return
        try:
            data.record_similarity(
                self.submission.submission_id, score=score,
                provider=self.provider_e.get().strip() or None,
                report_ref=self.report_e.get().strip() or None)
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()

    def _run(self) -> None:
        try:
            result = data.run_similarity_check(
                self.submission.submission_id)
        except Exception as e:
            messagebox.showerror("Check failed", str(e))
            return
        if result is None:
            messagebox.showinfo(
                "Similarity",
                "No similarity provider is configured on this "
                "installation.\n\nEnter the score by hand, or register "
                "a provider via\nassignments.register_similarity_"
                "provider().")
            return
        self.score_e.delete(0, "end")
        self.score_e.insert(0, str(result.score))
        if result.provider:
            self.provider_e.delete(0, "end")
            self.provider_e.insert(0, result.provider)


class AssignmentStatusDialog:
    def __init__(self, parent: tk.Misc, existing: Assignment,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Status — assignment #{existing.assignment_id}")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="New status:").grid(row=0, column=0,
                                                    sticky="e", pady=4)
        self.cb = ttk.Combobox(form, values=ASSIGNMENT_STATUSES,
                                  state="readonly", width=14)
        self.cb.set(existing.status)
        self.cb.grid(row=0, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=1, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.set_assignment_status(
                self.existing.assignment_id, self.cb.get())
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class SubStatusDialog:
    def __init__(self, parent: tk.Misc, *, submission: Submission,
                 on_save: Callable[[], None]) -> None:
        self.submission = submission
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Status — submission #{submission.submission_id}")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="New status:").grid(row=0, column=0,
                                                    sticky="e", pady=4)
        self.cb = ttk.Combobox(form, values=SUBMISSION_STATUSES,
                                  state="readonly", width=14)
        self.cb.set(submission.status)
        self.cb.grid(row=0, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=1, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.set_submission_status(
                self.submission.submission_id, self.cb.get())
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class AddStudentDialog:
    def __init__(self, parent: tk.Misc, *, assignment: Assignment,
                 on_save: Callable[[], None]) -> None:
        self.assignment = assignment
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Add student — assignment "
                          f"#{assignment.assignment_id}")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        opts = _student_options()
        self._ids = [s for s, _ in opts]
        ttk.Label(form, text="Student:").grid(row=0, column=0,
                                                 sticky="e", pady=4)
        self.student_cb = ttk.Combobox(
            form, values=[l for _, l in opts],
            state="readonly", width=44)
        if opts:
            self.student_cb.current(0)
        self.student_cb.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(form, text="(or)").grid(row=1, column=0, columnspan=2,
                                             pady=(8, 0))
        ttk.Label(form, text="Class group id:").grid(row=2, column=0,
                                                       sticky="e", pady=4)
        self.group_e = ttk.Entry(form, width=8)
        self.group_e.grid(row=2, column=1, sticky="w", padx=6)

        bar = ttk.Frame(form)
        bar.grid(row=3, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Add student",
                    command=self._add_student).pack(side="left")
        ttk.Button(bar, text="Add class group",
                    command=self._add_group).pack(side="left", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _add_student(self) -> None:
        idx = self.student_cb.current()
        if idx < 0:
            messagebox.showerror("Add", "Pick a student.")
            return
        try:
            data.add_student(
                self.assignment.assignment_id, self._ids[idx])
        except Exception as e:
            messagebox.showerror("Add failed", str(e))
            return
        self.win.destroy()
        self.on_save()

    def _add_group(self) -> None:
        gid_raw = self.group_e.get().strip()
        if not gid_raw:
            messagebox.showerror("Add", "Enter a class group id.")
            return
        try:
            gid = int(gid_raw)
        except ValueError:
            messagebox.showerror("Add",
                                    "Class group id must be a number.")
            return
        try:
            n = data.add_class_group(
                self.assignment.assignment_id, gid)
        except Exception as e:
            messagebox.showerror("Add failed", str(e))
            return
        messagebox.showinfo("Add", f"Added {n} new student(s)")
        self.win.destroy()
        self.on_save()


class MarkDialog:
    def __init__(self, parent: tk.Misc, *, submission: Submission,
                 assignment: Assignment | None,
                 on_save: Callable[[], None]) -> None:
        self.submission = submission
        self.assignment = assignment
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Mark — submission #{submission.submission_id}")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        names = _name_lookup()
        title = (f"Student: {self.submission.student_id} — "
                 f"{names.get(self.submission.student_id, '?')}")
        if self.assignment:
            title += f"   Max: {self.assignment.max_marks or '—'}"
        ttk.Label(form, text=title,
                   font=("", 10, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        ttk.Label(form, text="Marks:").grid(row=1, column=0,
                                               sticky="e", pady=4)
        self.marks_e = ttk.Entry(form, width=10)
        if self.submission.marks is not None:
            self.marks_e.insert(0, str(self.submission.marks))
        self.marks_e.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Grade:").grid(row=2, column=0,
                                               sticky="e", pady=4)
        self.grade_e = ttk.Entry(form, width=8)
        if self.submission.grade:
            self.grade_e.insert(0, self.submission.grade)
        self.grade_e.grid(row=2, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Marked by:").grid(row=3, column=0,
                                                   sticky="e", pady=4)
        self.by_e = ttk.Entry(form, width=30)
        default_by = (self.submission.marked_by
                       or (self.assignment.teacher
                            if self.assignment else "")
                       or "")
        if default_by:
            self.by_e.insert(0, default_by)
        self.by_e.grid(row=3, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Feedback:").grid(row=4, column=0,
                                                  sticky="ne", pady=4)
        self.feedback_t = tk.Text(form, width=44, height=6)
        if self.submission.feedback:
            self.feedback_t.insert("1.0", self.submission.feedback)
        self.feedback_t.grid(row=4, column=1, sticky="w", padx=6)

        bar = ttk.Frame(form)
        bar.grid(row=5, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save mark",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        marks_raw = self.marks_e.get().strip()
        try:
            marks = float(marks_raw) if marks_raw else None
        except ValueError:
            messagebox.showerror("Mark",
                                    "Marks must be a number.")
            return
        try:
            data.mark_submission(
                self.submission.submission_id,
                marks=marks,
                grade=self.grade_e.get().strip() or None,
                feedback=self.feedback_t.get("1.0", "end").strip()
                          or None,
                marked_by=self.by_e.get().strip() or None,
            )
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class AssignmentDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: Assignment | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Assignment" if existing
                          else "New Assignment")
        self.win.transient(parent)
        self.win.geometry("840x680")
        grab_when_viewable(self.win)
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self.win, padding=10)
        outer.pack(fill="both", expand=True)

        meta = ttk.LabelFrame(outer, text="Details", padding=8)
        meta.pack(fill="x", pady=(0, 6))
        r = 0

        ttk.Label(meta, text="Title:").grid(row=r, column=0,
                                               sticky="e", pady=3)
        self.title_e = ttk.Entry(meta, width=44)
        if self.existing:
            self.title_e.insert(0, self.existing.title)
        self.title_e.grid(row=r, column=1, columnspan=3,
                            sticky="w", padx=6)

        r += 1
        ttk.Label(meta, text="Subject:").grid(row=r, column=0,
                                                 sticky="e", pady=3)
        self.subject_cb = ttk.Combobox(
            meta, values=_subject_options(), width=26)
        if self.existing:
            self.subject_cb.set(self.existing.subject_name)
        self.subject_cb.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(meta, text="Type:").grid(row=r, column=2,
                                              sticky="e", pady=3)
        self.type_cb = ttk.Combobox(meta, values=ASSIGNMENT_TYPES,
                                       state="readonly", width=20)
        self.type_cb.set(self.existing.assignment_type
                            if self.existing
                            else DEFAULT_ASSIGNMENT_TYPE)
        self.type_cb.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(meta, text="Teacher:").grid(row=r, column=0,
                                                 sticky="e", pady=3)
        teacher_vals = _teacher_options()
        self.teacher_cb = ttk.Combobox(
            meta, values=("",) + tuple(teacher_vals), width=26)
        if self.existing and self.existing.teacher:
            self.teacher_cb.set(self.existing.teacher)
        self.teacher_cb.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(meta, text="Year:").grid(row=r, column=2,
                                              sticky="e", pady=3)
        self.year_cb = ttk.Combobox(meta, values=("",) + YEAR_GROUPS,
                                       state="readonly", width=10)
        self.year_cb.set((self.existing.year_group or "")
                            if self.existing else "")
        self.year_cb.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(meta, text="Course:").grid(row=r, column=0,
                                                sticky="e", pady=3)
        self._course_opts = _course_options()
        self._course_ids = [cid for cid, _ in self._course_opts]
        self.course_cb = ttk.Combobox(
            meta,
            values=["(none)"] + [label for _, label in self._course_opts],
            state="readonly", width=54)
        # Select current course if editing, else default to (none).
        if self.existing and self.existing.course_id is not None:
            try:
                idx = self._course_ids.index(self.existing.course_id)
                self.course_cb.current(idx + 1)
            except ValueError:
                self.course_cb.current(0)
        else:
            self.course_cb.current(0)
        self.course_cb.grid(row=r, column=1, columnspan=3,
                              sticky="w", padx=6)

        r += 1
        ttk.Label(meta, text="Set date:").grid(row=r, column=0,
                                                  sticky="e", pady=3)
        self.set_e = ttk.Entry(meta, width=14)
        if self.existing and self.existing.set_date:
            self.set_e.insert(0, self.existing.set_date)
        elif not self.existing:
            self.set_e.insert(0, _today())
        self.set_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(meta, text="Due date:").grid(row=r, column=2,
                                                  sticky="e", pady=3)
        self.due_e = ttk.Entry(meta, width=14)
        if self.existing and self.existing.due_date:
            self.due_e.insert(0, self.existing.due_date)
        self.due_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(meta, text="Max marks:").grid(row=r, column=0,
                                                   sticky="e", pady=3)
        self.max_e = ttk.Entry(meta, width=10)
        if self.existing and self.existing.max_marks is not None:
            self.max_e.insert(0, str(self.existing.max_marks))
        self.max_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(meta, text="Weight %:").grid(row=r, column=2,
                                                  sticky="e", pady=3)
        self.weight_e = ttk.Entry(meta, width=10)
        if (self.existing
                and self.existing.weight_percent is not None):
            self.weight_e.insert(0,
                                   str(self.existing.weight_percent))
        self.weight_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(meta, text="Status:").grid(row=r, column=0,
                                                sticky="e", pady=3)
        self.status_cb = ttk.Combobox(meta, values=ASSIGNMENT_STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_ASSIGNMENT_STATUS)
        self.status_cb.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(meta, text="Submission method:").grid(row=r, column=2,
                                                          sticky="e", pady=3)
        self.method_e = ttk.Entry(meta, width=24)
        if self.existing and self.existing.submission_method:
            self.method_e.insert(0, self.existing.submission_method)
        self.method_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(meta, text="Word limit:").grid(row=r, column=0,
                                                    sticky="e", pady=3)
        self.wordlimit_e = ttk.Entry(meta, width=10)
        if self.existing and self.existing.word_limit is not None:
            self.wordlimit_e.insert(0, str(self.existing.word_limit))
        self.wordlimit_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(meta, text="Flag similarity at %:").grid(
            row=r, column=2, sticky="e", pady=3)
        self.simthresh_e = ttk.Entry(meta, width=10)
        if (self.existing
                and self.existing.similarity_threshold is not None):
            self.simthresh_e.insert(
                0, str(self.existing.similarity_threshold))
        self.simthresh_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        self.resub_var = tk.BooleanVar(
            value=(self.existing.allow_resubmission
                    if self.existing else True))
        ttk.Checkbutton(
            meta,
            text="Allow resubmission after a final attempt "
                 "(drafts are always allowed)",
            variable=self.resub_var).grid(row=r, column=1, columnspan=3,
                                            sticky="w", padx=6, pady=3)

        policy = ttk.LabelFrame(outer, text="Marking policy", padding=8)
        policy.pack(fill="x", pady=(0, 6))
        ttk.Label(policy, text="Late penalty %/day:").grid(
            row=0, column=0, sticky="e", pady=3)
        self.penalty_e = ttk.Entry(policy, width=8)
        if (self.existing
                and self.existing.late_penalty_percent_per_day is not None):
            self.penalty_e.insert(
                0, str(self.existing.late_penalty_percent_per_day))
        self.penalty_e.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(policy, text="Cap %:").grid(row=0, column=2,
                                                 sticky="e", pady=3)
        self.penalty_cap_e = ttk.Entry(policy, width=8)
        if (self.existing
                and self.existing.late_penalty_cap_percent is not None):
            self.penalty_cap_e.insert(
                0, str(self.existing.late_penalty_cap_percent))
        self.penalty_cap_e.grid(row=0, column=3, sticky="w", padx=6)

        ttk.Label(policy, text="Grace days:").grid(row=0, column=4,
                                                      sticky="e", pady=3)
        self.grace_e = ttk.Entry(policy, width=8)
        self.grace_e.insert(
            0, str(self.existing.late_penalty_grace_days)
            if self.existing else "0")
        self.grace_e.grid(row=0, column=5, sticky="w", padx=6)

        ttk.Label(policy, text="Moderation tolerance:").grid(
            row=1, column=0, sticky="e", pady=3)
        self.tolerance_e = ttk.Entry(policy, width=8)
        if (self.existing
                and self.existing.moderation_tolerance is not None):
            self.tolerance_e.insert(
                0, str(self.existing.moderation_tolerance))
        self.tolerance_e.grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(policy,
                   text="marks — a bigger first/second gap needs a "
                        "moderator",
                   foreground="#555").grid(row=1, column=2, columnspan=4,
                                             sticky="w", padx=6)

        self.access_var = tk.BooleanVar(
            value=(self.existing.honour_access_arrangements
                    if self.existing else True))
        ttk.Checkbutton(
            policy,
            text="Honour exam-access arrangements "
                 "(extra time becomes extra days on the deadline)",
            variable=self.access_var).grid(row=2, column=0, columnspan=6,
                                             sticky="w", pady=(6, 0))

        # Body notebook
        body_nb = ttk.Notebook(outer)
        body_nb.pack(fill="both", expand=True, pady=6)
        self._body_widgets: dict[str, tk.Text] = {}
        for label, attr in (
                ("Brief",     "brief"),
                ("Rubric",    "rubric"),
                ("Resources", "resources"),
                ("Notes",     "notes"),
        ):
            f = ttk.Frame(body_nb)
            body_nb.add(f, text=label)
            t = tk.Text(f, wrap="word", height=8)
            t.pack(fill="both", expand=True)
            if self.existing:
                v = getattr(self.existing, attr, None)
                if v:
                    t.insert("1.0", v)
            self._body_widgets[attr] = t

        # Files tab: real attachments, as opposed to the Resources tab
        # above which is only a text description of them.
        files_frame = ttk.Frame(body_nb)
        body_nb.add(files_frame, text="Files")
        if self.existing:
            AttachmentPanel(files_frame,
                             assignment_id=self.existing.assignment_id)
        else:
            ttk.Label(
                files_frame,
                text="Save the assignment first, then reopen it to "
                     "attach the brief, mark scheme and resources.",
                foreground="#555",
                padding=20).pack(anchor="w")

        bar = ttk.Frame(outer)
        bar.pack(fill="x")
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _collect(self) -> dict:
        course_idx = self.course_cb.current()
        course_id = (self._course_ids[course_idx - 1]
                      if course_idx >= 1 else None)
        payload = {
            "title":             self.title_e.get().strip(),
            "subject_name":      self.subject_cb.get().strip(),
            "assignment_type":   self.type_cb.get().strip(),
            "teacher":           self.teacher_cb.get().strip(),
            "year_group":        self.year_cb.get().strip(),
            "course_id":         course_id,
            "set_date":          self.set_e.get().strip(),
            "due_date":          self.due_e.get().strip(),
            "max_marks":         self.max_e.get().strip() or None,
            "weight_percent":    self.weight_e.get().strip() or None,
            "status":            self.status_cb.get().strip(),
            "submission_method": self.method_e.get().strip(),
            "word_limit":        self.wordlimit_e.get().strip() or None,
            "similarity_threshold": (self.simthresh_e.get().strip()
                                      or None),
            "allow_resubmission": self.resub_var.get(),
            "late_penalty_percent_per_day": (self.penalty_e.get().strip()
                                              or None),
            "late_penalty_cap_percent": (self.penalty_cap_e.get().strip()
                                          or None),
            "late_penalty_grace_days": self.grace_e.get().strip() or 0,
            "moderation_tolerance": (self.tolerance_e.get().strip()
                                      or None),
            "honour_access_arrangements": self.access_var.get(),
        }
        for attr, t in self._body_widgets.items():
            payload[attr] = t.get("1.0", "end").strip()
        return payload

    def _save(self) -> None:
        try:
            payload = self._collect()
            if self.existing:
                data.update_assignment(
                    self.existing.assignment_id, payload)
            else:
                data.create_assignment(payload)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()
