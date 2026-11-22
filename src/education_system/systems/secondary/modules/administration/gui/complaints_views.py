"""Complaints screen.

The old Complaints window's tabs are kept in order - Open, Overdue,
Stage 2 / Appeal, All and Summary - each list with its filter bar
(Category, Stage, Status, Outcome, Subject; Apply, Clear, New), its columns
(Id, Received, Complainant, Category, Subject, Stage, Severity, Status,
Outcome, Target), its row colours (by status, overdue, critical), its
actions (View / Edit, Acknowledge, Investigate, Issue response, Escalate,
Satisfaction, Close, Change status, Delete, Refresh) and the count, and the
edit dialog with every old field and the Flags. Added: Timeline, Add event,
Letter…, Panel…, Withdraw, Unreasonable…, Open pupil, History, Export CSV,
and the Serial complainants and Annual report tabs. Rules are in
:mod:`modules.administration.domain.complaints`.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox
from education_system.systems.secondary.modules.administration.domain import complaints as CM
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
_ERRORS = W.ERRORS
_problems = W.problems
_text_window = W.text_window
_form = W.form_dialog
_STATUS_TAGS = {"Received": "#eef3ff", "Acknowledged": "#e8f4fd",
                "Under Investigation": "#fff7d6", "Response Drafted": "#fff1c2",
                "Response Issued": "#e7f6ea", "Escalated": "#ffe4b3",
                "Closed": {"foreground": "#888"}}
_TAGS = {**W.STANDARD_TAGS, **_STATUS_TAGS,
         "overdue": {"background": "#ffd1d1", "foreground": "#8c0d0d"},
         "critical": {"background": "#ffb0b0", "foreground": "#6c0000"}}
_SCOPES = {"Open": dict(open_only=True), "Overdue": dict(overdue_only=True),
           "Stage 2 / Appeal": dict(stage2_or_higher=True), "All": {}}
_LETTERS = {"Acknowledgement": "acknowledgement", "Response": "response",
            "Escalation / panel": "escalation"}


def _tree(parent, columns, height: int = 16) -> ttk.Treeview:
    return W.tree(parent, columns, height=height,
                  stretch={"subject", "complainant", "summary", "group"}, tags=_TAGS)


def _fields(c: CM.Complaint | None) -> list:
    """Every field of the old edit dialog, then the new ones."""
    def g(k, default=""):
        v = getattr(c, k) if c else None
        return default if v is None else v
    return [
        ("received_on", "Received on (blank = today)", g("received_on"), None),
        ("complainant_name", "Complainant name*", g("complainant_name"), None),
        ("complainant_role", "Complainant role", g("complainant_role",
                                                   CM.DEFAULT_COMPLAINANT_ROLE),
         CM.COMPLAINANT_ROLES),
        ("contact_email", "Contact e-mail", g("contact_email"), None),
        ("contact_phone", "Contact phone", g("contact_phone"), None),
        ("subject", "Subject*", g("subject"), None),
        ("description", "Description", g("description"), "text"),
        ("category", "Category", g("category", CM.DEFAULT_CATEGORY), CM.CATEGORIES),
        ("stage", "Stage", g("stage", CM.DEFAULT_STAGE),
         CM.STAGES if c is None else [c.stage]),
        ("severity", "Severity (1-5)", g("severity", 2), ["1", "2", "3", "4", "5"]),
        ("assigned_to", "Assigned to / investigator", g("assigned_to"), None),
        ("acknowledged_on", "Acknowledged on", g("acknowledged_on"), None),
        ("target_response_date", "Target response date (blank = by stage)",
         g("target_response_date"), None),
        ("response_issued_on", "Response issued on", g("response_issued_on"), None),
        ("response_summary", "Response summary", g("response_summary"), "text"),
        ("outcome", "Outcome", g("outcome"), ["", *CM.OUTCOMES]),
        ("actions_taken", "Actions taken", g("actions_taken"), "text"),
        ("complainant_satisfaction", "Satisfaction",
         g("complainant_satisfaction", CM.DEFAULT_SATISFACTION), CM.SATISFACTIONS),
        ("status", "Status", g("status", CM.DEFAULT_STATUS), CM.STATUSES),
        ("closed_on", "Closed on", g("closed_on"), None),
        ("linked_to", "Linked to", g("linked_to"), None),
        ("notes", "Notes", g("notes"), "text"),
        ("complainant_informed", "Flags: complainant informed",
         bool(c and c.complainant_informed), "check"),
        ("escalated_to_stage_2", "Flags: escalated to stage 2",
         bool(c and c.escalated_to_stage_2), "check"),
        ("escalated_to_appeal", "Flags: escalated to appeal / governors",
         bool(c and c.escalated_to_appeal), "check"),
        ("governors_informed", "Flags: governors informed", bool(c and c.governors_informed),
         "check"),
        ("pupil_id", "Linked pupil (ID / admission no., optional)",
         _pupil_ref(c), None),
        ("complainant_address", "Complainant address", g("complainant_address"), "text"),
    ]


def _pupil_ref(c: CM.Complaint | None) -> str:
    if not c or not c.pupil_id:
        return ""
    p = CM.P.get_pupil(c.pupil_id)
    return p.admission_no if p else ""


class ComplaintsPage:
    TABS = ("Open", "Overdue", "Stage 2 / Appeal", "All", "Summary", "Serial complainants",
            "Annual report")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil = open_pupil
        self.editor = CM.is_editor(principal)
        activity_log.record("complaints.view")
        ttk.Label(parent, text="Complaints", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(parent, text="Stage 1 informal (a member of staff) → Stage 2 formal (the "
                               "headteacher) → Stage 3 governors' panel. Acknowledge within "
                               f"{CM.ACK_DAYS} school days.", foreground="#666").pack(
            anchor="w", pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self.lists: dict[str, dict[str, Any]] = {}
        self._built: set[str] = set()
        start = state.get("tab") if state.get("tab") in self.TABS else "Open"
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

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        if name not in self._built:
            self._built.add(name)
            if name in _SCOPES:
                self._build_list(self.tabs[name], name)
            else:
                {"Summary": self._build_summary, "Serial complainants": self._build_serial,
                 "Annual report": self._build_annual}[name](self.tabs[name])
        self._refresh(name)

    def _refresh(self, name: str) -> None:
        if name in _SCOPES:
            self.refresh_list(name)
        else:
            {"Summary": self.refresh_summary, "Serial complainants": self.refresh_serial,
             "Annual report": self.refresh_annual}[name]()

    def _refresh_all(self) -> None:
        for name in self._built:
            self._refresh(name)

    def _current(self) -> str:
        return self.TABS[self.book.index(self.book.select())]

    # ── The old list tabs ────────────────────────────────────────────

    _COLUMNS = [("id", "Id", 45), ("received", "Received", 90),
                ("complainant", "Complainant", 140), ("category", "Category", 150),
                ("subject", "Subject", 200), ("stage", "Stage", 150),
                ("severity", "Severity", 75), ("status", "Status", 120),
                ("outcome", "Outcome", 110), ("target", "Target", 90)]

    def _build_list(self, tab, scope: str) -> None:
        w: dict[str, Any] = {"scope": scope}
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        w["cat"], w["stage"], w["status"], w["outcome"], w["subj"] = (
            tk.StringVar() for _ in range(5))
        for label, var, values, width in (
                ("Category:", w["cat"], ["", *CM.CATEGORIES], 18),
                ("Stage:", w["stage"], ["", *CM.STAGES], 22),
                ("Status:", w["status"], ["", *CM.STATUSES], 16),
                ("Outcome:", w["outcome"], ["", *CM.OUTCOMES], 14)):
            if label == "Status:" and scope == "Open":
                continue
            ttk.Label(bar, text=label).pack(side="left")
            cb = ttk.Combobox(bar, textvariable=var, values=values, state="readonly",
                              width=width)
            cb.pack(side="left", padx=(2, 6))
            cb.bind("<<ComboboxSelected>>", lambda _e, s=scope: self.refresh_list(s))
        ttk.Label(bar, text="Subject:").pack(side="left")
        e = ttk.Entry(bar, textvariable=w["subj"], width=14)
        e.pack(side="left", padx=(2, 6))
        e.bind("<Return>", lambda _e, s=scope: self.refresh_list(s))
        self._button(bar, "Apply", lambda s=scope: self.refresh_list(s))
        self._button(bar, "Clear", lambda s=scope: self._clear(s))
        self._button(bar, "New", self.new, True)
        w["tree"] = _tree(tab, self._COLUMNS)
        w["tree"].bind("<Double-1>", lambda _e: self.edit())
        w["rows"] = {}
        actions = ttk.Frame(tab)
        actions.pack(fill="x", pady=(4, 2))
        for text, cmd, lead in (("View / Edit", self.edit, False),
                                ("Acknowledge", self.acknowledge, False),
                                ("Investigate", self.investigate, False),
                                ("Issue response", self.respond, False),
                                ("Escalate", self.escalate, True),
                                ("Satisfaction", self.satisfaction, False),
                                ("Close", self.close, True),
                                ("Change status", self.set_status, True),
                                ("Delete", self.delete, True),
                                ("Refresh", lambda s=scope: self.refresh_list(s), False)):
            self._button(actions, text, cmd, lead)
        w["count"] = ttk.Label(actions, text="")
        w["count"].pack(side="right")
        more = ttk.Frame(tab)
        more.pack(fill="x", pady=(2, 0))
        for text, cmd, lead in (("Timeline", self.timeline, False),
                                ("Add event…", self.add_event, False),
                                ("Letter…", self.letter, False),
                                ("Panel…", self.panel, True),
                                ("Withdraw…", self.withdraw, True),
                                ("Unreasonable…", self.unreasonable, True),
                                ("Open pupil", self._open_pupil, False),
                                ("History", self.history, False),
                                ("Export CSV…", self.export, False)):
            self._button(more, text, cmd, lead)
        self.lists[scope] = w

    def _clear(self, scope: str) -> None:
        w = self.lists[scope]
        for k in ("cat", "stage", "status", "outcome", "subj"):
            w[k].set("")
        self.refresh_list(scope)

    def refresh_list(self, scope: str) -> None:
        w = self.lists[scope]
        try:
            rows = CM.list_complaints(actor=self.principal, category=w["cat"].get() or None,
                                      stage=w["stage"].get() or None,
                                      status=w["status"].get() or None,
                                      outcome=w["outcome"].get() or None,
                                      subject_like=w["subj"].get().strip() or None,
                                      **_SCOPES[scope])
        except _ERRORS as e:
            self._err("Complaints", e)
            return
        t = w["tree"]
        t.delete(*t.get_children())
        w["rows"] = {}
        for c in rows:
            w["rows"][str(c.complaint_id)] = c
            tag = ("critical" if c.severity >= 5 and c.is_open else
                   "overdue" if c.overdue else c.status)
            t.insert("", "end", iid=str(c.complaint_id), tags=(tag,),
                     values=(c.complaint_id, c.received_on, c.complainant_name
                             + (" ⚑" if c.unreasonable else ""), c.category, c.subject,
                             c.stage, f"{c.severity} {c.severity_label}", c.status,
                             c.outcome or "", c.target_response_date or ""))
        w["count"].configure(text=f"{len(rows)} complaint(s)")

    def _selected(self, title: str) -> CM.Complaint | None:
        w = self.lists.get(self._current())
        sel = w["tree"].selection() if w else ()
        if not sel:
            self._info(title, "Select a complaint first.")
            return None
        return CM.get(int(sel[0]))

    def _confirm(self, data: dict[str, Any], complaint_id: int | None = None) -> None:
        try:
            warnings = CM.check(data, actor=self.principal, complaint_id=complaint_id)
        except _ERRORS:
            return
        if warnings and not messagebox.askyesno(
                "Complaints", "\n\n".join(warnings) + "\n\nSave anyway?", parent=self._top()):
            raise CM.ValidationError(["Not saved yet"])

    def new(self) -> None:
        def save(v):
            self._confirm(v)
            c = CM.create_complaint(v, actor=self.principal)
            self._refresh_all()
            if c.contact_email and messagebox.askyesno(
                    "Complaints", f"Complaint #{c.complaint_id} saved. Acknowledge by "
                                  f"{c.ack_due}.\n\nE-mail the acknowledgement now?",
                    parent=self._top()):
                self._acknowledge_and_send(c)
        _form(self.parent, "New complaint", _fields(None), save,
              note="Deadlines are set in school days from the received date.")

    def _acknowledge_and_send(self, c: CM.Complaint) -> None:
        try:
            CM.acknowledge(c.complaint_id, actor=self.principal)
            self._send(c.complaint_id, "acknowledgement", "")
        except _ERRORS as e:
            self._err("Acknowledge", e)

    def edit(self) -> None:
        c = self._selected("View / Edit")
        if c is None:
            return
        if not self.editor:
            self._view(c)
            return

        def save(v):
            v.pop("stage", None)
            if (v.get("pupil_id") or "") == _pupil_ref(c):
                v.pop("pupil_id", None)
            v["severity"] = int(v["severity"])
            self._confirm(v, c.complaint_id)
            CM.update_complaint(c.complaint_id, v, actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"Complaint #{c.complaint_id}", _fields(c), save,
              note=f"{c.stage}: acknowledge by {c.ack_due or '-'}, respond by "
                   f"{c.target_response_date or '-'}. Use Escalate to change the stage.")

    def _view(self, c: CM.Complaint) -> None:
        lines = [f"Complaint #{c.complaint_id} - {c.subject}", ""]
        for label, v in (("Received", c.received_on),
                         ("Complainant", f"{c.complainant_name} ({c.complainant_role})"),
                         ("Contact", " ".join(x for x in (c.contact_email, c.contact_phone)
                                              if x)),
                         ("Pupil", c.pupil_name), ("Category", c.category),
                         ("Stage", c.stage), ("Severity", f"{c.severity} {c.severity_label}"),
                         ("Assigned to", c.assigned_to),
                         ("Acknowledge by", c.ack_due), ("Acknowledged", c.acknowledged_on),
                         ("Respond by", c.target_response_date),
                         ("Responded", c.response_issued_on), ("Outcome", c.outcome),
                         ("Status", c.status), ("Description", c.description),
                         ("Response", c.response_summary), ("Actions", c.actions_taken)):
            if v:
                lines.append(f"{label + ':':<16} {v}")
        _text_window(self.parent, f"Complaint #{c.complaint_id}", "\n".join(lines))

    def acknowledge(self) -> None:
        c = self._selected("Acknowledge")
        if c is None:
            return

        def save(v):
            CM.acknowledge(c.complaint_id, actor=self.principal,
                           assigned_to=v.get("assigned") or None,
                           acknowledged_on=v["day"] or None,
                           target_response_date=v["target"] or None)
            self._refresh_all()
            if v["send"]:
                self._send(c.complaint_id, "acknowledgement", "")
        fields = [("day", "Acknowledged on (blank = today)", "", None),
                  ("target", "Target response date", c.target_response_date or "", None),
                  ("send", "E-mail the acknowledgement", bool(c.contact_email), "check")]
        if self.editor:
            fields.insert(0, ("assigned", "Assign to", c.assigned_to or "", None))
        _form(self.parent, f"Acknowledge #{c.complaint_id}", fields, save,
              note=f"Due by {c.ack_due or '-'} ({CM.ACK_DAYS} school days).")

    def investigate(self) -> None:
        c = self._selected("Investigate")
        if c is None:
            return
        try:
            CM.start_investigation(c.complaint_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Investigate", e)
            return
        self._refresh_all()

    def respond(self) -> None:
        c = self._selected("Issue response")
        if c is None:
            return

        def save(v):
            CM.issue_response(c.complaint_id, actor=self.principal, summary=v["summary"],
                              outcome=v["outcome"], issued_on=v["day"] or None,
                              actions_taken=v["actions"])
            self._refresh_all()
            if v["send"]:
                self._send(c.complaint_id, "response", "")
        _form(self.parent, f"Issue response - #{c.complaint_id}", [
            ("outcome", "Outcome*", "", CM.OUTCOMES),
            ("day", "Issued on (blank = today)", "", None),
            ("summary", "Response summary*", "", "text"),
            ("actions", "Actions taken", "", "text"),
            ("send", "E-mail the response", bool(c.contact_email), "check")], save,
            note=f"{c.stage} response, due {c.target_response_date or '-'}.")

    def escalate(self) -> None:
        c = self._selected("Escalate")
        if c is None:
            return
        later = list(CM.STAGES[c.stage_no:])
        if not later:
            self._info("Escalate", "The complaint is at the last stage.")
            return

        def save(v):
            CM.escalate(c.complaint_id, actor=self.principal, to_stage=v["stage"],
                        reason=v["reason"], requested_on=v["day"] or None)
            self._refresh_all()
            if v["send"]:
                self._send(c.complaint_id, "escalation", "")
        _form(self.parent, f"Escalate #{c.complaint_id} (now {c.stage})", [
            ("stage", "Escalate to", later[0], later),
            ("day", "Requested on (blank = today)", "", None),
            ("reason", "Reason", "", "text"),
            ("send", "E-mail the complainant", bool(c.contact_email), "check")], save,
            note="The complainant asks for the next stage once they have the response "
                 f"(normally within {CM.ESCALATE_WITHIN} school days).")

    def satisfaction(self) -> None:
        c = self._selected("Satisfaction")
        if c is None:
            return

        def save(v):
            CM.record_satisfaction(c.complaint_id, actor=self.principal,
                                   satisfaction=v["sat"])
            self._refresh_all()
        _form(self.parent, f"Satisfaction - #{c.complaint_id}",
              [("sat", "Complainant", c.complainant_satisfaction, CM.SATISFACTIONS)], save)

    def close(self) -> None:
        c = self._selected("Close")
        if c is None:
            return
        try:
            CM.close_complaint(c.complaint_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Close", e)
            return
        self._refresh_all()

    def set_status(self) -> None:
        c = self._selected("Change status")
        if c is None:
            return

        def save(v):
            CM.set_status(c.complaint_id, v["status"], actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"Status - #{c.complaint_id}",
              [("status", "Status", c.status, CM.STATUSES)], save)

    def delete(self) -> None:
        c = self._selected("Delete")
        if c is None or not messagebox.askyesno(
                "Delete", f"Delete complaint #{c.complaint_id} ({c.subject})?",
                parent=self._top()):
            return
        try:
            CM.delete_complaint(c.complaint_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Delete", e)
            return
        self._refresh_all()

    # ── Added actions ────────────────────────────────────────────────

    def timeline(self) -> None:
        c = self._selected("Timeline")
        if c is None:
            return
        win, frm = W.dialog(self.parent, f"Timeline — #{c.complaint_id} {c.subject}",
                            size="780x420")
        bar = ttk.Frame(frm)
        bar.pack(fill="x", pady=(0, 6))
        tree = _tree(frm, [("date", "Date", 90), ("type", "Type", 110),
                           ("stage", "Stage", 160), ("summary", "Summary", 330),
                           ("by", "By", 80)], height=12)

        def refresh() -> None:
            tree.delete(*tree.get_children())
            for e in CM.list_events(c.complaint_id):
                tree.insert("", "end", iid=str(e.event_id), values=(
                    e.event_date, e.event_type, e.stage or "", e.summary, e.created_by or ""))

        def remove() -> None:
            sel = tree.selection()
            if not sel or not messagebox.askyesno("Delete event", "Delete the selected event?",
                                                  parent=win):
                return
            try:
                CM.delete_event(int(sel[0]), actor=self.principal)
            except _ERRORS as e:
                messagebox.showerror("Delete event", _problems(e), parent=win)
                return
            refresh()
        ttk.Button(bar, text="Add event", command=lambda: self._event_form(
            win, c, refresh)).pack(side="left", padx=2)
        d = ttk.Button(bar, text="Delete selected", command=remove)
        if not self.editor:
            d.state(["disabled"])
        d.pack(side="left", padx=2)
        ttk.Button(bar, text="Refresh", command=refresh).pack(side="left", padx=2)
        refresh()

    def _event_form(self, owner, c: CM.Complaint, after: Callable[[], None]) -> None:
        def save(v):
            CM.add_event(c.complaint_id, v, actor=self.principal)
            after()
        _form(owner, f"Event - #{c.complaint_id}", [
            ("event_type", "Type", "Note", CM.EVENT_TYPES),
            ("event_date", "Date (blank = today)", "", None),
            ("summary", "Summary*", "", "text")], save)

    def add_event(self) -> None:
        c = self._selected("Add event")
        if c is not None:
            self._event_form(self.parent, c, self._refresh_all)

    def _send(self, complaint_id: int, kind: str, note: str) -> None:
        try:
            res = CM.send_letter(complaint_id, kind, actor=self.principal, note=note)
        except _ERRORS as e:
            self._err("Letter", e)
            return
        if not res["message_id"]:
            self._info("Letter", "There is no e-mail address for the complainant - post the "
                                 "letter and add an event.")
            return
        from education_system.systems.secondary.modules.communication.gui import email_views

        def done(_report, error) -> None:
            try:
                self._info("Letter", "Queued - delivery failed: " + str(error) if error
                           else "Sent.")
            except tk.TclError:
                pass
        email_views.deliver_in_background(self.parent, res["message_id"], self.principal, done)

    def letter(self) -> None:
        c = self._selected("Letter")
        if c is None:
            return

        def save(v):
            self._send(c.complaint_id, _LETTERS[v["kind"]], v["note"])
            self._refresh_all()
        _form(self.parent, f"Letter - #{c.complaint_id}", [
            ("kind", "Letter", "Acknowledgement", list(_LETTERS)),
            ("note", "Extra paragraph (optional)", "", "text")], save,
            note=f"To {c.contact_email or '(no e-mail address)'} through the school outbox.")

    def panel(self) -> None:
        c = self._selected("Panel")
        if c is None:
            return

        def save(v):
            CM.set_panel(c.complaint_id, actor=self.principal, panel_date=v["day"],
                         members=v["members"], note=v["note"])
            self._refresh_all()
        _form(self.parent, f"Governors' panel - #{c.complaint_id}", [
            ("day", "Panel date*", c.panel_date or "", None),
            ("members", "Members (comma-separated, 3+)*", c.panel_members or "", None),
            ("note", "Note", "", "text")], save,
            note="Stage 3 only. Members must not have been involved in the complaint.")

    def withdraw(self) -> None:
        c = self._selected("Withdraw")
        if c is None:
            return

        def save(v):
            CM.withdraw(c.complaint_id, actor=self.principal, reason=v["reason"])
            self._refresh_all()
        _form(self.parent, f"Withdraw #{c.complaint_id}",
              [("reason", "Why (optional)", "", "text")], save)

    def unreasonable(self) -> None:
        c = self._selected("Unreasonable")
        if c is None:
            return

        def save(v):
            CM.flag_unreasonable(c.complaint_id, v["flag"], actor=self.principal,
                                 notes=v["notes"], review_date=v["review"] or None)
            self._refresh_all()
        _form(self.parent, f"Unreasonable / serial complainant - {c.complainant_name}", [
            ("flag", "Flag this complainant", c.unreasonable or True, "check"),
            ("notes", "Why, and the communication plan", c.unreasonable_notes or "", "text"),
            ("review", "Review the flag on (blank = 6 months)", c.unreasonable_review or "",
             None)], save,
            note="Applies to all of this complainant's complaints. Untick to remove.")

    def _open_pupil(self) -> None:
        c = self._selected("Open pupil")
        if c is None:
            return
        if not c.pupil_id:
            self._info("Open pupil", "No pupil is linked to this complaint.")
        elif self.open_pupil:
            self.open_pupil(c.pupil_id)

    def history(self) -> None:
        c = self._selected("History")
        if c is None:
            return
        _text_window(self.parent, "History", "\n".join(
            f"{h['at']}  {h['actor']:<14} {h['action']:<12} "
            + ", ".join(f"{k}={v}" for k, v in h["detail"].items())
            for h in CM.history(c.complaint_id)) or "No changes recorded.")

    def export(self) -> None:
        path = filedialog.asksaveasfilename(parent=self._top(), defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")],
                                            initialfile="complaints.csv")
        if not path:
            return
        try:
            n = CM.export_csv(path, actor=self.principal, **_SCOPES.get(self._current(), {}))
        except _ERRORS as e:
            self._err("Export", e)
            return
        self._info("Export", f"Exported {n} complaint(s).")

    # ── Summary (old) ────────────────────────────────────────────────

    def _build_summary(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x")
        self._button(bar, "Refresh", self.refresh_summary)
        self.sum_text = tk.Text(tab, wrap="word", font=("TkFixedFont", 10), height=24)
        self.sum_text.pack(fill="both", expand=True, pady=6)

    def refresh_summary(self) -> None:
        if not self.editor:
            text = "The summary is for the complaints lead."
        else:
            s = CM.summary()
            lines = [f"Total: {s.total}   Open: {s.open_count}   Overdue: {s.overdue}   "
                     f"Closed: {s.closed_count}",
                     f"Serious or major: {s.serious_or_major}   At stage 2 or above: "
                     f"{s.at_stage_2_or_appeal}   Governors informed: {s.governors_informed}",
                     f"Upheld: {s.upheld_count}   Not upheld: {s.not_upheld_count}   "
                     f"Unreasonable flags: {s.unreasonable}",
                     "Average days to close: " + (f"{s.average_days_to_close}" if
                                                  s.average_days_to_close is not None else "-"),
                     ""]
            for title, d in (("By category", s.by_category), ("By stage", s.by_stage),
                             ("By status", s.by_status), ("By outcome", s.by_outcome)):
                lines.append(title + ":")
                lines += [f"    {k:<30} {v}" for k, v in d.items()] or ["    -"]
            text = "\n".join(lines)
        self.sum_text.configure(state="normal")
        self.sum_text.delete("1.0", "end")
        self.sum_text.insert("1.0", text)
        self.sum_text.configure(state="disabled")

    # ── Serial complainants ──────────────────────────────────────────

    def _build_serial(self, tab) -> None:
        ttk.Label(tab, text=f"Complainants with {CM.SERIAL_COUNT}+ complaints in "
                            f"{CM.SERIAL_MONTHS} months, or flagged as unreasonable.",
                  foreground="#555").pack(anchor="w")
        self.serial_tree = _tree(tab, [("complainant", "Complainant", 200),
                                       ("email", "E-mail", 200), ("count", "Complaints", 90),
                                       ("flag", "Flagged", 70), ("ids", "Ids", 160)])

    def refresh_serial(self) -> None:
        self.serial_tree.delete(*self.serial_tree.get_children())
        if not self.editor:
            return
        for x in CM.serial_complainants():
            self.serial_tree.insert("", "end", tags=("bad",) if x["flagged"] else (), values=(
                x["complainant"], x["email"] or "", x["count"], "Yes" if x["flagged"] else "",
                ", ".join(f"#{i}" for i in x["ids"])))

    # ── Annual report ────────────────────────────────────────────────

    def _build_annual(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x")
        self.ar_year = tk.StringVar(value=CM.current_year())
        ttk.Label(bar, text="School year:").pack(side="left")
        e = ttk.Entry(bar, textvariable=self.ar_year, width=9)
        e.pack(side="left", padx=4)
        e.bind("<Return>", lambda _e: self.refresh_annual())
        self._button(bar, "Show", self.refresh_annual)
        self.ar_text = tk.Text(tab, wrap="word", font=("TkFixedFont", 10), height=24)
        self.ar_text.pack(fill="both", expand=True, pady=6)

    def refresh_annual(self) -> None:
        if not self.editor:
            text = "The annual report is for the complaints lead."
        else:
            r = CM.annual_report(self.ar_year.get().strip() or None)
            lines = [f"Complaints report to governors - {r['academic_year']}", "",
                     f"Received: {r['received']}   Closed: {r['closed']}   Open: {r['open']}"
                     f"   Withdrawn: {r['withdrawn']}   Panels: {r['panels']}",
                     f"Responses on time: {r['responses_on_time']} of {r['responses']}"
                     + (f" ({r['on_time_pct']}%)" if r["on_time_pct"] is not None else ""),
                     "Average days to close: " + (str(r["avg_days_to_close"])
                                                  if r["avg_days_to_close"] is not None
                                                  else "-"),
                     f"Unreasonable / serial complainants: {r['unreasonable']}", ""]
            for title, key in (("By category", "by_category"),
                               ("Stage reached", "by_stage_reached"),
                               ("By outcome", "by_outcome"), ("By complainant", "by_role")):
                lines.append(title + ":")
                lines += [f"    {k:<32} {v}" for k, v in r[key].items()] or ["    -"]
            text = "\n".join(lines)
        self.ar_text.configure(state="normal")
        self.ar_text.delete("1.0", "end")
        self.ar_text.insert("1.0", text)
        self.ar_text.configure(state="disabled")


def draw_complaints(parent: ttk.Frame, *, principal: Principal, state: dict,
                    open_pupil: Callable[[int], None] | None = None) -> ComplaintsPage:
    return ComplaintsPage(parent, principal=principal, state=state, open_pupil=open_pupil)
