"""Tkinter views for Primary School GDPR."""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.primary.domain.governance.gdpr import gdpr as data
from education_system.platform import branding
from education_system.systems.primary.domain.governance.gdpr.gdpr import (
    BREACH_SEVERITIES,
    BREACH_STATUSES,
    CONSENT_PURPOSES,
    DEFAULT_BREACH_SEVERITY,
    DEFAULT_BREACH_STATUS,
    DEFAULT_CONSENT_PURPOSE,
    DEFAULT_PROCESSING_STATUS,
    DEFAULT_REQUEST_STATUS,
    DEFAULT_REQUEST_TYPE,
    DEFAULT_SUBJECT_TYPE,
    LAWFUL_BASES,
    PROCESSING_STATUSES,
    REQUEST_STATUSES,
    REQUEST_TYPES,
    SUBJECT_TYPES,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_gdpr_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"GDPR — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)
    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)
    RequestsTab(nb)
    ProcessingTab(nb)
    BreachesTab(nb)
    ConsentsTab(nb)
    OverviewTab(nb)


def _set_text(text: tk.Text, body: str) -> None:
    text.configure(state="normal")
    text.delete("1.0", "end")
    text.insert("1.0", body)
    text.configure(state="disabled")


# ── Reusable form helpers ─────────────────────────────────────────

@staticmethod
def _add_field(parent: tk.Misc, row: int, label: str,
               widget_factory: Callable[[tk.Misc], tk.Widget],
               *, sticky_widget: str = "ew") -> tk.Widget:
    ttk.Label(parent, text=label).grid(row=row, column=0,
                                          sticky="e", padx=6, pady=3)
    w = widget_factory(parent)
    w.grid(row=row, column=1, sticky=sticky_widget,
           padx=6, pady=3)
    return w


# ══ Requests tab ═══════════════════════════════════════════════════

class RequestsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Requests (DSAR)")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Filter:").pack(side="left")
        self.filter_var = tk.StringVar(value="open")
        for label, val in (("Open", "open"), ("Overdue", "overdue"),
                            ("All", "all")):
            ttk.Radiobutton(bar, text=label, value=val,
                             variable=self.filter_var,
                             command=self.refresh).pack(side="left")
        ttk.Label(bar, text="    Search:").pack(side="left")
        self.search_e = ttk.Entry(bar, width=24)
        self.search_e.pack(side="left", padx=4)
        self.search_e.bind("<Return>", lambda _e: self.refresh())
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=4)

        ttk.Button(bar, text="New…",
                    command=self._new).pack(side="right")
        ttk.Button(bar, text="Edit…",
                    command=self._edit).pack(side="right", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="right", padx=4)

        cols = ("request_id", "type", "subject", "received", "due",
                "days", "status", "handler")
        widths = {"request_id": 50, "type": 180, "subject": 180,
                   "received": 90, "due": 90, "days": 60,
                   "status": 120, "handler": 110}
        wrap = ttk.Frame(self.frame)
        wrap.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree = ttk.Treeview(wrap, columns=cols,
                                    show="headings", height=22)
        for c, h in zip(cols, ("#", "Type", "Subject", "Received",
                                  "Due", "Days", "Status", "Handler")):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(wrap, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("overdue", background="#ffe2e2")
        self.tree.tag_configure("closed", foreground="#999")
        self.tree.bind("<Double-1>", lambda _e: self._edit())

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        filt = self.filter_var.get()
        search = self.search_e.get().strip() or None
        if filt == "open":
            rows = data.list_requests(open_only=True, search=search)
        elif filt == "overdue":
            rows = data.list_requests(overdue_only=True,
                                        search=search)
        else:
            rows = data.list_requests(search=search)
        for r in rows:
            dr = r.days_remaining
            days = ("OVR" if r.is_overdue
                    else (str(dr) if dr is not None else "—"))
            tags = []
            if r.is_overdue:
                tags.append("overdue")
            if not r.is_open:
                tags.append("closed")
            self.tree.insert("", "end", iid=str(r.request_id),
                              values=(r.request_id, r.request_type,
                                       r.subject_name,
                                       r.received_date, r.due_date,
                                       days, r.status,
                                       r.handler or ""),
                              tags=tuple(tags))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except ValueError:
            return None

    def _new(self) -> None:
        RequestDialog(self.frame, on_save=self._save_new)

    def _save_new(self, payload: dict[str, Any]) -> None:
        try:
            data.create_request(payload)
        except ValidationError as e:
            messagebox.showerror("Save", str(e))
            return
        self.refresh()

    def _edit(self) -> None:
        rid = self._selected_id()
        if rid is None:
            return
        existing = data.get_request(rid)
        if existing is None:
            return
        RequestDialog(self.frame, existing=existing,
                       on_save=lambda p: self._save_edit(rid, p))

    def _save_edit(self, rid: int, payload: dict[str, Any]) -> None:
        try:
            data.update_request(rid, payload)
        except ValidationError as e:
            messagebox.showerror("Save", str(e))
            return
        self.refresh()

    def _delete(self) -> None:
        rid = self._selected_id()
        if rid is None:
            return
        if not messagebox.askyesno("Delete",
                                      f"Delete request #{rid}?"):
            return
        data.delete_request(rid)
        self.refresh()


class RequestDialog(tk.Toplevel):
    def __init__(self, master, existing: data.Request | None = None,
                 *, on_save) -> None:
        super().__init__(master)
        self.title("DSAR / Rights Request")
        self.geometry("720x720")
        self.transient(master.winfo_toplevel())
        self.after_idle(self.grab_set)
        self._existing = existing
        self._on_save = on_save
        self._build()

    def _build(self) -> None:
        wrap = ttk.Frame(self, padding=10)
        wrap.pack(fill="both", expand=True)
        wrap.columnconfigure(1, weight=1)

        self.subj_name_e = ttk.Entry(wrap)
        self.subj_type_cb = ttk.Combobox(
            wrap, values=SUBJECT_TYPES, state="readonly")
        self.subj_ref_e = ttk.Entry(wrap)
        self.req_type_cb = ttk.Combobox(
            wrap, values=REQUEST_TYPES, state="readonly")
        self.received_e = ttk.Entry(wrap)
        self.due_e = ttk.Entry(wrap)
        self.id_var = tk.BooleanVar()
        id_cb = ttk.Checkbutton(wrap, variable=self.id_var)
        self.status_cb = ttk.Combobox(
            wrap, values=REQUEST_STATUSES, state="readonly")
        self.resp_date_e = ttk.Entry(wrap)
        self.handler_e = ttk.Entry(wrap)
        self.email_e = ttk.Entry(wrap)
        self.phone_e = ttk.Entry(wrap)
        self.desc_t = tk.Text(wrap, height=3, width=40)
        self.resp_summary_t = tk.Text(wrap, height=3, width=40)
        self.refusal_e = ttk.Entry(wrap)
        self.notes_t = tk.Text(wrap, height=3, width=40)

        fields = [
            ("Subject name:",   self.subj_name_e),
            ("Subject type:",   self.subj_type_cb),
            ("Subject ref:",    self.subj_ref_e),
            ("Request type:",   self.req_type_cb),
            ("Received date:",  self.received_e),
            ("Due date:",       self.due_e),
            ("Identity verified:", id_cb),
            ("Status:",         self.status_cb),
            ("Responded date:", self.resp_date_e),
            ("Handler:",        self.handler_e),
            ("Contact email:",  self.email_e),
            ("Contact phone:",  self.phone_e),
            ("Description:",    self.desc_t),
            ("Response summary:", self.resp_summary_t),
            ("Refusal reason:", self.refusal_e),
            ("Notes:",          self.notes_t),
        ]
        for i, (lbl, w) in enumerate(fields):
            ttk.Label(wrap, text=lbl).grid(row=i, column=0,
                                              sticky="ne",
                                              padx=6, pady=2)
            w.grid(row=i, column=1, sticky="ew",
                   padx=6, pady=2)

        btns = ttk.Frame(wrap)
        btns.grid(row=len(fields), column=0, columnspan=2,
                   sticky="e", pady=10)
        ttk.Button(btns, text="Save",
                    command=self._save).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancel",
                    command=self.destroy).pack(side="left", padx=4)

        # Defaults
        today = _date.today().isoformat()
        if self._existing is None:
            self.subj_type_cb.set(DEFAULT_SUBJECT_TYPE)
            self.req_type_cb.set(DEFAULT_REQUEST_TYPE)
            self.received_e.insert(0, today)
            self.status_cb.set(DEFAULT_REQUEST_STATUS)
        else:
            e = self._existing
            self.subj_name_e.insert(0, e.subject_name)
            self.subj_type_cb.set(e.subject_type)
            self.subj_ref_e.insert(0, e.subject_ref or "")
            self.req_type_cb.set(e.request_type)
            self.received_e.insert(0, e.received_date)
            self.due_e.insert(0, e.due_date)
            self.id_var.set(e.identity_verified)
            self.status_cb.set(e.status)
            self.resp_date_e.insert(0, e.responded_date or "")
            self.handler_e.insert(0, e.handler or "")
            self.email_e.insert(0, e.contact_email or "")
            self.phone_e.insert(0, e.contact_phone or "")
            self.desc_t.insert("1.0", e.description or "")
            self.resp_summary_t.insert("1.0",
                                         e.response_summary or "")
            self.refusal_e.insert(0, e.refusal_reason or "")
            self.notes_t.insert("1.0", e.notes or "")

    def _save(self) -> None:
        payload = {
            "subject_name": self.subj_name_e.get().strip(),
            "subject_type": self.subj_type_cb.get(),
            "subject_ref":  self.subj_ref_e.get().strip(),
            "request_type": self.req_type_cb.get(),
            "received_date": self.received_e.get().strip(),
            "due_date":     self.due_e.get().strip(),
            "identity_verified": self.id_var.get(),
            "status":       self.status_cb.get(),
            "responded_date": self.resp_date_e.get().strip(),
            "handler":      self.handler_e.get().strip(),
            "contact_email": self.email_e.get().strip(),
            "contact_phone": self.phone_e.get().strip(),
            "description":  self.desc_t.get("1.0", "end").strip(),
            "response_summary":
                self.resp_summary_t.get("1.0", "end").strip(),
            "refusal_reason": self.refusal_e.get().strip(),
            "notes":        self.notes_t.get("1.0", "end").strip(),
        }
        if not payload["subject_name"]:
            messagebox.showerror("Save", "Subject name is required.")
            return
        self._on_save(payload)
        self.destroy()


# ══ Processing tab ═════════════════════════════════════════════════

class ProcessingTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Processing (RoPA)")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Search:").pack(side="left")
        self.search_e = ttk.Entry(bar, width=28)
        self.search_e.pack(side="left", padx=4)
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="New…",
                    command=self._new).pack(side="right")
        ttk.Button(bar, text="Edit…",
                    command=self._edit).pack(side="right", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="right", padx=4)

        cols = ("activity_id", "name", "lawful_basis", "status",
                "retention", "dpia", "next_review")
        widths = {"activity_id": 50, "name": 240,
                   "lawful_basis": 170, "status": 110,
                   "retention": 200, "dpia": 80,
                   "next_review": 110}
        wrap = ttk.Frame(self.frame)
        wrap.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree = ttk.Treeview(wrap, columns=cols,
                                    show="headings", height=22)
        for c, h in zip(cols, ("#", "Name", "Lawful basis", "Status",
                                  "Retention", "DPIA",
                                  "Next review")):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(wrap, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self._edit())

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        q = self.search_e.get().strip() or None
        for p in data.list_processing(search=q):
            dpia = ("done" if p.dpia_completed
                    else ("required" if p.dpia_required else "—"))
            self.tree.insert("", "end", iid=str(p.activity_id),
                              values=(p.activity_id, p.name,
                                       p.lawful_basis, p.status,
                                       p.retention or "", dpia,
                                       p.next_review or ""))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except ValueError:
            return None

    def _new(self) -> None:
        ProcessingDialog(self.frame, on_save=self._save_new)

    def _save_new(self, payload: dict[str, Any]) -> None:
        try:
            data.create_processing(payload)
        except ValidationError as e:
            messagebox.showerror("Save", str(e))
            return
        self.refresh()

    def _edit(self) -> None:
        aid = self._selected_id()
        if aid is None:
            return
        existing = data.get_processing(aid)
        if existing is None:
            return
        ProcessingDialog(self.frame, existing=existing,
                          on_save=lambda p: self._save_edit(aid, p))

    def _save_edit(self, aid: int, payload: dict[str, Any]) -> None:
        try:
            data.update_processing(aid, payload)
        except ValidationError as e:
            messagebox.showerror("Save", str(e))
            return
        self.refresh()

    def _delete(self) -> None:
        aid = self._selected_id()
        if aid is None:
            return
        if not messagebox.askyesno("Delete",
                                      f"Delete activity #{aid}?"):
            return
        data.delete_processing(aid)
        self.refresh()


class ProcessingDialog(tk.Toplevel):
    def __init__(self, master,
                 existing: data.ProcessingActivity | None = None, *,
                 on_save) -> None:
        super().__init__(master)
        self.title("Processing Activity")
        self.geometry("720x740")
        self.transient(master.winfo_toplevel())
        self.after_idle(self.grab_set)
        self._existing = existing
        self._on_save = on_save
        self._build()

    def _build(self) -> None:
        wrap = ttk.Frame(self, padding=10)
        wrap.pack(fill="both", expand=True)
        wrap.columnconfigure(1, weight=1)
        self.name_e = ttk.Entry(wrap)
        self.controller_e = ttk.Entry(wrap)
        self.purpose_t = tk.Text(wrap, height=2, width=40)
        self.basis_cb = ttk.Combobox(
            wrap, values=LAWFUL_BASES, state="readonly")
        self.cats_t = tk.Text(wrap, height=2, width=40)
        self.subj_e = ttk.Entry(wrap)
        self.recip_e = ttk.Entry(wrap)
        self.retain_e = ttk.Entry(wrap)
        self.transfers_e = ttk.Entry(wrap)
        self.security_t = tk.Text(wrap, height=2, width=40)
        self.dpia_req_var = tk.BooleanVar()
        self.dpia_done_var = tk.BooleanVar()
        dpia_req_cb = ttk.Checkbutton(wrap, variable=self.dpia_req_var)
        dpia_done_cb = ttk.Checkbutton(wrap,
                                          variable=self.dpia_done_var)
        self.dpia_date_e = ttk.Entry(wrap)
        self.status_cb = ttk.Combobox(
            wrap, values=PROCESSING_STATUSES, state="readonly")
        self.last_e = ttk.Entry(wrap)
        self.next_e = ttk.Entry(wrap)
        self.notes_t = tk.Text(wrap, height=3, width=40)

        fields = [
            ("Name:",             self.name_e),
            ("Controller:",       self.controller_e),
            ("Purpose:",          self.purpose_t),
            ("Lawful basis:",     self.basis_cb),
            ("Data categories:",  self.cats_t),
            ("Data subjects:",    self.subj_e),
            ("Recipients:",       self.recip_e),
            ("Retention:",        self.retain_e),
            ("Transfers:",        self.transfers_e),
            ("Security measures:", self.security_t),
            ("DPIA required:",    dpia_req_cb),
            ("DPIA completed:",   dpia_done_cb),
            ("DPIA date:",        self.dpia_date_e),
            ("Status:",           self.status_cb),
            ("Last reviewed:",    self.last_e),
            ("Next review:",      self.next_e),
            ("Notes:",            self.notes_t),
        ]
        for i, (lbl, w) in enumerate(fields):
            ttk.Label(wrap, text=lbl).grid(row=i, column=0,
                                              sticky="ne",
                                              padx=6, pady=2)
            w.grid(row=i, column=1, sticky="ew",
                   padx=6, pady=2)
        btns = ttk.Frame(wrap)
        btns.grid(row=len(fields), column=0, columnspan=2,
                   sticky="e", pady=10)
        ttk.Button(btns, text="Save",
                    command=self._save).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancel",
                    command=self.destroy).pack(side="left", padx=4)

        if self._existing is None:
            self.basis_cb.set("Public Task")
            self.status_cb.set(DEFAULT_PROCESSING_STATUS)
        else:
            e = self._existing
            self.name_e.insert(0, e.name)
            self.controller_e.insert(0, e.controller or "")
            self.purpose_t.insert("1.0", e.purpose)
            self.basis_cb.set(e.lawful_basis)
            self.cats_t.insert("1.0", e.data_categories or "")
            self.subj_e.insert(0, e.data_subjects or "")
            self.recip_e.insert(0, e.recipients or "")
            self.retain_e.insert(0, e.retention or "")
            self.transfers_e.insert(0, e.transfers or "")
            self.security_t.insert("1.0", e.security_measures or "")
            self.dpia_req_var.set(e.dpia_required)
            self.dpia_done_var.set(e.dpia_completed)
            self.dpia_date_e.insert(0, e.dpia_date or "")
            self.status_cb.set(e.status)
            self.last_e.insert(0, e.last_reviewed or "")
            self.next_e.insert(0, e.next_review or "")
            self.notes_t.insert("1.0", e.notes or "")

    def _save(self) -> None:
        payload = {
            "name":            self.name_e.get().strip(),
            "controller":      self.controller_e.get().strip(),
            "purpose":         self.purpose_t.get(
                "1.0", "end").strip(),
            "lawful_basis":    self.basis_cb.get(),
            "data_categories": self.cats_t.get(
                "1.0", "end").strip(),
            "data_subjects":   self.subj_e.get().strip(),
            "recipients":      self.recip_e.get().strip(),
            "retention":       self.retain_e.get().strip(),
            "transfers":       self.transfers_e.get().strip(),
            "security_measures":
                self.security_t.get("1.0", "end").strip(),
            "dpia_required":   self.dpia_req_var.get(),
            "dpia_completed":  self.dpia_done_var.get(),
            "dpia_date":       self.dpia_date_e.get().strip(),
            "status":          self.status_cb.get(),
            "last_reviewed":   self.last_e.get().strip(),
            "next_review":     self.next_e.get().strip(),
            "notes":           self.notes_t.get(
                "1.0", "end").strip(),
        }
        if not payload["name"] or not payload["purpose"]:
            messagebox.showerror(
                "Save", "Name and Purpose are required.")
            return
        self._on_save(payload)
        self.destroy()


# ══ Breaches tab ═══════════════════════════════════════════════════

class BreachesTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Breaches")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        self.open_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Open only",
                         variable=self.open_var,
                         command=self.refresh).pack(side="left")
        ttk.Button(bar, text="New…",
                    command=self._new).pack(side="right")
        ttk.Button(bar, text="Edit…",
                    command=self._edit).pack(side="right", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="right", padx=4)

        cols = ("breach_id", "discovered", "title", "severity",
                "status", "affected", "ico", "closed")
        widths = {"breach_id": 50, "discovered": 100,
                   "title": 280, "severity": 90, "status": 130,
                   "affected": 80, "ico": 80, "closed": 100}
        wrap = ttk.Frame(self.frame)
        wrap.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree = ttk.Treeview(wrap, columns=cols,
                                    show="headings", height=22)
        for c, h in zip(cols, ("#", "Discovered", "Title",
                                  "Severity", "Status", "Affected",
                                  "ICO?", "Closed")):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.tag_configure("hi", background="#ffe2e2")
        vs = ttk.Scrollbar(wrap, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self._edit())

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for b in data.list_breaches(open_only=self.open_var.get()):
            tags = ("hi",) if b.severity in (
                "High", "Critical") else ()
            self.tree.insert("", "end", iid=str(b.breach_id),
                              values=(b.breach_id, b.discovered_date,
                                       b.title, b.severity, b.status,
                                       b.affected_count,
                                       "Yes" if b.ico_notifiable
                                       else "No",
                                       b.closed_date or ""),
                              tags=tags)

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except ValueError:
            return None

    def _new(self) -> None:
        BreachDialog(self.frame, on_save=self._save_new)

    def _save_new(self, payload: dict[str, Any]) -> None:
        try:
            data.create_breach(payload)
        except ValidationError as e:
            messagebox.showerror("Save", str(e))
            return
        self.refresh()

    def _edit(self) -> None:
        bid = self._selected_id()
        if bid is None:
            return
        existing = data.get_breach(bid)
        if existing is None:
            return
        BreachDialog(self.frame, existing=existing,
                      on_save=lambda p: self._save_edit(bid, p))

    def _save_edit(self, bid: int, payload: dict[str, Any]) -> None:
        try:
            data.update_breach(bid, payload)
        except ValidationError as e:
            messagebox.showerror("Save", str(e))
            return
        self.refresh()

    def _delete(self) -> None:
        bid = self._selected_id()
        if bid is None:
            return
        if not messagebox.askyesno("Delete",
                                      f"Delete breach #{bid}?"):
            return
        data.delete_breach(bid)
        self.refresh()


class BreachDialog(tk.Toplevel):
    def __init__(self, master, existing: data.Breach | None = None,
                 *, on_save) -> None:
        super().__init__(master)
        self.title("Personal Data Breach")
        self.geometry("760x820")
        self.transient(master.winfo_toplevel())
        self.after_idle(self.grab_set)
        self._existing = existing
        self._on_save = on_save
        self._build()

    def _build(self) -> None:
        wrap = ttk.Frame(self, padding=10)
        wrap.pack(fill="both", expand=True)
        wrap.columnconfigure(1, weight=1)

        self.title_e = ttk.Entry(wrap)
        self.disc_e = ttk.Entry(wrap)
        self.occ_e = ttk.Entry(wrap)
        self.reporter_e = ttk.Entry(wrap)
        self.severity_cb = ttk.Combobox(
            wrap, values=BREACH_SEVERITIES, state="readonly")
        self.status_cb = ttk.Combobox(
            wrap, values=BREACH_STATUSES, state="readonly")
        self.affected_e = ttk.Entry(wrap)
        self.cats_e = ttk.Entry(wrap)
        self.summary_t = tk.Text(wrap, height=3, width=40)
        self.cause_t = tk.Text(wrap, height=3, width=40)
        self.remed_t = tk.Text(wrap, height=3, width=40)
        self.ico_var = tk.BooleanVar()
        ico_cb = ttk.Checkbutton(wrap, variable=self.ico_var)
        self.ico_date_e = ttk.Entry(wrap)
        self.ico_ref_e = ttk.Entry(wrap)
        self.subj_var = tk.BooleanVar()
        subj_cb = ttk.Checkbutton(wrap, variable=self.subj_var)
        self.subj_date_e = ttk.Entry(wrap)
        self.closed_e = ttk.Entry(wrap)
        self.lessons_t = tk.Text(wrap, height=3, width=40)
        self.notes_t = tk.Text(wrap, height=3, width=40)

        fields = [
            ("Title:",            self.title_e),
            ("Discovered date:",  self.disc_e),
            ("Occurred date:",    self.occ_e),
            ("Reported by:",      self.reporter_e),
            ("Severity:",         self.severity_cb),
            ("Status:",           self.status_cb),
            ("Affected count:",   self.affected_e),
            ("Affected categories:", self.cats_e),
            ("Summary:",          self.summary_t),
            ("Root cause:",       self.cause_t),
            ("Remediation:",      self.remed_t),
            ("ICO notifiable:",   ico_cb),
            ("ICO notified date:", self.ico_date_e),
            ("ICO reference:",    self.ico_ref_e),
            ("Subjects notified:", subj_cb),
            ("Subjects notified date:", self.subj_date_e),
            ("Closed date:",      self.closed_e),
            ("Lessons learned:",  self.lessons_t),
            ("Notes:",            self.notes_t),
        ]
        for i, (lbl, w) in enumerate(fields):
            ttk.Label(wrap, text=lbl).grid(row=i, column=0,
                                              sticky="ne",
                                              padx=6, pady=2)
            w.grid(row=i, column=1, sticky="ew",
                   padx=6, pady=2)
        btns = ttk.Frame(wrap)
        btns.grid(row=len(fields), column=0, columnspan=2,
                   sticky="e", pady=10)
        ttk.Button(btns, text="Save",
                    command=self._save).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancel",
                    command=self.destroy).pack(side="left", padx=4)

        today = _date.today().isoformat()
        if self._existing is None:
            self.disc_e.insert(0, today)
            self.severity_cb.set(DEFAULT_BREACH_SEVERITY)
            self.status_cb.set(DEFAULT_BREACH_STATUS)
            self.affected_e.insert(0, "0")
        else:
            e = self._existing
            self.title_e.insert(0, e.title)
            self.disc_e.insert(0, e.discovered_date)
            self.occ_e.insert(0, e.occurred_date or "")
            self.reporter_e.insert(0, e.reported_by or "")
            self.severity_cb.set(e.severity)
            self.status_cb.set(e.status)
            self.affected_e.insert(0, str(e.affected_count))
            self.cats_e.insert(0, e.affected_categories or "")
            self.summary_t.insert("1.0", e.summary)
            self.cause_t.insert("1.0", e.root_cause or "")
            self.remed_t.insert("1.0", e.remediation or "")
            self.ico_var.set(e.ico_notifiable)
            self.ico_date_e.insert(0, e.ico_notified_date or "")
            self.ico_ref_e.insert(0, e.ico_reference or "")
            self.subj_var.set(e.subjects_notified)
            self.subj_date_e.insert(0,
                                       e.subjects_notified_date or "")
            self.closed_e.insert(0, e.closed_date or "")
            self.lessons_t.insert("1.0", e.lessons_learned or "")
            self.notes_t.insert("1.0", e.notes or "")

    def _save(self) -> None:
        payload = {
            "title":          self.title_e.get().strip(),
            "discovered_date": self.disc_e.get().strip(),
            "occurred_date":  self.occ_e.get().strip(),
            "reported_by":    self.reporter_e.get().strip(),
            "severity":       self.severity_cb.get(),
            "status":         self.status_cb.get(),
            "affected_count": self.affected_e.get().strip() or 0,
            "affected_categories": self.cats_e.get().strip(),
            "summary":        self.summary_t.get(
                "1.0", "end").strip(),
            "root_cause":     self.cause_t.get(
                "1.0", "end").strip(),
            "remediation":    self.remed_t.get(
                "1.0", "end").strip(),
            "ico_notifiable": self.ico_var.get(),
            "ico_notified_date": self.ico_date_e.get().strip(),
            "ico_reference":  self.ico_ref_e.get().strip(),
            "subjects_notified": self.subj_var.get(),
            "subjects_notified_date":
                self.subj_date_e.get().strip(),
            "closed_date":    self.closed_e.get().strip(),
            "lessons_learned": self.lessons_t.get(
                "1.0", "end").strip(),
            "notes":          self.notes_t.get(
                "1.0", "end").strip(),
        }
        if not payload["title"] or not payload["summary"]:
            messagebox.showerror(
                "Save", "Title and Summary are required.")
            return
        self._on_save(payload)
        self.destroy()


# ══ Consents tab ═══════════════════════════════════════════════════

class ConsentsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Consents")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        self.active_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Active only",
                         variable=self.active_var,
                         command=self.refresh).pack(side="left")
        ttk.Label(bar, text="    Search:").pack(side="left")
        self.search_e = ttk.Entry(bar, width=24)
        self.search_e.pack(side="left", padx=4)
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=4)

        ttk.Button(bar, text="New…",
                    command=self._new).pack(side="right")
        ttk.Button(bar, text="Edit…",
                    command=self._edit).pack(side="right", padx=4)
        ttk.Button(bar, text="Withdraw…",
                    command=self._withdraw).pack(side="right", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="right", padx=4)

        cols = ("consent_id", "subject", "purpose", "granted_date",
                "expires_date", "withdrawn_date", "state")
        widths = {"consent_id": 60, "subject": 220, "purpose": 200,
                   "granted_date": 100, "expires_date": 100,
                   "withdrawn_date": 110, "state": 80}
        wrap = ttk.Frame(self.frame)
        wrap.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree = ttk.Treeview(wrap, columns=cols,
                                    show="headings", height=22)
        for c, h in zip(cols, ("#", "Subject", "Purpose", "Granted",
                                  "Expires", "Withdrawn", "State")):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(wrap, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("inactive", foreground="#888")
        self.tree.bind("<Double-1>", lambda _e: self._edit())

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        rows = data.list_consents(
            active_only=self.active_var.get(),
            search=self.search_e.get().strip() or None)
        for c in rows:
            tags = () if c.is_active else ("inactive",)
            self.tree.insert("", "end", iid=str(c.consent_id),
                              values=(c.consent_id, c.subject_name,
                                       c.purpose, c.granted_date,
                                       c.expires_date or "",
                                       c.withdrawn_date or "",
                                       "active" if c.is_active
                                       else "inactive"),
                              tags=tags)

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except ValueError:
            return None

    def _new(self) -> None:
        ConsentDialog(self.frame, on_save=self._save_new)

    def _save_new(self, payload: dict[str, Any]) -> None:
        try:
            data.create_consent(payload)
        except ValidationError as e:
            messagebox.showerror("Save", str(e))
            return
        self.refresh()

    def _edit(self) -> None:
        cid = self._selected_id()
        if cid is None:
            return
        existing = data.get_consent(cid)
        if existing is None:
            return
        ConsentDialog(self.frame, existing=existing,
                       on_save=lambda p: self._save_edit(cid, p))

    def _save_edit(self, cid: int, payload: dict[str, Any]) -> None:
        try:
            data.update_consent(cid, payload)
        except ValidationError as e:
            messagebox.showerror("Save", str(e))
            return
        self.refresh()

    def _withdraw(self) -> None:
        cid = self._selected_id()
        if cid is None:
            return
        when = _date.today().isoformat()
        if not messagebox.askyesno(
                "Withdraw",
                f"Withdraw consent #{cid} as of {when}?"):
            return
        try:
            data.withdraw_consent(cid, withdrawn_date=when)
        except ValidationError as e:
            messagebox.showerror("Withdraw", str(e))
            return
        self.refresh()

    def _delete(self) -> None:
        cid = self._selected_id()
        if cid is None:
            return
        if not messagebox.askyesno("Delete",
                                      f"Delete consent #{cid}?"):
            return
        data.delete_consent(cid)
        self.refresh()


class ConsentDialog(tk.Toplevel):
    def __init__(self, master, existing: data.Consent | None = None,
                 *, on_save) -> None:
        super().__init__(master)
        self.title("Consent")
        self.geometry("640x520")
        self.transient(master.winfo_toplevel())
        self.after_idle(self.grab_set)
        self._existing = existing
        self._on_save = on_save
        self._build()

    def _build(self) -> None:
        wrap = ttk.Frame(self, padding=10)
        wrap.pack(fill="both", expand=True)
        wrap.columnconfigure(1, weight=1)
        self.subj_name_e = ttk.Entry(wrap)
        self.subj_type_cb = ttk.Combobox(
            wrap, values=SUBJECT_TYPES, state="readonly")
        self.subj_ref_e = ttk.Entry(wrap)
        self.purpose_cb = ttk.Combobox(
            wrap, values=CONSENT_PURPOSES, state="readonly")
        self.granted_var = tk.BooleanVar(value=True)
        granted_cb = ttk.Checkbutton(wrap, variable=self.granted_var)
        self.granted_e = ttk.Entry(wrap)
        self.expires_e = ttk.Entry(wrap)
        self.withdrawn_e = ttk.Entry(wrap)
        self.source_e = ttk.Entry(wrap)
        self.detail_t = tk.Text(wrap, height=3, width=40)
        self.notes_t = tk.Text(wrap, height=3, width=40)

        fields = [
            ("Subject name:",  self.subj_name_e),
            ("Subject type:",  self.subj_type_cb),
            ("Subject ref:",   self.subj_ref_e),
            ("Purpose:",       self.purpose_cb),
            ("Granted:",       granted_cb),
            ("Granted date:",  self.granted_e),
            ("Expires date:",  self.expires_e),
            ("Withdrawn date:", self.withdrawn_e),
            ("Source:",        self.source_e),
            ("Detail:",        self.detail_t),
            ("Notes:",         self.notes_t),
        ]
        for i, (lbl, w) in enumerate(fields):
            ttk.Label(wrap, text=lbl).grid(row=i, column=0,
                                              sticky="ne",
                                              padx=6, pady=2)
            w.grid(row=i, column=1, sticky="ew",
                   padx=6, pady=2)
        btns = ttk.Frame(wrap)
        btns.grid(row=len(fields), column=0, columnspan=2,
                   sticky="e", pady=10)
        ttk.Button(btns, text="Save",
                    command=self._save).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancel",
                    command=self.destroy).pack(side="left", padx=4)

        today = _date.today().isoformat()
        if self._existing is None:
            self.subj_type_cb.set(DEFAULT_SUBJECT_TYPE)
            self.purpose_cb.set(DEFAULT_CONSENT_PURPOSE)
            self.granted_e.insert(0, today)
        else:
            e = self._existing
            self.subj_name_e.insert(0, e.subject_name)
            self.subj_type_cb.set(e.subject_type)
            self.subj_ref_e.insert(0, e.subject_ref or "")
            self.purpose_cb.set(e.purpose)
            self.granted_var.set(e.granted)
            self.granted_e.insert(0, e.granted_date)
            self.expires_e.insert(0, e.expires_date or "")
            self.withdrawn_e.insert(0, e.withdrawn_date or "")
            self.source_e.insert(0, e.source or "")
            self.detail_t.insert("1.0", e.detail or "")
            self.notes_t.insert("1.0", e.notes or "")

    def _save(self) -> None:
        payload = {
            "subject_name": self.subj_name_e.get().strip(),
            "subject_type": self.subj_type_cb.get(),
            "subject_ref":  self.subj_ref_e.get().strip(),
            "purpose":      self.purpose_cb.get(),
            "granted":      self.granted_var.get(),
            "granted_date": self.granted_e.get().strip(),
            "expires_date": self.expires_e.get().strip(),
            "withdrawn_date": self.withdrawn_e.get().strip(),
            "source":       self.source_e.get().strip(),
            "detail":       self.detail_t.get(
                "1.0", "end").strip(),
            "notes":        self.notes_t.get(
                "1.0", "end").strip(),
        }
        if not payload["subject_name"]:
            messagebox.showerror("Save", "Subject name is required.")
            return
        self._on_save(payload)
        self.destroy()


# ══ Overview tab ═══════════════════════════════════════════════════

class OverviewTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Overview")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        self.text = tk.Text(self.frame, wrap="word",
                             font=("TkFixedFont", 10),
                             state="disabled")
        self.text.pack(fill="both", expand=True, padx=8, pady=8)

    def refresh(self) -> None:
        try:
            o = data.overview()
        except Exception as e:
            _set_text(self.text, f"Error: {e}")
            return
        lines = [
            "═══ GDPR Overview ═══",
            "",
            "  Requests",
            f"    Total              : {o.total_requests}",
            f"    Open               : {o.open_requests}",
            f"    Overdue            : {o.overdue_requests}",
        ]
        if o.requests_by_type:
            lines.append("    By type:")
            for k, n in sorted(o.requests_by_type.items(),
                                key=lambda kv: -kv[1]):
                if n:
                    lines.append(f"      {k:<30} : {n}")
        lines += [
            "",
            "  Processing register (RoPA)",
            f"    Total              : {o.total_processing}",
            f"    Active             : {o.processing_active}",
            f"    Reviews due/overdue: {o.processing_due_review}",
            "",
            "  Breaches",
            f"    Total              : {o.total_breaches}",
            f"    Open               : {o.open_breaches}",
            f"    High / Critical    : {o.high_or_critical_breaches}",
            f"    ICO notifiable open: {o.ico_notifiable_open}",
            "",
            "  Consents",
            f"    Total              : {o.total_consents}",
            f"    Active             : {o.active_consents}",
            f"    Withdrawn          : {o.withdrawn_consents}",
        ]
        _set_text(self.text, "\n".join(lines))
