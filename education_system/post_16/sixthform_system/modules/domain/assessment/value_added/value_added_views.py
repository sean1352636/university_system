"""Tkinter views for Sixth Form Value Added."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable
from education_system.shared import branding
from education_system.post_16.sixthform_system.modules.domain.assessment.value_added import (
    value_added as data,
)
from education_system.post_16.sixthform_system.modules.domain.students.students import (
    students as student_data,
)
from education_system.post_16.sixthform_system.modules.domain.assessment.value_added.value_added import (
    A_LEVEL_GRADES,
    DEFAULT_STATUS,
    STATUSES,
    VARecord,
    ValidationError,
    YEAR_GROUPS,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_value_added_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Value Added — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    RecordsTab(nb)
    SummaryTab(nb)


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
        from education_system.post_16.sixthform_system.modules.domain.academics.subjects import (
            subjects as _subjects,
        )
        return [s.name for s in _subjects.list_subjects()]
    except Exception:
        return []


# ══ Records tab ═══════════════════════════════════════════════════

class RecordsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Records")
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

        ttk.Label(bar, text="Session:").pack(side="left")
        self.f_session = ttk.Entry(bar, width=14)
        self.f_session.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, values=("",) + STATUSES,
                                       state="readonly", width=14)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 8))

        self.pos_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Positive VA only",
                          variable=self.pos_var,
                          command=self.refresh).pack(side="left", padx=4)
        self.neg_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Negative VA only",
                          variable=self.neg_var,
                          command=self.refresh).pack(side="left", padx=4)

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "student", "name", "subject", "session",
                "exp", "tgt", "pred", "act", "va", "alps",
                "status")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "student": 80, "name": 140,
                  "subject": 140, "session": 100,
                  "exp": 40, "tgt": 40, "pred": 40,
                  "act": 40, "va": 60, "alps": 50,
                  "status": 100}
        headings = {"id": "ID", "student": "Stu", "name": "Name",
                    "subject": "Subject", "session": "Session",
                    "exp": "Exp", "tgt": "Tgt", "pred": "Pred",
                    "act": "Act", "va": "VA", "alps": "ALPS",
                    "status": "Status"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = ("center" if c in
                          ("exp", "tgt", "pred", "act",
                           "va", "alps")
                       else "w")
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("positive", background="#d8f4d8")
        self.tree.tag_configure("strongpos", background="#cce8cc")
        self.tree.tag_configure("negative", background="#fff7d0")
        self.tree.tag_configure("strongneg", background="#ffd0d0")
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
        ttk.Button(actions, text="Set actual",
                    command=self._set_actual).pack(side="left", padx=4)
        ttk.Button(actions, text="Set predicted",
                    command=self._set_predicted).pack(side="left", padx=4)
        ttk.Button(actions, text="Status",
                    command=self._status_selected).pack(side="left",
                                                          padx=4)
        ttk.Button(actions, text="Delete",
                    command=self._delete_selected).pack(side="left",
                                                          padx=4)
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear(self) -> None:
        self.f_student.delete(0, "end")
        self.f_subject.set("")
        self.f_session.delete(0, "end")
        self.f_status.current(0)
        self.pos_var.set(False)
        self.neg_var.set(False)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_records(
                student_id=self.f_student.get().strip() or None,
                subject_name=self.f_subject.get().strip() or None,
                exam_session=self.f_session.get().strip() or None,
                status=self.f_status.get() or None,
                positive_only=self.pos_var.get(),
                negative_only=self.neg_var.get(),
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        names = _name_lookup()
        for r in rows:
            tag = ""
            if r.va_score is not None:
                if r.va_score >= 2:
                    tag = "strongpos"
                elif r.va_score > 0:
                    tag = "positive"
                elif r.va_score <= -2:
                    tag = "strongneg"
                elif r.va_score < 0:
                    tag = "negative"
            self.tree.insert("", "end", iid=str(r.record_id), values=(
                r.record_id, r.student_id,
                names.get(r.student_id, "?"),
                r.subject_name, r.exam_session,
                r.expected_grade or "—",
                r.target_grade or "—",
                r.predicted_grade or "—",
                r.actual_grade or "—",
                r.va_label,
                r.alps_indicator if r.alps_indicator is not None else "—",
                r.status,
            ), tags=(tag,) if tag else ())
        self.count_var.set(f"{len(rows)} record(s).")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _selected(self) -> VARecord | None:
        rid = self._selected_id()
        if rid is None:
            return None
        return data.get_record(rid)

    def _view_selected(self) -> None:
        r = self._selected()
        if r is None:
            messagebox.showinfo("View", "Select a record first.")
            return
        names = _name_lookup()
        lines = [
            f"#{r.record_id}",
            f"Student        : {r.student_id} — "
            f"{names.get(r.student_id, '?')}",
            f"Subject        : {r.subject_name}",
            f"Exam session   : {r.exam_session}",
            f"Year           : {r.year_group or '—'}",
            f"Prior          : "
            f"{r.prior_attainment if r.prior_attainment is not None else '—'}",
            f"Expected       : {r.expected_grade or '—'}",
            f"Target         : {r.target_grade or '—'}",
            f"Predicted      : {r.predicted_grade or '—'}",
            f"Actual         : {r.actual_grade or '—'}",
            f"VA score       : {r.va_label}",
            f"ALPS           : "
            f"{r.alps_indicator if r.alps_indicator is not None else '—'}",
            f"Status         : {r.status}",
            f"Teacher        : {r.teacher or '—'}",
        ]
        if r.actual_vs_target is not None:
            lines.append(
                f"Actual vs tgt  : {r.actual_vs_target:+d}")
        if r.predicted_vs_target is not None:
            lines.append(
                f"Pred vs tgt    : {r.predicted_vs_target:+d}")
        if r.notes:
            lines.extend(["", "Notes:", r.notes])
        messagebox.showinfo(f"VA #{r.record_id}", "\n".join(lines))

    def _new(self) -> None:
        RecordDialog(self.frame.winfo_toplevel(),
                       existing=None, on_save=self.refresh)

    def _edit_selected(self) -> None:
        r = self._selected()
        if r is None:
            messagebox.showinfo("Edit", "Select a record first.")
            return
        RecordDialog(self.frame.winfo_toplevel(),
                       existing=r, on_save=self.refresh)

    def _set_actual(self) -> None:
        r = self._selected()
        if r is None:
            messagebox.showinfo("Actual",
                                  "Select a record first.")
            return
        ActualDialog(self.frame.winfo_toplevel(),
                       r, on_save=self.refresh)

    def _set_predicted(self) -> None:
        r = self._selected()
        if r is None:
            messagebox.showinfo("Predicted",
                                  "Select a record first.")
            return
        PredictedDialog(self.frame.winfo_toplevel(),
                          r, on_save=self.refresh)

    def _status_selected(self) -> None:
        r = self._selected()
        if r is None:
            messagebox.showinfo("Status",
                                  "Select a record first.")
            return
        StatusDialog(self.frame.winfo_toplevel(),
                       r, on_save=self.refresh)

    def _delete_selected(self) -> None:
        r = self._selected()
        if r is None:
            messagebox.showinfo("Delete",
                                  "Select a record first.")
            return
        if not messagebox.askyesno("Delete",
                                     f"Delete VA #{r.record_id}?"):
            return
        try:
            data.delete_record(r.record_id)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


# ══ Summary tab ════════════════════════════════════════════════════

class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        self._build()
        self.refresh()

    def _build(self) -> None:
        ttk.Button(self.frame, text="Refresh",
                    command=self.refresh).pack(side="top", anchor="w",
                                                 padx=8, pady=(8, 4))
        self.text = tk.Text(self.frame, wrap="none", height=30,
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.text.configure(state="disabled")

    def refresh(self) -> None:
        summ = data.summary()
        lines = [
            f"Total records       : {summ.total_records}",
            f"Distinct students   : {summ.distinct_students}",
            f"Average VA          : "
            f"{summ.average_va if summ.average_va is not None else '—'}",
            f"Average ALPS        : "
            f"{summ.average_alps if summ.average_alps is not None else '—'}",
            f"Positive VA         : {summ.positive_va}",
            f"Negative VA         : {summ.negative_va}",
            f"Actual ≥ target     : {summ.above_target}",
            f"Actual < target     : {summ.below_target}",
            "",
            "By status:",
        ]
        for s in STATUSES:
            n = summ.by_status.get(s, 0)
            if n:
                lines.append(f"  {s:<14} : {n}")
        if summ.by_session:
            lines.append("")
            lines.append("By session:")
            for sess, n in summ.by_session.items():
                lines.append(f"  {sess:<16} : {n}")
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
    def __init__(self, parent: tk.Misc, existing: VARecord,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Status — #{existing.record_id}")
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
            data.set_status(self.existing.record_id, self.cb.get())
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class ActualDialog:
    def __init__(self, parent: tk.Misc, existing: VARecord,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Actual grade — #{existing.record_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form,
                   text=(f"Expected: {existing.expected_grade or '—'}  "
                          f"Target: {existing.target_grade or '—'}"),
                   foreground="#555").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(form, text="Actual grade:").grid(row=1, column=0,
                                                      sticky="e", pady=4)
        self.cb = ttk.Combobox(form, values=A_LEVEL_GRADES,
                                  state="readonly", width=8)
        if existing.actual_grade:
            self.cb.set(existing.actual_grade)
        self.cb.grid(row=1, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=2, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        grade = self.cb.get().strip()
        if not grade:
            messagebox.showerror("Actual", "Pick a grade.")
            return
        try:
            data.set_actual_grade(self.existing.record_id, grade)
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class PredictedDialog:
    def __init__(self, parent: tk.Misc, existing: VARecord,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Predicted grade — #{existing.record_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="Predicted grade:").grid(
            row=0, column=0, sticky="e", pady=4)
        self.cb = ttk.Combobox(form, values=("",) + A_LEVEL_GRADES,
                                  state="readonly", width=8)
        if existing.predicted_grade:
            self.cb.set(existing.predicted_grade)
        self.cb.grid(row=0, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=1, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.set_predicted_grade(self.existing.record_id,
                                         self.cb.get().strip() or None)
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class RecordDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: VARecord | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit VA Record" if existing
                          else "New VA Record")
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
                       text=self.existing.subject_name
                       ).grid(row=r, column=1, sticky="w", padx=6)
            self.subject_cb = None
        else:
            self.subject_cb = ttk.Combobox(
                form, values=_subject_options(), width=26)
            self.subject_cb.grid(row=r, column=1, sticky="w",
                                    padx=6)
        ttk.Label(form, text="Session:").grid(row=r, column=2,
                                                 sticky="e", pady=3)
        if self.existing:
            ttk.Label(form,
                       text=self.existing.exam_session
                       ).grid(row=r, column=3, sticky="w", padx=6)
            self.session_e = None
        else:
            self.session_e = ttk.Entry(form, width=14)
            self.session_e.insert(0,
                                      f"Summer {_dt.date.today().year + 1}")
            self.session_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Year:").grid(row=r, column=0,
                                              sticky="e", pady=3)
        self.year_cb = ttk.Combobox(form, values=("",) + YEAR_GROUPS,
                                       state="readonly", width=10)
        self.year_cb.set((self.existing.year_group or "")
                            if self.existing else "")
        self.year_cb.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Prior attainment:").grid(row=r, column=2,
                                                          sticky="e",
                                                          pady=3)
        self.prior_e = ttk.Entry(form, width=8)
        if (self.existing
                and self.existing.prior_attainment is not None):
            self.prior_e.insert(0,
                                  str(self.existing.prior_attainment))
        self.prior_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Expected:").grid(row=r, column=0,
                                                  sticky="e", pady=3)
        self.exp_cb = ttk.Combobox(form, values=("",) + A_LEVEL_GRADES,
                                      state="readonly", width=8)
        if self.existing and self.existing.expected_grade:
            self.exp_cb.set(self.existing.expected_grade)
        self.exp_cb.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Target (MTE):").grid(row=r, column=2,
                                                      sticky="e", pady=3)
        self.tgt_cb = ttk.Combobox(form, values=("",) + A_LEVEL_GRADES,
                                      state="readonly", width=8)
        if self.existing and self.existing.target_grade:
            self.tgt_cb.set(self.existing.target_grade)
        self.tgt_cb.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Predicted:").grid(row=r, column=0,
                                                   sticky="e", pady=3)
        self.pred_cb = ttk.Combobox(form, values=("",) + A_LEVEL_GRADES,
                                       state="readonly", width=8)
        if self.existing and self.existing.predicted_grade:
            self.pred_cb.set(self.existing.predicted_grade)
        self.pred_cb.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Actual:").grid(row=r, column=2,
                                                sticky="e", pady=3)
        self.act_cb = ttk.Combobox(form, values=("",) + A_LEVEL_GRADES,
                                      state="readonly", width=8)
        if self.existing and self.existing.actual_grade:
            self.act_cb.set(self.existing.actual_grade)
        self.act_cb.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="ALPS (1-9):").grid(row=r, column=0,
                                                    sticky="e", pady=3)
        self.alps_cb = ttk.Combobox(
            form,
            values=("",) + tuple(str(i) for i in range(1, 10)),
            state="readonly", width=6)
        if (self.existing
                and self.existing.alps_indicator is not None):
            self.alps_cb.set(str(self.existing.alps_indicator))
        self.alps_cb.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Status:").grid(row=r, column=2,
                                                sticky="e", pady=3)
        self.status_cb = ttk.Combobox(form, values=STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_STATUS)
        self.status_cb.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Teacher:").grid(row=r, column=0,
                                                 sticky="e", pady=3)
        self.teacher_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.teacher:
            self.teacher_e.insert(0, self.existing.teacher)
        self.teacher_e.grid(row=r, column=1, columnspan=3,
                              sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                               sticky="ne", pady=3)
        self.notes_t = tk.Text(form, width=60, height=4)
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
            session = self.existing.exam_session
        else:
            if self.student_cb is None:
                raise ValidationError("Pick a student")
            idx = self.student_cb.current()
            if idx < 0:
                raise ValidationError("Pick a student")
            sid = self._student_ids[idx]
            subject = (self.subject_cb.get().strip()
                        if self.subject_cb else "")
            session = (self.session_e.get().strip()
                        if self.session_e else "")
        return {
            "student_id":       sid,
            "subject_name":     subject,
            "exam_session":     session,
            "year_group":       self.year_cb.get().strip() or None,
            "prior_attainment": self.prior_e.get().strip() or None,
            "expected_grade":   self.exp_cb.get().strip() or None,
            "target_grade":     self.tgt_cb.get().strip() or None,
            "predicted_grade":  self.pred_cb.get().strip() or None,
            "actual_grade":     self.act_cb.get().strip() or None,
            "alps_indicator":   self.alps_cb.get().strip() or None,
            "status":           self.status_cb.get().strip(),
            "teacher":          self.teacher_e.get().strip(),
            "notes":            self.notes_t.get(
                                    "1.0", "end").strip(),
        }

    def _save(self) -> None:
        try:
            payload = self._collect()
            if self.existing:
                data.update_record(self.existing.record_id, payload)
            else:
                data.create_record(payload)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()
