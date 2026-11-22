"""Wellbeing screen.

The old Wellbeing window is the first tab ("Check-ins") with its toolbar
(Year, Pupil and Status filters, Action only; Apply, Log, Edit, Status, Low
ratings, Pupil summary, Delete, Refresh), its columns (ID, Date, Pupil, Yr,
Source, Mood, Conf, Conn, Avg, Action, Status), its row colours (action,
low) and its check-in dialog (Pupil ID, Date, Source, Mood, Confidence,
Connection, Action needed, Recorded by, Status, Follow-up date, Follow-up
with, Stressors, Supports, Action summary, Notes). Added: Flagged only,
Trend, Refer…, Open pupil, History, Export CSV, and the safeguarding prompt.

New tabs: Caseload, Referrals, Support plans and Surveys. Rules are in
:mod:`modules.wellbeing.domain.wellbeing`.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox
from education_system.systems.secondary.modules.wellbeing.domain import wellbeing as WB
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
YEARS = ("7", "8", "9", "10", "11")
_ERRORS = W.ERRORS
_problems = W.problems
_text_window = W.text_window
_form = W.form_dialog
_TAGS = {**W.STANDARD_TAGS, "action": "#fff2cc", "low": "#fde7e7",
         "flag": {"background": "#f8c8c8", "foreground": "#700"}}
_RATINGS = ["", "1", "2", "3", "4", "5"]
SAFEGUARDING_BANNER = ("Worried a pupil is at risk of harm? Use \"Report a Safeguarding "
                       "Concern\" - don't only record it here.")


def _tree(parent, columns, height: int = 16, select: str = "browse") -> ttk.Treeview:
    return W.tree(parent, columns, height=height, select=select,
                  stretch={"pupil", "reason", "need", "title", "summary"}, tags=_TAGS)


def _r(v) -> str:
    return "" if v is None else str(v)


def _checkin_fields(c: WB.CheckIn | None, pupil: str = "") -> list:
    """The old dialog's fields, in its order."""
    def g(k, default=""):
        v = getattr(c, k) if c else None
        return default if v is None else v
    return [
        ("pupil_id", "Pupil ID / admission no.", c.admission_no if c else pupil, None),
        ("checkin_date", "Date (blank = today)", g("checkin_date"), None),
        ("source", "Source", g("source", WB.DEFAULT_SOURCE), WB.CHECKIN_SOURCES),
        ("mood_rating", "Mood (1-5)", _r(g("mood_rating", None)), _RATINGS),
        ("confidence_rating", "Confidence (1-5)", _r(g("confidence_rating", None)), _RATINGS),
        ("connection_rating", "Connection (1-5)", _r(g("connection_rating", None)), _RATINGS),
        ("action_needed", "Action needed", bool(c and c.action_needed), "check"),
        ("recorded_by", "Recorded by (blank = you)", g("recorded_by"), None),
        ("status", "Status", g("status", WB.DEFAULT_STATUS), WB.CHECKIN_STATUSES),
        ("follow_up_date", "Follow-up date", g("follow_up_date"), None),
        ("follow_up_with", "Follow-up with", g("follow_up_with"), None),
        ("stressors", "Stressors", g("stressors"), "text"),
        ("supports", "Supports", g("supports"), "text"),
        ("action_summary", "Action summary", g("action_summary"), "text"),
        ("notes", "Notes", g("notes"), "text"),
    ]


def _referral_fields(r: WB.Referral | None, pupil: str = "", reason: str = "") -> list:
    def g(k, default=""):
        v = getattr(r, k) if r else None
        return default if v is None else v
    return [
        ("pupil_id", "Pupil ID / admission no.", r.admission_no if r else pupil, None),
        ("service", "Service", g("service", WB.SERVICES[0]), WB.SERVICES),
        ("referral_date", "Referral date (blank = today)", g("referral_date"), None),
        ("reason", "Reason (required)", g("reason", reason), "text"),
        ("urgency", "Urgency", g("urgency", "Routine"), WB.URGENCIES),
        ("consent", "Consent", g("consent", WB.CONSENTS[0]), WB.CONSENTS),
        ("status", "Status", g("status", "Referred"), WB.REFERRAL_STATUSES),
        ("contact_name", "Service contact", g("contact_name"), None),
        ("accepted_date", "Accepted on", g("accepted_date"), None),
        ("first_appointment", "First appointment", g("first_appointment"), None),
        ("closed_date", "Closed on", g("closed_date"), None),
        ("outcome", "Outcome", g("outcome"), ["", *WB.REFERRAL_OUTCOMES]),
        ("outcome_notes", "Outcome notes", g("outcome_notes"), "text"),
    ]


def _plan_fields(w: WB.Plan | None, pupil: str = "") -> list:
    def g(k, default=""):
        v = getattr(w, k) if w else None
        return default if v is None else v
    return [
        ("pupil_id", "Pupil ID / admission no.", w.admission_no if w else pupil, None),
        ("start_date", "Start (blank = today)", g("start_date"), None),
        ("review_date", "Review date (blank = 6 weeks)", g("review_date"), None),
        ("key_adult", "Key adult", g("key_adult"), None),
        ("status", "Status", g("status", "Active"), WB.PLAN_STATUSES),
        ("need", "Need (required)", g("need"), "text"),
        ("strategies", "Strategies (for all staff)", g("strategies"), "text"),
        ("staff_actions", "Staff actions", g("staff_actions"), "text"),
        ("pupil_actions", "Pupil actions", g("pupil_actions"), "text"),
        ("family_actions", "Family actions", g("family_actions"), "text"),
        ("outcome", "Outcome (when closed)", g("outcome"), "text"),
    ]


class WellbeingPage:
    TABS = ("Check-ins", "Caseload", "Referrals", "Support plans", "Surveys")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil = open_pupil
        self.editor = WB.is_editor(principal)
        activity_log.record("wellbeing.view")
        ttk.Label(parent, text="Wellbeing", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(parent, text=SAFEGUARDING_BANNER, foreground="#a33").pack(anchor="w")
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(
            anchor="w", pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._built: set[str] = set()
        start = state.get("tab") if state.get("tab") in self.TABS else "Check-ins"
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

    def _button(self, bar, text: str, command, editor_only: bool = False) -> ttk.Button:
        b = ttk.Button(bar, text=text, command=command)
        if editor_only and not self.editor:
            b.state(["disabled"])
        b.pack(side="left", padx=2)
        return b

    def _builders(self) -> dict[str, tuple[Callable, Callable]]:
        return {"Check-ins": (self._build_checkins, self.refresh),
                "Caseload": (self._build_caseload, self.refresh_caseload),
                "Referrals": (self._build_referrals, self.refresh_referrals),
                "Support plans": (self._build_plans, self.refresh_plans),
                "Surveys": (self._build_surveys, self.refresh_surveys)}

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        build, refresh = self._builders()[name]
        if name not in self._built:
            self._built.add(name)
            build(self.tabs[name])
        refresh()

    def _refresh_all(self) -> None:
        for name, (_b, fn) in self._builders().items():
            if name in self._built:
                fn()

    def _open_from(self, tree, rows: dict) -> None:
        sel = tree.selection()
        if sel and self.open_pupil:
            self.open_pupil(rows[sel[0]].pupil_id if hasattr(rows[sel[0]], "pupil_id")
                            else rows[sel[0]]["pupil_id"])

    def _safeguarding_prompt(self, data: dict[str, Any]) -> None:
        """Show the check's warnings; the safeguarding one always tells the
        user to report it. "No" keeps the form open."""
        warnings = WB.check_checkin(data)
        if warnings and not messagebox.askyesno(
                "Wellbeing", "\n\n".join(warnings) + "\n\nSave the check-in now?",
                parent=self._top()):
            raise WB.ValidationError(["Not saved yet"])

    # ── Check-ins (the old window) ───────────────────────────────────

    _COLUMNS = [("id", "ID", 50), ("date", "Date", 90), ("pupil", "Pupil", 180),
                ("year", "Yr", 40), ("source", "Source", 120), ("mood", "Mood", 50),
                ("conf", "Conf", 50), ("conn", "Conn", 50), ("avg", "Avg", 50),
                ("act", "Action", 55), ("status", "Status", 90), ("fu", "Follow-up", 90)]

    def _build_checkins(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.year = tk.StringVar(value=self.state.get("year", ""))
        self.pupil = tk.StringVar(value=self.state.get("pupil", ""))
        self.status = tk.StringVar(value=self.state.get("status", ""))
        self.action_only = tk.BooleanVar(value=self.state.get("action_only", False))
        self.flag_only = tk.BooleanVar(value=False)
        ttk.Label(bar, text="Year:").pack(side="left", padx=(0, 4))
        yb = ttk.Combobox(bar, textvariable=self.year, values=["", *YEARS], width=4,
                          state="readonly")
        yb.pack(side="left", padx=(0, 6))
        ttk.Label(bar, text="Pupil:").pack(side="left", padx=(0, 4))
        ttk.Entry(bar, textvariable=self.pupil, width=12).pack(side="left", padx=(0, 6))
        ttk.Label(bar, text="Status:").pack(side="left", padx=(0, 4))
        sb = ttk.Combobox(bar, textvariable=self.status, values=["", *WB.CHECKIN_STATUSES],
                          width=11, state="readonly")
        sb.pack(side="left", padx=(0, 6))
        for w in (yb, sb):
            w.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        ttk.Checkbutton(bar, text="Action only", variable=self.action_only,
                        command=self.refresh).pack(side="left", padx=4)
        ttk.Checkbutton(bar, text="Flagged only", variable=self.flag_only,
                        command=self.refresh).pack(side="left", padx=4)
        bar1 = ttk.Frame(tab)
        bar1.pack(fill="x", pady=(0, 4))
        for text, cmd, lead in (("Apply", self.refresh, False), ("Log", self.log, False),
                                ("Edit", self.edit, False), ("Status", self.set_status, False),
                                ("Low ratings", self.low, False),
                                ("Pupil summary", self.pupil_summary, False),
                                ("Delete", self.delete, True), ("Refresh", self.refresh, False)):
            self._button(bar1, text, cmd, lead)
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(0, 6))
        for text, cmd, lead in (("View", self.view, False), ("Trend", self.trend, False),
                                ("Refer…", self.refer_from_checkin, True),
                                ("Open pupil", lambda: self._open_from(self.tree, self.rows),
                                 False),
                                ("History", self.history, False),
                                ("Export CSV…", self.export, False)):
            self._button(bar2, text, cmd, lead)
        self.tree = _tree(tab, self._COLUMNS)
        self.tree.bind("<Double-1>", lambda _e: self.view())
        self.rows: dict[str, WB.CheckIn] = {}

    def refresh(self) -> None:
        y, pref, st = self.year.get(), self.pupil.get().strip(), self.status.get()
        self.state.update(year=y, pupil=pref, status=st, action_only=self.action_only.get())
        pid = None
        if pref:
            p = WB._pupil(pref)
            pid = p.pupil_id if p else -1
        try:
            rows = WB.list_checkins(actor=self.principal, year_group=y or None, pupil_id=pid,
                                    status=st or None, action_only=self.action_only.get(),
                                    flagged_only=self.flag_only.get())
        except _ERRORS as e:
            self._err("Wellbeing", e)
            return
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        for c in rows:
            self.rows[str(c.checkin_id)] = c
            tag = ("flag" if c.safeguarding_flag else
                   "low" if c.lowest is not None and c.lowest <= WB.LOW_THRESHOLD else
                   "action" if c.action_needed else "muted" if c.status == "Closed" else "")
            self.tree.insert("", "end", iid=str(c.checkin_id), tags=(tag,) if tag else (),
                             values=(c.checkin_id, c.checkin_date,
                                     f"{c.pupil_name} ({c.admission_no})", c.pupil_year,
                                     c.source, _r(c.mood_rating), _r(c.confidence_rating),
                                     _r(c.connection_rating), _r(c.average_rating),
                                     "Yes" if c.action_needed else "", c.status,
                                     c.follow_up_date or ""))
        if self.editor:
            s = WB.cohort_summary(year_group=y or None)
            self.summary_var.set(
                f"Check-ins: {s['total']}    Pupils: {s['pupils']}    Avg mood: "
                f"{_r(s['avg_mood']) or '-'}    Action needed: {s['action_needed']}    "
                f"Flagged: {s['flagged']}    Open referrals: {s['open_referrals']}    "
                f"Active plans: {s['active_plans']}")
        else:
            self.summary_var.set(f"{len(rows)} check-in(s) you can see (your own, and your "
                                 "form / year's)")

    def _selected(self, title: str) -> WB.CheckIn | None:
        sel = self.tree.selection()
        if not sel:
            self._info(title, "Select a check-in first.")
            return None
        return WB.get_checkin(int(sel[0]))

    def log(self, pupil: str = "") -> None:
        def save(v):
            self._safeguarding_prompt(v)
            c = WB.log_checkin(v, actor=self.principal)
            self._refresh_all()
            if c.safeguarding_flag:
                messagebox.showwarning("Wellbeing", "Saved and flagged.\n\n"
                                       + WB.SAFEGUARDING_ADVICE, parent=self._top())
        _form(self.parent, "Log check-in", _checkin_fields(None, pupil), save,
              note="Ratings 1 (low) to 5 (high). " + SAFEGUARDING_BANNER)

    def edit(self) -> None:
        c = self._selected("Edit check-in")
        if c is None:
            return
        if not WB.can_edit_checkin(self.principal, c):
            self._info("Edit check-in", "Only the wellbeing lead or the person who recorded it "
                                        "can change a check-in.")
            return

        def save(v):
            v.pop("pupil_id", None)
            self._safeguarding_prompt(v)
            WB.update(c.checkin_id, v, actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"Edit check-in #{c.checkin_id}", _checkin_fields(c), save)

    def set_status(self) -> None:
        c = self._selected("Status")
        if c is None:
            return

        def save(v):
            WB.set_status(c.checkin_id, v["status"], actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"Status - check-in #{c.checkin_id}",
              [("status", "Status", c.status, WB.CHECKIN_STATUSES)], save)

    def delete(self) -> None:
        c = self._selected("Delete check-in")
        if c is None or not messagebox.askyesno(
                "Delete check-in", f"Delete check-in #{c.checkin_id} for {c.pupil_name}?",
                parent=self._top()):
            return
        try:
            WB.delete(c.checkin_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Delete check-in", e)
            return
        self._refresh_all()

    def view(self) -> None:
        c = self._selected("View")
        if c is None:
            return
        lines = [f"{c.pupil_name} ({c.admission_no}), Year {c.pupil_year} - {c.checkin_date}",
                 ""]
        if c.safeguarding_flag:
            lines += ["!! " + WB.SAFEGUARDING_ADVICE, ""]
        for label, v in (("Source", c.source), ("Mood", c.mood_rating),
                         ("Confidence", c.confidence_rating),
                         ("Connection", c.connection_rating), ("Average", c.average_rating),
                         ("Stressors", c.stressors), ("Supports", c.supports),
                         ("Action needed", "Yes" if c.action_needed else "No"),
                         ("Action summary", c.action_summary), ("Status", c.status),
                         ("Follow-up", f"{c.follow_up_date or '-'} with "
                                       f"{c.follow_up_with or '-'}"),
                         ("Recorded by", c.recorded_by), ("Survey", c.survey_id),
                         ("Notes", c.notes)):
            if v not in (None, ""):
                lines.append(f"{label + ':':<16} {v}")
        _text_window(self.parent, f"Check-in #{c.checkin_id}", "\n".join(lines))

    def low(self) -> None:
        def save(v):
            got = WB.low_wellbeing(threshold=int(v["threshold"] or WB.LOW_THRESHOLD),
                                   year_group=self.year.get() or None, actor=self.principal)
            lines = [f"Pupils whose latest check-in has a rating at or below "
                     f"{v['threshold']}:", ""]
            for rows in got.values():
                c = rows[0]
                lines.append(f"{c.pupil_name:<28} Y{c.pupil_year:<3} {c.checkin_date}  mood "
                             f"{_r(c.mood_rating) or '-'} conf {_r(c.confidence_rating) or '-'}"
                             f" conn {_r(c.connection_rating) or '-'}  {c.status}")
            if not got:
                lines.append("None.")
            _text_window(self.parent, "Low ratings", "\n".join(lines))
        _form(self.parent, "Low ratings", [("threshold", "At or below", "2",
                                            ["1", "2", "3", "4", "5"])], save)

    def pupil_summary(self) -> None:
        c = self._selected("Pupil summary")
        if c is None:
            return
        s = WB.pupil_summary(c.pupil_id, actor=self.principal)
        lines = [f"{c.pupil_name} ({c.admission_no})", "",
                 f"Check-ins: {s['count']}   Action needed: {s['action_needed']}",
                 f"Average mood {_r(s['avg_mood']) or '-'}, confidence "
                 f"{_r(s['avg_confidence']) or '-'}, connection "
                 f"{_r(s['avg_connection']) or '-'}",
                 "By status: " + ", ".join(f"{k} {v}" for k, v in s["by_status"].items())]
        if WB.can_see_referrals(self.principal, c.pupil_year):
            lines += ["", "Referrals:"] + [f"  #{r.referral_id} {r.referral_date} {r.service} "
                                           f"- {r.status}" for r in s["referrals"]] or ["  -"]
        lines += ["", "Support plans:"] + [f"  #{w.plan_id} {w.status}, review {w.review_date}"
                                           f": {w.need[:60]}" for w in s["plans"]]
        lines += ["", "Recent check-ins:"]
        for x in s["checkins"][:10]:
            lines.append(f"  {x.checkin_date}  avg {_r(x.average_rating) or '-':<5} {x.source:<18}"
                         f" {x.status}")
        _text_window(self.parent, "Pupil summary", "\n".join(lines))

    def trend(self) -> None:
        c = self._selected("Trend")
        if c is None:
            return
        rows = WB.trend(c.pupil_id)
        lines = [f"{c.pupil_name} - average rating per check-in (1-5)", ""]
        lines += [f"{d}  {a:4.2f}  {'█' * int(round(a * 4))}" for d, a in rows] or ["No ratings."]
        _text_window(self.parent, "Trend", "\n".join(lines))

    def refer_from_checkin(self) -> None:
        c = self._selected("Refer")
        if c is None:
            return
        self._new_referral(c.admission_no, c.action_summary or c.stressors or "", c.checkin_id)

    def history(self) -> None:
        c = self._selected("History")
        if c is None:
            return
        _text_window(self.parent, "History", "\n".join(
            f"{h['at']}  {h['actor']:<14} {h['kind']:<8} {h['action']:<10} "
            + ", ".join(f"{k}={v}" for k, v in h["detail"].items())
            for h in WB.history(pupil_id=c.pupil_id)) or "No changes recorded.")

    def export(self) -> None:
        path = filedialog.asksaveasfilename(parent=self._top(), defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")],
                                            initialfile="wellbeing.csv")
        if not path:
            return
        try:
            n = WB.export_csv(path, actor=self.principal, year_group=self.year.get() or None,
                              status=self.status.get() or None)
        except _ERRORS as e:
            self._err("Export", e)
            return
        self._info("Export", f"Exported {n} check-in(s).")

    # ── Caseload ─────────────────────────────────────────────────────

    def _build_caseload(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.key_adult = tk.StringVar(value=self.state.get("key_adult", ""))
        ttk.Label(bar, text="Key adult:").pack(side="left")
        e = ttk.Entry(bar, textvariable=self.key_adult, width=16)
        e.pack(side="left", padx=(4, 8))
        e.bind("<Return>", lambda _e: self.refresh_caseload())
        self._button(bar, "Apply", self.refresh_caseload)
        self._button(bar, "Open pupil", lambda: self._open_from(self.case_tree,
                                                                self.case_rows))
        self._button(bar, "Log check-in", lambda: self.log(self._case_ref()))
        self._button(bar, "New plan", lambda: self.new_plan(self._case_ref()), True)
        self._button(bar, "New referral", lambda: self._new_referral(self._case_ref()), True)
        self.case_tree = _tree(tab, [("pupil", "Pupil", 200), ("year", "Yr", 40),
                                     ("form", "Form", 55), ("latest", "Latest", 60),
                                     ("trend", "Trend", 60), ("open", "Open", 45),
                                     ("fu", "Follow-up", 90), ("refs", "Referrals", 170),
                                     ("plan", "Plan review", 100), ("adult", "Key adult", 110)])
        self.case_rows: dict[str, dict] = {}

    def _case_ref(self) -> str:
        sel = self.case_tree.selection()
        return self.case_rows[sel[0]]["admission_no"] if sel else ""

    def refresh_caseload(self) -> None:
        self.state["key_adult"] = self.key_adult.get()
        try:
            rows = WB.caseload(actor=self.principal, key_adult=self.key_adult.get() or None)
        except _ERRORS as e:
            self._err("Caseload", e)
            return
        self.case_tree.delete(*self.case_tree.get_children())
        self.case_rows = {}
        arrows = {"up": "↑", "down": "↓", "steady": "→", "": ""}
        for e in rows:
            iid = str(e["pupil_id"])
            self.case_rows[iid] = e
            tag = ("flag" if e["flagged"] else "bad" if e["latest"] is not None and
                   e["latest"] <= WB.LOW_THRESHOLD else "warn" if e["review_due"] else "")
            self.case_tree.insert("", "end", iid=iid, tags=(tag,) if tag else (), values=(
                f"{e['pupil_name']} ({e['admission_no']})", e["year"], e["form"] or "",
                _r(e["latest"]), arrows[e["trend"]], e["open_checkins"], e["follow_up"] or "",
                ", ".join(e["referrals"]),
                (e["plan"].review_date + (" due" if e["review_due"] else "")) if e["plan"]
                else "", e["key_adult"] or ""))

    # ── Referrals ────────────────────────────────────────────────────

    def _build_referrals(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.ref_service = tk.StringVar(value="")
        self.ref_open = tk.BooleanVar(value=True)
        ttk.Label(bar, text="Service:").pack(side="left")
        cb = ttk.Combobox(bar, textvariable=self.ref_service, values=["", *WB.SERVICES],
                          state="readonly", width=24)
        cb.pack(side="left", padx=(4, 8))
        cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh_referrals())
        ttk.Checkbutton(bar, text="Open only", variable=self.ref_open,
                        command=self.refresh_referrals).pack(side="left", padx=4)
        for text, cmd, lead in (("New", lambda: self._new_referral(""), True),
                                ("Edit / update", self.edit_referral, True),
                                ("Delete", self.delete_referral, True),
                                ("Report by service", self.referral_report, False),
                                ("Open pupil", lambda: self._open_from(self.ref_tree,
                                                                       self.ref_rows), False)):
            self._button(bar, text, cmd, lead)
        self.ref_tree = _tree(tab, [("id", "ID", 45), ("date", "Referred", 90),
                                    ("pupil", "Pupil", 190), ("service", "Service", 170),
                                    ("urg", "Urgency", 75), ("status", "Status", 95),
                                    ("wait", "Days", 50), ("outcome", "Outcome", 130),
                                    ("reason", "Reason", 220)])
        self.ref_tree.bind("<Double-1>", lambda _e: self.edit_referral())
        self.ref_rows: dict[str, WB.Referral] = {}

    def refresh_referrals(self) -> None:
        try:
            rows = WB.list_referrals(actor=self.principal,
                                     service=self.ref_service.get() or None,
                                     open_only=self.ref_open.get())
        except _ERRORS as e:
            self._err("Referrals", e)
            return
        self.ref_tree.delete(*self.ref_tree.get_children())
        self.ref_rows = {}
        for r in rows:
            self.ref_rows[str(r.referral_id)] = r
            tag = "bad" if r.urgency != "Routine" and r.is_open else (
                "muted" if not r.is_open else "")
            self.ref_tree.insert("", "end", iid=str(r.referral_id), tags=(tag,) if tag else (),
                                 values=(r.referral_id, r.referral_date,
                                         f"{r.pupil_name} ({r.admission_no})", r.service,
                                         r.urgency, r.status, r.waiting_days, r.outcome or "",
                                         r.reason))

    def _new_referral(self, pupil: str, reason: str = "", checkin_id: int | None = None
                      ) -> None:
        def save(v):
            if WB.safeguarding_signs(v.get("reason")) and not messagebox.askyesno(
                    "Referral", WB.SAFEGUARDING_ADVICE + "\n\nSave the referral too?",
                    parent=self._top()):
                raise WB.ValidationError(["Not saved yet"])
            WB.create_referral({**v, "checkin_id": checkin_id}, actor=self.principal)
            self._refresh_all()
        _form(self.parent, "New referral", _referral_fields(None, pupil, reason), save,
              note="Get consent first (unless it's an emergency). The check-in it came from "
                   "is marked Escalated." if checkin_id else
                   "Get consent first (unless it's an emergency).")

    def _sel_referral(self, title: str) -> WB.Referral | None:
        if "Referrals" not in self._built:
            return None
        sel = self.ref_tree.selection()
        if not sel:
            self._info(title, "Select a referral first.")
            return None
        return self.ref_rows[sel[0]]

    def edit_referral(self) -> None:
        r = self._sel_referral("Referral")
        if r is None:
            return

        def save(v):
            v.pop("pupil_id", None)
            WB.update_referral(r.referral_id, v, actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"Referral #{r.referral_id} - {r.pupil_name}", _referral_fields(r),
              save)

    def delete_referral(self) -> None:
        r = self._sel_referral("Delete referral")
        if r is None or not messagebox.askyesno("Delete referral",
                                                f"Delete referral #{r.referral_id}?",
                                                parent=self._top()):
            return
        try:
            WB.delete_referral(r.referral_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Delete referral", e)
            return
        self._refresh_all()

    def referral_report(self) -> None:
        lines = [f"{'Service':<28} {'Refs':>5} {'Open':>5} {'Accepted':>9} {'Avg wait':>9}  "
                 "Outcomes"]
        for g in WB.referral_report():
            lines.append(f"{g['service']:<28} {g['referrals']:>5} {g['open']:>5} "
                         f"{g['accepted']:>9} {_r(g['avg_wait']) or '-':>9}  "
                         + ", ".join(f"{k} {v}" for k, v in g["outcomes"].items()))
        _text_window(self.parent, "Referrals by service", "\n".join(lines))

    # ── Support plans ────────────────────────────────────────────────

    def _build_plans(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.plan_status = tk.StringVar(value="Active")
        ttk.Label(bar, text="Status:").pack(side="left")
        cb = ttk.Combobox(bar, textvariable=self.plan_status, values=["", *WB.PLAN_STATUSES],
                          state="readonly", width=8)
        cb.pack(side="left", padx=(4, 8))
        cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh_plans())
        for text, cmd, lead in (("New", lambda: self.new_plan(""), True),
                                ("View", self.view_plan, False),
                                ("Edit", self.edit_plan, True),
                                ("Review…", self.review_plan, True),
                                ("Delete", self.delete_plan, True),
                                ("Open pupil", lambda: self._open_from(self.plan_tree,
                                                                       self.plan_rows), False)):
            self._button(bar, text, cmd, lead)
        self.plan_tree = _tree(tab, [("id", "ID", 45), ("pupil", "Pupil", 200),
                                     ("start", "Start", 90), ("review", "Review", 90),
                                     ("adult", "Key adult", 120), ("status", "Status", 70),
                                     ("need", "Need", 300)])
        self.plan_tree.bind("<Double-1>", lambda _e: self.view_plan())
        self.plan_rows: dict[str, WB.Plan] = {}

    def refresh_plans(self) -> None:
        try:
            rows = WB.list_plans(actor=self.principal, status=self.plan_status.get() or None)
        except _ERRORS as e:
            self._err("Support plans", e)
            return
        self.plan_tree.delete(*self.plan_tree.get_children())
        self.plan_rows = {}
        for w in rows:
            self.plan_rows[str(w.plan_id)] = w
            self.plan_tree.insert("", "end", iid=str(w.plan_id),
                                  tags=("warn",) if w.review_due else (),
                                  values=(w.plan_id, f"{w.pupil_name} ({w.admission_no})",
                                          w.start_date, w.review_date, w.key_adult or "",
                                          w.status, w.need))

    def _sel_plan(self, title: str) -> WB.Plan | None:
        if "Support plans" not in self._built:
            return None
        sel = self.plan_tree.selection()
        if not sel:
            self._info(title, "Select a plan first.")
            return None
        return WB.get_plan(int(sel[0]))

    def new_plan(self, pupil: str) -> None:
        def save(v):
            WB.create_plan(v, actor=self.principal)
            self._refresh_all()
        _form(self.parent, "New support plan", _plan_fields(None, pupil), save)

    def view_plan(self) -> None:
        w = self._sel_plan("Support plan")
        if w is None:
            return
        lines = [f"{w.pupil_name} ({w.admission_no}) - support plan #{w.plan_id} ({w.status})",
                 f"From {w.start_date}, review {w.review_date}, key adult {w.key_adult or '-'}",
                 ""]
        for label, v in (("Need", w.need), ("Strategies", w.strategies),
                         ("Staff actions", w.staff_actions), ("Pupil actions", w.pupil_actions),
                         ("Family actions", w.family_actions), ("Outcome", w.outcome)):
            if v:
                lines += [f"{label}:", f"  {v}", ""]
        reviews = WB.plan_reviews(w.plan_id)
        if reviews:
            lines.append("Reviews:")
            lines += [f"  {r['review_date']}  {r['summary']}" for r in reviews]
        _text_window(self.parent, "Support plan", "\n".join(lines))

    def edit_plan(self) -> None:
        w = self._sel_plan("Edit plan")
        if w is None:
            return

        def save(v):
            v.pop("pupil_id", None)
            WB.update_plan(w.plan_id, v, actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"Support plan #{w.plan_id}", _plan_fields(w), save)

    def review_plan(self) -> None:
        w = self._sel_plan("Review plan")
        if w is None:
            return

        def save(v):
            WB.review_plan(w.plan_id, actor=self.principal, summary=v["summary"],
                           next_review=v["next"] or None, close=v["close"],
                           outcome=v["outcome"])
            self._refresh_all()
        _form(self.parent, f"Review plan #{w.plan_id} - {w.pupil_name}", [
            ("summary", "How it's going (required)", "", "text"),
            ("next", "Next review (blank = 6 weeks)", "", None),
            ("close", "Close the plan", False, "check"),
            ("outcome", "Outcome (when closing)", "", "text")], save)

    def delete_plan(self) -> None:
        w = self._sel_plan("Delete plan")
        if w is None or not messagebox.askyesno("Delete plan", f"Delete plan #{w.plan_id}?",
                                                parent=self._top()):
            return
        try:
            WB.delete_plan(w.plan_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Delete plan", e)
            return
        self._refresh_all()

    # ── Surveys ──────────────────────────────────────────────────────

    def _build_surveys(self, tab) -> None:
        ttk.Label(tab, text="Mood survey rounds. Staff record answers with Log (Source: Mood "
                            "survey, Survey ID); pupils can answer from their portal while a "
                            "survey is open.", foreground="#555", wraplength=900).pack(
            anchor="w")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=4)
        for text, cmd, lead in (("New", lambda: self.edit_survey(None), True),
                                ("Edit", self.edit_selected_survey, True),
                                ("Results", self.survey_results, False),
                                ("Record answer", self.record_answer, False),
                                ("Delete", self.delete_survey, True)):
            self._button(bar, text, cmd, lead)
        self.sv_tree = _tree(tab, [("id", "ID", 45), ("title", "Title", 240),
                                   ("scope", "Who", 110), ("open", "Opens", 90),
                                   ("close", "Closes", 90), ("status", "Status", 70)])
        self.sv_tree.bind("<Double-1>", lambda _e: self.survey_results())

    def refresh_surveys(self) -> None:
        self.sv_tree.delete(*self.sv_tree.get_children())
        for s in WB.list_surveys():
            self.sv_tree.insert("", "end", iid=str(s.survey_id),
                                tags=("good",) if s.is_open_on() else (),
                                values=(s.survey_id, s.title, s.scope, s.open_date,
                                        s.close_date, s.status))

    def _sel_survey(self) -> WB.Survey | None:
        sel = self.sv_tree.selection()
        if not sel:
            self._info("Surveys", "Select a survey first.")
            return None
        return WB.get_survey(int(sel[0]))

    def edit_selected_survey(self) -> None:
        s = self._sel_survey()
        if s is not None:
            self.edit_survey(s)

    def edit_survey(self, s: WB.Survey | None) -> None:
        def save(v):
            WB.save_survey(v, actor=self.principal, survey_id=s.survey_id if s else None)
            self.refresh_surveys()
        _form(self.parent, "Survey" if s is None else f"Survey #{s.survey_id}", [
            ("title", "Title", s.title if s else "", None),
            ("year_group", "Year group (blank = whole school)", _r(s.year_group) if s else "",
             ["", *YEARS]),
            ("form_group", "Form (optional)", s.form_group or "" if s else "", None),
            ("open_date", "Opens (blank = today)", s.open_date if s else "", None),
            ("close_date", "Closes (blank = a week later)", s.close_date if s else "", None),
            ("status", "Status", s.status if s else "Draft", WB.SURVEY_STATUSES),
            ("question", "Question / prompt", s.question or "" if s else "", "text")], save)

    def record_answer(self) -> None:
        s = self._sel_survey()
        if s is None:
            return

        def save(v):
            self._safeguarding_prompt(v)
            WB.log_checkin({**v, "survey_id": s.survey_id, "source": "Mood survey"},
                           actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"Answer - {s.title}", [
            ("pupil_id", "Pupil ID / admission no.", "", None),
            ("mood_rating", "Mood (1-5)", "", _RATINGS),
            ("confidence_rating", "Confidence (1-5)", "", _RATINGS),
            ("connection_rating", "Connection (1-5)", "", _RATINGS),
            ("notes", "Anything else", "", "text")], save)

    def survey_results(self) -> None:
        s = self._sel_survey()
        if s is None:
            return
        r = WB.survey_results(s.survey_id)
        lines = [f"{s.title} ({s.scope}, {s.open_date} to {s.close_date})", "",
                 f"Responses: {r['responses']} of {r['pupils']} ("
                 f"{_r(r['rate']) or '-'}%)",
                 f"Average mood {_r(r['avg_mood']) or '-'}, confidence "
                 f"{_r(r['avg_confidence']) or '-'}, connection {_r(r['avg_connection']) or '-'}",
                 "", f"Low scores ({len(r['low'])}):"]
        lines += [f"  {c.pupil_name}  mood {_r(c.mood_rating) or '-'}  conn "
                  f"{_r(c.connection_rating) or '-'}" for c in r["low"]]
        if r["flagged"]:
            lines += ["", "Flagged for safeguarding words:"] + [f"  {c.pupil_name}"
                                                                 for c in r["flagged"]]
        lines += ["", f"Not answered ({len(r['missing'])}):"]
        lines += [f"  {p.display_name} ({p.form_group or '-'})" for p in r["missing"][:200]]
        _text_window(self.parent, "Survey results", "\n".join(lines))

    def delete_survey(self) -> None:
        s = self._sel_survey()
        if s is None or not messagebox.askyesno("Delete survey", f"Delete '{s.title}'?",
                                                parent=self._top()):
            return
        try:
            WB.delete_survey(s.survey_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Delete survey", e)
            return
        self.refresh_surveys()


def draw_wellbeing(parent: ttk.Frame, *, principal: Principal, state: dict,
                   open_pupil: Callable[[int], None] | None = None) -> WellbeingPage:
    return WellbeingPage(parent, principal=principal, state=state, open_pupil=open_pupil)
