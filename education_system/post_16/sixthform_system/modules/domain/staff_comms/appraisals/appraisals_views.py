"""Tkinter views for Sixth Form Appraisals."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from education_system.shared import branding
from education_system.post_16.sixthform_system.modules.domain.staff_comms.appraisals import (
    appraisals as data,
)
from education_system.post_16.sixthform_system.modules.domain.staff_comms.appraisals.appraisals import (
    Appraisal,
    DEFAULT_OBJECTIVE_STATUS,
    DEFAULT_OBJECTIVE_TYPE,
    DEFAULT_PAY_PROGRESSION,
    DEFAULT_STATUS,
    GRADES,
    OBJECTIVE_STATUSES,
    OBJECTIVE_TYPES,
    Objective,
    PAY_PROGRESSION,
    STATUSES,
    ValidationError,
    grade_label,
)
from education_system.post_16.sixthform_system.modules.domain.staff_comms.staff import (
    staff as staff_data,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_APPR_TAGS = {
    "Setting Objectives": ("#fff7e6", "#7a5800"),
    "In Progress":        ("#e6f0ff", "#1a3f8c"),
    "Mid-Year Review":    ("#fff0d6", "#7a5800"),
    "Awaiting End Year":  ("#e6e6ff", "#3a3a8c"),
    "End Year Review":    ("#fff0d6", "#7a5800"),
    "Completed":          ("#e6f7e6", "#0d6b2a"),
    "Closed":             ("#eeeeee", "#444444"),
    "Archived":           ("#dddddd", "#444444"),
}
_OBJ_TAGS = {
    "Not Started":         ("#fff7e6", "#7a5800"),
    "In Progress":         ("#e6f0ff", "#1a3f8c"),
    "On Track":            ("#e6f7e6", "#0d6b2a"),
    "At Risk":             ("#ffd1d1", "#8c0d0d"),
    "Achieved":            ("#d6ffd6", "#0d6b2a"),
    "Partially Achieved":  ("#fff0d6", "#7a5800"),
    "Not Achieved":        ("#ffd1d1", "#8c0d0d"),
    "Removed":             ("#eeeeee", "#444444"),
}


def open_appraisals_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Appraisals — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    AppraisalsTab(nb)
    SummaryTab(nb)


def _staff_options() -> list[tuple[str, str]]:
    rows = sorted(staff_data.list_staff(),
                   key=lambda s: s.staff_id)
    return [(s.staff_id,
             f"{s.staff_id} — "
             f"{getattr(s, 'first_name', '')} "
             f"{getattr(s, 'last_name', '')}".strip())
            for s in rows]


def _staff_options_optional() -> list[tuple[str | None, str]]:
    return [(None, "(none)"), *_staff_options()]


class AppraisalsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Appraisals & Objectives")
        paned = ttk.PanedWindow(self.frame, orient="vertical")
        paned.pack(fill="both", expand=True, padx=8, pady=8)
        self.top = ttk.Frame(paned)
        self.bottom = ttk.Frame(paned)
        paned.add(self.top, weight=3)
        paned.add(self.bottom, weight=2)
        self._build_top()
        self._build_bottom()
        self.refresh()

    def _build_top(self) -> None:
        bar = ttk.Frame(self.top)
        bar.pack(fill="x", pady=(0, 4))
        ttk.Label(bar, text="Cycle:").pack(side="left")
        self.f_cycle = ttk.Entry(bar, width=14)
        self.f_cycle.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Staff id:").pack(side="left")
        self.f_staff = ttk.Entry(bar, width=12)
        self.f_staff.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar,
                                       values=("",) + STATUSES,
                                       state="readonly", width=20)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 8))
        self.open_only = tk.BooleanVar()
        ttk.Checkbutton(bar, text="Open only",
                         variable=self.open_only,
                         command=self.refresh).pack(side="left",
                                                        padx=(2, 8))
        self.mid_overdue = tk.BooleanVar()
        ttk.Checkbutton(bar, text="Mid-year overdue",
                         variable=self.mid_overdue,
                         command=self.refresh).pack(side="left",
                                                        padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="New appraisal",
                    command=self._new).pack(side="left",
                                                padx=(16, 0))

        table_frame = ttk.Frame(self.top)
        table_frame.pack(fill="both", expand=True)
        cols = ("id", "staff", "cycle", "appraiser", "mid_year",
                "end_year", "grade", "pay", "status",
                "objectives")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "staff": 110, "cycle": 110,
                   "appraiser": 110, "mid_year": 100,
                   "end_year": 100, "grade": 90, "pay": 100,
                   "status": 170, "objectives": 80}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "grade",
                                                  "objectives")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _APPR_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        self.tree.tag_configure("overdue", background="#ffd1d1",
                                  foreground="#8c0d0d")
        self.tree.bind("<<TreeviewSelect>>",
                         lambda _e: self._refresh_objectives())
        self.tree.bind("<Double-Button-1>",
                         lambda _e: self._edit())

        actions = ttk.Frame(self.top)
        actions.pack(fill="x", pady=(4, 0))
        for label, cmd in (
                ("Edit",                self._edit),
                ("Set objectives date", self._set_objectives_date),
                ("Mid-year review",     self._mid_year),
                ("End-year review",     self._end_year),
                ("Close",               self._close),
                ("Change status",       self._set_status),
                ("Delete",              self._delete),
                ("Refresh",             self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _build_bottom(self) -> None:
        bar = ttk.Frame(self.bottom)
        bar.pack(fill="x", pady=(0, 4))
        ttk.Label(bar, text="Objectives for selected appraisal"
                  ).pack(side="left")
        ttk.Button(bar, text="Add",
                    command=self._add_objective).pack(
            side="right", padx=4)
        ttk.Button(bar, text="Edit",
                    command=self._edit_objective).pack(
            side="right", padx=4)
        ttk.Button(bar, text="Change status",
                    command=self._set_objective_status).pack(
            side="right", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete_objective).pack(
            side="right", padx=4)

        table_frame = ttk.Frame(self.bottom)
        table_frame.pack(fill="both", expand=True)
        cols = ("id", "n", "type", "title", "weighting",
                "status", "reviewed_on")
        self.otree = ttk.Treeview(table_frame, columns=cols,
                                       show="headings",
                                       selectmode="browse")
        widths = {"id": 50, "n": 40, "type": 180,
                     "title": 360, "weighting": 90,
                     "status": 150, "reviewed_on": 110}
        for c in cols:
            self.otree.heading(c,
                                   text=c.replace("_", " ").title())
            self.otree.column(c, width=widths[c],
                                  anchor=("center"
                                           if c in ("id", "n",
                                                      "weighting")
                                           else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.otree.yview)
        self.otree.configure(yscrollcommand=vsb.set)
        self.otree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _OBJ_TAGS.items():
            self.otree.tag_configure(status, background=bg,
                                          foreground=fg)
        self.otree.bind("<Double-Button-1>",
                            lambda _e: self._edit_objective())

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_cycle.get().strip():
            f["cycle"] = self.f_cycle.get().strip()
        if self.f_staff.get().strip():
            f["staff_id"] = self.f_staff.get().strip()
        if self.f_status.get():
            f["status"] = self.f_status.get()
        if self.open_only.get():
            f["open_only"] = True
        if self.mid_overdue.get():
            f["mid_year_overdue"] = True
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        rows = data.list_appraisals(**self._filters())
        for a in rows:
            n_obj = data.objective_count(a.appraisal_id)
            grade_txt = (f"{a.overall_grade} "
                            f"{grade_label(a.overall_grade)[:3]}"
                            if a.overall_grade else "—")
            tag = ("overdue" if a.mid_year_overdue
                     else a.status)
            self.tree.insert(
                "", "end", iid=str(a.appraisal_id),
                values=(a.appraisal_id, a.staff_id, a.cycle,
                         a.appraiser_id or "—",
                         a.mid_year_review_on or "—",
                         a.end_year_review_on or "—",
                         grade_txt, a.pay_progression,
                         a.status, n_obj),
                tags=(tag,))
        self.count.config(text=f"{len(rows)} appraisal(s)")
        self._refresh_objectives()

    def _selected(self) -> Appraisal | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Appraisals",
                                  "Select an appraisal first.",
                                  parent=self.frame)
            return None
        return data.get_appraisal(int(sel[0]))

    def _refresh_objectives(self) -> None:
        for iid in self.otree.get_children():
            self.otree.delete(iid)
        sel = self.tree.selection()
        if not sel:
            return
        aid = int(sel[0])
        for o in data.list_objectives(aid):
            w = (f"{o.weighting:.0f}%"
                  if o.weighting is not None else "—")
            self.otree.insert(
                "", "end", iid=str(o.objective_id),
                values=(o.objective_id, o.objective_number,
                         o.objective_type, o.title, w,
                         o.status, o.reviewed_on or "—"),
                tags=(o.status,))

    def _selected_objective(self) -> Objective | None:
        sel = self.otree.selection()
        if not sel:
            messagebox.showinfo("Appraisals",
                                  "Select an objective first.",
                                  parent=self.frame)
            return None
        return data.get_objective(int(sel[0]))

    def _new(self) -> None:
        if AppraisalEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        a = self._selected()
        if a and AppraisalEditor(self.frame,
                                       appraisal=a).result is not None:
            self.refresh()

    def _set_objectives_date(self) -> None:
        a = self._selected()
        if not a:
            return
        when = _prompt_text(
            self.frame, "Objectives set on (YYYY-MM-DD)",
            initial=_dt.date.today().isoformat())
        if not when:
            return
        try:
            data.set_objectives(a.appraisal_id,
                                    objectives_set_on=when)
        except ValidationError as e:
            messagebox.showerror("Appraisals", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _mid_year(self) -> None:
        a = self._selected()
        if not a:
            return
        when = _prompt_text(self.frame,
                              "Reviewed on (YYYY-MM-DD)",
                              initial=_dt.date.today().isoformat())
        if not when:
            return
        try:
            data.record_mid_year(a.appraisal_id,
                                       reviewed_on=when)
        except ValidationError as e:
            messagebox.showerror("Appraisals", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _end_year(self) -> None:
        a = self._selected()
        if not a:
            return
        if EndYearDialog(self.frame,
                            appraisal=a).result is not None:
            self.refresh()

    def _close(self) -> None:
        a = self._selected()
        if not a:
            return
        try:
            data.close_appraisal(a.appraisal_id)
        except ValidationError as e:
            messagebox.showerror("Appraisals", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _set_status(self) -> None:
        a = self._selected()
        if not a:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(STATUSES),
                                default=a.status)
        if not new:
            return
        try:
            data.set_appraisal_status(a.appraisal_id, new)
        except ValidationError as e:
            messagebox.showerror("Appraisals", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        a = self._selected()
        if not a:
            return
        if not messagebox.askyesno(
                "Appraisals",
                f"Delete appraisal #{a.appraisal_id} "
                "and all objectives?",
                parent=self.frame):
            return
        data.delete_appraisal(a.appraisal_id)
        self.refresh()

    def _add_objective(self) -> None:
        a = self._selected()
        if not a:
            return
        if ObjectiveEditor(
                self.frame,
                appraisal_id=a.appraisal_id).result is not None:
            self._refresh_objectives()
            self.refresh()

    def _edit_objective(self) -> None:
        a = self._selected()
        o = self._selected_objective()
        if not a or not o:
            return
        if ObjectiveEditor(
                self.frame, appraisal_id=a.appraisal_id,
                objective=o).result is not None:
            self._refresh_objectives()

    def _set_objective_status(self) -> None:
        o = self._selected_objective()
        if not o:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(OBJECTIVE_STATUSES),
                                default=o.status)
        if not new:
            return
        try:
            data.set_objective_status(o.objective_id, new)
        except ValidationError as e:
            messagebox.showerror("Appraisals", str(e),
                                    parent=self.frame)
            return
        self._refresh_objectives()

    def _delete_objective(self) -> None:
        o = self._selected_objective()
        if not o:
            return
        if not messagebox.askyesno(
                "Appraisals",
                f"Delete objective O{o.objective_number}?",
                parent=self.frame):
            return
        data.delete_objective(o.objective_id)
        self._refresh_objectives()
        self.refresh()


class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8,
                          pady=(4, 8))
        self.refresh()

    def refresh(self) -> None:
        s = data.summary()
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", "Appraisals Summary\n")
        self.text.insert("end", "=" * 60 + "\n\n")
        self.text.insert("end",
                            f"Total appraisals       : {s.total}\n"
                            f"Open                   : {s.open_count}\n"
                            f"Mid-year overdue       : {s.mid_year_overdue}\n"
                            f"Completed              : {s.completed}\n"
                            f"Upholding standards    : {s.upholding_standards}\n"
                            f"Pay progression: Yes   : {s.pay_progression_yes}\n"
                            f"Pay progression: Defer : {s.pay_progression_deferred}\n"
                            f"Distinct cycles        : {s.distinct_cycles}\n"
                            f"Average grade          : "
                            f"{s.average_grade if s.average_grade is not None else '—'}\n"
                            f"Total objectives       : {s.total_objectives}\n"
                            f"Objectives achieved    : {s.objectives_achieved}\n\n")
        self.text.insert("end", "By cycle:\n")
        for k, n in s.by_cycle.items():
            if n:
                self.text.insert("end", f"  {k:<14}: {n}\n")
        self.text.insert("end", "\nBy status:\n")
        for k in STATUSES:
            n = s.by_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<22}: {n}\n")
        self.text.insert("end", "\nBy grade:\n")
        for g in GRADES:
            n = s.by_grade.get(g, 0)
            if n:
                self.text.insert("end",
                                    f"  {g}  {grade_label(g):<24}: {n}\n")
        self.text.insert("end", "\nBy pay progression:\n")
        for k in PAY_PROGRESSION:
            n = s.by_pay_progression.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<16}: {n}\n")
        if s.by_objective_status:
            self.text.insert("end", "\nBy objective status:\n")
            for k in OBJECTIVE_STATUSES:
                n = s.by_objective_status.get(k, 0)
                if n:
                    self.text.insert("end",
                                        f"  {k:<22}: {n}\n")
        self.text.config(state="disabled")


# ── Editors ──────────────────────────────────────────────

class AppraisalEditor:
    def __init__(self, parent, *,
                 appraisal: Appraisal | None = None) -> None:
        self.appraisal = appraisal
        self.result: Appraisal | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Edit appraisal #{appraisal.appraisal_id}"
                          if appraisal else "New appraisal")
        self.win.geometry("880x820")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if appraisal:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(3, weight=1)
        self.vars: dict[str, tk.Variable] = {}
        self.texts: dict[str, tk.Text] = {}
        self.bools: dict[str, tk.BooleanVar] = {}

        ttk.Label(body, text="Staff*").grid(
            row=0, column=0, sticky="w", padx=4, pady=2)
        self.staff_combo = ttk.Combobox(body, state="readonly",
                                            width=42)
        opts = _staff_options()
        self._staff_opts = opts
        self.staff_combo["values"] = [lbl for _, lbl in opts]
        self.staff_combo.grid(row=0, column=1, sticky="ew",
                                  padx=4, pady=2)

        ttk.Label(body, text="Appraiser").grid(
            row=0, column=2, sticky="w", padx=4, pady=2)
        self.appr_combo = ttk.Combobox(body, state="readonly",
                                            width=42)
        appr_opts = _staff_options_optional()
        self._appr_opts = appr_opts
        self.appr_combo["values"] = [lbl for _, lbl in appr_opts]
        self.appr_combo.current(0)
        self.appr_combo.grid(row=0, column=3, sticky="ew",
                                  padx=4, pady=2)

        def entry(row, col, label, key, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Entry(body, textvariable=v, width=width).grid(
                row=row, column=col + 1, sticky="ew", padx=4, pady=2)

        def combo(row, col, label, key, values, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Combobox(body, textvariable=v, values=values,
                          state="readonly", width=width).grid(
                row=row, column=col + 1, sticky="ew", padx=4, pady=2)

        entry(1, 0, "Cycle*", "cycle")
        entry(1, 2, "Appraiser name", "appraiser_name")
        entry(2, 0, "Job role", "job_role")
        combo(2, 2, "Status*", "status", STATUSES)
        entry(3, 0, "Objectives set on", "objectives_set_on")
        entry(3, 2, "Mid-year review on", "mid_year_review_on")
        entry(4, 0, "End-year review on", "end_year_review_on")
        combo(4, 2, "Overall grade", "overall_grade",
                 ("", "1", "2", "3", "4"))
        combo(5, 0, "Pay progression*", "pay_progression",
                 PAY_PROGRESSION)
        self.bools["self_review_completed"] = tk.BooleanVar()
        ttk.Checkbutton(body, text="Self review completed",
                         variable=self.bools[
                             "self_review_completed"]).grid(
            row=5, column=2, sticky="w", padx=4, pady=2)
        self.bools["upholding_standards"] = tk.BooleanVar(
            value=True)
        ttk.Checkbutton(body, text="Upholding standards",
                         variable=self.bools[
                             "upholding_standards"]).grid(
            row=6, column=0, sticky="w", padx=4, pady=2)

        row = 7
        for key, label in (
                ("strengths",          "Strengths"),
                ("areas_to_develop",   "Areas to develop"),
                ("cpd_needs",          "CPD needs"),
                ("appraiser_comments", "Appraiser comments"),
                ("appraisee_comments", "Appraisee comments"),
                ("notes",              "Notes"),
        ):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="nw", padx=4, pady=(6, 2))
            t = tk.Text(body, height=2, width=74, wrap="word")
            t.grid(row=row, column=1, columnspan=3,
                     sticky="ew", padx=4, pady=(6, 2))
            self.texts[key] = t
            row += 1

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")

        today = _dt.date.today()
        self.vars["cycle"].set(f"{today.year}-{today.year + 1}")
        self.vars["status"].set(DEFAULT_STATUS)
        self.vars["pay_progression"].set(DEFAULT_PAY_PROGRESSION)

    def _load(self) -> None:
        a = self.appraisal
        assert a is not None
        for i, (sid, _) in enumerate(self._staff_opts):
            if sid == a.staff_id:
                self.staff_combo.current(i)
                break
        for i, (sid, _) in enumerate(self._appr_opts):
            if sid == a.appraiser_id:
                self.appr_combo.current(i)
                break
        for key in ("cycle", "appraiser_name", "job_role",
                     "objectives_set_on", "mid_year_review_on",
                     "end_year_review_on", "status",
                     "pay_progression"):
            self.vars[key].set(getattr(a, key) or "")
        self.vars["overall_grade"].set(
            str(a.overall_grade)
            if a.overall_grade is not None else "")
        for k in self.bools:
            self.bools[k].set(getattr(a, k))
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(a, k) or "")

    def _save(self) -> None:
        sidx = self.staff_combo.current()
        if sidx < 0:
            messagebox.showerror("Appraisals",
                                    "Pick a staff member.",
                                    parent=self.win)
            return
        aidx = self.appr_combo.current()
        payload: dict = {
            "staff_id": self._staff_opts[sidx][0],
            "appraiser_id": (self._appr_opts[aidx][0]
                                if aidx >= 0 else None),
        }
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        for k, b in self.bools.items():
            payload[k] = b.get()
        try:
            if self.appraisal:
                self.result = data.update_appraisal(
                    self.appraisal.appraisal_id, payload)
            else:
                self.result = data.create_appraisal(payload)
        except ValidationError as exc:
            messagebox.showerror("Appraisals", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class ObjectiveEditor:
    def __init__(self, parent, *,
                 appraisal_id: int,
                 objective: Objective | None = None) -> None:
        self.appraisal_id = appraisal_id
        self.objective = objective
        self.result: Objective | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Edit objective O{objective.objective_number}"
            if objective else "New objective")
        self.win.geometry("780x780")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if objective:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        self.vars: dict[str, tk.Variable] = {}
        self.texts: dict[str, tk.Text] = {}

        def entry(row, label, key):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Entry(body, textvariable=v).grid(
                row=row, column=1, sticky="ew", padx=4, pady=2)

        def combo(row, label, key, values):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Combobox(body, textvariable=v, values=values,
                          state="readonly").grid(
                row=row, column=1, sticky="ew", padx=4, pady=2)

        entry(0, "Title*", "title")
        combo(1, "Type*", "objective_type", OBJECTIVE_TYPES)
        combo(2, "Status*", "status", OBJECTIVE_STATUSES)
        entry(3, "Target metric", "target_metric")
        entry(4, "Weighting (%)", "weighting")
        entry(5, "Reviewed on", "reviewed_on")

        row = 6
        for key, label in (
                ("description",       "Description"),
                ("success_criteria",  "Success criteria"),
                ("progress_notes",    "Progress notes"),
                ("mid_year_progress", "Mid-year progress"),
                ("end_year_evidence", "End-year evidence"),
                ("notes",             "Notes"),
        ):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="nw", padx=4, pady=(6, 2))
            t = tk.Text(body, height=3, wrap="word")
            t.grid(row=row, column=1, sticky="ew",
                     padx=4, pady=(6, 2))
            self.texts[key] = t
            row += 1

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")

        self.vars["objective_type"].set(DEFAULT_OBJECTIVE_TYPE)
        self.vars["status"].set(DEFAULT_OBJECTIVE_STATUS)

    def _load(self) -> None:
        o = self.objective
        assert o is not None
        for key in ("title", "objective_type", "status",
                     "target_metric", "reviewed_on"):
            self.vars[key].set(getattr(o, key) or "")
        self.vars["weighting"].set(
            str(o.weighting) if o.weighting is not None else "")
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(o, k) or "")

    def _save(self) -> None:
        payload: dict = {}
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        try:
            if self.objective:
                self.result = data.update_objective(
                    self.objective.objective_id, payload)
            else:
                self.result = data.add_objective(
                    self.appraisal_id, payload)
        except ValidationError as exc:
            messagebox.showerror("Appraisals", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class EndYearDialog:
    def __init__(self, parent, *,
                 appraisal: Appraisal) -> None:
        self.appraisal = appraisal
        self.result: Appraisal | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"End-year review — #{appraisal.appraisal_id}")
        self.win.geometry("680x680")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Reviewed on").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self.when = tk.StringVar(
            value=_dt.date.today().isoformat())
        ttk.Entry(body, textvariable=self.when, width=14).grid(
            row=0, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(body, text="Overall grade").grid(
            row=1, column=0, sticky="w", padx=4, pady=4)
        self.grade = tk.StringVar(
            value=str(appraisal.overall_grade)
            if appraisal.overall_grade else "")
        ttk.Combobox(body, textvariable=self.grade,
                      values=("", "1", "2", "3", "4"),
                      state="readonly", width=8).grid(
            row=1, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(body, text="Pay progression").grid(
            row=2, column=0, sticky="w", padx=4, pady=4)
        self.pay = tk.StringVar(value=appraisal.pay_progression)
        ttk.Combobox(body, textvariable=self.pay,
                      values=PAY_PROGRESSION,
                      state="readonly").grid(
            row=2, column=1, sticky="ew", padx=4, pady=4)
        self.upholding = tk.BooleanVar(
            value=appraisal.upholding_standards)
        ttk.Checkbutton(body, text="Upholding standards",
                         variable=self.upholding).grid(
            row=3, column=0, columnspan=2, sticky="w",
            padx=4, pady=4)

        self.texts: dict[str, tk.Text] = {}
        row = 4
        for key, label in (
                ("strengths",         "Strengths"),
                ("areas_to_develop",  "Areas to develop"),
                ("cpd_needs",         "CPD needs"),
                ("appraiser_comments", "Appraiser comments"),
        ):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="nw", padx=4, pady=4)
            t = tk.Text(body, height=3, wrap="word")
            t.insert("1.0", getattr(appraisal, key) or "")
            t.grid(row=row, column=1, sticky="ew",
                     padx=4, pady=4)
            self.texts[key] = t
            row += 1

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        grade_raw = self.grade.get().strip()
        grade = (int(grade_raw) if grade_raw.isdigit() else None)
        try:
            self.result = data.record_end_year(
                self.appraisal.appraisal_id,
                reviewed_on=self.when.get().strip(),
                overall_grade=grade,
                pay_progression=self.pay.get() or None,
                upholding_standards=self.upholding.get(),
                strengths=self.texts["strengths"].get(
                    "1.0", "end").rstrip() or None,
                areas_to_develop=self.texts[
                    "areas_to_develop"].get(
                    "1.0", "end").rstrip() or None,
                cpd_needs=self.texts["cpd_needs"].get(
                    "1.0", "end").rstrip() or None,
                appraiser_comments=self.texts[
                    "appraiser_comments"].get(
                    "1.0", "end").rstrip() or None)
        except ValidationError as exc:
            messagebox.showerror("Appraisals", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


def _prompt_text(parent, title: str, *,
                  initial: str = "") -> str | None:
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("360x140")
    win.transient(parent); win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(value=initial)
    ttk.Entry(win, textvariable=var).pack(fill="x", padx=8)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = var.get().strip()
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="right", padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


def _prompt_choice(parent, title: str, options: list[str], *,
                    default: str | None = None) -> str | None:
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("320x140")
    win.transient(parent); win.after_idle(win.grab_set)
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


__all__ = ["open_appraisals_window"]
