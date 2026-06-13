"""Tkinter views for Sixth Form Study Planner."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable
from education_system.shared import branding
from education_system.sixthform_system.modules.domain.academics.study_planner import (
    study_planner as data,
)
from education_system.sixthform_system.modules.domain.students.students import (
    students as student_data,
)
from education_system.sixthform_system.modules.domain.academics.study_planner.study_planner import (
    DEFAULT_PRIORITY,
    DEFAULT_STATUS,
    DEFAULT_TASK_TYPE,
    PRIORITIES,
    STATUSES,
    StudyTask,
    TASK_TYPES,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_study_planner_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Study Planner — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    TasksTab(nb, scope="today",   label="Today")
    TasksTab(nb, scope="open",    label="Open")
    TasksTab(nb, scope="all",     label="All")
    PlanBlockTab(nb)
    SummaryTab(nb)


def _today() -> str:
    return _dt.date.today().isoformat()


def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}")
            for s in rows]


def _name_lookup() -> dict[str, str]:
    return {s.student_id: s.full_name
             for s in student_data.list_students()}


def _subject_options() -> list[str]:
    try:
        from education_system.sixthform_system.modules.domain.academics.subjects import (
            subjects as _subjects,
        )
        return [s.name for s in _subjects.list_subjects()]
    except Exception:
        return []


# ══ Tasks tab ═════════════════════════════════════════════════════

class TasksTab:
    def __init__(self, nb: ttk.Notebook, *,
                 scope: str, label: str) -> None:
        self.scope = scope
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text=label)
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Student id:").pack(side="left")
        self.f_student = ttk.Entry(bar, width=12)
        self.f_student.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Subject:").pack(side="left")
        self.f_subject = ttk.Combobox(
            bar, values=("",) + tuple(_subject_options()), width=20)
        self.f_subject.set("")
        self.f_subject.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Type:").pack(side="left")
        self.f_type = ttk.Combobox(bar, values=("",) + TASK_TYPES,
                                     state="readonly", width=16)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Priority:").pack(side="left")
        self.f_priority = ttk.Combobox(bar,
                                         values=("",) + PRIORITIES,
                                         state="readonly", width=10)
        self.f_priority.current(0)
        self.f_priority.pack(side="left", padx=(2, 8))

        if self.scope == "all":
            ttk.Label(bar, text="From:").pack(side="left")
            self.f_from = ttk.Entry(bar, width=12)
            self.f_from.pack(side="left", padx=(2, 6))
            ttk.Label(bar, text="To:").pack(side="left")
            self.f_to = ttk.Entry(bar, width=12)
            self.f_to.pack(side="left", padx=(2, 6))
        else:
            self.f_from = None
            self.f_to = None

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "date", "time", "student", "name",
                "subject", "type", "priority",
                "status", "minutes", "title")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "date": 90, "time": 60,
                  "student": 70, "name": 130,
                  "subject": 110, "type": 110,
                  "priority": 70, "status": 100,
                  "minutes": 60, "title": 240}
        headings = {"id": "ID", "date": "Date", "time": "Time",
                    "student": "Stu", "name": "Name",
                    "subject": "Subject", "type": "Type",
                    "priority": "Pri", "status": "Status",
                    "minutes": "Mins", "title": "Title"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = "center" if c == "minutes" else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Planned",      background="#eef7ff")
        self.tree.tag_configure("In Progress",  background="#fff7d0")
        self.tree.tag_configure("Completed",    background="#d8f4d8")
        self.tree.tag_configure("Skipped",      background="#eeeeee")
        self.tree.tag_configure("Rescheduled",  background="#eef7ff")
        self.tree.tag_configure("Cancelled",    background="#eeeeee")
        self.tree.tag_configure("Overdue",      background="#ffd0d0")
        self.tree.tag_configure("Urgent",       background="#ffe0d8")
        self.tree.bind("<Double-1>",
                        lambda _e: self._edit_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(actions, text="View",
                    command=self._view_selected).pack(side="left")
        ttk.Button(actions, text="Edit",
                    command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Start",
                    command=lambda: self._quick_status(
                        "In Progress")).pack(side="left", padx=2)
        ttk.Button(actions, text="Complete",
                    command=self._complete).pack(side="left", padx=2)
        ttk.Button(actions, text="Skip",
                    command=lambda: self._quick_status(
                        "Skipped")).pack(side="left", padx=2)
        ttk.Button(actions, text="Reschedule",
                    command=self._reschedule).pack(side="left", padx=2)
        ttk.Button(actions, text="Duplicate",
                    command=self._duplicate).pack(side="left", padx=2)
        ttk.Button(actions, text="Status",
                    command=self._status_selected).pack(side="left",
                                                          padx=2)
        ttk.Button(actions, text="Delete",
                    command=self._delete_selected).pack(side="left",
                                                          padx=4)
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear(self) -> None:
        self.f_student.delete(0, "end")
        self.f_subject.set("")
        self.f_type.current(0)
        self.f_priority.current(0)
        if self.f_from is not None:
            self.f_from.delete(0, "end")
        if self.f_to is not None:
            self.f_to.delete(0, "end")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        kwargs: dict = {
            "student_id":    self.f_student.get().strip() or None,
            "subject_name":  self.f_subject.get().strip() or None,
            "task_type":     self.f_type.get() or None,
            "priority":      self.f_priority.get() or None,
        }
        if self.scope == "today":
            kwargs["today_only"] = True
        elif self.scope == "open":
            kwargs["open_only"] = True
        else:
            if self.f_from is not None:
                kwargs["date_from"] = self.f_from.get().strip() or None
            if self.f_to is not None:
                kwargs["date_to"] = self.f_to.get().strip() or None
        try:
            rows = data.list_tasks(**kwargs)
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        names = _name_lookup()
        for t in rows:
            tags: list[str] = []
            if t.status in STATUSES:
                tags.append(t.status)
            if t.is_overdue:
                tags.append("Overdue")
            if t.priority == "Urgent":
                tags.append("Urgent")
            mins = (str(t.planned_duration)
                    if t.planned_duration is not None else "—")
            self.tree.insert("", "end", iid=str(t.task_id), values=(
                t.task_id, t.planned_date or "—",
                t.time_label,
                t.student_id, names.get(t.student_id, "?"),
                t.subject_name or "—", t.task_type,
                t.priority, t.status, mins,
                t.title,
            ), tags=tuple(tags))
        self.count_var.set(f"{len(rows)} task(s).")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _selected(self) -> StudyTask | None:
        tid = self._selected_id()
        if tid is None:
            return None
        return data.get_task(tid)

    def _view_selected(self) -> None:
        t = self._selected()
        if t is None:
            messagebox.showinfo("View", "Select a task first.")
            return
        names = _name_lookup()
        lines = [
            f"#{t.task_id}  {t.title}",
            f"Student        : {t.student_id} — "
            f"{names.get(t.student_id, '?')}",
            f"Subject        : {t.subject_name or '—'}",
            f"Topic          : {t.topic or '—'}",
            f"Type           : {t.task_type}",
            f"Priority       : {t.priority}",
            f"Status         : {t.status}"
            + ("  (overdue)" if t.is_overdue else ""),
            f"Planned date   : {t.planned_date or '—'}",
            f"Start time     : {t.time_label}",
            f"Planned mins   : {t.planned_duration or '—'}",
            f"Actual mins    : {t.actual_duration or '—'}",
            f"Completed on   : {t.completed_on or '—'}",
        ]
        for label, val in (
                ("Description", t.description),
                ("Resources",   t.resources),
                ("Reflection",  t.reflection),
                ("Notes",       t.notes),
        ):
            if val:
                lines.append("")
                lines.append(f"{label}:")
                lines.append(val)
        messagebox.showinfo(f"Task #{t.task_id}",
                              "\n".join(lines))

    def _new(self) -> None:
        TaskDialog(self.frame.winfo_toplevel(),
                     existing=None, on_save=self.refresh)

    def _edit_selected(self) -> None:
        t = self._selected()
        if t is None:
            messagebox.showinfo("Edit", "Select a task first.")
            return
        TaskDialog(self.frame.winfo_toplevel(),
                     existing=t, on_save=self.refresh)

    def _status_selected(self) -> None:
        t = self._selected()
        if t is None:
            messagebox.showinfo("Status", "Select a task first.")
            return
        StatusDialog(self.frame.winfo_toplevel(),
                       t, on_save=self.refresh)

    def _complete(self) -> None:
        t = self._selected()
        if t is None:
            messagebox.showinfo("Complete",
                                  "Select a task first.")
            return
        CompleteDialog(self.frame.winfo_toplevel(),
                          t, on_save=self.refresh)

    def _reschedule(self) -> None:
        t = self._selected()
        if t is None:
            messagebox.showinfo("Reschedule",
                                  "Select a task first.")
            return
        RescheduleDialog(self.frame.winfo_toplevel(),
                            t, on_save=self.refresh)

    def _duplicate(self) -> None:
        t = self._selected()
        if t is None:
            messagebox.showinfo("Duplicate",
                                  "Select a task first.")
            return
        DuplicateDialog(self.frame.winfo_toplevel(),
                          t, on_save=self.refresh)

    def _quick_status(self, new_status: str) -> None:
        t = self._selected()
        if t is None:
            messagebox.showinfo(new_status,
                                  "Select a task first.")
            return
        if not messagebox.askyesno(
                new_status,
                f"Set #{t.task_id} → {new_status}?"):
            return
        try:
            data.set_status(t.task_id, new_status)
        except ValidationError as e:
            messagebox.showerror(new_status, str(e))
            return
        self.refresh()

    def _delete_selected(self) -> None:
        t = self._selected()
        if t is None:
            messagebox.showinfo("Delete",
                                  "Select a task first.")
            return
        if not messagebox.askyesno(
                "Delete", f"Delete task #{t.task_id}?"):
            return
        try:
            data.delete_task(t.task_id)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


# ══ Plan-block tab ════════════════════════════════════════════════

class PlanBlockTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Plan Block")
        self._build()

    def _build(self) -> None:
        form = ttk.LabelFrame(
            self.frame,
            text="Plan a revision block: one task per topic on "
                 "consecutive days",
            padding=10)
        form.pack(fill="x", padx=12, pady=12)

        opts = _student_options()
        self._ids = [s for s, _ in opts]
        ttk.Label(form, text="Student:").grid(row=0, column=0,
                                                 sticky="e", pady=4)
        self.student_cb = ttk.Combobox(
            form, values=[l for _, l in opts],
            state="readonly", width=40)
        if opts:
            self.student_cb.current(0)
        self.student_cb.grid(row=0, column=1, columnspan=3,
                                sticky="w", padx=6)

        ttk.Label(form, text="Subject:").grid(row=1, column=0,
                                                 sticky="e", pady=4)
        subj_opts = _subject_options()
        self.subject_cb = ttk.Combobox(form, values=subj_opts, width=26)
        self.subject_cb.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Type:").grid(row=1, column=2,
                                              sticky="e", pady=4)
        self.type_cb = ttk.Combobox(form, values=TASK_TYPES,
                                       state="readonly", width=18)
        self.type_cb.set(DEFAULT_TASK_TYPE)
        self.type_cb.grid(row=1, column=3, sticky="w", padx=6)

        ttk.Label(form, text="Start date:").grid(row=2, column=0,
                                                    sticky="e", pady=4)
        self.date_e = ttk.Entry(form, width=14)
        self.date_e.insert(0, _today())
        self.date_e.grid(row=2, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Minutes/topic:").grid(row=2, column=2,
                                                       sticky="e", pady=4)
        self.mins_e = ttk.Entry(form, width=8)
        self.mins_e.insert(0, "45")
        self.mins_e.grid(row=2, column=3, sticky="w", padx=6)

        ttk.Label(form, text="Priority:").grid(row=3, column=0,
                                                  sticky="e", pady=4)
        self.priority_cb = ttk.Combobox(form, values=PRIORITIES,
                                           state="readonly", width=10)
        self.priority_cb.set(DEFAULT_PRIORITY)
        self.priority_cb.grid(row=3, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Topics (one per line):").grid(
            row=4, column=0, sticky="ne", pady=4)
        self.topics_t = tk.Text(form, width=44, height=10)
        self.topics_t.grid(row=4, column=1, columnspan=3,
                              sticky="w", padx=6)

        bar = ttk.Frame(form)
        bar.grid(row=5, column=0, columnspan=4, pady=(12, 0))
        ttk.Button(bar, text="Plan block",
                    command=self._plan).pack(side="left")

        self.status_var = tk.StringVar(value="")
        ttk.Label(form, textvariable=self.status_var,
                   foreground="#555").grid(row=6, column=0,
                                             columnspan=4,
                                             sticky="w", pady=(8, 0))

    def _plan(self) -> None:
        idx = self.student_cb.current()
        if idx < 0:
            messagebox.showerror("Plan", "Pick a student.")
            return
        sid = self._ids[idx]
        subject = self.subject_cb.get().strip()
        if not subject:
            messagebox.showerror("Plan", "Pick a subject.")
            return
        topics = [t.strip() for t
                   in self.topics_t.get("1.0", "end").splitlines()
                   if t.strip()]
        if not topics:
            messagebox.showerror("Plan",
                                    "Enter at least one topic.")
            return
        try:
            mins = int(self.mins_e.get().strip() or "45")
        except ValueError:
            messagebox.showerror("Plan", "Minutes must be a number.")
            return
        try:
            created = data.plan_revision_block(
                sid, subject_name=subject, topics=topics,
                start_date=self.date_e.get().strip(),
                daily_minutes=mins,
                priority=self.priority_cb.get().strip()
                          or DEFAULT_PRIORITY,
                task_type=self.type_cb.get().strip()
                            or DEFAULT_TASK_TYPE,
            )
        except (ValidationError, Exception) as e:
            messagebox.showerror("Plan failed", str(e))
            return
        self.status_var.set(
            f"✓ Planned {len(created)} task(s) "
            f"({created[0].planned_date} → "
            f"{created[-1].planned_date})")
        self.topics_t.delete("1.0", "end")


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
        self.window_e.insert(0, "7")
        self.window_e.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left")

        self.text = tk.Text(self.frame, wrap="none", height=30,
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.text.configure(state="disabled")

    def refresh(self) -> None:
        try:
            win = int(self.window_e.get().strip() or "7")
        except ValueError:
            messagebox.showerror("Summary",
                                    "Window must be a number.")
            return
        summ = data.summary(upcoming_window_days=win)
        lines = [
            f"Total tasks       : {summ.total_tasks}",
            f"Open              : {summ.open_count}",
            f"Completed         : {summ.completed_count}",
            f"Overdue           : {summ.overdue}",
            f"Today             : {summ.today_count}",
            f"This week         : {summ.this_week_count}",
            f"Upcoming ({win}d)    : {summ.upcoming}",
            f"Minutes planned   : {summ.minutes_planned}",
            f"Minutes actual    : {summ.minutes_actual}",
            f"Distinct students : {summ.distinct_students}",
            "",
            "By status:",
        ]
        for s in STATUSES:
            n = summ.by_status.get(s, 0)
            if n:
                lines.append(f"  {s:<14} : {n}")
        lines.append("")
        lines.append("By type:")
        for t in TASK_TYPES:
            n = summ.by_type.get(t, 0)
            if n:
                lines.append(f"  {t:<22} : {n}")
        lines.append("")
        lines.append("By priority:")
        for p in PRIORITIES:
            n = summ.by_priority.get(p, 0)
            if n:
                lines.append(f"  {p:<8} : {n}")
        if summ.by_subject:
            lines.append("")
            lines.append("Top subjects:")
            for sub, n in list(summ.by_subject.items())[:10]:
                lines.append(f"  {sub:<22} : {n}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")


# ══ Dialogs ═══════════════════════════════════════════════════════

class StatusDialog:
    def __init__(self, parent: tk.Misc, existing: StudyTask,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Status — task #{existing.task_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="New status:").grid(row=0, column=0,
                                                    sticky="e", pady=4)
        self.cb = ttk.Combobox(form, values=STATUSES,
                                  state="readonly", width=14)
        self.cb.set(existing.status)
        self.cb.grid(row=0, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=1, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.set_status(self.existing.task_id, self.cb.get())
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class CompleteDialog:
    def __init__(self, parent: tk.Misc, existing: StudyTask,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Complete — task #{existing.task_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="Actual duration (mins):").grid(
            row=0, column=0, sticky="e", pady=4)
        self.actual_e = ttk.Entry(form, width=10)
        if existing.planned_duration is not None:
            self.actual_e.insert(0, str(existing.planned_duration))
        self.actual_e.grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Reflection:").grid(row=1, column=0,
                                                    sticky="ne", pady=4)
        self.reflection_t = tk.Text(form, width=44, height=4)
        if existing.reflection:
            self.reflection_t.insert("1.0", existing.reflection)
        self.reflection_t.grid(row=1, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=2, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Complete",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        v = self.actual_e.get().strip()
        try:
            actual = int(v) if v else None
        except ValueError:
            messagebox.showerror("Complete",
                                    "Duration must be a number.")
            return
        try:
            data.complete_task(
                self.existing.task_id,
                actual_duration=actual,
                reflection=self.reflection_t.get(
                    "1.0", "end").strip() or None,
            )
        except (ValidationError, Exception) as e:
            messagebox.showerror("Complete", str(e))
            return
        self.win.destroy()
        self.on_save()


class RescheduleDialog:
    def __init__(self, parent: tk.Misc, existing: StudyTask,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Reschedule — task #{existing.task_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="New date:").grid(row=0, column=0,
                                                  sticky="e", pady=4)
        self.date_e = ttk.Entry(form, width=14)
        self.date_e.grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(form, text="New start time:").grid(row=1, column=0,
                                                       sticky="e", pady=4)
        self.time_e = ttk.Entry(form, width=10)
        if existing.planned_start:
            self.time_e.insert(0, existing.planned_start[:5])
        self.time_e.grid(row=1, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=2, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Reschedule",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        new_date = self.date_e.get().strip()
        if not new_date:
            messagebox.showerror("Reschedule",
                                    "Enter a new date.")
            return
        try:
            data.reschedule(
                self.existing.task_id,
                new_date=new_date,
                new_start=self.time_e.get().strip() or None,
            )
        except (ValidationError, Exception) as e:
            messagebox.showerror("Reschedule", str(e))
            return
        self.win.destroy()
        self.on_save()


class DuplicateDialog:
    def __init__(self, parent: tk.Misc, existing: StudyTask,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Duplicate — task #{existing.task_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="New planned date:").grid(
            row=0, column=0, sticky="e", pady=4)
        self.date_e = ttk.Entry(form, width=14)
        self.date_e.grid(row=0, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=1, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Duplicate",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.duplicate_task(
                self.existing.task_id,
                new_date=self.date_e.get().strip() or None)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Duplicate", str(e))
            return
        self.win.destroy()
        self.on_save()


class TaskDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: StudyTask | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Study Task" if existing
                          else "New Study Task")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        r = 0

        ttk.Label(form, text="Student:").grid(row=r, column=0,
                                                 sticky="e", pady=3)
        if self.existing:
            self._student_id = self.existing.student_id
            self.student_cb = None
            names = _name_lookup()
            ttk.Label(form,
                       text=f"{self._student_id} — "
                             f"{names.get(self._student_id, '?')}"
                       ).grid(row=r, column=1, columnspan=3,
                               sticky="w", padx=6)
        else:
            opts = _student_options()
            self._student_ids = [s for s, _ in opts]
            self.student_cb = ttk.Combobox(
                form, values=[l for _, l in opts],
                state="readonly", width=44)
            if opts:
                self.student_cb.current(0)
            self.student_cb.grid(row=r, column=1, columnspan=3,
                                    sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Title:").grid(row=r, column=0,
                                               sticky="e", pady=3)
        self.title_e = ttk.Entry(form, width=44)
        if self.existing:
            self.title_e.insert(0, self.existing.title)
        self.title_e.grid(row=r, column=1, columnspan=3,
                            sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Subject:").grid(row=r, column=0,
                                                 sticky="e", pady=3)
        self.subject_cb = ttk.Combobox(
            form, values=_subject_options(), width=22)
        if self.existing:
            self.subject_cb.set(self.existing.subject_name or "")
        self.subject_cb.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Topic:").grid(row=r, column=2,
                                               sticky="e", pady=3)
        self.topic_e = ttk.Entry(form, width=24)
        if self.existing and self.existing.topic:
            self.topic_e.insert(0, self.existing.topic)
        self.topic_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Type:").grid(row=r, column=0,
                                              sticky="e", pady=3)
        self.type_cb = ttk.Combobox(form, values=TASK_TYPES,
                                       state="readonly", width=20)
        self.type_cb.set(self.existing.task_type
                            if self.existing else DEFAULT_TASK_TYPE)
        self.type_cb.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Priority:").grid(row=r, column=2,
                                                  sticky="e", pady=3)
        self.priority_cb = ttk.Combobox(form, values=PRIORITIES,
                                           state="readonly", width=10)
        self.priority_cb.set(self.existing.priority
                                if self.existing else DEFAULT_PRIORITY)
        self.priority_cb.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Planned date:").grid(row=r, column=0,
                                                      sticky="e", pady=3)
        self.date_e = ttk.Entry(form, width=14)
        self.date_e.insert(0, (self.existing.planned_date
                                  if self.existing
                                  else _today()))
        self.date_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Start time:").grid(row=r, column=2,
                                                    sticky="e", pady=3)
        self.start_e = ttk.Entry(form, width=10)
        if self.existing and self.existing.planned_start:
            self.start_e.insert(0, self.existing.planned_start[:5])
        self.start_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Planned mins:").grid(row=r, column=0,
                                                      sticky="e", pady=3)
        self.planned_e = ttk.Entry(form, width=8)
        self.planned_e.insert(0, (str(self.existing.planned_duration)
                                     if self.existing
                                       and self.existing.planned_duration
                                       is not None
                                     else "60"))
        self.planned_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Actual mins:").grid(row=r, column=2,
                                                     sticky="e", pady=3)
        self.actual_e = ttk.Entry(form, width=8)
        if (self.existing
                and self.existing.actual_duration is not None):
            self.actual_e.insert(0,
                                   str(self.existing.actual_duration))
        self.actual_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Status:").grid(row=r, column=0,
                                                sticky="e", pady=3)
        self.status_cb = ttk.Combobox(form, values=STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_STATUS)
        self.status_cb.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Completed on:").grid(row=r, column=2,
                                                      sticky="e", pady=3)
        self.completed_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.completed_on:
            self.completed_e.insert(0, self.existing.completed_on)
        self.completed_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Description:").grid(row=r, column=0,
                                                     sticky="ne", pady=3)
        self.desc_t = tk.Text(form, width=60, height=3)
        if self.existing and self.existing.description:
            self.desc_t.insert("1.0", self.existing.description)
        self.desc_t.grid(row=r, column=1, columnspan=3,
                            sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Resources:").grid(row=r, column=0,
                                                   sticky="ne", pady=3)
        self.resources_t = tk.Text(form, width=60, height=3)
        if self.existing and self.existing.resources:
            self.resources_t.insert("1.0", self.existing.resources)
        self.resources_t.grid(row=r, column=1, columnspan=3,
                                  sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Reflection:").grid(row=r, column=0,
                                                    sticky="ne", pady=3)
        self.reflection_t = tk.Text(form, width=60, height=3)
        if self.existing and self.existing.reflection:
            self.reflection_t.insert("1.0", self.existing.reflection)
        self.reflection_t.grid(row=r, column=1, columnspan=3,
                                  sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                               sticky="ne", pady=3)
        self.notes_t = tk.Text(form, width=60, height=2)
        if self.existing and self.existing.notes:
            self.notes_t.insert("1.0", self.existing.notes)
        self.notes_t.grid(row=r, column=1, columnspan=3,
                            sticky="w", padx=6)

        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=4, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _collect(self) -> dict:
        if self.existing:
            sid = self._student_id
        elif self.student_cb is not None:
            idx = self.student_cb.current()
            if idx < 0:
                raise ValidationError("Pick a student")
            sid = self._student_ids[idx]
        else:
            raise ValidationError("Pick a student")
        return {
            "student_id":       sid,
            "title":            self.title_e.get().strip(),
            "subject_name":     self.subject_cb.get().strip() or None,
            "topic":            self.topic_e.get().strip(),
            "task_type":        self.type_cb.get().strip(),
            "priority":         self.priority_cb.get().strip(),
            "planned_date":     self.date_e.get().strip(),
            "planned_start":    self.start_e.get().strip() or None,
            "planned_duration": self.planned_e.get().strip() or None,
            "actual_duration":  self.actual_e.get().strip() or None,
            "status":           self.status_cb.get().strip(),
            "completed_on":     self.completed_e.get().strip() or None,
            "description":      self.desc_t.get("1.0", "end").strip(),
            "resources":        self.resources_t.get(
                                    "1.0", "end").strip(),
            "reflection":       self.reflection_t.get(
                                    "1.0", "end").strip(),
            "notes":            self.notes_t.get("1.0", "end").strip(),
        }

    def _save(self) -> None:
        try:
            payload = self._collect()
            if self.existing:
                data.update_task(self.existing.task_id, payload)
            else:
                data.create_task(payload)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()
