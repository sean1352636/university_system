"""Tkinter views for Sixth Form Target Setting."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable
from education_system.platform import branding
from education_system.systems.sixth_form.domain.assessment.target_setting import (
    target_setting as data,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)
from education_system.systems.sixth_form.domain.assessment.target_setting.target_setting import (
    A_LEVEL_GRADES,
    DEFAULT_STATUS,
    PROGRESS_TAGS,
    Review,
    STATUSES,
    Target,
    ValidationError,
    YEAR_GROUPS,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_target_setting_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Target Setting — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    TargetsTab(nb)
    SeedTab(nb)
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
        from education_system.systems.sixth_form.domain.academics.subjects import (
            subjects as _subjects,
        )
        return [s.name for s in _subjects.list_subjects()]
    except Exception:
        return []


# ══ Targets tab ═══════════════════════════════════════════════════

class TargetsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Targets")
        self._selected_id: int | None = None
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

        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, values=("",) + STATUSES,
                                       state="readonly", width=14)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Year:").pack(side="left")
        self.f_year = ttk.Combobox(bar, values=("",) + YEAR_GROUPS,
                                     state="readonly", width=10)
        self.f_year.current(0)
        self.f_year.pack(side="left", padx=(2, 8))

        self.at_risk_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="At risk / Below",
                          variable=self.at_risk_var,
                          command=self.refresh).pack(side="left", padx=4)
        self.overdue_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Review overdue",
                          variable=self.overdue_var,
                          command=self.refresh).pack(side="left", padx=4)

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        ttk.Button(bar, text="New target",
                    command=self._new).pack(side="left", padx=(16, 0))

        pane = ttk.Panedwindow(self.frame, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=8, pady=4)

        # Left: list
        left = ttk.Frame(pane)
        pane.add(left, weight=3)
        cols = ("id", "student", "name", "subject",
                "mte", "asp", "cur", "delta", "status")
        self.tree = ttk.Treeview(left, columns=cols, show="headings")
        widths = {"id": 50, "student": 70, "name": 140,
                  "subject": 160, "mte": 50, "asp": 50,
                  "cur": 50, "delta": 50, "status": 110}
        headings = {"id": "ID", "student": "Stu",
                    "name": "Name", "subject": "Subject",
                    "mte": "MTE", "asp": "Asp", "cur": "Cur",
                    "delta": "Δ", "status": "Status"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = ("center" if c in
                          ("mte", "asp", "cur", "delta")
                       else "w")
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(left, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("On Track",     background="#d8f4d8")
        self.tree.tag_configure("Above Target", background="#cce8cc")
        self.tree.tag_configure("Met",          background="#cce8cc")
        self.tree.tag_configure("At Risk",      background="#fff7d0")
        self.tree.tag_configure("Below Target", background="#ffd0d0")
        self.tree.tag_configure("Not Started",  background="#eef7ff")
        self.tree.tag_configure("Withdrawn",    background="#eeeeee")
        self.tree.bind("<<TreeviewSelect>>",
                        lambda _e: self._on_select())
        self.tree.bind("<Double-1>",
                        lambda _e: self._edit_selected())

        # Right: detail + reviews
        right = ttk.Frame(pane)
        pane.add(right, weight=2)
        self.detail_var = tk.StringVar(
            value="Select a target on the left.")
        ttk.Label(right, textvariable=self.detail_var,
                   font=("", 11, "bold"),
                   anchor="w").pack(fill="x", padx=2, pady=(0, 4))
        self.subdetail_var = tk.StringVar(value="")
        ttk.Label(right, textvariable=self.subdetail_var,
                   foreground="#555",
                   anchor="w").pack(fill="x", padx=2, pady=(0, 6))

        rv_cols = ("id", "date", "current", "on_track", "reviewer")
        self.rv_tree = ttk.Treeview(right, columns=rv_cols,
                                          show="headings")
        rv_headings = {"id": "ID", "date": "Date",
                          "current": "Current",
                          "on_track": "On Track",
                          "reviewer": "Reviewer"}
        rv_widths = {"id": 50, "date": 100, "current": 70,
                       "on_track": 110, "reviewer": 130}
        for c in rv_cols:
            self.rv_tree.heading(c, text=rv_headings[c])
            self.rv_tree.column(c, width=rv_widths[c], anchor="w")
        rvs = ttk.Scrollbar(right, orient="vertical",
                              command=self.rv_tree.yview)
        self.rv_tree.configure(yscrollcommand=rvs.set)
        self.rv_tree.pack(side="left", fill="both", expand=True)
        rvs.pack(side="right", fill="y")

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(actions, text="View",
                    command=self._view_selected).pack(side="left")
        ttk.Button(actions, text="Edit",
                    command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Set current",
                    command=self._set_current).pack(side="left", padx=4)
        ttk.Button(actions, text="Status",
                    command=self._status_selected).pack(side="left",
                                                          padx=4)
        ttk.Button(actions, text="Add review",
                    command=self._add_review).pack(side="left",
                                                     padx=(12, 4))
        ttk.Button(actions, text="Delete review",
                    command=self._delete_review).pack(side="left", padx=2)
        ttk.Button(actions, text="Delete target",
                    command=self._delete_target).pack(side="left",
                                                        padx=(12, 4))
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="right")

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8, pady=(0, 8))

    def _clear(self) -> None:
        self.f_student.delete(0, "end")
        self.f_subject.set("")
        self.f_status.current(0)
        self.f_year.current(0)
        self.at_risk_var.set(False)
        self.overdue_var.set(False)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_targets(
                student_id=self.f_student.get().strip() or None,
                subject_name=self.f_subject.get().strip() or None,
                status=self.f_status.get() or None,
                year_group=self.f_year.get() or None,
                at_risk_only=self.at_risk_var.get(),
                review_overdue=self.overdue_var.get(),
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        names = _name_lookup()
        for t in rows:
            delta = t.points_vs_target
            delta_s = (f"{delta:+d}" if delta is not None else "—")
            tags = (t.status,) if t.status in STATUSES else ()
            self.tree.insert("", "end", iid=str(t.target_id), values=(
                t.target_id, t.student_id,
                names.get(t.student_id, "?"),
                t.subject_name,
                t.mte_grade, t.aspirational_grade or "—",
                t.current_grade or "—",
                delta_s, t.status,
            ), tags=tags)
        self.count_var.set(f"{len(rows)} target(s).")

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
        for i in self.rv_tree.get_children():
            self.rv_tree.delete(i)
        self.detail_var.set("Select a target on the left.")
        self.subdetail_var.set("")

    def _render_detail(self) -> None:
        for i in self.rv_tree.get_children():
            self.rv_tree.delete(i)
        if self._selected_id is None:
            return
        detail = data.get_target_detail(self._selected_id)
        if detail is None:
            self._clear_detail()
            return
        t = detail.target
        self.detail_var.set(
            f"#{t.target_id}  {t.student_id} × {t.subject_name}")
        delta = t.points_vs_target
        self.subdetail_var.set(
            f"MTE={t.mte_grade}  ·  "
            f"Asp={t.aspirational_grade or '—'}  ·  "
            f"Current={t.current_grade or '—'}  ·  "
            f"Δ={(format(delta, '+d') if delta is not None else '—')}"
            f"  ·  Status: {t.status}  ·  "
            f"Reviews: {len(detail.reviews)}  ·  "
            f"Last reviewed: {t.last_reviewed or '—'}  ·  "
            f"Next due: {t.next_review_due or '—'}")
        for r in detail.reviews:
            self.rv_tree.insert("", "end",
                                     iid=str(r.review_id), values=(
                r.review_id, r.review_date,
                r.current_grade or "—",
                r.on_track or "—",
                r.reviewer or "—",
            ))

    def _selected(self) -> Target | None:
        if self._selected_id is None:
            return None
        return data.get_target(self._selected_id)

    def _selected_review_id(self) -> int | None:
        sel = self.rv_tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _view_selected(self) -> None:
        t = self._selected()
        if t is None:
            messagebox.showinfo("View", "Select a target first.")
            return
        names = _name_lookup()
        detail = data.get_target_detail(t.target_id)
        delta = t.points_vs_target
        lines = [
            f"#{t.target_id}  {t.student_id} — "
            f"{names.get(t.student_id, '?')}",
            f"Subject         : {t.subject_name}",
            f"Year group      : {t.year_group or '—'}",
            f"MTE             : {t.mte_grade}",
            f"Aspirational    : {t.aspirational_grade or '—'}",
            f"Current         : {t.current_grade or '—'}",
            f"Vs target       : "
            f"{(format(delta, '+d') if delta is not None else '—')}",
            f"Status          : {t.status}",
            f"Baseline ref    : "
            f"{('#' + str(t.baseline_record_id)) if t.baseline_record_id else '—'}",
            f"Set on          : {t.set_on or '—'} by "
            f"{t.set_by or '—'}",
            f"Last reviewed   : {t.last_reviewed or '—'}",
            f"Next review due : {t.next_review_due or '—'}",
        ]
        if t.rationale:
            lines += ["", "Rationale:", t.rationale]
        if t.notes:
            lines += ["", "Notes:", t.notes]
        if detail and detail.reviews:
            lines.append("")
            lines.append(f"Reviews ({len(detail.reviews)}):")
            for r in detail.reviews:
                lines.append(
                    f"  #{r.review_id}  {r.review_date}  "
                    f"cur={r.current_grade or '—'}  "
                    f"on_track={r.on_track or '—'}  "
                    f"by {r.reviewer or '—'}")
                if r.comments:
                    for line in r.comments.splitlines():
                        lines.append(f"    {line}")
        messagebox.showinfo(f"Target #{t.target_id}",
                              "\n".join(lines))

    def _new(self) -> None:
        TargetDialog(self.frame.winfo_toplevel(),
                       existing=None, on_save=self.refresh)

    def _edit_selected(self) -> None:
        t = self._selected()
        if t is None:
            messagebox.showinfo("Edit", "Select a target first.")
            return
        TargetDialog(self.frame.winfo_toplevel(),
                       existing=t, on_save=self.refresh)

    def _set_current(self) -> None:
        t = self._selected()
        if t is None:
            messagebox.showinfo("Set current",
                                  "Select a target first.")
            return
        SetCurrentDialog(self.frame.winfo_toplevel(),
                            t, on_save=self.refresh)

    def _status_selected(self) -> None:
        t = self._selected()
        if t is None:
            messagebox.showinfo("Status",
                                  "Select a target first.")
            return
        StatusDialog(self.frame.winfo_toplevel(),
                       t, on_save=self.refresh)

    def _add_review(self) -> None:
        t = self._selected()
        if t is None:
            messagebox.showinfo("Review",
                                  "Select a target first.")
            return
        AddReviewDialog(self.frame.winfo_toplevel(),
                           t, on_save=self.refresh)

    def _delete_review(self) -> None:
        rid = self._selected_review_id()
        if rid is None:
            messagebox.showinfo("Delete review",
                                  "Select a review first.")
            return
        if not messagebox.askyesno("Delete review",
                                     f"Delete review #{rid}?"):
            return
        try:
            data.delete_review(rid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()

    def _delete_target(self) -> None:
        t = self._selected()
        if t is None:
            messagebox.showinfo("Delete",
                                  "Select a target first.")
            return
        if not messagebox.askyesno(
                "Delete",
                f"Delete target #{t.target_id}? "
                "Cascade-deletes reviews."):
            return
        try:
            data.delete_target(t.target_id)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self._selected_id = None
        self.refresh()


# ══ Seed tab ═════════════════════════════════════════════════════

class SeedTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Seed from Baselines")
        self._build()

    def _build(self) -> None:
        form = ttk.LabelFrame(
            self.frame,
            text="Bulk-create targets from primary baselines",
            padding=10)
        form.pack(fill="x", padx=12, pady=12)

        ttk.Label(
            form,
            text="For every Primary baseline record with a subject "
                 "and A-Level grade, a target will be created with "
                 "MTE = baseline grade and aspirational = "
                 "baseline +N grades. Existing targets are skipped.",
            foreground="#555", wraplength=820, justify="left",
        ).grid(row=0, column=0, columnspan=4, sticky="w",
                pady=(0, 8))

        opts = _student_options()
        self._ids = [s for s, _ in opts]
        ttk.Label(form, text="Student:").grid(row=1, column=0,
                                                 sticky="e", pady=4)
        self.student_cb = ttk.Combobox(
            form, values=[l for _, l in opts],
            state="readonly", width=40)
        if opts:
            self.student_cb.current(0)
        self.student_cb.grid(row=1, column=1, columnspan=3,
                                sticky="w", padx=6)

        ttk.Label(form, text="Aspirational = MTE + N:").grid(
            row=2, column=0, sticky="e", pady=4)
        self.plus_e = ttk.Entry(form, width=6)
        self.plus_e.insert(0, "1")
        self.plus_e.grid(row=2, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Set by:").grid(row=2, column=2,
                                                sticky="e", pady=4)
        self.by_e = ttk.Entry(form, width=20)
        self.by_e.grid(row=2, column=3, sticky="w", padx=6)

        ttk.Label(form, text="Year group:").grid(row=3, column=0,
                                                    sticky="e", pady=4)
        self.year_cb = ttk.Combobox(form, values=("",) + YEAR_GROUPS,
                                       state="readonly", width=12)
        self.year_cb.current(0)
        self.year_cb.grid(row=3, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Next review due:").grid(row=3, column=2,
                                                          sticky="e",
                                                          pady=4)
        self.next_e = ttk.Entry(form, width=14)
        self.next_e.grid(row=3, column=3, sticky="w", padx=6)

        bar = ttk.Frame(form)
        bar.grid(row=4, column=0, columnspan=4, pady=(12, 0))
        ttk.Button(bar, text="Seed targets",
                    command=self._seed).pack(side="left")
        self.status_var = tk.StringVar(value="")
        ttk.Label(form, textvariable=self.status_var,
                   foreground="#555",
                   wraplength=820, justify="left").grid(
            row=5, column=0, columnspan=4, sticky="w", pady=(8, 0))

    def _seed(self) -> None:
        idx = self.student_cb.current()
        if idx < 0:
            messagebox.showerror("Seed", "Pick a student.")
            return
        sid = self._ids[idx]
        try:
            plus = int(self.plus_e.get().strip() or "1")
        except ValueError:
            messagebox.showerror("Seed",
                                    "Plus-grades must be a number.")
            return
        try:
            created = data.seed_from_baseline(
                sid, plus_grades=plus,
                set_by=self.by_e.get().strip() or None,
                year_group=self.year_cb.get() or None,
                next_review_due=self.next_e.get().strip() or None,
            )
        except (ValidationError, Exception) as e:
            messagebox.showerror("Seed failed", str(e))
            return
        if not created:
            self.status_var.set(
                "No new targets — student may have no primary "
                "A-Level baselines, or targets already exist for "
                "those subjects.")
            return
        lines = [f"✓ Seeded {len(created)} target(s):"]
        for t in created:
            lines.append(f"  #{t.target_id}  {t.subject_name}  "
                          f"MTE={t.mte_grade}  "
                          f"asp={t.aspirational_grade}")
        self.status_var.set("\n".join(lines))


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
        ttk.Label(bar, text="Upcoming review window (days):").pack(
            side="left")
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
            f"Total targets         : {summ.total_targets}",
            f"Distinct students     : {summ.distinct_students}",
            f"On-track / Above / Met: {summ.on_track}",
            f"At risk               : {summ.at_risk}",
            f"Below target          : {summ.below_target}",
            f"Reviews overdue       : {summ.overdue_review}",
            f"Reviews due ({win}d)     : {summ.upcoming_review}",
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
        lines.append("")
        lines.append("By year:")
        for y in YEAR_GROUPS:
            n = summ.by_year.get(y, 0)
            if n:
                lines.append(f"  {y:<10} : {n}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")


# ══ Dialogs ═══════════════════════════════════════════════════════

class StatusDialog:
    def __init__(self, parent: tk.Misc, existing: Target,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Status — target #{existing.target_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form,
                   text="Note: Withdrawn and Met override the "
                         "auto-derived status until changed manually.",
                   foreground="#555", wraplength=320,
                   justify="left").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(form, text="New status:").grid(row=1, column=0,
                                                    sticky="e", pady=4)
        self.cb = ttk.Combobox(form, values=STATUSES,
                                  state="readonly", width=14)
        self.cb.set(existing.status)
        self.cb.grid(row=1, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=2, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.set_status(self.existing.target_id, self.cb.get())
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class SetCurrentDialog:
    def __init__(self, parent: tk.Misc, existing: Target,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Set current grade — target #{existing.target_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form,
                   text=f"MTE: {existing.mte_grade}   "
                         f"Aspirational: {existing.aspirational_grade or '—'}",
                   foreground="#555").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(form, text="Current grade:").grid(row=1, column=0,
                                                       sticky="e", pady=4)
        self.cb = ttk.Combobox(form, values=("",) + A_LEVEL_GRADES,
                                  state="readonly", width=10)
        self.cb.set(existing.current_grade or "")
        self.cb.grid(row=1, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=2, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.set_current_grade(
                self.existing.target_id,
                self.cb.get().strip() or None)
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class AddReviewDialog:
    def __init__(self, parent: tk.Misc, target: Target,
                 on_save: Callable[[], None]) -> None:
        self.target = target
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Review — target #{target.target_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)

        ttk.Label(form, text="Review date:").grid(row=0, column=0,
                                                     sticky="e", pady=4)
        self.date_e = ttk.Entry(form, width=14)
        self.date_e.insert(0, _today())
        self.date_e.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Current grade:").grid(row=1, column=0,
                                                       sticky="e", pady=4)
        self.grade_cb = ttk.Combobox(
            form, values=("",) + A_LEVEL_GRADES,
            state="readonly", width=10)
        self.grade_cb.set(self.target.current_grade or "")
        self.grade_cb.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(form, text="On track?").grid(row=2, column=0,
                                                  sticky="e", pady=4)
        self.on_track_cb = ttk.Combobox(
            form, values=("",) + PROGRESS_TAGS,
            state="readonly", width=14)
        self.on_track_cb.current(0)
        self.on_track_cb.grid(row=2, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Reviewer:").grid(row=3, column=0,
                                                  sticky="e", pady=4)
        self.reviewer_e = ttk.Entry(form, width=30)
        if self.target.set_by:
            self.reviewer_e.insert(0, self.target.set_by)
        self.reviewer_e.grid(row=3, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Comments:").grid(row=4, column=0,
                                                  sticky="ne", pady=4)
        self.comments_t = tk.Text(form, width=40, height=4)
        self.comments_t.grid(row=4, column=1, sticky="w", padx=6)

        bar = ttk.Frame(form)
        bar.grid(row=5, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save review",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.add_review(
                self.target.target_id,
                review_date=self.date_e.get().strip() or None,
                current_grade=self.grade_cb.get().strip() or None,
                on_track=self.on_track_cb.get().strip() or None,
                reviewer=self.reviewer_e.get().strip() or None,
                comments=self.comments_t.get(
                    "1.0", "end").strip() or None,
            )
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class TargetDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: Target | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Target" if existing else "New Target")
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
        ttk.Label(form, text="Subject:").grid(row=r, column=0,
                                                 sticky="e", pady=3)
        if self.existing:
            ttk.Label(form,
                       text=self.existing.subject_name).grid(
                row=r, column=1, sticky="w", padx=6)
            self.subject_cb = None
        else:
            self.subject_cb = ttk.Combobox(
                form, values=_subject_options(),
                state="readonly", width=26)
            self.subject_cb.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Year:").grid(row=r, column=2,
                                              sticky="e", pady=3)
        self.year_cb = ttk.Combobox(form, values=("",) + YEAR_GROUPS,
                                       state="readonly", width=10)
        self.year_cb.set((self.existing.year_group or "")
                            if self.existing else "")
        self.year_cb.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="MTE:").grid(row=r, column=0,
                                             sticky="e", pady=3)
        self.mte_cb = ttk.Combobox(form, values=A_LEVEL_GRADES,
                                      state="readonly", width=6)
        if self.existing:
            self.mte_cb.set(self.existing.mte_grade)
        self.mte_cb.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Aspirational:").grid(row=r, column=2,
                                                      sticky="e", pady=3)
        self.asp_cb = ttk.Combobox(
            form, values=("",) + A_LEVEL_GRADES,
            state="readonly", width=6)
        if self.existing and self.existing.aspirational_grade:
            self.asp_cb.set(self.existing.aspirational_grade)
        self.asp_cb.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Current:").grid(row=r, column=0,
                                                 sticky="e", pady=3)
        self.cur_cb = ttk.Combobox(
            form, values=("",) + A_LEVEL_GRADES,
            state="readonly", width=6)
        if self.existing and self.existing.current_grade:
            self.cur_cb.set(self.existing.current_grade)
        self.cur_cb.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Baseline id:").grid(row=r, column=2,
                                                     sticky="e", pady=3)
        self.baseline_e = ttk.Entry(form, width=8)
        if (self.existing
                and self.existing.baseline_record_id is not None):
            self.baseline_e.insert(0,
                                      str(self.existing.baseline_record_id))
        self.baseline_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Set on:").grid(row=r, column=0,
                                                sticky="e", pady=3)
        self.set_e = ttk.Entry(form, width=14)
        self.set_e.insert(0, (self.existing.set_on
                                if self.existing
                                  and self.existing.set_on
                                else _today()))
        self.set_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Set by:").grid(row=r, column=2,
                                                sticky="e", pady=3)
        self.by_e = ttk.Entry(form, width=24)
        if self.existing and self.existing.set_by:
            self.by_e.insert(0, self.existing.set_by)
        self.by_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Last reviewed:").grid(row=r, column=0,
                                                       sticky="e", pady=3)
        self.last_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.last_reviewed:
            self.last_e.insert(0, self.existing.last_reviewed)
        self.last_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Next review due:").grid(row=r, column=2,
                                                          sticky="e",
                                                          pady=3)
        self.next_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.next_review_due:
            self.next_e.insert(0, self.existing.next_review_due)
        self.next_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Status:").grid(row=r, column=0,
                                                sticky="e", pady=3)
        self.status_cb = ttk.Combobox(form, values=STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_STATUS)
        self.status_cb.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form,
                   text="(auto-derived from current grade)",
                   foreground="#888").grid(row=r, column=2,
                                              columnspan=2,
                                              sticky="w")

        r += 1
        ttk.Label(form, text="Rationale:").grid(row=r, column=0,
                                                   sticky="ne", pady=3)
        self.rationale_t = tk.Text(form, width=60, height=3)
        if self.existing and self.existing.rationale:
            self.rationale_t.insert("1.0", self.existing.rationale)
        self.rationale_t.grid(row=r, column=1, columnspan=3,
                                  sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                               sticky="ne", pady=3)
        self.notes_t = tk.Text(form, width=60, height=3)
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
            subject = self.existing.subject_name
        else:
            if self.student_cb is None:
                raise ValidationError("Pick a student")
            idx = self.student_cb.current()
            if idx < 0:
                raise ValidationError("Pick a student")
            sid = self._student_ids[idx]
            subject = (self.subject_cb.get().strip()
                        if self.subject_cb else "")
        return {
            "student_id":         sid,
            "subject_name":       subject,
            "year_group":         self.year_cb.get().strip() or None,
            "mte_grade":          self.mte_cb.get().strip(),
            "aspirational_grade": self.asp_cb.get().strip() or None,
            "current_grade":      self.cur_cb.get().strip() or None,
            "baseline_record_id": self.baseline_e.get().strip() or None,
            "set_on":             self.set_e.get().strip(),
            "set_by":             self.by_e.get().strip(),
            "last_reviewed":      self.last_e.get().strip() or None,
            "next_review_due":    self.next_e.get().strip() or None,
            "status":             self.status_cb.get().strip(),
            "rationale":          self.rationale_t.get(
                                    "1.0", "end").strip(),
            "notes":              self.notes_t.get(
                                    "1.0", "end").strip(),
        }

    def _save(self) -> None:
        try:
            payload = self._collect()
            if self.existing:
                data.update_target(self.existing.target_id, payload)
            else:
                data.create_target(payload)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()
