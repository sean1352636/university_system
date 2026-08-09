"""Tkinter views for Primary School Progress Tracking."""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date
from tkinter import messagebox, ttk
from typing import Callable
from education_system.systems.primary.domain.assessment.progress import progress
from education_system.systems.primary.domain.staff import staff
from education_system.systems.primary.domain.assessment.progress import progress as data
from education_system.systems.primary.domain.staff import staff as staff_data
from education_system.systems.primary.domain import _pupils_bridge as student_data
from education_system.platform import branding
from education_system.systems.primary.domain.assessment.progress.progress import (
    DEFAULT_PERIOD,
    DEFAULT_RATING,
    DEFAULT_RISK,
    DEFAULT_REVIEW_STATUS,
    DEFAULT_TARGET_AREA,
    DEFAULT_TARGET_STATUS,
    RATINGS,
    REVIEW_PERIODS,
    REVIEW_STATUSES,
    RISK_LEVELS,
    Review,
    TARGET_AREAS,
    TARGET_STATUSES,
    Target,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_progress_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Progress Tracking — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)
    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)
    ReviewsTab(nb)
    TargetsTab(nb)
    PerStudentTab(nb)
    SummaryTab(nb)


def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}") for s in rows]


def _staff_options() -> list[tuple[str, str]]:
    rows = sorted(staff_data.list_staff(active_only=True),
                   key=lambda s: (s.last_name, s.first_name))
    return [(t.staff_id,
              f"{t.staff_id} — {t.full_name} ({t.role})")
            for t in rows]


def _student_names() -> dict[str, str]:
    return {s.student_id: s.full_name for s in student_data.list_students()}


# ══ Reviews tab ════════════════════════════════════════════════════

class ReviewsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Reviews")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Student:").pack(side="left")
        self.f_student = ttk.Entry(bar, width=12)
        self.f_student.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Period:").pack(side="left")
        self.f_period = ttk.Combobox(bar, values=("",) + REVIEW_PERIODS,
                                        state="readonly", width=24)
        self.f_period.current(0)
        self.f_period.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, values=("",) + REVIEW_STATUSES,
                                        state="readonly", width=12)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Risk:").pack(side="left")
        self.f_risk = ttk.Combobox(bar, values=("",) + RISK_LEVELS,
                                      state="readonly", width=10)
        self.f_risk.current(0)
        self.f_risk.pack(side="left", padx=(2, 10))
        self.f_active = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Active only",
                          variable=self.f_active,
                          command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(10, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "student", "name", "date", "period", "status",
                "risk", "overall", "attendance")
        widths = {"id": 50, "student": 90, "name": 180, "date": 100,
                  "period": 200, "status": 100, "risk": 80,
                  "overall": 200, "attendance": 90}
        heads = {"id": "#", "student": "Student", "name": "Name",
                 "date": "Date", "period": "Period",
                 "status": "Status", "risk": "Risk",
                 "overall": "Overall", "attendance": "Att %"}
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings")
        for c in cols:
            self.tree.heading(c, text=heads[c])
            anchor = "e" if c == "attendance" else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Critical", background="#ffd0d0")
        self.tree.tag_configure("High", background="#ffe6d0")
        self.tree.tag_configure("Archived", foreground="#888")
        self.tree.bind("<Double-1>", lambda _e: self._view_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        self.actions_holder = ttk.Frame(self.frame)
        self.actions_holder.pack(fill="x", padx=8, pady=(4, 8))
        self._build_actions()

    def _build_actions(self) -> None:
        for w in self.actions_holder.winfo_children():
            w.destroy()
        bar = ttk.Frame(self.actions_holder)
        bar.pack(fill="x")
        ttk.Button(bar, text="View",
                    command=self._view_selected).pack(side="left")
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=4)
        ttk.Button(bar, text="Edit",
                    command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Publish",
                    command=self._publish_selected).pack(
            side="left", padx=4)
        ttk.Button(bar, text="Share",
                    command=self._share_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Archive",
                    command=self._archive_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Add Target",
                    command=self._add_target).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear(self) -> None:
        self.f_student.delete(0, "end")
        self.f_period.current(0)
        self.f_status.current(0)
        self.f_risk.current(0)
        self.f_active.set(False)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_reviews(
                student_id=self.f_student.get().strip() or None,
                period=self.f_period.get() or None,
                status=self.f_status.get() or None,
                risk_level=self.f_risk.get() or None,
                active_only=self.f_active.get(),
            )
        except ValidationError as e:
            messagebox.showerror("Filter", str(e))
            return
        names = _student_names()
        for r in rows:
            tags = []
            if r.risk_level in ("Critical", "High"):
                tags.append(r.risk_level)
            if r.status == "Archived":
                tags.append("Archived")
            att = (f"{r.attendance_pct:.1f}"
                    if r.attendance_pct is not None else "—")
            self.tree.insert("", "end", iid=str(r.review_id), values=(
                r.review_id, r.student_id,
                names.get(r.student_id, "?"),
                r.review_date, r.period, r.status, r.risk_level,
                r.overall, att,
            ), tags=tuple(tags))
        self.count_var.set(f"{len(rows)} review(s).")
        self._build_actions()

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _view_selected(self) -> None:
        rid = self._selected_id()
        if rid is None:
            messagebox.showinfo("View", "Select a review first.")
            return
        ViewDialog(self.frame.winfo_toplevel(), rid)

    def _new(self) -> None:
        ReviewDialog(self.frame.winfo_toplevel(),
                       existing=None, on_save=self.refresh)

    def _edit_selected(self) -> None:
        rid = self._selected_id()
        if rid is None:
            messagebox.showinfo("Edit", "Select a review first.")
            return
        r = data.get_review(rid)
        if r is None:
            return
        if r.status == "Archived":
            messagebox.showerror(
                "Edit", "Archived reviews can't be edited.")
            return
        ReviewDialog(self.frame.winfo_toplevel(),
                       existing=r, on_save=self.refresh)

    def _publish_selected(self) -> None:
        rid = self._selected_id()
        if rid is None:
            return
        try:
            data.publish(rid)
        except ValidationError as e:
            messagebox.showerror("Publish", str(e))
            return
        self.refresh()

    def _share_selected(self) -> None:
        rid = self._selected_id()
        if rid is None:
            return
        try:
            data.share(rid)
        except ValidationError as e:
            messagebox.showerror("Share", str(e))
            return
        self.refresh()

    def _archive_selected(self) -> None:
        rid = self._selected_id()
        if rid is None:
            return
        if not messagebox.askyesno("Archive",
                                     f"Archive review #{rid}?"):
            return
        try:
            data.archive(rid)
        except ValidationError as e:
            messagebox.showerror("Archive", str(e))
            return
        self.refresh()

    def _add_target(self) -> None:
        rid = self._selected_id()
        if rid is None:
            messagebox.showinfo("Target", "Select a review first.")
            return
        TargetDialog(self.frame.winfo_toplevel(),
                       review_id=rid, existing=None,
                       on_save=self.refresh)

    def _delete_selected(self) -> None:
        rid = self._selected_id()
        if rid is None:
            return
        r = data.get_review(rid)
        if r is None:
            return
        if r.status != "Draft":
            messagebox.showerror(
                "Delete",
                f"Only Drafts can be deleted. Archive #{rid} instead.")
            return
        if not messagebox.askyesno("Delete",
                                     f"Delete draft review #{rid}?"):
            return
        try:
            data.delete_review(rid)
        except ValidationError as e:
            messagebox.showerror("Delete", str(e))
            return
        self.refresh()


class ViewDialog:
    def __init__(self, parent: tk.Misc, review_id: int) -> None:
        self.win = tk.Toplevel(parent)
        rv = data.view_review(review_id)
        if rv is None:
            self.win.destroy()
            return
        r = rv.review
        self.win.title(f"Review #{r.review_id}")
        self.win.transient(parent)
        self.win.geometry("800x700")

        head = ttk.Frame(self.win)
        head.pack(fill="x", padx=12, pady=(12, 4))
        ttk.Label(head,
                   text=f"{r.student_id} — {rv.student_name}",
                   font=("", 13, "bold")).pack(side="left")
        ttk.Label(head, text=f"[{r.status}]",
                   foreground="#888").pack(side="right")

        info = ttk.Frame(self.win)
        info.pack(fill="x", padx=12)
        rows = [
            ("Review #",   str(r.review_id)),
            ("Date",       r.review_date),
            ("Period",     r.period + (f"   ({r.academic_year})"
                                          if r.academic_year else "")),
            ("Reviewer",   rv.reviewer_name
                               or r.reviewer_staff_id or "—"),
            ("Risk",       r.risk_level),
            ("Overall",    r.overall),
            ("Attitude",   r.attitude),
            ("Homework",   r.homework),
            ("Attendance", (f"{r.attendance_pct:.1f}%"
                             if r.attendance_pct is not None else "—")),
        ]
        if r.shared_at:
            rows.append(("Shared at", r.shared_at))
        for i, (k, v) in enumerate(rows):
            ttk.Label(info, text=f"{k}:",
                       foreground="#555").grid(row=i, column=0,
                                                 sticky="e",
                                                 padx=(0, 6), pady=1)
            ttk.Label(info, text=v).grid(row=i, column=1,
                                              sticky="w")

        ttk.Separator(self.win, orient="horizontal").pack(
            fill="x", padx=12, pady=8)

        for label, val in (("Academic summary", r.academic_summary),
                            ("Behaviour summary", r.behaviour_summary),
                            ("Next steps", r.next_steps),
                            ("Notes", r.notes)):
            ttk.Label(self.win, text=f"{label}:",
                       foreground="#555").pack(anchor="w", padx=12)
            ttk.Label(self.win, text=val or "—", justify="left",
                       wraplength=750).pack(anchor="w", padx=12)
            ttk.Separator(self.win,
                            orient="horizontal").pack(fill="x",
                                                        padx=12, pady=4)

        ttk.Label(self.win,
                   text=f"Targets ({len(rv.targets)}): "
                        f"{rv.open_targets} open, "
                        f"{rv.met_targets} met",
                   font=("", 10, "bold")).pack(anchor="w",
                                                   padx=12, pady=(8, 0))
        table_frame = ttk.Frame(self.win)
        table_frame.pack(fill="both", expand=True, padx=12,
                            pady=(4, 8))
        cols = ("id", "area", "desc", "due", "status")
        widths = {"id": 50, "area": 110, "desc": 360,
                  "due": 100, "status": 100}
        tree = ttk.Treeview(table_frame, columns=cols,
                               show="headings", height=8)
        for c in cols:
            tree.heading(c, text=c.capitalize())
            tree.column(c, width=widths[c], anchor="w")
        tree.pack(fill="both", expand=True)
        for t in rv.targets:
            tree.insert("", "end", values=(
                t.target_id, t.area, t.description,
                t.due_date or "—", t.status))

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Button(bar, text="Close",
                    command=self.win.destroy).pack(side="right")


class ReviewDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: Review | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Review" if existing else "New Review")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self.prefill: dict = {}
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self.win)
        outer.pack(fill="both", expand=True, padx=12, pady=12)
        r = 0

        def label(t: str):
            nonlocal r
            ttk.Label(outer, text=t).grid(row=r, column=0,
                                             sticky="e", pady=3)

        label("Student:")
        if self.existing:
            self.student_cb = None
            self._student_id = self.existing.student_id
            names = _student_names()
            ttk.Label(outer,
                       text=f"{self._student_id} — "
                            f"{names.get(self._student_id, '?')}"
                       ).grid(row=r, column=1, sticky="w", padx=6)
        else:
            opts = _student_options()
            self._student_ids = [s for s, _ in opts]
            self.student_cb = ttk.Combobox(
                outer, values=[l for _, l in opts],
                state="readonly", width=40)
            if opts:
                self.student_cb.current(0)
            self.student_cb.grid(row=r, column=1, sticky="w", padx=6)
            ttk.Button(outer, text="Auto-fill",
                        command=self._auto_fill).grid(
                row=r, column=2, sticky="w", padx=6)
        r += 1

        label("Date:")
        self.date_e = ttk.Entry(outer, width=14)
        self.date_e.insert(0, self.existing.review_date
                                if self.existing
                                else _date.today().isoformat())
        self.date_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Period:")
        self.period_cb = ttk.Combobox(outer, values=REVIEW_PERIODS,
                                          state="readonly", width=24)
        self.period_cb.set(self.existing.period if self.existing
                              else DEFAULT_PERIOD)
        self.period_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Academic year:")
        self.year_e = ttk.Entry(outer, width=12)
        if self.existing and self.existing.academic_year:
            self.year_e.insert(0, self.existing.academic_year)
        self.year_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Reviewer:")
        opts_t = _staff_options()
        labels_t = ["(none)"] + [l for _, l in opts_t]
        ids_t = [None] + [s for s, _ in opts_t]
        self._reviewer_ids = ids_t
        self.reviewer_cb = ttk.Combobox(outer, values=labels_t,
                                            state="readonly", width=40)
        seed = (self.existing.reviewer_staff_id
                 if self.existing and self.existing.reviewer_staff_id
                 else None)
        if seed in ids_t:
            self.reviewer_cb.current(ids_t.index(seed))
        else:
            self.reviewer_cb.current(0)
        self.reviewer_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Overall:")
        self.overall_cb = ttk.Combobox(outer, values=RATINGS,
                                           state="readonly", width=26)
        self.overall_cb.set(self.existing.overall if self.existing
                               else DEFAULT_RATING)
        self.overall_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Attitude:")
        self.att_cb = ttk.Combobox(outer, values=RATINGS,
                                      state="readonly", width=26)
        self.att_cb.set(self.existing.attitude if self.existing
                          else DEFAULT_RATING)
        self.att_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Homework:")
        self.hw_cb = ttk.Combobox(outer, values=RATINGS,
                                     state="readonly", width=26)
        self.hw_cb.set(self.existing.homework if self.existing
                         else DEFAULT_RATING)
        self.hw_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Attendance %:")
        self.pct_e = ttk.Entry(outer, width=10)
        if (self.existing
                and self.existing.attendance_pct is not None):
            self.pct_e.insert(
                0, f"{self.existing.attendance_pct:.1f}")
        self.pct_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Risk:")
        self.risk_cb = ttk.Combobox(outer, values=RISK_LEVELS,
                                       state="readonly", width=14)
        self.risk_cb.set(self.existing.risk_level if self.existing
                            else DEFAULT_RISK)
        self.risk_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Status:")
        self.status_cb = ttk.Combobox(outer, values=REVIEW_STATUSES,
                                          state="readonly", width=14)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_REVIEW_STATUS)
        self.status_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Academic summary:")
        self.acad_text = tk.Text(outer, width=60, height=3,
                                    wrap="word")
        if self.existing and self.existing.academic_summary:
            self.acad_text.insert("1.0", self.existing.academic_summary)
        self.acad_text.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Behaviour summary:")
        self.beh_text = tk.Text(outer, width=60, height=3,
                                   wrap="word")
        if self.existing and self.existing.behaviour_summary:
            self.beh_text.insert("1.0", self.existing.behaviour_summary)
        self.beh_text.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Next steps:")
        self.next_text = tk.Text(outer, width=60, height=3,
                                     wrap="word")
        if self.existing and self.existing.next_steps:
            self.next_text.insert("1.0", self.existing.next_steps)
        self.next_text.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Notes:")
        self.notes_text = tk.Text(outer, width=60, height=3,
                                       wrap="word")
        if self.existing and self.existing.notes:
            self.notes_text.insert("1.0", self.existing.notes)
        self.notes_text.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        bar = ttk.Frame(outer)
        bar.grid(row=r, column=0, columnspan=3, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _auto_fill(self) -> None:
        if self.student_cb is None:
            return
        idx = self.student_cb.current()
        if idx < 0:
            return
        sid = self._student_ids[idx]
        pre = data.populate_from_data(sid)
        att = pre.get("attendance_pct")
        if att is not None:
            self.pct_e.delete(0, "end")
            self.pct_e.insert(0, f"{att:.1f}")
        if pre.get("academic_summary"):
            self.acad_text.delete("1.0", "end")
            self.acad_text.insert("1.0", pre["academic_summary"])
        if pre.get("notes"):
            self.notes_text.delete("1.0", "end")
            self.notes_text.insert("1.0", pre["notes"])

    def _save(self) -> None:
        if self.student_cb is not None:
            idx = self.student_cb.current()
            if idx < 0:
                messagebox.showerror("Validation", "Pick a student.")
                return
            sid = self._student_ids[idx]
        else:
            sid = self._student_id
        idx_r = self.reviewer_cb.current()
        reviewer = (self._reviewer_ids[idx_r]
                     if idx_r > 0 else "")
        payload = {
            "student_id":        sid,
            "review_date":       self.date_e.get().strip(),
            "period":            self.period_cb.get(),
            "academic_year":     self.year_e.get().strip(),
            "reviewer_staff_id": reviewer or "",
            "overall":           self.overall_cb.get(),
            "attitude":          self.att_cb.get(),
            "homework":          self.hw_cb.get(),
            "attendance_pct":    self.pct_e.get().strip() or None,
            "risk_level":        self.risk_cb.get(),
            "status":            self.status_cb.get(),
            "academic_summary":  self.acad_text.get("1.0",
                                                       "end").strip(),
            "behaviour_summary": self.beh_text.get("1.0",
                                                       "end").strip(),
            "next_steps":        self.next_text.get("1.0",
                                                       "end").strip(),
            "notes":             self.notes_text.get("1.0",
                                                       "end").strip(),
        }
        try:
            if self.existing:
                data.update_review(self.existing.review_id, payload)
            else:
                data.create_review(payload)
        except ValidationError as e:
            messagebox.showerror("Validation", str(e))
            return
        except Exception as e:
            logger.exception("save review failed")
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class TargetDialog:
    def __init__(self, parent: tk.Misc, *,
                 review_id: int | None,
                 existing: Target | None,
                 on_save: Callable[[], None]) -> None:
        self.review_id = review_id or (
            existing.review_id if existing else None)
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Target" if existing else "Add Target")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        r = 0
        ttk.Label(form,
                   text=f"Review #{self.review_id}",
                   foreground="#555").grid(row=r, column=0,
                                              columnspan=2,
                                              sticky="w", pady=(0, 8))
        r += 1

        ttk.Label(form, text="Area:").grid(row=r, column=0,
                                              sticky="e", pady=3)
        self.area_cb = ttk.Combobox(form, values=TARGET_AREAS,
                                        state="readonly", width=22)
        self.area_cb.set(self.existing.area if self.existing
                            else DEFAULT_TARGET_AREA)
        self.area_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Description:").grid(row=r, column=0,
                                                     sticky="ne", pady=3)
        self.desc_text = tk.Text(form, width=50, height=3, wrap="word")
        if self.existing:
            self.desc_text.insert("1.0", self.existing.description)
        self.desc_text.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Measure:").grid(row=r, column=0,
                                                 sticky="e", pady=3)
        self.measure_e = ttk.Entry(form, width=50)
        if self.existing and self.existing.measure:
            self.measure_e.insert(0, self.existing.measure)
        self.measure_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Due date:").grid(row=r, column=0,
                                                  sticky="e", pady=3)
        self.due_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.due_date:
            self.due_e.insert(0, self.existing.due_date)
        self.due_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Status:").grid(row=r, column=0,
                                                sticky="e", pady=3)
        self.status_cb = ttk.Combobox(form, values=TARGET_STATUSES,
                                          state="readonly", width=14)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_TARGET_STATUS)
        self.status_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Progress note:").grid(row=r, column=0,
                                                       sticky="ne", pady=3)
        self.note_text = tk.Text(form, width=50, height=3, wrap="word")
        if self.existing and self.existing.progress_note:
            self.note_text.insert("1.0", self.existing.progress_note)
        self.note_text.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        payload = {
            "area":          self.area_cb.get(),
            "description":   self.desc_text.get("1.0", "end").strip(),
            "measure":       self.measure_e.get().strip(),
            "due_date":      self.due_e.get().strip(),
            "status":        self.status_cb.get(),
            "progress_note": self.note_text.get("1.0", "end").strip(),
        }
        try:
            if self.existing:
                data.update_target(self.existing.target_id, payload)
            else:
                data.add_target(self.review_id, payload)
        except ValidationError as e:
            messagebox.showerror("Validation", str(e))
            return
        except Exception as e:
            logger.exception("save target failed")
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


# ══ Targets tab ════════════════════════════════════════════════════

class TargetsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Targets")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Student:").pack(side="left")
        self.f_student = ttk.Entry(bar, width=12)
        self.f_student.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Area:").pack(side="left")
        self.f_area = ttk.Combobox(bar, values=("",) + TARGET_AREAS,
                                      state="readonly", width=16)
        self.f_area.current(0)
        self.f_area.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, values=("",) + TARGET_STATUSES,
                                        state="readonly", width=12)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 10))
        self.f_open = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Open only",
                          variable=self.f_open,
                          command=self.refresh).pack(side="left")
        self.f_overdue = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Overdue only",
                          variable=self.f_overdue,
                          command=self.refresh).pack(side="left",
                                                       padx=(8, 0))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(10, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "review", "area", "due", "status",
                "desc", "note")
        widths = {"id": 50, "review": 60, "area": 110, "due": 100,
                  "status": 100, "desc": 360, "note": 240}
        heads = {"id": "#", "review": "Review", "area": "Area",
                 "due": "Due", "status": "Status",
                 "desc": "Description", "note": "Progress note"}
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings")
        for c in cols:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Met", background="#e6f7e0")
        self.tree.tag_configure("Missed", background="#ffe0e0")
        self.tree.tag_configure("overdue", background="#ffd0d0")
        self.tree.bind("<Double-1>", lambda _e: self._edit())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        self.actions_holder = ttk.Frame(self.frame)
        self.actions_holder.pack(fill="x", padx=8, pady=(4, 8))
        self._build_actions()

    def _build_actions(self) -> None:
        for w in self.actions_holder.winfo_children():
            w.destroy()
        bar = ttk.Frame(self.actions_holder)
        bar.pack(fill="x")
        ttk.Button(bar, text="Edit",
                    command=self._edit).pack(side="left")
        ttk.Button(bar, text="Status",
                    command=self._status).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear(self) -> None:
        self.f_student.delete(0, "end")
        self.f_area.current(0)
        self.f_status.current(0)
        self.f_open.set(False)
        self.f_overdue.set(False)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_targets(
                student_id=self.f_student.get().strip() or None,
                area=self.f_area.get() or None,
                status=self.f_status.get() or None,
                open_only=self.f_open.get(),
            )
        except ValidationError as e:
            messagebox.showerror("Filter", str(e))
            return
        today = _date.today().isoformat()
        if self.f_overdue.get():
            rows = [t for t in rows
                     if t.is_open and t.due_date and t.due_date < today]
        for t in rows:
            tags = []
            if t.status in ("Met", "Missed"):
                tags.append(t.status)
            if t.is_open and t.due_date and t.due_date < today:
                tags.append("overdue")
            self.tree.insert("", "end", iid=str(t.target_id), values=(
                t.target_id, t.review_id, t.area,
                t.due_date or "—", t.status, t.description,
                (t.progress_note or "").replace("\n", " ⏎ "),
            ), tags=tuple(tags))
        self.count_var.set(f"{len(rows)} target(s).")
        self._build_actions()

    def _selected(self) -> Target | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return data.get_target(int(sel[0]))

    def _edit(self) -> None:
        t = self._selected()
        if t is None:
            messagebox.showinfo("Edit", "Select a target first.")
            return
        TargetDialog(self.frame.winfo_toplevel(),
                       review_id=t.review_id, existing=t,
                       on_save=self.refresh)

    def _status(self) -> None:
        t = self._selected()
        if t is None:
            messagebox.showinfo("Status", "Select a target first.")
            return
        StatusDialog(self.frame.winfo_toplevel(),
                      title=f"Target #{t.target_id} status",
                      current=t.status,
                      options=list(TARGET_STATUSES),
                      on_save=lambda s:
                          self._save_status(t.target_id, s))

    def _save_status(self, tid: int, status: str) -> None:
        try:
            data.set_target_status(tid, status)
        except ValidationError as e:
            messagebox.showerror("Status", str(e))
            return
        self.refresh()

    def _delete(self) -> None:
        t = self._selected()
        if t is None:
            return
        if not messagebox.askyesno("Delete",
                                     f"Delete target #{t.target_id}?"):
            return
        try:
            data.delete_target(t.target_id)
        except Exception as e:
            messagebox.showerror("Delete", str(e))
            return
        self.refresh()


class StatusDialog:
    def __init__(self, parent: tk.Misc, *,
                 title: str, current: str, options: list[str],
                 on_save: Callable[[str], None]) -> None:
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(title)
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        ttk.Label(form, text="New status:").grid(row=0, column=0,
                                                    sticky="e", pady=4)
        self.cb = ttk.Combobox(form, values=options, state="readonly",
                                  width=20)
        self.cb.set(current)
        self.cb.grid(row=0, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=1, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        v = self.cb.get()
        self.win.destroy()
        self.on_save(v)


# ══ Per-Student tab ═════════════════════════════════════════════════

class PerStudentTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Per-Student")
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Student:").pack(side="left")
        opts = _student_options()
        self._sids = [s for s, _ in opts]
        self.cb = ttk.Combobox(bar, values=[l for _, l in opts],
                                  state="readonly", width=40)
        if opts:
            self.cb.current(0)
        self.cb.pack(side="left", padx=6)
        ttk.Button(bar, text="Load",
                    command=self._load).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh roster",
                    command=self._refresh_roster).pack(side="left",
                                                         padx=4)

        self.summary_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.summary_var,
                   anchor="w", font=("", 10, "bold")).pack(
            fill="x", padx=12, pady=(0, 4))

        paned = ttk.Panedwindow(self.frame, orient="vertical")
        paned.pack(fill="both", expand=True, padx=8, pady=4)

        top = ttk.LabelFrame(paned, text="Reviews")
        cols = ("id", "date", "period", "status", "risk",
                "overall", "att")
        widths = {"id": 50, "date": 100, "period": 200,
                  "status": 100, "risk": 80, "overall": 200,
                  "att": 80}
        self.review_tree = ttk.Treeview(top, columns=cols,
                                            show="headings",
                                            height=6)
        for c in cols:
            self.review_tree.heading(c, text=c.capitalize())
            self.review_tree.column(c, width=widths[c], anchor="w")
        self.review_tree.pack(fill="both", expand=True, padx=6,
                                 pady=6)
        paned.add(top, weight=2)

        bot = ttk.LabelFrame(paned, text="Targets")
        cols2 = ("id", "review", "area", "due", "status", "desc")
        widths2 = {"id": 50, "review": 60, "area": 110, "due": 100,
                   "status": 100, "desc": 400}
        self.target_tree = ttk.Treeview(bot, columns=cols2,
                                            show="headings",
                                            height=6)
        for c in cols2:
            self.target_tree.heading(c, text=c.capitalize())
            self.target_tree.column(c, width=widths2[c], anchor="w")
        self.target_tree.pack(fill="both", expand=True, padx=6,
                                 pady=6)
        self.target_tree.tag_configure("Met", background="#e6f7e0")
        self.target_tree.tag_configure("Missed", background="#ffe0e0")
        paned.add(bot, weight=2)

    def _refresh_roster(self) -> None:
        opts = _student_options()
        self._sids = [s for s, _ in opts]
        self.cb["values"] = [l for _, l in opts]
        if opts:
            self.cb.current(0)

    def _load(self) -> None:
        idx = self.cb.current()
        if idx < 0:
            return
        sid = self._sids[idx]
        student = student_data.get_student(sid)
        reviews = data.reviews_for_student(sid)
        targets = data.list_targets(student_id=sid)
        self.summary_var.set(
            f"{sid} — {student.full_name if student else '?'}    "
            f"{len(reviews)} review(s), {len(targets)} target(s)"
        )
        for i in self.review_tree.get_children():
            self.review_tree.delete(i)
        for r in reviews:
            self.review_tree.insert("", "end", values=(
                r.review_id, r.review_date, r.period,
                r.status, r.risk_level, r.overall,
                f"{r.attendance_pct:.1f}"
                    if r.attendance_pct is not None else "—",
            ))
        for i in self.target_tree.get_children():
            self.target_tree.delete(i)
        for t in targets:
            tags = (t.status,) if t.status in (
                "Met", "Missed") else ()
            self.target_tree.insert("", "end", values=(
                t.target_id, t.review_id, t.area,
                t.due_date or "—", t.status, t.description,
            ), tags=tags)


# ══ Summary tab ════════════════════════════════════════════════════

class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=8)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10), state="disabled")
        self.text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def refresh(self) -> None:
        s = data.summary()
        L: list[str] = []
        L.append("Reviews")
        L.append("-------")
        L.append(f"  Total              : {s.total_reviews}")
        L.append(f"  Drafts             : {s.drafts}")
        L.append(f"  Published          : {s.published}")
        L.append(f"  Shared             : {s.shared}")
        L.append(f"  Archived           : {s.archived}")
        L.append(f"  High/Critical risk : "
                  f"{s.students_at_high_risk}")
        L.append("")
        L.append("By period")
        L.append("---------")
        for p in REVIEW_PERIODS:
            n = s.by_period.get(p, 0)
            if n:
                L.append(f"  {p:<24} : {n}")
        L.append("")
        L.append("By risk")
        L.append("-------")
        for r in RISK_LEVELS:
            n = s.by_risk.get(r, 0)
            if n:
                L.append(f"  {r:<10} : {n}")
        L.append("")
        L.append("By overall rating")
        L.append("-----------------")
        for r in RATINGS:
            n = s.by_overall.get(r, 0)
            if n:
                L.append(f"  {r:<26} : {n}")
        L.append("")
        L.append("Targets")
        L.append("-------")
        L.append(f"  Total              : {s.total_targets}")
        L.append(f"  Open               : {s.open_targets}")
        L.append(f"  Met                : {s.met_targets}")
        L.append(f"  Missed             : {s.missed_targets}")
        L.append(f"  Overdue (open)     : "
                  f"{s.overdue_open_targets}")
        L.append("")
        L.append("By area")
        L.append("-------")
        for a in TARGET_AREAS:
            n = s.by_target_area.get(a, 0)
            if n:
                L.append(f"  {a:<18} : {n}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(L))
        self.text.configure(state="disabled")
