"""Suspensions & Exclusions screen.

The old "Disciplinary" window is the first tab ("Cases"), with its toolbar
(Year, Type, Severity and Status filters; Apply, New, Edit, Events, Status,
Delete, Refresh), its columns (ID, Start, Pupil, Yr, Type, Severity, Days,
Status, Reason), its severity colours, its case dialog (Pupil ID, Type,
Severity, Incident date, Start date, End date, Days (auto), Decision maker,
Status, Appeal decision, Return date, Reason, Notes) and its Events window
(Add event, Delete selected, Refresh; ID, Date, Type, Participants,
Summary). Added to it: Steps & deadlines, Notice home, Family told, Governors /
LA told, Governors' decision, Independent review, Mark registers, Take off
roll, Withdraw, Open pupil, Pupil summary, History and Export CSV.

New tabs: Due (outstanding steps across the school and pupils ready to come
off roll), Out today and Reports. The rules are in
:mod:`modules.behaviour.domain.exclusions`.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox
from education_system.systems.secondary.modules.behaviour.domain import exclusions as EX
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


def _tree(parent, columns, height: int = 16, select: str = "browse") -> ttk.Treeview:
    t = W.tree(parent, columns, height=height, select=select,
               stretch={"pupil", "reason", "step", "summary", "group"}, tags=W.STANDARD_TAGS)
    for sev, colour in _SEVERITY_COLOURS.items():
        t.tag_configure(f"sev_{sev}", background=colour)
    return t


def _fields(c: EX.Case | None, pupil: str = "") -> list:
    """The old dialog's fields, in its order, then the new ones."""
    return [
        ("pupil_id", "Pupil ID / admission no.", c.admission_no if c else pupil, None),
        ("case_type", "Type", c.case_type if c else EX.DEFAULT_TYPE, EX.CASE_TYPES),
        ("severity", "Severity", c.severity if c else EX.DEFAULT_SEVERITY, EX.SEVERITIES),
        ("incident_date", "Incident date", c.incident_date if c else "", None),
        ("start_date", "Start date", c.start_date if c else "", None),
        ("end_date", "End date (last day out)", c.end_date if c else "", None),
        ("days", "Days (auto)", c.days if c and c.days is not None else "", None),
        ("decision_maker", "Decision maker", c.decision_maker if c else "", None),
        ("status", "Status", c.status if c else EX.DEFAULT_STATUS, EX.CASE_STATUSES),
        ("appeal_decision", "Appeal decision", c.appeal_decision if c else "", None),
        ("return_date", "Return date", c.return_date if c else "", None),
        ("reason", "Reason (required)", c.reason if c else "", "text"),
        ("notes", "Notes", c.notes if c else "", "text"),
        ("reason_category", "Reason category (census)", c.reason_category if c else "",
         ["", *EX.REASON_CATEGORIES]),
        ("provision_from", "Education from (day 6+)", c.provision_from if c else "", None),
        ("provision_details", "Where / what education", c.provision_details if c else "",
         None),
        ("reintegration_date", "Reintegration meeting", c.reintegration_date if c else "",
         None),
        ("related_entry_id", "Behaviour incident ID", c.related_entry_id if c else "", None),
    ]


class ExclusionsPage:
    TABS = ("Cases", "Due", "Out today", "Reports")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil = open_pupil
        self.editor = EX.is_editor(principal)
        activity_log.record("exclusions.view")
        ttk.Label(parent, text="Suspensions & Exclusions", font=("", 16, "bold")).pack(
            anchor="w")
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(
            anchor="w", pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._built: set[str] = set()
        start = state.get("tab") if state.get("tab") in self.TABS else "Cases"
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

    def _button(self, bar, text: str, command, editor_only: bool = False) -> None:
        b = ttk.Button(bar, text=text, command=command)
        if editor_only and not self.editor:
            b.state(["disabled"])
        b.pack(side="left", padx=2)

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        build = {"Cases": (self._build_cases, self.refresh),
                 "Due": (self._build_due, self.refresh_due),
                 "Out today": (self._build_out, self.refresh_out),
                 "Reports": (self._build_reports, self.refresh_reports)}[name]
        if name not in self._built:
            self._built.add(name)
            build[0](self.tabs[name])
        build[1]()

    def _refresh_all(self) -> None:
        for name, fn in (("Cases", self.refresh), ("Due", self.refresh_due),
                         ("Out today", self.refresh_out), ("Reports", self.refresh_reports)):
            if name in self._built:
                fn()

    def _confirm_warnings(self, data: dict[str, Any], case_id: int | None = None) -> None:
        """Ask about EX.check's warnings; "No" keeps the form open."""
        try:
            warnings = EX.check(data, actor=self.principal, case_id=case_id)
        except _ERRORS:
            return
        if warnings and not messagebox.askyesno(
                "Suspensions & Exclusions", "\n\n".join(warnings) + "\n\nSave anyway?",
                parent=self._top()):
            raise EX.ValidationError(["Not saved yet - change the details, or Save again and "
                                      "answer Yes"])

    def _insert(self, tree: ttk.Treeview, c: EX.Case, rows: dict) -> None:
        rows[str(c.case_id)] = c
        tag = "muted" if c.status == "Overturned" else f"sev_{c.severity}"
        tree.insert("", "end", iid=str(c.case_id), tags=(tag,),
                    values=(c.case_id, c.start_date, f"{c.pupil_name} ({c.admission_no})",
                            c.pupil_year, c.case_type, c.severity,
                            c.days if c.days is not None else "", c.status, c.reason))

    _COLUMNS = [("id", "ID", 50), ("start", "Start", 90), ("pupil", "Pupil", 190),
                ("year", "Yr", 40), ("type", "Type", 160), ("sev", "Severity", 80),
                ("days", "Days", 50), ("status", "Status", 90), ("reason", "Reason", 260)]

    # ── Cases (the old Disciplinary window) ──────────────────────────

    def _build_cases(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.year = tk.StringVar(value=self.state.get("year", ""))
        self.ctype = tk.StringVar(value=self.state.get("type", ""))
        self.sev = tk.StringVar(value=self.state.get("severity", ""))
        self.status = tk.StringVar(value=self.state.get("status", ""))
        for label, var, values, width in (
                ("Year:", self.year, ["", *YEARS], 5),
                ("Type:", self.ctype, ["", *EX.CASE_TYPES], 20),
                ("Severity:", self.sev, ["", *EX.SEVERITIES], 10),
                ("Status:", self.status, ["", *EX.CASE_STATUSES], 12)):
            ttk.Label(bar, text=label).pack(side="left", padx=(0, 4))
            cb = ttk.Combobox(bar, textvariable=var, values=values, state="readonly",
                              width=width)
            cb.pack(side="left", padx=(0, 6))
            cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        for text, cmd, lead in (("Apply", self.refresh, False), ("New", self.new, True),
                                ("Edit", self.edit, True), ("Events", self.events, False),
                                ("Status", self.set_status, True),
                                ("Delete", self.delete, True), ("Refresh", self.refresh, False)):
            self._button(bar, text, cmd, lead)
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(0, 6))
        for text, cmd, lead in (("Steps & deadlines", self.steps, False),
                                ("Notice home…", self.notice_home, True),
                                ("Family told…", self.family_told, True),
                                ("Governors / LA told…", self.notified, True),
                                ("Governors' decision…", self.governors, True),
                                ("Independent review…", self.review, True),
                                ("Mark registers", self.mark_registers, True),
                                ("Take off roll…", self.off_roll, True),
                                ("Withdraw…", self.withdraw, True)):
            self._button(bar2, text, cmd, lead)
        bar3 = ttk.Frame(tab)
        bar3.pack(fill="x", pady=(0, 6))
        for text, cmd in (("Open pupil", self._open_selected_pupil),
                          ("Pupil summary", self.pupil_summary), ("History", self.history),
                          ("Export CSV…", self.export)):
            self._button(bar3, text, cmd)
        self.tree = _tree(tab, self._COLUMNS)
        self.tree.bind("<Double-1>", lambda _e: self.events())
        self.rows: dict[str, EX.Case] = {}

    def refresh(self) -> None:
        y, t, sv, st = self.year.get(), self.ctype.get(), self.sev.get(), self.status.get()
        self.state.update(year=y, type=t, severity=sv, status=st)
        try:
            rows = EX.list_cases(year_group=y or None, case_type=t or None,
                                 severity=sv or None, status=st or None)
        except _ERRORS as e:
            self._err("Suspensions & Exclusions", e)
            return
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        for c in rows:
            self._insert(self.tree, c, self.rows)
        s = EX.cohort_summary(year_group=y or None)
        self.summary_var.set(f"Total: {s['total']}    Open: {s['open']}    Suspensions: "
                             f"{s['suspensions']}    Permanent: {s['permanent']}    "
                             f"Pupils: {s['pupils']}    Days: {s['total_days']}")

    def _selected(self, title: str) -> EX.Case | None:
        sel = self.tree.selection()
        if not sel:
            self._info(title, "Select a case first.")
            return None
        return self.rows[sel[0]]

    def new(self) -> None:
        def save(v):
            v = {k: x for k, x in v.items() if x not in ("", None)}
            self._confirm_warnings(v)
            c = EX.create_case(v, actor=self.principal)
            self._refresh_all()
            if c.is_formal and messagebox.askyesno(
                    "Suspensions & Exclusions",
                    f"Case #{c.case_id} saved: {c.case_type}, {c.period}"
                    + (f", {c.days} school day(s)" if c.days is not None else "")
                    + ".\n\nE-mail the notice to the family now?", parent=self._top()):
                self._send_notice(c, "")
        _form(self.parent, "New case", _fields(None), save,
              note="Suspensions and permanent exclusions are the headteacher's decision. "
                   "Days are counted in school days when left blank.")

    def edit(self) -> None:
        c = self._selected("Edit case")
        if c is None:
            return

        def save(v):
            v.pop("pupil_id", None)
            changes = {k: x for k, x in v.items() if str(x or "") != str(
                getattr(c, k) if getattr(c, k) is not None else "")}
            if "days" in changes and changes["days"] == "":
                changes["days"] = None
            self._confirm_warnings(changes, c.case_id)
            EX.update_case(c.case_id, changes, actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"Edit case #{c.case_id}", _fields(c), save,
              note="Change the dates and the days are recounted.")

    def set_status(self) -> None:
        c = self._selected("Status")
        if c is None:
            return

        def save(v):
            EX.set_status(c.case_id, v["status"], actor=self.principal,
                          appeal_decision=v["appeal_decision"])
            self._refresh_all()
        _form(self.parent, f"Status - case #{c.case_id}", [
            ("status", "Status", c.status, EX.CASE_STATUSES),
            ("appeal_decision", "Appeal decision (if Appealed/Overturned)",
             c.appeal_decision or "", None)], save)

    def delete(self) -> None:
        c = self._selected("Delete case")
        if c is None or not messagebox.askyesno(
                "Delete case", f"Delete case #{c.case_id} ({c.case_type}) and its events?",
                parent=self._top()):
            return
        try:
            EX.delete_case(c.case_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Delete case", e)
            return
        self._refresh_all()

    # ── The old Events window ────────────────────────────────────────

    def events(self) -> None:
        c = self._selected("Events")
        if c is None:
            return
        win, frm = W.dialog(self.parent, f"Events — case #{c.case_id} ({c.pupil_name})",
                            size="760x420")
        bar = ttk.Frame(frm)
        bar.pack(fill="x", pady=(0, 6))
        tree = _tree(frm, [("id", "ID", 50), ("date", "Date", 90), ("type", "Type", 150),
                           ("part", "Participants", 160), ("summary", "Summary", 300)],
                     height=12)
        rows: dict[str, EX.Event] = {}

        def refresh() -> None:
            tree.delete(*tree.get_children())
            rows.clear()
            for e in EX.list_events(c.case_id):
                rows[str(e.event_id)] = e
                tree.insert("", "end", iid=str(e.event_id),
                            values=(e.event_id, e.event_date, e.event_type,
                                    e.participants or "", e.summary))

        def add() -> None:
            def save(v):
                EX.add_event({**v, "case_id": c.case_id}, actor=self.principal)
                refresh()
            _form(win, f"Event — case #{c.case_id}", [
                ("event_date", "Date (blank = today)", "", None),
                ("event_type", "Type", EX.DEFAULT_EVENT_TYPE, EX.EVENT_TYPES),
                ("participants", "Participants", "", None),
                ("summary", "Summary (required)", "", "text"),
                ("outcome", "Outcome", "", "text"), ("follow_up", "Follow-up", "", "text"),
                ("notes", "Notes", "", "text")], save)

        def remove() -> None:
            sel = tree.selection()
            if not sel or not messagebox.askyesno("Delete event", "Delete the selected event?",
                                                  parent=win):
                return
            try:
                EX.delete_event(int(sel[0]), actor=self.principal)
            except _ERRORS as e:
                messagebox.showerror("Delete event", _problems(e), parent=win)
                return
            refresh()

        def view() -> None:
            sel = tree.selection()
            if sel:
                e = rows[sel[0]]
                _text_window(win, f"Event #{e.event_id}", "\n".join(
                    f"{k}: {v}" for k, v in (("Date", e.event_date), ("Type", e.event_type),
                                             ("Participants", e.participants),
                                             ("Summary", e.summary), ("Outcome", e.outcome),
                                             ("Follow-up", e.follow_up), ("Notes", e.notes),
                                             ("Recorded by", e.created_by)) if v))
        add_b = ttk.Button(bar, text="Add event", command=add)
        if not EX.can_add_event(self.principal, c):
            add_b.state(["disabled"])
        add_b.pack(side="left", padx=2)
        del_b = ttk.Button(bar, text="Delete selected", command=remove)
        if not self.editor:
            del_b.state(["disabled"])
        del_b.pack(side="left", padx=2)
        ttk.Button(bar, text="Refresh", command=refresh).pack(side="left", padx=2)
        ttk.Button(bar, text="View", command=view).pack(side="left", padx=2)
        tree.bind("<Double-1>", lambda _e: view())
        refresh()

    # ── Steps the law sets ───────────────────────────────────────────

    def steps(self) -> None:
        c = self._selected("Steps & deadlines")
        if c is None:
            return
        rows = EX.deadlines(c)
        lines = [f"Case #{c.case_id} - {c.pupil_name}: {c.case_type}, {c.period}", ""]
        if not rows:
            lines.append("No statutory steps for this case.")
        for d in rows:
            mark = f"done {d['done'][:10]}" if d["done"] else (
                "OVERDUE" if d["overdue"] else "to do")
            lines.append(f"{d['step']:<48} due {d['due'] or '-':<10}  {mark}")
            if d["note"]:
                lines.append(f"    {d['note']}")
        if c.case_type == EX.PERMANENT:
            probs = EX.off_roll_problems(c)
            lines += ["", "Off roll: " + ("ready" if not probs else "; ".join(probs))]
        _text_window(self.parent, "Steps & deadlines", "\n".join(lines))

    def _send_notice(self, c: EX.Case, note: str) -> None:
        res = EX.notify_parents(c.case_id, actor=self.principal, note=note)
        self._refresh_all()
        if not res["message_id"]:
            self._info("Notice home", "No contact with parental responsibility has an e-mail "
                                      "address. Tell the family another way and use "
                                      "\"Family told…\".")
            return
        text = f"{res['emails']} notice(s) prepared."
        from education_system.systems.secondary.modules.communication.gui import email_views

        def done(_report, error) -> None:
            try:
                self._info("Notice home", text + (f"\n\nQueued - delivery failed: {error}"
                                                  if error else "\n\nSent."))
            except tk.TclError:
                pass
        email_views.deliver_in_background(self.parent, res["message_id"], self.principal, done)

    def notice_home(self) -> None:
        c = self._selected("Notice home")
        if c is None:
            return

        def save(v):
            self._send_notice(c, v["note"])
        _form(self.parent, f"Notice home - case #{c.case_id}",
              [("note", "Extra message (optional)", "", "text")], save,
              note="The formal notice goes to contacts with parental responsibility: the "
                   "decision, the dates, the reason and their right to make representations.")

    def family_told(self) -> None:
        c = self._selected("Family told")
        if c is None:
            return

        def save(v):
            EX.record_parents_told(c.case_id, actor=self.principal, how=v["how"],
                                   day=v["day"] or None)
            self._refresh_all()
        _form(self.parent, f"Family told - case #{c.case_id}", [
            ("how", "How", "Phone call", ["Phone call", "Letter sent", "Meeting"]),
            ("day", "Date (blank = today)", "", None)], save)

    def notified(self) -> None:
        c = self._selected("Governors / LA told")
        if c is None:
            return
        who = {"Local authority": "la", "Governing board": "governors"}

        def save(v):
            EX.record_notified(c.case_id, who[v["who"]], actor=self.principal,
                               day=v["day"] or None)
            self._refresh_all()
        _form(self.parent, f"Told - case #{c.case_id}", [
            ("who", "Who was told", "Local authority", list(who)),
            ("day", "Date (blank = today)", "", None)], save)

    def governors(self) -> None:
        c = self._selected("Governors' decision")
        if c is None:
            return
        need = EX.governors_required(c)

        def save(v):
            done = EX.record_governors(c.case_id, decision=v["decision"],
                                       meeting_date=v["day"] or None, actor=self.principal,
                                       note=v["note"])
            self._refresh_all()
            due = EX.review_deadline(done)
            if due:
                self._info("Governors' decision", "Upheld. The family can ask for an "
                                                  f"independent review until {due}; the pupil "
                                                  "stays on roll until then.")
        _form(self.parent, f"Governors' decision - case #{c.case_id}", [
            ("decision", "Decision", "Upheld", EX.GOVERNOR_DECISIONS),
            ("day", "Meeting date (blank = today)", "", None),
            ("note", "Note", "", "text")], save,
            note={"must": "The governors must consider this case.",
                  "on request": "The governors consider this case if the parents ask."}.get(
                need or "", "The governors don't have to consider this case."))

    def review(self) -> None:
        c = self._selected("Independent review")
        if c is None:
            return

        def save(v):
            EX.record_review(c.case_id, actor=self.principal,
                             requested_date=v["requested"] or None,
                             review_date=v["review"] or None, outcome=v["outcome"] or None,
                             note=v["note"])
            self._refresh_all()
        _form(self.parent, f"Independent review - case #{c.case_id}", [
            ("requested", "Asked for on (blank = today / as recorded)",
             c.review_requested_date or "", None),
            ("review", "Panel date", c.review_date or "", None),
            ("outcome", "Outcome (blank = not heard yet)", c.review_outcome or "",
             ["", *EX.REVIEW_OUTCOMES]),
            ("note", "Note", "", "text")], save,
            note="Quash or Recommend reconsider sends the case back to the governors.")

    def mark_registers(self) -> None:
        c = self._selected("Mark registers")
        if c is None:
            return
        if not messagebox.askyesno("Mark registers", f"Mark E (or B from the education-from "
                                   f"date) for {c.pupil_name}'s days out up to today?",
                                   parent=self._top()):
            return
        try:
            r = EX.mark_attendance(c.case_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Mark registers", e)
            return
        self._info("Mark registers", f"Marked {r['saved']} session(s); kept {r['skipped']} "
                                     "already marked.")

    def off_roll(self) -> None:
        c = self._selected("Take off roll")
        if c is None:
            return
        probs = EX.off_roll_problems(c)
        if probs:
            self._info("Take off roll", "Not yet:\n\n" + "\n".join(f"• {p}" for p in probs))
            return

        def save(v):
            EX.remove_from_roll(c.case_id, actor=self.principal,
                                leaving_date=v["day"] or None, notes=v["notes"] or None)
            self._refresh_all()
            self._info("Take off roll", f"{c.pupil_name} is off roll. Enrolment & Leavers "
                                        "has the leaving record.")
        _form(self.parent, f"Take off roll - {c.pupil_name}", [
            ("day", "Leaving date (blank = today)", "", None),
            ("notes", "Leaving notes", "", "text")], save,
            note="Recorded in Enrolment & Leavers with the reason \"Permanent exclusion\".")

    def withdraw(self) -> None:
        c = self._selected("Withdraw")
        if c is None:
            return

        def save(v):
            EX.withdraw(c.case_id, actor=self.principal, reason=v["reason"])
            self._refresh_all()
        _form(self.parent, f"Withdraw case #{c.case_id}", [
            ("reason", "Why (required)", "", "text")], save,
            note="A withdrawn case stays on record but no longer counts.")

    # ── Pupil, history, export ───────────────────────────────────────

    def _open_selected_pupil(self) -> None:
        c = self._selected("Open pupil")
        if c and self.open_pupil:
            self.open_pupil(c.pupil_id)

    def pupil_summary(self) -> None:
        c = self._selected("Pupil summary")
        if c is None:
            return
        s = EX.case_summary(c.pupil_id)
        lines = [f"{c.pupil_name} ({c.admission_no}), Year {c.pupil_year}", "",
                 f"This year: {s['suspensions']} suspension(s), {s['suspension_days']} "
                 f"school day(s) - {s['days_left']} left of {EX.MAX_SUSPENSION_DAYS}", ""]
        for x in s["cases"]:
            lines.append(f"#{x.case_id:<4} {x.start_date}  {x.case_type:<22} "
                         f"{x.days if x.days is not None else '-':>3} day(s)  {x.status:<10} "
                         f"{x.reason[:50]}")
        _text_window(self.parent, "Pupil summary", "\n".join(lines))

    def history(self) -> None:
        c = self._selected("History")
        if c is None:
            return
        _text_window(self.parent, "History", "\n".join(
            f"{h['at']}  {h['actor']:<14} {h['action']:<12} "
            + ", ".join(f"{k}={v}" for k, v in h["detail"].items())
            for h in EX.history(c.case_id)) or "No changes recorded.")

    def export(self) -> None:
        path = filedialog.asksaveasfilename(parent=self._top(), defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")],
                                            initialfile="exclusions.csv")
        if not path:
            return
        try:
            n = EX.export_csv(path, actor=self.principal, year_group=self.year.get() or None,
                              case_type=self.ctype.get() or None,
                              severity=self.sev.get() or None,
                              status=self.status.get() or None)
        except _ERRORS as e:
            self._err("Export", e)
            return
        self._info("Export", f"Exported {n} case(s).")

    # ── Due ──────────────────────────────────────────────────────────

    def _build_due(self, tab) -> None:
        ttk.Label(tab, text="Steps still to do for suspensions and permanent exclusions, "
                            "soonest first.", font=("", 11, "bold")).pack(anchor="w")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(4, 4))
        self._button(bar, "Go to case", lambda: self._goto(self.due_tree, self.due_rows))
        self._button(bar, "Open pupil", lambda: self._open_from(self.due_tree, self.due_rows))
        self.due_tree = _tree(tab, [("due", "Due", 90), ("flag", "", 70), ("id", "Case", 50),
                                    ("pupil", "Pupil", 200), ("type", "Type", 150),
                                    ("step", "Step", 300)], height=12)
        self.due_tree.bind("<Double-1>", lambda _e: self._goto(self.due_tree, self.due_rows))
        self.due_rows: dict[str, EX.Case] = {}
        ttk.Label(tab, text="Permanent exclusions ready to take off roll (governors upheld, "
                            "review window passed or review upheld).",
                  font=("", 11, "bold")).pack(anchor="w", pady=(10, 4))
        self.roll_tree = _tree(tab, [("id", "Case", 50), ("pupil", "Pupil", 260),
                                     ("start", "From", 90), ("gov", "Governors", 120)],
                               height=4)
        self.roll_tree.bind("<Double-1>", lambda _e: self._goto(self.roll_tree,
                                                                self.roll_rows))
        self.roll_rows: dict[str, EX.Case] = {}

    def refresh_due(self) -> None:
        self.due_tree.delete(*self.due_tree.get_children())
        self.due_rows = {}
        for i, (c, d) in enumerate(EX.due()):
            iid = f"{c.case_id}:{i}"
            self.due_rows[iid] = c
            self.due_tree.insert("", "end", iid=iid, tags=("bad",) if d["overdue"] else (),
                                 values=(d["due"] or "", "OVERDUE" if d["overdue"] else "",
                                         c.case_id, f"{c.pupil_name} ({c.admission_no})",
                                         c.case_type, d["step"]))
        self.roll_tree.delete(*self.roll_tree.get_children())
        self.roll_rows = {}
        for c in EX.ready_for_off_roll():
            self.roll_rows[str(c.case_id)] = c
            self.roll_tree.insert("", "end", iid=str(c.case_id), values=(
                c.case_id, f"{c.pupil_name} ({c.admission_no})", c.start_date,
                c.governors_decision or ""))

    def _goto(self, tree, rows) -> None:
        sel = tree.selection()
        if not sel:
            return
        c = rows[sel[0]]
        self.book.select(self.TABS.index("Cases"))
        for v in (self.year, self.ctype, self.sev, self.status):
            v.set("")
        self.refresh()
        if self.tree.exists(str(c.case_id)):
            self.tree.selection_set(str(c.case_id))
            self.tree.see(str(c.case_id))

    def _open_from(self, tree, rows) -> None:
        sel = tree.selection()
        if sel and self.open_pupil:
            self.open_pupil(rows[sel[0]].pupil_id)

    # ── Out today ────────────────────────────────────────────────────

    def _build_out(self, tab) -> None:
        ttk.Label(tab, text="Pupils out of school today on a suspension or permanent "
                            "exclusion (set work; check education from day 6).",
                  foreground="#555").pack(anchor="w", pady=(0, 6))
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self._button(bar, "Go to case", lambda: self._goto(self.out_tree, self.out_rows))
        self._button(bar, "Open pupil", lambda: self._open_from(self.out_tree, self.out_rows))
        self.out_tree = _tree(tab, [("pupil", "Pupil", 220), ("year", "Yr", 40),
                                    ("form", "Form", 60), ("type", "Type", 150),
                                    ("period", "Period", 180), ("ret", "Back", 90),
                                    ("prov", "Education from", 110)])
        self.out_rows: dict[str, EX.Case] = {}

    def refresh_out(self) -> None:
        self.out_tree.delete(*self.out_tree.get_children())
        self.out_rows = {}
        for c in EX.out_on():
            self.out_rows[str(c.case_id)] = c
            self.out_tree.insert("", "end", iid=str(c.case_id), values=(
                f"{c.pupil_name} ({c.admission_no})", c.pupil_year, c.form_group or "",
                c.case_type, c.period, c.return_date or "", c.provision_from or "-"))

    # ── Reports ──────────────────────────────────────────────────────

    def _build_reports(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        self.rep_by = tk.StringVar(value=self.state.get("report_by", "type"))
        self.rep_year = tk.StringVar(value="")
        ttk.Label(bar, text="Group by:").pack(side="left")
        cb = ttk.Combobox(bar, textvariable=self.rep_by, state="readonly", width=10,
                          values=["type", "reason", "year", "severity", "month"])
        cb.pack(side="left", padx=(4, 8))
        ttk.Label(bar, text="Year:").pack(side="left")
        yb = ttk.Combobox(bar, textvariable=self.rep_year, state="readonly", width=5,
                          values=["", *YEARS])
        yb.pack(side="left", padx=(4, 8))
        for w in (cb, yb):
            w.bind("<<ComboboxSelected>>", lambda _e: self.refresh_reports())
        ttk.Label(bar, text=f"School year {EX.current_year()} (withdrawn cases left out)",
                  foreground="#777").pack(side="left")
        self.rep_tree = _tree(tab, [("group", "Group", 320), ("cases", "Cases", 70),
                                    ("days", "School days", 90), ("pupils", "Pupils", 70)])

    def refresh_reports(self) -> None:
        self.state["report_by"] = self.rep_by.get()
        try:
            rows = EX.analysis(by=self.rep_by.get(), year_group=self.rep_year.get() or None,
                               academic_year=EX.current_year())
        except _ERRORS as e:
            self._err("Reports", e)
            return
        self.rep_tree.delete(*self.rep_tree.get_children())
        for g in rows:
            self.rep_tree.insert("", "end", values=(g["group"], g["cases"], g["days"],
                                                    g["pupils"]))


def draw_exclusions(parent: ttk.Frame, *, principal: Principal, state: dict,
                    open_pupil: Callable[[int], None] | None = None) -> ExclusionsPage:
    return ExclusionsPage(parent, principal=principal, state=state, open_pupil=open_pupil)
