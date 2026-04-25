"""Standalone Tk launcher for the KPI Dashboard."""
from __future__ import annotations

import sys, pathlib  # noqa: E401
_p = pathlib.Path(__file__).resolve()
while _p.parent != _p and not (_p / "education_system").is_dir():
    _p = _p.parent
if str(_p) not in sys.path:
    sys.path.insert(0, str(_p))

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from education_system.university_system.modules.domain.analytics.kpi_dashboard import (
    KpiDashboardService,
    KpiDashboardError,
)


class _Frame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg="#ecf0f1")
        self._svc = KpiDashboardService()
        self._build()
        self._refresh()

    def _build(self):
        hdr = tk.Frame(self, bg="#2c3e50", height=44)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="Institutional KPI Dashboard",
                 font=("Helvetica", 14, "bold"), bg="#2c3e50", fg="white").pack(
            side="left", padx=20, pady=8)

        ctrl = tk.Frame(self, bg="#ecf0f1"); ctrl.pack(fill="x", padx=10, pady=6)
        tk.Button(ctrl, text="Refresh KPIs", command=self._refresh).pack(side="left", padx=4)
        tk.Button(ctrl, text="Update KPI Actual", command=self._update_actual).pack(side="left", padx=4)
        tk.Button(ctrl, text="View Dashboard", command=self._view_dashboard).pack(side="left", padx=4)

        cols = ("id", "name", "category", "current", "target", "status", "progress%")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=14)
        for c in cols:
            self._tree.heading(c, text=c.title()); self._tree.column(c, width=110)
        self._tree.pack(fill="both", expand=True, padx=10, pady=8)

    def _refresh(self):
        for r in self._tree.get_children(): self._tree.delete(r)
        try:
            for k in self._svc.list_kpis():
                kid = k.get("kpi_id") or k.get("id")
                st = self._svc.kpi_status(kid)
                self._tree.insert("", "end", values=(
                    kid, k.get("name") or k.get("kpi_name", "-"),
                    k.get("kpi_category") or k.get("category", "-"),
                    k.get("current_value", "-"), k.get("target_value", "-"),
                    st.get("status", "-"),
                    f"{(st.get('progress') or 0) * 100:.1f}",
                ))
        except KpiDashboardError as e:
            messagebox.showerror("Error", str(e))

    def _update_actual(self):
        kid = simpledialog.askinteger("KPI", "KPI ID:", parent=self)
        if kid is None: return
        val = simpledialog.askfloat("KPI", "New current value:", parent=self)
        if val is None: return
        try:
            self._svc.update_kpi_actual(kid, val)
            self._refresh()
        except KpiDashboardError as e:
            messagebox.showerror("Error", str(e))

    def _view_dashboard(self):
        did = simpledialog.askinteger("Dashboard", "Dashboard ID:", parent=self)
        if did is None: return
        try:
            d = self._svc.get_dashboard(did)
        except KpiDashboardError as e:
            messagebox.showerror("Error", str(e)); return
        win = tk.Toplevel(self); win.title(f"Dashboard #{did}"); win.geometry("680x420")
        txt = tk.Text(win, wrap="word"); txt.pack(fill="both", expand=True, padx=10, pady=10)
        meta = d.get("dashboard") or d
        txt.insert("end", f"Dashboard: {meta.get('name', meta.get('dashboard_name','-'))}\n")
        txt.insert("end", f"Owner: {meta.get('owner_id','-')}\n\n")
        for w in d.get("widgets", []):
            kpi = w.get("resolved_kpi") or w.get("kpi")
            txt.insert("end", f"  • {w.get('title') or w.get('widget_name','widget')}\n")
            if kpi:
                txt.insert("end", f"      KPI {kpi.get('kpi_id') or kpi.get('id')}: "
                                  f"{kpi.get('current_value')} / {kpi.get('target_value')}\n")
        txt.config(state="disabled")


def main() -> None:
    root = tk.Tk()
    root.title("KPI Dashboard"); root.geometry("960x600")
    _Frame(root).pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()
