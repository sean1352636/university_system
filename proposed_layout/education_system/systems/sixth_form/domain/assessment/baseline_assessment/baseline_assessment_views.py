"""Tkinter views for Sixth Form Baseline Assessment."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable
from education_system.platform import branding
from education_system.systems.sixth_form.domain.assessment.baseline_assessment import (
    baseline_assessment as data,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)
from education_system.systems.sixth_form.domain.assessment.baseline_assessment.baseline_assessment import (
    A_LEVEL_GRADES,
    ASSESSMENT_TYPES,
    BaselineRecord,
    CONFIDENCE,
    DEFAULT_ASSESSMENT_TYPE,
    DEFAULT_CONFIDENCE,
    GCSE_GRADES,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_baseline_assessment_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Baseline Assessment — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    RecordsTab(nb)
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

        ttk.Label(bar, text="Type:").pack(side="left")
        self.f_type = ttk.Combobox(bar,
                                     values=("",) + ASSESSMENT_TYPES,
                                     state="readonly", width=18)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Grade:").pack(side="left")
        self.f_grade = ttk.Entry(bar, width=6)
        self.f_grade.pack(side="left", padx=(2, 8))

        self.primary_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Primary only",
                          variable=self.primary_var,
                          command=self.refresh).pack(side="left", padx=4)

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "primary", "student", "name", "subject",
                "type", "date", "score", "grade",
                "confidence")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "primary": 50, "student": 80,
                  "name": 160, "subject": 140,
                  "type": 130, "date": 100,
                  "score": 100, "grade": 60,
                  "confidence": 90}
        headings = {"id": "ID", "primary": "★",
                    "student": "Student", "name": "Name",
                    "subject": "Subject", "type": "Type",
                    "date": "Date", "score": "Score",
                    "grade": "Grade", "confidence": "Confidence"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = "center" if c == "primary" else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("primary", background="#d8f4d8")
        self.tree.tag_configure("low",     background="#fff7d0")
        self.tree.bind("<Double-1>", lambda _e: self._edit_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(actions, text="View",
                    command=self._view_selected).pack(side="left")
        ttk.Button(actions, text="Edit",
                    command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Mark primary",
                    command=self._set_primary).pack(side="left", padx=4)
        ttk.Button(actions, text="Delete",
                    command=self._delete_selected).pack(side="left",
                                                          padx=4)
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear(self) -> None:
        self.f_student.delete(0, "end")
        self.f_subject.set("")
        self.f_type.current(0)
        self.f_grade.delete(0, "end")
        self.primary_var.set(False)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_records(
                student_id=self.f_student.get().strip() or None,
                subject_name=self.f_subject.get().strip() or None,
                assessment_type=self.f_type.get() or None,
                grade=self.f_grade.get().strip() or None,
                primary_only=self.primary_var.get(),
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        names = _name_lookup()
        for r in rows:
            tags = []
            if r.is_primary:
                tags.append("primary")
            if r.confidence == "Low":
                tags.append("low")
            self.tree.insert("", "end", iid=str(r.record_id), values=(
                r.record_id, "★" if r.is_primary else "",
                r.student_id, names.get(r.student_id, "?"),
                r.subject_name or "—", r.assessment_type,
                r.assessment_date or "—",
                r.score_label, r.baseline_grade or "—",
                r.confidence,
            ), tags=tuple(tags))
        self.count_var.set(f"{len(rows)} record(s).")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _selected(self) -> BaselineRecord | None:
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
            f"#{r.record_id}" +
            ("  (PRIMARY)" if r.is_primary else ""),
            f"Student       : {r.student_id} — "
            f"{names.get(r.student_id, '?')}",
            f"Subject       : {r.subject_name or '—'}",
            f"Type          : {r.assessment_type}",
            f"Date          : {r.assessment_date or '—'}",
            f"Raw / Max     : "
            f"{r.raw_score or '—'} / {r.max_score or '—'}",
            f"Percentage    : "
            f"{r.percentage if r.percentage is not None else '—'}",
            f"Standardised  : "
            f"{r.standardised_score if r.standardised_score is not None else '—'}",
            f"Baseline grade: {r.baseline_grade or '—'}",
            f"Confidence    : {r.confidence}",
            f"Assessor      : {r.assessor or '—'}",
        ]
        if r.notes:
            lines.append("")
            lines.append("Notes:")
            lines.append(r.notes)
        messagebox.showinfo(f"Baseline #{r.record_id}",
                              "\n".join(lines))

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

    def _set_primary(self) -> None:
        r = self._selected()
        if r is None:
            messagebox.showinfo("Primary",
                                  "Select a record first.")
            return
        try:
            data.set_primary(r.record_id)
        except ValidationError as e:
            messagebox.showerror("Primary", str(e))
            return
        self.refresh()

    def _delete_selected(self) -> None:
        r = self._selected()
        if r is None:
            messagebox.showinfo("Delete",
                                  "Select a record first.")
            return
        if not messagebox.askyesno("Delete",
                                     f"Delete record #{r.record_id}?"):
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
            f"Total records      : {summ.total_records}",
            f"Primary baselines  : {summ.primary_count}",
            f"Distinct students  : {summ.distinct_students}",
            f"Average percentage : "
            f"{summ.average_percentage if summ.average_percentage is not None else '—'}",
            "",
            "By type:",
        ]
        for t in ASSESSMENT_TYPES:
            n = summ.by_type.get(t, 0)
            if n:
                lines.append(f"  {t:<22} : {n}")
        if summ.by_subject:
            lines.append("")
            lines.append("Top subjects:")
            for sub, n in list(summ.by_subject.items())[:15]:
                lines.append(f"  {sub:<22} : {n}")
        if summ.by_grade:
            lines.append("")
            lines.append("By grade:")
            for g, n in summ.by_grade.items():
                lines.append(f"  {g:<8} : {n}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")


# ══ Dialog ════════════════════════════════════════════════════════

class RecordDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: BaselineRecord | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Baseline Record" if existing
                          else "New Baseline Record")
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
        self.subject_cb = ttk.Combobox(
            form, values=_subject_options(), width=24)
        if self.existing:
            self.subject_cb.set(self.existing.subject_name or "")
        self.subject_cb.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Type:").grid(row=r, column=2,
                                              sticky="e", pady=3)
        self.type_cb = ttk.Combobox(form, values=ASSESSMENT_TYPES,
                                       state="readonly", width=18)
        self.type_cb.set(self.existing.assessment_type
                            if self.existing
                            else DEFAULT_ASSESSMENT_TYPE)
        self.type_cb.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Date:").grid(row=r, column=0,
                                              sticky="e", pady=3)
        self.date_e = ttk.Entry(form, width=14)
        self.date_e.insert(0, (self.existing.assessment_date
                                  if self.existing
                                    and self.existing.assessment_date
                                  else _today()))
        self.date_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Confidence:").grid(row=r, column=2,
                                                    sticky="e", pady=3)
        self.confidence_cb = ttk.Combobox(
            form, values=CONFIDENCE,
            state="readonly", width=10)
        self.confidence_cb.set(self.existing.confidence
                                    if self.existing
                                    else DEFAULT_CONFIDENCE)
        self.confidence_cb.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Raw score:").grid(row=r, column=0,
                                                   sticky="e", pady=3)
        self.raw_e = ttk.Entry(form, width=10)
        if self.existing and self.existing.raw_score is not None:
            self.raw_e.insert(0, str(self.existing.raw_score))
        self.raw_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Max score:").grid(row=r, column=2,
                                                   sticky="e", pady=3)
        self.max_e = ttk.Entry(form, width=10)
        if self.existing and self.existing.max_score is not None:
            self.max_e.insert(0, str(self.existing.max_score))
        self.max_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Percentage:").grid(row=r, column=0,
                                                    sticky="e", pady=3)
        self.pct_e = ttk.Entry(form, width=8)
        if self.existing and self.existing.percentage is not None:
            self.pct_e.insert(0, str(self.existing.percentage))
        self.pct_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Standardised:").grid(row=r, column=2,
                                                      sticky="e", pady=3)
        self.std_e = ttk.Entry(form, width=8)
        if (self.existing
                and self.existing.standardised_score is not None):
            self.std_e.insert(0,
                                str(self.existing.standardised_score))
        self.std_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Baseline grade:").grid(
            row=r, column=0, sticky="e", pady=3)
        self.grade_cb = ttk.Combobox(
            form,
            values=[""] + list(A_LEVEL_GRADES) + list(GCSE_GRADES),
            width=10)
        if self.existing and self.existing.baseline_grade:
            self.grade_cb.set(self.existing.baseline_grade)
        self.grade_cb.grid(row=r, column=1, sticky="w", padx=6)
        self.primary_var = tk.BooleanVar(
            value=(self.existing.is_primary
                   if self.existing else False))
        ttk.Checkbutton(form, text="Primary baseline",
                          variable=self.primary_var).grid(
            row=r, column=2, columnspan=2, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Assessor:").grid(row=r, column=0,
                                                  sticky="e", pady=3)
        self.assessor_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.assessor:
            self.assessor_e.insert(0, self.existing.assessor)
        self.assessor_e.grid(row=r, column=1, columnspan=3,
                                sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                               sticky="ne", pady=3)
        self.notes_t = tk.Text(form, width=50, height=3)
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
            "student_id":         sid,
            "subject_name":       self.subject_cb.get().strip() or None,
            "assessment_type":    self.type_cb.get().strip(),
            "assessment_date":    self.date_e.get().strip(),
            "raw_score":          self.raw_e.get().strip() or None,
            "max_score":          self.max_e.get().strip() or None,
            "percentage":         self.pct_e.get().strip() or None,
            "standardised_score": self.std_e.get().strip() or None,
            "baseline_grade":     self.grade_cb.get().strip() or None,
            "confidence":         self.confidence_cb.get().strip(),
            "is_primary":         self.primary_var.get(),
            "assessor":           self.assessor_e.get().strip(),
            "notes":              self.notes_t.get("1.0", "end").strip(),
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
