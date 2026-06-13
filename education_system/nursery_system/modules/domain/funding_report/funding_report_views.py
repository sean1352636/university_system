"""Tkinter view for the Funding Report (Nursery System).

Renders into the shared content pane of ``main_gui.NurseryMainGUI`` (the
``host``): a headline summary line, a claims-detail tree (submitted rows green,
drafts amber), a small entitlement-breakdown tree and Refresh / Export-CSV
buttons. Read-only.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from education_system.nursery_system.modules.domain.funding_report import (
    funding_report as data,
)

logger = logging.getLogger(__name__)


def _money(amount: float) -> str:
    return f"£{amount:,.2f}"


def open_funding_report_window(host) -> None:
    """Open the Funding Report in the GUI host's content pane."""
    try:
        host._clear_content()
        root = host.content_frame
        ttk.Label(root, text="Funding Report",
                  font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))

        summary = ttk.Label(root, foreground="#555")
        summary.pack(anchor="w", pady=(0, 6))

        bar = ttk.Frame(root)
        bar.pack(fill="x", pady=(0, 8))

        # Claims detail tree
        ttk.Label(root, text="Claims", font=("", 11, "bold")).pack(anchor="w")
        cols = ("child", "period", "entitlement", "hours", "weeks", "rate",
                "amount", "status")
        tree = ttk.Treeview(root, columns=cols, show="headings", height=12)
        for c, label, w, anchor in [
            ("child", "Child", 160, "w"), ("period", "Period", 110, "w"),
            ("entitlement", "Entitlement", 150, "w"), ("hours", "Hours", 70, "e"),
            ("weeks", "Weeks", 60, "e"), ("rate", "Rate", 80, "e"),
            ("amount", "Amount", 110, "e"), ("status", "Status", 100, "w"),
        ]:
            tree.heading(c, text=label)
            tree.column(c, width=w, anchor=anchor)
        tree.tag_configure("submitted", foreground="#1e7e34")
        tree.tag_configure("draft", foreground="#b9770e")
        tree.pack(fill="both", expand=True, pady=(2, 8))

        # Entitlement breakdown tree
        ttk.Label(root, text="Entitlement breakdown",
                  font=("", 11, "bold")).pack(anchor="w")
        ecols = ("entitlement", "children", "funded", "additional")
        etree = ttk.Treeview(root, columns=ecols, show="headings", height=5)
        for c, label, w, anchor in [
            ("entitlement", "Entitlement", 220, "w"),
            ("children", "Children", 90, "e"),
            ("funded", "Funded h/pw", 110, "e"),
            ("additional", "Additional h/pw", 130, "e"),
        ]:
            etree.heading(c, text=label)
            etree.column(c, width=w, anchor=anchor)
        etree.pack(fill="x", pady=(2, 0))

        ttk.Button(bar, text="Refresh",
                   command=lambda: _refresh(tree, etree, summary)
                   ).pack(side="left", padx=2)
        ttk.Button(bar, text="Export CSV",
                   command=lambda: _export(host)).pack(side="left", padx=2)

        _refresh(tree, etree, summary)
        host.status_var.set("Funding report loaded")
    except Exception:
        logger.exception("open_funding_report_window failed")
        try:
            messagebox.showerror(
                "Funding Report",
                "Could not open the Funding Report — see logs for details.",
                parent=getattr(host, "root", None))
        except Exception:
            logger.debug("Could not show error dialog", exc_info=True)


def _refresh(tree: ttk.Treeview, etree: ttk.Treeview,
             summary: ttk.Label) -> None:
    for i in tree.get_children():
        tree.delete(i)
    for i in etree.get_children():
        etree.delete(i)
    try:
        claims = data.list_claims()
        ents = data.entitlement_breakdown()
        s = data.summary()
    except Exception:
        logger.exception("Could not refresh funding report")
        messagebox.showerror("Funding Report", "Could not load — see logs.")
        return
    for c in claims:
        tag = c.status if c.status in ("submitted", "draft") else ""
        tree.insert("", "end", tags=(tag,), values=(
            c.pupil_name, c.funding_period or "-", c.entitlement or "-",
            f"{c.funded_hours:.1f}", f"{c.weeks:.0f}",
            _money(c.hourly_rate), _money(c.claim_amount), c.status))
    for e in ents:
        etree.insert("", "end", values=(
            e.entitlement, e.children, f"{e.funded_hours_pw_total:.1f}",
            f"{e.additional_hours_total:.1f}"))
    summary.config(
        text=f"Funded children: {s['active_funded_children']}   "
             f"Funded h/pw: {s['total_funded_hours_pw']:.1f}   "
             f"Claims: {s['claims_count']}   "
             f"Total: {_money(s['total_claim_amount'])}   "
             f"Submitted: {_money(s['submitted_amount'])}   "
             f"Draft: {_money(s['draft_amount'])}")


def _export(host) -> None:
    path = filedialog.asksaveasfilename(
        parent=getattr(host, "root", None), title="Export Funding Report",
        defaultextension=".csv", filetypes=[("CSV files", "*.csv")],
        initialfile="funding_report.csv")
    if not path:
        return
    try:
        res = data.export_csv(path)
        messagebox.showinfo(
            "Funding Report",
            f"Wrote {res['row_count']} row(s) to:\n{res['path']}",
            parent=getattr(host, "root", None))
        host.status_var.set(f"Exported funding report → {res['path']}")
    except OSError as e:
        messagebox.showerror("Funding Report", str(e),
                             parent=getattr(host, "root", None))


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Funding Report",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open the Funding Report from the navigation menu."
              ).pack(anchor="w")
    return frame
