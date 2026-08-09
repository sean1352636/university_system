"""Tkinter views for Sixth Form Self-Assessments."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable
from education_system.platform import branding
from education_system.systems.sixth_form.domain.assessment.self_assessment import (
    self_assessment as data,
)
from education_system.systems.sixth_form.domain.assessment.self_assessment.self_assessment import (
    ASSESSMENT_TYPES,
    DEFAULT_ASSESSMENT_TYPE,
    DEFAULT_STATUS,
    DIMENSIONS,
    SelfAssessment,
    STATUSES,
    ValidationError,
    dimension_label,
    likert_label,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_STATUS_TAGS = {
    "Draft":         ("#fff7e6", "#7a5800"),
    "Submitted":     ("#e6f0ff", "#1a3f8c"),
    "Under Review":  ("#fff0d6", "#7a5800"),
    "Reviewed":      ("#e6f7e6", "#0d6b2a"),
    "Acknowledged":  ("#e6f7e6", "#0d6b2a"),
    "Archived":      ("#eeeeee", "#444444"),
}


def open_self_assessment_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Self-Assessments — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    AssessmentsTab(nb, scope="open",             label="Open")
    AssessmentsTab(nb, scope="awaiting_review",  label="Awaiting Review")
    AssessmentsTab(nb, scope="all",              label="All")
    PerStudentTab(nb)
    SummaryTab(nb)


def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}")
            for s in rows]


# ══ Table tab ════════════════════════════════════════════════════

class AssessmentsTab:
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

        ttk.Label(bar, text="Type:").pack(side="left")
        self.f_type = ttk.Combobox(bar,
                                     values=("",) + ASSESSMENT_TYPES,
                                     state="readonly", width=22)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 8))

        if self.scope == "all":
            ttk.Label(bar, text="Status:").pack(side="left")
            self.f_status = ttk.Combobox(bar,
                                           values=("",) + STATUSES,
                                           state="readonly", width=14)
            self.f_status.current(0)
            self.f_status.pack(side="left", padx=(2, 8))
        else:
            self.f_status = None

        ttk.Label(bar, text="Reviewer:").pack(side="left")
        self.f_reviewer = ttk.Entry(bar, width=14)
        self.f_reviewer.pack(side="left", padx=(2, 8))

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left",
                                                  padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "date", "student", "type", "avg",
                "status", "reviewer", "reviewed_on")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings", selectmode="browse")
        widths = {"id": 60, "date": 90, "student": 110,
                   "type": 200, "avg": 70, "status": 110,
                   "reviewer": 140, "reviewed_on": 110}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center" if c in ("id", "avg")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _STATUS_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        self.tree.bind("<Double-Button-1>", lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("View / Edit",   self._edit),
                ("Submit",        self._submit),
                ("Record review", self._review),
                ("Acknowledge",   self._acknowledge),
                ("Change status", self._set_status),
                ("Delete",        self._delete),
                ("Refresh",       self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _clear(self) -> None:
        self.f_student.delete(0, "end")
        self.f_type.current(0)
        self.f_reviewer.delete(0, "end")
        if self.f_status is not None:
            self.f_status.current(0)
        self.refresh()

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_student.get().strip():
            f["student_id"] = self.f_student.get().strip()
        if self.f_type.get():
            f["assessment_type"] = self.f_type.get()
        if self.f_reviewer.get().strip():
            f["reviewer_like"] = self.f_reviewer.get().strip()
        if self.f_status is not None and self.f_status.get():
            f["status"] = self.f_status.get()
        if self.scope == "open":
            f["open_only"] = True
        elif self.scope == "awaiting_review":
            f["awaiting_review"] = True
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            rows = data.list_assessments(**self._filters())
        except ValidationError as e:
            messagebox.showerror("Self-Assessment", str(e),
                                    parent=self.frame)
            return
        for a in rows:
            avg = (f"{a.average_score:.2f}"
                    if a.average_score is not None else "—")
            self.tree.insert("", "end",
                              iid=str(a.assessment_id),
                              values=(a.assessment_id,
                                       a.assessment_date,
                                       a.student_id,
                                       a.assessment_type,
                                       avg, a.status,
                                       a.reviewer or "—",
                                       a.reviewed_on or "—"),
                              tags=(a.status,))
        self.count.config(text=f"{len(rows)} assessment(s)")

    def _selected(self) -> SelfAssessment | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Self-Assessment",
                                  "Select an assessment first.",
                                  parent=self.frame)
            return None
        return data.get_assessment(int(sel[0]))

    def _new(self) -> None:
        if SelfAssessmentEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        a = self._selected()
        if not a:
            return
        if SelfAssessmentEditor(self.frame,
                                    assessment=a).result is not None:
            self.refresh()

    def _submit(self) -> None:
        a = self._selected()
        if not a:
            return
        try:
            data.submit(a.assessment_id)
        except ValidationError as e:
            messagebox.showerror("Self-Assessment", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _review(self) -> None:
        a = self._selected()
        if not a:
            return
        if ReviewDialog(self.frame,
                          assessment=a).result is not None:
            self.refresh()

    def _acknowledge(self) -> None:
        a = self._selected()
        if not a:
            return
        try:
            data.acknowledge(a.assessment_id)
        except ValidationError as e:
            messagebox.showerror("Self-Assessment", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _set_status(self) -> None:
        a = self._selected()
        if not a:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(STATUSES), default=a.status)
        if not new:
            return
        try:
            data.set_status(a.assessment_id, new)
        except ValidationError as e:
            messagebox.showerror("Self-Assessment", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        a = self._selected()
        if not a:
            return
        if not messagebox.askyesno(
                "Self-Assessment",
                f"Delete assessment #{a.assessment_id}?",
                parent=self.frame):
            return
        data.delete_assessment(a.assessment_id)
        self.refresh()


# ══ Per-student tab ══════════════════════════════════════════════

class PerStudentTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Per Student")
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Student:").pack(side="left")
        self.combo = ttk.Combobox(bar, state="readonly", width=42)
        opts = _student_options()
        self.combo["values"] = [lbl for _, lbl in opts]
        self._opts = opts
        self.combo.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Show",
                    command=self._show).pack(side="left")

        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.text.config(state="disabled")

    def _show(self) -> None:
        idx = self.combo.current()
        if idx < 0:
            return
        sid = self._opts[idx][0]
        rows = data.assessments_for_student(sid)
        summ = data.student_summary(sid)
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end",
                            f"Self-Assessments for {sid}\n"
                            f"{'=' * 60}\n\n"
                            f"Total              : {summ.total}\n"
                            f"Awaiting review    : {summ.awaiting_review}\n"
                            f"Reviewed           : {summ.reviewed}\n"
                            f"Most-recent score  : "
                            f"{summ.most_recent_score if summ.most_recent_score is not None else '—'}\n\n")
        for a in rows:
            avg = (f"{a.average_score:.2f}"
                    if a.average_score is not None else "—")
            self.text.insert("end",
                                f"#{a.assessment_id}  "
                                f"{a.assessment_date}  "
                                f"{a.assessment_type}  "
                                f"avg={avg}  [{a.status}]\n")
            if a.strengths:
                self.text.insert("end",
                                    f"   + {a.strengths.splitlines()[0]}\n")
            if a.areas_to_improve:
                self.text.insert("end",
                                    f"   - {a.areas_to_improve.splitlines()[0]}\n")
            if a.reviewer:
                self.text.insert("end",
                                    f"   reviewer: {a.reviewer}"
                                    f" ({a.reviewed_on or '—'})\n")
            self.text.insert("end", "\n")
        self.text.config(state="disabled")


# ══ Summary tab ═══════════════════════════════════════════════════

class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.text.config(state="disabled")

    def refresh(self) -> None:
        s = data.summary()
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", "Self-Assessments Summary\n")
        self.text.insert("end", "=" * 60 + "\n\n")
        self.text.insert("end",
                            f"Total              : {s.total}\n"
                            f"Awaiting review    : {s.awaiting_review}\n"
                            f"Reviewed           : {s.reviewed}\n"
                            f"Distinct students  : {s.distinct_students}\n\n")
        self.text.insert("end", "By status:\n")
        for k in STATUSES:
            n = s.by_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<14}: {n}\n")
        self.text.insert("end", "\nBy type:\n")
        for k in ASSESSMENT_TYPES:
            n = s.by_type.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<22}: {n}\n")
        self.text.insert("end", "\nAverage per dimension:\n")
        for d in DIMENSIONS:
            v = s.average_per_dimension.get(d)
            if v is not None:
                self.text.insert("end",
                                    f"  {dimension_label(d):<22}: {v:.2f}\n")
        self.text.config(state="disabled")


# ══ Editor dialog ═════════════════════════════════════════════════

class SelfAssessmentEditor:
    def __init__(self, parent, *,
                 assessment: SelfAssessment | None = None) -> None:
        self.assessment = assessment
        self.result: SelfAssessment | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Edit assessment #{assessment.assessment_id}"
            if assessment else "New self-assessment")
        self.win.geometry("820x820")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()
        if assessment:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(3, weight=1)

        self.vars: dict[str, tk.Variable] = {}
        self.texts: dict[str, tk.Text] = {}

        ttk.Label(body, text="Student*").grid(
            row=0, column=0, sticky="w", padx=4, pady=2)
        self.student_combo = ttk.Combobox(body, state="readonly",
                                              width=42)
        opts = _student_options()
        self._student_opts = opts
        self.student_combo["values"] = [lbl for _, lbl in opts]
        self.student_combo.grid(row=0, column=1, columnspan=3,
                                  sticky="ew", padx=4, pady=2)

        def entry(row, col, label, key, width=18):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Entry(body, textvariable=v, width=width).grid(
                row=row, column=col + 1, sticky="ew", padx=4, pady=2)

        def combo(row, col, label, key, values, width=20):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Combobox(body, textvariable=v, values=values,
                          state="readonly", width=width).grid(
                row=row, column=col + 1, sticky="ew", padx=4, pady=2)

        entry(1, 0, "Date* (YYYY-MM-DD)", "assessment_date")
        combo(1, 2, "Type*", "assessment_type", ASSESSMENT_TYPES)
        entry(2, 0, "Term", "term")
        entry(2, 2, "Year group", "year_group")
        combo(3, 0, "Status*", "status", STATUSES)
        entry(3, 2, "Reviewer", "reviewer")
        entry(4, 0, "Reviewed on (YYYY-MM-DD)", "reviewed_on")

        # Dimensions panel
        dims_frame = ttk.LabelFrame(body,
                                          text="Ratings (1=Very Low .. 5=Excellent)")
        dims_frame.grid(row=5, column=0, columnspan=4,
                          sticky="ew", padx=4, pady=(8, 4))
        for i in range(4):
            dims_frame.grid_columnconfigure(i * 2 + 1, weight=1)
        rating_values = ("", "1", "2", "3", "4", "5")
        for i, d in enumerate(DIMENSIONS):
            r, c = divmod(i, 2)
            ttk.Label(dims_frame,
                        text=dimension_label(d)).grid(
                row=r, column=c * 2, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[d] = v
            ttk.Combobox(dims_frame, textvariable=v,
                          values=rating_values,
                          state="readonly", width=6).grid(
                row=r, column=c * 2 + 1, sticky="w", padx=4, pady=2)

        # Text panels
        row = 6
        for key, label in (
                ("strengths",          "Strengths"),
                ("areas_to_improve",   "Areas to improve"),
                ("action_plan",        "Action plan"),
                ("support_needed",     "Support needed"),
                ("proudest_moment",    "Proudest moment"),
                ("biggest_challenge",  "Biggest challenge"),
                ("reviewer_feedback",  "Reviewer feedback"),
                ("agreed_actions",     "Agreed actions"),
                ("notes",              "Notes"),
        ):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="nw", padx=4, pady=(6, 2))
            t = tk.Text(body, height=2, width=70, wrap="word")
            t.grid(row=row, column=1, columnspan=3,
                     sticky="ew", padx=4, pady=(6, 2))
            self.texts[key] = t
            row += 1

        actions = ttk.Frame(self.win)
        actions.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(actions, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(actions, text="Cancel",
                    command=self.win.destroy).pack(side="right")

        # Defaults
        self.vars["assessment_date"].set(
            _dt.date.today().isoformat())
        self.vars["assessment_type"].set(DEFAULT_ASSESSMENT_TYPE)
        self.vars["status"].set(DEFAULT_STATUS)

    def _load(self) -> None:
        a = self.assessment
        assert a is not None
        for i, (sid, _) in enumerate(self._student_opts):
            if sid == a.student_id:
                self.student_combo.current(i)
                break
        for key in ("assessment_date", "assessment_type",
                     "term", "year_group", "status",
                     "reviewer", "reviewed_on"):
            self.vars[key].set(getattr(a, key) or "")
        for d in DIMENSIONS:
            v = getattr(a, d)
            self.vars[d].set(str(v) if v is not None else "")
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(a, k) or "")

    def _save(self) -> None:
        idx = self.student_combo.current()
        if idx < 0:
            messagebox.showerror("Self-Assessment",
                                    "Pick a student.",
                                    parent=self.win)
            return
        payload: dict = {"student_id": self._student_opts[idx][0]}
        for k, v in self.vars.items():
            val = v.get().strip()
            if k in DIMENSIONS:
                payload[k] = (int(val) if val.isdigit() else None)
            else:
                payload[k] = val
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        try:
            if self.assessment:
                self.result = data.update_assessment(
                    self.assessment.assessment_id, payload)
            else:
                self.result = data.create_assessment(payload)
        except ValidationError as e:
            messagebox.showerror("Self-Assessment", str(e),
                                    parent=self.win)
            return
        self.win.destroy()


# ══ Review dialog ═════════════════════════════════════════════════

class ReviewDialog:
    def __init__(self, parent, *,
                 assessment: SelfAssessment) -> None:
        self.assessment = assessment
        self.result: SelfAssessment | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Review assessment #{assessment.assessment_id}")
        self.win.geometry("560x460")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()
        self.win.wait_window()

    def _build(self) -> None:
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Reviewer*").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self.reviewer = tk.StringVar(
            value=self.assessment.reviewer or "")
        ttk.Entry(body, textvariable=self.reviewer).grid(
            row=0, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(body, text="Reviewed on").grid(
            row=1, column=0, sticky="w", padx=4, pady=4)
        self.when = tk.StringVar(
            value=self.assessment.reviewed_on
            or _dt.date.today().isoformat())
        ttk.Entry(body, textvariable=self.when, width=14).grid(
            row=1, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(body, text="Feedback").grid(
            row=2, column=0, sticky="nw", padx=4, pady=4)
        self.fb = tk.Text(body, height=5, width=50, wrap="word")
        self.fb.insert("1.0", self.assessment.reviewer_feedback or "")
        self.fb.grid(row=2, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(body, text="Agreed actions").grid(
            row=3, column=0, sticky="nw", padx=4, pady=4)
        self.actions = tk.Text(body, height=5, width=50, wrap="word")
        self.actions.insert("1.0", self.assessment.agreed_actions or "")
        self.actions.grid(row=3, column=1, sticky="ew", padx=4, pady=4)

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")

    def _save(self) -> None:
        try:
            self.result = data.record_review(
                self.assessment.assessment_id,
                reviewer=self.reviewer.get().strip(),
                feedback=self.fb.get("1.0", "end").rstrip(),
                agreed_actions=self.actions.get("1.0", "end").rstrip(),
                reviewed_on=self.when.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Self-Assessment", str(e),
                                    parent=self.win)
            return
        self.win.destroy()


# ── Helpers ───────────────────────────────────────────────────────

def _prompt_choice(parent, title: str, options: list[str], *,
                    default: str | None = None) -> str | None:
    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry("320x140")
    win.transient(parent)
    win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(value=default or (options[0] if options else ""))
    ttk.Combobox(win, textvariable=var, values=options,
                  state="readonly").pack(fill="x", padx=8)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = var.get()
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="right", padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


__all__ = ["open_self_assessment_window"]
