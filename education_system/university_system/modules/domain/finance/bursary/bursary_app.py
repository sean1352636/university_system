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

from education_system.university_system.modules.domain.finance.bursary import (
    BursaryService,
    BursaryError,
)

try:
    from education_system.university_system.infrastructure.logging.log_config import configure_logging
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
        tk.Button(ctrl, text="Award", command=self._award).pack(side="left", padx=4)
        tk.Button(ctrl, text="Refresh", command=self._refresh_apps).pack(side="left", padx=4)
        cols = ("id", "student", "fund", "requested", "status", "decided_at")
        self._apps = ttk.Treeview(at, columns=cols, show="headings", height=12)
        for c in cols: self._apps.heading(c, text=c.title()); self._apps.column(c, width=120)
        self._apps.pack(fill="both", expand=True, padx=4, pady=4)

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


def main() -> None:
    root = tk.Tk()
    root.title("Bursary Management"); root.geometry("980x620")
    _Frame(root).pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()
