"""Cross-system reporting warehouse — read-only Tkinter dashboard.

A thin GUI over :class:`education_system.platform.features.analytics.warehouse.Warehouse`:
org-wide headcounts, the nursery→university retention funnel, and
phase-to-phase progression rates — the questions no single system can
answer. Follows the shared-frame convention ``(parent, db_path=None,
auth=None)`` so any system's GUI can embed it.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from education_system.platform.kernel.database.paths import SYSTEM_LABELS, SYSTEM_ORDER

_HEADER_BG = "#1a5276"
_BODY_BG = "#ecf0f1"
_CARD_BG = "white"


class WarehouseFrame(tk.Frame):
    """Cross-system reporting dashboard."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._auth = auth
        self._build_ui()
        self.after(100, self.refresh)

    def _build_ui(self):
        self.configure(bg=_BODY_BG)
        header = tk.Frame(self, bg=_HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Cross-System Reporting Warehouse",
                 font=("Helvetica", 15, "bold"), bg=_HEADER_BG,
                 fg="white").pack(side="left", padx=20, pady=10)
        ttk.Button(header, text="Refresh", command=self.refresh).pack(
            side="right", padx=10, pady=10)

        outer = tk.Frame(self, bg=_BODY_BG)
        outer.pack(fill="both", expand=True)
        self._canvas = tk.Canvas(outer, bg=_BODY_BG, highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient="vertical",
                            command=self._canvas.yview)
        self._body = tk.Frame(self._canvas, bg=_BODY_BG)
        self._body.bind("<Configure>", lambda _e: self._canvas.configure(
            scrollregion=self._canvas.bbox("all")))
        self._canvas.create_window((0, 0), window=self._body, anchor="nw")
        self._canvas.configure(yscrollcommand=vsb.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def refresh(self):
        for w in self._body.winfo_children():
            w.destroy()
        try:
            from education_system.platform.features.analytics.warehouse import Warehouse
            summary = Warehouse().summary()
        except Exception as exc:  # noqa: BLE001
            tk.Label(self._body, text=f"Could not load warehouse: {exc}",
                     bg=_BODY_BG, fg="#a00").pack(anchor="w", padx=16, pady=16)
            return
        self._render_headcount(summary.get("headcount", {}))
        self._render_funnel(summary.get("retention_funnel", {}))
        self._render_rates(summary.get("progression_rates", {}))

    def _render_headcount(self, headcount: dict):
        section = self._section("Headcount by system")
        row = tk.Frame(section, bg=_BODY_BG)
        row.pack(fill="x", padx=12, pady=6)
        if not headcount:
            tk.Label(row, text="No system databases attached.",
                     bg=_BODY_BG, fg="#555").pack(anchor="w")
            return
        for system in SYSTEM_ORDER:
            info = headcount.get(system)
            if not info:
                continue
            card = tk.Frame(row, bg=_CARD_BG, bd=1, relief="groove",
                            padx=14, pady=10)
            card.pack(side="left", fill="x", expand=True, padx=5)
            tk.Label(card, text=str(info["headcount"]), bg=_CARD_BG,
                     font=("Helvetica", 18, "bold")).pack()
            tk.Label(card, text=info.get("label", system), bg=_CARD_BG,
                     font=("Helvetica", 9)).pack()

    def _render_funnel(self, funnel: dict):
        section = self._section(
            f"Retention funnel  ({funnel.get('_total_journeys', 0)} journeys)")
        for system in SYSTEM_ORDER:
            info = funnel.get(system)
            if not info:
                continue
            line = (f"{info.get('label', system):<20}  "
                    f"{info['reached']:>5}   ({info['pct_of_total']}% of all)")
            tk.Label(section, text=line, bg=_BODY_BG,
                     font=("Courier", 10)).pack(anchor="w", padx=14)

    def _render_rates(self, rates: dict):
        section = self._section("Phase-to-phase progression rates")
        labels = {s: SYSTEM_LABELS.get(s, s.title()) for s in SYSTEM_ORDER}
        for key, pct in rates.items():
            a, _, b = key.partition("->")
            tk.Label(section,
                     text=f"{labels.get(a, a)} → {labels.get(b, b)}:  {pct}%",
                     bg=_BODY_BG, font=("Helvetica", 10)).pack(
                         anchor="w", padx=14)

    def _section(self, title: str) -> tk.Frame:
        tk.Label(self._body, text=title, bg=_BODY_BG,
                 font=("Helvetica", 12, "bold")).pack(
                     anchor="w", padx=14, pady=(14, 2))
        frame = tk.Frame(self._body, bg=_BODY_BG)
        frame.pack(fill="x")
        return frame


__all__ = ["WarehouseFrame"]
