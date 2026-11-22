"""Exam Results screen.

The old "Results Day" window is kept as the Results tab: the Year and Status
filters with Apply, Record for entry, Edit, Pupil sheet, Summary, Pending,
Delete and Refresh; the columns ID, Entry, Pupil, Yr, Subj, Board, Tier,
Grade, Marks, UMS, Status; the old result dialog (Final grade, Marks
awarded, UMS, Result date, Status, Remark outcome, Notes) and the Pupil
sheet and Pending windows.

Added: the exam series picker and embargo line; a Grade entry tab (a whole
subject at once); Reviews (reviews of marking with consent, outcomes and
refunds); Analysis (headlines, subjects against mocks and targets, pupils
against target); and Release & slips (results file import, release, export,
results slips by e-mail, history). Rules live in :mod:`modules.examinations.domain.exam_results`.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable

from education_system.platform.delivery.gui.parented_dialogs import (
    filedialog,
    messagebox,
)
from education_system.systems.secondary.modules.examinations.domain import exam_entries as EE
from education_system.systems.secondary.modules.examinations.domain import exam_results as ER
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
ALL = ""
TITLE = "Results Day"
_ERRORS = (ER.ValidationError, ER.PermissionDenied, ER.NotFound)
ROW_BG = {"Pending": "#f4f4f4", "Final": "#ffffff", "Remarked": "#fff6d6",
          "Adjusted": "#e8f0fe", "Withheld": "#fde2e2", "good": "#e7f6ea", "bad": "#fde2e2"}


_problems = W.problems


def _tree(parent, columns, height: int = 14) -> ttk.Treeview:
    return W.tree(parent, columns, height=height, stretch={"name", "detail"}, tags=ROW_BG,
                  minwidth=0)


def _dialog(owner: tk.Misc, title: str, size: str) -> tuple[tk.Toplevel, ttk.Frame]:
    return W.dialog(owner, title, size=size)


def _text_window(owner, title: str, text: str) -> None:
    W.text_window(owner, title, text, size="760x480")


def _form(frm: ttk.Frame, rows: list[tuple[str, tk.Widget]]) -> None:
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w", pady=2, padx=(0, 8))
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)


def _sixth_form_text(sf: dict) -> str:
    """What happened to the pupils' sixth form applications after a release."""
    if sf.get("failed"):
        return ("Results released. They couldn't be passed on to the sixth form just now - "
                "use Send exam results in Move to Sixth Form.")
    lines = [f"Results released and passed on to {len(sf['sent'])} sixth form "
             "application(s)."]
    if sf.get("skipped"):
        lines.append("Not passed on: " + "; ".join(f"{k} ({v})"
                                                    for k, v in sf["skipped"].items()))
    return "\n".join(lines)


def _pct(v) -> str:
    return "-" if v is None else f"{v:g}%"


def _gap(v) -> str:
    return "-" if v is None else f"{v:+.2f}"


# ── Old dialogs and windows ──────────────────────────────────────────

def result_dialog(owner, *, principal: Principal, entry: EE.ExamEntry,
                  result: ER.ExamResult | None = None,
                  after: Callable[[], None] | None = None) -> None:
    """The old result dialog (record for an entry, or edit)."""
    win, frm = _dialog(owner, f"Result - {entry.pupil_name} {entry.subject_code}", "500x470")
    ttk.Label(frm, text=f"Entry #{entry.entry_id}: {entry.pupil_name} · {entry.subject_name} "
                        f"{entry.exam_board} {entry.entry_code}"
                        + ("" if entry.tier == "N/A" else f" ({entry.tier})"),
              foreground="#555", wraplength=460).grid(row=0, column=0, columnspan=2,
                                                      sticky="w", pady=(0, 6))
    r = result
    v = {"final_grade": tk.StringVar(value=(r.final_grade or "") if r else ""),
         "marks_awarded": tk.StringVar(value=EE._num(r.marks_awarded) if r else ""),
         "max_marks": tk.StringVar(value=EE._num(r.max_marks) if r else ""),
         "ums": tk.StringVar(value=EE._num(r.ums) if r else ""),
         "result_date": tk.StringVar(value=r.result_date if r else ER._today().isoformat()),
         "status": tk.StringVar(value=r.status if r else "Final"),
         "remark_outcome": tk.StringVar(value=(r.remark_outcome or "") if r else "")}
    grades = list(ER.GCSE_GRADES) if entry.qualification in ER.GCSE_QUALS else []
    sub = ttk.Frame(frm)
    sub.grid(row=1, column=0, columnspan=2, sticky="ew")
    _form(sub, [
        ("Final grade:", ttk.Combobox(sub, textvariable=v["final_grade"], values=grades,
                                      width=8)),
        ("Marks awarded:", ttk.Entry(sub, textvariable=v["marks_awarded"], width=10)),
        ("Out of:", ttk.Entry(sub, textvariable=v["max_marks"], width=10)),
        ("UMS:", ttk.Entry(sub, textvariable=v["ums"], width=10)),
        ("Result date:", ttk.Entry(sub, textvariable=v["result_date"], width=14)),
        ("Status:", ttk.Combobox(sub, textvariable=v["status"], values=list(ER.RESULT_STATUSES),
                                 state="readonly", width=12)),
        ("Remark outcome:", ttk.Entry(sub, textvariable=v["remark_outcome"], width=36)),
    ])
    ttk.Label(frm, text="Notes:").grid(row=2, column=0, sticky="nw", pady=(8, 0))
    notes = tk.Text(frm, height=4, wrap="word")
    notes.insert("1.0", (r.notes or "") if r else "")
    notes.grid(row=2, column=1, sticky="nsew", pady=(8, 0))
    frm.columnconfigure(1, weight=1)

    def save() -> None:
        data = {k: x.get().strip() for k, x in v.items()}
        data.update(entry_id=entry.entry_id, notes=notes.get("1.0", "end").strip())
        try:
            ER.upsert(data, actor=principal)
        except _ERRORS as e:
            messagebox.showerror(TITLE, _problems(e), parent=win)
            return
        win.destroy()
        if after:
            after()

    btns = ttk.Frame(frm)
    btns.grid(row=3, column=0, columnspan=2, sticky="e", pady=(10, 0))
    ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="right", padx=(6, 0))
    ttk.Button(btns, text="Save", command=save).pack(side="right")


def pupil_sheet(owner, *, principal: Principal, pupil: P.Pupil,
                series_id: int | None = None) -> None:
    """The old Pupil sheet window."""
    win, frm = _dialog(owner, f"Results - {pupil.display_name}", "720x420")
    d = ER.pupil_results(pupil.pupil_id, actor=principal, series_id=series_id)
    ttk.Label(frm, text=f"{pupil.display_name} ({pupil.admission_no}) · graded {d['graded']} · "
                        f"4+ {d['passes']} · 5+ {d['strong_passes']}").pack(anchor="w")
    t = _tree(frm, [("series", "Series", 90), ("subj", "Subject", 140), ("board", "Board", 90),
                    ("tier", "Tier", 80), ("grade", "Grade", 60), ("marks", "Marks", 60),
                    ("ums", "UMS", 50), ("status", "Status", 80)], height=12)
    for r in d["results"]:
        t.insert("", "end", tags=(r.status,), values=(
            r.series_name, r.subject_name, r.exam_board, r.tier, r.final_grade or "-",
            EE._num(r.marks_awarded) or "-", EE._num(r.ums) or "-", r.status))
    ttk.Button(frm, text="Close", command=win.destroy).pack(anchor="e", pady=(6, 0))


def pending_window(owner, *, series_id: int | None, year_group: int | None = None) -> None:
    """The old Pending window: Final entries with no result yet."""
    win, frm = _dialog(owner, "Pending entries (no result yet)", "720x420")
    rows = ER.list_pending_for_entries(year_group, series_id=series_id)
    ttk.Label(frm, text=f"{len(rows)} entr{'y' if len(rows) == 1 else 'ies'} without a "
                        "result").pack(anchor="w")
    t = _tree(frm, [("entry", "Entry", 60), ("pupil", "Pupil", 160), ("year", "Yr", 40),
                    ("subj", "Subj", 70), ("board", "Board", 100), ("tier", "Tier", 90),
                    ("cand", "Cand#", 60)], height=14)
    for e in rows:
        t.insert("", "end", values=(e.entry_id, e.pupil_name, e.pupil_year, e.subject_code,
                                    e.exam_board, e.tier, e.candidate_number or "-"))
    ttk.Button(frm, text="Close", command=win.destroy).pack(anchor="e", pady=(6, 0))


def review_dialog(owner, *, principal: Principal, result: ER.ExamResult,
                  after: Callable[[], None] | None = None) -> None:
    win, frm = _dialog(owner, f"Review - {result.pupil_name} {result.subject_code}", "520x330")
    v = {"service": tk.StringVar(value=ER.REVIEW_SERVICES[1]), "consent_by": tk.StringVar(),
         "consent_on": tk.StringVar(value=ER._today().isoformat()),
         "deadline": tk.StringVar(), "fee": tk.StringVar(), "fee_payer": tk.StringVar(
             value="School"), "notes": tk.StringVar()}
    _form(frm, [
        ("Service:", ttk.Combobox(frm, textvariable=v["service"], values=list(
            ER.REVIEW_SERVICES), state="readonly", width=28)),
        ("Consent given by:", ttk.Entry(frm, textvariable=v["consent_by"], width=30)),
        ("Consent date:", ttk.Entry(frm, textvariable=v["consent_on"], width=14)),
        ("Board deadline:", ttk.Entry(frm, textvariable=v["deadline"], width=14)),
        ("Fee £:", ttk.Entry(frm, textvariable=v["fee"], width=10)),
        ("Fee payer:", ttk.Combobox(frm, textvariable=v["fee_payer"], values=list(
            EE.FEE_PAYERS), state="readonly", width=10)),
        ("Notes:", ttk.Entry(frm, textvariable=v["notes"], width=36)),
    ])
    ttk.Label(frm, text=f"Current grade {result.final_grade}. A review can lower the grade as "
                        "well as raise it - record the candidate's written consent.",
              foreground="#a60", wraplength=470).grid(row=7, column=0, columnspan=2,
                                                      sticky="w", pady=6)

    def save() -> None:
        try:
            ER.request_review(result.result_id, {k: x.get() for k, x in v.items()},
                              actor=principal)
        except _ERRORS as e:
            messagebox.showerror("Review of marking", _problems(e), parent=win)
            return
        win.destroy()
        if after:
            after()

    btns = ttk.Frame(frm)
    btns.grid(row=8, column=0, columnspan=2, sticky="e")
    ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="right", padx=(6, 0))
    ttk.Button(btns, text="Request", command=save).pack(side="right")


def outcome_dialog(owner, *, principal: Principal, review: ER.Review,
                   after: Callable[[], None] | None = None) -> None:
    r = ER.get_result(review.result_id)
    win, frm = _dialog(owner, f"Outcome - {r.pupil_name} {r.subject_code}", "460x250")
    out = tk.StringVar(value="Unchanged")
    grade = tk.StringVar()
    marks = tk.StringVar()
    notes = tk.StringVar()
    _form(frm, [
        ("Outcome:", ttk.Combobox(frm, textvariable=out, values=list(ER.REVIEW_OUTCOMES),
                                  state="readonly", width=18)),
        (f"New grade (was {r.final_grade}):", ttk.Entry(frm, textvariable=grade, width=8)),
        (f"New marks (was {EE._num(r.marks_awarded) or '-'}):",
         ttk.Entry(frm, textvariable=marks, width=8)),
        ("Notes:", ttk.Entry(frm, textvariable=notes, width=30)),
    ])

    def save() -> None:
        try:
            ER.record_outcome(review.review_id, out.get(), new_grade=grade.get() or None,
                              new_marks=marks.get() or None, notes=notes.get() or None,
                              actor=principal)
        except _ERRORS as e:
            messagebox.showerror("Review outcome", _problems(e), parent=win)
            return
        win.destroy()
        if after:
            after()

    btns = ttk.Frame(frm)
    btns.grid(row=4, column=0, columnspan=2, sticky="e", pady=(10, 0))
    ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="right", padx=(6, 0))
    ttk.Button(btns, text="Save", command=save).pack(side="right")


# ── The page ─────────────────────────────────────────────────────────

class ExamResultsPage:
    TABS = ("Results", "Grade entry", "Reviews", "Analysis", "Release & slips")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None,
                 on_status: Callable[[str], None] | None = None) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil, self.on_status = open_pupil, on_status
        self.editor = ER.is_editor(principal)
        activity_log.record("exam.results.view")
        ttk.Label(parent, text=TITLE, font=("", 16, "bold")).pack(anchor="w")
        top = ttk.Frame(parent)
        top.pack(fill="x", pady=(2, 4))
        ttk.Label(top, text="Exam series:").pack(side="left")
        self.series_var = tk.StringVar()
        self.series_cb = ttk.Combobox(top, textvariable=self.series_var, state="readonly",
                                      width=30)
        self.series_cb.pack(side="left", padx=4)
        self.series_cb.bind("<<ComboboxSelected>>", lambda _e: self._series_changed())
        self.embargo_var = tk.StringVar()
        self.embargo_lbl = ttk.Label(top, textvariable=self.embargo_var)
        self.embargo_lbl.pack(side="left", padx=8)
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(
            anchor="w", pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._build_results(self.tabs["Results"])
        self._build_sheet(self.tabs["Grade entry"])
        self._build_reviews(self.tabs["Reviews"])
        self._build_analysis(self.tabs["Analysis"])
        self._build_release(self.tabs["Release & slips"])
        self._load_series_choices()
        self.book.select(self.TABS.index(state.get("tab", "Results")))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    # helpers
    def _top(self):
        return self.parent.winfo_toplevel()

    def _err(self, e: Exception) -> None:
        messagebox.showerror(TITLE, _problems(e), parent=self._top())

    def _info(self, text: str) -> None:
        messagebox.showinfo(TITLE, text, parent=self._top())

    def _load_series_choices(self) -> None:
        self.series_map = {f"{s.name} ({s.status})": s for s in EE.list_series()}
        self.series_cb.configure(values=list(self.series_map))
        want = self.state.get("series_id")
        label = next((k for k, s in self.series_map.items() if s.series_id == want), None)
        if label is None:
            done = next((k for k, s in self.series_map.items() if ER.list_results(
                series_id=s.series_id)), None)
            label = done or next(iter(self.series_map), "")
        self.series_var.set(label or "")
        self._show_embargo()

    def series(self) -> EE.ExamSeries | None:
        s = self.series_map.get(self.series_var.get())
        return EE.get_series(s.series_id) if s else None

    def _need_series(self) -> EE.ExamSeries | None:
        s = self.series()
        if s is None:
            self._info("Set up an exam series in Exam Entries first.")
        return s

    def _show_embargo(self) -> None:
        s = self.series()
        if s is None:
            self.embargo_var.set("No exam series yet - set one up in Exam Entries.")
            return
        rel = ER.released(s.series_id)
        self.embargo_var.set(
            (f"Released {rel['at'][:16]} by {rel['by']}" if rel else
             "UNDER EMBARGO - only the exams officer can see these results")
            + (f" · results day {s.results_day}" if s.results_day else ""))
        self.embargo_lbl.configure(foreground="#060" if rel else "#a00")

    def _series_changed(self) -> None:
        s = self.series()
        self.state["series_id"] = s.series_id if s else None
        self._show_embargo()
        self._on_tab()

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        try:
            {"Results": self.refresh_results, "Grade entry": self.refresh_sheet_choices,
             "Reviews": self.refresh_reviews, "Analysis": self.refresh_analysis,
             "Release & slips": self.refresh_release}[name]()
        except _ERRORS as e:
            self._err(e)
        self._summary()

    def _summary(self) -> None:
        s = self.series()
        if s is None or not ER.can_see(self.principal, s.series_id):
            self.summary_var.set("")
            return
        d = ER.cohort_summary(series_id=s.series_id,
                              year_group=self.f_year.get() or None, actor=self.principal)
        self.summary_var.set(
            f"Results: {d['total']}    Graded: {d['graded']}    4+: {_pct(d['pass_rate_pct'])}"
            f"    5+: {_pct(d['strong_pass_pct'])}    Awaited: {d['pending']}"
            + (f"    Reviews open: {d['reviews_open']}" if d["reviews_open"] else ""))

    # Results (the old window)
    def _build_results(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        self.f_year = tk.StringVar(value=self.state.get("f_year", ALL))
        self.f_status = tk.StringVar(value=self.state.get("f_status", ALL))
        for label, var, values, w in (("Year:", self.f_year, [ALL, *map(str, P.YEAR_GROUPS)],
                                       5),
                                      ("Status:", self.f_status, [ALL, *ER.RESULT_STATUSES],
                                       11)):
            ttk.Label(bar, text=label).pack(side="left", padx=(0, 4))
            cb = ttk.Combobox(bar, textvariable=var, values=values, state="readonly", width=w)
            cb.pack(side="left", padx=(0, 6))
            cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh_results())
        ttk.Button(bar, text="Apply", command=self.refresh_results).pack(side="left", padx=2)
        if self.editor:
            ttk.Button(bar, text="Record for entry", command=self.record_for_entry).pack(
                side="left", padx=2)
            ttk.Button(bar, text="Edit", command=self.edit_result).pack(side="left", padx=2)
        ttk.Button(bar, text="Pupil sheet", command=self.pupil_sheet).pack(side="left", padx=2)
        ttk.Button(bar, text="Summary", command=self.show_summary).pack(side="left", padx=2)
        ttk.Button(bar, text="Pending", command=self.show_pending).pack(side="left", padx=2)
        if self.editor:
            ttk.Button(bar, text="Delete", command=self.delete_result).pack(side="left",
                                                                            padx=2)
        ttk.Button(bar, text="Refresh", command=self.refresh_results).pack(side="left", padx=2)
        self.r_note = tk.StringVar()
        ttk.Label(tab, textvariable=self.r_note, foreground="#a00").pack(anchor="w")
        self.r_tree = _tree(tab, [
            ("id", "ID", 50), ("entry", "Entry", 60), ("pupil", "Pupil", 90),
            ("name", "Name", 160), ("year", "Yr", 40), ("subj", "Subj", 70),
            ("board", "Board", 90), ("tier", "Tier", 85), ("grade", "Grade", 60),
            ("marks", "Marks", 60), ("ums", "UMS", 50), ("status", "Status", 90)], height=16)
        self.r_tree.bind("<Double-1>", lambda _e: self.edit_result() if self.editor
                         else self.pupil_sheet())
        acts = ttk.Frame(tab)
        acts.pack(fill="x", pady=(6, 0))
        if self.editor:
            ttk.Button(acts, text="Request review of marking…",
                       command=self.request_review).pack(side="left")
        ttk.Button(acts, text="Pupil profile", command=self.profile).pack(side="left",
                                                                         padx=(4, 0))
        ttk.Button(acts, text="Result history", command=self.result_history).pack(
            side="left", padx=(4, 0))

    def refresh_results(self) -> None:
        self.state["f_year"], self.state["f_status"] = self.f_year.get(), self.f_status.get()
        self.r_tree.delete(*self.r_tree.get_children())
        s = self.series()
        if s is None:
            return
        if not ER.can_see(self.principal, s.series_id):
            self.r_note.set(f"Results for {s.name} are under embargo until the exams officer "
                            "releases them.")
            return
        self.r_note.set("")
        rows = ER.list_results(series_id=s.series_id, year_group=self.f_year.get() or None,
                               status=self.f_status.get() or None, actor=self.principal)
        for r in rows:
            self.r_tree.insert("", "end", iid=str(r.result_id), tags=(r.status,), values=(
                r.result_id, r.entry_id, r.admission_no, r.pupil_name, r.pupil_year,
                r.subject_code, r.exam_board, r.tier, r.final_grade or "-",
                EE._num(r.marks_awarded) or "-", EE._num(r.ums) or "-",
                r.status + (f" (was {r.original_grade})" if r.original_grade else "")))
        if self.on_status:
            self.on_status(f"Exam results: {len(rows)} record(s)")
        self._summary()

    def _result(self) -> ER.ExamResult | None:
        sel = self.r_tree.selection()
        if not sel:
            self._info("Select a result first.")
            return None
        return ER.get(int(sel[0]))

    def record_for_entry(self) -> None:
        s = self._need_series()
        if not s:
            return
        pending = ER.list_pending_for_entries(series_id=s.series_id)
        if not pending:
            self._info("Every Final entry in this series has a result.")
            return
        win, frm = _dialog(self.parent, "Record for entry", "560x170")
        labels = {f"#{e.entry_id} {e.pupil_name} - {e.subject_name} {e.entry_code}": e
                  for e in pending}
        pick = tk.StringVar(value=next(iter(labels)))
        ttk.Combobox(frm, textvariable=pick, values=list(labels), state="readonly",
                     width=60).pack(fill="x")

        def go() -> None:
            e = labels[pick.get()]
            win.destroy()
            result_dialog(self.parent, principal=self.principal, entry=e,
                          result=ER.get_for_entry(e.entry_id), after=self.refresh_results)

        ttk.Button(frm, text="Next…", command=go).pack(anchor="e", pady=(10, 0))

    def edit_result(self) -> None:
        r = self._result()
        if r:
            result_dialog(self.parent, principal=self.principal, entry=EE.get_entry(r.entry_id),
                          result=r, after=self.refresh_results)

    def pupil_sheet(self) -> None:
        r = self._result()
        p = P.get_pupil(r.pupil_id) if r else None
        if p:
            pupil_sheet(self.parent, principal=self.principal, pupil=p)

    def show_summary(self) -> None:
        s = self._need_series()
        if not s:
            return
        try:
            d = ER.cohort_summary(series_id=s.series_id, year_group=self.f_year.get() or None,
                                  actor=self.principal)
        except _ERRORS as e:
            self._err(e)
            return
        grades = sorted(d["by_grade"].items(), key=lambda kv: -(ER.grade_value(kv[0]) or -1))
        _text_window(self.parent, f"Summary - {s.name}", "\n".join([
            f"Results: {d['total']}   graded: {d['graded']}   awaited: {d['pending']}",
            f"Grade 4+: {_pct(d['pass_rate_pct'])}   grade 5+: {_pct(d['strong_pass_pct'])}",
            "", "By status: " + ", ".join(f"{k} {n}" for k, n in d["by_status"].items()),
            "By grade:  " + ", ".join(f"{k} {n}" for k, n in grades)]))

    def show_pending(self) -> None:
        s = self._need_series()
        if s:
            pending_window(self.parent, series_id=s.series_id,
                           year_group=int(self.f_year.get()) if self.f_year.get() else None)

    def delete_result(self) -> None:
        r = self._result()
        if not r or not messagebox.askyesno(
                "Delete result", f"Delete the result for {r.pupil_name} / {r.subject_code}?",
                parent=self._top()):
            return
        try:
            ER.delete(r.result_id, actor=self.principal)
        except _ERRORS as e:
            self._err(e)
        self.refresh_results()

    def request_review(self) -> None:
        r = self._result()
        if r:
            review_dialog(self.parent, principal=self.principal, result=r,
                          after=self.refresh_results)

    def profile(self) -> None:
        r = self._result()
        if r and self.open_pupil:
            self.open_pupil(r.pupil_id)

    def result_history(self) -> None:
        r = self._result()
        if r:
            _text_window(self.parent, f"History - {r.pupil_name} {r.subject_code}", "\n".join(
                f"{h['at']}  {h['actor']:<12} {h['action']:<16} {h['detail']}"
                for h in ER.history(result_id=r.result_id)) or "No changes.")

    # Grade entry
    def _build_sheet(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Subject:").pack(side="left")
        self.g_subject = tk.StringVar()
        self.g_cb = ttk.Combobox(bar, textvariable=self.g_subject, state="readonly", width=40)
        self.g_cb.pack(side="left", padx=4)
        self.g_cb.bind("<<ComboboxSelected>>", lambda _e: self.load_sheet())
        if self.editor:
            ttk.Button(bar, text="Save grades", command=self.save_sheet).pack(side="left",
                                                                             padx=(8, 0))
        self.g_info = tk.StringVar()
        ttk.Label(tab, textvariable=self.g_info, foreground="#666", wraplength=900).pack(
            anchor="w")
        holder = ttk.Frame(tab)
        holder.pack(fill="both", expand=True)
        canvas = tk.Canvas(holder, highlightthickness=0)
        sb = ttk.Scrollbar(holder, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self.g_body = ttk.Frame(canvas)
        canvas.create_window(0, 0, window=self.g_body, anchor="nw")
        self.g_body.bind("<Configure>",
                         lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        self.g_rows: dict[int, dict[str, tk.StringVar]] = {}

    def refresh_sheet_choices(self) -> None:
        s = self.series()
        specs = {}
        if s:
            for e in EE.list_entries(series_id=s.series_id, entry_status="Final"):
                specs.setdefault(f"{e.subject_name} - {e.exam_board} {e.spec_code}", e.spec_id)
        self.g_map = specs
        self.g_cb.configure(values=list(specs))
        if self.g_subject.get() not in specs:
            self.g_subject.set(next(iter(specs), ""))
        self.load_sheet()

    def load_sheet(self) -> None:
        for w in self.g_body.winfo_children():
            w.destroy()
        self.g_rows = {}
        s = self.series()
        spec_id = getattr(self, "g_map", {}).get(self.g_subject.get())
        if s is None or spec_id is None:
            self.g_info.set("No Final entries in this series.")
            return
        if not ER.can_see(self.principal, s.series_id):
            self.g_info.set("Under embargo until the exams officer releases the results.")
            return
        entries = EE.list_entries(series_id=s.series_id, spec_id=spec_id, entry_status="Final")
        self.g_info.set(f"{len(entries)} candidate(s). Grades 9-1, U or X (absent); leave a "
                        "row blank to skip it. Results under review can't be changed here.")
        for c, text in enumerate(("Cand#", "Pupil", "Tier", "Grade", "Marks", "Status")):
            ttk.Label(self.g_body, text=text, font=("", 9, "bold")).grid(row=0, column=c,
                                                                         sticky="w", padx=3)
        for i, e in enumerate(entries, start=1):
            r = ER.get_for_entry(e.entry_id)
            locked = not self.editor or bool(r and r.status == "Remarked")
            v = {"final_grade": tk.StringVar(value=(r.final_grade or "") if r else ""),
                 "marks_awarded": tk.StringVar(value=EE._num(r.marks_awarded) if r else "")}
            ttk.Label(self.g_body, text=e.candidate_number or "-").grid(row=i, column=0,
                                                                        sticky="w", padx=3)
            ttk.Label(self.g_body, text=e.pupil_name).grid(row=i, column=1, sticky="w", padx=3)
            ttk.Label(self.g_body, text="" if e.tier == "N/A" else e.tier).grid(
                row=i, column=2, sticky="w", padx=3)
            st = "disabled" if locked else "normal"
            ttk.Entry(self.g_body, textvariable=v["final_grade"], width=6, state=st).grid(
                row=i, column=3, padx=3)
            ttk.Entry(self.g_body, textvariable=v["marks_awarded"], width=6, state=st).grid(
                row=i, column=4, padx=3)
            ttk.Label(self.g_body, text=r.status if r else "awaited").grid(row=i, column=5,
                                                                           sticky="w", padx=3)
            if not locked:
                self.g_rows[e.entry_id] = v

    def save_sheet(self) -> None:
        s = self._need_series()
        if not s:
            return
        rows = {eid: {k: x.get().strip() for k, x in v.items()}
                for eid, v in self.g_rows.items()}
        try:
            n = ER.save_sheet(s.series_id, rows, actor=self.principal)
        except _ERRORS as e:
            self._err(e)
            return
        self._info(f"Saved {n} result(s).")
        self.load_sheet()
        self._summary()

    # Reviews
    def _build_reviews(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        if self.editor:
            ttk.Button(bar, text="Mark sent to board", command=self.review_submitted).pack(
                side="left")
            ttk.Button(bar, text="Record outcome…", command=self.review_outcome).pack(
                side="left", padx=(4, 0))
            ttk.Button(bar, text="Cancel review", command=self.review_cancel).pack(
                side="left", padx=(4, 0))
        ttk.Button(bar, text="Refresh", command=self.refresh_reviews).pack(side="right")
        ttk.Label(tab, text="Request a review from the Results tab (select a result).",
                  foreground="#777").pack(anchor="w")
        self.v_tree = _tree(tab, [
            ("id", "ID", 45), ("pupil", "Pupil", 150), ("subj", "Subj", 60),
            ("service", "Service", 170), ("status", "Status", 85), ("deadline", "Deadline", 90),
            ("before", "Before", 55), ("after", "After", 55), ("outcome", "Outcome", 110),
            ("fee", "Fee", 70), ("refund", "Refund", 60), ("name", "Consent", 120)])

    def refresh_reviews(self) -> None:
        self.v_tree.delete(*self.v_tree.get_children())
        s = self.series()
        if s is None or not ER.can_see(self.principal, s.series_id):
            return
        for v in ER.reviews(series_id=s.series_id):
            r = ER.get(v.result_id)
            self.v_tree.insert("", "end", iid=str(v.review_id), tags=(
                ("good" if v.outcome == "Grade raised" else "bad" if v.outcome ==
                 "Grade lowered" else ""),), values=(
                v.review_id, r.pupil_name if r else "", r.subject_code if r else "",
                v.service, v.status, v.deadline or "", v.grade_before or "",
                v.grade_after or "", v.outcome or "", EE.money(v.fee),
                "Yes" if v.refunded else "", f"{v.consent_by} {v.consent_on}"))

    def _review(self) -> ER.Review | None:
        sel = self.v_tree.selection()
        if not sel:
            self._info("Select a review first.")
            return None
        return ER.get_review(int(sel[0]))

    def review_submitted(self) -> None:
        v = self._review()
        if v:
            try:
                ER.mark_submitted(v.review_id, actor=self.principal)
            except _ERRORS as e:
                self._err(e)
            self.refresh_reviews()

    def review_outcome(self) -> None:
        v = self._review()
        if v:
            outcome_dialog(self.parent, principal=self.principal, review=v,
                           after=self.refresh_reviews)

    def review_cancel(self) -> None:
        v = self._review()
        if v and messagebox.askyesno("Cancel review", "Cancel this review?",
                                     parent=self._top()):
            try:
                ER.cancel_review(v.review_id, actor=self.principal)
            except _ERRORS as e:
                self._err(e)
            self.refresh_reviews()

    # Analysis
    def _build_analysis(self, tab: ttk.Frame) -> None:
        self.a_head = tk.StringVar()
        ttk.Label(tab, textvariable=self.a_head, font=("", 10, "bold"), wraplength=950,
                  justify="left").pack(anchor="w", pady=(0, 6))
        ttk.Label(tab, text="Subjects (gaps are average grades better (+) or worse (-) than "
                            "the latest mock and the target)", foreground="#666").pack(
            anchor="w")
        self.a_tree = _tree(tab, [("name", "Subject", 200), ("graded", "Graded", 60),
                                  ("avg", "Average", 70), ("p7", "7+", 60), ("p5", "5+", 60),
                                  ("p4", "4+", 60), ("mock", "vs mock", 70),
                                  ("target", "vs target", 75)], height=8)
        ttk.Label(tab, text="Pupils against target (furthest below first)",
                  foreground="#666").pack(anchor="w", pady=(8, 0))
        self.a_pupils = _tree(tab, [("adm", "Adm no", 90), ("name", "Pupil", 170),
                                    ("gap", "Gap", 60), ("detail", "Grades", 400)], height=8)
        self.a_pupils.bind("<Double-1>", lambda _e: self._open_analysis_pupil())

    def refresh_analysis(self) -> None:
        self.a_tree.delete(*self.a_tree.get_children())
        self.a_pupils.delete(*self.a_pupils.get_children())
        s = self.series()
        if s is None:
            return
        if not ER.can_see(self.principal, s.series_id):
            self.a_head.set("Under embargo until the exams officer releases the results.")
            return
        h = ER.headlines(s.series_id, actor=self.principal)
        vt = h["vs_target"]
        self.a_head.set(
            f"{h['candidates']} candidates · {h['results']} results · average grade "
            f"{h['average'] if h['average'] is not None else '-'} · 7+ {_pct(h['pct_7'])} · "
            f"English and maths 4+ {h['english_maths_4']} ({_pct(h['english_maths_4_pct'])}), "
            f"5+ {h['english_maths_5']} ({_pct(h['english_maths_5_pct'])}) · against target: "
            f"{vt.get('above', 0)} above, {vt.get('met', 0)} met, {vt.get('below', 0)} below")
        for d in ER.subject_analysis(s.series_id, actor=self.principal):
            self.a_tree.insert("", "end", tags=(
                "good" if (d["vs_target"] or 0) > 0 else "bad" if (d["vs_target"] or 0) < 0
                else "",), values=(
                d["subject"], d["graded"], d["average"] if d["average"] is not None else "-",
                _pct(d["pct_7"]), _pct(d["pct_5"]), _pct(d["pct_4"]), _gap(d["vs_mock"]),
                _gap(d["vs_target"])))
        for d in ER.pupils_vs_target(s.series_id, actor=self.principal):
            self.a_pupils.insert("", "end", iid=str(d["pupil_id"]), tags=(
                "bad" if (d["average_gap"] or 0) < 0 else "",), values=(
                d["admission_no"], d["name"], _gap(d["average_gap"]), ", ".join(d["grades"])))

    def _open_analysis_pupil(self) -> None:
        sel = self.a_pupils.selection()
        if sel and self.open_pupil:
            self.open_pupil(int(sel[0]))

    # Release & slips
    def _build_release(self, tab: ttk.Frame) -> None:
        box = ttk.LabelFrame(tab, text="Results file", padding=8)
        box.pack(fill="x")
        if self.editor:
            ttk.Button(box, text="Import the board's results file…",
                       command=self.import_file).pack(side="left")
        ttk.Button(box, text="Export results (CSV)…", command=self.export_file).pack(
            side="left", padx=(4, 0))
        ttk.Label(box, text="Columns: Candidate number, Entry code, Grade (+ Marks, Max marks, "
                            "UMS, Status)", foreground="#777").pack(side="left", padx=8)
        box = ttk.LabelFrame(tab, text="Embargo", padding=8)
        box.pack(fill="x", pady=(8, 0))
        self.rel_var = tk.StringVar()
        ttk.Label(box, textvariable=self.rel_var, wraplength=900).pack(anchor="w")
        if self.editor:
            bar = ttk.Frame(box)
            bar.pack(anchor="w", pady=(6, 0))
            ttk.Button(bar, text="Release results", command=lambda: self.release(True)).pack(
                side="left")
            ttk.Button(bar, text="Put back under embargo",
                       command=lambda: self.release(False)).pack(side="left", padx=(4, 0))
        box = ttk.LabelFrame(tab, text="Results slips", padding=8)
        box.pack(fill="x", pady=(8, 0))
        ttk.Button(box, text="Preview slip for selected result's pupil",
                   command=self.preview_slip).pack(side="left")
        if self.editor:
            ttk.Button(box, text="E-mail results to pupils and families",
                       command=self.send_slips).pack(side="left", padx=(4, 0))
        ttk.Button(tab, text="Series history", command=self.series_history).pack(
            anchor="w", pady=(8, 0))

    def refresh_release(self) -> None:
        s = self.series()
        if s is None:
            self.rel_var.set("")
            return
        rel = ER.released(s.series_id)
        n = len(ER.list_results(series_id=s.series_id))
        self.rel_var.set(
            (f"Released {rel['at'][:16]} by {rel['by']}: all staff can see the results, and "
             "pupils and parents see them in the portal." if rel else
             f"Under embargo: {n} result(s) are visible to the exams officer only. Release them "
             "on results day morning.") + (f" Results day: {s.results_day}." if s.results_day
                                            else ""))
        self._show_embargo()

    def release(self, on: bool) -> None:
        s = self._need_series()
        if not s:
            return
        if on and not messagebox.askyesno(
                TITLE, f"Release {s.name} results to all staff, pupils and parents?",
                parent=self._top()):
            return
        try:
            out = ER.release(s.series_id, on=on, actor=self.principal)
        except _ERRORS as e:
            self._err(e)
        else:
            sf = (out or {}).get("sixth_form")
            if sf and (sf.get("sent") or sf.get("skipped") or sf.get("failed")):
                self._info(_sixth_form_text(sf))
        self.refresh_release()

    def import_file(self) -> None:
        s = self._need_series()
        if not s:
            return
        path = filedialog.askopenfilename(parent=self._top(), title="Board results file",
                                          filetypes=[("CSV", "*.csv"), ("All files", "*")])
        if not path:
            return
        try:
            c = ER.import_results(s.series_id, path, actor=self.principal)
        except (OSError, *_ERRORS) as e:
            self._err(e)
            return
        self._info(f"{c['record']} new, {c['change']} changed, {c['unchanged']} unchanged.")
        self.refresh_release()

    def export_file(self) -> None:
        s = self._need_series()
        if not s:
            return
        path = filedialog.asksaveasfilename(parent=self._top(), defaultextension=".csv",
                                            initialfile=f"results-{s.name}.csv".replace(" ",
                                                                                        "-"),
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            n = ER.export_results(s.series_id, path, actor=self.principal)
        except (OSError, *_ERRORS) as e:
            self._err(e)
            return
        self._info(f"Saved {n} result(s).")

    def preview_slip(self) -> None:
        s = self._need_series()
        sel = self.r_tree.selection()
        if not s:
            return
        if not sel:
            self._info("Select a result on the Results tab first.")
            return
        r = ER.get(int(sel[0]))
        if r:
            _text_window(self.parent, "Results slip", ER.slip_text(ER.slip(r.pupil_id,
                                                                           s.series_id)))

    def send_slips(self) -> None:
        s = self._need_series()
        if not s or not messagebox.askyesno(
                TITLE, f"E-mail every candidate's {s.name} results to their school address "
                       "and their contacts?", parent=self._top()):
            return
        try:
            r = ER.send_slips(s.series_id, actor=self.principal)
        except _ERRORS as e:
            self._err(e)
            return
        from education_system.systems.secondary.modules.communication.gui import email_views

        def done(report, error) -> None:
            text = f"{r['emails']} results e-mail(s) " + (
                f"queued - delivery failed: {error}" if error else "sent.")
            if r["nobody"]:
                text += ("\n\nNo e-mail address for: "
                         + ", ".join(p.display_name for p in r["nobody"][:20]))
            try:
                self._info(text)
            except tk.TclError:
                pass

        email_views.deliver_in_background(self.parent, r["message_id"], self.principal, done)

    def series_history(self) -> None:
        s = self._need_series()
        if s and ER.can_see(self.principal, s.series_id):
            _text_window(self.parent, f"History - {s.name}", "\n".join(
                f"{h['at']}  {h['actor']:<12} {h['action']:<16} "
                + (f"result {h['result_id']} " if h["result_id"] else "") + str(h["detail"])
                for h in ER.history(series_id=s.series_id)) or "No changes yet.")


def draw_exam_results(parent: ttk.Frame, *, principal: Principal, state: dict,
                      open_pupil: Callable[[int], None] | None = None,
                      on_status: Callable[[str], None] | None = None) -> ExamResultsPage:
    return ExamResultsPage(parent, principal=principal, state=state, open_pupil=open_pupil,
                           on_status=on_status)


def draw_profile_results(parent: ttk.Frame, pupil: P.Pupil, *, principal: Principal) -> None:
    """Exam results on the pupil's profile (released series, or all for the
    exams officer)."""
    rows = ER.list_results(pupil_id=pupil.pupil_id, actor=principal)
    if not rows:
        return
    box = ttk.LabelFrame(parent, text="Exam results", padding=8)
    box.pack(fill="x", pady=(8, 0))
    for r in rows:
        ttk.Label(box, text=f"{r.series_name}: {r.subject_name} {r.final_grade or '-'}"
                            + ("" if r.status == "Final" else f" ({r.status.lower()})")
                            + ("" if ER.released(r.series_id) else " - under embargo"),
                  foreground="#a60" if r.status in ("Remarked", "Withheld") else "").pack(
            anchor="w")
