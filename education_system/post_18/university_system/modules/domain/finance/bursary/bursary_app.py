"""Standalone Tk launcher for Bursary Management."""
from __future__ import annotations

import sys, pathlib  # noqa: E401
_p = pathlib.Path(__file__).resolve()
while _p.parent != _p and not (_p / "education_system").is_dir():
    _p = _p.parent
if str(_p) not in sys.path:
    sys.path.insert(0, str(_p))

import logging

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from education_system.post_18.university_system.modules.domain.finance.bursary import (
    BursaryService,
    BursaryError,
)

try:
    from education_system.post_18.university_system.infrastructure.logging.log_config import configure_logging
    logger = configure_logging(name=__name__)
except ImportError:
    logger = logging.getLogger(__name__)


class _Frame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg="#ecf0f1")
        logger.info("Opening Bursary Management UI")
        self._svc = BursaryService()
        self._build()
        self._refresh_funds(); self._refresh_apps()

    def _build(self):
        hdr = tk.Frame(self, bg="#2c3e50", height=44)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="Bursary Management",
                 font=("Helvetica", 14, "bold"), bg="#2c3e50", fg="white").pack(
            side="left", padx=20, pady=8)

        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True, padx=10, pady=8)

        # Funds tab
        ft = tk.Frame(nb, bg="#ecf0f1"); nb.add(ft, text="Funds")
        ctrl = tk.Frame(ft, bg="#ecf0f1"); ctrl.pack(fill="x", pady=4)
        tk.Button(ctrl, text="Create Fund", command=self._create_fund).pack(side="left", padx=4)
        tk.Button(ctrl, text="Update Budget", command=self._update_budget).pack(side="left", padx=4)
        tk.Button(ctrl, text="Refresh", command=self._refresh_funds).pack(side="left", padx=4)
        cols = ("id", "name", "type", "budget", "allocated", "status")
        self._funds = ttk.Treeview(ft, columns=cols, show="headings", height=10)
        for c in cols: self._funds.heading(c, text=c.title()); self._funds.column(c, width=120)
        self._funds.pack(fill="both", expand=True, padx=4, pady=4)

        # Applications tab
        at = tk.Frame(nb, bg="#ecf0f1"); nb.add(at, text="Applications")
        ctrl = tk.Frame(at, bg="#ecf0f1"); ctrl.pack(fill="x", pady=4)
        tk.Button(ctrl, text="Submit Application", command=self._submit).pack(side="left", padx=4)
        tk.Button(ctrl, text="Approve", command=lambda: self._set_status("approved")).pack(side="left", padx=4)
        tk.Button(ctrl, text="Reject", command=lambda: self._set_status("rejected")).pack(side="left", padx=4)
        tk.Button(ctrl, text="Set Status", command=self._set_status_custom).pack(side="left", padx=4)
        tk.Button(ctrl, text="Award", command=self._award).pack(side="left", padx=4)
        tk.Button(ctrl, text="Refresh", command=self._refresh_apps).pack(side="left", padx=4)
        cols = ("id", "student", "fund", "requested", "status", "decided_at")
        self._apps = ttk.Treeview(at, columns=cols, show="headings", height=12)
        for c in cols: self._apps.heading(c, text=c.title()); self._apps.column(c, width=120)
        self._apps.pack(fill="both", expand=True, padx=4, pady=4)

        # Evidence controls (second row)
        ectrl = tk.Frame(at, bg="#ecf0f1"); ectrl.pack(fill="x", pady=4)
        tk.Button(ectrl, text="Add Evidence", command=self._add_evidence).pack(side="left", padx=4)
        tk.Button(ectrl, text="Verify Evidence", command=self._verify_evidence).pack(side="left", padx=4)
        tk.Button(ectrl, text="List Evidence", command=self._list_evidence).pack(side="left", padx=4)
        tk.Button(ectrl, text="Summary", command=self._application_summary).pack(side="left", padx=4)

        # Payments tab
        pt = tk.Frame(nb, bg="#ecf0f1"); nb.add(pt, text="Payments")
        ctrl = tk.Frame(pt, bg="#ecf0f1"); ctrl.pack(fill="x", pady=4)
        tk.Button(ctrl, text="Payment Schedule", command=self._payment_schedule).pack(side="left", padx=4)
        tk.Button(ctrl, text="Mark Payment Paid", command=self._mark_payment_paid).pack(side="left", padx=4)
        cols = ("id", "scheduled", "amount", "status", "paid", "reference")
        self._pays = ttk.Treeview(pt, columns=cols, show="headings", height=12)
        for c in cols: self._pays.heading(c, text=c.title()); self._pays.column(c, width=120)
        self._pays.pack(fill="both", expand=True, padx=4, pady=4)

    def _refresh_funds(self):
        for r in self._funds.get_children(): self._funds.delete(r)
        try:
            for f in self._svc.list_funds():
                self._funds.insert("", "end", values=(
                    f["fund_id"], f.get("name"), f.get("fund_type"),
                    f.get("total_budget"), f.get("allocated"), f.get("status"),
                ))
        except BursaryError as e:
            logger.warning("Bursary GUI action failed: %s", e)
            messagebox.showerror("Error", str(e))

    def _refresh_apps(self):
        for r in self._apps.get_children(): self._apps.delete(r)
        try:
            for a in self._svc.list_applications():
                self._apps.insert("", "end", values=(
                    a["application_id"], a.get("student_id"), a.get("fund_id"),
                    a.get("requested_amount"), a.get("status"), a.get("decided_at", "-"),
                ))
        except BursaryError as e:
            logger.warning("Bursary GUI action failed: %s", e)
            messagebox.showerror("Error", str(e))

    def _create_fund(self):
        name = simpledialog.askstring("Fund", "Fund name:", parent=self)
        if not name: return
        ftype = simpledialog.askstring("Fund", "Type (hardship/maintenance/scholarship/emergency):",
                                       initialvalue="hardship", parent=self) or "hardship"
        budget = simpledialog.askfloat("Fund", "Total budget:", parent=self)
        if budget is None: return
        try:
            self._svc.create_fund(name, ftype, budget); self._refresh_funds()
        except BursaryError as e:
            logger.warning("Bursary GUI action failed: %s", e)
            messagebox.showerror("Error", str(e))

    def _submit(self):
        sid = simpledialog.askstring("Application", "Student ID:", parent=self)
        if not sid: return
        fid = simpledialog.askinteger("Application", "Fund ID:", parent=self)
        amt = simpledialog.askfloat("Application", "Requested amount:", parent=self)
        if fid is None or amt is None: return
        try:
            self._svc.submit_application(sid, fid, amt); self._refresh_apps()
        except BursaryError as e:
            logger.warning("Bursary GUI action failed: %s", e)
            messagebox.showerror("Error", str(e))

    def _selected_app_id(self) -> int | None:
        sel = self._apps.focus()
        if not sel: messagebox.showwarning("Select", "Select an application first."); return None
        return int(self._apps.item(sel, "values")[0])

    def _set_status(self, status):
        aid = self._selected_app_id()
        if aid is None: return
        try:
            self._svc.update_application_status(aid, status); self._refresh_apps()
        except BursaryError as e:
            logger.warning("Bursary GUI action failed: %s", e)
            messagebox.showerror("Error", str(e))

    def _award(self):
        aid = self._selected_app_id()
        if aid is None: return
        amt = simpledialog.askfloat("Award", "Amount:", parent=self)
        freq = simpledialog.askstring("Award", "Frequency (one_off/weekly/monthly/termly):",
                                      initialvalue="monthly", parent=self) or "monthly"
        n = simpledialog.askinteger("Award", "Number of payments:", initialvalue=6, parent=self)
        start = simpledialog.askstring("Award", "Start date YYYY-MM-DD:", parent=self)
        if amt is None or n is None or not start: return
        try:
            self._svc.award_bursary(aid, amt, freq, n, start)
            messagebox.showinfo("OK", "Award created."); self._refresh_funds(); self._refresh_apps()
        except BursaryError as e:
            logger.warning("Bursary GUI action failed: %s", e)
            messagebox.showerror("Error", str(e))

    def _selected_fund_id(self) -> int | None:
        sel = self._funds.focus()
        if not sel: messagebox.showwarning("Select", "Select a fund first."); return None
        return int(self._funds.item(sel, "values")[0])

    def _update_budget(self):
        fid = self._selected_fund_id()
        if fid is None: return
        budget = simpledialog.askfloat("Update Budget", "New total budget:", parent=self)
        if budget is None: return
        try:
            self._svc.update_fund_budget(fid, budget); self._refresh_funds()
        except BursaryError as e:
            logger.warning("Bursary GUI action failed: %s", e)
            messagebox.showerror("Error", str(e))

    def _set_status_custom(self):
        aid = self._selected_app_id()
        if aid is None: return
        status = simpledialog.askstring(
            "Set Status",
            "Status (submitted/under_review/approved/rejected/awarded):",
            parent=self,
        )
        if not status: return
        notes = simpledialog.askstring("Set Status", "Decision notes (blank=none):", parent=self)
        try:
            self._svc.update_application_status(aid, status.strip(), decision_notes=notes or None)
            self._refresh_apps()
        except BursaryError as e:
            logger.warning("Bursary GUI action failed: %s", e)
            messagebox.showerror("Error", str(e))

    def _add_evidence(self):
        aid = self._selected_app_id()
        if aid is None: return
        etype = simpledialog.askstring("Add Evidence", "Evidence type (e.g. payslip/bank_statement):", parent=self)
        if not etype: return
        filename = simpledialog.askstring("Add Evidence", "Filename (blank=none):", parent=self) or ""
        desc = simpledialog.askstring("Add Evidence", "Description (blank=none):", parent=self) or ""
        try:
            eid = self._svc.add_evidence(aid, etype, filename=filename, description=desc)
            messagebox.showinfo("OK", f"Evidence #{eid} added.")
        except BursaryError as e:
            logger.warning("Bursary GUI action failed: %s", e)
            messagebox.showerror("Error", str(e))

    def _verify_evidence(self):
        eid = simpledialog.askinteger("Verify Evidence", "Evidence ID:", parent=self)
        if eid is None: return
        verifier = simpledialog.askstring("Verify Evidence", "Verified by (your name/role):", parent=self)
        if not verifier: return
        try:
            self._svc.verify_evidence(eid, verifier)
            messagebox.showinfo("OK", "Evidence verified.")
        except BursaryError as e:
            logger.warning("Bursary GUI action failed: %s", e)
            messagebox.showerror("Error", str(e))

    def _list_evidence(self):
        aid = self._selected_app_id()
        if aid is None: return
        try:
            rows = self._svc.list_evidence(aid)
        except BursaryError as e:
            logger.warning("Bursary GUI action failed: %s", e)
            messagebox.showerror("Error", str(e)); return
        if not rows:
            messagebox.showinfo("Evidence", "No evidence found."); return
        lines = [
            f"#{r['evidence_id']} {r.get('evidence_type') or '-'} "
            f"{'[verified]' if r.get('verified') else '[unverified]'} "
            f"{r.get('filename') or '-'}"
            for r in rows
        ]
        messagebox.showinfo(f"Evidence for application #{aid}", "\n".join(lines))

    def _mark_payment_paid(self):
        pid = simpledialog.askinteger("Mark Payment Paid", "Payment ID:", parent=self)
        if pid is None: return
        ref = simpledialog.askstring("Mark Payment Paid", "Payment reference:", parent=self)
        if not ref: return
        try:
            self._svc.mark_payment_paid(pid, ref)
            messagebox.showinfo("OK", "Payment marked as paid.")
        except BursaryError as e:
            logger.warning("Bursary GUI action failed: %s", e)
            messagebox.showerror("Error", str(e))

    def _payment_schedule(self):
        award_id = simpledialog.askinteger("Payment Schedule", "Award ID:", parent=self)
        if award_id is None: return
        for r in self._pays.get_children(): self._pays.delete(r)
        try:
            rows = self._svc.get_payment_schedule(award_id)
        except BursaryError as e:
            logger.warning("Bursary GUI action failed: %s", e)
            messagebox.showerror("Error", str(e)); return
        for r in rows:
            self._pays.insert("", "end", values=(
                r["payment_id"], r.get("scheduled_date"), r.get("amount"),
                r.get("status"), r.get("paid_date", "-"), r.get("reference", "-"),
            ))

    def _application_summary(self):
        aid = self._selected_app_id()
        if aid is None: return
        try:
            s = self._svc.get_application_summary(aid)
        except BursaryError as e:
            logger.warning("Bursary GUI action failed: %s", e)
            messagebox.showerror("Error", str(e)); return

        app = s["application"]; fund = s["fund"]; award = s["award"]
        lines = [
            f"Application #{app['application_id']}",
            f"  Student:   {app['student_id']}",
            f"  Fund:      {fund['name']} ({fund['fund_type']})",
            f"  Requested: {app.get('requested_amount', 0):.2f}",
            f"  Status:    {app.get('status')}",
            f"  Submitted: {app.get('submitted_at')}",
            f"  Decision:  {app.get('decision_notes') or '-'}",
            "",
            f"Evidence ({len(s['evidence'])} items):",
        ]
        for e in s["evidence"]:
            flag = "[verified]" if e.get("verified") else "[unverified]"
            lines.append(f"  - #{e['evidence_id']} {e['evidence_type']} {flag}")
        if award:
            lines += [
                "",
                f"Award #{award['award_id']}: {award['awarded_amount']:.2f} "
                f"({award['payment_frequency']}, {award['num_payments']} payments)",
                f"  {award['start_date']} -> {award['end_date']}  status={award['status']}",
                "",
                f"Payments ({len(s['payments'])}):",
            ]
            for p in s["payments"]:
                ref = f"  ref={p['reference']}" if p.get("reference") else ""
                lines.append(f"  #{p['payment_id']} {p['scheduled_date']}  "
                             f"{p['amount']:.2f}  {p['status']}{ref}")
        else:
            lines += ["", "No award yet."]

        dlg = tk.Toplevel(self)
        dlg.title(f"Application #{aid} Summary")
        dlg.geometry("480x460")
        txt = tk.Text(dlg, wrap="word")
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        txt.insert("1.0", "\n".join(lines))
        txt.configure(state="disabled")
        tk.Button(dlg, text="Close", command=dlg.destroy).pack(pady=6)


def main() -> None:
    root = tk.Tk()
    root.title("Bursary Management"); root.geometry("980x620")
    _Frame(root).pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()
