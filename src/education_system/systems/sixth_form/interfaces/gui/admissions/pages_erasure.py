"""Admissions window page: GDPR erasure requests (two people).

One person requests erasure with a reason; a second person with
governance access approves (the data is erased then) or rejects it with
a note. The erasure log keeps who, when and why, by applicant id only.
"""

from __future__ import annotations

import json
from tkinter import ttk
from typing import Any

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.sixth_form.domain.admissions import (
    admissions as adm,
    record_safety,
)
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)
from education_system.systems.sixth_form.interfaces.gui.admissions import (
    pages_common as pc,
)

TITLE = "Erasure Requests"


class ErasurePage:
    COLS = [("id", "#", 45), ("aid", "Applicant", 85), ("name", "Name", 160),
            ("by", "Requested by", 110), ("at", "Requested", 140),
            ("reason", "Reason", 260), ("status", "Status", 75),
            ("decided_by", "Decided by", 100), ("decided_at", "Decided", 140),
            ("note", "Note", 200)]
    LOG_COLS = [("id", "#", 45), ("aid", "Applicant", 90),
                ("at", "Erased", 140), ("by", "Requested by", 130),
                ("approved", "Approved by", 170), ("reason", "Reason", 330),
                ("rows", "Rows removed", 90)]

    def __init__(self, nb: Any) -> None:
        self.frame = pc.new_page(
            nb, TITLE, "GDPR erasure requests",
            "Erasure needs two people: a request with a reason, then approval "
            "by a different person with governance access. An applicant who "
            "became a student is erased through the student's GDPR request "
            "instead.")
        self.can_request = pc.can(access.ADMISSIONS)
        self.can_decide = record_safety.can_approve_erasure()
        bar = ttk.Frame(self.frame)
        bar.pack(side="top", fill="x", pady=(0, 2))
        ttk.Label(bar, text="Show:").pack(side="left")
        self.filter = ttk.Combobox(bar, state="readonly", width=12,
                                   values=("Pending", "All")
                                   + tuple(s for s in
                                           record_safety.REQUEST_STATUSES
                                           if s != "Pending"))
        self.filter.set("Pending")
        self.filter.pack(side="left", padx=(4, 10))
        self.filter.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        dst = "normal" if self.can_decide else "disabled"
        ttk.Button(bar, text="Approve and erase…", command=self._approve,
                   state=dst).pack(side="left", padx=(0, 4))
        ttk.Button(bar, text="Reject…", command=self._reject,
                   state=dst).pack(side="left", padx=(0, 4))
        ttk.Button(bar, text="Request erasure…", command=self._request,
                   state="normal" if self.can_request else "disabled").pack(
            side="left", padx=(12, 4))
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(
            side="right")
        if not self.can_decide:
            ttk.Label(self.frame, text="Approving or rejecting needs "
                      "governance access.", foreground=pc.MUTED).pack(
                side="top", anchor="w")
        self.status = pc.status_line(self.frame)
        log = ttk.LabelFrame(self.frame, text="Erasure log", padding=4)
        log.pack(side="bottom", fill="x", pady=(6, 0))
        self.log = pc.make_tree(log, self.LOG_COLS, height=6)
        holder = ttk.Frame(self.frame)
        holder.pack(fill="both", expand=True)
        self.tree = pc.make_tree(holder, self.COLS, height=10)
        self._rows: dict[str, record_safety.ErasureRequest] = {}
        self.refresh()

    def refresh(self) -> None:
        pc.clear(self.tree)
        f = self.filter.get()
        status = None if f == "All" else f
        ok, rows = pc.load(self.status, TITLE,
                           record_safety.list_erasure_requests, status=status)
        if ok:
            names: dict[str, str] = {}
            ok2, apps = pc.load(self.status, TITLE, adm.list_applicants,
                                include_archived=True)
            for a in apps or []:
                names[a.applicant_id] = a.full_name
            self._rows = {str(r.request_id): r for r in rows}
            for r in rows:
                self.tree.insert("", "end", iid=str(r.request_id), values=(
                    r.request_id, r.applicant_id,
                    names.get(r.applicant_id, "(erased)"), r.requested_by,
                    r.requested_at, r.reason.replace("\n", " "), r.status,
                    r.decided_by or "", r.decided_at or "",
                    (r.decision_note or "").replace("\n", " ")))
            pending = sum(1 for r in rows if r.status == "Pending")
            if ok2:
                self.status.set(f"{len(rows)} request(s) shown · {pending} "
                                "waiting for a second person")
        pc.clear(self.log)
        ok, log = pc.load(self.status, TITLE, record_safety.erasure_log)
        for e in log or []:
            try:
                n = sum((json.loads(e.get("rows_json") or "{}") or {}).values())
            except (ValueError, TypeError, AttributeError):
                n = ""
            self.log.insert("", "end", iid=str(e["id"]), values=(
                e["id"], e["applicant_id"], e["erased_at"],
                e.get("requested_by") or "", e.get("approved_by") or "",
                (e.get("reason") or "").replace("\n", " "), n))

    def _request_row(self) -> record_safety.ErasureRequest | None:
        iid = pc.selected(self.tree, TITLE)
        return self._rows.get(iid) if iid else None

    def _approve(self) -> None:
        r = self._request_row()
        if r is None:
            return
        if r.status != "Pending":
            messagebox.showinfo(TITLE, f"Request #{r.request_id} is already "
                                f"{r.status}.",
                                parent=self.frame.winfo_toplevel())
            return
        if not messagebox.askyesno(
                TITLE, f"Approve request #{r.request_id} and erase applicant "
                f"{r.applicant_id} now?\n\nRequested by {r.requested_by}: "
                f"{r.reason}\n\nEverything held about the applicant is removed "
                "permanently. This cannot be undone.",
                parent=self.frame.winfo_toplevel(), icon="warning"):
            return
        note = pc.ask_text(self.frame, f"Approve #{r.request_id}",
                           "Approval note (optional)")
        if note is None:
            return
        ok, done = pc.run(self.frame, TITLE, record_safety.approve_erasure,
                          r.request_id, note=note or None)
        if ok:
            messagebox.showinfo(
                TITLE, f"{r.applicant_id} erased." if done else
                f"{r.applicant_id} no longer exists; request approved.",
                parent=self.frame.winfo_toplevel())
            self.refresh()

    def _reject(self) -> None:
        r = self._request_row()
        if r is None:
            return
        note = pc.ask_text(self.frame, f"Reject #{r.request_id}",
                           "Why is the request rejected?", required=True)
        if note is None:
            return
        ok, _ = pc.run(self.frame, TITLE, record_safety.reject_erasure,
                       r.request_id, note=note)
        if ok:
            self.refresh()

    def _request(self) -> None:
        ok, apps = pc.run(self.frame, TITLE, adm.list_applicants,
                          include_archived=True)
        if not ok:
            return
        rows = [(a.applicant_id, (a.applicant_id, a.full_name, a.status,
                                  "Yes" if a.is_archived else ""))
                for a in apps if not a.converted_student_id]
        aid = pc.pick_row(self.frame, "Request erasure — choose applicant",
                          [("id", "ID", 90), ("name", "Name", 220),
                           ("status", "Status", 140),
                           ("archived", "Archived", 70)], rows,
                          prompt="Applicants who became students are not "
                                 "listed: erase them through the student's "
                                 "GDPR request.")
        if not aid:
            return
        reason = pc.ask_text(
            self.frame, f"Request erasure — {aid}",
            "Reason (e.g. the applicant's request and its date)",
            required=True)
        if reason is None:
            return
        ok, req = pc.run(self.frame, TITLE, record_safety.request_erasure, aid,
                         reason=reason)
        if ok:
            messagebox.showinfo(
                TITLE, f"Request #{req.request_id} recorded. A second person "
                "with governance access must approve it.",
                parent=self.frame.winfo_toplevel())
            self.filter.set("Pending")
            self.refresh()
