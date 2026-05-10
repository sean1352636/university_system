"""
Information Rights GUI — SAR / FOI / EIR request lifecycle dashboard.

Window sizing follows the project convention (1400x900, minsize
1200x800, no zoomed/fullscreen) so it lines up with Finance / Library.
"""

from __future__ import annotations

import os
import sys
import tkinter as tk
from datetime import date, datetime
from tkinter import messagebox, ttk
from typing import Optional


# Allow running this file directly (the launcher subprocess pattern).
if "education_system" not in sys.modules:
    _here = os.path.abspath(os.path.dirname(__file__))
    while _here and not os.path.isdir(
            os.path.join(_here, "education_system")):
        _parent = os.path.dirname(_here)
        if _parent == _here:
            break
        _here = _parent
    if _here and _here not in sys.path:
        sys.path.insert(0, _here)


from education_system.university_system.modules.domain.legal.information_rights.services.information_rights_core import (  # noqa: E501
    InformationRightsService,
    InformationRightsError,
    REQUEST_TYPES,
    REQUEST_STATUSES,
    OUTCOMES,
    FOIA_EXEMPTIONS,
    DPA_EXEMPTIONS,
    EIR_EXCEPTIONS,
)


def _parse_date(s: str) -> Optional[date]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


class InformationRightsGUI:
    """Tk window managing SAR/FOI/EIR requests."""

    # Open-in bar targets — same convention as the EQA dashboard. Each
    # entry is (label, UnifiedManagementGUI method name); buttons
    # auto-disable when the parent app doesn't expose the method.
    _OPEN_IN_TARGETS = (
        ("Student Records", "show_student_records"),
        ("Communication Hub", "show_communication_hub_gui"),
        ("Documents", "show_data_documents_gui"),
        ("Security Dashboard", "show_security_dashboard"),
        ("Cross-System Calendar", "show_cross_system_calendar_gui"),
        ("Business Intel", "show_business_intelligence_gui"),
        ("GDPR Cross-System", "show_cross_gdpr_gui"),
    )

    def __init__(self, master: Optional[tk.Tk] = None,
                 actor: str = "gui",
                 app: object | None = None) -> None:
        self.actor = actor
        self.svc = InformationRightsService()

        # Reference to the UnifiedManagementGUI instance (when launched
        # in-process). Drill-through buttons require it; the subprocess
        # path leaves it None and the Open-in bar is disabled.
        self.app = app

        self.root = master or tk.Tk()
        self.root.title("Information Rights — SAR / FOI / EIR")
        self.root.geometry("1400x900")
        self.root.minsize(1200, 800)

        self._build_open_in_bar(self.root)
        self._build_ui()
        self.refresh_all()

        if self.app is not None:
            try:
                self.app._ir_window = self
                self.root.bind("<Destroy>", self._on_destroy, add="+")
            except Exception:
                pass

    def _on_destroy(self, event) -> None:
        if event.widget is not self.root:
            return
        try:
            if getattr(self.app, "_ir_window", None) is self:
                self.app._ir_window = None
        except Exception:
            pass

    # ---------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_dash = ttk.Frame(nb)
        self.tab_list = ttk.Frame(nb)
        self.tab_intake = ttk.Frame(nb)
        self.tab_detail = ttk.Frame(nb)

        nb.add(self.tab_dash, text="Dashboard")
        nb.add(self.tab_list, text="All requests")
        nb.add(self.tab_intake, text="New request")
        nb.add(self.tab_detail, text="Request detail")

        self._build_dashboard(self.tab_dash)
        self._build_list(self.tab_list)
        self._build_intake(self.tab_intake)
        self._build_detail(self.tab_detail)

        self.notebook = nb

    # ----------------------------------------------------- DASHBOARD tab
    def _build_dashboard(self, parent: ttk.Frame) -> None:
        head = ttk.Frame(parent)
        head.pack(fill="x", pady=(8, 4), padx=8)
        ttk.Label(head, text="Statutory deadline dashboard",
                  font=("TkDefaultFont", 14, "bold")).pack(side="left")
        ttk.Button(head, text="Refresh",
                   command=self.refresh_all).pack(side="right")

        self.lbl_summary = ttk.Label(parent, text="", justify="left",
                                     font=("TkFixedFont", 10))
        self.lbl_summary.pack(fill="x", padx=8, pady=4)

        sec = ttk.LabelFrame(parent, text="OVERDUE")
        sec.pack(fill="both", expand=True, padx=8, pady=4)
        self.tv_overdue = self._make_request_tree(sec)

        sec2 = ttk.LabelFrame(parent, text="Due within 7 days")
        sec2.pack(fill="both", expand=True, padx=8, pady=4)
        self.tv_due_soon = self._make_request_tree(sec2)

    def _make_request_tree(self, parent) -> ttk.Treeview:
        cols = ("ref", "type", "status", "deadline", "days",
                "officer", "requester")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=6)
        for c, w in zip(cols, (110, 60, 130, 110, 70, 140, 240)):
            tv.heading(c, text=c.title())
            tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=4, pady=4)
        tv.bind("<Double-1>", lambda e, t=tv: self._open_from_tree(t))
        return tv

    def _open_from_tree(self, tv: ttk.Treeview) -> None:
        sel = tv.selection()
        if not sel:
            return
        ref = tv.item(sel[0], "values")[0]
        try:
            r = self.svc.get_by_reference(ref)
        except InformationRightsError as e:
            messagebox.showerror("Open request", str(e))
            return
        self._load_detail(r["request_id"])
        self.notebook.select(self.tab_detail)

    # ---------------------------------------------------------- LIST tab
    def _build_list(self, parent: ttk.Frame) -> None:
        bar = ttk.Frame(parent)
        bar.pack(fill="x", padx=8, pady=6)
        ttk.Label(bar, text="Type:").pack(side="left")
        self.var_filter_type = tk.StringVar(value="(all)")
        ttk.Combobox(bar, textvariable=self.var_filter_type,
                     values=("(all)",) + REQUEST_TYPES,
                     state="readonly", width=8).pack(side="left", padx=4)

        ttk.Label(bar, text="Status:").pack(side="left", padx=(10, 0))
        self.var_filter_status = tk.StringVar(value="(all open)")
        ttk.Combobox(bar, textvariable=self.var_filter_status,
                     values=("(all open)", "(all incl. closed)") +
                            REQUEST_STATUSES,
                     state="readonly", width=20).pack(side="left", padx=4)

        ttk.Button(bar, text="Apply",
                   command=self._refresh_list).pack(side="left", padx=8)
        ttk.Button(bar, text="Open",
                   command=lambda: self._open_from_tree(self.tv_list)) \
            .pack(side="right")

        self.tv_list = self._make_request_tree(parent)

    def _refresh_list(self) -> None:
        rt = self.var_filter_type.get()
        rt = None if rt == "(all)" else rt
        st = self.var_filter_status.get()
        if st == "(all open)":
            rows = self.svc.list_requests(request_type=rt,
                                          include_closed=False)
        elif st == "(all incl. closed)":
            rows = self.svc.list_requests(request_type=rt,
                                          include_closed=True)
        else:
            rows = self.svc.list_requests(request_type=rt, status=st)
        self._fill_tree(self.tv_list, rows)

    def _fill_tree(self, tv: ttk.Treeview, rows: list) -> None:
        for i in tv.get_children():
            tv.delete(i)
        today = date.today()
        for r in rows:
            days = self.svc.days_remaining(r, today)
            tv.insert("", "end", values=(
                r["reference"], r["request_type"], r["status"],
                r["deadline_on"], f"{days:+}",
                r.get("assigned_officer") or "",
                f"{r['requester_name']} <{r['requester_email']}>",
            ))

    # ------------------------------------------------------- INTAKE tab
    def _build_intake(self, parent: ttk.Frame) -> None:
        frm = ttk.LabelFrame(parent, text="Log a new request")
        frm.pack(fill="x", padx=8, pady=8)

        self.intake_vars = {
            "request_type": tk.StringVar(value="SAR"),
            "requester_name": tk.StringVar(),
            "requester_email": tk.StringVar(),
            "requester_phone": tk.StringVar(),
            "subject_summary": tk.StringVar(),
            "received_on": tk.StringVar(value=date.today().isoformat()),
            "assigned_officer": tk.StringVar(),
        }

        rows = [
            ("Type", "request_type", "combo", REQUEST_TYPES),
            ("Requester name *", "requester_name", "entry", None),
            ("Requester email *", "requester_email", "entry", None),
            ("Requester phone", "requester_phone", "entry", None),
            ("Subject / summary *", "subject_summary", "entry", None),
            ("Received on (YYYY-MM-DD)", "received_on", "entry", None),
            ("Assigned officer", "assigned_officer", "entry", None),
        ]
        for i, (lbl, key, kind, opts) in enumerate(rows):
            ttk.Label(frm, text=lbl).grid(row=i, column=0, sticky="e",
                                          padx=6, pady=3)
            if kind == "combo":
                ttk.Combobox(frm, textvariable=self.intake_vars[key],
                             values=opts, state="readonly",
                             width=10).grid(row=i, column=1,
                                            sticky="w", padx=4)
            else:
                ttk.Entry(frm, textvariable=self.intake_vars[key],
                          width=60).grid(row=i, column=1,
                                         sticky="w", padx=4)

        ttk.Label(frm, text="Scope details").grid(row=len(rows), column=0,
                                                  sticky="ne", padx=6,
                                                  pady=3)
        self.txt_scope = tk.Text(frm, height=4, width=60)
        self.txt_scope.grid(row=len(rows), column=1, sticky="w", padx=4,
                            pady=3)

        ttk.Button(frm, text="Create request",
                   command=self._submit_intake) \
            .grid(row=len(rows) + 1, column=1, sticky="w", padx=4, pady=8)

    def _submit_intake(self) -> None:
        v = {k: var.get() for k, var in self.intake_vars.items()}
        try:
            r = self.svc.create_request(
                request_type=v["request_type"],
                requester_name=v["requester_name"],
                requester_email=v["requester_email"],
                requester_phone=v["requester_phone"],
                subject_summary=v["subject_summary"],
                scope_details=self.txt_scope.get("1.0", "end").strip(),
                received_on=_parse_date(v["received_on"]),
                assigned_officer=v["assigned_officer"],
                actor=self.actor,
            )
        except InformationRightsError as exc:
            messagebox.showerror("Create request", str(exc))
            return
        messagebox.showinfo(
            "Created",
            f"{r['reference']} created.\nDeadline: {r['deadline_on']}",
        )
        for var in self.intake_vars.values():
            if var is self.intake_vars["request_type"]:
                continue
            var.set("")
        self.intake_vars["received_on"].set(date.today().isoformat())
        self.txt_scope.delete("1.0", "end")
        self.refresh_all()
        self._load_detail(r["request_id"])
        self.notebook.select(self.tab_detail)

    # ------------------------------------------------------- DETAIL tab
    def _build_detail(self, parent: ttk.Frame) -> None:
        top = ttk.Frame(parent)
        top.pack(fill="x", padx=8, pady=6)
        ttk.Label(top, text="Reference:").pack(side="left")
        self.var_lookup = tk.StringVar()
        ttk.Entry(top, textvariable=self.var_lookup, width=18) \
            .pack(side="left", padx=4)
        ttk.Button(top, text="Load",
                   command=self._load_by_ref).pack(side="left")

        self.lbl_detail = ttk.Label(parent, text="(no request loaded)",
                                    justify="left",
                                    font=("TkFixedFont", 10))
        self.lbl_detail.pack(fill="x", padx=8, pady=6)

        actions = ttk.Frame(parent)
        actions.pack(fill="x", padx=8, pady=4)
        ttk.Button(actions, text="Verify ID (SAR)",
                   command=self._action_verify_id).pack(side="left", padx=2)
        ttk.Button(actions, text="Apply 2-month extension",
                   command=self._action_extension).pack(side="left", padx=2)
        ttk.Button(actions, text="Change status",
                   command=self._action_status).pack(side="left", padx=2)
        ttk.Button(actions, text="Log communication",
                   command=self._action_comm).pack(side="left", padx=2)
        ttk.Button(actions, text="Apply exemption",
                   command=self._action_exemption).pack(side="left", padx=2)
        ttk.Button(actions, text="Log redaction",
                   command=self._action_redaction).pack(side="left", padx=2)
        ttk.Button(actions, text="Close request",
                   command=self._action_close).pack(side="left", padx=2)

        nb = ttk.Notebook(parent)
        nb.pack(fill="both", expand=True, padx=8, pady=6)
        self.tab_comms = ttk.Frame(nb)
        self.tab_exempts = ttk.Frame(nb)
        self.tab_redacts = ttk.Frame(nb)
        self.tab_audit = ttk.Frame(nb)
        nb.add(self.tab_comms, text="Communications")
        nb.add(self.tab_exempts, text="Exemptions")
        nb.add(self.tab_redacts, text="Redactions")
        nb.add(self.tab_audit, text="Audit log")

        self.tv_comms = self._tree(self.tab_comms,
                                   ("when", "dir", "channel", "summary"),
                                   (140, 80, 90, 600))
        self.tv_exempts = self._tree(self.tab_exempts,
                                     ("regime", "code", "label", "reason"),
                                     (60, 80, 220, 600))
        self.tv_redacts = self._tree(self.tab_redacts,
                                     ("doc", "page", "type", "rationale"),
                                     (200, 80, 140, 500))
        self.tv_audit = self._tree(self.tab_audit,
                                   ("when", "event", "actor", "detail"),
                                   (160, 140, 100, 500))

        self.current_request: Optional[dict] = None

    def _tree(self, parent, cols, widths) -> ttk.Treeview:
        tv = ttk.Treeview(parent, columns=cols, show="headings")
        for c, w in zip(cols, widths):
            tv.heading(c, text=c.title())
            tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=4, pady=4)
        return tv

    def _load_by_ref(self) -> None:
        ref = self.var_lookup.get().strip()
        if not ref:
            return
        try:
            r = self.svc.get_by_reference(ref)
        except InformationRightsError as e:
            messagebox.showerror("Load", str(e))
            return
        self._load_detail(r["request_id"])

    def _load_detail(self, request_id: str) -> None:
        try:
            r = self.svc.get_request(request_id)
        except InformationRightsError as e:
            messagebox.showerror("Load", str(e))
            return
        self.current_request = r
        self.var_lookup.set(r["reference"])
        days = self.svc.days_remaining(r)
        flag = "OVERDUE" if days < 0 else (
            "DUE-SOON" if days <= 7 else "on-track")
        self.lbl_detail.config(text=(
            f"{r['reference']}  [{r['request_type']}]   "
            f"status={r['status']}   id={r['identity_status']}\n"
            f"  requester: {r['requester_name']} <{r['requester_email']}>"
            f" {r.get('requester_phone') or ''}\n"
            f"  subject: {r['subject_summary']}\n"
            f"  scope:   {(r.get('scope_details') or '')[:200]}\n"
            f"  received: {r['received_on']}   "
            f"deadline: {r['deadline_on']} ({days:+}d) [{flag}]\n"
            f"  officer: {r.get('assigned_officer') or '—'}   "
            f"extended: {'YES' if r['extended'] else 'no'}"
            f"   outcome: {r.get('outcome') or '—'}"
        ))
        self._fill(self.tv_comms,
                   self.svc.list_communications(request_id),
                   ("occurred_at", "direction", "channel", "summary"))
        self._fill(self.tv_exempts,
                   self.svc.list_exemptions(request_id),
                   ("regime", "code", "label", "reason"))
        self._fill(self.tv_redacts,
                   self.svc.list_redactions(request_id),
                   ("document_ref", "page", "redaction_type", "rationale"))
        self._fill(self.tv_audit,
                   self.svc.list_audit(request_id),
                   ("occurred_at", "event", "actor", "detail"))

    def _fill(self, tv: ttk.Treeview, rows: list, fields) -> None:
        for i in tv.get_children():
            tv.delete(i)
        for r in rows:
            tv.insert("", "end",
                      values=tuple(r.get(f) or "" for f in fields))

    # --------------------------------------------------- detail actions
    def _need_request(self) -> Optional[dict]:
        if not self.current_request:
            messagebox.showinfo("Action", "Load a request first.")
            return None
        return self.current_request

    def _action_verify_id(self) -> None:
        r = self._need_request()
        if not r:
            return
        try:
            out = self.svc.mark_identity_verified(
                r["request_id"], actor=self.actor)
        except InformationRightsError as e:
            messagebox.showerror("Verify ID", str(e)); return
        messagebox.showinfo("Verify ID",
                            f"Clock restarted. New deadline: "
                            f"{out['deadline_on']}")
        self._load_detail(r["request_id"]); self.refresh_all()

    def _action_extension(self) -> None:
        r = self._need_request()
        if not r:
            return
        reason = _prompt(self.root, "Extension reason",
                         "Why is the extension necessary?\n"
                         "(complex / numerous, etc.)")
        if not reason:
            return
        try:
            out = self.svc.apply_extension(r["request_id"], reason,
                                           actor=self.actor)
        except InformationRightsError as e:
            messagebox.showerror("Extension", str(e)); return
        messagebox.showinfo(
            "Extension",
            f"Applied. New deadline: {out['deadline_on']}")
        self._load_detail(r["request_id"]); self.refresh_all()

    def _action_status(self) -> None:
        r = self._need_request()
        if not r:
            return
        new = _choose(self.root, "Change status",
                      "New status:", REQUEST_STATUSES)
        if not new:
            return
        note = _prompt(self.root, "Status note",
                       "Optional note:") or ""
        try:
            self.svc.set_status(r["request_id"], new, actor=self.actor,
                                note=note)
        except InformationRightsError as e:
            messagebox.showerror("Status", str(e)); return
        self._load_detail(r["request_id"]); self.refresh_all()

    def _action_comm(self) -> None:
        r = self._need_request()
        if not r:
            return
        direction = _choose(self.root, "Communication direction",
                            "Direction:",
                            ("inbound", "outbound", "internal"))
        if not direction:
            return
        channel = _prompt(self.root, "Channel",
                          "Channel (email/post/phone/portal):", "email")
        if not channel:
            return
        summary = _prompt(self.root, "Summary",
                          "One-line summary:")
        if not summary:
            return
        body = _prompt(self.root, "Body", "Body (optional):") or ""
        try:
            self.svc.log_communication(
                r["request_id"], direction, channel, summary, body,
                author=self.actor)
        except InformationRightsError as e:
            messagebox.showerror("Communication", str(e)); return
        self._load_detail(r["request_id"])

    def _action_exemption(self) -> None:
        r = self._need_request()
        if not r:
            return
        regime = _choose(self.root, "Regime",
                         "Statutory regime:", ("FOIA", "DPA", "EIR"))
        if not regime:
            return
        catalogue = {"FOIA": FOIA_EXEMPTIONS,
                     "DPA": DPA_EXEMPTIONS,
                     "EIR": EIR_EXCEPTIONS}[regime]
        opts = tuple(f"{c}: {l}" for c, l in catalogue.items())
        sel = _choose(self.root, "Exemption code",
                      f"{regime} exemption:", opts)
        if not sel:
            return
        code = sel.split(":", 1)[0]
        reason = _prompt(self.root, "Reason",
                         "Document the harm test / public-interest "
                         "balance / rationale:")
        if not reason:
            return
        try:
            self.svc.apply_exemption(r["request_id"], regime, code, reason,
                                     actor=self.actor)
        except InformationRightsError as e:
            messagebox.showerror("Exemption", str(e)); return
        self._load_detail(r["request_id"])

    def _action_redaction(self) -> None:
        r = self._need_request()
        if not r:
            return
        doc = _prompt(self.root, "Document",
                      "Document reference (file name / path):")
        if not doc:
            return
        page = _prompt(self.root, "Page", "Page (optional):") or ""
        location = _prompt(self.root, "Location",
                           "Location (e.g. 'para 3', optional):") or ""
        rtype = _choose(self.root, "Redaction type",
                        "Type:",
                        ("third_party_pii", "exempt_info",
                         "legally_privileged", "out_of_scope", "other"))
        if not rtype:
            return
        rationale = _prompt(self.root, "Rationale",
                            "Why was this redacted?")
        if not rationale:
            return
        try:
            self.svc.log_redaction(r["request_id"], doc, rtype, rationale,
                                   page=page, location=location,
                                   actor=self.actor)
        except InformationRightsError as e:
            messagebox.showerror("Redaction", str(e)); return
        self._load_detail(r["request_id"])

    def _action_close(self) -> None:
        r = self._need_request()
        if not r:
            return
        outcome = _choose(self.root, "Close request",
                          "Outcome:", OUTCOMES)
        if not outcome:
            return
        note = _prompt(self.root, "Closing note",
                       "Optional closing note:") or ""
        try:
            self.svc.close_request(r["request_id"], outcome,
                                   actor=self.actor, note=note)
        except InformationRightsError as e:
            messagebox.showerror("Close", str(e)); return
        self._load_detail(r["request_id"]); self.refresh_all()

    # --------------------------------------------------------- refresh
    def refresh_all(self) -> None:
        s = self.svc.dashboard_summary()
        self.lbl_summary.config(text=(
            f"As of {s['as_of']} — open: {s['total_open']}   "
            f"closed: {s['total_closed']}   "
            f"overdue: {s['overdue_count']}   "
            f"due within 7 days: {s['due_within_7_days']}\n"
            f"by type: {s['by_type']}\n"
            f"by status: {s['by_status']}"
        ))
        self._fill_tree(self.tv_overdue, s["overdue"])
        self._fill_tree(self.tv_due_soon, s["due_soon"])
        self._refresh_list()

    def run(self) -> None:
        self.root.mainloop()

    # =================================================================
    # Open-in bar + drill-throughs (mirror of QADashboardGUI)
    # =================================================================

    def _build_open_in_bar(self, parent) -> None:
        bar = ttk.Frame(parent, padding=(8, 4, 8, 0))
        bar.pack(fill="x")
        ttk.Label(bar, text="Open in:",
                  font=("TkDefaultFont", 9, "bold")).pack(side="left",
                                                          padx=(0, 6))
        for label, method in self._OPEN_IN_TARGETS:
            btn = ttk.Button(
                bar, text=label,
                command=lambda m=method, lab=label: self._open_in(m, lab),
            )
            btn.pack(side="left", padx=2)
            if not (self.app and hasattr(self.app, method)):
                btn.state(["disabled"])
        # Contextual drill buttons (operate on the currently selected
        # request — read in :func:`_selected_request`).
        ttk.Separator(bar, orient="vertical").pack(side="left",
                                                    padx=8, fill="y")
        ttk.Label(bar, text="Selected request:",
                  font=("TkDefaultFont", 9, "italic")).pack(side="left",
                                                            padx=(0, 4))
        for label, method in (
            ("Open subject", "drill_to_data_subject"),
            ("Audit log", "drill_to_audit_log"),
            ("Comms", "drill_to_communications"),
            ("Calendar", "drill_to_deadline_calendar"),
        ):
            ttk.Button(
                bar, text=label,
                command=getattr(self, method),
            ).pack(side="left", padx=2)

    def _open_in(self, method_name: str, label: str) -> None:
        self._dispatch_with_context(method_name, label, context=None)

    def _dispatch_with_context(self, method_name: str, label: str,
                                context: dict | None) -> None:
        """Stash ``context`` on ``app._last_academic_context`` then
        invoke the parent app's launcher. Same convention as EQA — the
        existing ``qa_receivers.consume_eqa_context`` bridge in each
        sibling launcher reads it transparently."""
        if not self.app:
            messagebox.showinfo(
                "Not available",
                "Cross-module navigation requires the main GUI; open "
                "this dashboard from the main menu rather than standalone.",
                parent=self.root,
            )
            return
        fn = getattr(self.app, method_name, None)
        if fn is None:
            messagebox.showwarning("Not available",
                                    f"{label} is not registered on this build.",
                                    parent=self.root)
            return
        try:
            self.app._last_academic_context = context
        except Exception:
            pass
        try:
            fn()
        except Exception as exc:
            messagebox.showerror("Failed to open",
                                  f"Could not open {label}: {exc}",
                                  parent=self.root)

    # ---- selection helpers ----
    def _selected_request(self) -> dict | None:
        """Resolve the request highlighted in the All-requests tree (or
        currently displayed in the detail tab) into a dict."""
        for tree_attr in ("tv_list", "tv_overdue", "tv_due_soon"):
            tree = getattr(self, tree_attr, None)
            if tree is None:
                continue
            sel = tree.selection()
            if not sel:
                continue
            try:
                vals = tree.item(sel[0])["values"]
                # First column is reference or id depending on tree
                # layout — try reference first, then id.
                ref = str(vals[0]) if vals else ""
                if ref:
                    try:
                        return self.svc.get_by_reference(ref)
                    except Exception:
                        try:
                            return self.svc.get_request(ref)
                        except Exception:
                            continue
            except Exception:
                continue
        # Fallback: detail tab may have a current request stashed
        cur = getattr(self, "_current_request", None)
        if isinstance(cur, dict):
            return cur
        return None

    def _require_request(self, action: str) -> dict | None:
        req = self._selected_request()
        if not req:
            messagebox.showinfo(
                "Pick a request",
                f"Select a request first to {action}.",
                parent=self.root,
            )
        return req

    # ---- six drill-throughs ----
    def drill_to_data_subject(self) -> dict | None:
        """#1 — Open Student Records for the data subject behind a
        SAR. Payload includes the SAR reference, request type, and
        any subject id captured at intake."""
        req = self._require_request("open the data subject")
        if not req:
            return None
        payload = {
            "source": "ir.request",
            "ir_reference": req.get("reference"),
            "request_type": req.get("request_type"),
            "subject_id": req.get("subject_id") or req.get("data_subject_id"),
            "subject_email": req.get("subject_email")
                              or req.get("data_subject_email"),
        }
        self._dispatch_with_context("show_student_records",
                                      "Student Records", payload)
        return payload

    def drill_to_audit_log(self) -> dict | None:
        """#2 — Open Security Dashboard filtered to ``ir.request_*``
        events for the selected request."""
        req = self._require_request("view its audit log")
        if not req:
            return None
        payload = {
            "source": "ir.request",
            "audit_action_prefix": "ir.request_",
            "resource_type": "ir",
            "resource_id": str(req.get("id") or req.get("reference")),
            "ir_reference": req.get("reference"),
        }
        self._dispatch_with_context("show_security_dashboard",
                                      "Security Dashboard", payload)
        return payload

    def drill_to_communications(self) -> dict | None:
        """#3 — Open Communication Hub focused on the request's comms
        thread."""
        req = self._require_request("open its communications thread")
        if not req:
            return None
        payload = {
            "source": "ir.request",
            "ir_reference": req.get("reference"),
            "request_type": req.get("request_type"),
            "thread_subject": f"IR {req.get('reference')}",
        }
        self._dispatch_with_context("show_communication_hub_gui",
                                      "Communication Hub", payload)
        return payload

    def drill_to_deadline_calendar(self) -> dict | None:
        """#4 — Open Cross-System Calendar focused on the request's
        statutory deadline."""
        req = self._require_request("show its deadline on the calendar")
        if not req:
            return None
        payload = {
            "source": "ir.request",
            "deadline_on": req.get("deadline_on"),
            "ir_reference": req.get("reference"),
            "request_type": req.get("request_type"),
        }
        self._dispatch_with_context("show_cross_system_calendar_gui",
                                      "Cross-System Calendar", payload)
        return payload

    def drill_to_documents(self) -> dict | None:
        """#5 — Open the Documents store for SAR redaction prep."""
        req = self._require_request("gather its documents")
        if not req:
            return None
        payload = {
            "source": "ir.request",
            "ir_reference": req.get("reference"),
            "subject_id": req.get("subject_id") or req.get("data_subject_id"),
            "purpose": "sar_gathering",
        }
        self._dispatch_with_context("show_data_documents_gui",
                                      "Documents", payload)
        return payload

    def drill_to_response_kpis(self) -> dict:
        """#6 — Open Business Intelligence with the IR KPI category."""
        payload = {"source": "ir.kpis",
                   "kpi_category": "information_rights"}
        self._dispatch_with_context("show_business_intelligence_gui",
                                      "Business Intel", payload)
        return payload

    # =================================================================
    # set_focus + register_open_in (mirror of EQA)
    # =================================================================

    def set_focus(self, reference: str | None = None,
                   tab: str | None = None,
                   request_id: int | None = None) -> None:
        """Programmatic focus API — switch tab and load a request.

        ``tab`` accepts ``"dashboard" | "list" | "intake" | "detail"``.
        ``reference`` (e.g. ``SAR-2026-0042``) loads the matching
        request into the detail tab.
        """
        try:
            tabs = {"dashboard": self.tab_dash, "list": self.tab_list,
                    "intake": self.tab_intake, "detail": self.tab_detail}
            if tab and tab in tabs:
                self.notebook.select(tabs[tab])
            if reference or request_id:
                req = None
                try:
                    if reference:
                        req = self.svc.get_by_reference(reference)
                    elif request_id:
                        req = self.svc.get_request(str(request_id))
                except Exception:
                    req = None
                if req:
                    self._current_request = req
                    fn = getattr(self, "_load_request_into_detail", None)
                    if callable(fn):
                        try:
                            fn(req)
                        except Exception:
                            pass
                    if not tab:
                        try:
                            self.notebook.select(self.tab_detail)
                        except Exception:
                            pass
        except Exception:
            pass

    @classmethod
    def register_open_in(cls, label: str, method_name: str,
                          replace: bool = False) -> None:
        """Extension point: append (or replace) a target on the IR
        Open-in bar. Idempotent on label."""
        new = list(cls._OPEN_IN_TARGETS)
        if replace:
            new = [(lab, m) for lab, m in new if lab != label]
        else:
            for lab, _ in new:
                if lab == label:
                    return
        new.append((label, method_name))
        cls._OPEN_IN_TARGETS = tuple(new)


# ----- small modal helpers (avoid pulling in a heavy dialog framework)

def _prompt(master, title: str, msg: str,
            default: str = "") -> Optional[str]:
    from tkinter.simpledialog import askstring
    return askstring(title, msg, initialvalue=default, parent=master)


def _choose(master, title: str, msg: str,
            options) -> Optional[str]:
    """Modal combobox picker."""
    win = tk.Toplevel(master)
    win.title(title)
    win.transient(master)
    win.grab_set()
    ttk.Label(win, text=msg).pack(padx=12, pady=(12, 4))
    var = tk.StringVar(value=options[0] if options else "")
    ttk.Combobox(win, textvariable=var, values=list(options),
                 state="readonly", width=40).pack(padx=12, pady=4)
    result: dict = {"v": None}

    def ok():
        result["v"] = var.get()
        win.destroy()

    def cancel():
        win.destroy()

    btns = ttk.Frame(win)
    btns.pack(pady=(4, 12))
    ttk.Button(btns, text="OK", command=ok).pack(side="left", padx=4)
    ttk.Button(btns, text="Cancel", command=cancel).pack(side="left", padx=4)
    win.wait_window()
    return result["v"]


def launch_information_rights_gui(actor: str = "gui") -> None:
    """Entrypoint used by the launcher / dispatch table."""
    app = InformationRightsGUI(actor=actor)
    app.run()


if __name__ == "__main__":  # pragma: no cover
    launch_information_rights_gui()
