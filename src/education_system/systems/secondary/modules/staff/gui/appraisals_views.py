"""Appraisals & CPD screen.

The old Appraisals window's "Appraisals & Objectives" tab is kept: Cycle,
Staff id and Status filters, Open only and Mid-year overdue, Apply, New
appraisal; columns ID, Staff, Cycle, Appraiser, Mid year, End year, Grade,
Pay, Status, Objectives; Edit, Set objectives date, Mid-year review,
End-year review, Close, Change status, Delete; and "Objectives for selected
appraisal" (Add, Edit, Change status, Delete). The appraisal form keeps Staff,
Appraiser, Self review completed, Upholding standards; the end-year form
Reviewed on, Overall grade, Pay progression, Upholding standards.

The old CPD window's tabs are kept: Activities (Type, Status, Title filters,
Upcoming only, Apply, New; Edit, Mark Completed, Change status, Delete) and
Records (Staff id, Status, Awaiting cert, Completed only, Apply, New; Edit,
Mark attended, Record evaluation, File certificate, Change status, Delete).
One Summary tab covers both.

Added: Start cycle, View, Export CSV; Request training, Approve, Decline,
Withdraw, CPD log, CPD budget on Records; new tabs Observations and
Statutory training (with the missing / overdue / due-soon list). Staff see
their own records; appraisers their appraisees'. Rules:
:mod:`modules.staff.domain.appraisals` and :mod:`appraisals_cpd`.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any

from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox
from education_system.systems.secondary.modules.staff.domain import appraisals as AP
from education_system.systems.secondary.modules.staff.domain import appraisals_cpd as CP
from education_system.systems.secondary.modules.staff.domain import staff_directory as SD
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
_ERRORS = W.ERRORS
_form = W.form_dialog
_TITLE = "Appraisals & CPD"


def _staff_kind(include_leavers: bool = False) -> tuple:
    return ("edit", ["", *SD.choices(include_leavers=include_leavers)])


def _getter(obj: Any):
    """g(key, default) - the field's value, or *default* when blank / no record."""
    def g(key: str, default: Any = "") -> Any:
        v = None if obj is None else getattr(obj, key)
        return default if v is None else v
    return g


def _diff(obj: Any, values: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for k, v in values.items():
        cur = getattr(obj, k, None)
        if str(v if v is not None else "") != str(cur if cur is not None else ""):
            out[k] = v
    return out


def _staff_id(text: str) -> int | None:
    m = SD.find(text) if text else None
    return m.staff_id if m else None


class AppraisalsPage:
    TABS = ("Appraisals & Objectives", "Observations", "Activities", "Records",
            "Statutory training", "Summary")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.editor = AP.is_editor(principal)
        self.appraiser = AP.is_appraiser(principal)
        activity_log.record("appraisals.view")
        ttk.Label(parent, text=_TITLE, font=("", 16, "bold")).pack(anchor="w")
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(
            anchor="w", pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._built: set[str] = set()
        start = state.get("tab") if state.get("tab") in self.TABS else self.TABS[0]
        self.book.select(self.TABS.index(start))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    # ── helpers ──────────────────────────────────────────────────────

    def _top(self):
        return self.parent.winfo_toplevel()

    def _err(self, title: str, e: Exception) -> None:
        messagebox.showerror(title, W.problems(e), parent=self._top())

    def _info(self, title: str, text: str) -> None:
        messagebox.showinfo(title, text, parent=self._top())

    def _button(self, bar, text: str, command, editor_only: bool = False,
                appraiser_only: bool = False) -> ttk.Button:
        b = ttk.Button(bar, text=text, command=command)
        if (editor_only and not self.editor) or (appraiser_only and not self.appraiser):
            b.state(["disabled"])
        b.pack(side="left", padx=2)
        return b

    def _run(self, title: str, fn, *args, **kw) -> Any:
        try:
            out = fn(*args, **kw)
        except _ERRORS as e:
            self._err(title, e)
            return None
        self._refresh_all()
        return out

    def _builders(self) -> dict:
        return {"Appraisals & Objectives": (self._build_appraisals, self.refresh_appraisals),
                "Observations": (self._build_observations, self.refresh_observations),
                "Activities": (self._build_activities, self.refresh_activities),
                "Records": (self._build_records, self.refresh_records),
                "Statutory training": (self._build_training, self.refresh_training),
                "Summary": (self._build_summary, self.refresh_summary)}

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        build, refresh = self._builders()[name]
        if name not in self._built:
            self._built.add(name)
            build(self.tabs[name])
        refresh()
        self._header()

    def _header(self) -> None:
        try:
            b = CP.budget()
            mine = len([a for a in AP.list_appraisals(actor=self.principal, open_only=True)])
        except _ERRORS:
            return
        budget = (f"CPD budget {b['year']}: £{b['used']:,.0f} used of £{b['available']:,.0f}"
                  if b["available"] is not None else f"No CPD budget set for {b['year']}")
        self.summary_var.set(f"Open appraisals you can see: {mine}    {budget}")

    def _refresh_all(self) -> None:
        for name, (_b, refresh) in self._builders().items():
            if name in self._built:
                refresh()
        self._header()

    def _filter_bar(self, tab, specs) -> dict[str, tk.Variable]:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        out: dict[str, tk.Variable] = {}
        for key, label, values, width in specs:
            if values == "check":
                var: tk.Variable = tk.BooleanVar(value=False)
                ttk.Checkbutton(bar, text=label, variable=var).pack(side="left", padx=4)
            else:
                ttk.Label(bar, text=label).pack(side="left")
                var = tk.StringVar(value="")
                if values is None:
                    ttk.Entry(bar, textvariable=var, width=width).pack(side="left", padx=(2, 6))
                else:
                    ttk.Combobox(bar, textvariable=var, values=values, state="readonly",
                                 width=width).pack(side="left", padx=(2, 6))
            out[key] = var
        out["_bar"] = bar  # type: ignore[assignment]
        return out

    # ── Appraisals & Objectives ──────────────────────────────────────

    def _build_appraisals(self, tab) -> None:
        f = self._filter_bar(tab, (
            ("cycle", "Cycle:", ["", *AP.list_cycles()], 9),
            ("staff", "Staff id:", None, 12), ("status", "Status:", ["", *AP.STATUSES], 18),
            ("open", "Open only", "check", 0), ("overdue", "Mid-year overdue", "check", 0)))
        self.ap_f = f
        bar = f["_bar"]
        self._button(bar, "Apply", self.refresh_appraisals)
        self._button(bar, "New appraisal", self.new_appraisal, True)
        self._button(bar, "Start cycle…", self.start_cycle, True)
        paned = ttk.PanedWindow(tab, orient="vertical")
        paned.pack(fill="both", expand=True)
        top, bottom = ttk.Frame(paned), ttk.Frame(paned)
        paned.add(top, weight=3)
        paned.add(bottom, weight=2)
        self.ap_tree = W.tree(top, [("id", "ID", 50), ("staff", "Staff", 170),
                                    ("cycle", "Cycle", 70), ("appraiser", "Appraiser", 150),
                                    ("mid", "Mid year", 90), ("end", "End year", 90),
                                    ("grade", "Grade", 60), ("pay", "Pay", 80),
                                    ("status", "Status", 130), ("objs", "Objectives", 80)],
                              height=9, stretch={"staff"}, tags=W.STANDARD_TAGS)
        self.ap_tree.bind("<<TreeviewSelect>>", lambda _e: self.refresh_objectives())
        self.ap_tree.bind("<Double-1>", lambda _e: self.view_appraisal())
        acts = ttk.Frame(top)
        acts.pack(fill="x", pady=(4, 0))
        for text, cmd in (("View", self.view_appraisal), ("Edit", self.edit_appraisal),
                          ("Set objectives date", self.set_objectives),
                          ("Mid-year review", self.mid_year), ("End-year review", self.end_year),
                          ("Close", self.close), ("Change status", self.ap_status),
                          ("Delete", self.delete_appraisal), ("Export CSV…",
                                                              lambda: self.export("appraisals"))):
            self._button(acts, text, cmd, text == "Delete",
                         text in ("Set objectives date", "Mid-year review", "End-year review",
                                  "Close", "Change status"))
        obar = ttk.Frame(bottom)
        obar.pack(fill="x", pady=(4, 4))
        ttk.Label(obar, text="Objectives for selected appraisal").pack(side="left")
        for text, cmd in (("Delete", self.delete_objective), ("Change status", self.obj_status),
                          ("Edit", self.edit_objective), ("Add", self.add_objective)):
            self._button(obar, text, cmd, appraiser_only=text != "Edit").pack_configure(
                side="right", padx=4)
        self.ob_tree = W.tree(bottom, [("id", "Id", 50), ("n", "N", 30), ("type", "Type", 150),
                                       ("title", "Title", 260), ("pct", "%", 50),
                                       ("weighting", "Weighting", 70),
                                       ("status", "Status", 110), ("reviewed", "Reviewed on", 90)],
                              height=5, stretch={"title"})
        self.ob_tree.bind("<Double-1>", lambda _e: self.edit_objective())

    def refresh_appraisals(self) -> None:
        f = self.ap_f
        try:
            rows = AP.list_appraisals(actor=self.principal, academic_year=f["cycle"].get() or None,
                                      staff_id=_staff_id(f["staff"].get()),
                                      status=f["status"].get() or None,
                                      open_only=f["open"].get(),
                                      mid_year_overdue=f["overdue"].get())
        except _ERRORS as e:
            self._err(_TITLE, e)
            return
        sel = self.ap_tree.selection()
        self.ap_tree.delete(*self.ap_tree.get_children())
        for a in rows:
            self.ap_tree.insert("", "end", iid=str(a.appraisal_id),
                                tags=("bad",) if a.mid_year_overdue else (
                                    ("muted",) if not a.is_open else ()),
                                values=(a.appraisal_id, a.staff_name, a.academic_year,
                                        a.appraiser_name or "", a.mid_year_review_on or "",
                                        a.end_year_review_on or "", a.overall_grade or "",
                                        a.pay_progression, a.status, a.objectives))
        if sel and self.ap_tree.exists(sel[0]):
            self.ap_tree.selection_set(sel[0])
        self.refresh_objectives()

    def _appraisal(self, title: str) -> AP.Appraisal | None:
        sel = self.ap_tree.selection()
        if not sel:
            self._info(title, "Select an appraisal first.")
            return None
        return AP.get_appraisal(int(sel[0]))

    def refresh_objectives(self) -> None:
        self.ob_tree.delete(*self.ob_tree.get_children())
        sel = self.ap_tree.selection()
        if not sel:
            return
        for o in AP.list_objectives(int(sel[0])):
            self.ob_tree.insert("", "end", iid=str(o.objective_id), values=(
                o.objective_id, o.objective_number, o.objective_type, o.title,
                o.progress_percent if o.progress_percent is not None else "",
                o.weighting if o.weighting is not None else "", o.status, o.reviewed_on or ""))

    def view_appraisal(self) -> None:
        a = self._appraisal("View")
        if a is None:
            return
        try:
            text = AP.appraisal_text(a.appraisal_id, actor=self.principal)
        except _ERRORS as e:
            self._err("View", e)
            return
        W.text_window(self.parent, f"Appraisal — {a.staff_name} {a.academic_year}", text,
                      size="760x600", save_name=f"appraisal-{a.appraisal_id}.txt")

    def new_appraisal(self) -> None:
        def save(v):
            AP.create_appraisal({k: x for k, x in v.items() if x not in ("", None)},
                                actor=self.principal)
            self._refresh_all()
        _form(self.parent, "New appraisal", [
            ("staff_id", "Staff*", "", _staff_kind()),
            ("academic_year", "Cycle (academic year)", AP.current_year(), None),
            ("appraiser_id", "Appraiser (blank = line manager)", "", _staff_kind()),
            ("job_role", "Job role", "", None),
            ("self_review_completed", "Self review completed", False, "check"),
            ("upholding_standards", "Upholding standards", True, "check"),
            ("notes", "Notes", "", "text")], save)

    def start_cycle(self) -> None:
        def save(v):
            r = AP.start_cycle(v["year"], actor=self.principal)
            self._refresh_all()
            msg = f"Opened {len(r['created'])} appraisal(s)."
            if r["no_appraiser"]:
                msg += "\n\nNo line manager, so no appraiser yet:\n  " + "\n  ".join(
                    r["no_appraiser"])
            self._info("Start cycle", msg)
        _form(self.parent, "Start the appraisal cycle", [
            ("year", "Academic year", AP.current_year(), None)], save,
            note="Opens an appraisal for every current member of staff who hasn't one; "
                 "the appraiser is their line manager.")

    def edit_appraisal(self) -> None:
        a = self._appraisal("Edit")
        if a is None:
            return
        appraisee_only = not AP.can_manage_appraisal(self.principal, a)
        keys = (("appraisee_comments", "Your comments", "text"),
                ("self_review_completed", "Self review completed", "check")) \
            if appraisee_only else (
            ("appraiser_id", "Appraiser", _staff_kind()), ("job_role", "Job role", None),
            ("self_review_completed", "Self review completed", "check"),
            ("upholding_standards", "Upholding standards", "check"),
            ("strengths", "Strengths", "text"), ("areas_to_develop", "Areas to develop", "text"),
            ("cpd_needs", "CPD needs", "text"),
            ("appraiser_comments", "Appraiser comments", "text"),
            ("appraisee_comments", "Appraisee comments", "text"), ("notes", "Notes", "text"))

        def initial(k):
            if k == "appraiser_id":
                m = SD.find(a.appraiser_id) if a.appraiser_id else None
                return m.label if m else ""
            return getattr(a, k)

        def save(v):
            ch = _diff(a, v)
            if "appraiser_id" in ch and ch["appraiser_id"] == initial("appraiser_id"):
                ch.pop("appraiser_id")
            AP.update_appraisal(a.appraisal_id, ch, actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"Edit — {a.staff_name} {a.academic_year}",
              [(k, label, initial(k) if initial(k) is not None else "", kind)
               for k, label, kind in keys], save)

    def set_objectives(self) -> None:
        a = self._appraisal("Set objectives date")
        if a is not None:
            _form(self.parent, "Objectives set", [("on", "Date (blank = today)", "", None)],
                  lambda v: (AP.set_objectives(a.appraisal_id, actor=self.principal,
                                               on=v["on"] or None), self._refresh_all()))

    def mid_year(self) -> None:
        a = self._appraisal("Mid-year review")
        if a is not None:
            _form(self.parent, "Mid-year review", [
                ("reviewed_on", "Reviewed on (blank = today)", "", None),
                ("notes", "Notes", a.mid_year_notes or "", "text")],
                lambda v: (AP.record_mid_year(a.appraisal_id, actor=self.principal,
                                              reviewed_on=v["reviewed_on"] or None,
                                              notes=v["notes"]), self._refresh_all()))

    def end_year(self) -> None:
        a = self._appraisal("End-year review")
        if a is None:
            return

        def save(v):
            AP.record_end_year(
                a.appraisal_id, actor=self.principal, reviewed_on=v["reviewed_on"] or None,
                overall_grade=v["overall_grade"] or None, pay_progression=v["pay_progression"],
                upholding_standards=v["upholding_standards"], outcome=v["outcome"] or None,
                strengths=v["strengths"], areas_to_develop=v["areas_to_develop"],
                cpd_needs=v["cpd_needs"], appraiser_comments=v["appraiser_comments"],
                pay_notes=v["pay_notes"])
            self._refresh_all()
        grades = ["", *(f"{g} {AP.GRADE_LABELS[g]}" for g in AP.GRADES)]
        _form(self.parent, f"End-year review — {a.staff_name}", [
            ("reviewed_on", "Reviewed on (blank = today)", "", None),
            ("overall_grade", "Overall grade", next((g for g in grades if a.overall_grade and
                                                     g.startswith(str(a.overall_grade))), ""),
             grades),
            ("outcome", "Outcome*", a.outcome or "", ["", *AP.OUTCOMES]),
            ("pay_progression", "Pay progression*", a.pay_progression, AP.PAY_PROGRESSION),
            ("pay_notes", "Pay recommendation notes", a.pay_notes or "", "text"),
            ("upholding_standards", "Upholding standards", a.upholding_standards, "check"),
            ("strengths", "Strengths", a.strengths or "", "text"),
            ("areas_to_develop", "Areas to develop", a.areas_to_develop or "", "text"),
            ("cpd_needs", "CPD needs", a.cpd_needs or "", "text"),
            ("appraiser_comments", "Appraiser comments", a.appraiser_comments or "", "text")],
            save)

    def close(self) -> None:
        a = self._appraisal("Close")
        if a is not None and messagebox.askyesno("Close", f"Close {a.staff_name}'s appraisal?",
                                                 parent=self._top()):
            self._run("Close", AP.close_appraisal, a.appraisal_id, actor=self.principal)

    def ap_status(self) -> None:
        a = self._appraisal("Change status")
        if a is not None:
            _form(self.parent, "Change status", [("status", "Status", a.status, AP.STATUSES)],
                  lambda v: (AP.set_appraisal_status(a.appraisal_id, v["status"],
                                                     actor=self.principal),
                             self._refresh_all()))

    def delete_appraisal(self) -> None:
        a = self._appraisal("Delete")
        if a is not None and messagebox.askyesno(
                "Delete", f"Delete appraisal #{a.appraisal_id} and its objectives?",
                parent=self._top()):
            self._run("Delete", AP.delete_appraisal, a.appraisal_id, actor=self.principal)

    def _objective_fields(self, o: AP.Objective | None, own: bool) -> list:
        g = _getter(o)
        if own:
            return [("progress_notes", "Progress notes", g("progress_notes"), "text"),
                    ("progress_percent", "Progress %", g("progress_percent"), None)]
        return [("objective_type", "Type", g("objective_type", AP.DEFAULT_OBJECTIVE_TYPE),
                 AP.OBJECTIVE_TYPES), ("title", "Title*", g("title"), None),
                ("description", "Description", g("description"), "text"),
                ("target_metric", "Target", g("target_metric"), None),
                ("success_criteria", "Success criteria", g("success_criteria"), "text"),
                ("progress_notes", "Progress notes", g("progress_notes"), "text"),
                ("progress_percent", "Progress %", g("progress_percent"), None),
                ("mid_year_progress", "Mid-year progress", g("mid_year_progress"), "text"),
                ("end_year_evidence", "End-year evidence", g("end_year_evidence"), "text"),
                ("weighting", "Weighting", g("weighting"), None),
                ("notes", "Notes", g("notes"), None)]

    def _objective(self, title: str) -> AP.Objective | None:
        sel = self.ob_tree.selection()
        if not sel:
            self._info(title, "Select an objective first.")
            return None
        return AP.get_objective(int(sel[0]))

    def add_objective(self) -> None:
        a = self._appraisal("Add objective")
        if a is not None:
            _form(self.parent, "Add objective", self._objective_fields(None, False),
                  lambda v: (AP.add_objective(a.appraisal_id, v, actor=self.principal),
                             self._refresh_all()))

    def edit_objective(self) -> None:
        o = self._objective("Edit objective")
        if o is None:
            return
        own = not AP.can_manage_appraisal(self.principal, AP.get_appraisal(o.appraisal_id))
        _form(self.parent, f"Objective {o.objective_number}", self._objective_fields(o, own),
              lambda v: (AP.update_objective(o.objective_id, _diff(o, v), actor=self.principal),
                         self._refresh_all()))

    def obj_status(self) -> None:
        o = self._objective("Change status")
        if o is not None:
            _form(self.parent, "Objective status", [
                ("status", "Status", o.status, AP.OBJECTIVE_STATUSES),
                ("reviewed_on", "Reviewed on (blank = today)", "", None)],
                lambda v: (AP.set_objective_status(o.objective_id, v["status"],
                                                   actor=self.principal,
                                                   reviewed_on=v["reviewed_on"] or None),
                           self._refresh_all()))

    def delete_objective(self) -> None:
        o = self._objective("Delete objective")
        if o is not None and messagebox.askyesno("Delete objective", f"Delete '{o.title}'?",
                                                 parent=self._top()):
            self._run("Delete objective", AP.delete_objective, o.objective_id,
                      actor=self.principal)

    # ── Observations ─────────────────────────────────────────────────

    def _build_observations(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        for text, cmd in (("New observation…", self.new_observation), ("View", self.view_obs),
                          ("Edit…", self.edit_obs), ("My response…", self.respond_obs),
                          ("Delete", self.delete_obs)):
            self._button(bar, text, cmd, text == "Delete",
                         text in ("New observation…", "Edit…"))
        self.obs_tree = W.tree(tab, [("date", "Date", 90), ("staff", "Teacher", 170),
                                     ("type", "Type", 120), ("class", "Class", 80),
                                     ("observer", "Observer", 150),
                                     ("judgement", "Judgement", 120),
                                     ("feedback", "Feedback", 90),
                                     ("appraisal", "Appraisal", 70)], height=16,
                               stretch={"staff"})
        self.obs_tree.bind("<Double-1>", lambda _e: self.view_obs())

    def refresh_observations(self) -> None:
        self.obs_tree.delete(*self.obs_tree.get_children())
        for o in AP.list_observations(actor=self.principal):
            self.obs_tree.insert("", "end", iid=str(o.observation_id), values=(
                o.observed_on, o.staff_name, o.observation_type, o.class_observed or "",
                o.observer_name or "", o.judgement or "", o.feedback_given_on or "",
                f"#{o.appraisal_id}" if o.appraisal_id else ""))

    def _obs(self, title: str) -> AP.Observation | None:
        sel = self.obs_tree.selection()
        if not sel:
            self._info(title, "Select an observation first.")
            return None
        return AP.get_observation(int(sel[0]))

    def _obs_fields(self, o: AP.Observation | None) -> list:
        g = _getter(o)
        return [("observed_on", "Date (blank = today)", g("observed_on"), None),
                ("observation_type", "Type", g("observation_type", "Formal"),
                 AP.OBSERVATION_TYPES),
                ("class_observed", "Class / group", g("class_observed"), None),
                ("focus", "Focus", g("focus"), "text"), ("strengths", "Strengths",
                                                         g("strengths"), "text"),
                ("development_points", "Development points", g("development_points"), "text"),
                ("judgement", "Judgement", g("judgement"), ["", *AP.JUDGEMENTS]),
                ("feedback_given_on", "Feedback given on", g("feedback_given_on"), None),
                ("notes", "Notes", g("notes"), None)]

    def new_observation(self) -> None:
        def save(v):
            AP.add_observation(v, actor=self.principal)
            self._refresh_all()
        _form(self.parent, "New lesson observation",
              [("staff_id", "Teacher observed*", "", _staff_kind()),
               ("observer_id", "Observer (blank = you)", "", _staff_kind())]
              + self._obs_fields(None), save,
              note="Linked to the teacher's appraisal for that year. Their appraiser or the "
                   "appraisal lead records observations.")

    def view_obs(self) -> None:
        o = self._obs("View")
        if o is None:
            return
        text = "\n".join(f"{label}: {v}" for label, v in (
            ("Teacher", o.staff_name), ("Date", o.observed_on), ("Type", o.observation_type),
            ("Class", o.class_observed), ("Observer", o.observer_name), ("Focus", o.focus),
            ("Strengths", o.strengths), ("Development points", o.development_points),
            ("Judgement", o.judgement), ("Feedback given", o.feedback_given_on),
            ("Teacher's response", o.staff_response), ("Notes", o.notes)) if v)
        W.text_window(self.parent, f"Observation — {o.staff_name}", text)

    def edit_obs(self) -> None:
        o = self._obs("Edit")
        if o is not None:
            _form(self.parent, "Edit observation", self._obs_fields(o),
                  lambda v: (AP.update_observation(o.observation_id, _diff(o, v),
                                                   actor=self.principal), self._refresh_all()))

    def respond_obs(self) -> None:
        o = self._obs("Response")
        if o is not None:
            _form(self.parent, "Your response", [
                ("staff_response", "Response", o.staff_response or "", "text")],
                lambda v: (AP.update_observation(o.observation_id, v, actor=self.principal),
                           self._refresh_all()))

    def delete_obs(self) -> None:
        o = self._obs("Delete")
        if o is not None and messagebox.askyesno("Delete", "Delete this observation?",
                                                 parent=self._top()):
            self._run("Delete", AP.delete_observation, o.observation_id, actor=self.principal)

    # ── Activities (the old CPD catalogue) ───────────────────────────

    def _build_activities(self, tab) -> None:
        f = self._filter_bar(tab, (
            ("type", "Type:", ["", *AP.ACTIVITY_TYPES], 18),
            ("status", "Status:", ["", *AP.ACTIVITY_STATUSES], 14),
            ("title", "Title:", None, 16), ("upcoming", "Upcoming only", "check", 0)))
        self.ac_f = f
        self._button(f["_bar"], "Apply", self.refresh_activities)
        self._button(f["_bar"], "New", self.new_activity, True)
        self.ac_tree = W.tree(tab, [("id", "Id", 50), ("date", "Date", 90), ("type", "Type", 130),
                                    ("title", "Title", 240), ("provider", "Provider", 130),
                                    ("hours", "Hours", 50), ("cost", "Cost", 70),
                                    ("cert", "Cert", 40), ("records", "Records", 60),
                                    ("status", "Status", 110)], height=14, stretch={"title"})
        self.ac_tree.bind("<Double-1>", lambda _e: self.edit_activity())
        acts = ttk.Frame(tab)
        acts.pack(fill="x", pady=(4, 0))
        for text, cmd in (("Edit", self.edit_activity), ("Mark Completed", self.complete_activity),
                          ("Change status", self.activity_status),
                          ("Delete", self.delete_activity)):
            self._button(acts, text, cmd, True)
        self._button(acts, "Refresh", self.refresh_activities)
        self._button(acts, "Book staff…", self.book_staff, True)

    def refresh_activities(self) -> None:
        f = self.ac_f
        self.ac_tree.delete(*self.ac_tree.get_children())
        for a in CP.list_activities(activity_type=f["type"].get() or None,
                                    status=f["status"].get() or None, title=f["title"].get(),
                                    upcoming_only=f["upcoming"].get()):
            self.ac_tree.insert("", "end", iid=str(a.activity_id), values=(
                a.activity_id, a.activity_date, a.activity_type, a.title, a.provider or "",
                a.hours if a.hours is not None else "",
                f"£{a.cost:,.2f}" if a.cost is not None else "", "yes" if a.certificated else "",
                a.records, a.status))

    def _activity(self, title: str) -> AP.Activity | None:
        sel = self.ac_tree.selection()
        if not sel:
            self._info(title, "Select an activity first.")
            return None
        return CP.get_activity(int(sel[0]))

    def _activity_fields(self, a: AP.Activity | None) -> list:
        g = _getter(a)
        return [("title", "Title*", g("title"), None), ("provider", "Provider", g("provider"),
                                                         None),
                ("activity_type", "Type", g("activity_type", AP.DEFAULT_ACTIVITY_TYPE),
                 AP.ACTIVITY_TYPES),
                ("activity_date", "Date*", g("activity_date"), None),
                ("end_date", "End date", g("end_date"), None), ("hours", "Hours", g("hours"), None),
                ("cost", "Cost (£)", g("cost"), None),
                ("certificated", "Certificated", g("certificated", False), "check"),
                ("accreditor", "Accreditor", g("accreditor"), None),
                ("location", "Location", g("location"), None),
                ("capacity", "Capacity", g("capacity"), None),
                ("organiser", "Organiser", g("organiser"), None),
                ("description", "Description", g("description"), "text"),
                ("outcomes", "Outcomes", g("outcomes"), "text"),
                ("status", "Status", g("status", AP.DEFAULT_ACTIVITY_STATUS),
                 AP.ACTIVITY_STATUSES), ("notes", "Notes", g("notes"), None)]

    def new_activity(self) -> None:
        _form(self.parent, "New CPD activity", self._activity_fields(None),
              lambda v: (CP.create_activity(v, actor=self.principal), self._refresh_all()))

    def edit_activity(self) -> None:
        a = self._activity("Edit")
        if a is not None and self.editor:
            _form(self.parent, f"Edit — {a.title}", self._activity_fields(a),
                  lambda v: (CP.update_activity(a.activity_id, _diff(a, v),
                                                actor=self.principal), self._refresh_all()))

    def complete_activity(self) -> None:
        a = self._activity("Mark Completed")
        if a is not None:
            self._run("Mark Completed", CP.mark_activity_completed, a.activity_id,
                      actor=self.principal)

    def activity_status(self) -> None:
        a = self._activity("Change status")
        if a is not None:
            _form(self.parent, "Change status", [("status", "Status", a.status,
                                                  AP.ACTIVITY_STATUSES)],
                  lambda v: (CP.set_activity_status(a.activity_id, v["status"],
                                                    actor=self.principal), self._refresh_all()))

    def delete_activity(self) -> None:
        a = self._activity("Delete")
        if a is not None and messagebox.askyesno(
                "Delete", f"Delete '{a.title}'? Its {a.records} record(s) are kept.",
                parent=self._top()):
            self._run("Delete", CP.delete_activity, a.activity_id, actor=self.principal)

    def book_staff(self) -> None:
        a = self._activity("Book staff")
        if a is not None:
            _form(self.parent, f"Book onto {a.title}", [
                ("staff_id", "Staff*", "", _staff_kind()), ("notes", "Notes", "", None)],
                lambda v: (CP.create_record({**v, "activity_id": a.activity_id},
                                            actor=self.principal), self._refresh_all()))

    # ── Records: requests, bookings, attendance ──────────────────────

    def _build_records(self, tab) -> None:
        f = self._filter_bar(tab, (
            ("staff", "Staff id:", None, 12), ("status", "Status:", ["", *AP.RECORD_STATUSES], 11),
            ("cert", "Awaiting cert", "check", 0), ("done", "Completed only", "check", 0)))
        self.rc_f = f
        self._button(f["_bar"], "Apply", self.refresh_records)
        self._button(f["_bar"], "New", self.new_record, True)
        self._button(f["_bar"], "Request training…", self.request)
        self.rc_budget = tk.StringVar()
        ttk.Label(tab, textvariable=self.rc_budget, foreground="#555").pack(anchor="w")
        self.rc_tree = W.tree(tab, [("id", "Id", 50), ("staff", "Staff", 160),
                                    ("activity", "Training", 220), ("booked", "Dates", 150),
                                    ("cost", "Cost", 70), ("cover", "Cover", 50),
                                    ("attended", "Attended", 90), ("hours", "Hours", 50),
                                    ("rating", "Rating", 50), ("cert", "Cert", 40),
                                    ("status", "Status", 90)], height=12, stretch={"activity"},
                              tags=W.STANDARD_TAGS)
        acts = ttk.Frame(tab)
        acts.pack(fill="x", pady=(4, 0))
        for text, cmd, ed in (("Edit", self.edit_record, False),
                              ("Mark attended", self.attended, False),
                              ("Record evaluation", self.evaluate, False),
                              ("File certificate", self.certificate, False),
                              ("Change status", self.record_status, True),
                              ("Delete", self.delete_record, True)):
            self._button(acts, text, cmd, ed)
        acts2 = ttk.Frame(tab)
        acts2.pack(fill="x", pady=(4, 0))
        for text, cmd, ed in (("Approve…", lambda: self.decide(True), True),
                              ("Decline…", lambda: self.decide(False), True),
                              ("Withdraw", self.withdraw, False), ("CPD log", self.cpd_log, False),
                              ("CPD budget…", self.set_budget, True),
                              ("Export CSV…", lambda: self.export("cpd"), False)):
            self._button(acts2, text, cmd, ed)

    def refresh_records(self) -> None:
        f = self.rc_f
        b = CP.budget()
        self.rc_budget.set(
            f"CPD budget {b['year']}: " + (
                f"£{b['available']:,.2f} available, £{b['used']:,.2f} used, £{b['remaining']:,.2f}"
                f" left, £{b['requested']:,.2f} waiting for a decision"
                if b["available"] is not None else
                f"not set (£{b['used']:,.2f} approved so far)"))
        self.rc_tree.delete(*self.rc_tree.get_children())
        try:
            rows = CP.list_records(actor=self.principal, staff_id=_staff_id(f["staff"].get()),
                                   status=f["status"].get() or None,
                                   awaiting_cert=f["cert"].get(),
                                   completed_only=f["done"].get())
        except _ERRORS as e:
            self._err("Records", e)
            return
        for r in rows:
            tag = ("warn",) if r.status == "Requested" else (
                ("muted",) if r.status in ("Declined", "Cancelled", "No-Show") else ())
            dates = r.start_date or ""
            if r.end_date and r.end_date != r.start_date:
                dates += f" to {r.end_date}"
            self.rc_tree.insert("", "end", iid=str(r.record_id), tags=tag, values=(
                r.record_id, r.staff_name, r.title, dates,
                f"£{r.cost:,.2f}" if r.cost is not None else "", "yes" if r.cover_needed else "",
                r.attended_on or "", r.hours_completed if r.hours_completed is not None else "",
                r.evaluation_rating or "", "yes" if r.certificate_filed else "", r.status))

    def _record(self, title: str) -> AP.Record | None:
        sel = self.rc_tree.selection()
        if not sel:
            self._info(title, "Select a record first.")
            return None
        return CP.get_record(int(sel[0]))

    def _request_fields(self, r: AP.Record | None) -> list:
        g = _getter(r)
        acts = [f"{a.activity_id} {a.title}" for a in CP.list_activities(upcoming_only=True)]
        return [("activity_id", "From the catalogue (optional)", g("activity_id"),
                 ("edit", ["", *acts])),
                ("title", "Title", g("title"), None), ("provider", "Provider", g("provider"),
                                                       None),
                ("start_date", "Start date", g("start_date"), None),
                ("end_date", "End date", g("end_date"), None), ("cost", "Cost (£)", g("cost"),
                                                                None),
                ("cover_needed", "Cover needed", g("cover_needed", False), "check"),
                ("cover_days", "Cover days", g("cover_days"), None),
                ("reason", "Why / what for", g("reason"), "text")]

    def request(self) -> None:
        fields = self._request_fields(None)
        if self.editor:
            fields = [("staff_id", "For (blank = you)", "", _staff_kind())] + fields
        _form(self.parent, "Request training", fields,
              lambda v: (CP.request_cpd(v, actor=self.principal), self._refresh_all()),
              note="The CPD lead approves or declines it against this year's budget.")

    def new_record(self) -> None:
        _form(self.parent, "New CPD record", [("staff_id", "Staff*", "", _staff_kind(True))]
              + self._request_fields(None)
              + [("status", "Status", AP.DEFAULT_RECORD_STATUS, AP.RECORD_STATUSES),
                 ("notes", "Notes", "", None)],
              lambda v: (CP.create_record(v, actor=self.principal), self._refresh_all()))

    def edit_record(self) -> None:
        r = self._record("Edit")
        if r is None:
            return
        fields = self._request_fields(r)
        if self.editor:
            fields += [("cost_to_staff", "Cost to staff (£)", r.cost_to_staff or "", None),
                       ("certificate_ref", "Certificate ref", r.certificate_ref or "", None),
                       ("notes", "Notes", r.notes or "", None)]
        _form(self.parent, f"Edit — {r.title}", fields,
              lambda v: (CP.update_record(r.record_id, _diff(r, v), actor=self.principal),
                         self._refresh_all()))

    def decide(self, approve: bool) -> None:
        r = self._record("Approve" if approve else "Decline")
        if r is None:
            return

        def save(v):
            try:
                CP.decide(r.record_id, approve, actor=self.principal, note=v["note"])
            except AP.ValidationError as e:
                if not (approve and "over" in str(e) and messagebox.askyesno(
                        "Over budget", f"{e}\n\nApprove anyway?", parent=self._top())):
                    raise
                CP.decide(r.record_id, True, actor=self.principal, note=v["note"],
                          allow_over_budget=True)
            self._refresh_all()
        _form(self.parent, f"{'Approve' if approve else 'Decline'} — {r.title} "
                           f"({r.staff_name})",
              [("note", "Note" + ("" if approve else " (why)*"), "", "text")], save,
              note=f"Cost £{r.cost or 0:,.2f}" + (", cover needed" if r.cover_needed else ""))

    def withdraw(self) -> None:
        r = self._record("Withdraw")
        if r is not None and messagebox.askyesno("Withdraw", f"Withdraw '{r.title}'?",
                                                 parent=self._top()):
            self._run("Withdraw", CP.withdraw_request, r.record_id, actor=self.principal)

    def attended(self) -> None:
        r = self._record("Mark attended")
        if r is not None:
            _form(self.parent, "Mark attended", [
                ("attended_on", "Attended on (blank = today)", "", None),
                ("hours", "Hours completed", r.hours_completed or "", None)],
                lambda v: (CP.mark_attended(r.record_id, actor=self.principal,
                                            attended_on=v["attended_on"] or None,
                                            hours_completed=v["hours"]), self._refresh_all()))

    def evaluate(self) -> None:
        r = self._record("Record evaluation")
        if r is not None:
            _form(self.parent, "Record evaluation", [
                ("rating", "Rating (1-5)", r.evaluation_rating or "",
                 [f"{n} {AP.RATING_LABELS[n]}" for n in AP.RATINGS]),
                ("notes", "Notes", r.evaluation_notes or "", "text"),
                ("impact", "Impact on practice", r.impact_on_practice or "", "text")],
                lambda v: (CP.record_evaluation(r.record_id, actor=self.principal,
                                                rating=v["rating"], notes=v["notes"],
                                                impact=v["impact"]), self._refresh_all()))

    def certificate(self) -> None:
        r = self._record("File certificate")
        if r is not None:
            _form(self.parent, "File certificate", [
                ("ref", "Certificate", r.certificate_ref or "", None)],
                lambda v: (CP.file_certificate(r.record_id, actor=self.principal, ref=v["ref"]),
                           self._refresh_all()))

    def record_status(self) -> None:
        r = self._record("Change status")
        if r is not None:
            _form(self.parent, "Change status", [("status", "Status", r.status,
                                                  AP.RECORD_STATUSES)],
                  lambda v: (CP.set_record_status(r.record_id, v["status"],
                                                  actor=self.principal), self._refresh_all()))

    def delete_record(self) -> None:
        r = self._record("Delete")
        if r is not None and messagebox.askyesno("Delete", f"Delete record #{r.record_id}?",
                                                 parent=self._top()):
            self._run("Delete", CP.delete_record, r.record_id, actor=self.principal)

    def cpd_log(self) -> None:
        r = self._record("CPD log")
        me = SD.me(self.principal)
        sid = r.staff_id if r else (me.staff_id if me else None)
        if sid is None:
            return
        try:
            log = CP.cpd_log(sid, actor=self.principal)
        except _ERRORS as e:
            self._err("CPD log", e)
            return
        lines = [f"CPD log — {log['member'].full_name}: {log['hours']:g} hour(s)", ""]
        for y, d in sorted(log["by_year"].items(), reverse=True):
            lines.append(f"{y}: {d['courses']} course(s), {d['hours']:g} h, £{d['cost']:,.2f}")
        lines.append("")
        for x in log["records"]:
            lines.append(f"  {x.attended_on or x.start_date or ''}  {x.title}"
                         + (f" ({x.provider})" if x.provider else "")
                         + (f" - rated {x.evaluation_rating}" if x.evaluation_rating else ""))
        W.text_window(self.parent, "CPD log", "\n".join(lines),
                      save_name=f"cpd-log-{log['member'].staff_code}.txt")

    def set_budget(self) -> None:
        b = CP.budget()
        _form(self.parent, "CPD budget", [
            ("year", "Academic year", b["year"], None),
            ("amount", "Budget (£)", b["available"] if b["available"] is not None else "", None)],
            lambda v: (CP.set_budget(v["year"], v["amount"], actor=self.principal),
                       self._refresh_all()))

    # ── Statutory training ───────────────────────────────────────────

    def _build_training(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        for text, cmd, ed in (("Record training…", self.add_training, True),
                              ("Edit…", self.edit_training, True),
                              ("Delete", self.delete_training, True),
                              ("Export CSV…", lambda: self.export("training"), False)):
            self._button(bar, text, cmd, ed)
        ttk.Label(tab, text="Missing, overdue or due within 60 days").pack(anchor="w")
        self.due_tree = W.tree(tab, [("state", "State", 80), ("staff", "Staff", 180),
                                     ("type", "Training", 180), ("last", "Last done", 100),
                                     ("expires", "Expires", 100)], height=7, stretch={"staff"},
                               tags=W.STANDARD_TAGS)
        ttk.Label(tab, text="Training records").pack(anchor="w", pady=(6, 0))
        self.tr_tree = W.tree(tab, [("staff", "Staff", 180), ("type", "Training", 180),
                                    ("done", "Completed", 100), ("expires", "Expires", 100),
                                    ("provider", "Provider", 150), ("cert", "Certificate", 100)],
                              height=9, stretch={"staff"}, tags=W.STANDARD_TAGS)

    def refresh_training(self) -> None:
        self.due_tree.delete(*self.due_tree.get_children())
        for d in CP.training_due(actor=self.principal):
            self.due_tree.insert("", "end", tags=("warn",) if d["state"] == "Due soon"
                                 else ("bad",), values=(
                d["state"], d["staff"], d["training_type"], d["last_completed"] or "",
                d["expires_on"] or ""))
        self.tr_tree.delete(*self.tr_tree.get_children())
        for t in CP.list_training(actor=self.principal):
            self.tr_tree.insert("", "end", iid=str(t.training_id),
                                tags=("bad",) if t.expired else (), values=(
                t.staff_name, t.training_type, t.completed_on, t.expires_on or "",
                t.provider or "", t.certificate_ref or ""))

    def _training_fields(self, t: AP.Training | None) -> list:
        g = _getter(t)
        return [("training_type", "Training*", g("training_type"), list(AP.TRAINING_TYPES)),
                ("completed_on", "Completed on*", g("completed_on"), None),
                ("expires_on", "Expires on (blank = worked out)", "" if t is None
                 else g("expires_on"), None),
                ("provider", "Provider", g("provider"), None),
                ("certificate_ref", "Certificate", g("certificate_ref"), None),
                ("notes", "Notes", g("notes"), None)]

    def add_training(self) -> None:
        _form(self.parent, "Record training",
              [("staff_id", "Staff*", "", _staff_kind())] + self._training_fields(None),
              lambda v: (CP.add_training(v, actor=self.principal), self._refresh_all()),
              note="Safeguarding / KCSIE lasts a year, Prevent two, first aid and fire marshal "
                   "three.")

    def _training(self, title: str) -> AP.Training | None:
        sel = self.tr_tree.selection()
        if not sel:
            self._info(title, "Select a training record first.")
            return None
        return CP.get_training(int(sel[0]))

    def edit_training(self) -> None:
        t = self._training("Edit")
        if t is not None:
            _form(self.parent, "Edit training", self._training_fields(t),
                  lambda v: (CP.update_training(t.training_id, _diff(t, v),
                                                actor=self.principal), self._refresh_all()))

    def delete_training(self) -> None:
        t = self._training("Delete")
        if t is not None and messagebox.askyesno("Delete", "Delete this training record?",
                                                 parent=self._top()):
            self._run("Delete", CP.delete_training, t.training_id, actor=self.principal)

    # ── Summary and export ───────────────────────────────────────────

    def _build_summary(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Button(bar, text="Refresh", command=self.refresh_summary).pack(side="left")
        self.sum_text = tk.Text(tab, wrap="word", font=("TkFixedFont", 10))
        self.sum_text.pack(fill="both", expand=True)

    def refresh_summary(self) -> None:
        try:
            s = CP.summary(actor=self.principal)
        except _ERRORS as e:
            self._err("Summary", e)
            return
        b = s["budget"]
        lines = [f"Appraisals {s['year']}: {s['appraisals']} ({s['open']} open, "
                 f"{s['completed']} completed, {s['mid_year_overdue']} mid-year overdue, "
                 f"{s['no_appraiser']} without an appraiser)"]
        for title, key in (("By status", "by_status"), ("By grade", "by_grade"),
                           ("Pay progression", "pay")):
            if s[key]:
                lines += ["", f"{title}:"] + [f"  {k:<22} {n}" for k, n in s[key].items()]
        lines += ["", f"CPD: {s['activities']} activities ({s['upcoming']} upcoming), "
                      f"{s['records']} records this year, {s['requests']} waiting for a "
                      f"decision, {s['attended']} attended ({s['hours']:g} h), "
                      f"{s['awaiting_cert']} awaiting a certificate, average rating "
                      f"{s['average_rating']}",
                  "Budget: " + (f"£{b['used']:,.2f} used of £{b['available']:,.2f}"
                                if b["available"] is not None else "not set"),
                  f"Statutory training missing or overdue: {s['training_overdue']}"]
        self.sum_text.configure(state="normal")
        self.sum_text.delete("1.0", "end")
        self.sum_text.insert("1.0", "\n".join(lines))
        self.sum_text.configure(state="disabled")

    def export(self, what: str) -> None:
        path = filedialog.asksaveasfilename(parent=self._top(), defaultextension=".csv",
                                            initialfile=f"{what}.csv",
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            n = CP.export_csv(path, what, actor=self.principal)
        except (*_ERRORS, OSError) as e:
            self._err("Export CSV", e)
            return
        self._info("Export CSV", f"Exported {n} row(s).")


def draw_appraisals(parent: ttk.Frame, *, principal: Principal, state: dict) -> AppraisalsPage:
    return AppraisalsPage(parent, principal=principal, state=state)
