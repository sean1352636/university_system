"""Mitigating Circumstances (MC/EC) GUI."""

import logging
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

logger = logging.getLogger(__name__)


class MitigatingCircumstancesGUI:
    def __init__(self, parent=None):
        self.root = tk.Toplevel(parent) if parent else tk.Tk()
        self.root.title("Mitigating Circumstances (MC / EC)")
        self.root.geometry("1400x900")
        self.root.minsize(1200, 800)

        try:
            from education_system.university_system.modules.domain.academics.mitigating_circumstances.services.mitigating_circumstances_service import (
                MitigatingCircumstancesService,
            )
            self.service = MitigatingCircumstancesService()
        except Exception as e:
            logger.error(f"Service init error: {e}")
            self.service = None

        try:
            from education_system.university_system.infrastructure.shared_context import get_auth
            self.auth = get_auth()
        except Exception:
            self.auth = None

        self._username = ((self.auth.current_user or {}).get('username')
                          if self.auth and self.auth.current_user else 'unknown')

        self._build_ui()

    def _build_ui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self._build_claims_tab(notebook)
        self._build_evidence_tab(notebook)
        self._build_panels_tab(notebook)
        self._build_extensions_tab(notebook)
        self._build_stats_tab(notebook)

    # --------------------------------------------------------------- Claims
    def _build_claims_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Claims")

        cols = ("id", "student", "module", "assessment", "grounds", "status", "submitted")
        self.claims_tree = ttk.Treeview(tab, columns=cols, show="headings", height=20)
        widths = {"id": 50, "student": 100, "module": 100, "assessment": 120,
                  "grounds": 110, "status": 130, "submitted": 150}
        for c in cols:
            self.claims_tree.heading(c, text=c.replace("_", " ").title())
            self.claims_tree.column(c, width=widths.get(c, 120))
        self.claims_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        btns = ttk.Frame(tab)
        btns.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btns, text="Submit Claim", command=self._submit_claim).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="View / Update Status", command=self._view_claim).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Withdraw", command=self._withdraw_claim).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Refresh", command=self._refresh_claims).pack(side=tk.RIGHT, padx=2)

        self._refresh_claims()

    def _refresh_claims(self):
        for r in self.claims_tree.get_children():
            self.claims_tree.delete(r)
        if not self.service:
            return
        try:
            for c in self.service.list_claims():
                self.claims_tree.insert("", tk.END, values=(
                    c['id'], c['student_id'], c.get('module_code') or '',
                    c.get('assessment_ref') or '', c.get('grounds') or '',
                    c['status'], (c.get('submitted_at') or '')[:19],
                ))
        except Exception as e:
            logger.error(f"refresh claims: {e}")

    def _submit_claim(self):
        from education_system.university_system.modules.domain.academics.mitigating_circumstances.services.mitigating_circumstances_service import VALID_GROUNDS

        dlg = tk.Toplevel(self.root)
        dlg.title("Submit MC Claim")
        dlg.geometry("520x600")
        dlg.transient(self.root)
        dlg.grab_set()

        fields = [
            ("Student ID:", "student_id", "entry"),
            ("Module code:", "module_code", "entry"),
            ("Assessment ref:", "assessment_ref", "entry"),
            ("Grounds:", "grounds", "combo"),
            ("Period start (YYYY-MM-DD):", "period_start", "entry"),
            ("Period end (YYYY-MM-DD):", "period_end", "entry"),
            ("Requested remedy:", "requested_remedy", "entry"),
        ]
        vars_ = {}
        for label, key, kind in fields:
            ttk.Label(dlg, text=label).pack(padx=10, pady=(8, 0), anchor=tk.W)
            var = tk.StringVar()
            if kind == "combo":
                ttk.Combobox(dlg, textvariable=var, values=list(VALID_GROUNDS),
                             state="readonly").pack(fill=tk.X, padx=10)
            else:
                ttk.Entry(dlg, textvariable=var).pack(fill=tk.X, padx=10)
            vars_[key] = var

        ttk.Label(dlg, text="Description:").pack(padx=10, pady=(8, 0), anchor=tk.W)
        desc_text = tk.Text(dlg, height=4)
        desc_text.pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="Impact statement:").pack(padx=10, pady=(8, 0), anchor=tk.W)
        impact_text = tk.Text(dlg, height=4)
        impact_text.pack(fill=tk.X, padx=10)

        def save():
            data = {k: v.get() or None for k, v in vars_.items()}
            if not data.get('student_id'):
                messagebox.showwarning("Validation", "Student ID is required.", parent=dlg)
                return
            data['description'] = desc_text.get("1.0", tk.END).strip() or None
            data['impact_statement'] = impact_text.get("1.0", tk.END).strip() or None
            data['submitted_by'] = self._username
            try:
                cid = self.service.submit_claim(**data)
                dlg.destroy()
                self._refresh_claims()
                messagebox.showinfo("Submitted", f"Claim #{cid} submitted.", parent=self.root)
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Submit", command=save).pack(pady=12)

    def _selected_claim_id(self):
        sel = self.claims_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a claim first.", parent=self.root)
            return None
        return int(self.claims_tree.item(sel[0], "values")[0])

    def _view_claim(self):
        from education_system.university_system.modules.domain.academics.mitigating_circumstances.services.mitigating_circumstances_service import VALID_STATUSES

        cid = self._selected_claim_id()
        if not cid:
            return
        claim = self.service.get_claim(cid)
        if not claim:
            return

        dlg = tk.Toplevel(self.root)
        dlg.title(f"Claim #{cid}")
        dlg.geometry("520x500")
        dlg.transient(self.root)

        info = (
            f"Student:     {claim['student_id']}\n"
            f"Module:      {claim.get('module_code') or '-'}\n"
            f"Assessment:  {claim.get('assessment_ref') or '-'}\n"
            f"Grounds:     {claim.get('grounds') or '-'}\n"
            f"Period:      {claim.get('period_start') or '-'} → {claim.get('period_end') or '-'}\n"
            f"Submitted:   {claim.get('submitted_at') or '-'}\n\n"
            f"Description:\n{claim.get('description') or '-'}\n\n"
            f"Impact:\n{claim.get('impact_statement') or '-'}\n\n"
            f"Remedy:      {claim.get('requested_remedy') or '-'}"
        )
        text = tk.Text(dlg, height=20, wrap=tk.WORD)
        text.insert("1.0", info)
        text.config(state=tk.DISABLED)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        status_frame = ttk.Frame(dlg)
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(status_frame, text="Status:").pack(side=tk.LEFT)
        status_var = tk.StringVar(value=claim['status'])
        ttk.Combobox(status_frame, textvariable=status_var, values=list(VALID_STATUSES),
                     state="readonly").pack(side=tk.LEFT, padx=5)

        def update_status():
            try:
                self.service.update_claim_status(cid, status_var.get())
                self._refresh_claims()
                messagebox.showinfo("Updated", "Status updated.", parent=dlg)
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(status_frame, text="Update", command=update_status).pack(side=tk.LEFT, padx=5)

    def _withdraw_claim(self):
        cid = self._selected_claim_id()
        if not cid:
            return
        if not messagebox.askyesno("Withdraw", f"Withdraw claim #{cid}?", parent=self.root):
            return
        try:
            self.service.withdraw_claim(cid)
            self._refresh_claims()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.root)

    # ------------------------------------------------------------- Evidence
    def _build_evidence_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Evidence")

        top = ttk.Frame(tab)
        top.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(top, text="Claim ID:").pack(side=tk.LEFT)
        self.evidence_claim_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.evidence_claim_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text="Load", command=self._refresh_evidence).pack(side=tk.LEFT, padx=2)
        ttk.Button(top, text="Add Evidence", command=self._add_evidence).pack(side=tk.LEFT, padx=2)
        ttk.Button(top, text="Verify Selected", command=self._verify_evidence).pack(side=tk.LEFT, padx=2)

        cols = ("id", "type", "description", "document", "received", "verified", "verified_by")
        self.evidence_tree = ttk.Treeview(tab, columns=cols, show="headings", height=18)
        widths = {"id": 50, "type": 120, "description": 280, "document": 160,
                  "received": 100, "verified": 80, "verified_by": 120}
        for c in cols:
            self.evidence_tree.heading(c, text=c.replace("_", " ").title())
            self.evidence_tree.column(c, width=widths.get(c, 120))
        self.evidence_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _refresh_evidence(self):
        for r in self.evidence_tree.get_children():
            self.evidence_tree.delete(r)
        cid_str = self.evidence_claim_var.get().strip()
        if not cid_str or not self.service:
            return
        try:
            cid = int(cid_str)
        except ValueError:
            messagebox.showwarning("Validation", "Claim ID must be numeric.", parent=self.root)
            return
        try:
            for e in self.service.list_evidence(cid):
                self.evidence_tree.insert("", tk.END, values=(
                    e['id'], e.get('evidence_type') or '', e.get('description') or '',
                    e.get('document_ref') or '', e.get('received_date') or '',
                    'Yes' if e.get('verified') else 'No', e.get('verified_by') or '',
                ))
        except Exception as e:
            logger.error(f"refresh evidence: {e}")

    def _add_evidence(self):
        cid_str = self.evidence_claim_var.get().strip()
        if not cid_str:
            messagebox.showwarning("Validation", "Enter a Claim ID first.", parent=self.root)
            return
        try:
            cid = int(cid_str)
        except ValueError:
            return

        dlg = tk.Toplevel(self.root)
        dlg.title(f"Add Evidence (claim #{cid})")
        dlg.geometry("440x320")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text="Type:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        type_var = tk.StringVar(value="medical_letter")
        ttk.Combobox(dlg, textvariable=type_var, values=[
            "medical_letter", "death_certificate", "police_report",
            "email_correspondence", "screenshot", "other",
        ]).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="Description:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        desc_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=desc_var).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="Document ref / path:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        doc_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=doc_var).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="Received (YYYY-MM-DD):").pack(padx=10, pady=(10, 0), anchor=tk.W)
        recv_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(dlg, textvariable=recv_var).pack(fill=tk.X, padx=10)

        def save():
            try:
                self.service.add_evidence(
                    claim_id=cid, evidence_type=type_var.get(),
                    description=desc_var.get(), document_ref=doc_var.get() or None,
                    received_date=recv_var.get() or None,
                )
                dlg.destroy()
                self._refresh_evidence()
                self._refresh_claims()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Save", command=save).pack(pady=12)

    def _verify_evidence(self):
        sel = self.evidence_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select an evidence row.", parent=self.root)
            return
        eid = int(self.evidence_tree.item(sel[0], "values")[0])
        try:
            self.service.verify_evidence(eid, verified_by=self._username, verified=True)
            self._refresh_evidence()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.root)

    # --------------------------------------------------------------- Panels
    def _build_panels_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Panels")

        left = ttk.Frame(tab)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        cols = ("id", "panel_date", "chair", "status")
        self.panels_tree = ttk.Treeview(left, columns=cols, show="headings", height=20)
        for c in cols:
            self.panels_tree.heading(c, text=c.replace("_", " ").title())
            self.panels_tree.column(c, width=120)
        self.panels_tree.pack(fill=tk.BOTH, expand=True)
        self.panels_tree.bind("<<TreeviewSelect>>", lambda _e: self._refresh_panel_items())

        btns = ttk.Frame(left)
        btns.pack(fill=tk.X, pady=4)
        ttk.Button(btns, text="Schedule Panel", command=self._schedule_panel).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Close Panel", command=self._close_panel).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Refresh", command=self._refresh_panels).pack(side=tk.RIGHT, padx=2)

        right = ttk.Frame(tab)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        ttk.Label(right, text="Panel Items / Decisions").pack(anchor=tk.W)
        cols2 = ("id", "claim", "student", "module", "decision", "outcome")
        self.panel_items_tree = ttk.Treeview(right, columns=cols2, show="headings", height=20)
        for c in cols2:
            self.panel_items_tree.heading(c, text=c.replace("_", " ").title())
            self.panel_items_tree.column(c, width=110)
        self.panel_items_tree.pack(fill=tk.BOTH, expand=True)

        btns2 = ttk.Frame(right)
        btns2.pack(fill=tk.X, pady=4)
        ttk.Button(btns2, text="Assign Claim", command=self._assign_claim).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns2, text="Record Decision", command=self._record_decision).pack(side=tk.LEFT, padx=2)

        self._refresh_panels()

    def _refresh_panels(self):
        for r in self.panels_tree.get_children():
            self.panels_tree.delete(r)
        if not self.service:
            return
        for p in self.service.list_panels():
            self.panels_tree.insert("", tk.END, values=(
                p['id'], p.get('panel_date') or '', p.get('chair') or '', p.get('status') or '',
            ))

    def _selected_panel_id(self):
        sel = self.panels_tree.selection()
        if not sel:
            return None
        return int(self.panels_tree.item(sel[0], "values")[0])

    def _refresh_panel_items(self):
        for r in self.panel_items_tree.get_children():
            self.panel_items_tree.delete(r)
        pid = self._selected_panel_id()
        if not pid or not self.service:
            return
        for it in self.service.get_panel_items(pid):
            self.panel_items_tree.insert("", tk.END, values=(
                it['id'], it['claim_id'], it.get('student_id') or '',
                it.get('module_code') or '', it.get('decision') or '',
                it.get('outcome') or '',
            ))

    def _schedule_panel(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Schedule Panel")
        dlg.geometry("400x320")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text="Date (YYYY-MM-DD):").pack(padx=10, pady=(10, 0), anchor=tk.W)
        date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(dlg, textvariable=date_var).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="Chair:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        chair_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=chair_var).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="Members (comma separated):").pack(padx=10, pady=(10, 0), anchor=tk.W)
        members_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=members_var).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="Location:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        loc_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=loc_var).pack(fill=tk.X, padx=10)

        def save():
            try:
                self.service.schedule_panel(
                    date_var.get(), chair_var.get() or None,
                    members_var.get() or None, loc_var.get() or None,
                )
                dlg.destroy()
                self._refresh_panels()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Save", command=save).pack(pady=12)

    def _close_panel(self):
        pid = self._selected_panel_id()
        if not pid:
            messagebox.showwarning("Selection", "Select a panel.", parent=self.root)
            return
        try:
            self.service.close_panel(pid)
            self._refresh_panels()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.root)

    def _assign_claim(self):
        pid = self._selected_panel_id()
        if not pid:
            messagebox.showwarning("Selection", "Select a panel first.", parent=self.root)
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("Assign Claim to Panel")
        dlg.geometry("320x150")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text=f"Panel #{pid} — Claim ID:").pack(padx=10, pady=10, anchor=tk.W)
        cid_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=cid_var).pack(fill=tk.X, padx=10)

        def save():
            try:
                self.service.assign_claim_to_panel(pid, int(cid_var.get()))
                dlg.destroy()
                self._refresh_panel_items()
                self._refresh_claims()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Assign", command=save).pack(pady=10)

    def _record_decision(self):
        from education_system.university_system.modules.domain.academics.mitigating_circumstances.services.mitigating_circumstances_service import VALID_OUTCOMES

        pid = self._selected_panel_id()
        sel = self.panel_items_tree.selection()
        if not pid or not sel:
            messagebox.showwarning("Selection", "Select a panel and a claim row.", parent=self.root)
            return
        item_values = self.panel_items_tree.item(sel[0], "values")
        cid = int(item_values[1])

        dlg = tk.Toplevel(self.root)
        dlg.title(f"Decision (panel {pid}, claim {cid})")
        dlg.geometry("420x360")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text="Decision:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        decision_var = tk.StringVar(value="approved")
        ttk.Combobox(dlg, textvariable=decision_var,
                     values=["approved", "rejected", "deferred"],
                     state="readonly").pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="Outcome:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        outcome_var = tk.StringVar(value="extension_granted")
        ttk.Combobox(dlg, textvariable=outcome_var, values=list(VALID_OUTCOMES),
                     state="readonly").pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="Rationale:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        rationale_text = tk.Text(dlg, height=6)
        rationale_text.pack(fill=tk.BOTH, padx=10, expand=True)

        def save():
            try:
                self.service.record_panel_decision(
                    pid, cid, decision_var.get(), outcome_var.get(),
                    rationale_text.get("1.0", tk.END).strip() or None,
                )
                dlg.destroy()
                self._refresh_panel_items()
                self._refresh_claims()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Save", command=save).pack(pady=10)

    # ----------------------------------------------------------- Extensions
    def _build_extensions_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Extensions")

        cols = ("id", "claim", "student", "module", "assessment",
                "original", "new", "days", "applied", "granted_by")
        self.ext_tree = ttk.Treeview(tab, columns=cols, show="headings", height=20)
        widths = {"id": 50, "claim": 60, "student": 100, "module": 100,
                  "assessment": 110, "original": 100, "new": 100,
                  "days": 60, "applied": 70, "granted_by": 110}
        for c in cols:
            self.ext_tree.heading(c, text=c.replace("_", " ").title())
            self.ext_tree.column(c, width=widths.get(c, 110))
        self.ext_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        btns = ttk.Frame(tab)
        btns.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btns, text="Grant Extension", command=self._grant_extension).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Mark Applied", command=self._mark_applied).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Refresh", command=self._refresh_extensions).pack(side=tk.RIGHT, padx=2)

        self._refresh_extensions()

    def _refresh_extensions(self):
        for r in self.ext_tree.get_children():
            self.ext_tree.delete(r)
        if not self.service:
            return
        for ex in self.service.list_extensions():
            self.ext_tree.insert("", tk.END, values=(
                ex['id'], ex['claim_id'], ex['student_id'],
                ex.get('module_code') or '', ex.get('assessment_ref') or '',
                ex.get('original_deadline') or '', ex.get('new_deadline') or '',
                ex.get('extension_days') or 0,
                'Yes' if ex.get('applied') else 'No',
                ex.get('granted_by') or '',
            ))

    def _grant_extension(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Grant Deadline Extension")
        dlg.geometry("440x380")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text="Claim ID:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        cid_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=cid_var).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="Original deadline (YYYY-MM-DD):").pack(padx=10, pady=(10, 0), anchor=tk.W)
        orig_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=orig_var).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="Extension days:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        days_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=days_var).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="…or new deadline (YYYY-MM-DD):").pack(padx=10, pady=(10, 0), anchor=tk.W)
        new_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=new_var).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="Reason:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        reason_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=reason_var).pack(fill=tk.X, padx=10)

        def save():
            try:
                days = int(days_var.get()) if days_var.get().strip() else None
                self.service.grant_extension(
                    claim_id=int(cid_var.get()),
                    original_deadline=orig_var.get(),
                    extension_days=days,
                    new_deadline=new_var.get() or None,
                    granted_by=self._username,
                    reason=reason_var.get() or None,
                )
                dlg.destroy()
                self._refresh_extensions()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Grant", command=save).pack(pady=12)

    def _mark_applied(self):
        sel = self.ext_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select an extension row.", parent=self.root)
            return
        ext_id = int(self.ext_tree.item(sel[0], "values")[0])
        try:
            self.service.mark_extension_applied(ext_id)
            self._refresh_extensions()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.root)

    # ---------------------------------------------------------------- Stats
    def _build_stats_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Statistics")

        self.stats_text = tk.Text(tab, wrap=tk.WORD, height=30)
        self.stats_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Button(tab, text="Refresh", command=self._refresh_stats).pack(pady=5)
        self._refresh_stats()

    def _refresh_stats(self):
        if not self.service:
            return
        try:
            stats = self.service.claim_statistics()
        except Exception as e:
            self.stats_text.delete("1.0", tk.END)
            self.stats_text.insert("1.0", f"Error: {e}")
            return
        lines = [
            f"Total claims:        {stats['total_claims']}",
            f"Extensions granted:  {stats['extensions_granted']}",
            "",
            "By status:",
        ]
        for k, v in (stats.get('by_status') or {}).items():
            lines.append(f"  {k:<22} {v}")
        lines.append("")
        lines.append("By grounds:")
        for k, v in (stats.get('by_grounds') or {}).items():
            lines.append(f"  {(k or 'unknown'):<22} {v}")
        self.stats_text.delete("1.0", tk.END)
        self.stats_text.insert("1.0", "\n".join(lines))


def main():
    root = tk.Tk()
    root.withdraw()
    MitigatingCircumstancesGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
