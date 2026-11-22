"""Exam Entries screen.

The old window is kept as the Entries tab: the summary line, the Year /
Board / Status filters and Apply, New / update, Edit, Set status, Delete and
Refresh, the columns ID, Pupil, Yr, Subj, Board, Spec, Tier, Cand#, Status,
Fee, double-click to edit, and the old entry dialog (Pupil ID, Subject,
Board, Spec code, Tier, Candidate #, Status, Entry date, Fee £, Notes) and
status dialog.

Added: an exam series picker; Generate from teaching groups, Make Final,
View, CSV import / export and History on the Entries tab; and tabs for
Series, Specifications, Candidates (candidate numbers and UCIs), Checks
(with access arrangements), Fees, and Board files (the exam centre, board
files and statements of entry). Rules live in :mod:`modules.examinations.domain.exam_entries`.
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
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
ALL = ""
TITLE = "GCSE Exam Entries"
_ERRORS = (EE.ValidationError, EE.PermissionDenied, EE.NotFound)
ROW_BG = {"Provisional": "#fff6d6", "Final": "#ffffff", "Withdrawn": "#eeeeee",
          "Cancelled": "#eeeeee", "error": "#fde2e2", "warning": "#fff6d6", "info": "#ffffff",
          "unsent": "#e8f0fe"}


_problems = W.problems


def _tree(parent, columns, height: int = 14) -> ttk.Treeview:
    return W.tree(parent, columns, height=height, select="extended",
                  stretch={"name", "detail", "text"}, tags=ROW_BG, minwidth=0)


def _dialog(owner: tk.Misc, title: str, size: str) -> tuple[tk.Toplevel, ttk.Frame]:
    return W.dialog(owner, title, size=size)


def _text_window(owner, title: str, text: str) -> None:
    W.text_window(owner, title, text, size="760x480")


def _form(frm: ttk.Frame, rows: list[tuple[str, tk.Widget]]) -> None:
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w", pady=2, padx=(0, 8))
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)


def _buttons(frm, row: int, win, save) -> None:
    btns = ttk.Frame(frm)
    btns.grid(row=row, column=0, columnspan=2, sticky="e", pady=(10, 0))
    ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="right", padx=(6, 0))
    ttk.Button(btns, text="Save", command=save).pack(side="right")


def _spec_label(x: EE.Spec) -> str:
    return f"#{x.spec_id} {x.subject_name} - {x.exam_board} {x.spec_code}" + (
        " (tiered)" if x.tiered else "")


# ── Old dialogs ──────────────────────────────────────────────────────

def entry_dialog(owner, *, principal: Principal, series: EE.ExamSeries,
                 entry: EE.ExamEntry | None = None,
                 after: Callable[[], None] | None = None) -> None:
    """The old "New / update entry" and "Edit entry" dialog."""
    win, frm = _dialog(owner, f"Edit entry #{entry.entry_id}" if entry
                       else "New / update entry", "560x560")
    specs = EE.list_specs(active_only=not entry)
    if entry and all(x.spec_id != entry.spec_id for x in specs):
        specs.append(EE.get_spec(entry.spec_id))
    spec_map = {_spec_label(x): x for x in specs}
    v = {
        "pupil": tk.StringVar(value=entry.admission_no if entry else ""),
        "spec": tk.StringVar(value=next((k for k, x in spec_map.items()
                                         if entry and x.spec_id == entry.spec_id), "")),
        "board": tk.StringVar(value=entry.exam_board if entry else ""),
        "spec_code": tk.StringVar(value=entry.spec_code if entry else ""),
        "tier": tk.StringVar(value=entry.tier if entry else EE.DEFAULT_TIER),
        "cand": tk.StringVar(value=(entry.candidate_number or "") if entry else ""),
        "status": tk.StringVar(value=entry.entry_status if entry else EE.DEFAULT_ENTRY_STATUS),
        "date": tk.StringVar(value=entry.entry_date if entry else "(today)"),
        "fee": tk.StringVar(value=EE._num(entry.fee) if entry and entry.fee_manual else ""),
        "payer": tk.StringVar(value=entry.fee_payer if entry else "School"),
    }
    resit = tk.BooleanVar(value=bool(entry and entry.resit))
    who = tk.StringVar(value=entry.pupil_name if entry else "")
    fee_hint = tk.StringVar()

    pupil_e = ttk.Entry(frm, textvariable=v["pupil"], width=16,
                        state="readonly" if entry else "normal")
    spec_cb = ttk.Combobox(frm, textvariable=v["spec"], values=list(spec_map),
                           state="disabled" if entry else "readonly", width=46)
    tier_cb = ttk.Combobox(frm, textvariable=v["tier"], values=list(EE.TIERS),
                           state="readonly", width=12)
    status_cb = ttk.Combobox(frm, textvariable=v["status"], values=["Provisional", "Final"],
                             state="disabled" if entry else "readonly", width=14)
    cand_e = ttk.Entry(frm, textvariable=v["cand"], width=10,
                       state="normal" if EE.is_editor(principal) else "readonly")
    rows = [
        ("Pupil ID:", pupil_e),
        ("", ttk.Label(frm, textvariable=who, foreground="#555")),
        ("Subject:", spec_cb),
        ("Board:", ttk.Entry(frm, textvariable=v["board"], state="readonly", width=16)),
        ("Spec code:", ttk.Entry(frm, textvariable=v["spec_code"], state="readonly", width=16)),
        ("Tier:", tier_cb),
        ("Candidate #:", cand_e),
        ("Status:", status_cb),
        ("Entry date:", ttk.Entry(frm, textvariable=v["date"], state="readonly", width=14)),
        ("Fee £:", ttk.Entry(frm, textvariable=v["fee"], width=10)),
        ("", ttk.Label(frm, textvariable=fee_hint, foreground="#777")),
        ("Fee payer:", ttk.Combobox(frm, textvariable=v["payer"], values=list(EE.FEE_PAYERS),
                                    state="readonly", width=10)),
        ("", ttk.Checkbutton(frm, text="Resit", variable=resit)),
    ]
    _form(frm, rows)
    ttk.Label(frm, text="Notes:").grid(row=len(rows), column=0, sticky="nw", pady=2)
    notes = tk.Text(frm, width=40, height=3, wrap="word")
    notes.insert("1.0", (entry.notes or "") if entry else "")
    notes.grid(row=len(rows), column=1, sticky="ew", pady=2)

    def show_pupil(_e=None) -> None:
        if entry:
            return
        ref = v["pupil"].get().strip()
        p = P.find_by_reference(ref) if ref else None
        who.set(f"{p.display_name} (Year {p.year_group})" if p else
                ("No pupil with that admission number" if ref else ""))
        c = EE.candidate(p.pupil_id) if p else None
        v["cand"].set(c.candidate_number if c else "")

    def show_spec(_e=None) -> None:
        x = spec_map.get(v["spec"].get())
        if not x:
            return
        v["board"].set(x.exam_board)
        v["spec_code"].set(x.spec_code)
        if not x.tiered:
            v["tier"].set("N/A")
        fee_hint.set("Blank = automatic fee: " + EE.money(x.fee)
                     + (f", late {EE.money(x.late_fee)}" if x.late_fee is not None else ""))

    pupil_e.bind("<FocusOut>", show_pupil)
    pupil_e.bind("<Return>", show_pupil)
    spec_cb.bind("<<ComboboxSelected>>", show_spec)
    show_spec()
    if entry and not entry.fee_manual:
        fee_hint.set(f"Automatic: {EE.money(entry.fee)} (type a fee to override)")

    def save() -> None:
        x = spec_map.get(v["spec"].get())
        data = {"series_id": series.series_id, "pupil_id": v["pupil"].get().strip(),
                "spec_id": x.spec_id if x else None, "tier": v["tier"].get(),
                "fee": v["fee"].get().strip(), "fee_payer": v["payer"].get(),
                "resit": resit.get(), "notes": notes.get("1.0", "end").strip()}
        try:
            cand = v["cand"].get().strip()
            if EE.is_editor(principal) and cand:
                p = (P.get_pupil(entry.pupil_id) if entry
                     else P.find_by_reference(data["pupil_id"]))
                cur = EE.candidate(p.pupil_id) if p else None
                if p and (cur is None or cur.candidate_number != cand):
                    EE.set_candidate(p.pupil_id, candidate_number=cand, actor=principal)
            if entry:
                data = {k: data[k] for k in ("tier", "fee", "fee_payer", "resit", "notes")}
                EE.update_entry(entry.entry_id, data, actor=principal)
            else:
                data["entry_status"] = v["status"].get()
                e = EE.upsert(data, actor=principal)
                messagebox.showinfo(TITLE, f"Saved {e.admission_no} / {e.subject_code} "
                                           f"({e.exam_board} {e.tier}, {e.entry_status})",
                                    parent=win)
        except _ERRORS as e:
            messagebox.showerror(TITLE, _problems(e), parent=win)
            return
        win.destroy()
        if after:
            after()

    _buttons(frm, len(rows) + 1, win, save)


def status_dialog(owner, *, principal: Principal, entry: EE.ExamEntry,
                  after: Callable[[], None] | None = None) -> None:
    """The old Set status dialog (with a reason for the record)."""
    win, frm = _dialog(owner, f"Status - #{entry.entry_id}", "400x230")
    ttk.Label(frm, text=f"{entry.pupil_name} / {entry.subject_code} {entry.spec_code}").pack(
        anchor="w")
    ttk.Label(frm, text=f"Current: {entry.entry_status}", foreground="#666").pack(
        anchor="w", pady=(0, 8))
    new = tk.StringVar(value=entry.entry_status)
    ttk.Combobox(frm, textvariable=new, values=list(EE.ENTRY_STATUSES),
                 state="readonly").pack(fill="x")
    ttk.Label(frm, text="Reason (optional):").pack(anchor="w", pady=(8, 0))
    reason = tk.StringVar()
    ttk.Entry(frm, textvariable=reason).pack(fill="x")

    def save() -> None:
        try:
            EE.set_status(entry.entry_id, new.get(), actor=principal, reason=reason.get())
        except _ERRORS as e:
            messagebox.showerror(TITLE, _problems(e), parent=win)
            return
        win.destroy()
        if after:
            after()

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(10, 0))
    ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=save).pack(side="right")


def series_dialog(owner, *, principal: Principal, series: EE.ExamSeries | None = None,
                  after: Callable[[], None] | None = None) -> None:
    win, frm = _dialog(owner, "Edit series" if series else "New exam series", "520x380")
    v = {k: tk.StringVar(value=str((getattr(series, k) if series else d) or "")) for k, d in (
        ("name", ""), ("season", "June"), ("exam_year", ""), ("entry_deadline", ""),
        ("late_deadline", ""), ("results_day", ""))}
    _form(frm, [
        ("Name (blank = season + year):", ttk.Entry(frm, textvariable=v["name"], width=30)),
        ("Season:", ttk.Combobox(frm, textvariable=v["season"], values=list(EE.SEASONS),
                                 state="readonly", width=12)),
        ("Exam year:", ttk.Entry(frm, textvariable=v["exam_year"], width=8)),
        ("Entry deadline:", ttk.Entry(frm, textvariable=v["entry_deadline"], width=14)),
        ("Late deadline:", ttk.Entry(frm, textvariable=v["late_deadline"], width=14)),
        ("Results day:", ttk.Entry(frm, textvariable=v["results_day"], width=14)),
    ])
    ttk.Label(frm, text="Notes:").grid(row=6, column=0, sticky="nw", pady=2)
    notes = tk.Text(frm, height=4, wrap="word")
    notes.insert("1.0", (series.notes or "") if series else "")
    notes.grid(row=6, column=1, sticky="nsew", pady=2)

    def save() -> None:
        data = {k: x.get() for k, x in v.items()}
        data["notes"] = notes.get("1.0", "end").strip()
        try:
            if series:
                EE.update_series(series.series_id, data, actor=principal)
            else:
                EE.create_series(data, actor=principal)
        except _ERRORS as e:
            messagebox.showerror("Exam series", _problems(e), parent=win)
            return
        win.destroy()
        if after:
            after()

    _buttons(frm, 7, win, save)


def spec_dialog(owner, *, principal: Principal, spec: EE.Spec | None = None,
                after: Callable[[], None] | None = None) -> None:
    win, frm = _dialog(owner, "Edit specification" if spec else "New specification",
                       "560x520")
    subjects = {s.label: s for s in S.list_subjects(active_only=not spec)}
    sub_label = next((k for k, s in subjects.items() if spec and s.subject_id == spec.subject_id),
                     "")
    v = {k: tk.StringVar(value=str((getattr(spec, k) if spec else d) or "")) for k, d in (
        ("exam_board", EE.DEFAULT_BOARD), ("spec_code", ""), ("title", ""),
        ("qualification", "GCSE"), ("entry_code", ""), ("foundation_code", ""),
        ("higher_code", ""), ("fee", ""), ("late_fee", ""))}
    if spec:
        v["fee"].set(EE._num(spec.fee))
        v["late_fee"].set(EE._num(spec.late_fee))
    subject = tk.StringVar(value=sub_label)
    tiered = tk.BooleanVar(value=bool(spec and spec.tiered))
    _form(frm, [
        ("Subject:", ttk.Combobox(frm, textvariable=subject, values=list(subjects),
                                  state="readonly", width=36)),
        ("Exam board:", ttk.Combobox(frm, textvariable=v["exam_board"],
                                     values=list(EE.EXAM_BOARDS), state="readonly", width=18)),
        ("Spec code:", ttk.Entry(frm, textvariable=v["spec_code"], width=14)),
        ("Title:", ttk.Entry(frm, textvariable=v["title"], width=36)),
        ("Qualification:", ttk.Combobox(frm, textvariable=v["qualification"],
                                        values=list(EE.QUALIFICATIONS), state="readonly",
                                        width=18)),
        ("", ttk.Checkbutton(frm, text="Tiered (Foundation / Higher)", variable=tiered)),
        ("Entry code:", ttk.Entry(frm, textvariable=v["entry_code"], width=14)),
        ("Foundation code:", ttk.Entry(frm, textvariable=v["foundation_code"], width=14)),
        ("Higher code:", ttk.Entry(frm, textvariable=v["higher_code"], width=14)),
        ("Fee £:", ttk.Entry(frm, textvariable=v["fee"], width=10)),
        ("Late fee £:", ttk.Entry(frm, textvariable=v["late_fee"], width=10)),
    ])

    def save() -> None:
        s = subjects.get(subject.get())
        data = {k: x.get() for k, x in v.items()}
        data.update(subject_id=s.subject_id if s else "", tiered=tiered.get())
        try:
            if spec:
                EE.update_spec(spec.spec_id, data, actor=principal)
            else:
                EE.create_spec(data, actor=principal)
        except _ERRORS as e:
            messagebox.showerror("Specification", _problems(e), parent=win)
            return
        win.destroy()
        if after:
            after()

    _buttons(frm, 11, win, save)


def candidate_dialog(owner, *, principal: Principal, pupil: P.Pupil,
                     after: Callable[[], None] | None = None) -> None:
    c = EE.candidate(pupil.pupil_id)
    win, frm = _dialog(owner, f"Candidate - {pupil.display_name}", "420x200")
    num = tk.StringVar(value=c.candidate_number if c else "")
    uci = tk.StringVar(value=(c.uci or "") if c else "")
    _form(frm, [("Candidate number (blank = next free):", ttk.Entry(frm, textvariable=num,
                                                                     width=8)),
                ("UCI (13 characters):", ttk.Entry(frm, textvariable=uci, width=18))])

    def save() -> None:
        try:
            EE.set_candidate(pupil.pupil_id, candidate_number=num.get(), uci=uci.get(),
                             actor=principal)
        except _ERRORS as e:
            messagebox.showerror("Candidate", _problems(e), parent=win)
            return
        win.destroy()
        if after:
            after()

    _buttons(frm, 2, win, save)


def centre_dialog(owner, *, principal: Principal, after: Callable[[], None] | None = None
                  ) -> None:
    c = EE.get_centre()
    win, frm = _dialog(owner, "Exam centre", "460x220")
    v = {k: tk.StringVar(value=getattr(c, k) or "") for k in (
        "centre_number", "centre_name", "officer_name", "officer_email")}
    _form(frm, [("Centre number:", ttk.Entry(frm, textvariable=v["centre_number"], width=8)),
                ("Centre name:", ttk.Entry(frm, textvariable=v["centre_name"], width=30)),
                ("Exams officer:", ttk.Entry(frm, textvariable=v["officer_name"], width=30)),
                ("Officer e-mail:", ttk.Entry(frm, textvariable=v["officer_email"], width=30))])

    def save() -> None:
        try:
            EE.update_centre({k: x.get() for k, x in v.items()}, actor=principal)
        except _ERRORS as e:
            messagebox.showerror("Exam centre", _problems(e), parent=win)
            return
        win.destroy()
        if after:
            after()

    _buttons(frm, 4, win, save)


# ── The page ─────────────────────────────────────────────────────────

class ExamEntriesPage:
    TABS = ("Entries", "Series", "Specifications", "Candidates", "Checks", "Fees",
            "Board files")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None,
                 on_status: Callable[[str], None] | None = None) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil, self.on_status = open_pupil, on_status
        self.editor = EE.is_editor(principal)
        activity_log.record("exam.entries.view")
        ttk.Label(parent, text=TITLE, font=("", 16, "bold")).pack(anchor="w")
        top = ttk.Frame(parent)
        top.pack(fill="x", pady=(2, 4))
        ttk.Label(top, text="Exam series:").pack(side="left")
        self.series_var = tk.StringVar()
        self.series_cb = ttk.Combobox(top, textvariable=self.series_var, state="readonly",
                                      width=30)
        self.series_cb.pack(side="left", padx=4)
        self.series_cb.bind("<<ComboboxSelected>>", lambda _e: self._series_changed())
        self.info_var = tk.StringVar()
        ttk.Label(top, textvariable=self.info_var, foreground="#666").pack(side="left", padx=8)
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(
            anchor="w", pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        for n in self.TABS:
            getattr(self, "_build_" + n.lower().replace(" ", "_"))(self.tabs[n])
        self._load_series_choices()
        self.book.select(self.TABS.index(state.get("tab", "Entries")))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    # helpers
    def _top(self):
        return self.parent.winfo_toplevel()

    def _err(self, e: Exception, title: str = TITLE) -> None:
        messagebox.showerror(title, _problems(e), parent=self._top())

    def _info(self, text: str) -> None:
        messagebox.showinfo(TITLE, text, parent=self._top())

    def _status(self, text: str) -> None:
        if self.on_status:
            self.on_status(text)

    def _load_series_choices(self) -> None:
        self.series_map = {f"{s.name} ({s.status})": s for s in EE.list_series()}
        self.series_cb.configure(values=list(self.series_map))
        want = self.state.get("series_id")
        if want is None:
            cur = EE.current_series()
            want = cur.series_id if cur else None
        label = next((k for k, s in self.series_map.items() if s.series_id == want), None)
        if label is None and self.series_map:
            label = next(iter(self.series_map))
        self.series_var.set(label or "")
        self._show_info()

    def series(self) -> EE.ExamSeries | None:
        s = self.series_map.get(self.series_var.get())
        try:
            return EE.get_series(s.series_id) if s else None
        except EE.NotFound:
            return None

    def _need_series(self) -> EE.ExamSeries | None:
        s = self.series()
        if s is None:
            self._info("Create an exam series first (Series tab).")
        return s

    def _show_info(self) -> None:
        s = self.series()
        self.info_var.set("" if s is None else f"{s.status} · {EE.deadline_text(s)}")

    def _series_changed(self) -> None:
        s = self.series()
        self.state["series_id"] = s.series_id if s else None
        self._show_info()
        self._on_tab()

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        try:
            getattr(self, "refresh_" + name.lower().replace(" ", "_"))()
        except _ERRORS as e:
            self._err(e)
        self._summary()

    def _summary(self) -> None:
        s = self.series()
        if s is None:
            self.summary_var.set("No exam series yet - add one on the Series tab.")
            return
        try:
            yg = self.f_year.get() or None
            d = EE.cohort_summary(series_id=s.series_id, year_group=yg)
        except _ERRORS:
            return
        self.summary_var.set(
            f"Total: {d['total']}    " + "    ".join(f"{k}: {v}" for k, v in
                                                     d["by_status"].items())
            + f"    Fees: {EE.money(d['total_fees'])}"
            + (f" (+{EE.money(d['estimated'])} provisional)" if d["estimated"] else "")
            + (f"    Not sent to board: {d['unsent']}" if d["unsent"] else ""))

    # Entries (the old window)
    def _build_entries(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        self.f_year = tk.StringVar(value=self.state.get("f_year", ALL))
        self.f_board = tk.StringVar(value=self.state.get("f_board", ALL))
        self.f_status = tk.StringVar(value=self.state.get("f_status", ALL))
        for label, var, values, w in (
                ("Year:", self.f_year, [ALL, *map(str, P.YEAR_GROUPS)], 5),
                ("Board:", self.f_board, [ALL, *EE.EXAM_BOARDS], 14),
                ("Status:", self.f_status, [ALL, *EE.ENTRY_STATUSES], 11)):
            ttk.Label(bar, text=label).pack(side="left", padx=(0, 4))
            cb = ttk.Combobox(bar, textvariable=var, values=values, state="readonly", width=w)
            cb.pack(side="left", padx=(0, 6))
            cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh_entries())
        ttk.Button(bar, text="Apply", command=self.refresh_entries).pack(side="left", padx=2)
        if self.editor:
            ttk.Button(bar, text="New / update", command=self.new_entry).pack(side="left",
                                                                             padx=2)
            ttk.Button(bar, text="Edit", command=self.edit_entry).pack(side="left", padx=2)
            ttk.Button(bar, text="Set status", command=self.set_status).pack(side="left",
                                                                            padx=2)
            ttk.Button(bar, text="Delete", command=self.delete_entry).pack(side="left", padx=2)
        else:
            ttk.Button(bar, text="Set tier", command=self.teacher_tier).pack(side="left",
                                                                            padx=2)
        ttk.Button(bar, text="Refresh", command=self.refresh_entries).pack(side="left", padx=2)
        self.e_tree = _tree(tab, [
            ("id", "ID", 50), ("pupil", "Pupil", 90), ("name", "Name", 170), ("year", "Yr", 40),
            ("subj", "Subj", 70), ("board", "Board", 90), ("spec", "Spec", 80),
            ("code", "Entry code", 80), ("tier", "Tier", 85), ("cand", "Cand#", 60),
            ("status", "Status", 90), ("fee", "Fee", 70), ("sent", "Sent", 90)], height=16)
        self.e_tree.bind("<Double-1>", lambda _e: (self.edit_entry() if self.editor
                                                   else self.view_entry()))
        acts = ttk.Frame(tab)
        acts.pack(fill="x", pady=(6, 0))
        if self.editor:
            ttk.Button(acts, text="Generate from teaching groups…",
                       command=self.generate).pack(side="left")
            ttk.Button(acts, text="Make selected Final", command=self.make_final).pack(
                side="left", padx=(4, 0))
            ttk.Button(acts, text="Make all provisional Final",
                       command=lambda: self.make_final(all_=True)).pack(side="left",
                                                                         padx=(4, 0))
            ttk.Button(acts, text="Import CSV…", command=self.import_csv).pack(side="left",
                                                                              padx=(4, 0))
        ttk.Button(acts, text="View", command=self.view_entry).pack(side="left", padx=(4, 0))
        ttk.Button(acts, text="Pupil profile", command=self.profile).pack(side="left",
                                                                         padx=(4, 0))
        ttk.Button(acts, text="Export CSV…", command=self.export_csv).pack(side="left",
                                                                          padx=(4, 0))
        ttk.Button(acts, text="History", command=self.show_history).pack(side="left",
                                                                        padx=(4, 0))

    def refresh_entries(self) -> None:
        for k in ("f_year", "f_board", "f_status"):
            self.state[k] = getattr(self, k).get()
        self.e_tree.delete(*self.e_tree.get_children())
        s = self.series()
        if s is None:
            return
        rows = EE.list_entries(series_id=s.series_id, year_group=self.f_year.get() or None,
                               exam_board=self.f_board.get() or None,
                               entry_status=self.f_status.get() or None)
        for e in rows:
            self.e_tree.insert("", "end", iid=str(e.entry_id), tags=(
                "unsent" if e.unsent else e.entry_status,), values=(
                e.entry_id, e.admission_no, e.pupil_name, e.pupil_year or "-",
                e.subject_code or "?", e.exam_board, e.spec_code or "-", e.entry_code, e.tier,
                e.candidate_number or "-", e.entry_status + (" (late)" if e.late else ""),
                EE.money(e.fee) if e.fee is not None else "-",
                ("to send" if e.unsent else (e.submitted_on or ""))))
        self._status(f"GCSE Entries: {len(rows)} record(s)")
        self._summary()

    def _selected(self, many: bool = False):
        sel = self.e_tree.selection()
        if not sel:
            self._info("Select an entry first.")
            return [] if many else None
        if many:
            return [int(i) for i in sel]
        return EE.get(int(sel[0]))

    def new_entry(self) -> None:
        s = self._need_series()
        if s:
            entry_dialog(self.parent, principal=self.principal, series=s,
                         after=self.refresh_entries)

    def edit_entry(self) -> None:
        e = self._selected()
        s = self.series()
        if e and s:
            entry_dialog(self.parent, principal=self.principal, series=s, entry=e,
                         after=self.refresh_entries)

    def set_status(self) -> None:
        e = self._selected()
        if e:
            status_dialog(self.parent, principal=self.principal, entry=e,
                          after=self.refresh_entries)

    def delete_entry(self) -> None:
        e = self._selected()
        if not e or not messagebox.askyesno(
                "Delete entry", f"Delete entry for {e.admission_no} / {e.subject_code}?",
                parent=self._top()):
            return
        try:
            EE.delete(e.entry_id, actor=self.principal)
        except _ERRORS as ex:
            self._err(ex)
        self.refresh_entries()

    def teacher_tier(self) -> None:
        e = self._selected()
        if not e:
            return
        win, frm = _dialog(self.parent, f"Tier - {e.pupil_name} {e.subject_code}", "340x150")
        tier = tk.StringVar(value=e.tier)
        ttk.Combobox(frm, textvariable=tier, values=list(EE.TIERS), state="readonly").pack(
            fill="x")

        def save() -> None:
            try:
                EE.set_tier(e.entry_id, tier.get(), actor=self.principal)
            except _ERRORS as ex:
                messagebox.showerror(TITLE, _problems(ex), parent=win)
                return
            win.destroy()
            self.refresh_entries()

        ttk.Button(frm, text="Save", command=save).pack(anchor="e", pady=(10, 0))

    def view_entry(self) -> None:
        e = self._selected()
        if not e:
            return
        lines = [f"Entry #{e.entry_id} - {e.series_name}",
                 f"Pupil:        {e.admission_no} {e.pupil_name} (Year {e.pupil_year})"
                 + ("" if e.on_roll else "  ** no longer on roll **"),
                 f"Candidate #:  {e.candidate_number or '-'}   UCI: {e.uci or '-'}",
                 f"Subject:      {e.subject_name} ({e.subject_code})",
                 f"Board / spec: {e.exam_board} {e.spec_code} - {e.spec_title} "
                 f"({e.qualification})",
                 f"Entry code:   {e.entry_code}   Tier: {e.tier}",
                 f"Status:       {e.entry_status}" + (" (late)" if e.late else "")
                 + f"   since {e.entry_date}",
                 f"Fee:          {EE.money(e.fee)}" + (" (typed in)" if e.fee_manual else "")
                 + f"   paid by {e.fee_payer}" + ("   resit" if e.resit else ""),
                 f"Board:        " + ("change not sent yet" if e.unsent else
                                      (f"sent {e.submitted_on}" if e.submitted_on
                                       else "not sent")),
                 f"Notes:        {e.notes or '-'}", "", "History:"]
        for h in EE.history(pupil_id=e.pupil_id):
            if h["entry_id"] == e.entry_id:
                lines.append(f"  {h['at']}  {h['actor']:<12} {h['action']:<14} {h['detail']}")
        _text_window(self.parent, f"Entry #{e.entry_id}", "\n".join(lines))

    def profile(self) -> None:
        e = self._selected()
        if e and self.open_pupil:
            self.open_pupil(e.pupil_id)

    def generate(self) -> None:
        s = self._need_series()
        if not s:
            return
        win, frm = _dialog(self.parent, "Generate provisional entries", "460x200")
        yg = tk.StringVar(value="11")
        _form(frm, [("Year group:", ttk.Combobox(frm, textvariable=yg, values=[
            str(y) for y in P.YEAR_GROUPS], state="readonly", width=6))])
        ttk.Label(frm, text="Everyone in a teaching group for each specification's subject "
                            "who isn't entered yet gets a provisional entry, with the tier "
                            "from their last mock.", wraplength=400, foreground="#555").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=6)

        def go() -> None:
            try:
                r = EE.generate(s.series_id, int(yg.get()), actor=self.principal)
            except _ERRORS as e:
                messagebox.showerror(TITLE, _problems(e), parent=win)
                return
            win.destroy()
            msg = (f"{r['created']} provisional entr{'y' if r['created'] == 1 else 'ies'} made"
                   f" ({r['tiers']} with a tier from the mocks); {r['already']} already "
                   "entered.")
            if r["several_specs"]:
                msg += ("\n\nMore than one specification - enter these by hand: "
                        + ", ".join(r["several_specs"]))
            if r["no_pupils"]:
                msg += "\n\nNobody in a teaching group for: " + ", ".join(r["no_pupils"])
            self._info(msg)
            self.refresh_entries()

        btns = ttk.Frame(frm)
        btns.grid(row=2, column=0, columnspan=2, sticky="e")
        ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(btns, text="Generate", command=go).pack(side="right")

    def make_final(self, all_: bool = False) -> None:
        s = self._need_series()
        if not s:
            return
        ids = None if all_ else self._selected(many=True)
        if ids == []:
            return
        if all_ and not messagebox.askyesno(
                TITLE, f"Make every provisional entry in {s.name} Final?\n\n"
                       + EE.deadline_text(s), parent=self._top()):
            return
        try:
            r = EE.finalise(s.series_id, entry_ids=ids, actor=self.principal)
        except _ERRORS as e:
            self._err(e)
            return
        msg = f"{r['made']} entr{'y' if r['made'] == 1 else 'ies'} made Final."
        if r["skipped"]:
            msg += "\n\nNot ready:\n" + "\n".join(
                f"• {e.pupil_name} {e.subject_code}: {why}" for e, why in r["skipped"][:25])
        self._info(msg)
        self.refresh_entries()

    def import_csv(self) -> None:
        s = self._need_series()
        if not s:
            return
        path = filedialog.askopenfilename(parent=self._top(), title="Import entries",
                                          filetypes=[("CSV", "*.csv"), ("All files", "*")])
        if not path:
            return
        try:
            n = EE.import_entries(s.series_id, path, actor=self.principal)
        except (OSError, *_ERRORS) as e:
            self._err(e)
            return
        self._info(f"Imported {n} entr{'y' if n == 1 else 'ies'}.")
        self.refresh_entries()

    def export_csv(self) -> None:
        s = self._need_series()
        if not s:
            return
        path = filedialog.asksaveasfilename(parent=self._top(), defaultextension=".csv",
                                            initialfile=f"entries-{s.name}.csv",
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            n = EE.export_entries(s.series_id, path, actor=self.principal)
        except (OSError, *_ERRORS) as e:
            self._err(e)
            return
        self._info(f"Saved {n} entr{'y' if n == 1 else 'ies'}.")

    def show_history(self) -> None:
        s = self._need_series()
        if s:
            _text_window(self.parent, f"History - {s.name}", "\n".join(
                f"{h['at']}  {h['actor']:<12} {h['action']:<14} "
                + (f"entry {h['entry_id']} " if h["entry_id"] else "") + str(h["detail"])
                for h in EE.history(series_id=s.series_id)) or "No changes yet.")

    # Series
    def _build_series(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        if self.editor:
            ttk.Button(bar, text="New series", command=lambda: series_dialog(
                tab, principal=self.principal, after=self._after_series)).pack(side="left")
            ttk.Button(bar, text="Edit", command=self.edit_series).pack(side="left",
                                                                        padx=(4, 0))
            for st in EE.SERIES_STATUSES:
                ttk.Button(bar, text=f"Mark {st}", command=lambda st=st: self.series_status(
                    st)).pack(side="left", padx=(4, 0))
            ttk.Button(bar, text="Delete", command=self.delete_series).pack(side="left",
                                                                            padx=(4, 0))
        ttk.Button(bar, text="Refresh", command=self.refresh_series).pack(side="right")
        self.s_tree = _tree(tab, [("id", "ID", 50), ("name", "Name", 160),
                                  ("status", "Status", 80), ("entry", "Entry deadline", 110),
                                  ("late", "Late deadline", 110), ("results", "Results day", 110),
                                  ("entries", "Entries", 70), ("detail", "Deadline", 300)])
        self.s_tree.bind("<Double-1>", lambda _e: self._pick_series(go=True))

    def _after_series(self) -> None:
        self._load_series_choices()
        self.refresh_series()

    def refresh_series(self) -> None:
        self.s_tree.delete(*self.s_tree.get_children())
        for s in EE.list_series():
            n = len(EE.list_entries(series_id=s.series_id))
            self.s_tree.insert("", "end", iid=str(s.series_id), values=(
                s.series_id, s.name, s.status, s.entry_deadline or "", s.late_deadline or "",
                s.results_day or "", n, EE.deadline_text(s)))

    def _pick_series(self, go: bool = False) -> EE.ExamSeries | None:
        sel = self.s_tree.selection()
        if not sel:
            self._info("Select a series first.")
            return None
        s = EE.get_series(int(sel[0]))
        if go:
            self.state["series_id"] = s.series_id
            self._load_series_choices()
            self.book.select(0)
        return s

    def edit_series(self) -> None:
        s = self._pick_series()
        if s:
            series_dialog(self.parent, principal=self.principal, series=s,
                          after=self._after_series)

    def series_status(self, status: str) -> None:
        s = self._pick_series()
        if not s:
            return
        try:
            EE.set_series_status(s.series_id, status, actor=self.principal)
        except _ERRORS as e:
            self._err(e)
        self._after_series()

    def delete_series(self) -> None:
        s = self._pick_series()
        if not s or not messagebox.askyesno("Delete series", f"Delete {s.name}?",
                                            parent=self._top()):
            return
        try:
            EE.delete_series(s.series_id, actor=self.principal)
        except _ERRORS as e:
            self._err(e)
        self.state["series_id"] = None
        self._after_series()

    # Specifications
    def _build_specifications(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        if self.editor:
            ttk.Button(bar, text="New specification", command=lambda: spec_dialog(
                tab, principal=self.principal, after=self.refresh_specifications)).pack(
                side="left")
            ttk.Button(bar, text="Edit", command=self.edit_spec).pack(side="left", padx=(4, 0))
            ttk.Button(bar, text="Active / inactive", command=self.toggle_spec).pack(
                side="left", padx=(4, 0))
            ttk.Button(bar, text="Delete", command=self.delete_spec).pack(side="left",
                                                                          padx=(4, 0))
            ttk.Button(bar, text="Set up from subjects", command=self.specs_from_subjects).pack(
                side="left", padx=(12, 0))
        ttk.Button(bar, text="Refresh", command=self.refresh_specifications).pack(side="right")
        self.x_tree = _tree(tab, [("id", "ID", 45), ("subj", "Subject", 150),
                                  ("board", "Board", 100), ("spec", "Spec", 70),
                                  ("name", "Title", 180), ("qual", "Qualification", 100),
                                  ("codes", "Entry codes", 140), ("fee", "Fee", 70),
                                  ("late", "Late fee", 70), ("active", "Active", 55),
                                  ("used", "Entries", 60)])
        self.x_tree.bind("<Double-1>", lambda _e: self.edit_spec() if self.editor else None)
        self.x_note = tk.StringVar()
        ttk.Label(tab, textvariable=self.x_note, foreground="#a60", wraplength=900).pack(
            anchor="w", pady=(6, 0))

    def refresh_specifications(self) -> None:
        self.x_tree.delete(*self.x_tree.get_children())
        for x in EE.list_specs():
            codes = (f"F {x.foundation_code} / H {x.higher_code}" if x.tiered
                     else (x.entry_code or x.spec_code))
            self.x_tree.insert("", "end", iid=str(x.spec_id), values=(
                x.spec_id, x.subject_name, x.exam_board, x.spec_code, x.title,
                x.qualification, codes, EE.money(x.fee) if x.fee is not None else "-",
                EE.money(x.late_fee) if x.late_fee is not None else "-",
                "Yes" if x.is_active else "No", EE.spec_in_use(x.spec_id)["entries"]))
        missing = EE.subjects_without_spec()
        self.x_note.set("KS4 subjects with no specification: "
                        + ", ".join(s.name for s in missing) if missing else "")

    def _spec(self) -> EE.Spec | None:
        sel = self.x_tree.selection()
        if not sel:
            self._info("Select a specification first.")
            return None
        return EE.get_spec(int(sel[0]))

    def edit_spec(self) -> None:
        x = self._spec()
        if x:
            spec_dialog(self.parent, principal=self.principal, spec=x,
                        after=self.refresh_specifications)

    def toggle_spec(self) -> None:
        x = self._spec()
        if x:
            EE.set_spec_active(x.spec_id, not x.is_active, actor=self.principal)
            self.refresh_specifications()

    def delete_spec(self) -> None:
        x = self._spec()
        if not x or not messagebox.askyesno("Delete", f"Delete {x.label}?", parent=self._top()):
            return
        try:
            EE.delete_spec(x.spec_id, actor=self.principal)
        except _ERRORS as e:
            self._err(e)
        self.refresh_specifications()

    def specs_from_subjects(self) -> None:
        try:
            made = EE.specs_from_subjects(actor=self.principal)
        except _ERRORS as e:
            self._err(e)
            return
        self._info(f"Set up {len(made)} specification(s) from the subjects' board and spec "
                   "code." + ("" if made else "\n\nEvery subject with a board and spec code is "
                                              "already set up.")
                   + "\n\nCheck the entry codes, tiers and fees.")
        self.refresh_specifications()

    # Candidates
    def _build_candidates(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Year:").pack(side="left", padx=(0, 4))
        self.c_year = tk.StringVar(value=self.state.get("c_year", "11"))
        cb = ttk.Combobox(bar, textvariable=self.c_year, values=[str(y) for y in P.YEAR_GROUPS],
                          state="readonly", width=5)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh_candidates())
        if self.editor:
            ttk.Button(bar, text="Set number / UCI", command=self.edit_candidate).pack(
                side="left", padx=(12, 0))
            ttk.Button(bar, text="Number everyone in the year",
                       command=self.number_year).pack(side="left", padx=(4, 0))
            ttk.Button(bar, text="Number everyone entered in the series",
                       command=self.number_series).pack(side="left", padx=(4, 0))
        ttk.Button(bar, text="Refresh", command=self.refresh_candidates).pack(side="right")
        self.c_tree = _tree(tab, [("adm", "Adm no", 90), ("name", "Pupil", 200),
                                  ("form", "Form", 60), ("cand", "Cand#", 70),
                                  ("uci", "UCI", 140), ("entries", "Live entries", 90),
                                  ("detail", "Access arrangements", 260)])
        self.c_tree.bind("<Double-1>", lambda _e: self.edit_candidate() if self.editor else None)

    def refresh_candidates(self) -> None:
        from education_system.systems.secondary.modules.pupils.domain import sen_details as SEN
        self.state["c_year"] = self.c_year.get()
        self.c_tree.delete(*self.c_tree.get_children())
        pupils = P.list_pupils(year_group=int(self.c_year.get() or 11))
        cands = EE.candidates([p.pupil_id for p in pupils])
        s = self.series()
        counts: dict[int, int] = {}
        if s:
            for e in EE.list_entries(series_id=s.series_id):
                if e.entry_status in ("Provisional", "Final"):
                    counts[e.pupil_id] = counts.get(e.pupil_id, 0) + 1
        for p in pupils:
            c = cands.get(p.pupil_id)
            d = SEN.get(p.pupil_id)
            self.c_tree.insert("", "end", iid=str(p.pupil_id), tags=(
                "warning" if counts.get(p.pupil_id) and not c else "",), values=(
                p.admission_no, p.display_name, p.form_group or "",
                c.candidate_number if c else "", (c.uci or "") if c else "",
                counts.get(p.pupil_id, 0), (d.exam_access or "") if d else ""))

    def edit_candidate(self) -> None:
        sel = self.c_tree.selection()
        if not sel:
            self._info("Select a pupil first.")
            return
        p = P.get_pupil(int(sel[0]))
        if p:
            candidate_dialog(self.parent, principal=self.principal, pupil=p,
                             after=self.refresh_candidates)

    def number_year(self) -> None:
        try:
            n = EE.assign_numbers([p.pupil_id for p in P.list_pupils(
                year_group=int(self.c_year.get() or 11))], actor=self.principal)
        except _ERRORS as e:
            self._err(e)
            return
        self._info(f"{n} candidate number(s) given.")
        self.refresh_candidates()

    def number_series(self) -> None:
        s = self._need_series()
        if not s:
            return
        try:
            n = EE.assign_series_numbers(s.series_id, actor=self.principal)
        except _ERRORS as e:
            self._err(e)
            return
        self._info(f"{n} candidate number(s) given.")
        self.refresh_candidates()

    # Checks
    def _build_checks(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Also check who's taught but not entered in Year:").pack(
            side="left")
        self.k_year = tk.StringVar(value=self.state.get("k_year", "11"))
        cb = ttk.Combobox(bar, textvariable=self.k_year, values=[ALL, *map(
            str, P.YEAR_GROUPS)], state="readonly", width=5)
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh_checks())
        ttk.Button(bar, text="Access arrangements", command=self.show_access).pack(
            side="left", padx=(12, 0))
        ttk.Button(bar, text="Refresh", command=self.refresh_checks).pack(side="right")
        self.k_tree = _tree(tab, [("level", "", 70), ("text", "What to sort out", 700)])
        self.k_tree.bind("<Double-1>", lambda _e: self._open_check())
        self._check_rows: dict[str, dict] = {}

    def refresh_checks(self) -> None:
        self.state["k_year"] = self.k_year.get()
        self.k_tree.delete(*self.k_tree.get_children())
        s = self.series()
        if s is None:
            return
        rows = EE.checks(s.series_id, year_group=int(self.k_year.get()) if self.k_year.get()
                         else None)
        self._check_rows = {}
        for i, c in enumerate(rows):
            self._check_rows[str(i)] = c
            self.k_tree.insert("", "end", iid=str(i), tags=(c["level"],), values=(
                c["level"].title(), c["text"]))
        if not rows:
            self.k_tree.insert("", "end", values=("", "Nothing to sort out. ✓"))

    def _open_check(self) -> None:
        sel = self.k_tree.selection()
        c = self._check_rows.get(sel[0]) if sel else None
        if c and c.get("entry_id"):
            self.book.select(0)
            self.f_year.set(ALL)
            self.f_board.set(ALL)
            self.f_status.set(ALL)
            self.refresh_entries()
            iid = str(c["entry_id"])
            if self.e_tree.exists(iid):
                self.e_tree.selection_set(iid)
                self.e_tree.see(iid)

    def show_access(self) -> None:
        s = self._need_series()
        if s:
            _text_window(self.parent, f"Access arrangements - {s.name}", "\n".join(
                f"{p.admission_no:<10} {p.display_name:<26} {a}"
                for p, a in EE.access_arrangements(s.series_id))
                or "No candidates with Final entries have access arrangements.")

    # Fees
    def _build_fees(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Group by:").pack(side="left")
        self.fee_by = tk.StringVar(value="subject")
        for k in ("subject", "board", "payer"):
            ttk.Radiobutton(bar, text=k.title(), value=k, variable=self.fee_by,
                            command=self.refresh_fees).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh", command=self.refresh_fees).pack(side="right")
        self.f_tree = _tree(tab, [("name", "Name", 260), ("entries", "Entries", 80),
                                  ("late", "Late", 60), ("fees", "Fees", 100)])
        self.fee_total = tk.StringVar()
        ttk.Label(tab, textvariable=self.fee_total, font=("", 10, "bold")).pack(anchor="w",
                                                                               pady=(6, 0))
        ttk.Label(tab, text="Fees count Final entries and withdrawals made after the entry "
                            "deadline. Provisional entries are shown as an estimate.",
                  foreground="#777").pack(anchor="w")

    def refresh_fees(self) -> None:
        self.f_tree.delete(*self.f_tree.get_children())
        s = self.series()
        if s is None:
            return
        for d in EE.fees_by(s.series_id, self.fee_by.get()):
            self.f_tree.insert("", "end", values=(d["name"], d["entries"], d["late"],
                                                  EE.money(d["fees"])))
        t = EE.cohort_summary(series_id=s.series_id)
        self.fee_total.set(f"Billed {EE.money(t['billed'])} (late fees "
                           f"{EE.money(t['late_fees'])}; parents "
                           f"{EE.money(t['by_payer']['Parent'])})    Provisional estimate "
                           f"{EE.money(t['estimated'])}")

    # Board files and statements
    def _build_board_files(self, tab: ttk.Frame) -> None:
        box = ttk.LabelFrame(tab, text="Exam centre", padding=8)
        box.pack(fill="x")
        self.centre_var = tk.StringVar()
        ttk.Label(box, textvariable=self.centre_var).pack(side="left")
        if self.editor:
            ttk.Button(box, text="Edit centre…", command=lambda: centre_dialog(
                tab, principal=self.principal, after=self.refresh_board_files)).pack(
                side="right")
        box = ttk.LabelFrame(tab, text="Board files", padding=8)
        box.pack(fill="both", expand=True, pady=(8, 0))
        self.b_tree = _tree(box, [("board", "Board", 160), ("unsent", "Changes to send", 120),
                                  ("final", "Final entries", 100),
                                  ("withdrawn", "Withdrawn", 90)], height=6)
        bar = ttk.Frame(box)
        bar.pack(fill="x", pady=(6, 0))
        if self.editor:
            ttk.Button(bar, text="Save changes file…", command=self.board_file).pack(
                side="left")
            ttk.Button(bar, text="Save full file…", command=lambda: self.board_file(
                full=True)).pack(side="left", padx=(4, 0))
        ttk.Label(bar, text="Saving a file records those entries as sent to the board.",
                  foreground="#777").pack(side="left", padx=8)
        box = ttk.LabelFrame(tab, text="Statements of entry", padding=8)
        box.pack(fill="x", pady=(8, 0))
        ttk.Button(box, text="Preview for selected pupil (Entries tab)",
                   command=self.preview_statement).pack(side="left")
        if self.editor:
            ttk.Button(box, text="E-mail statements to pupils and families",
                       command=self.send_statements).pack(side="left", padx=(4, 0))

    def refresh_board_files(self) -> None:
        c = EE.get_centre()
        self.centre_var.set(
            f"Centre {c.centre_number or '(no number set)'} · {c.centre_name or '-'} · exams "
            f"officer {c.officer_name or '-'}" + (f" <{c.officer_email}>" if c.officer_email
                                                   else ""))
        self.b_tree.delete(*self.b_tree.get_children())
        s = self.series()
        if s is None:
            return
        rows = EE.list_entries(series_id=s.series_id)
        unsent = EE.unsent_by_board(s.series_id)
        for b in sorted({e.exam_board for e in rows}):
            self.b_tree.insert("", "end", iid=b, tags=("unsent" if unsent.get(b) else "",),
                               values=(b, unsent.get(b, 0),
                                       sum(1 for e in rows if e.exam_board == b
                                           and e.entry_status == "Final"),
                                       sum(1 for e in rows if e.exam_board == b
                                           and e.entry_status == "Withdrawn")))

    def board_file(self, full: bool = False) -> None:
        s = self._need_series()
        sel = self.b_tree.selection()
        if not s:
            return
        if not sel:
            self._info("Select a board first.")
            return
        board = sel[0]
        path = filedialog.asksaveasfilename(
            parent=self._top(), defaultextension=".csv",
            initialfile=f"{board}-{s.name}-{'full' if full else 'changes'}.csv".replace(" ", "-"),
            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            n = EE.export_board_file(s.series_id, board, path, actor=self.principal,
                                     changes_only=not full)
        except (OSError, *_ERRORS) as e:
            self._err(e)
            return
        self._info(f"Saved {n} row(s) for {board}. Upload the file to the board's entries "
                   "system.")
        self.refresh_board_files()

    def _statement_pupil(self) -> int | None:
        sel = self.e_tree.selection()
        if sel:
            e = EE.get(int(sel[0]))
            return e.pupil_id if e else None
        self._info("Select one of the pupil's entries on the Entries tab first.")
        return None

    def preview_statement(self) -> None:
        s = self._need_series()
        pid = self._statement_pupil() if s else None
        if s and pid:
            _text_window(self.parent, "Statement of entry",
                         EE.statement_text(EE.statement(pid, s.series_id)))

    def send_statements(self) -> None:
        s = self._need_series()
        if not s or not messagebox.askyesno(
                TITLE, f"E-mail every candidate's statement of entry for {s.name} to their "
                       "school address and their contacts?", parent=self._top()):
            return
        try:
            r = EE.send_statements(s.series_id, actor=self.principal)
        except _ERRORS as e:
            self._err(e)
            return
        from education_system.systems.secondary.modules.communication.gui import email_views

        def done(report, error) -> None:
            text = f"{r['emails']} statement e-mail(s) " + (
                f"queued - delivery failed: {error}" if error else "sent.")
            if r["nobody"]:
                text += ("\n\nNo e-mail address for: "
                         + ", ".join(p.display_name for p in r["nobody"][:20]))
            try:
                self._info(text)
            except tk.TclError:
                pass

        email_views.deliver_in_background(self.parent, r["message_id"], self.principal, done)


def draw_exam_entries(parent: ttk.Frame, *, principal: Principal, state: dict,
                      open_pupil: Callable[[int], None] | None = None,
                      on_status: Callable[[str], None] | None = None) -> ExamEntriesPage:
    return ExamEntriesPage(parent, principal=principal, state=state, open_pupil=open_pupil,
                           on_status=on_status)


def draw_profile_entries(parent: ttk.Frame, pupil: P.Pupil) -> None:
    """The pupil's exam entries on their profile."""
    rows = [e for e in EE.entries_for_pupil(pupil.pupil_id)
            if e.entry_status in ("Provisional", "Final")]
    c = EE.candidate(pupil.pupil_id)
    if not rows and not c:
        return
    box = ttk.LabelFrame(parent, text="Exam entries"
                         + (f" - candidate {c.candidate_number}" if c else ""), padding=8)
    box.pack(fill="x", pady=(8, 0))
    for e in rows:
        ttk.Label(box, text=f"{e.series_name}: {e.subject_name} {e.exam_board} {e.entry_code}"
                            + ("" if e.tier == "N/A" else f" ({e.tier})")
                            + f" - {e.entry_status}",
                  foreground="#a60" if e.entry_status == "Provisional" else "").pack(anchor="w")
    if not rows:
        ttk.Label(box, text="No live entries.", foreground="#777").pack(anchor="w")
