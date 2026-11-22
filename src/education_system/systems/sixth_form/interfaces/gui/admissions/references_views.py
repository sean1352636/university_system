"""Feeder-school references: request → sent → chased → received."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox

from education_system.systems.sixth_form.domain.admissions import (
    admissions as adm,
    references as refs,
)
from education_system.systems.sixth_form.interfaces.gui.admissions import (
    _admissions_ui as ui,
)
from education_system.systems.sixth_form.interfaces.gui.admissions import (
    applicant_actions as act,
)

logger = logging.getLogger(__name__)

_REFEREE_FIELDS = [
    ("referee_name", "Referee name", "entry", None),
    ("referee_role", "Role (e.g. Head of Year 11)", "entry", None),
    ("referee_school", "School", "entry", None),
    ("referee_email", "Email", "entry", None),
    ("referee_phone", "Phone", "entry", None),
    ("due_date", "Due date (YYYY-MM-DD)", "entry", None),
    ("notes", "Notes", "text", None),
]


class ReferencesPanel:
    """Reference worklist; limited to one applicant when ``applicant_id``."""

    COLS = [("id", "#", 45), ("applicant", "Applicant", 85),
            ("name", "Name", 150), ("referee", "Referee", 150),
            ("school", "School", 140), ("status", "Status", 80),
            ("requested", "Requested", 85), ("sent", "Sent", 85),
            ("due", "Due", 85), ("chased", "Chased", 55),
            ("received", "Received", 85), ("dsl", "DSL", 40)]

    def __init__(self, parent: tk.Misc, applicant_id: str | None = None,
                 on_change=None) -> None:
        self.parent = parent
        self.aid = applicant_id
        self.on_change = on_change
        bar = ttk.Frame(parent)
        bar.pack(fill="x", padx=8, pady=(8, 2))
        ttk.Button(bar, text="Request reference…",
                   command=self._request).pack(side="left")
        if applicant_id:
            ttk.Button(bar, text="From referee on application",
                       command=self._adopt).pack(side="left", padx=4)
        ttk.Button(bar, text="Mark sent (letter)…",
                   command=self._sent).pack(side="left", padx=4)
        ttk.Button(bar, text="Chase (letter)…",
                   command=self._chase).pack(side="left")
        ttk.Button(bar, text="E-mail request / reminder…",
                   command=self._email).pack(side="left", padx=4)
        ttk.Button(bar, text="Record received…",
                   command=self._received).pack(side="left", padx=4)
        ttk.Button(bar, text="Declined",
                   command=self._declined).pack(side="left")
        ttk.Button(bar, text="Cancel request",
                   command=self._cancel).pack(side="left", padx=4)
        bar2 = ttk.Frame(parent)
        bar2.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Button(bar2, text="View…", command=self._view).pack(side="left")
        ttk.Button(bar2, text="Edit referee…",
                   command=self._edit).pack(side="left", padx=4)
        if not applicant_id:
            ttk.Button(bar2, text="Due a chase",
                       command=self._chase_list).pack(side="left", padx=4)
            ttk.Button(bar2, text="E-mail all due…",
                       command=self._email_all).pack(side="left")
            if act.can_area("safeguarding"):
                ttk.Button(bar2, text="DSL-flagged…",
                           command=self._dsl_flagged).pack(side="left",
                                                           padx=4)
        ttk.Label(bar2, text="Status:").pack(side="left", padx=(12, 2))
        self.f_status = ttk.Combobox(bar2, state="readonly", width=12,
                                     values=("",) + refs.STATUSES)
        self.f_status.pack(side="left")
        self.f_status.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        self.f_overdue = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar2, text="Overdue only", variable=self.f_overdue,
                        command=self.refresh).pack(side="left", padx=6)
        ttk.Button(bar2, text="Refresh", command=self.refresh).pack(
            side="right")
        for b in (*bar.winfo_children(), *bar2.winfo_children()):
            if isinstance(b, ttk.Button) and str(b.cget("text")) not in (
                    "View…", "Due a chase", "DSL-flagged…", "Refresh"):
                act.gate(b, act.can_admissions())
        self.info = tk.StringVar()
        ttk.Label(parent, textvariable=self.info, foreground="#555").pack(
            fill="x", padx=8)
        holder = ttk.Frame(parent)
        holder.pack(fill="both", expand=True, padx=8, pady=(2, 8))
        self.tree = ui.make_tree(holder, self.COLS, height=16)
        self.tree.tag_configure("overdue", background="#ffd6d6")
        self.tree.tag_configure("Received", background="#d8f4d8")
        self.tree.bind("<Double-1>", lambda _e: self._view())
        self.refresh()

    def refresh(self) -> None:
        ui.clear(self.tree)
        try:
            rows = refs.list_references(
                applicant_id=self.aid, status=self.f_status.get() or None,
                overdue_only=self.f_overdue.get())
        except Exception as e:  # noqa: BLE001
            logger.exception("References failed to load")
            self.info.set(f"Error: {e}")
            return
        names = {a.applicant_id: a.full_name for a in adm.list_applicants()}
        for r in rows:
            tag = "overdue" if r.is_overdue else r.status
            self.tree.insert("", "end", iid=str(r.reference_id), values=(
                r.reference_id, r.applicant_id,
                names.get(r.applicant_id, ""), r.referee_name,
                r.referee_school or "", r.status, r.requested_on,
                r.sent_on or "", r.effective_due or "", r.chase_count or "",
                r.received_on or "", "Yes" if r.contact_dsl else ""),
                tags=(tag,))
        s = refs.summary()
        self.info.set(" · ".join(f"{k} {v}" for k, v in s.items() if v)
                      or "No references yet.")

    def _changed(self) -> None:
        self.refresh()
        if self.on_change:
            self.on_change()

    def _rid(self) -> int | None:
        iid = ui.require_iid(self.tree, "References")
        return int(iid) if iid else None

    def _run(self, fn, *a, **kw):
        ok, out = act.attempt(self.parent, "References", fn, *a, **kw)
        if not ok:
            return None
        self._changed()
        return out

    def _request(self) -> None:
        aid = self.aid or ui.pick_applicant(self.parent,
                                            "Reference for which applicant?")
        if not aid:
            return
        a = adm.get_applicant(aid)
        initial = {"referee_school": a.previous_school if a else ""}
        if ui.ask_form(self.parent, f"Request reference — {aid}",
                       _REFEREE_FIELDS, initial,
                       on_submit=lambda v: refs.request_reference(
                           aid, requested_by=ui.current_username(), **v)):
            self._changed()

    def _adopt(self) -> None:
        self._run(refs.adopt_legacy_reference, self.aid)

    def _sent(self) -> None:
        rid = self._rid()
        if not rid:
            return
        subject, body = refs.render_request(rid)
        ui.show_text(self.parent, subject, f"Subject: {subject}\n\n{body}")
        if messagebox.askyesno("References", "Mark the request as sent today?",
                               parent=self.parent):
            self._run(refs.mark_sent, rid)

    def _chase(self) -> None:
        rid = self._rid()
        if not rid:
            return
        subject, body = refs.render_chase(rid)
        ui.show_text(self.parent, subject, f"Subject: {subject}\n\n{body}")
        if messagebox.askyesno("References", "Record this chase?",
                               parent=self.parent):
            self._run(refs.chase, rid)

    def _received(self) -> None:
        rid = self._rid()
        if not rid:
            return
        fields = [
            ("received_on", "Received on (blank = today)", "entry", None),
            ("attendance_pct", "Attendance %", "entry", None),
            ("predicted_gcses", "Predicted GCSEs (Maths 7, English 6, …)",
             "entry", None),
            ("behaviour", "Behaviour", "readonly", ("",) + refs.BEHAVIOUR_RATINGS),
            ("behaviour_comment", "Behaviour comment", "text", None),
            ("academic_comment", "Academic comment", "text", None),
            ("contact_dsl", "Referee asks us to contact the DSL "
                            "(flag only — no details here)", "check", None),
        ]
        if ui.ask_form(self.parent, "Reference received", fields,
                       on_submit=lambda v: refs.record_received(
                           rid, recorded_by=ui.current_username(), **v)):
            self._changed()

    def _declined(self) -> None:
        rid = self._rid()
        if rid:
            self._run(refs.decline, rid)

    def _cancel(self) -> None:
        rid = self._rid()
        if rid and messagebox.askyesno("References",
                                       "Cancel this reference request?",
                                       parent=self.parent):
            self._run(refs.cancel, rid)

    def _edit(self) -> None:
        rid = self._rid()
        if rid and edit_referee(self.parent, rid):
            self._changed()

    def _email(self) -> None:
        """E-mail the request (not yet sent) or a reminder through the
        outbox, recorded on the tracker."""
        rid = self._rid()
        if not rid:
            return
        from . import applicant_email
        applicant_email.email_reference(self.parent, rid,
                                        on_done=self._changed)

    def _email_all(self) -> None:
        from . import applicant_email
        applicant_email.chase_all(self.parent, on_done=self._changed)

    def _dsl_flagged(self) -> None:
        """Read-only: applicants whose referee asked for the DSL to be
        contacted (flag only — no details are held here)."""
        ok, ids = act.attempt(self.parent, "DSL-flagged",
                              refs.dsl_flagged_applicants)
        if not ok:
            return
        lines = [f"{len(ids)} applicant(s) whose referee asked admissions "
                 "to contact the DSL:", ""]
        for aid in ids:
            a = adm.get_applicant(aid)
            lines.append(f"{aid}  {a.full_name if a else '(removed)'}  "
                         f"{a.status if a else ''}  "
                         f"{(a.previous_school or '') if a else ''}")
        ui.show_text(self.parent, "DSL-flagged references", "\n".join(lines))

    def _view(self) -> None:
        rid = self._rid()
        r = refs.get_reference(rid) if rid else None
        if r is None:
            return
        lines = [
            f"Reference #{r.reference_id} for {r.applicant_id}",
            f"Referee: {r.referee_name} {('— ' + r.referee_role) if r.referee_role else ''}",
            f"School: {r.referee_school or '—'}",
            f"Contact: {r.referee_email or ''} {r.referee_phone or ''}",
            f"Status: {r.status}   requested {r.requested_on} by "
            f"{r.requested_by or '—'}",
            f"Sent: {r.sent_on or '—'}   due {r.effective_due or '—'}   "
            f"chased {r.chase_count}x (last {r.last_chased_on or '—'})",
            f"Received: {r.received_on or '—'}", "",
            f"Attendance: {r.attendance_pct if r.attendance_pct is not None else '—'}%",
            f"Predicted GCSEs: {r.predicted_gcses or '—'}",
            f"Behaviour: {r.behaviour or '—'}", r.behaviour_comment or "", "",
            f"Academic: {r.academic_comment or '—'}", "",
            ("*** Referee asked admissions to contact the DSL before "
             "enrolment (no details are held here). ***"
             if r.contact_dsl else ""),
            f"Notes: {r.notes or '—'}",
        ]
        ui.show_text(self.parent, f"Reference #{r.reference_id}",
                     "\n".join(lines))

    def _chase_list(self) -> None:
        rows = refs.chase_list()
        ui.show_text(self.parent, "References due a chase", "\n".join(
            f"#{r.reference_id}  {r.applicant_id}  {r.referee_name}  "
            f"due {r.effective_due}  chased {r.chase_count}x"
            for r in rows) or "Nothing to chase.")


def edit_referee(parent: tk.Misc, reference_id: int) -> bool:
    """Correct a referee's details or the due date. True when saved."""
    r = refs.get_reference(reference_id)
    if r is None:
        messagebox.showerror("Edit referee", f"No reference #{reference_id}",
                             parent=parent.winfo_toplevel())
        return False
    return ui.ask_form(parent, "Edit referee", _REFEREE_FIELDS, vars(r),
                       on_submit=lambda v: refs.update_referee(
                           reference_id, **v)) is not None


class ReferencesTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="References")
        self.panel = ReferencesPanel(self.frame)

    def refresh(self) -> None:
        self.panel.refresh()


def open_applicant_references(parent: tk.Misc, applicant_id: str,
                              on_change=None) -> None:
    a = adm.get_applicant(applicant_id)
    win = ui.new_window(parent, f"References — {applicant_id} "
                        f"{a.full_name if a else ''}",
                        geometry="1300x700", minsize=(1000, 600))
    ReferencesPanel(win, applicant_id=applicant_id, on_change=on_change)


def open_references_window(parent=None) -> None:
    win = ui.new_window(parent, "Feeder-school references")
    ReferencesPanel(win)
