"""Tkinter views for Sixth Form Assignments.

Notebook with 3 tabs:

* Assignments — left = filterable list, right = full detail + submissions
                table with submit / mark / status actions.
* Submissions — flat list of every submission, filterable by status /
                marked / unmarked.
* Summary     — counts and alerts.
"""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
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
    ASSIGNMENT_STATUSES,
    ASSIGNMENT_TYPES,
    Assignment,
    DEFAULT_ASSIGNMENT_STATUS,
    DEFAULT_ASSIGNMENT_TYPE,
    DEFAULT_SUBMISSION_STATUS,
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

        sub_cols = ("id", "student", "name", "status",
                     "marks", "grade", "marked_on")
        self.subs_tree = ttk.Treeview(right, columns=sub_cols,
                                          show="headings")
        sub_headings = {"id": "ID", "student": "Student",
                          "name": "Name", "status": "Status",
                          "marks": "Marks", "grade": "Grade",
                          "marked_on": "Marked on"}
        sub_widths = {"id": 50, "student": 80, "name": 200,
                       "status": 100, "marks": 80, "grade": 60,
                       "marked_on": 100}
        for c in sub_cols:
            self.subs_tree.heading(c, text=sub_headings[c])
            anchor = "e" if c == "marks" else "w"
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
        ttk.Button(actions, text="Add student",
                    command=self._add_student).pack(side="left",
                                                      padx=(16, 4))
        ttk.Button(actions, text="Submit",
                    command=self._submit_sub).pack(side="left", padx=2)
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
        self.detail_var.set(f"#{a.assignment_id}  {a.title}")
        self.subdetail_var.set(
            f"{a.subject_name}  ·  {a.assignment_type}  ·  "
            f"Teacher: {a.teacher or '—'}  ·  "
            f"Due: {a.due_date or '—'}  ·  "
            f"Max: {a.max_marks or '—'}  ·  "
            f"Status: {a.status}  ·  "
            f"Submitted: {detail.submitted_count}/"
            f"{detail.total_submissions} "
            f"({detail.percent_submitted}%)  ·  "
            f"Avg: {detail.average_mark or '—'}")
        names = _name_lookup()
        for s in detail.submissions:
            marks = (f"{s.marks}" if s.marks is not None else "—")
            tags = (s.status,) if s.status in SUBMISSION_STATUSES else ()
            self.subs_tree.insert("", "end",
                                      iid=str(s.submission_id), values=(
                s.submission_id, s.student_id,
                names.get(s.student_id, "?"),
                s.status, marks, s.grade or "—",
                s.marked_on or "—",
            ), tags=tags)

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

    def _submit_sub(self) -> None:
        sid = self._selected_sub_id()
        if sid is None:
            messagebox.showinfo("Submit",
                                  "Select a submission first.")
            return
        sub = data.get_submission(sid)
        if sub is None:
            return
        late = messagebox.askyesno("Late?",
                                      "Mark as Late?")
        try:
            data.submit(sid, late=late)
        except ValidationError as e:
            messagebox.showerror("Submit", str(e))
            return
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
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "assignment", "student", "name",
                "status", "marks", "grade", "marked_on")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "assignment": 80, "student": 80,
                  "name": 180, "status": 100, "marks": 70,
                  "grade": 60, "marked_on": 100}
        headings = {"id": "ID", "assignment": "Assignment",
                    "student": "Student", "name": "Name",
                    "status": "Status", "marks": "Marks",
                    "grade": "Grade", "marked_on": "Marked on"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = "e" if c == "marks" else "w"
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
        for r in rows:
            s = r.submission
            marks = f"{s.marks}" if s.marks is not None else "—"
            tags = (s.status,) if s.status in SUBMISSION_STATUSES else ()
            self.tree.insert("", "end", iid=str(s.submission_id), values=(
                s.submission_id, s.assignment_id,
                s.student_id, r.student_name,
                s.status, marks, s.grade or "—",
                s.marked_on or "—",
            ), tags=tags)
        self.count_var.set(f"{len(rows)} submission(s).")


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


# ══ Dialogs ═══════════════════════════════════════════════════════

class AssignmentStatusDialog:
    def __init__(self, parent: tk.Misc, existing: Assignment,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Status — assignment #{existing.assignment_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
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
        self.win.after_idle(self.win.grab_set)
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
        self.win.after_idle(self.win.grab_set)
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
        self.win.after_idle(self.win.grab_set)
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
        self.win.after_idle(self.win.grab_set)
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
