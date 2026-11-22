"""Admissions CRM tabs: Conditions & Documents, and Postgraduate; plus the
supervisor's PGR Supervision Requests window.

The tabs are thin: every action calls ``admissions_checklist`` /
``admissions_postgraduate`` / ``admissions_sponsors``, which check the
admissions permission and write the casework audit trail. Loads and
actions run off the Tk thread (``tk_threads``) and report back on it.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

from education_system.platform.delivery.gui.tk_threads import start_thread, ui
from education_system.systems.university.domains.admissions.domain.services import (
    admissions_casework as casework,
)
from education_system.systems.university.domains.admissions.domain.services import (
    admissions_checklist as checklist,
)
from education_system.systems.university.domains.admissions.domain.services import (
    admissions_postgraduate as postgraduate,
)
from education_system.systems.university.domains.admissions.domain.services import (
    admissions_sponsors as sponsors,
)
from education_system.systems.university.domains.admissions.domain.services.admissions_policies import (
    RightToStudyPolicy,
)
from education_system.systems.university.infrastructure.i18n import get_text as _t

logger = logging.getLogger(__name__)

_K = "gui.admissions.casework"


def _tr(key: str, default: str, **kw) -> str:
    return _t(f"{_K}.{key}", default=default, **kw)


# ── Small form dialog ──────────────────────────────────────────────

class _FormDialog:
    """A modal form parented to ``parent``. ``fields`` are tuples of
    ``(key, label, kind, options)`` with kind entry/text/combo/file/check."""

    def __init__(self, parent, title: str, fields, *, ok_text: str = "Save"):
        self.result: dict | None = None
        self.top = tk.Toplevel(parent)
        self.top.title(title)
        self.top.transient(parent.winfo_toplevel())
        body = ttk.Frame(self.top, padding=12)
        body.pack(fill=tk.BOTH, expand=True)
        self._getters: dict[str, Callable[[], Any]] = {}
        for row, (key, label, kind, options) in enumerate(fields):
            ttk.Label(body, text=label).grid(row=row, column=0, sticky="nw", padx=4, pady=4)
            self._getters[key] = self._field(body, row, kind, options)
        body.columnconfigure(1, weight=1)
        buttons = ttk.Frame(self.top, padding=(12, 0, 12, 12))
        buttons.pack(fill=tk.X)
        ttk.Button(buttons, text=ok_text, command=self._ok).pack(side=tk.RIGHT, padx=4)
        ttk.Button(buttons, text=_tr("cancel", "Cancel"),
                   command=self.top.destroy).pack(side=tk.RIGHT)
        self.top.grab_set()
        parent.wait_window(self.top)

    def _field(self, body, row, kind, options):
        if kind == "text":
            widget = tk.Text(body, width=50, height=5, wrap=tk.WORD)
            widget.grid(row=row, column=1, sticky="ew", padx=4, pady=4)
            return lambda: widget.get("1.0", tk.END).strip()
        if kind == "check":
            var = tk.BooleanVar(value=bool(options))
            ttk.Checkbutton(body, variable=var).grid(row=row, column=1, sticky="w")
            return var.get
        var = tk.StringVar(value="" if kind != "combo" or not options else options[0])
        if kind == "combo":
            ttk.Combobox(body, textvariable=var, values=list(options), state="readonly",
                         width=40).grid(row=row, column=1, sticky="ew", padx=4, pady=4)
            return lambda: var.get().strip()
        ttk.Entry(body, textvariable=var, width=50).grid(row=row, column=1, sticky="ew",
                                                          padx=4, pady=4)
        if kind == "file":
            ttk.Button(body, text=_tr("browse", "Browse…"), command=lambda: var.set(
                filedialog.askopenfilename(parent=self.top) or var.get())
            ).grid(row=row, column=2, padx=4)
        elif options:
            var.set(str(options))
        return lambda: var.get().strip()

    def _ok(self):
        self.result = {key: get() for key, get in self._getters.items()}
        self.top.destroy()


def ask_form(parent, title, fields, **kw) -> dict | None:
    return _FormDialog(parent, title, fields, **kw).result


def _tree(parent, columns, headings, height=6) -> ttk.Treeview:
    frame = ttk.Frame(parent)
    frame.pack(fill=tk.BOTH, expand=True)
    tree = ttk.Treeview(frame, columns=columns, show="headings", height=height,
                        selectmode="browse")
    for col, text in zip(columns, headings):
        tree.heading(col, text=text)
        tree.column(col, width=90 if col.endswith("id") else 140, stretch=True)
    scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scroll.pack(side=tk.RIGHT, fill=tk.Y)
    return tree


def _fill(tree: ttk.Treeview, rows, key: str, values: Callable[[dict], tuple]) -> None:
    tree.delete(*tree.get_children())
    for row in rows:
        tree.insert("", tk.END, iid=str(row[key]), values=values(row))


def _selected(tree: ttk.Treeview) -> int | None:
    sel = tree.selection()
    return int(sel[0]) if sel else None


def open_document(parent, document_id) -> None:
    path = casework.document_path(document_id) if document_id else None
    if path is None:
        messagebox.showwarning(_tr("title", "Admissions"),
                               _tr("file_missing", "The file is not in storage."), parent=parent)
        return
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # noqa: S606 - opening the user's own document
        else:
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.Popen([opener, str(path)])  # noqa: S603
    except Exception:
        messagebox.showinfo(_tr("title", "Admissions"), str(path), parent=parent)


# ── Shared base: application picker + threaded actions ────────────

class _CaseworkTab(ttk.Frame):
    """Left: the application list. Right: built by the subclass."""

    def __init__(self, parent, auth):
        super().__init__(parent, padding=8)
        self.auth = auth
        self.application_id: int | None = None
        self.data: dict | None = None
        left = ttk.Frame(self)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        search = ttk.Frame(left)
        search.pack(fill=tk.X)
        self.search_var = tk.StringVar()
        entry = ttk.Entry(search, textvariable=self.search_var, width=24)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        entry.bind("<Return>", lambda _e: self.load_applications())
        ttk.Button(search, text=_tr("search", "Search"),
                   command=self.load_applications).pack(side=tk.LEFT, padx=4)
        self.app_tree = _tree(left, ("application_id", "applicant", "type", "status"),
                              (_tr("col.id", "ID"), _tr("col.applicant", "Applicant"),
                               _tr("col.type", "Type"), _tr("col.status", "Status")),
                              height=24)
        self.app_tree.bind("<<TreeviewSelect>>", self._on_pick)
        self.right = ttk.Frame(self)
        self.right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.banner = ttk.Label(self.right, text=_tr("pick", "Choose an application."),
                                font=("Arial", 11, "bold"), wraplength=820, justify=tk.LEFT)
        self.banner.pack(fill=tk.X, pady=(0, 6))
        if not casework.can_manage(auth):
            self.banner.config(text=_tr("no_permission",
                                        "Admissions staff only (approve_applications)."))
            return
        self.build()
        self.load_applications()

    def build(self) -> None:  # pragma: no cover - subclasses
        raise NotImplementedError

    def fetch(self, application_id: int) -> dict:  # pragma: no cover
        raise NotImplementedError

    def render(self, data: dict) -> None:  # pragma: no cover
        raise NotImplementedError

    def load_applications(self) -> None:
        term = self.search_var.get()

        def work():
            try:
                rows = checklist.applications(search=term)
            except Exception as exc:
                logger.exception("Loading applications failed")
                ui(self, self._error, exc)
                return
            ui(self, _fill, self.app_tree, rows, "application_id", lambda r: (
                r["application_id"],
                f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip(),
                r.get("application_type") or "", r.get("status") or ""))
        start_thread(self, work)

    def _on_pick(self, _event=None) -> None:
        picked = _selected(self.app_tree)
        if picked is not None:
            self.application_id = picked
            self.refresh()

    def refresh(self) -> None:
        if self.application_id is None:
            return
        aid = self.application_id

        def work():
            try:
                data = self.fetch(aid)
            except Exception as exc:
                logger.exception("Loading application %s failed", aid)
                ui(self, self._error, exc)
                return
            ui(self, self._render, data)
        start_thread(self, work)

    def _render(self, data: dict) -> None:
        self.data = data
        self.render(data)

    def _error(self, exc) -> None:
        messagebox.showerror(_tr("title", "Admissions"), str(exc), parent=self)

    def act(self, fn: Callable, *args, done: str = "", **kwargs) -> None:
        """Run a domain action off the Tk thread, then report and refresh."""
        def work():
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:
                ui(self, self._error, exc)
                return
            ui(self, self._done, result, done)
        start_thread(self, work)

    def _done(self, result, message: str) -> None:
        if isinstance(result, dict) and result.get("message"):
            message = result["message"]
        elif message and isinstance(result, str):
            message = message.format(result=result)
        if message:
            messagebox.showinfo(_tr("title", "Admissions"), message, parent=self)
        self.refresh()
        self.load_applications()

    def need_selection(self, tree: ttk.Treeview) -> int | None:
        picked = _selected(tree)
        if picked is None:
            messagebox.showwarning(_tr("title", "Admissions"),
                                   _tr("select_row", "Select a row first."), parent=self)
        return picked

    def toolbar(self, parent, buttons) -> ttk.Frame:
        bar = ttk.Frame(parent)
        bar.pack(fill=tk.X, pady=(0, 4))
        for text, command in buttons:
            ttk.Button(bar, text=text, command=command).pack(side=tk.LEFT, padx=2)
        return bar


# ── Conditions & Documents ─────────────────────────────────────────

class ConditionsDocumentsTab(_CaseworkTab):
    """Conditions and required documents, readiness, and Convert to Student."""

    def build(self) -> None:
        cond = ttk.LabelFrame(self.right, text=_tr("conditions", "Offer conditions"), padding=6)
        cond.pack(fill=tk.BOTH, expand=True)
        self.toolbar(cond, (
            (_tr("add_condition", "Add condition"), self._add_condition),
            (_tr("satisfy", "Mark satisfied…"), self._satisfy),
            (_tr("waive", "Waive…"), self._waive),
        ))
        self.cond_tree = _tree(cond, ("condition_id", "type", "description", "due", "status",
                                      "evidence", "by"),
                               ("ID", _tr("col.type", "Type"), _tr("col.description", "Description"),
                                _tr("col.due", "Due"), _tr("col.status", "Status"),
                                _tr("col.evidence", "Evidence / reason"), _tr("col.by", "By")))
        docs = ttk.LabelFrame(self.right, text=_tr("documents", "Required documents"), padding=6)
        docs.pack(fill=tk.BOTH, expand=True, pady=6)
        self.toolbar(docs, (
            (_tr("add_requirement", "Add required document"), self._add_requirement),
            (_tr("verify", "Verify document…"), self._verify),
            (_tr("open_file", "Open evidence"), self._open_evidence),
        ))
        self.req_tree = _tree(docs, ("requirement_id", "type", "description", "required",
                                     "status", "file", "verified_by"),
                              ("ID", _tr("col.type", "Type"), _tr("col.description", "Description"),
                               _tr("col.required", "Required"), _tr("col.status", "Status"),
                               _tr("col.file", "Evidence file"), _tr("col.by", "Verified by")))
        gates = ttk.LabelFrame(self.right, text=_tr("gates", "Enrolment gates"), padding=6)
        gates.pack(fill=tk.X)
        self.gate_label = ttk.Label(gates, text="", justify=tk.LEFT, wraplength=820)
        self.gate_label.pack(fill=tk.X)
        bar = self.toolbar(gates, (
            (_tr("right_to_study", "Record right to study…"), self._right_to_study),
            (_tr("deposit", "Record deposit…"), self._deposit),
        ))
        self.status_var = tk.StringVar()
        self.status_combo = ttk.Combobox(bar, textvariable=self.status_var, state="readonly",
                                         width=22)
        self.status_combo.pack(side=tk.LEFT, padx=(12, 2))
        ttk.Button(bar, text=_tr("advance", "Move status"),
                   command=self._advance).pack(side=tk.LEFT, padx=2)
        self.convert_btn = ttk.Button(bar, text=_tr("convert", "Convert to Student"),
                                      command=self._convert, state=tk.DISABLED)
        self.convert_btn.pack(side=tk.RIGHT, padx=2)
        hist = ttk.LabelFrame(self.right, text=_tr("history", "Casework history"), padding=6)
        hist.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        self.audit_tree = _tree(hist, ("audit_id", "when", "actor", "action", "detail"),
                                ("#", _tr("col.when", "When"), _tr("col.by", "By"),
                                 _tr("col.action", "Action"), _tr("col.detail", "Detail")),
                                height=4)

    def fetch(self, application_id: int) -> dict:
        return checklist.checklist(application_id)

    def render(self, data: dict) -> None:
        app = data["application"]
        name = f"{app.get('first_name') or ''} {app.get('last_name') or ''}".strip()
        if data["converted_student_id"]:
            state = _tr("converted", "Converted — student {sid}", sid=data["converted_student_id"])
        elif data["ready"]:
            state = _tr("ready", "READY TO ENROL")
        else:
            state = _tr("not_ready", "Not ready: ") + "; ".join(data["issues"])
        self.banner.config(text=f"#{app['application_id']} {name} — "
                                f"{app.get('program_applied') or ''} "
                                f"[{app.get('application_type')}, {app.get('status')}]\n{state}")
        _fill(self.cond_tree, data["conditions"], "condition_id", lambda c: (
            c["condition_id"], c["condition_type"], c["description"], c.get("due_date") or "",
            c["status"], c.get("waiver_reason") or c.get("evidence_reference") or "",
            c.get("decided_by") or ""))
        _fill(self.req_tree, data["requirements"], "requirement_id", lambda r: (
            r["requirement_id"], r["requirement_type"], r["description"],
            "yes" if r["required"] else "no", r["status"],
            r.get("original_filename") or r.get("document_name") or "",
            r.get("verified_by") or ""))
        _fill(self.audit_tree, data["audit"], "audit_id", lambda a: (
            a["audit_id"], (a["created_at"] or "")[:16], a["actor"], a["action"], a["detail"]))
        self.gate_label.config(text=self._gate_text(data))
        self.status_combo.config(values=data["next_statuses"])
        self.status_var.set(data["next_statuses"][0] if data["next_statuses"] else "")
        self.convert_btn.config(state=tk.NORMAL if data["ready"] else tk.DISABLED)

    @staticmethod
    def _gate_text(data: dict) -> str:
        d = data["decisions"]
        rts = d.get("right_to_study")
        parts = [_tr("rts_line", "Right to study: ") +
                 (f"{rts['status']} ({rts['route']}, {rts['evidence_reference']})" if rts
                  else _tr("not_recorded", "not recorded"))]
        if data["has_deposit_condition"]:
            dep = d.get("deposit")
            parts.append(_tr("deposit_line", "Deposit: ") +
                         (f"{dep['status']} ({dep['received_amount']}/{dep['required_amount']} "
                          f"{dep['currency']})" if dep else _tr("not_recorded", "not recorded")))
        if data["has_sponsorship_condition"] or data["sponsor"]:
            sp = data["sponsor"]
            parts.append(_tr("sponsor_line", "Sponsor: ") +
                         (f"{sp['organisation']} — decision {sp['sponsorship_decision'] or 'none'}"
                          if sp else _tr("sponsor_none", "none recorded (Postgraduate tab → Sponsor)")))
        return "   |   ".join(parts)

    @property
    def _aid(self) -> int | None:
        if self.application_id is None:
            messagebox.showwarning(_tr("title", "Admissions"),
                                   _tr("pick", "Choose an application."), parent=self)
        return self.application_id

    def _add_condition(self) -> None:
        if self._aid is None:
            return
        form = ask_form(self, _tr("add_condition", "Add condition"), (
            ("type", _tr("col.type", "Type"), "combo", checklist.CONDITION_TYPES),
            ("description", _tr("col.description", "Description"), "entry", None),
            ("due", _tr("col.due", "Due date (YYYY-MM-DD)"), "entry", None),
            ("amount", _tr("amount", "Amount (deposit)"), "entry", None),
            ("sponsor", _tr("sponsor_name", "Sponsor name (sponsorship)"), "entry", None),
        ))
        if form:
            amount = float(form["amount"]) if form["amount"] else None
            self.act(checklist.add_condition, self.auth, self.application_id, form["type"],
                     form["description"], due_date=form["due"], amount=amount,
                     currency="GBP" if amount else "", sponsor_name=form["sponsor"])

    def _satisfy(self) -> None:
        cid = self.need_selection(self.cond_tree)
        if cid is None:
            return
        form = ask_form(self, _tr("satisfy", "Mark satisfied"), (
            ("note", _tr("evidence_note", "Evidence (what showed it was met)"), "text", None),))
        if form:
            self.act(checklist.satisfy_condition, self.auth, cid, form["note"])

    def _waive(self) -> None:
        cid = self.need_selection(self.cond_tree)
        if cid is None:
            return
        form = ask_form(self, _tr("waive", "Waive condition"), (
            ("reason", _tr("waive_reason", "Reason for waiving"), "text", None),))
        if form:
            self.act(checklist.waive_condition, self.auth, cid, form["reason"])

    def _add_requirement(self) -> None:
        if self._aid is None:
            return
        form = ask_form(self, _tr("add_requirement", "Add required document"), (
            ("type", _tr("col.type", "Type"), "combo", checklist.REQUIREMENT_TYPES),
            ("description", _tr("what_needed", "What is needed"), "entry", None),
            ("due", _tr("col.due", "Due date (YYYY-MM-DD)"), "entry", None),
            ("required", _tr("col.required", "Required for enrolment"), "check", True),
        ))
        if form:
            self.act(checklist.add_requirement, self.auth, self.application_id, form["type"],
                     form["description"], due_date=form["due"], required=form["required"])

    def _verify(self) -> None:
        rid = self.need_selection(self.req_tree)
        if rid is None or not self.data:
            return
        on_file = ["—"] + [f"{d['document_id']}: {d.get('original_filename') or d.get('document_name')}"
                           for d in self.data["documents"]]
        form = ask_form(self, _tr("verify", "Verify document"), (
            ("file", _tr("upload", "Upload file"), "file", None),
            ("existing", _tr("on_file", "…or a document on file"), "combo", on_file),
            ("notes", _tr("verify_note", "Verification note"), "text", None),
        ))
        if form:
            existing = form["existing"].split(":", 1)[0] if form["existing"] != "—" else ""
            self.act(checklist.verify_document, self.auth, rid,
                     file_path=form["file"] or None,
                     document_id=int(existing) if existing and not form["file"] else None,
                     notes=form["notes"])

    def _open_evidence(self) -> None:
        rid = self.need_selection(self.req_tree)
        if rid is None or not self.data:
            return
        row = next((r for r in self.data["requirements"] if r["requirement_id"] == rid), None)
        open_document(self, row and row.get("evidence_document_id"))

    def _right_to_study(self) -> None:
        if self._aid is None:
            return
        form = ask_form(self, _tr("right_to_study", "Record right to study"), (
            ("route", _tr("route", "Route"), "combo", sorted(RightToStudyPolicy.ALLOWED_ROUTES)),
            ("evidence", _tr("evidence_ref", "Evidence reference (passport, CAS, share code)"),
             "entry", None),
            ("until", _tr("valid_until", "Valid until (YYYY-MM-DD, optional)"), "entry", None),
        ))
        if form:
            self.act(checklist.record_right_to_study, self.auth, self.application_id,
                     form["route"], form["evidence"], valid_until=form["until"] or None,
                     done=_tr("rts_done", "Right to study: {result}"))

    def _deposit(self) -> None:
        if self._aid is None:
            return
        form = ask_form(self, _tr("deposit", "Record deposit"), (
            ("required", _tr("required_amount", "Deposit required"), "entry", None),
            ("received", _tr("received_amount", "Amount received"), "entry", None),
            ("ref", _tr("payment_ref", "Payment reference"), "entry", None),
        ))
        if form:
            try:
                required, received = float(form["required"]), float(form["received"])
            except ValueError:
                self._error(_tr("number", "Amounts must be numbers"))
                return
            self.act(checklist.record_deposit, self.auth, self.application_id,
                     required_amount=required, received_amount=received,
                     payment_reference=form["ref"],
                     done=_tr("deposit_done", "Deposit decision: {result}"))

    def _advance(self) -> None:
        if self._aid is None or not self.status_var.get():
            return
        self.act(checklist.advance_status, self.auth, self.application_id,
                 self.status_var.get(), "Moved in Conditions & Documents")

    def _convert(self) -> None:
        if self._aid is None:
            return
        if not messagebox.askyesno(_tr("convert", "Convert to Student"),
                                   _tr("convert_confirm",
                                       "Create the student record and registration now?"),
                                   parent=self):
            return
        self.act(checklist.convert, self.auth, self.application_id,
                 done=_tr("converted_done", "Converted to student {result}"))


# ── Postgraduate ───────────────────────────────────────────────────

class PostgraduateTab(_CaseworkTab):
    """References; research proposal, supervisors and interview; sponsor."""

    def build(self) -> None:
        refs = ttk.LabelFrame(self.right, text=_tr("referees", "Referees (two required)"),
                              padding=6)
        refs.pack(fill=tk.BOTH, expand=True)
        self.toolbar(refs, (
            (_tr("add_referee", "Add referee"), self._add_referee),
            (_tr("send_request", "Send reference request"), self._request),
            (_tr("record_reference", "Record reference received…"), self._record),
            (_tr("withdraw", "Withdraw…"), self._withdraw_referee),
            (_tr("open_file", "Open reference"), self._open_reference),
        ))
        self.ref_tree = _tree(refs, ("referee_id", "name", "email", "relationship", "status",
                                     "requested", "received"),
                              ("ID", _tr("col.name", "Name"), _tr("col.email", "E-mail"),
                               _tr("col.relationship", "Relationship"), _tr("col.status", "Status"),
                               _tr("col.requested", "Requested"), _tr("col.received", "Received")),
                              height=3)
        self.research = ttk.LabelFrame(self.right, text=_tr("research", "Research degree"),
                                       padding=6)
        self.research.pack(fill=tk.BOTH, expand=True, pady=6)
        self.proposal_label = ttk.Label(self.research, text="")
        self.proposal_label.pack(fill=tk.X)
        self.toolbar(self.research, (
            (_tr("upload_proposal", "Upload research proposal…"), self._proposal),
            (_tr("open_proposal", "Open proposal"), self._open_proposal),
            (_tr("propose_supervisor", "Propose supervisor…"), self._nominate),
            (_tr("withdraw_supervisor", "Withdraw supervisor…"), self._withdraw_nomination),
        ))
        self.sup_tree = _tree(self.research, ("nomination_id", "supervisor", "role", "status",
                                              "comment", "decided"),
                              ("ID", _tr("col.supervisor", "Supervisor"), _tr("col.role", "Role"),
                               _tr("col.status", "Status"), _tr("col.comment", "Comment"),
                               _tr("col.decided", "Decided")), height=3)
        ivs = ttk.LabelFrame(self.right, text=_tr("interviews", "Interview"), padding=6)
        ivs.pack(fill=tk.BOTH, expand=True)
        self.toolbar(ivs, (
            (_tr("schedule_interview", "Schedule interview…"), self._interview),
            (_tr("record_outcome", "Record outcome…"), self._outcome),
        ))
        self.iv_tree = _tree(ivs, ("interview_id", "when", "panel", "format", "status",
                                   "outcome", "notes"),
                             ("ID", _tr("col.when", "When"), _tr("col.panel", "Panel"),
                              _tr("col.format", "Format"), _tr("col.status", "Status"),
                              _tr("col.outcome", "Outcome"), _tr("col.notes", "Notes")), height=3)
        spon = ttk.LabelFrame(self.right, text=_tr("sponsor", "Third-party sponsor"), padding=6)
        spon.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        self.toolbar(spon, (
            (_tr("record_sponsor", "Record sponsor / letter…"), self._sponsor),
            (_tr("withdraw", "Withdraw…"), self._withdraw_sponsor),
            (_tr("open_letter", "Open letter"), self._open_letter),
        ))
        self.sp_tree = _tree(spon, ("sponsor_record_id", "organisation", "reference", "covers",
                                    "amount", "status", "by"),
                             ("ID", _tr("col.organisation", "Organisation"),
                              _tr("col.reference", "Reference"), _tr("col.covers", "Covers"),
                              _tr("col.amount", "Amount"), _tr("col.status", "Status"),
                              _tr("col.by", "Recorded by")), height=2)

    def fetch(self, application_id: int) -> dict:
        data = postgraduate.summary(application_id)
        data["sponsors"] = sponsors.sponsors_for_application(application_id)
        data["application_id"] = application_id
        return data

    def render(self, data: dict) -> None:
        if not data["postgraduate"]:
            head = _tr("not_pg", "Not a postgraduate application ({kind}). Only the sponsor "
                                 "section applies.", kind=data["application_type"])
        elif data["issues"]:
            head = _tr("pg_outstanding", "Outstanding: ") + "; ".join(data["issues"])
        else:
            head = _tr("pg_complete", "All postgraduate requirements are complete.")
        self.banner.config(text=f"#{data['application_id']} [{data['application_type']}]\n{head}")
        _fill(self.ref_tree, data["referees"], "referee_id", lambda r: (
            r["referee_id"], r["name"], r["email"], r["relationship"], r["status"],
            (r.get("requested_at") or "")[:10], (r.get("received_at") or "")[:10]))
        current = [p for p in data["proposals"] if p["is_current"]]
        self.proposal_label.config(text=_tr("proposal", "Proposal: ") + (
            current[0]["title"] if current else _tr("none", "none uploaded"))
            if data["research"] else _tr("taught", "Taught programme — no proposal or supervisors."))
        _fill(self.sup_tree, data["nominations"], "nomination_id", lambda n: (
            n["nomination_id"], n["supervisor_username"], n["role"], n["status"],
            n.get("comment") or "", (n.get("decided_at") or "")[:10]))
        _fill(self.iv_tree, data["interviews"], "interview_id", lambda i: (
            i["interview_id"], (i["scheduled_at"] or "")[:16], i.get("panel") or "",
            i.get("format") or "", i["status"], i.get("outcome") or "", i.get("notes") or ""))
        _fill(self.sp_tree, data["sponsors"], "sponsor_record_id", lambda s: (
            s["sponsor_record_id"], s["organisation"], s.get("sponsor_reference") or "",
            s["covers"], f"{s['amount'] or ''} {s['currency']}", s["status"], s["recorded_by"]))

    def _need_pg(self, research: bool = False) -> bool:
        if not self.data:
            messagebox.showwarning(_tr("title", "Admissions"), _tr("pick", "Choose an application."),
                                   parent=self)
            return False
        ok = self.data["research"] if research else self.data["postgraduate"]
        if not ok:
            messagebox.showwarning(_tr("title", "Admissions"),
                                   _tr("need_research", "Only for research (PGR) applications.")
                                   if research else _tr("need_pg", "Only for postgraduate "
                                                                   "applications."), parent=self)
        return ok

    def _add_referee(self) -> None:
        if not self._need_pg():
            return
        form = ask_form(self, _tr("add_referee", "Add referee"), (
            ("name", _tr("col.name", "Name"), "entry", None),
            ("email", _tr("col.email", "E-mail"), "entry", None),
            ("relationship", _tr("col.relationship", "Relationship"), "combo",
             postgraduate.RELATIONSHIPS),
        ))
        if form:
            self.act(postgraduate.add_referee, self.auth, self.application_id, form["name"],
                     form["email"], form["relationship"])

    def _request(self) -> None:
        rid = self.need_selection(self.ref_tree)
        if rid is not None:
            self.act(postgraduate.request_reference, self.auth, rid)

    def _record(self) -> None:
        rid = self.need_selection(self.ref_tree)
        if rid is None:
            return
        form = ask_form(self, _tr("record_reference", "Record reference received"), (
            ("file", _tr("reference_file", "Reference file"), "file", None),
            ("text", _tr("reference_text", "Text / summary (optional)"), "text", None),
        ))
        if form:
            self.act(postgraduate.record_reference, self.auth, rid, text=form["text"],
                     file_path=form["file"] or None)

    def _withdraw_referee(self) -> None:
        rid = self.need_selection(self.ref_tree)
        form = rid is not None and ask_form(self, _tr("withdraw", "Withdraw"), (
            ("reason", _tr("reason", "Reason"), "entry", None),))
        if form:
            self.act(postgraduate.withdraw_referee, self.auth, rid, form["reason"])

    def _open_reference(self) -> None:
        rid = self.need_selection(self.ref_tree)
        row = next((r for r in (self.data or {}).get("referees", [])
                    if r["referee_id"] == rid), None)
        if row is not None:
            open_document(self, row.get("document_id"))

    def _proposal(self) -> None:
        if not self._need_pg(research=True):
            return
        form = ask_form(self, _tr("upload_proposal", "Upload research proposal"), (
            ("title", _tr("proposal_title", "Title"), "entry", None),
            ("summary", _tr("proposal_summary", "Summary"), "text", None),
            ("file", _tr("proposal_file", "Proposal document"), "file", None),
        ))
        if form:
            self.act(postgraduate.add_proposal, self.auth, self.application_id, form["title"],
                     summary=form["summary"], file_path=form["file"] or None)

    def _open_proposal(self) -> None:
        current = [p for p in (self.data or {}).get("proposals", []) if p["is_current"]]
        open_document(self, current[0]["document_id"] if current else None)

    def _nominate(self) -> None:
        if not self._need_pg(research=True):
            return
        staff = postgraduate.staff_directory()
        if not staff:
            self._error(_tr("no_staff", "No staff accounts were found."))
            return
        choices = [f"{s['username']} — {s['first_name']} {s['last_name']} ({s['role']})"
                   for s in staff]
        form = ask_form(self, _tr("propose_supervisor", "Propose supervisor"), (
            ("who", _tr("col.supervisor", "Supervisor"), "combo", choices),
            ("role", _tr("col.role", "Role"), "combo", postgraduate.SUPERVISOR_ROLES),
        ))
        if form and form["who"]:
            self.act(postgraduate.nominate_supervisor, self.auth, self.application_id,
                     form["who"].split(" — ", 1)[0], form["role"],
                     done=_tr("nominated", "Proposed. The supervisor answers from "
                                           "'PGR Supervision Requests' in their portal."))

    def _withdraw_nomination(self) -> None:
        nid = self.need_selection(self.sup_tree)
        form = nid is not None and ask_form(self, _tr("withdraw_supervisor", "Withdraw supervisor"),
                                            (("reason", _tr("reason", "Reason"), "entry", None),))
        if form:
            self.act(postgraduate.withdraw_nomination, self.auth, nid, form["reason"])

    def _interview(self) -> None:
        if not self._need_pg():
            return
        form = ask_form(self, _tr("schedule_interview", "Schedule interview"), (
            ("when", _tr("when", "Date and time (YYYY-MM-DD HH:MM)"), "entry", None),
            ("panel", _tr("col.panel", "Panel members"), "entry", None),
            ("format", _tr("col.format", "Format"), "combo", ("online", "in person", "telephone")),
            ("location", _tr("location", "Location or link"), "entry", None),
        ))
        if form:
            self.act(postgraduate.schedule_interview, self.auth, self.application_id,
                     form["when"], panel=form["panel"], format=form["format"],
                     location=form["location"])

    def _outcome(self) -> None:
        iid = self.need_selection(self.iv_tree)
        form = iid is not None and ask_form(self, _tr("record_outcome", "Record outcome"), (
            ("outcome", _tr("col.outcome", "Outcome"), "combo", postgraduate.INTERVIEW_OUTCOMES),
            ("notes", _tr("col.notes", "Notes"), "text", None),
        ))
        if form:
            self.act(postgraduate.record_interview_outcome, self.auth, iid, form["outcome"],
                     form["notes"])

    def _sponsor(self) -> None:
        if not self.data:
            return
        form = ask_form(self, _tr("record_sponsor", "Record sponsor"), (
            ("organisation", _tr("col.organisation", "Organisation"), "entry", None),
            ("contact", _tr("contact_name", "Contact name"), "entry", None),
            ("email", _tr("col.email", "Contact e-mail"), "entry", None),
            ("reference", _tr("col.reference", "Sponsor's reference / PO"), "entry", None),
            ("covers", _tr("col.covers", "Covers"), "combo", sponsors.COVERS),
            ("amount", _tr("col.amount", "Amount (optional)"), "entry", None),
            ("until", _tr("valid_until", "Valid until (YYYY-MM-DD)"), "entry", None),
            ("letter", _tr("letter", "Sponsor letter"), "file", None),
            ("approve", _tr("approve_sponsorship", "Approve as sponsorship evidence"),
             "check", False),
        ))
        if form:
            try:
                amount = float(form["amount"]) if form["amount"] else None
            except ValueError:
                self._error(_tr("number", "Amounts must be numbers"))
                return
            self.act(sponsors.record_sponsor, self.auth, self.application_id,
                     form["organisation"], contact_name=form["contact"],
                     contact_email=form["email"], sponsor_reference=form["reference"],
                     covers=form["covers"], amount=amount, valid_until=form["until"],
                     letter_path=form["letter"] or None, approve_sponsorship=form["approve"])

    def _withdraw_sponsor(self) -> None:
        sid = self.need_selection(self.sp_tree)
        form = sid is not None and ask_form(self, _tr("withdraw", "Withdraw sponsor"), (
            ("reason", _tr("reason", "Reason"), "entry", None),))
        if form:
            self.act(sponsors.withdraw_sponsor, self.auth, sid, form["reason"])

    def _open_letter(self) -> None:
        sid = self.need_selection(self.sp_tree)
        row = next((s for s in (self.data or {}).get("sponsors", [])
                    if s["sponsor_record_id"] == sid), None)
        if row is not None:
            open_document(self, row.get("letter_document_id"))


# ── Supervisor's window ───────────────────────────────────────────

class SupervisionRequestsWindow:
    """Requests to supervise a research applicant, for the signed-in staff member."""

    def __init__(self, root, auth):
        from education_system.platform.delivery.gui import window_sizing
        window_sizing.install()
        self.auth = auth
        self.window = tk.Toplevel(root)
        self.window.title(_tr("sup_title", "PGR Supervision Requests"))
        self.window.geometry("1400x900")
        self.window.minsize(1200, 800)
        frame = ttk.Frame(self.window, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        bar = ttk.Frame(frame)
        bar.pack(fill=tk.X, pady=(0, 6))
        for text, command in ((_tr("accept", "Accept…"), lambda: self._decide(True)),
                              (_tr("decline", "Decline…"), lambda: self._decide(False)),
                              (_tr("open_proposal", "Open proposal"), self._open),
                              (_tr("refresh", "Refresh"), self.load)):
            ttk.Button(bar, text=text, command=command).pack(side=tk.LEFT, padx=2)
        self.empty = ttk.Label(frame, text="")
        self.empty.pack(fill=tk.X)
        self.tree = _tree(frame, ("nomination_id", "applicant", "programme", "year", "role",
                                  "status", "proposal", "comment"),
                          ("ID", _tr("col.applicant", "Applicant"),
                           _tr("col.programme", "Programme"), _tr("col.year", "Year"),
                           _tr("col.role", "Role"), _tr("col.status", "Status"),
                           _tr("col.proposal", "Proposal"), _tr("col.comment", "Comment")),
                          height=24)
        self.rows: list[dict] = []
        self.load()

    def load(self) -> None:
        def work():
            try:
                rows = postgraduate.supervision_requests(self.auth)
            except Exception as exc:
                ui(self.window, messagebox.showerror, "PGR", str(exc), parent=self.window)
                return
            ui(self.window, self._render, rows)
        start_thread(self.window, work)

    def _render(self, rows) -> None:
        self.rows = rows
        self.empty.config(text="" if rows else _tr("sup_empty",
                                                  "No supervision requests addressed to you."))
        _fill(self.tree, rows, "nomination_id", lambda r: (
            r["nomination_id"], f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip(),
            r.get("program_applied") or "", r.get("academic_year") or "", r["role"],
            r["status"], r.get("proposal_title") or "", r.get("comment") or ""))

    def _decide(self, accept: bool) -> None:
        nid = _selected(self.tree)
        if nid is None:
            return
        form = ask_form(self.window, _tr("accept", "Accept") if accept else _tr("decline", "Decline"),
                        (("comment", _tr("col.comment", "Comment") +
                          ("" if accept else _tr("required", " (required)")), "text", None),))
        if not form:
            return
        try:
            status = postgraduate.decide_supervision(self.auth, nid, accept, form["comment"])
        except Exception as exc:
            messagebox.showerror("PGR", str(exc), parent=self.window)
            return
        messagebox.showinfo("PGR", _tr("decided", "Request {status}.", status=status),
                            parent=self.window)
        self.load()

    def _open(self) -> None:
        nid = _selected(self.tree)
        row = next((r for r in self.rows if r["nomination_id"] == nid), None)
        if row is not None:
            open_document(self.window, row.get("proposal_document_id"))


def open_supervision_requests(root, auth) -> SupervisionRequestsWindow:
    return SupervisionRequestsWindow(root, auth)


__all__ = ["ConditionsDocumentsTab", "PostgraduateTab", "SupervisionRequestsWindow",
           "ask_form", "open_supervision_requests"]
