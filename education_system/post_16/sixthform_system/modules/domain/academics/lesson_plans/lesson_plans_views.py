"""Tkinter views for Sixth Form Lesson Plans.

Notebook with 3 tabs:

* Plans    — left = filterable list, right = full detail of the
             selected plan, with mark-delivered / duplicate / etc.
* Templates / catalogue not stored — plans are independent rows.
* Summary  — counts (drafts/ready/delivered, by subject, by teacher).
"""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable
from education_system.shared import branding
from education_system.post_16.sixthform_system.modules.domain.academics.lesson_plans import (
    lesson_plans as data,
)
from education_system.post_16.sixthform_system.modules.domain.academics.lesson_plans.lesson_plans import (
    DEFAULT_STATUS,
    LEVELS,
    LessonPlan,
    STATUSES,
    ValidationError,
    YEAR_GROUPS,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_lesson_plans_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Lesson Plans — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    PlansTab(nb)
    SummaryTab(nb)


def _today() -> str:
    return _dt.date.today().isoformat()


def _subject_options() -> list[str]:
    try:
        from education_system.post_16.sixthform_system.modules.domain.academics.subjects import (
            subjects as _subjects,
        )
        return [s.name for s in _subjects.list_subjects()]
    except Exception:
        return []


# ══ Plans tab ═════════════════════════════════════════════════════

class PlansTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Plans")
        self._selected_id: int | None = None
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))

        ttk.Label(bar, text="Subject:").pack(side="left")
        self.f_subject = ttk.Combobox(bar,
                                         values=("",) + tuple(_subject_options()),
                                         width=20)
        self.f_subject.set("")
        self.f_subject.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Teacher:").pack(side="left")
        self.f_teacher = ttk.Entry(bar, width=16)
        self.f_teacher.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, values=("",) + STATUSES,
                                       state="readonly", width=12)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Year:").pack(side="left")
        self.f_year = ttk.Combobox(bar, values=("",) + YEAR_GROUPS,
                                     state="readonly", width=10)
        self.f_year.current(0)
        self.f_year.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Title:").pack(side="left")
        self.f_title = ttk.Entry(bar, width=14)
        self.f_title.pack(side="left", padx=(2, 8))

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=(16, 0))

        pane = ttk.Panedwindow(self.frame, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=8, pady=4)

        # ── Left: list ────────────────────────────────────────────
        left = ttk.Frame(pane)
        pane.add(left, weight=2)

        cols = ("id", "date", "subject", "year", "teacher",
                "status", "title")
        self.tree = ttk.Treeview(left, columns=cols, show="headings")
        widths = {"id": 50, "date": 90, "subject": 130,
                  "year": 70, "teacher": 120,
                  "status": 90, "title": 240}
        headings = {"id": "ID", "date": "Date", "subject": "Subject",
                    "year": "Year", "teacher": "Teacher",
                    "status": "Status", "title": "Title"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(left, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Draft",     background="#eef7ff")
        self.tree.tag_configure("Ready",     background="#fff7d0")
        self.tree.tag_configure("Delivered", background="#d8f4d8")
        self.tree.tag_configure("Cancelled", background="#ffd0d0")
        self.tree.tag_configure("Archived",  background="#eeeeee")
        self.tree.bind("<<TreeviewSelect>>",
                        lambda _e: self._on_select())
        self.tree.bind("<Double-1>",
                        lambda _e: self._edit_selected())

        # ── Right: detail ─────────────────────────────────────────
        right = ttk.Frame(pane)
        pane.add(right, weight=3)
        self.detail_var = tk.StringVar(
            value="Select a plan on the left.")
        ttk.Label(right, textvariable=self.detail_var,
                   font=("", 11, "bold"),
                   anchor="w").pack(fill="x", padx=2, pady=(0, 4))
        self.subdetail_var = tk.StringVar(value="")
        ttk.Label(right, textvariable=self.subdetail_var,
                   foreground="#555",
                   anchor="w").pack(fill="x", padx=2, pady=(0, 6))

        self.detail_text = tk.Text(right, wrap="word",
                                       font=("TkDefaultFont", 10))
        self.detail_text.pack(fill="both", expand=True,
                                 padx=2, pady=(0, 6))
        self.detail_text.configure(state="disabled")

        actions = ttk.Frame(right)
        actions.pack(fill="x", padx=2, pady=(0, 0))
        ttk.Button(actions, text="Edit",
                    command=self._edit_selected).pack(side="left")
        ttk.Button(actions, text="Mark delivered",
                    command=self._mark_delivered).pack(side="left",
                                                         padx=4)
        ttk.Button(actions, text="Status",
                    command=self._status_selected).pack(side="left",
                                                          padx=4)
        ttk.Button(actions, text="Duplicate",
                    command=self._duplicate).pack(side="left", padx=4)
        ttk.Button(actions, text="Delete",
                    command=self._delete_selected).pack(side="left",
                                                          padx=4)

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8, pady=(0, 8))

    def _clear(self) -> None:
        self.f_subject.set("")
        self.f_teacher.delete(0, "end")
        self.f_status.current(0)
        self.f_year.current(0)
        self.f_title.delete(0, "end")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_plans(
                subject_name=self.f_subject.get().strip() or None,
                teacher_like=self.f_teacher.get().strip() or None,
                status=self.f_status.get() or None,
                year_group=self.f_year.get() or None,
                title_like=self.f_title.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        for p in rows:
            tags = (p.status,) if p.status in STATUSES else ()
            self.tree.insert("", "end", iid=str(p.plan_id), values=(
                p.plan_id, p.planned_date or "—",
                p.subject_name,
                p.year_group or "—",
                p.teacher or "—",
                p.status, p.title,
            ), tags=tags)
        self.count_var.set(f"{len(rows)} plan(s).")

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
        self.detail_var.set("Select a plan on the left.")
        self.subdetail_var.set("")
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.configure(state="disabled")

    def _render_detail(self) -> None:
        if self._selected_id is None:
            self._clear_detail()
            return
        p = data.get_plan(self._selected_id)
        if p is None:
            self._clear_detail()
            return
        self.detail_var.set(f"#{p.plan_id}  {p.title}")
        self.subdetail_var.set(
            f"{p.subject_name}  ·  "
            f"{p.level or '—'}  ·  {p.year_group or '—'}  ·  "
            f"Teacher: {p.teacher or '—'}  ·  "
            f"Planned: {p.planned_date or '—'}  ·  "
            f"Duration: {p.duration_minutes or '—'} min  ·  "
            f"Status: {p.status}"
            f"{'  · Delivered: ' + p.delivered_on if p.delivered_on else ''}")

        lines: list[str] = []
        if p.topic:
            lines.append(f"Topic: {p.topic}")
        if p.keywords:
            lines.append(f"Keywords: {p.keywords}")
        if (p.sequence_number is not None
                or p.week_number is not None):
            lines.append(
                f"Sequence: #{p.sequence_number or '—'}   "
                f"Week: {p.week_number or '—'}")
        if (p.course_id is not None
                or p.class_group_id is not None):
            lines.append(
                f"Course id: {p.course_id or '—'}   "
                f"Class group id: {p.class_group_id or '—'}")
        for label, val in (
                ("Objectives",       p.objectives),
                ("Success criteria", p.success_criteria),
                ("Activities",       p.activities),
                ("Resources",        p.resources),
                ("Homework",         p.homework),
                ("Assessment / AfL", p.assessment),
                ("Differentiation",  p.differentiation),
                ("Notes",            p.notes),
        ):
            if val:
                lines.append("")
                lines.append(f"── {label} ──")
                lines.append(val)
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0", "\n".join(lines))
        self.detail_text.configure(state="disabled")

    def _selected(self) -> LessonPlan | None:
        if self._selected_id is None:
            return None
        return data.get_plan(self._selected_id)

    def _new(self) -> None:
        PlanDialog(self.frame.winfo_toplevel(),
                     existing=None, on_save=self.refresh)

    def _edit_selected(self) -> None:
        p = self._selected()
        if p is None:
            messagebox.showinfo("Edit", "Select a plan first.")
            return
        PlanDialog(self.frame.winfo_toplevel(),
                     existing=p, on_save=self.refresh)

    def _mark_delivered(self) -> None:
        p = self._selected()
        if p is None:
            messagebox.showinfo("Deliver", "Select a plan first.")
            return
        if not messagebox.askyesno(
                "Mark delivered",
                f"Mark plan #{p.plan_id} ({p.title}) as Delivered?"):
            return
        try:
            data.mark_delivered(p.plan_id)
        except Exception as e:
            messagebox.showerror("Deliver", str(e))
            return
        self.refresh()

    def _status_selected(self) -> None:
        p = self._selected()
        if p is None:
            messagebox.showinfo("Status", "Select a plan first.")
            return
        StatusDialog(self.frame.winfo_toplevel(), p,
                       on_save=self.refresh)

    def _duplicate(self) -> None:
        p = self._selected()
        if p is None:
            messagebox.showinfo("Duplicate", "Select a plan first.")
            return
        DuplicateDialog(self.frame.winfo_toplevel(), p,
                          on_save=self.refresh)

    def _delete_selected(self) -> None:
        p = self._selected()
        if p is None:
            messagebox.showinfo("Delete", "Select a plan first.")
            return
        if not messagebox.askyesno(
                "Delete",
                f"Delete plan #{p.plan_id} ({p.title})?"):
            return
        try:
            data.delete_plan(p.plan_id)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self._selected_id = None
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
            f"Total plans     : {summ.total}",
            f"Drafts          : {summ.drafts}",
            f"Ready           : {summ.ready}",
            f"Delivered       : {summ.delivered}",
            f"Upcoming ({win}d)  : {summ.upcoming}",
            "",
            "By status:",
        ]
        for s in STATUSES:
            n = summ.by_status.get(s, 0)
            if n:
                lines.append(f"  {s:<14} : {n}")
        if summ.by_subject:
            lines.append("")
            lines.append("Top subjects:")
            for sub, n in list(summ.by_subject.items())[:15]:
                lines.append(f"  {sub:<22} : {n}")
        if summ.by_teacher:
            lines.append("")
            lines.append("Top teachers:")
            for t, n in list(summ.by_teacher.items())[:15]:
                lines.append(f"  {t:<22} : {n}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")


# ══ Dialogs ═══════════════════════════════════════════════════════

class StatusDialog:
    def __init__(self, parent: tk.Misc, existing: LessonPlan,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Status — plan #{existing.plan_id}")
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
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.set_status(self.existing.plan_id, self.cb.get())
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class DuplicateDialog:
    def __init__(self, parent: tk.Misc, existing: LessonPlan,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Duplicate — plan #{existing.plan_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="New title:").grid(row=0, column=0,
                                                   sticky="e", pady=4)
        self.title_e = ttk.Entry(form, width=40)
        self.title_e.insert(0, f"{existing.title} (copy)")
        self.title_e.grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(form, text="New date (optional):").grid(row=1, column=0,
                                                            sticky="e",
                                                            pady=4)
        self.date_e = ttk.Entry(form, width=14)
        self.date_e.grid(row=1, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=2, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Duplicate",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.duplicate_plan(
                self.existing.plan_id,
                new_title=self.title_e.get().strip() or None,
                new_date=self.date_e.get().strip() or None,
            )
        except Exception as e:
            messagebox.showerror("Duplicate", str(e))
            return
        self.win.destroy()
        self.on_save()


class PlanDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: LessonPlan | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Lesson Plan" if existing
                          else "New Lesson Plan")
        self.win.transient(parent)
        self.win.geometry("900x720")
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self.win, padding=10)
        outer.pack(fill="both", expand=True)

        # Top metadata grid
        meta = ttk.LabelFrame(outer, text="Details", padding=8)
        meta.pack(fill="x", pady=(0, 6))
        r = 0

        ttk.Label(meta, text="Title:").grid(row=r, column=0,
                                               sticky="e", pady=3)
        self.title_e = ttk.Entry(meta, width=46)
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
        ttk.Label(meta, text="Teacher:").grid(row=r, column=2,
                                                 sticky="e", pady=3)
        self.teacher_e = ttk.Entry(meta, width=24)
        if self.existing and self.existing.teacher:
            self.teacher_e.insert(0, self.existing.teacher)
        self.teacher_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(meta, text="Level:").grid(row=r, column=0,
                                               sticky="e", pady=3)
        self.level_cb = ttk.Combobox(meta, values=("",) + LEVELS,
                                        state="readonly", width=14)
        self.level_cb.set((self.existing.level or "")
                            if self.existing else "")
        self.level_cb.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(meta, text="Year:").grid(row=r, column=2,
                                              sticky="e", pady=3)
        self.year_cb = ttk.Combobox(meta, values=("",) + YEAR_GROUPS,
                                       state="readonly", width=10)
        self.year_cb.set((self.existing.year_group or "")
                            if self.existing else "")
        self.year_cb.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(meta, text="Planned date:").grid(row=r, column=0,
                                                      sticky="e", pady=3)
        self.date_e = ttk.Entry(meta, width=14)
        if self.existing and self.existing.planned_date:
            self.date_e.insert(0, self.existing.planned_date)
        self.date_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(meta, text="Duration (min):").grid(row=r, column=2,
                                                       sticky="e", pady=3)
        self.duration_e = ttk.Entry(meta, width=8)
        self.duration_e.insert(0,
            str(self.existing.duration_minutes)
            if self.existing and self.existing.duration_minutes
            else "60")
        self.duration_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(meta, text="Sequence #:").grid(row=r, column=0,
                                                    sticky="e", pady=3)
        self.seq_e = ttk.Entry(meta, width=8)
        if self.existing and self.existing.sequence_number is not None:
            self.seq_e.insert(0, str(self.existing.sequence_number))
        self.seq_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(meta, text="Week #:").grid(row=r, column=2,
                                                sticky="e", pady=3)
        self.week_e = ttk.Entry(meta, width=8)
        if self.existing and self.existing.week_number is not None:
            self.week_e.insert(0, str(self.existing.week_number))
        self.week_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(meta, text="Topic:").grid(row=r, column=0,
                                               sticky="e", pady=3)
        self.topic_e = ttk.Entry(meta, width=46)
        if self.existing and self.existing.topic:
            self.topic_e.insert(0, self.existing.topic)
        self.topic_e.grid(row=r, column=1, columnspan=3,
                            sticky="w", padx=6)

        r += 1
        ttk.Label(meta, text="Keywords:").grid(row=r, column=0,
                                                  sticky="e", pady=3)
        self.keywords_e = ttk.Entry(meta, width=46)
        if self.existing and self.existing.keywords:
            self.keywords_e.insert(0, self.existing.keywords)
        self.keywords_e.grid(row=r, column=1, columnspan=3,
                                sticky="w", padx=6)

        r += 1
        ttk.Label(meta, text="Status:").grid(row=r, column=0,
                                                sticky="e", pady=3)
        self.status_cb = ttk.Combobox(meta, values=STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_STATUS)
        self.status_cb.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(meta, text="Delivered on:").grid(row=r, column=2,
                                                      sticky="e", pady=3)
        self.delivered_e = ttk.Entry(meta, width=14)
        if self.existing and self.existing.delivered_on:
            self.delivered_e.insert(0, self.existing.delivered_on)
        self.delivered_e.grid(row=r, column=3, sticky="w", padx=6)

        # Body: notebook of text fields
        body_nb = ttk.Notebook(outer)
        body_nb.pack(fill="both", expand=True, pady=6)

        self._body_widgets: dict[str, tk.Text] = {}
        body_fields = [
            ("Objectives",       "objectives"),
            ("Success criteria", "success_criteria"),
            ("Activities",       "activities"),
            ("Resources",        "resources"),
            ("Homework",         "homework"),
            ("Assessment",       "assessment"),
            ("Differentiation",  "differentiation"),
            ("Notes",            "notes"),
        ]
        for label, attr in body_fields:
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
        payload = {
            "title":            self.title_e.get().strip(),
            "subject_name":     self.subject_cb.get().strip(),
            "level":            self.level_cb.get().strip(),
            "year_group":       self.year_cb.get().strip(),
            "teacher":          self.teacher_e.get().strip(),
            "planned_date":     self.date_e.get().strip(),
            "duration_minutes": self.duration_e.get().strip(),
            "sequence_number":  self.seq_e.get().strip(),
            "week_number":      self.week_e.get().strip(),
            "topic":            self.topic_e.get().strip(),
            "keywords":         self.keywords_e.get().strip(),
            "status":           self.status_cb.get().strip(),
            "delivered_on":     self.delivered_e.get().strip(),
        }
        for attr, t in self._body_widgets.items():
            payload[attr] = t.get("1.0", "end").strip()
        return payload

    def _save(self) -> None:
        try:
            payload = self._collect()
            if self.existing:
                data.update_plan(self.existing.plan_id, payload)
            else:
                data.create_plan(payload)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()
