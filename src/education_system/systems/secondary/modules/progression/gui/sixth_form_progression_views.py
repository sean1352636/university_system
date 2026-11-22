"""Move to Sixth Form screen, plus the SEN details and GCSE results dialogs.

Tabs:

* **Year 11** - pupils on roll with their GCSE count, SEN and where their
  sixth form application is; Send selected (the old "Move to Sixth Form"
  dialog: Subject 1-3, Destination, Notes, consent tick), Preview, Withdraw.
* **GCSE results** - every result, filtered; Add / Edit, Delete, Import
  results-day CSV, Export.
* **Sent** - each application on the post-16 board with the stage the
  sixth form has reached.
* **SEN register** - Year 11 pupils with SEN support or an EHC plan and
  whether the SENCO has filled in their details.

Rules live in :mod:`modules.progression.domain.sixth_form_progression`, :mod:`modules.examinations.domain.gcse_results`
and :mod:`modules.pupils.domain.sen_details`.
"""

from __future__ import annotations

import json
import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable

from education_system.platform.delivery.gui.parented_dialogs import (
    filedialog,
    messagebox,
)
from education_system.systems.secondary.modules.examinations.domain import exam_results as ER
from education_system.systems.secondary.modules.examinations.domain import gcse_results as G
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.progression.domain import sixth_form_choices as SC
from education_system.systems.secondary.modules.progression.domain import (
    sixth_form_progression as SFP,
)
from education_system.systems.secondary.modules.pupils.domain import sen_details as SEN
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
ALL = ""
_ERRORS = (P.ValidationError, P.PermissionDenied, P.NotFound)
STAGE_BG = {"Not sent": "#ffffff", "Declined": "#fde2e2", "Withdrawn": "#eeeeee",
            "Enrolled / On Programme": "#e7f6ea", "Conditional offer": "#fff6d6",
            "Offer accepted": "#e7f0fb"}


def _results_sent(app: dict) -> str:
    """GCSE grades and entries still awaited in the stored handover."""
    try:
        h = json.loads(app.get("handover_json") or "{}")
    except ValueError:
        return ""
    grades = len(h.get("gcse_results") or [])
    waiting = sum(1 for e in h.get("gcse_entries") or [] if e.get("result") != "issued")
    return f"{grades} grade(s)" + (f", {waiting} to come" if waiting else "")


_problems = W.problems


def _tree(parent, columns, height: int = 14, select: str = "browse") -> ttk.Treeview:
    return W.tree(parent, columns, height=height, select=select, stretch={"name", "detail"},
                  tags=STAGE_BG)


def _dialog(owner: tk.Misc, title: str, size: str = "520x460") -> tuple[tk.Toplevel, ttk.Frame]:
    return W.dialog(owner, title, size=size)


# ── Send dialog (the old "Move to Sixth Form" dialog) ────────────────

def send_dialog(owner: tk.Misc, *, principal: Principal, pupil: P.Pupil,
                after: Callable[[], None] | None = None) -> None:
    win, frm = _dialog(owner, "Move to Sixth Form", "560x560")
    ttk.Label(frm, text=f"Move {pupil.full_name} ({pupil.admission_no}) into the sixth form "
                        "system?", wraplength=520, justify="left").pack(anchor="w")
    if pupil.year_group != P.YEAR_GROUPS[-1]:
        ttk.Label(frm, text=f"Current secondary year group is {pupil.year_group}.",
                  foreground="#a45").pack(anchor="w", pady=(4, 0))
    ttk.Label(frm, text="They become a sixth form applicant; they stay on roll here until "
                        "the sixth form enrols them.", foreground="#666", wraplength=520,
              justify="left").pack(anchor="w", pady=(4, 8))
    offered = list(SFP.offered_subjects())
    saved = SC.courses_for(pupil.pupil_id)  # the pupil's own A-level choices
    subjects = [tk.StringVar(value=saved[i] if i < len(saved) else "") for i in range(3)]
    destination = tk.StringVar(value=SFP.DESTINATION_LABEL)
    notes = tk.StringVar()
    grid = ttk.Frame(frm)
    grid.pack(fill="x")
    for row, var in enumerate(subjects):
        ttk.Label(grid, text=f"Subject {row + 1}:").grid(row=row, column=0, sticky="w", pady=3)
        ttk.Combobox(grid, textvariable=var, values=offered, width=34).grid(
            row=row, column=1, sticky="ew", pady=3)
    for row, (label, var) in enumerate((("Destination", destination), ("Notes", notes)),
                                       start=3):
        ttk.Label(grid, text=f"{label}:").grid(row=row, column=0, sticky="w", pady=3)
        ttk.Entry(grid, textvariable=var, width=36).grid(row=row, column=1, sticky="ew", pady=3)
    grid.columnconfigure(1, weight=1)
    ttk.Label(frm, text="Three A-levels (the pupil's own choices are filled in), or leave "
                        "them blank - the sixth form can take them at interview.",
              foreground="#666", wraplength=520, justify="left").pack(anchor="w", pady=(2, 6))

    results = G.for_pupil(pupil.pupil_id)
    sen = SEN.handover_block(pupil)
    goes = ttk.LabelFrame(frm, text="What goes with them", padding=8)
    goes.pack(fill="x")
    ttk.Label(goes, text="Full name, date of birth, gender, UPN, admission number").pack(
        anchor="w")
    ttk.Label(goes, text=(f"GCSE results: {G.summary_line(pupil.pupil_id)}" if results
                          else "GCSE results: none recorded yet"),
              wraplength=500, justify="left",
              foreground="" if results else "#a60").pack(anchor="w")
    share = tk.BooleanVar(value=False)
    ref = tk.StringVar()
    if sen:
        ttk.Label(goes, text=f"SEN: {SEN.summary_line(pupil)}", wraplength=500,
                  justify="left").pack(anchor="w")
        ttk.Checkbutton(goes, variable=share,
                        text="Consent recorded to share support, access and reference detail"
                        ).pack(anchor="w", pady=(6, 0))
        r = ttk.Frame(goes)
        r.pack(fill="x")
        ttk.Label(r, text="Consent reference:").pack(side="left")
        ttk.Entry(r, textvariable=ref, width=28).pack(side="left", padx=(6, 0))
        ttk.Label(goes, text="Without consent the SEN details are held back.",
                  foreground="#666").pack(anchor="w")
    else:
        ttk.Label(goes, text="SEN: none", foreground="#666").pack(anchor="w")

    def chosen() -> list[str]:
        return [v.get().strip() for v in subjects if v.get().strip()]

    def preview() -> None:
        try:
            pv = SFP.preview(pupil.pupil_id, actor=principal, consent_sen=share.get(),
                             consent_reference=ref.get(), subjects=chosen(),
                             notes=notes.get())
        except Exception as e:  # noqa: BLE001 - shown to the user
            messagebox.showerror("Preview", _problems(e), parent=win)
            return
        lines = ["Sent: " + ", ".join(pv.included)]
        if pv.withheld_no_consent:
            lines.append("Held back (no consent): " + ", ".join(pv.withheld_no_consent))
        if pv.missing_required:
            lines.append("Missing: " + ", ".join(pv.missing_required))
        messagebox.showinfo("Preview", "\n".join(lines), parent=win)

    def go() -> None:
        try:
            app = SFP.send(pupil.pupil_id, actor=principal, consent_sen=share.get(),
                           consent_reference=ref.get(), subjects=chosen(), notes=notes.get(),
                           destination_label=destination.get())
        except _ERRORS as e:
            messagebox.showerror("Move to sixth form", _problems(e), parent=win)
            return
        except Exception as e:  # noqa: BLE001 - the platform / sixth form failed
            logger.exception("Sending to the sixth form failed")
            messagebox.showerror("Move to sixth form", f"The sixth form could not take the "
                                 f"application:\n{e}", parent=win)
            return
        messagebox.showinfo("Move to sixth form",
                            f"{pupil.display_name} sent to the sixth form as an applicant "
                            f"({app['stage']}).", parent=win)
        win.destroy()
        if after:
            after()

    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(10, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Move to Sixth Form", command=go).pack(side="right", padx=(0, 6))
    ttk.Button(bar, text="Preview…", command=preview).pack(side="left")


# ── SEN details dialog ───────────────────────────────────────────────

NEED_CHOICES = [""] + [f"{k} - {v}" for k, v in SEN.NEEDS.items()]


def sen_dialog(owner: tk.Misc, *, principal: Principal, pupil: P.Pupil,
               after: Callable[[], None] | None = None) -> None:
    cur = SEN.get(pupil.pupil_id)
    win, frm = _dialog(owner, f"SEN details - {pupil.display_name}", "620x600")
    ttk.Label(frm, text=f"SEN status: {pupil.sen_label} (change it on the pupil record)",
              foreground="#555").pack(anchor="w", pady=(0, 6))
    grid = ttk.Frame(frm)
    grid.pack(fill="both", expand=True)
    grid.columnconfigure(1, weight=1)

    def need_label(code: str | None) -> str:
        return f"{code} - {SEN.NEEDS[code]}" if code in SEN.NEEDS else ""
    vars_: dict[str, tk.Variable] = {
        "primary_need": tk.StringVar(value=need_label(cur.primary_need if cur else None)),
        "secondary_need": tk.StringVar(value=need_label(cur.secondary_need if cur else None)),
        "ehcp_reference": tk.StringVar(value=(cur.ehcp_reference or "") if cur else ""),
        "ehcp_issued_on": tk.StringVar(value=(cur.ehcp_issued_on or "") if cur else ""),
        "exam_access": tk.StringVar(value=(cur.exam_access or "") if cur else ""),
    }
    row = 0
    for key, label in (("primary_need", "Primary need"), ("secondary_need", "Secondary need")):
        ttk.Label(grid, text=f"{label}:").grid(row=row, column=0, sticky="w", pady=3)
        ttk.Combobox(grid, textvariable=vars_[key], values=NEED_CHOICES, state="readonly",
                     width=52).grid(row=row, column=1, sticky="ew", pady=3)
        row += 1
    for key, label in (("ehcp_reference", "EHC plan reference"),
                       ("ehcp_issued_on", "EHC plan issued (YYYY-MM-DD)"),
                       ("exam_access", "Exam access arrangements")):
        ttk.Label(grid, text=f"{label}:").grid(row=row, column=0, sticky="w", pady=3)
        state = "normal" if key == "exam_access" or pupil.sen_status == "E" else "disabled"
        ttk.Entry(grid, textvariable=vars_[key], state=state).grid(
            row=row, column=1, sticky="ew", pady=3)
        row += 1
    texts: dict[str, tk.Text] = {}
    for key, label in (("provision", "Provision in place"), ("strategies", "Strategies"),
                       ("notes", "SENCO notes")):
        ttk.Label(grid, text=f"{label}:").grid(row=row, column=0, sticky="nw", pady=3)
        t = tk.Text(grid, height=4, wrap="word")
        t.insert("1.0", (getattr(cur, key) or "") if cur else "")
        t.grid(row=row, column=1, sticky="ew", pady=3)
        texts[key] = t
        row += 1

    def save() -> None:
        data = {k: v.get() for k, v in vars_.items()}
        for k in ("primary_need", "secondary_need"):
            data[k] = str(data[k]).split(" - ", 1)[0]
        if pupil.sen_status != "E":
            data.pop("ehcp_reference")
            data.pop("ehcp_issued_on")
        data.update({k: t.get("1.0", "end").strip() for k, t in texts.items()})
        try:
            SEN.save(pupil.pupil_id, data, actor=principal)
        except _ERRORS as e:
            messagebox.showerror("SEN details", _problems(e), parent=win)
            return
        win.destroy()
        if after:
            after()

    def clear() -> None:
        if not messagebox.askyesno("SEN details", "Clear this pupil's SEN details?",
                                   parent=win):
            return
        try:
            SEN.clear(pupil.pupil_id, actor=principal)
        except _ERRORS as e:
            messagebox.showerror("SEN details", _problems(e), parent=win)
            return
        win.destroy()
        if after:
            after()

    def history() -> None:
        rows = SEN.history(pupil.pupil_id)
        messagebox.showinfo("SEN history", "\n".join(
            f"{h['at']}  {h['actor']}  {h['action']}"
            + (f": {', '.join(h['fields'])}" if h["fields"] else "") for h in rows)
            or "No changes recorded.", parent=win)

    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(10, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Save", command=save).pack(side="right", padx=(0, 6))
    ttk.Button(bar, text="History", command=history).pack(side="left")
    if cur:
        ttk.Button(bar, text="Clear", command=clear).pack(side="left", padx=(6, 0))


# ── GCSE result dialog ───────────────────────────────────────────────

def gcse_dialog(owner: tk.Misc, *, principal: Principal, pupil: P.Pupil | None = None,
                result: G.Result | None = None,
                after: Callable[[], None] | None = None) -> None:
    win, frm = _dialog(owner, "GCSE result", "480x340")
    subjects = {f"{s.code} - {s.name}": s for s in S.list_subjects()}
    pupils = ({f"{p.display_name} ({p.admission_no})": p
               for p in P.list_pupils(year_group=P.YEAR_GROUPS[-1])}
              if pupil is None and result is None else {})
    target = pupil or (P.get_pupil(result.pupil_id) if result else None)
    v = {
        "pupil": tk.StringVar(),
        "subject": tk.StringVar(value=next((k for k, s in subjects.items()
                                            if result and s.subject_id == result.subject_id),
                                           "")),
        "qualification": tk.StringVar(value=result.qualification if result else "GCSE"),
        "grade": tk.StringVar(value=result.grade if result else ""),
        "exam_board": tk.StringVar(value=(result.exam_board or "") if result else ""),
        "exam_year": tk.StringVar(value=str(result.exam_year) if result else
                                  str(G._today().year)),
        "series": tk.StringVar(value=result.series if result else "June"),
    }
    grid = ttk.Frame(frm)
    grid.pack(fill="x")
    grid.columnconfigure(1, weight=1)
    rows: list[tuple[str, str, list[str] | None]] = []
    if pupils:
        rows.append(("pupil", "Pupil", list(pupils)))
    rows += [("subject", "Subject", list(subjects)),
             ("qualification", "Qualification", list(G.QUALIFICATIONS)),
             ("grade", "Grade", list(G.GRADES)),
             ("exam_board", "Board", [""] + list(G.BOARDS)),
             ("exam_year", "Exam year", None), ("series", "Series", list(G.SERIES))]
    if target is not None:
        ttk.Label(grid, text=f"Pupil: {target.display_name} ({target.admission_no})").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
    for i, (key, label, values) in enumerate(rows, start=1):
        ttk.Label(grid, text=f"{label}:").grid(row=i, column=0, sticky="w", pady=3)
        if values is None:
            w: tk.Widget = ttk.Entry(grid, textvariable=v[key], width=10)
        else:
            w = ttk.Combobox(grid, textvariable=v[key], values=values, state="readonly")
        if result is not None and key in ("subject", "qualification"):
            w.configure(state="disabled")
        w.grid(row=i, column=1, sticky="ew" if values else "w", pady=3)

    def save() -> None:
        p = target or pupils.get(v["pupil"].get())
        if p is None:
            messagebox.showerror("GCSE result", "Choose a pupil.", parent=win)
            return
        s = subjects.get(v["subject"].get())
        data = {k: v[k].get() for k in ("qualification", "grade", "exam_board", "exam_year",
                                        "series")}
        data["subject_id"] = s.subject_id if s else ""
        try:
            G.record(p.pupil_id, data, actor=principal)
        except _ERRORS as e:
            messagebox.showerror("GCSE result", _problems(e), parent=win)
            return
        win.destroy()
        if after:
            after()

    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(10, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Save", command=save).pack(side="right", padx=(0, 6))


# ── The page ─────────────────────────────────────────────────────────

class MoveToSixthFormPage:
    TABS = ("Year 11", "A-level choices", "GCSE results", "Sent", "SEN register")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil = open_pupil
        activity_log.record("progression.view")
        ttk.Label(parent, text="Move to Sixth Form", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(parent, text="Send Year 11 pupils to the sixth form as applicants, with "
                               "their name, GCSE results and SEN details.",
                  foreground="#666").pack(anchor="w", pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._build_year11(self.tabs["Year 11"])
        self._build_choices(self.tabs["A-level choices"])
        self._build_results(self.tabs["GCSE results"])
        self._build_sent(self.tabs["Sent"])
        self._build_sen(self.tabs["SEN register"])
        self.book.select(self.TABS.index(state.get("tab", "Year 11")))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        {"Year 11": self.refresh_year11, "A-level choices": self.refresh_choices,
         "GCSE results": self.refresh_results,
         "Sent": self.refresh_sent, "SEN register": self.refresh_sen}[name]()

    def _err(self, title: str, e: Exception) -> None:
        messagebox.showerror(title, _problems(e), parent=self.parent.winfo_toplevel())

    def _view(self, tree: ttk.Treeview, key: str = "pupil") -> None:
        sel = tree.selection()
        if sel and self.open_pupil:
            pid = tree.set(sel[0], key) if key != "iid" else sel[0]
            if str(pid).isdigit():
                self.open_pupil(int(pid))

    # Year 11
    def _build_year11(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Search:").pack(side="left")
        self.y_search = tk.StringVar(value=self.state.get("y_search", ""))
        e = ttk.Entry(bar, textvariable=self.y_search, width=24)
        e.pack(side="left", padx=(4, 0))
        e.bind("<Return>", lambda _e: self.refresh_year11())
        ttk.Button(bar, text="Apply", command=self.refresh_year11).pack(side="left", padx=4)
        ttk.Button(bar, text="↻ Refresh", command=self.refresh_year11).pack(side="right")
        self.y_tree = _tree(tab, [("adm", "Adm no", 90), ("name", "Pupil", 220),
                                  ("form", "Form", 70), ("gcse", "GCSEs", 60),
                                  ("sen", "SEN", 150), ("stage", "Sixth form", 190),
                                  ("exams", "Exam results", 200)],
                            select="extended")
        self.y_tree.bind("<Double-1>", lambda _e: self._view(self.y_tree, "iid"))
        acts = ttk.Frame(tab)
        acts.pack(fill="x", pady=(6, 0))
        ttk.Button(acts, text="View profile",
                   command=lambda: self._view(self.y_tree, "iid")).pack(side="left")
        if SFP.is_sender(self.principal):
            ttk.Button(acts, text="Move to Sixth Form…", command=self.send_one).pack(
                side="left", padx=(6, 0))
            ttk.Button(acts, text="Send selected (no subjects)",
                       command=self.send_selected).pack(side="left", padx=(6, 0))
            ttk.Button(acts, text="Withdraw…", command=self.withdraw).pack(side="left",
                                                                          padx=(6, 0))
        if SEN.is_editor(self.principal):
            ttk.Button(acts, text="SEN details…", command=self.edit_sen).pack(side="left",
                                                                             padx=(6, 0))
        if G.is_editor(self.principal):
            ttk.Button(acts, text="Add GCSE result…", command=self.add_result_for).pack(
                side="left", padx=(6, 0))
        self.y_info = tk.StringVar()
        ttk.Label(tab, textvariable=self.y_info, foreground="#666").pack(anchor="w",
                                                                        pady=(4, 0))

    def refresh_year11(self) -> None:
        self.state["y_search"] = self.y_search.get()
        self.y_tree.delete(*self.y_tree.get_children())
        rows = SFP.cohort(search=self.y_search.get() or None)
        for c in rows:
            p = c.pupil
            sen = ("—" if p.sen_status == "N" else
                   p.sen_label + ("" if c.sen_recorded else " (details missing)"))
            self.y_tree.insert("", "end", iid=str(p.pupil_id), tags=(c.stage,), values=(
                p.admission_no, p.display_name, p.form_group or "", c.gcse_count or "—",
                sen, c.stage, c.exam_results or "—"))
        sent = sum(1 for c in rows if not c.can_send)
        self.y_info.set(f"{len(rows)} Year 11 pupil(s) on roll · {sent} with an open sixth "
                        "form application")

    # A-level choices
    def _build_choices(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Show:").pack(side="left")
        self.c_show = tk.StringVar(value=self.state.get("c_show", "all"))
        cb = ttk.Combobox(bar, textvariable=self.c_show, state="readonly", width=18,
                          values=("all", "not chosen", "needs new choices"))
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh_choices())
        ttk.Button(bar, text="↻ Refresh", command=self.refresh_choices).pack(side="right")
        ttk.Label(tab, text="Pupils choose three A-levels in their portal (or staff choose with "
                            "them). Each is checked against the sixth form's entry "
                            "requirements once results are released; a pupil who misses one "
                            "can switch to a course their results meet.", foreground="#666",
                  wraplength=1000, justify="left").pack(anchor="w", pady=(0, 6))
        self.c_tree = _tree(tab, [("adm", "Adm no", 90), ("name", "Pupil", 180),
                                  ("form", "Form", 60), ("c1", "A-level 1", 140),
                                  ("c2", "A-level 2", 140), ("c3", "A-level 3", 140),
                                  ("by", "Chosen by", 80), ("res", "Results", 130),
                                  ("alt", "Can choose from", 220),
                                  ("stage", "Sixth form", 150)])
        self.c_tree.bind("<Double-1>", lambda _e: self.course_detail())
        for tag, bg in (("bad", "#fde2e2"), ("warn", "#fff6d6"), ("good", "#e7f6ea")):
            self.c_tree.tag_configure(tag, background=bg)
        acts = ttk.Frame(tab)
        acts.pack(fill="x", pady=(6, 0))
        ttk.Button(acts, text="View profile",
                   command=lambda: self._view(self.c_tree, "iid")).pack(side="left")
        ttk.Button(acts, text="Courses and requirements…", command=self.course_detail).pack(
            side="left", padx=(6, 0))
        if SFP.is_sender(self.principal):
            ttk.Button(acts, text="Choose / change A-levels…", command=self.edit_choices).pack(
                side="left", padx=(6, 0))
        ttk.Button(acts, text="History", command=self.choice_history).pack(side="left",
                                                                         padx=(6, 0))
        self.c_info = tk.StringVar()
        ttk.Label(tab, textvariable=self.c_info, foreground="#666").pack(anchor="w",
                                                                        pady=(4, 0))
        self.c_rows: dict[str, dict] = {}

    def refresh_choices(self) -> None:
        self.state["c_show"] = self.c_show.get()
        self.c_tree.delete(*self.c_tree.get_children())
        rows = SC.cohort(show=self.c_show.get())
        self.c_rows = {}
        for st in rows:
            p, ch = st["pupil"], st["choices"] + ["", "", ""]
            tag = ("good" if st["all_met"] else "bad" if st["all_met"] is False
                   and "not met" in st["summary"] else "warn" if st["all_met"] is False
                   else "")
            c = SC.get(p.pupil_id)
            self.c_rows[str(p.pupil_id)] = st
            self.c_tree.insert("", "end", iid=str(p.pupil_id), tags=(tag,), values=(
                p.admission_no, p.display_name, p.form_group or "", ch[0], ch[1], ch[2],
                c.chosen_as if c else "", st["summary"],
                ", ".join(st["can_choose_from"]) if st["all_met"] is False else "",
                st["stage"]))
        need = sum(1 for st in rows if st["all_met"] is False)
        none = sum(1 for st in rows if not st["choices"])
        self.c_info.set(f"{len(rows)} pupil(s) · {none} not chosen · {need} need new choices")

    def _choice_pupil(self) -> dict | None:
        sel = self.c_tree.selection()
        if not sel:
            messagebox.showinfo("A-level choices", "Select a pupil first.",
                                parent=self.parent.winfo_toplevel())
            return None
        return self.c_rows.get(sel[0])

    def course_detail(self) -> None:
        st = self._choice_pupil()
        if not st:
            return
        lines = [f"{st['pupil'].display_name} - {st['summary']}", ""]
        if st["options"] is None:
            lines.append("The sixth form's course list isn't available.")
        for o in st["options"] or []:
            mark = "*" if o["course"] in st["choices"] else " "
            need = "; ".join(o["requirements"]) or "no entry requirements"
            out = ("awaited" if not st["results_known"] and o["requirements"]
                   else o["outcome"])
            block = "/".join(o.get("blocks") or [])
            block = f"  [block {block}{', full' if o.get('full') else ''}]" if block else ""
            lines.append(f"{mark} {o['course']:<24} {out:<10} {need}{block}")
            for x in o["checks"]:
                if st["results_known"] and x["outcome"] != "Met":
                    lines.append(f"      {x['requirement']}: {x['detail']}")
        lines += ["", "* = chosen"]
        blocks = st.get("blocks") or {}
        if SC.block_lines(blocks):
            lines += ["", f"Option blocks ({blocks['academic_year']}) - one course from "
                      "each block:"] + [f"  {b}" for b in SC.block_lines(blocks)]
            lines += [f"  ✗ {c}" for c in blocks.get("clashes") or []]
        win, frm = _dialog(self.parent, "Courses and requirements", "760x520")
        txt = tk.Text(frm, wrap="none", font=("TkFixedFont", 9))
        txt.insert("1.0", "\n".join(lines))
        txt.configure(state="disabled")
        txt.pack(fill="both", expand=True)
        ttk.Button(frm, text="Close", command=win.destroy).pack(anchor="e", pady=(6, 0))

    def edit_choices(self) -> None:
        st = self._choice_pupil()
        if not st:
            return
        mine = {c.lower() for c in st["choices"]}
        names = [o["course"] for o in st["options"] or []
                 if (not st["results_known"] or o["outcome"] in SC.STAFF_OK)
                 and (not o.get("full") or o["course"].lower() in mine)]
        lines = SC.block_lines(st.get("blocks"))
        win, frm = _dialog(self.parent, "A-level choices",
                           "460x" + str(260 + 18 * (len(lines) + 1 if lines else 0)))
        ttk.Label(frm, text=f"{st['pupil'].display_name}: " + (
            "results are in - courses whose requirements are met (or one grade short)."
            if st["results_known"] else "choose three different A-levels."),
            wraplength=420, justify="left").pack(anchor="w", pady=(0, 6))
        if lines:
            ttk.Label(frm, text="One course from each block (full courses can't be "
                                "chosen):\n" + "\n".join(lines), foreground="#555",
                      wraplength=420, justify="left").pack(anchor="w", pady=(0, 6))
        vars_ = []
        for i in range(3):
            v = tk.StringVar(value=st["choices"][i] if i < len(st["choices"]) else "")
            row = ttk.Frame(frm)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=f"A-level {i + 1}", width=10).pack(side="left")
            ttk.Combobox(row, textvariable=v, values=names, state="readonly",
                         width=32).pack(side="left")
            vars_.append(v)

        def save() -> None:
            try:
                out = SC.save(st["pupil"].pupil_id, [v.get() for v in vars_],
                              actor=self.principal)
            except _ERRORS as e:
                messagebox.showerror("A-level choices", _problems(e), parent=win)
                return
            win.destroy()
            messagebox.showinfo("A-level choices", f"Saved ({out['sixth_form']}).",
                                parent=self.parent.winfo_toplevel())
            self.refresh_choices()

        bar = ttk.Frame(frm)
        bar.pack(fill="x", pady=(10, 0))
        ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(bar, text="Save", command=save).pack(side="right")

    def choice_history(self) -> None:
        st = self._choice_pupil()
        if not st:
            return
        rows = SC.history(st["pupil"].pupil_id)
        messagebox.showinfo("A-level choice history", "\n".join(
            f"{h['at'][:16]}  {h['actor']} ({h['detail'].get('as')}): "
            f"{', '.join(h['detail'].get('from') or []) or '-'} → "
            f"{', '.join(h['detail'].get('to') or [])}" for h in rows) or "No changes yet.",
            parent=self.parent.winfo_toplevel())

    def _selected_pupils(self) -> list[P.Pupil]:
        out = []
        for iid in self.y_tree.selection():
            p = P.get_pupil(int(iid))
            if p:
                out.append(p)
        if not out:
            messagebox.showinfo("Move to Sixth Form", "Select a pupil first.",
                                parent=self.parent.winfo_toplevel())
        return out

    def send_one(self) -> None:
        ps = self._selected_pupils()
        if ps:
            send_dialog(self.parent, principal=self.principal, pupil=ps[0],
                        after=self.refresh_year11)

    def send_selected(self) -> None:
        ps = self._selected_pupils()
        if not ps or not messagebox.askyesno(
                "Move to Sixth Form", f"Send {len(ps)} pupil(s) to the sixth form as "
                "applicants?\n\nSEN details are held back (no consent recorded here) - use "
                "Move to Sixth Form… for a pupil whose family agreed to share them.",
                parent=self.parent.winfo_toplevel()):
            return
        try:
            out = SFP.send_many([p.pupil_id for p in ps], actor=self.principal)
        except _ERRORS as e:
            self._err("Move to Sixth Form", e)
            return
        msg = f"Sent: {len(out['sent'])}"
        if out["failed"]:
            msg += "\n\nNot sent:\n" + "\n".join(f"• {k}: {v}" for k, v in out["failed"].items())
        messagebox.showinfo("Move to Sixth Form", msg, parent=self.parent.winfo_toplevel())
        self.refresh_year11()

    def withdraw(self) -> None:
        ps = self._selected_pupils()
        if not ps:
            return
        from education_system.platform.delivery.gui.parented_dialogs import simpledialog
        reason = simpledialog.askstring("Withdraw", f"Why withdraw {ps[0].display_name}'s "
                                        "sixth form application?",
                                        parent=self.parent.winfo_toplevel())
        if reason is None:
            return
        try:
            SFP.withdraw(ps[0].pupil_id, actor=self.principal, reason=reason)
        except _ERRORS as e:
            self._err("Withdraw", e)
            return
        self.refresh_year11()

    def edit_sen(self) -> None:
        ps = self._selected_pupils()
        if ps:
            sen_dialog(self.parent, principal=self.principal, pupil=ps[0],
                       after=self.refresh_year11)

    def add_result_for(self) -> None:
        ps = self._selected_pupils()
        if ps:
            gcse_dialog(self.parent, principal=self.principal, pupil=ps[0],
                        after=self.refresh_year11)

    # GCSE results
    def _build_results(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        self.r_subjects = {f"{s.code} - {s.name}": s for s in S.list_subjects(active_only=False)}
        self.r_year = tk.StringVar(value=self.state.get("r_year", ALL))
        self.r_subject = tk.StringVar(value=self.state.get("r_subject", ALL))
        self.r_exam = tk.StringVar(value=self.state.get("r_exam", ALL))
        self.r_pupil = tk.StringVar(value=self.state.get("r_pupil", ""))
        for label, var, values, width in (
                ("Year", self.r_year, [ALL] + [str(y) for y in P.YEAR_GROUPS], 5),
                ("Subject", self.r_subject, [ALL] + list(self.r_subjects), 24),
                ("Exam year", self.r_exam, [ALL] + [str(G._today().year - i)
                                                     for i in range(5)], 7)):
            ttk.Label(bar, text=f"{label}:").pack(side="left")
            ttk.Combobox(bar, textvariable=var, values=values, width=width,
                         state="readonly").pack(side="left", padx=(4, 8))
        ttk.Label(bar, text="Pupil:").pack(side="left")
        ttk.Entry(bar, textvariable=self.r_pupil, width=16).pack(side="left", padx=4)
        ttk.Button(bar, text="Apply", command=self.refresh_results).pack(side="left")
        ttk.Button(bar, text="↻ Refresh", command=self.refresh_results).pack(side="right")
        self.r_tree = _tree(tab, [("adm", "Adm no", 90), ("name", "Pupil", 200),
                                  ("yr", "Yr", 40), ("subj", "Subject", 160),
                                  ("qual", "Qualification", 120), ("grade", "Grade", 60),
                                  ("board", "Board", 110), ("exam", "Year", 60),
                                  ("series", "Series", 80), ("pupil", "", 0)])
        self.r_tree.column("pupil", width=0, stretch=False)
        self.r_tree.bind("<Double-1>", lambda _e: self._view(self.r_tree))
        acts = ttk.Frame(tab)
        acts.pack(fill="x", pady=(6, 0))
        if G.is_editor(self.principal):
            ttk.Button(acts, text="Add…", command=lambda: gcse_dialog(
                self.parent, principal=self.principal, after=self.refresh_results)).pack(
                side="left")
            ttk.Button(acts, text="Edit…", command=self.edit_result).pack(side="left",
                                                                         padx=(6, 0))
            ttk.Button(acts, text="Delete", command=self.delete_result).pack(side="left",
                                                                            padx=(6, 0))
            ttk.Button(acts, text="Import results CSV…", command=self.import_results).pack(
                side="left", padx=(6, 0))
        ttk.Button(acts, text="Export CSV…", command=self.export_results).pack(side="left",
                                                                              padx=(6, 0))
        ttk.Button(acts, text="View profile", command=lambda: self._view(self.r_tree)).pack(
            side="left", padx=(6, 0))
        self.r_info = tk.StringVar()
        ttk.Label(tab, textvariable=self.r_info, foreground="#666").pack(anchor="w",
                                                                        pady=(4, 0))

    def _filters(self) -> dict:
        s = self.r_subjects.get(self.r_subject.get())
        return {"year_group": self.r_year.get() or None,
                "subject_id": s.subject_id if s else None,
                "exam_year": self.r_exam.get() or None, "pupil": self.r_pupil.get() or None}

    def refresh_results(self) -> None:
        for k in ("r_year", "r_subject", "r_exam", "r_pupil"):
            self.state[k] = getattr(self, k).get()
        self.r_tree.delete(*self.r_tree.get_children())
        rows = G.list_results(**self._filters())
        for r in rows:
            self.r_tree.insert("", "end", iid=str(r.result_id), values=(
                r.admission_no, r.pupil_name, r.year_group, f"{r.subject_code} {r.subject_name}",
                r.qualification, r.grade, r.exam_board or "", r.exam_year, r.series,
                r.pupil_id))
        passes = sum(r.passed for r in rows)
        self.r_info.set(f"{len(rows)} result(s) · {passes} at grade 4 or above")

    def _result(self) -> G.Result | None:
        sel = self.r_tree.selection()
        if not sel:
            messagebox.showinfo("GCSE results", "Select a result first.",
                                parent=self.parent.winfo_toplevel())
            return None
        return G.get(int(sel[0]))

    def edit_result(self) -> None:
        r = self._result()
        if r:
            gcse_dialog(self.parent, principal=self.principal, result=r,
                        after=self.refresh_results)

    def delete_result(self) -> None:
        r = self._result()
        if r is None or not messagebox.askyesno(
                "GCSE results", f"Delete {r.pupil_name}'s {r.subject_name} result "
                f"({r.grade})?", parent=self.parent.winfo_toplevel()):
            return
        try:
            G.delete(r.result_id, actor=self.principal)
        except _ERRORS as e:
            self._err("GCSE results", e)
            return
        self.refresh_results()

    def import_results(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.parent.winfo_toplevel(), title="Results-day CSV",
            filetypes=[("CSV", "*.csv"), ("All files", "*")])
        if not path:
            return
        try:
            n = G.import_csv(path, actor=self.principal)
        except _ERRORS as e:
            self._err("Import results", e)
            return
        except (OSError, UnicodeDecodeError) as e:
            self._err("Import results", e)
            return
        messagebox.showinfo("Import results", f"New: {n['record']} · changed: {n['change']} · "
                            f"unchanged: {n['unchanged']}", parent=self.parent.winfo_toplevel())
        self.refresh_results()

    def export_results(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self.parent.winfo_toplevel(), title="Export GCSE results",
            defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            n = G.export_csv(path, actor=self.principal, **self._filters())
        except (*_ERRORS, OSError) as e:
            self._err("Export", e)
            return
        messagebox.showinfo("Export", f"{n} result(s) written.",
                            parent=self.parent.winfo_toplevel())

    # Sent
    def _build_sent(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Each application and the stage the sixth form has reached "
                            "(updated by the sixth form).", foreground="#666").pack(side="left")
        ttk.Button(bar, text="↻ Refresh", command=self.refresh_sent).pack(side="right")
        if SFP.is_sender(self.principal) or ER.is_editor(self.principal):
            ttk.Button(bar, text="Send exam results", command=self.send_results).pack(
                side="right", padx=(0, 6))
        self.s_tree = _tree(tab, [("adm", "Adm no", 90), ("name", "Pupil", 200),
                                  ("dest", "Destination", 120), ("prog", "Subjects", 200),
                                  ("stage", "Stage", 170), ("detail", "Detail", 200),
                                  ("sent", "Sent", 130), ("results", "Results sent", 130),
                                  ("updated", "Updated", 130), ("pupil", "", 0)])
        self.s_tree.column("pupil", width=0, stretch=False)
        self.s_tree.bind("<Double-1>", lambda _e: self._view(self.s_tree))
        self.s_info = tk.StringVar()
        ttk.Label(tab, textvariable=self.s_info, foreground="#666").pack(anchor="w",
                                                                        pady=(4, 0))

    def refresh_sent(self) -> None:
        self.s_tree.delete(*self.s_tree.get_children())
        try:
            rows = SFP.sent()
        except Exception as e:  # noqa: BLE001 - the platform board is unreachable
            logger.exception("Post-16 board unavailable")
            self.s_info.set(f"The post-16 board is unavailable: {e}")
            return
        for p, a in rows:
            self.s_tree.insert("", "end", iid=a["transition_id"], tags=(a["stage"],), values=(
                p.admission_no if p else a["pupil_id"], p.display_name if p else "",
                a.get("destination_label") or SFP.DESTINATION_LABEL,
                a.get("programme_label") or "", a["stage"],
                a.get("offer_conditions") or a.get("interview_details") or "",
                (a.get("created_at") or "")[:16], _results_sent(a),
                (a.get("updated_at") or "")[:16], p.pupil_id if p else ""))
        self.s_info.set(f"{len(rows)} application(s) · exam results go on automatically when "
                        "the exams officer releases them")

    def send_results(self) -> None:
        sel = self.s_tree.selection()
        ids = sorted({int(self.s_tree.set(i, "pupil")) for i in sel
                      if str(self.s_tree.set(i, "pupil")).isdigit()}) or None
        what = f"{len(ids)} selected pupil(s)" if ids else "every open application"
        if not messagebox.askyesno(
                "Send exam results", f"Send the current exam results and entries for {what} "
                "to the sixth form?\n\nGrades still under embargo stay back.",
                parent=self.parent.winfo_toplevel()):
            return
        try:
            out = SFP.send_results(ids, actor=self.principal)
        except _ERRORS as e:
            self._err("Send exam results", e)
            return
        lines = [f"Sent for {len(out['sent'])} pupil(s)."]
        if out["skipped"]:
            lines.append("Not sent: " + "; ".join(f"{k} ({v})" for k, v in
                                                  out["skipped"].items()))
        messagebox.showinfo("Send exam results", "\n".join(lines),
                            parent=self.parent.winfo_toplevel())
        self.refresh_sent()

    # SEN register
    def _build_sen(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Year:").pack(side="left")
        self.n_year = tk.StringVar(value=self.state.get("n_year", "11"))
        cb = ttk.Combobox(bar, textvariable=self.n_year, values=[ALL] + [
            str(y) for y in P.YEAR_GROUPS], width=5, state="readonly")
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh_sen())
        ttk.Button(bar, text="↻ Refresh", command=self.refresh_sen).pack(side="right")
        self.n_tree = _tree(tab, [("adm", "Adm no", 90), ("name", "Pupil", 200),
                                  ("yr", "Yr", 40), ("status", "SEN", 120),
                                  ("need", "Primary need", 200), ("plan", "EHC plan", 120),
                                  ("detail", "Exam access", 200)])
        self.n_tree.bind("<Double-1>", lambda _e: self._view(self.n_tree, "iid"))
        acts = ttk.Frame(tab)
        acts.pack(fill="x", pady=(6, 0))
        if SEN.is_editor(self.principal):
            ttk.Button(acts, text="Edit SEN details…", command=self.edit_sen_row).pack(
                side="left")
        ttk.Button(acts, text="View profile",
                   command=lambda: self._view(self.n_tree, "iid")).pack(side="left",
                                                                         padx=(6, 0))

    def refresh_sen(self) -> None:
        self.state["n_year"] = self.n_year.get()
        self.n_tree.delete(*self.n_tree.get_children())
        for p, dt in SEN.register(year_group=int(self.n_year.get()) if self.n_year.get()
                                  else None):
            self.n_tree.insert("", "end", iid=str(p.pupil_id), values=(
                p.admission_no, p.display_name, p.year_group, p.sen_label,
                f"{dt.primary_need} - {dt.primary_label}" if dt and dt.primary_need
                else "Not recorded",
                (dt.ehcp_reference or "") if dt else "", (dt.exam_access or "") if dt else ""))

    def edit_sen_row(self) -> None:
        sel = self.n_tree.selection()
        p = P.get_pupil(int(sel[0])) if sel else None
        if p is None:
            messagebox.showinfo("SEN details", "Select a pupil first.",
                                parent=self.parent.winfo_toplevel())
            return
        sen_dialog(self.parent, principal=self.principal, pupil=p, after=self.refresh_sen)


def draw_move_to_sixth_form(parent: ttk.Frame, *, principal: Principal, state: dict,
                            open_pupil: Callable[[int], None] | None = None
                            ) -> MoveToSixthFormPage:
    return MoveToSixthFormPage(parent, principal=principal, state=state,
                               open_pupil=open_pupil)


# ── Pupil profile sections ───────────────────────────────────────────

def draw_profile_sen(parent: ttk.Frame, pupil: P.Pupil, *, principal: Principal,
                     on_changed: Callable[[], None]) -> None:
    if pupil.sen_status == "N" and SEN.get(pupil.pupil_id) is None:
        return
    box = ttk.LabelFrame(parent, text="SEN details", padding=8)
    box.pack(fill="x", pady=(8, 0))
    d = SEN.get(pupil.pupil_id)
    ttk.Label(box, text=SEN.summary_line(pupil), wraplength=760, justify="left").pack(
        anchor="w")
    if d:
        for label, value in (("Provision", d.provision), ("Strategies", d.strategies)):
            if value:
                ttk.Label(box, text=f"{label}: {value}", wraplength=760, justify="left",
                          foreground="#444").pack(anchor="w")
    if SEN.is_editor(principal):
        ttk.Button(box, text="Edit SEN details…", command=lambda: sen_dialog(
            parent, principal=principal, pupil=pupil, after=on_changed)).pack(anchor="e")


def draw_profile_gcses(parent: ttk.Frame, pupil: P.Pupil, *, principal: Principal,
                       on_changed: Callable[[], None]) -> None:
    rows = G.for_pupil(pupil.pupil_id)
    if not rows and not (G.is_editor(principal) and pupil.year_group == P.YEAR_GROUPS[-1]):
        return
    box = ttk.LabelFrame(parent, text="GCSE results", padding=8)
    box.pack(fill="x", pady=(8, 0))
    if rows:
        s = G.summary(pupil.pupil_id)
        ttk.Label(box, text=G.summary_line(pupil.pupil_id), wraplength=760,
                  justify="left").pack(anchor="w")
        ttk.Label(box, text=f"{s['passes']} at 4+, {s['strong']} at 5+"
                            + (f" · English {s['english']}" if s["english"] else "")
                            + (f" · Maths {s['maths']}" if s["maths"] else ""),
                  foreground="#555").pack(anchor="w")
    else:
        ttk.Label(box, text="No GCSE results recorded.", foreground="#777").pack(anchor="w")
    app = SFP.application_for(pupil.pupil_id)
    bar = ttk.Frame(box)
    bar.pack(fill="x", pady=(4, 0))
    if app:
        ttk.Label(bar, text=f"Sixth form: {app['stage']}", foreground="#555").pack(side="left")
    if G.is_editor(principal):
        ttk.Button(bar, text="Add GCSE result…", command=lambda: gcse_dialog(
            parent, principal=principal, pupil=pupil, after=on_changed)).pack(side="right")
    if (SFP.is_sender(principal) and pupil.roll_status == "on_roll"
            and pupil.year_group == P.YEAR_GROUPS[-1]
            and (app is None or app["stage"] in SFP.CLOSED_STAGES)):
        ttk.Button(bar, text="Move to Sixth Form…", command=lambda: send_dialog(
            parent, principal=principal, pupil=pupil, after=on_changed)).pack(
            side="right", padx=(0, 6))
