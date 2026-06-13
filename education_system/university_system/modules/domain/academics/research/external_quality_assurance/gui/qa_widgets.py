"""Embeddable widgets and a context decorator for the External QA module.

These let *other* dashboards display EQA state inline without launching
the full QA window, and let any caller stamp EQA selection into a
launched dialog (#14, #15, #17).
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from education_system.university_system.modules.domain.academics.research.external_quality_assurance.services import (
    qa_service as qa,
)

logger = logging.getLogger(__name__)


_STATUS_COLOURS = {
    "draft": "#888888",
    "in_review": "#c47f00",
    "submitted": "#117a3a",
    "accepted": "#117a3a",
    "rejected": "#a32424",
}


class EQAStatusStrip(ttk.Frame):
    """#14 — One-line strip showing the latest submission status per
    framework. Drop into any dashboard::

        EQAStatusStrip(parent_frame).pack(fill="x")

    The strip auto-refreshes every ``poll_seconds`` (default 30s); pass 0
    to disable polling and call :meth:`refresh` manually."""

    def __init__(self, parent, poll_seconds: int = 30, **kw):
        super().__init__(parent, **kw)
        self._labels: dict[str, ttk.Label] = {}
        ttk.Label(self, text="External QA:",
                  font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=(0, 6))
        for fw in qa.FRAMEWORKS:
            lbl = ttk.Label(self, text=f"{fw} —", padding=(6, 0))
            lbl.pack(side=tk.LEFT)
            self._labels[fw] = lbl
        self._poll_ms = max(0, int(poll_seconds * 1000))
        self.refresh()
        if self._poll_ms:
            self._schedule()

    def refresh(self) -> None:
        try:
            summary = qa.get_qa_summary_dict()
        except Exception:
            logger.exception("EQAStatusStrip refresh failed")
            return
        for fw, lbl in self._labels.items():
            info = summary["frameworks"].get(fw, {})
            year, status = info.get("latest_year"), info.get("latest_status")
            if year and status:
                lbl.configure(
                    text=f"{fw} {year} · {status}",
                    foreground=_STATUS_COLOURS.get(status, "#000000"),
                )
            else:
                lbl.configure(text=f"{fw} —", foreground="#888888")

    def _schedule(self) -> None:
        try:
            self.after(self._poll_ms, self._tick)
        except Exception:
            pass

    def _tick(self) -> None:
        if not self.winfo_exists():
            return
        self.refresh()
        self._schedule()


def embed_kpi_panel(parent, category: str = "external_qa") -> ttk.Frame:
    """#15 — Render a compact KPI table inline. Returns the frame so the
    caller can pack/grid it. Default ``category`` shows EQA KPIs only."""
    f = ttk.Frame(parent, padding=4)
    cols = ("name", "value", "target")
    tv = ttk.Treeview(f, columns=cols, show="headings", height=6)
    for c, txt, w in [("name", "KPI", 320), ("value", "Value", 90),
                      ("target", "Target", 90)]:
        tv.heading(c, text=txt)
        tv.column(c, width=w, anchor=tk.W if c == "name" else tk.E)
    tv.pack(fill=tk.BOTH, expand=True)

    def _refresh() -> None:
        tv.delete(*tv.get_children())
        try:
            rows = qa.compute_external_qa_kpis()
        except Exception:
            logger.exception("embed_kpi_panel compute failed")
            rows = []
        for r in rows:
            if category and r.get("kpi_category") != category:
                continue
            tv.insert("", tk.END, values=(
                r["kpi_name"], r["current_value"],
                r.get("target_value") if r.get("target_value") is not None else "-",
            ))

    bar = ttk.Frame(f)
    bar.pack(fill=tk.X, pady=(4, 0))
    ttk.Button(bar, text="Refresh", command=_refresh).pack(side=tk.RIGHT)
    _refresh()
    return f


def with_qa_context(func: Callable) -> Callable:
    """#17 — Decorator: snapshot the EQA selection (framework, year, uoa)
    onto the wrapped callable's first arg's ``_last_academic_context``
    before invoking it.

    Intended use::

        @with_qa_context
        def open_grades(app, *args, **kwargs): ...

    The decorator looks up the live :class:`QADashboardGUI` via the
    currently-open Toplevel registry on the parent app (``app._eqa_dash``,
    set by ``show_qa_dashboard_gui`` once the dashboard is open). If no
    dashboard is open, the call is forwarded unchanged."""

    @functools.wraps(func)
    def wrapper(app, *args, **kwargs):
        try:
            dash = getattr(app, "_eqa_dash", None)
            if dash is not None and dash.window.winfo_exists():
                ctx: dict[str, Any] = {"source": "eqa.context"}
                # Tab-keyed selection — only include keys with values
                try:
                    ctx["b3_year"] = int(dash.b3_year.get())
                except Exception:
                    pass
                try:
                    ctx["tef_year"] = int(dash.tef_year.get())
                except Exception:
                    pass
                try:
                    uoa = dash.ref_uoa.get().strip()
                    if uoa:
                        ctx["uoa"] = uoa
                except Exception:
                    pass
                app._last_academic_context = ctx
        except Exception:
            logger.exception("with_qa_context: failed to stamp context")
        return func(app, *args, **kwargs)

    return wrapper


__all__ = ["EQAStatusStrip", "embed_kpi_panel", "with_qa_context"]
