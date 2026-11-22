"""Safeguarding screen (the DSL and deputies).

The old Safeguarding window is the first tab ("Concerns"), with its toolbar
(Year, Severity, Status and Category filters; Apply, Raise, Edit, Actions,
Status, Delete, Refresh), its columns (ID, Raised, Pupil, Yr, Category,
Severity, Status, DSL, Conf), its severity colours, its concern dialog (Pupil
ID, Category, Severity, Incident date / time, Location, Raised by / date, DSL
reviewer, DSL review date, Status, Referral body / date / ref, Closed date,
Confidential, Description, Outcome, Notes), its Status dialog and its Actions
window (Add action, Delete selected, Refresh; ID, Date, Type, Actioned by,
Summary). Added: Level and urgent columns, Level filter, View, Triage, Add
referral, Close, Reopen, Chronology, Pupil file, Open pupil, History, Export
CSV; actions get Due / Done and a Complete button.

The old Prevent Duty window is the "Prevent" tab (Status and Risk filters,
Open only; Apply, New, Edit, Close, Delete, Refresh).

New tabs: Triage (new reports, urgent first), Due, Pupil file, Referrals,
Plans, Transfers, Reports, Access log and Team. Rules:
:mod:`modules.safeguarding.domain.safeguarding` (+ ``safeguarding_records``,
``safeguarding_reports``).
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable

from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox
from education_system.systems.secondary.modules.safeguarding.domain import safeguarding as SG
from education_system.systems.secondary.modules.safeguarding.domain import (
    safeguarding_records as SR,
)
from education_system.systems.secondary.modules.safeguarding.domain import (
    safeguarding_reports as SGR,
)
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
YEARS = ("7", "8", "9", "10", "11")
_ERRORS = W.ERRORS
_problems = W.problems
_text_window = W.text_window
_form = W.form_dialog
_SEVERITY_COLOURS = {"Critical": "#ffcccc", "High": "#ffe0b3", "Medium": "#ffffb3",
                     "Low": "#e6f2ff"}
TITLE = "Safeguarding"


def _tree(parent, columns, height: int = 16, select: str = "browse") -> ttk.Treeview:
    t = W.tree(parent, columns, height=height, select=select,
               stretch={"pupil", "summary", "what", "group", "text", "category"},
               tags=W.STANDARD_TAGS)
    for sev, colour in _SEVERITY_COLOURS.items():
        t.tag_configure(f"sev_{sev}", background=colour)
    return t


def pupil_choices() -> list[str]:
    """"Surname, First (ADM)" for every pupil on roll (the domain reads the
    admission number in brackets)."""
    try:
        return [f"{p.legal_last_name}, {p.preferred_name or p.legal_first_name} "
                f"({p.admission_no})" for p in P.list_pupils()]
    except Exception:  # noqa: BLE001 - a typed admission number still works
        logger.exception("Could not list pupils")
        return []


def _concern_fields(c: SG.Concern | None, pupils: list[str]) -> list:
    """The old dialog's fields in its order, then the new ones."""
    def v(k, default=""):
        x = getattr(c, k) if c else None
        return default if x is None else x
    return [
        ("pupil_id", "Pupil ID / admission no.", c.admission_no if c else "", ("edit", pupils)),
        ("category", "Category", v("category", SG.DEFAULT_CATEGORY), SG.CONCERN_CATEGORIES),
        ("severity", "Severity", v("severity", SG.DEFAULT_SEVERITY), SG.SEVERITIES),
        ("incident_date", "Incident date", v("incident_date"), None),
        ("incident_time", "Incident time (HH:MM)", v("incident_time"), None),
        ("location", "Location", v("location"), None),
        ("raised_by", "Raised by", v("raised_by"), None),
        ("raised_date", "Raised date", v("raised_date"), None),
        ("dsl_reviewer", "DSL reviewer", v("dsl_reviewer"), None),
        ("review_date", "DSL review date", v("review_date"), None),
        ("status", "Status", v("status", SG.DEFAULT_STATUS), SG.CONCERN_STATUSES),
        ("referral_body", "Referral body", v("referral_body"), ["", *SG.REFERRAL_BODIES]),
        ("referral_date", "Referral date", v("referral_date"), None),
        ("referral_reference", "Referral ref", v("referral_reference"), None),
        ("closed_date", "Closed date", v("closed_date"), None),
        ("confidential", "Confidential", c.confidential if c else True, "check"),
        ("description", "Description (required)", v("description"), "text"),
        ("outcome", "Outcome", v("outcome"), "text"),
        ("notes", "Notes (DSL)", v("notes"), "text"),
        ("level_of_need", "Level of need / action", v("level_of_need"), ["", *SG.LEVELS]),
        ("child_words", "Child's own words", v("child_words"), "text"),
        ("body_map", "Injury / body map", v("body_map"), None),
        ("immediate_action", "Immediate action taken", v("immediate_action"), "text"),
        ("people_involved", "Others involved", v("people_involved"), None),
        ("allegation_about", "Allegation about (LADO)", v("allegation_about"), None),
        ("urgent", "Urgent", c.urgent if c else False, "check"),
    ]


def concern_text(c: SG.Concern) -> str:
    rows = [("Pupil", f"{c.pupil_name} ({c.admission_no}), Year {c.pupil_year}"
                      + (f", {c.form_group}" if c.form_group else "")),
            ("Category", c.category), ("Severity", c.severity),
            ("Urgent", "YES - child said to be in immediate danger" if c.immediate_danger
             else ("Yes" if c.urgent else "")),
            ("Level of need", c.level_of_need), ("Status", c.status),
            ("Incident", f"{c.incident_date or '-'} {c.incident_time or ''}".strip()),
            ("Location", c.location), ("Raised", f"{c.raised_date} by {c.raised_by or '-'}"),
            ("DSL reviewer", f"{c.dsl_reviewer or '-'} ({c.review_date or '-'})"),
            ("Referral", " ".join(x for x in (c.referral_body, c.referral_date,
                                              c.referral_reference) if x)),
            ("Allegation about", c.allegation_about), ("Outcome", c.outcome),
            ("Closed", c.closed_date), ("Confidential", "Yes" if c.confidential else "No"),
            ("DSL alerted", (f"{c.notified_at} ({c.notified_count} e-mail(s))"
                             if c.notified_at else "")
             + (" - PHONE THE DSL" if c.needs_phone_call else ""))]
    out = [f"Concern #{c.concern_id}", ""]
    out += [f"{k + ':':<18} {v}" for k, v in rows if v]
    for label, v in (("What was seen / heard", c.description),
                     ("Child's own words", c.child_words), ("Injury / body map", c.body_map),
                     ("Immediate action", c.immediate_action),
                     ("Others involved", c.people_involved), ("DSL notes", c.notes)):
        if v:
            out += ["", f"{label}:", f"  {v}"]
    return "\n".join(out)


class SafeguardingPage:
    TABS = ("Concerns", "Triage", "Due", "Pupil file", "Referrals", "Plans", "Prevent",
            "Transfers", "Reports", "Access log", "Team")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil = open_pupil
        self.lead = SG.is_lead(principal)
        activity_log.record("safeguarding.view")
        ttk.Label(parent, text=TITLE, font=("", 16, "bold")).pack(anchor="w")
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(
            anchor="w", pady=(0, 6))
        if not self.lead:
            ttk.Label(parent, text="Safeguarding records are for the designated safeguarding "
                                   "lead and deputies. To pass on a concern, use Report a "
                                   "Safeguarding Concern.", foreground="#a00",
                      wraplength=700).pack(anchor="w")
            return
        self._pupils: list[str] | None = None
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._built: set[str] = set()
        start = state.get("tab") if state.get("tab") in self.TABS else "Concerns"
        self.book.select(self.TABS.index(start))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    # ── helpers ──────────────────────────────────────────────────────

    def _top(self):
        return self.parent.winfo_toplevel()

    def _err(self, title: str, e: Exception) -> None:
        messagebox.showerror(title, _problems(e), parent=self._top())

    def _info(self, title: str, text: str) -> None:
        messagebox.showinfo(title, text, parent=self._top())

    def pupils(self) -> list[str]:
        if self._pupils is None:
            self._pupils = pupil_choices()
        return self._pupils

    def _bar(self, tab, buttons) -> ttk.Frame:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        for text, cmd in buttons:
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        return bar

    def _builders(self) -> dict[str, tuple[Callable, Callable]]:
        return {"Concerns": (self._build_concerns, self.refresh),
                "Triage": (self._build_triage, self.refresh_triage),
                "Due": (self._build_due, self.refresh_due),
                "Pupil file": (self._build_file, lambda: None),
                "Referrals": (self._build_referrals, self.refresh_referrals),
                "Plans": (self._build_plans, self.refresh_plans),
                "Prevent": (self._build_prevent, self.refresh_prevent),
                "Transfers": (self._build_transfers, self.refresh_transfers),
                "Reports": (self._build_reports, self.refresh_reports),
                "Access log": (self._build_access, self.refresh_access),
                "Team": (self._build_team, self.refresh_team)}

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        build, refresh = self._builders()[name]
        if name not in self._built:
            self._built.add(name)
            build(self.tabs[name])
        try:
            refresh()
        except _ERRORS as e:
            self._err(name, e)

    def _refresh_all(self) -> None:
        for name, (_b, fn) in self._builders().items():
            if name in self._built:
                try:
                    fn()
                except _ERRORS as e:
                    logger.warning("Safeguarding %s refresh: %s", name, e)

    def _insert(self, tree: ttk.Treeview, c: SG.Concern, rows: dict) -> None:
        rows[str(c.concern_id)] = c
        tag = "muted" if c.status in SG.FINISHED else f"sev_{c.severity}"
        tree.insert("", "end", iid=str(c.concern_id), tags=(tag,),
                    values=(c.concern_id, c.raised_date, f"{c.pupil_name} ({c.admission_no})",
                            c.pupil_year, c.category, c.severity, c.status,
                            c.dsl_reviewer or "-", "Yes" if c.confidential else "No",
                            c.level_of_need or "", "!" if c.urgent else ""))

    _COLUMNS = [("id", "ID", 50), ("raised", "Raised", 90), ("pupil", "Pupil", 190),
                ("year", "Yr", 40), ("category", "Category", 190), ("sev", "Severity", 80),
                ("status", "Status", 90), ("dsl", "DSL", 120), ("conf", "Conf", 45),
                ("level", "Level", 160), ("urgent", "!", 25)]

    # ── Concerns (the old window) ────────────────────────────────────

    def _build_concerns(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.year = tk.StringVar(value=self.state.get("year", ""))
        self.sev = tk.StringVar(value=self.state.get("severity", ""))
        self.status = tk.StringVar(value=self.state.get("status", ""))
        self.cat = tk.StringVar(value=self.state.get("category", ""))
        self.level = tk.StringVar(value=self.state.get("level", ""))
        for label, var, values, width in (
                ("Year:", self.year, ["", *YEARS], 5),
                ("Severity:", self.sev, ["", *SG.SEVERITIES], 10),
                ("Status:", self.status, ["", *SG.CONCERN_STATUSES], 12),
                ("Category:", self.cat, ["", *SG.CONCERN_CATEGORIES], 22),
                ("Level:", self.level, ["", *SG.LEVELS], 18)):
            ttk.Label(bar, text=label).pack(side="left", padx=(0, 4))
            cb = ttk.Combobox(bar, textvariable=var, values=values, state="readonly",
                              width=width)
            cb.pack(side="left", padx=(0, 6))
            cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        self._bar(tab, (("Apply", self.refresh), ("Raise", self.new), ("Edit", self.edit),
                        ("Actions", self.actions), ("Status", self.set_status),
                        ("Delete", self.delete), ("Refresh", self.refresh)))
        self._bar(tab, (("View", self.view), ("Triage…", self.triage),
                        ("Add referral…", self.add_referral), ("Close…", self.close),
                        ("Reopen…", self.reopen), ("Chronology", self.chronology),
                        ("Pupil file", self.pupil_file), ("Open pupil", self._open_selected),
                        ("History", self.history), ("Export CSV…", self.export)))
        self.tree = _tree(tab, self._COLUMNS)
        self.tree.bind("<Double-1>", lambda _e: self.actions())
        self.rows: dict[str, SG.Concern] = {}

    def refresh(self) -> None:
        y, sv, st, ca, lv = (self.year.get(), self.sev.get(), self.status.get(),
                             self.cat.get(), self.level.get())
        self.state.update(year=y, severity=sv, status=st, category=ca, level=lv)
        try:
            rows = SG.list_concerns(actor=self.principal, year_group=y or None,
                                    severity=sv or None, status=st or None,
                                    category=ca or None, level=lv or None)
        except _ERRORS as e:
            self._err(TITLE, e)
            return
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        for c in rows:
            self._insert(self.tree, c, self.rows)
        self._summary()

    def _summary(self) -> None:
        s = SGR.cohort_summary(actor=self.principal)
        self.summary_var.set(f"Concerns: {s['total']}    Open: {s['open']}    Open Critical: "
                             f"{s['open_critical']}    New: {s['new']}    Urgent open: "
                             f"{s['urgent_open']}    Pupils: {s['pupils']}")

    def _selected(self, title: str, tree=None, rows=None) -> SG.Concern | None:
        tree, rows = tree or self.tree, rows if rows is not None else self.rows
        sel = tree.selection()
        if not sel:
            self._info(title, "Select a concern first.")
            return None
        return rows[sel[0]]

    def new(self) -> None:
        def save(v):
            v = {k: x for k, x in v.items() if x not in ("", None)}
            c = SG.raise_concern(v, actor=self.principal)
            self._refresh_all()
            self._info(TITLE, f"Raised concern #{c.concern_id}: {c.category} ({c.severity})")
        _form(self.parent, "Raise safeguarding concern", _concern_fields(None, self.pupils()),
              save, note="Record facts: what was seen or heard, and the child's own words.")

    def edit(self) -> None:
        c = self._selected("Edit concern")
        if c is None:
            return
        c = SG.get(c.concern_id, actor=self.principal)

        def save(v):
            v.pop("pupil_id", None)
            changes = {k: x for k, x in v.items()
                       if str(x if x is not None else "") != str(
                           getattr(c, k) if getattr(c, k) is not None else "")}
            SG.update(c.concern_id, changes, actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"Edit concern #{c.concern_id}",
              _concern_fields(c, self.pupils()), save)

    def view(self) -> None:
        c = self._selected("View")
        if c:
            try:
                c = SG.get(c.concern_id, actor=self.principal)
            except _ERRORS as e:
                self._err("View", e)
                return
            _text_window(self.parent, f"Concern #{c.concern_id}", concern_text(c))

    def set_status(self) -> None:
        c = self._selected("Status")
        if c is None:
            return

        def save(v):
            SG.set_status(c.concern_id, v["status"], actor=self.principal,
                          outcome=v["outcome"] or None, referral_body=v["referral_body"] or None)
            self._refresh_all()
        _form(self.parent, f"Status — #{c.concern_id}", [
            ("status", "Status", c.status, SG.CONCERN_STATUSES),
            ("outcome", "Outcome (required for Closed)", c.outcome or "", None),
            ("referral_body", "Referral body (required for Referred)", c.referral_body or "",
             ["", *SG.REFERRAL_BODIES])], save,
            note=f"{c.pupil_name} — {c.category}. Current: {c.status}")

    def delete(self) -> None:
        c = self._selected("Delete concern")
        if c is None:
            return

        def save(v):
            SG.delete(c.concern_id, actor=self.principal, reason=v["reason"])
            self._refresh_all()
        _form(self.parent, f"Delete concern #{c.concern_id}", [
            ("reason", "Why (required)", "", "text")], save,
            note=f"Delete concern #{c.concern_id} ({c.pupil_name}, {c.category}) and ALL its "
                 "actions? Only for a concern logged in error - close a real one instead.")

    def triage(self, c: SG.Concern | None = None) -> None:
        c = c or self._selected("Triage")
        if c is None:
            return
        c = SG.get(c.concern_id, actor=self.principal)

        def save(v):
            SG.triage(c.concern_id, actor=self.principal, level=v["level"],
                      severity=v["severity"], category=v["category"],
                      status=v["status"] or None, note=v["note"],
                      allegation_about=v["allegation_about"] or None)
            self._refresh_all()
        _form(self.parent, f"Triage — concern #{c.concern_id}", [
            ("level", "Level of need / action", c.level_of_need or "", SG.LEVELS),
            ("severity", "Severity", c.severity, SG.SEVERITIES),
            ("category", "Category", c.category, SG.CONCERN_CATEGORIES),
            ("status", "Status (blank = from the level)", "", ["", *SG.CONCERN_STATUSES]),
            ("allegation_about", "Allegation about (LADO)", c.allegation_about or "", None),
            ("note", "Decision / rationale", "", "text")], save,
            note=concern_text(c)[:900])

    def add_referral(self, c: SG.Concern | None = None) -> None:
        c = c or self._selected("Add referral")
        if c is None:
            return

        def save(v):
            SG.add_referral(c.concern_id, v, actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"Referral — concern #{c.concern_id}", [
            ("agency", "Referred to", "MASH / Social Care", SG.REFERRAL_BODIES),
            ("referral_date", "Date (blank = today)", "", None),
            ("reference", "Their reference", "", None),
            ("allegation_about", "Allegation about (LADO)", c.allegation_about or "", None),
            ("reason", "Reason / what was shared", "", "text")], save)

    def close(self) -> None:
        c = self._selected("Close")
        if c is None:
            return

        def save(v):
            SG.close_concern(c.concern_id, actor=self.principal, outcome=v["outcome"],
                             closed_date=v["day"] or None)
            self._refresh_all()
        _form(self.parent, f"Close concern #{c.concern_id}", [
            ("outcome", "Outcome (required)", c.outcome or "", "text"),
            ("day", "Closed date (blank = today)", "", None)], save,
            note="Outstanding actions are marked done.")

    def reopen(self) -> None:
        c = self._selected("Reopen")
        if c is None:
            return

        def save(v):
            SG.reopen(c.concern_id, actor=self.principal, reason=v["reason"])
            self._refresh_all()
        _form(self.parent, f"Reopen concern #{c.concern_id}", [
            ("reason", "Why (required)", "", "text")], save)

    def _open_selected(self) -> None:
        c = self._selected("Open pupil")
        if c and self.open_pupil:
            self.open_pupil(c.pupil_id)

    def chronology(self, pupil_id: int | None = None) -> None:
        if pupil_id is None:
            c = self._selected("Chronology")
            if c is None:
                return
            pupil_id = c.pupil_id
        try:
            text = SR.chronology_text(pupil_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Chronology", e)
            return
        _text_window(self.parent, "Chronology", text, size="900x560",
                     save_name="chronology.txt")

    def pupil_file(self) -> None:
        c = self._selected("Pupil file")
        if c is None:
            return
        if "Pupil file" not in self._built:
            self._built.add("Pupil file")
            self._build_file(self.tabs["Pupil file"])
        self.book.select(self.TABS.index("Pupil file"))
        self.file_ref.set(c.admission_no)
        self.load_file()

    def history(self) -> None:
        c = self._selected("History")
        if c is None:
            return
        _text_window(self.parent, "History", "\n".join(
            f"{h['at']}  {h['actor']:<14} {h['action']:<16} "
            + ", ".join(f"{k}={v}" for k, v in h["detail"].items())
            for h in SG.history(c.concern_id, actor=self.principal)) or "No changes recorded.")

    def export(self) -> None:
        path = filedialog.asksaveasfilename(parent=self._top(), defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")],
                                            initialfile="safeguarding.csv")
        if not path:
            return
        try:
            n = SGR.export_csv(path, actor=self.principal, year_group=self.year.get() or None,
                               severity=self.sev.get() or None,
                               status=self.status.get() or None,
                               category=self.cat.get() or None)
        except _ERRORS as e:
            self._err("Export", e)
            return
        self._info("Export", f"Exported {n} concern(s) (no descriptions or notes).")

    # ── The old Actions window ───────────────────────────────────────

    def actions(self, c: SG.Concern | None = None) -> None:
        c = c or self._selected("Actions")
        if c is None:
            return
        try:
            s = SGR.concern_summary(c.concern_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Actions", e)
            return
        win, frm = W.dialog(self.parent, f"Actions — concern #{c.concern_id}", size="900x540")
        header = tk.StringVar()
        ttk.Label(frm, textvariable=header, font=("", 10, "bold")).pack(anchor="w")
        ttk.Label(frm, text="(Confidential — handle in line with DSL policy)"
                  if c.confidential else "", foreground="#aa0000").pack(anchor="w")
        bar = ttk.Frame(frm)
        bar.pack(fill="x", pady=(8, 4))
        tree = _tree(frm, [("id", "ID", 50), ("date", "Date", 90), ("type", "Type", 150),
                           ("by", "Actioned by", 130), ("summary", "Summary", 330),
                           ("due", "Due", 90), ("done", "Done", 90)], height=14)
        rows: dict[str, SG.SGAction] = {}

        def refresh(first: bool = False) -> None:
            data = s if first else SGR.concern_summary(c.concern_id, actor=self.principal)
            k = data["concern"]
            header.set(f"#{k.concern_id} {k.pupil_name} ({k.category}, {k.severity}, "
                       f"{k.status})    Actions: {data['action_count']}")
            tree.delete(*tree.get_children())
            rows.clear()
            today = SG._today().isoformat()
            for a in data["actions"]:
                rows[str(a.action_id)] = a
                tag = ("bad",) if a.outstanding and a.due_date < today else (
                    ("warn",) if a.outstanding else ())
                tree.insert("", "end", iid=str(a.action_id), tags=tag, values=(
                    a.action_id, a.action_date, a.action_type, a.actioned_by or "-",
                    a.summary[:120], a.due_date or "", a.completed_date or ""))

        def add() -> None:
            def save(v):
                SG.add_action({**v, "concern_id": c.concern_id}, actor=self.principal)
                refresh()
            _form(win, f"Action — concern #{c.concern_id}", [
                ("action_date", "Date", "", None),
                ("action_type", "Type", SG.DEFAULT_ACTION_TYPE, SG.ACTION_TYPES),
                ("actioned_by", "Actioned by", SG.staff_name(self.principal), None),
                ("summary", "Summary (required)", "", "text"), ("outcome", "Outcome", "", "text"),
                ("follow_up", "Follow-up", "", "text"),
                ("due_date", "Due date (for a follow-up)", "", None),
                ("assigned_to", "Who will do it", "", None)], save)

        def remove() -> None:
            sel = tree.selection()
            if not sel:
                messagebox.showinfo(TITLE, "Select an action first.", parent=win)
                return
            if not messagebox.askyesno("Delete action", f"Delete action #{sel[0]}?",
                                       parent=win):
                return
            try:
                SG.delete_action(int(sel[0]), actor=self.principal)
            except _ERRORS as e:
                messagebox.showerror("Delete action", _problems(e), parent=win)
                return
            refresh()

        def complete() -> None:
            sel = tree.selection()
            if not sel:
                return

            def save(v):
                SG.complete_action(int(sel[0]), actor=self.principal, outcome=v["outcome"],
                                   day=v["day"] or None)
                refresh()
                self._refresh_all()
            _form(win, f"Done — action #{sel[0]}", [("day", "Done on (blank = today)", "", None),
                                                    ("outcome", "Outcome", "", "text")], save)

        def view() -> None:
            sel = tree.selection()
            if sel:
                a = rows[sel[0]]
                _text_window(win, f"Action #{a.action_id}", "\n".join(
                    f"{k}: {v}" for k, v in (
                        ("Date", a.action_date), ("Type", a.action_type),
                        ("Actioned by", a.actioned_by), ("Summary", a.summary),
                        ("Outcome", a.outcome), ("Follow-up", a.follow_up),
                        ("Due", a.due_date), ("Who", a.assigned_to),
                        ("Done", a.completed_date), ("Recorded by", a.created_by)) if v))
        for text, cmd in (("Add action", add), ("Delete selected", remove),
                          ("Refresh", refresh), ("View", view), ("Complete…", complete),
                          ("View concern", lambda: _text_window(win, "Concern",
                                                                concern_text(s["concern"])))):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        tree.bind("<Double-1>", lambda _e: view())
        refresh(first=True)

    # ── Triage ───────────────────────────────────────────────────────

    def _build_triage(self, tab) -> None:
        ttk.Label(tab, text="New reports waiting for the DSL - urgent first.",
                  font=("", 11, "bold")).pack(anchor="w")
        self._bar(tab, (("Triage…", lambda: self.triage(self._selected(
            "Triage", self.tri_tree, self.tri_rows))),
                        ("View", self._view_from_triage),
                        ("Actions", lambda: self.actions(self._selected(
                            "Actions", self.tri_tree, self.tri_rows))),
                        ("Open pupil", lambda: self._open_from(self.tri_tree, self.tri_rows)),
                        ("Refresh", self.refresh_triage)))
        self.tri_tree = _tree(tab, self._COLUMNS)
        self.tri_tree.bind("<Double-1>", lambda _e: self.triage(self._selected(
            "Triage", self.tri_tree, self.tri_rows)))
        self.tri_rows: dict[str, SG.Concern] = {}

    def refresh_triage(self) -> None:
        self.tri_tree.delete(*self.tri_tree.get_children())
        self.tri_rows = {}
        for c in SG.awaiting_triage(actor=self.principal):
            self._insert(self.tri_tree, c, self.tri_rows)
            if c.urgent:
                self.tri_tree.item(str(c.concern_id), tags=("bad",))

    def _view_from_triage(self) -> None:
        c = self._selected("View", self.tri_tree, self.tri_rows)
        if c:
            _text_window(self.parent, f"Concern #{c.concern_id}",
                         concern_text(SG.get(c.concern_id, actor=self.principal)))

    def _open_from(self, tree, rows) -> None:
        sel = tree.selection()
        if sel and self.open_pupil:
            self.open_pupil(rows[sel[0]].pupil_id)

    # ── Due ──────────────────────────────────────────────────────────

    def _build_due(self, tab) -> None:
        ttk.Label(tab, text="Overdue first: new reports, urgent ones to phone through, actions "
                            "due in the next two weeks, referrals waiting over a week.",
                  foreground="#555").pack(anchor="w")
        self._bar(tab, (("Go to concern", self._due_goto), ("Complete action…", self._due_done),
                        ("Refresh", self.refresh_due)))
        self.due_tree = _tree(tab, [("due", "Due", 90), ("flag", "", 70), ("kind", "Kind", 110),
                                    ("id", "Concern", 60), ("pupil", "Pupil", 200),
                                    ("what", "What", 380)], height=12)
        self.due_tree.bind("<Double-1>", lambda _e: self._due_goto())
        ttk.Label(tab, text="Plan reviews in the next two weeks", font=("", 11, "bold")).pack(
            anchor="w", pady=(8, 2))
        self.rev_tree = _tree(tab, [("review", "Review", 90), ("pupil", "Pupil", 240),
                                    ("plan", "Plan", 200), ("la", "LA / social worker", 240)],
                              height=5)
        self.due_rows: dict[str, dict] = {}

    def refresh_due(self) -> None:
        self.due_tree.delete(*self.due_tree.get_children())
        self.due_rows = {}
        for i, d in enumerate(SGR.due(actor=self.principal)):
            iid = str(i)
            self.due_rows[iid] = d
            self.due_tree.insert("", "end", iid=iid, tags=("bad",) if d["overdue"] else (),
                                 values=(d["due"] or "", "OVERDUE" if d["overdue"] else "",
                                         d["kind"], d["concern_id"], d["pupil"], d["what"]))
        self.rev_tree.delete(*self.rev_tree.get_children())
        for x in SR.plan_reviews_due(actor=self.principal):
            self.rev_tree.insert("", "end", values=(
                x.next_review, f"{x.pupil_name} ({x.admission_no})",
                x.plan_type + (f" ({x.category})" if x.category else ""),
                " / ".join(v for v in (x.local_authority, x.social_worker) if v)))
        m = SGR.my_day(actor=self.principal) or {}
        self.summary_var.set(f"New reports: {m.get('new', 0)}    Urgent: {m.get('urgent', 0)}"
                             f"    Overdue: {m.get('overdue', 0)}")

    def _due_goto(self) -> None:
        sel = self.due_tree.selection()
        if not sel:
            return
        cid = self.due_rows[sel[0]]["concern_id"]
        c = SG.get(cid, actor=self.principal, log=False)
        self.actions(c)

    def _due_done(self) -> None:
        sel = self.due_tree.selection()
        d = self.due_rows.get(sel[0]) if sel else None
        if not d or not d["action_id"]:
            self._info("Complete action", "Select an action (kind Action) first.")
            return

        def save(v):
            SG.complete_action(d["action_id"], actor=self.principal, outcome=v["outcome"])
            self.refresh_due()
        _form(self.parent, f"Done — action #{d['action_id']}",
              [("outcome", "Outcome", "", "text")], save, note=d["what"])

    # ── Pupil file ───────────────────────────────────────────────────

    def _build_file(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Pupil:").pack(side="left")
        self.file_ref = tk.StringVar(value=self.state.get("file_pupil", ""))
        ttk.Combobox(bar, textvariable=self.file_ref, values=self.pupils(), width=40).pack(
            side="left", padx=4)
        for text, cmd in (("Load", self.load_file), ("Chronology", self._file_chron),
                          ("Transfer file…", self._file_transfer), ("New plan…", self._file_plan),
                          ("Raise concern…", self.new), ("Open pupil", self._file_open)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        self.flags_var = tk.StringVar()
        ttk.Label(tab, textvariable=self.flags_var, foreground="#a00",
                  font=("", 11, "bold")).pack(anchor="w")
        self.file_tree = _tree(tab, self._COLUMNS, height=7)
        self.file_tree.bind("<Double-1>", lambda _e: self.actions(self._selected(
            "Actions", self.file_tree, self.file_rows)))
        self.file_rows: dict[str, SG.Concern] = {}
        ttk.Label(tab, text="Chronology").pack(anchor="w", pady=(6, 0))
        self.file_text = tk.Text(tab, height=12, wrap="word", font=("TkFixedFont", 9))
        self.file_text.pack(fill="both", expand=True)
        self.file_pupil: P.Pupil | None = None

    def load_file(self) -> None:
        ref = self.file_ref.get().strip()
        p = SG._pupil(ref)
        if p is None:
            self._info("Pupil file", "Choose a pupil (or type an admission number).")
            return
        self.state["file_pupil"] = ref
        try:
            f = SR.pupil_file(p.pupil_id, actor=self.principal)
            chron = SR.chronology_text(p.pupil_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Pupil file", e)
            return
        self.file_pupil = p
        self.flags_var.set(f"{p.display_name} ({p.admission_no}), Year {p.year_group}:  "
                           + (", ".join(f["flags"]["labels"]) or "nothing current"))
        self.file_tree.delete(*self.file_tree.get_children())
        self.file_rows = {}
        for c in f["concerns"]:
            self._insert(self.file_tree, c, self.file_rows)
        self.file_text.configure(state="normal")
        self.file_text.delete("1.0", "end")
        self.file_text.insert("1.0", chron)
        self.file_text.configure(state="disabled")

    def _need_file_pupil(self) -> P.Pupil | None:
        if self.file_pupil is None:
            self.load_file()
        return self.file_pupil

    def _file_chron(self) -> None:
        p = self._need_file_pupil()
        if p:
            self.chronology(p.pupil_id)

    def _file_open(self) -> None:
        p = self._need_file_pupil()
        if p and self.open_pupil:
            self.open_pupil(p.pupil_id)

    def _file_plan(self) -> None:
        p = self._need_file_pupil()
        if p:
            self.new_plan(p.admission_no)

    def _file_transfer(self) -> None:
        p = self._need_file_pupil()
        if p:
            self.transfer_file(p)

    # ── Referrals ────────────────────────────────────────────────────

    def _build_referrals(self, tab) -> None:
        bar = self._bar(tab, (("Record outcome…", self.referral_outcome),
                              ("Go to concern", self._ref_goto),
                              ("Refresh", self.refresh_referrals)))
        self.ref_pending = tk.BooleanVar(value=self.state.get("ref_pending", True))
        ttk.Checkbutton(bar, text="Waiting for an outcome only", variable=self.ref_pending,
                        command=self.refresh_referrals).pack(side="left", padx=8)
        self.ref_tree = _tree(tab, [("id", "Ref", 45), ("date", "Date", 90),
                                    ("concern", "Concern", 60), ("pupil", "Pupil", 200),
                                    ("agency", "Agency", 140), ("reference", "Their ref", 100),
                                    ("outcome", "Outcome", 170), ("odate", "Outcome date", 90)])
        self.ref_tree.bind("<Double-1>", lambda _e: self.referral_outcome())
        self.ref_rows: dict[str, SG.Referral] = {}

    def refresh_referrals(self) -> None:
        self.state["ref_pending"] = self.ref_pending.get()
        self.ref_tree.delete(*self.ref_tree.get_children())
        self.ref_rows = {}
        for r in SG.list_referrals(actor=self.principal, pending_only=self.ref_pending.get()):
            self.ref_rows[str(r.referral_id)] = r
            self.ref_tree.insert("", "end", iid=str(r.referral_id),
                                 tags=("warn",) if r.pending else (),
                                 values=(r.referral_id, r.referral_date, r.concern_id,
                                         f"{r.pupil_name} ({r.admission_no})", r.agency,
                                         r.reference or "", r.outcome, r.outcome_date or ""))

    def referral_outcome(self) -> None:
        sel = self.ref_tree.selection()
        if not sel:
            self._info("Referral", "Select a referral first.")
            return
        r = self.ref_rows[sel[0]]

        def save(v):
            SG.record_referral_outcome(r.referral_id, actor=self.principal,
                                       outcome=v["outcome"], day=v["day"] or None,
                                       notes=v["notes"])
            self._refresh_all()
        _form(self.parent, f"Outcome — referral #{r.referral_id} ({r.agency})", [
            ("outcome", "Outcome", "", [o for o in SG.REFERRAL_OUTCOMES if o != "Pending"]),
            ("day", "Date (blank = today)", "", None), ("notes", "Notes", "", "text")], save)

    def _ref_goto(self) -> None:
        sel = self.ref_tree.selection()
        if sel:
            self.actions(SG.get(self.ref_rows[sel[0]].concern_id, actor=self.principal,
                                log=False))

    # ── Plans ────────────────────────────────────────────────────────

    def _build_plans(self, tab) -> None:
        bar = self._bar(tab, (("New plan…", self.new_plan), ("Edit…", self.edit_plan),
                              ("End plan…", self.end_plan), ("Delete", self.delete_plan),
                              ("Refresh", self.refresh_plans)))
        self.plan_type = tk.StringVar(value=self.state.get("plan_type", ""))
        self.plan_active = tk.BooleanVar(value=self.state.get("plan_active", True))
        ttk.Label(bar, text="Plan:").pack(side="left", padx=(8, 2))
        cb = ttk.Combobox(bar, textvariable=self.plan_type, values=["", *SR.PLAN_TYPES],
                          state="readonly", width=22)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh_plans())
        ttk.Checkbutton(bar, text="Current only", variable=self.plan_active,
                        command=self.refresh_plans).pack(side="left", padx=8)
        self.plan_tree = _tree(tab, [("id", "ID", 45), ("pupil", "Pupil", 200),
                                     ("type", "Plan", 170), ("cat", "Category", 110),
                                     ("start", "From", 90), ("end", "To", 90),
                                     ("la", "Local authority", 130), ("sw", "Social worker", 140),
                                     ("review", "Next review", 90)])
        self.plan_tree.bind("<Double-1>", lambda _e: self.edit_plan())
        self.plan_rows: dict[str, SR.Plan] = {}

    def refresh_plans(self) -> None:
        self.state.update(plan_type=self.plan_type.get(), plan_active=self.plan_active.get())
        self.plan_tree.delete(*self.plan_tree.get_children())
        self.plan_rows = {}
        for x in SR.list_plans(actor=self.principal, plan_type=self.plan_type.get() or None,
                               active_only=self.plan_active.get()):
            self.plan_rows[str(x.plan_id)] = x
            self.plan_tree.insert("", "end", iid=str(x.plan_id), values=(
                x.plan_id, f"{x.pupil_name} ({x.admission_no})", x.plan_type, x.category or "",
                x.start_date, x.end_date or "", x.local_authority or "", x.social_worker or "",
                x.next_review or ""))

    def _plan_fields(self, x: SR.Plan | None, pupil: str = "") -> list:
        def v(k):
            return (getattr(x, k) or "") if x else ""
        fields = [] if x else [("pupil_id", "Pupil", pupil, ("edit", self.pupils()))]
        return fields + [
            ("plan_type", "Plan", v("plan_type") or SR.CP, SR.PLAN_TYPES),
            ("category", "Category (child protection)", v("category"),
             ["", *SR.CP_CATEGORIES]),
            ("start_date", "Start date", v("start_date"), None),
            ("end_date", "End date", v("end_date"), None),
            ("local_authority", "Local authority", v("local_authority"), None),
            ("social_worker", "Social worker / lead professional", v("social_worker"), None),
            ("contact", "Their phone / e-mail", v("contact"), None),
            ("next_review", "Next review / conference", v("next_review"), None),
            ("notes", "Notes", v("notes"), "text")]

    def new_plan(self, pupil: str = "") -> None:
        def save(v):
            SR.add_plan(v, actor=self.principal)
            self._refresh_all()
        _form(self.parent, "New plan / status", self._plan_fields(None, pupil), save,
              note="Child protection, child in need, early help, looked after or previously "
                   "looked after.")

    def _plan_sel(self, title: str) -> SR.Plan | None:
        sel = self.plan_tree.selection() if "Plans" in self._built else ()
        if not sel:
            self._info(title, "Select a plan first.")
            return None
        return self.plan_rows[sel[0]]

    def edit_plan(self) -> None:
        x = self._plan_sel("Edit plan")
        if x is None:
            return

        def save(v):
            SR.update_plan(x.plan_id, v, actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"Plan #{x.plan_id} — {x.pupil_name}", self._plan_fields(x), save)

    def end_plan(self) -> None:
        x = self._plan_sel("End plan")
        if x is None:
            return

        def save(v):
            SR.end_plan(x.plan_id, actor=self.principal, end_date=v["day"] or None,
                        note=v["note"])
            self._refresh_all()
        _form(self.parent, f"End plan #{x.plan_id}", [
            ("day", "End date (blank = today)", "", None), ("note", "Why / next step", "",
                                                            "text")], save)

    def delete_plan(self) -> None:
        x = self._plan_sel("Delete plan")
        if x is None or not messagebox.askyesno(
                "Delete plan", f"Delete plan #{x.plan_id}? Only for one recorded in error - "
                               "end a real plan instead.", parent=self._top()):
            return
        try:
            SR.delete_plan(x.plan_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Delete plan", e)
            return
        self._refresh_all()

    # ── Prevent (the old Prevent Duty window) ───────────────────────

    def _build_prevent(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.pv_status = tk.StringVar(value="")
        self.pv_risk = tk.StringVar(value="")
        self.pv_open = tk.BooleanVar(value=False)
        for label, var, values, width in (("Status:", self.pv_status, SR.PREVENT_STATUSES, 24),
                                          ("Risk:", self.pv_risk, SR.RISK_LEVELS, 10)):
            ttk.Label(bar, text=label).pack(side="left", padx=(0, 4))
            cb = ttk.Combobox(bar, textvariable=var, values=["", *values], state="readonly",
                              width=width)
            cb.pack(side="left", padx=(0, 6))
            cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh_prevent())
        ttk.Checkbutton(bar, text="Open only", variable=self.pv_open,
                        command=self.refresh_prevent).pack(side="left", padx=6)
        for text, cmd in (("Apply", self.refresh_prevent), ("New", self.new_prevent),
                          ("Edit", self.edit_prevent), ("Close", self.close_prevent),
                          ("Delete", self.delete_prevent), ("Refresh", self.refresh_prevent),
                          ("Actions", lambda: self._pv_sel() and self.actions(
                              self._pv_sel().concern))):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        self.pv_tree = _tree(tab, [("id", "ID", 50), ("pupil", "Pupil", 190), ("year", "Yr", 40),
                                   ("raised", "Raised", 90), ("type", "Concern type", 200),
                                   ("risk", "Risk", 80), ("pathway", "Pathway", 170),
                                   ("status", "Status", 170), ("outcome", "Outcome", 110)])
        for risk, colour in (("Imminent", "#ffcccc"), ("High", "#ffe0b3"),
                             ("Medium", "#ffffb3")):
            self.pv_tree.tag_configure(f"risk_{risk}", background=colour)
        self.pv_tree.bind("<Double-1>", lambda _e: self.edit_prevent())
        self.pv_rows: dict[str, SR.Prevent] = {}

    def refresh_prevent(self) -> None:
        self.pv_tree.delete(*self.pv_tree.get_children())
        self.pv_rows = {}
        for x in SR.list_prevent(actor=self.principal, status=self.pv_status.get() or None,
                                 risk_level=self.pv_risk.get() or None,
                                 open_only=self.pv_open.get()):
            c = x.concern
            self.pv_rows[str(c.concern_id)] = x
            self.pv_tree.insert("", "end", iid=str(c.concern_id), tags=(
                "muted" if x.channel_status.startswith("Closed") else f"risk_{x.risk_level}",),
                values=(c.concern_id, f"{c.pupil_name} ({c.admission_no})", c.pupil_year,
                        c.raised_date, x.prevent_type, x.risk_level, x.pathway,
                        x.channel_status, x.prevent_outcome))

    def _pv_sel(self) -> SR.Prevent | None:
        sel = self.pv_tree.selection()
        if not sel:
            self._info("Prevent", "Select a referral first.")
            return None
        return self.pv_rows[sel[0]]

    def _prevent_fields(self, x: SR.Prevent | None) -> list:
        def v(k, d=""):
            return (getattr(x, k) or d) if x else d
        c = x.concern if x else None
        head = [] if x else [
            ("pupil_id", "Pupil", "", ("edit", self.pupils())),
            ("description", "Description (required)", "", "text"),
            ("raised_by", "Raised by", SG.staff_name(self.principal), None),
            ("raised_date", "Raised date", "", None),
            ("dsl_name", "DSL informed (name)", "", None),
            ("dsl_informed_date", "DSL informed date", "", None),
            ("referral_date", "Referral date (Channel / police)", "", None),
            ("referral_ref", "Referral ref", "", None)]
        return head + [
            ("prevent_type", "Concern type", v("prevent_type", SR.DEFAULT_PREVENT_TYPE),
             SR.PREVENT_TYPES),
            ("risk_level", "Risk level", v("risk_level", SR.DEFAULT_RISK), SR.RISK_LEVELS),
            ("indicators", "Indicators", v("indicators"), "text"),
            ("online_activity", "Online activity", v("online_activity"), "text"),
            ("pathway", "Referral pathway", v("pathway", SR.DEFAULT_PATHWAY), SR.PATHWAYS),
            ("agencies_involved", "Agencies involved", v("agencies_involved"), None),
            ("parents_informed_date", "Parents informed date", v("parents_informed_date"),
             None),
            ("next_review_date", "Next review date", v("next_review_date"), None),
            ("channel_status", "Status", v("channel_status", "Open"),
             [s for s in SR.PREVENT_STATUSES if not s.startswith("Closed")]
             if x is None else SR.PREVENT_STATUSES),
            ("prevent_outcome", "Outcome", v("prevent_outcome", "Pending"),
             SR.PREVENT_OUTCOMES)] + ([("notes", "Notes", c.notes or "", "text")] if c else [
                 ("notes", "Notes", "", "text")])

    def new_prevent(self) -> None:
        def save(v):
            v = {k: x for k, x in v.items() if x not in ("", None)}
            x = SR.create_prevent(v, actor=self.principal)
            self._refresh_all()
            self._info("Prevent", f"Created referral #{x.concern.concern_id}: "
                                  f"{x.concern.pupil_name} — {x.prevent_type} ({x.risk_level})")
        _form(self.parent, "New Prevent referral", self._prevent_fields(None), save,
              note="Recorded as a safeguarding concern (Radicalisation / Prevent).")

    def edit_prevent(self) -> None:
        x = self._pv_sel()
        if x is None:
            return

        def save(v):
            SR.update_prevent(x.concern.concern_id, v, actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"Edit Prevent referral #{x.concern.concern_id}",
              self._prevent_fields(x), save)

    def close_prevent(self) -> None:
        x = self._pv_sel()
        if x is None:
            return

        def save(v):
            SR.close_prevent(x.concern.concern_id, actor=self.principal, status=v["status"],
                             outcome=v["outcome"], notes=v["notes"])
            self._refresh_all()
        _form(self.parent, f"Close referral #{x.concern.concern_id}", [
            ("status", "Closed status", "Closed — no further action",
             [s for s in SR.PREVENT_STATUSES if s.startswith("Closed")]),
            ("outcome", "Outcome", "No further action", SR.PREVENT_OUTCOMES),
            ("notes", "Closure notes", "", "text")], save)

    def delete_prevent(self) -> None:
        x = self._pv_sel()
        if x is None:
            return

        def save(v):
            SG.delete(x.concern.concern_id, actor=self.principal, reason=v["reason"])
            self._refresh_all()
        _form(self.parent, f"Delete referral #{x.concern.concern_id}",
              [("reason", "Why (required)", "", "text")], save,
              note="Only for one recorded in error.")

    # ── Transfers ────────────────────────────────────────────────────

    def _build_transfers(self, tab) -> None:
        ttk.Label(tab, text=f"Leavers whose safeguarding file hasn't been sent (within "
                            f"{SR.TRANSFER_DAYS} school days of leaving)",
                  font=("", 11, "bold")).pack(anchor="w")
        self._bar(tab, (("Transfer file…", self._tr_file), ("Record transfer…", self._tr_record),
                        ("Refresh", self.refresh_transfers)))
        self.lv_tree = _tree(tab, [("pupil", "Pupil", 240), ("left", "Left", 90),
                                   ("dest", "Destination", 220), ("due", "Send by", 90),
                                   ("flag", "", 70)], height=6)
        self.lv_rows: dict[str, dict] = {}
        ttk.Label(tab, text="Files sent", font=("", 11, "bold")).pack(anchor="w", pady=(8, 2))
        self._bar(tab, (("Receipt confirmed…", self._tr_receipt),))
        self.tr_tree = _tree(tab, [("id", "ID", 45), ("pupil", "Pupil", 220),
                                   ("dest", "To", 200), ("method", "How", 170),
                                   ("sent", "Sent", 90), ("by", "By", 120),
                                   ("rec", "Receipt", 160)], height=8)
        self.tr_rows: dict[str, SR.Transfer] = {}

    def refresh_transfers(self) -> None:
        self.lv_tree.delete(*self.lv_tree.get_children())
        self.lv_rows = {}
        for i, x in enumerate(SR.leavers_to_transfer(actor=self.principal)):
            p = x["pupil"]
            self.lv_rows[str(i)] = x
            self.lv_tree.insert("", "end", iid=str(i), tags=("bad",) if x["overdue"] else (),
                                values=(f"{p.display_name} ({p.admission_no})",
                                        x["leaving_date"], x["destination"], x["due"],
                                        "OVERDUE" if x["overdue"] else ""))
        self.tr_tree.delete(*self.tr_tree.get_children())
        self.tr_rows = {}
        for t in SR.list_transfers(actor=self.principal):
            self.tr_rows[str(t.transfer_id)] = t
            self.tr_tree.insert("", "end", iid=str(t.transfer_id),
                                tags=() if t.received_date else ("warn",), values=(
                t.transfer_id, f"{t.pupil_name} ({t.admission_no})", t.destination, t.method,
                t.sent_date, t.sent_by or "",
                f"{t.received_date} {t.received_by_name or ''}" if t.received_date else
                "not confirmed"))

    def _lv_pupil(self) -> P.Pupil | None:
        sel = self.lv_tree.selection()
        if not sel:
            self._info("Transfers", "Select a leaver first (or use Pupil file).")
            return None
        return self.lv_rows[sel[0]]["pupil"]

    def transfer_file(self, p: P.Pupil) -> None:
        try:
            text = SR.transfer_file(p.pupil_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Transfer file", e)
            return
        _text_window(self.parent, f"Transfer file — {p.display_name}", text, size="900x620",
                     save_name=f"cp_file_{p.admission_no}.txt",
                     on_save=lambda _path: self._ask_record(p))

    def _ask_record(self, p: P.Pupil) -> None:
        if messagebox.askyesno("Transfer file", "File saved. Record that it has been sent "
                                                "to the new school now?", parent=self._top()):
            self.record_transfer(p)

    def _tr_file(self) -> None:
        p = self._lv_pupil()
        if p:
            self.transfer_file(p)

    def _tr_record(self) -> None:
        p = self._lv_pupil()
        if p:
            self.record_transfer(p)

    def record_transfer(self, p: P.Pupil) -> None:
        lv = SR._leaving(p.pupil_id)

        def save(v):
            SR.record_transfer(p.pupil_id, v, actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"Record transfer — {p.display_name}", [
            ("destination", "Sent to (school / setting)",
             (lv.destination_school if lv else "") or "", None),
            ("method", "How", SR.TRANSFER_METHODS[0], SR.TRANSFER_METHODS),
            ("sent_date", "Sent on (blank = today)", "", None),
            ("notes", "Notes (e.g. spoke to their DSL)", "", "text")], save,
            note="Open concerns are marked Transferred. Send the file separately from the "
                 "main pupil file, and ask for confirmation of receipt.")

    def _tr_receipt(self) -> None:
        sel = self.tr_tree.selection()
        if not sel:
            self._info("Receipt", "Select a transfer first.")
            return
        t = self.tr_rows[sel[0]]

        def save(v):
            SR.receipt_confirmed(t.transfer_id, actor=self.principal, received_by=v["who"],
                                 day=v["day"] or None)
            self.refresh_transfers()
        _form(self.parent, f"Receipt — transfer #{t.transfer_id}", [
            ("who", "Confirmed by (their DSL)", "", None),
            ("day", "Date (blank = today)", "", None)], save)

    # ── Reports ──────────────────────────────────────────────────────

    def _build_reports(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        self.rep_by = tk.StringVar(value=self.state.get("report_by", "category"))
        self.rep_from = tk.StringVar(value="")
        self.rep_to = tk.StringVar(value="")
        ttk.Label(bar, text="Group by:").pack(side="left")
        cb = ttk.Combobox(bar, textvariable=self.rep_by, state="readonly", width=10,
                          values=["category", "level", "year", "severity", "status", "month"])
        cb.pack(side="left", padx=(4, 8))
        cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh_reports())
        for label, var in (("From:", self.rep_from), ("To:", self.rep_to)):
            ttk.Label(bar, text=label).pack(side="left")
            ttk.Entry(bar, textvariable=var, width=11).pack(side="left", padx=(2, 6))
        ttk.Button(bar, text="Apply", command=self.refresh_reports).pack(side="left")
        ttk.Button(bar, text="Pupils with open concerns…", command=self.at_risk).pack(
            side="left", padx=6)
        self.rep_tree = _tree(tab, [("group", "Group", 320), ("concerns", "Concerns", 80),
                                    ("open", "Open", 70), ("pupils", "Pupils", 70),
                                    ("referred", "Referred", 80)])
        self.rep_text = tk.StringVar()
        ttk.Label(tab, textvariable=self.rep_text, foreground="#555", wraplength=900,
                  justify="left").pack(anchor="w", pady=(6, 0))

    def refresh_reports(self) -> None:
        self.state["report_by"] = self.rep_by.get()
        try:
            rows = SGR.analysis(actor=self.principal, by=self.rep_by.get(),
                                date_from=self.rep_from.get() or None,
                                date_to=self.rep_to.get() or None)
            s = SGR.cohort_summary(actor=self.principal, date_from=self.rep_from.get() or None,
                                   date_to=self.rep_to.get() or None)
        except _ERRORS as e:
            self._err("Reports", e)
            return
        self.rep_tree.delete(*self.rep_tree.get_children())
        for g in rows:
            self.rep_tree.insert("", "end", values=(g["group"], g["concerns"], g["open"],
                                                    g["pupils"], g["referred"]))
        self.rep_text.set(f"Concerns {s['total']}, open {s['open']}, open critical "
                          f"{s['open_critical']}, new {s['new']}.  By status: "
                          + ", ".join(f"{k} {v}" for k, v in s["by_status"].items())
                          + ".  By severity: "
                          + ", ".join(f"{k} {v}" for k, v in s["by_severity"].items()))

    def at_risk(self) -> None:
        def save(v):
            got = SGR.pupils_with_concerns(actor=self.principal, severity_min=v["sev"])
            lines = [f"{len(got)} pupil(s) with open concerns at {v['sev']} or above", ""]
            for cs in got.values():
                lines.append(f"{cs[0].pupil_name} ({cs[0].admission_no}) — {len(cs)} concern(s)")
                lines += [f"    #{c.concern_id:<5} {c.severity:<8} {c.category[:28]:<28} "
                          f"{c.status}" for c in cs]
            _text_window(self.parent, "Pupils with open concerns", "\n".join(lines))
        _form(self.parent, "Pupils with open concerns",
              [("sev", "Minimum severity", "High", SG.SEVERITIES)], save)

    # ── Access log ───────────────────────────────────────────────────

    def _build_access(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        self.acc_pupil = tk.StringVar(value="")
        self.acc_user = tk.StringVar(value="")
        ttk.Label(bar, text="Pupil:").pack(side="left")
        ttk.Combobox(bar, textvariable=self.acc_pupil, values=self.pupils(), width=34).pack(
            side="left", padx=(2, 8))
        ttk.Label(bar, text="User:").pack(side="left")
        ttk.Entry(bar, textvariable=self.acc_user, width=14).pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply", command=self.refresh_access).pack(side="left")
        ttk.Label(tab, text="Every time a pupil's safeguarding record is read, by whom.",
                  foreground="#555").pack(anchor="w")
        self.acc_tree = _tree(tab, [("at", "When", 140), ("user", "User", 110),
                                    ("role", "Role", 70), ("pupil", "Pupil", 240),
                                    ("concern", "Concern", 60), ("what", "What", 160)])

    def refresh_access(self) -> None:
        p = SG._pupil(self.acc_pupil.get()) if self.acc_pupil.get().strip() else None
        rows = SG.access_log(actor=self.principal, pupil_id=p.pupil_id if p else None,
                             username=self.acc_user.get() or None)
        self.acc_tree.delete(*self.acc_tree.get_children())
        for a in rows:
            self.acc_tree.insert("", "end", values=(a["at"], a["username"], a["role"] or "",
                                                    a["pupil"], a["concern_id"] or "",
                                                    a["what"]))

    # ── Team ─────────────────────────────────────────────────────────

    def _build_team(self, tab) -> None:
        ttk.Label(tab, text="Who staff go to, and who gets the urgent e-mail. With nobody "
                            "listed, every login with the safeguarding lead role does.",
                  foreground="#555", wraplength=900).pack(anchor="w")
        self._bar(tab, (("Add / change…", self.team_edit), ("Remove", self.team_remove),
                        ("Refresh", self.refresh_team)))
        self.team_tree = _tree(tab, [("name", "Name", 200), ("role", "Role", 140),
                                     ("phone", "Phone", 130), ("email", "E-mail", 220),
                                     ("user", "Login", 110)], height=8)
        self.team_rows: dict[str, dict] = {}

    def refresh_team(self) -> None:
        self.team_tree.delete(*self.team_tree.get_children())
        self.team_rows = {}
        for m in SG.team():
            self.team_rows[m["username"]] = m
            self.team_tree.insert("", "end", iid=m["username"],
                                  tags=() if m["listed"] else ("muted",),
                                  values=(m["name"], m["team_role"], m["phone"],
                                          m["email"] or "(none - phone)", m["username"]))

    def team_edit(self) -> None:
        sel = self.team_tree.selection()
        m = self.team_rows.get(sel[0]) if sel else None
        from education_system.systems.secondary.infrastructure.authentication import accounts
        try:
            users = [s["username"] for s in accounts.staff_logins()]
        except Exception:  # noqa: BLE001
            users = []

        def save(v):
            SG.set_team_member(v["username"], v, actor=self.principal)
            self.refresh_team()
        _form(self.parent, "Safeguarding team member", [
            ("username", "Staff login", m["username"] if m else "", ("edit", users)),
            ("team_role", "Role", m["team_role"] if m else "Deputy DSL", SG.TEAM_ROLES),
            ("phone", "Phone", m["phone"] if m else "", None),
            ("email", "E-mail (blank = the login's)", "", None)], save)

    def team_remove(self) -> None:
        sel = self.team_tree.selection()
        if not sel or not messagebox.askyesno("Remove", f"Take {sel[0]} off the team?",
                                              parent=self._top()):
            return
        try:
            SG.remove_team_member(sel[0], actor=self.principal)
        except _ERRORS as e:
            self._err("Remove", e)
            return
        self.refresh_team()


def draw_safeguarding(parent: ttk.Frame, *, principal: Principal, state: dict,
                      open_pupil: Callable[[int], None] | None = None) -> SafeguardingPage:
    return SafeguardingPage(parent, principal=principal, state=state, open_pupil=open_pupil)
