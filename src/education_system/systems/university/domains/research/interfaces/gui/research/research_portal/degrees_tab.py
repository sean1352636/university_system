"""Research Degrees: a read-only view of the PGR record.

Research degrees are run in PGR Administration (proposal, supervision team,
progress reviews, upgrade, thesis, examiners, viva, corrections, deposit).
This tab shows that record; changes are made there. It replaces the old
Theses tab, which kept a separate list in ``student_supervisions``.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from education_system.systems.university.domains.research.domain.research.pgr import service
from education_system.systems.university.domains.research.interfaces.gui.research.research_portal import (  # noqa: E501
    common,
)

logger = logging.getLogger(__name__)


def _rows(section, fmt):
    return [fmt(r) for r in section] or ["—"]


class DegreesTab(ttk.Frame):
    def __init__(self, parent, portal):
        super().__init__(parent)
        self.portal = portal
        self.who = portal.who
        top = ttk.Frame(self, padding=(6, 6, 6, 2))
        top.pack(side="top", fill="x")
        ttk.Label(top, text="Status").pack(side="left")
        self.status = tk.StringVar(value="")
        box = ttk.Combobox(top, textvariable=self.status, state="readonly", width=20,
                           values=("", *sorted(service.PGR_STATES)))
        box.pack(side="left", padx=4)
        box.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="left", padx=4)
        ttk.Button(top, text="Open PGR administration", command=self._open_admin).pack(
            side="left", padx=4)
        ttk.Label(top, text="Read-only here; make changes in PGR administration.",
                  foreground="#555555").pack(side="left", padx=8)
        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=6, pady=4)
        left, right = ttk.Frame(panes), ttk.Frame(panes)
        panes.add(left, weight=2)
        panes.add(right, weight=3)
        self.count = ttk.Label(left, text="")
        self.count.pack(side="bottom", anchor="w")
        self.tree = common.make_tree(left, [("student", "Student", 90),
                                            ("title", "Title", 220), ("route", "Route", 80),
                                            ("status", "Status", 110), ("deadline", "Due", 90)])
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._selected())
        self.detail = common.Detail(right)
        self.detail.pack(fill="both", expand=True)
        self.detail.clear("Select a research degree on the left.")

    def refresh(self):
        try:
            rows = service.list_projects(self.status.get() or None)
        except Exception as exc:          # the PGR tables may be missing on old databases
            logger.exception("PGR list failed")
            self.detail.clear(f"The research degree record could not be read: {exc}")
            rows = []
        common.fill(self.tree, rows, lambda r: r["project_id"], lambda r: (
            r["student_id"], r["proposal_title"], r.get("route"), r.get("status"),
            r.get("current_deadline") or r.get("expected_end_date")))
        self.count.configure(text=f"{len(rows)} research degree(s)")

    def open_record(self, record_id):
        self._show(record_id)

    def _selected(self):
        pid = common.selected(self.tree)
        if pid:
            self._show(pid)

    def _show(self, project_id):
        try:
            r = service.project_record(int(project_id))
        except Exception as exc:
            logger.exception("PGR record failed")
            self.detail.clear(f"This record could not be read: {exc}")
            return
        self.detail.show(r["proposal_title"], [
            ("", [("Student", r["student_id"]), ("Department", r.get("department")),
                  ("Route", r.get("route")), ("Status", r.get("status")),
                  ("Started", r.get("start_date")), ("Expected end", r.get("expected_end_date")),
                  ("Current deadline", r.get("current_deadline"))]),
            ("Supervisors", _rows(r["supervisors"], lambda s: (
                f"{s['supervisor_id']} – {s['role']} ({s['workload_fte']} FTE)"
                + ("" if s.get("active") else " (ended)")))),
            ("Progress reviews", _rows(r["reviews"], lambda v: " ".join(
                str(v.get(k) or "") for k in ("review_year", "due_date", "status", "outcome")))),
            ("Upgrade", _rows(r["upgrades"], lambda u: f"{u.get('report_reference') or ''} – "
                                                       f"{u.get('outcome') or u.get('status')}")),
            ("Milestones", _rows(r["milestones"], lambda m: (
                f"{m.get('title')} ({m.get('milestone_type')}) due {m.get('due_date')} – "
                f"{m.get('status')}"))),
            ("Thesis submissions", _rows(r["submissions"], lambda s: " ".join(
                str(v) for k, v in s.items() if k not in ("project_id",) and v))),
            ("Examiners", _rows(r["examiners"], lambda e: " ".join(
                str(v) for k, v in e.items() if k not in ("project_id",) and v))),
            ("Viva", _rows(r["vivas"], lambda v: f"{v.get('scheduled_at')} at "
                                                 f"{v.get('location') or '—'} – "
                                                 f"{v.get('outcome') or 'scheduled'}")),
            ("Corrections", _rows(r["corrections"], lambda c: (
                f"due {c.get('due_date')} – {c.get('status')}"))),
            ("Final deposit", _rows(r["deposits"], lambda d: " ".join(
                str(v) for k, v in d.items() if k not in ("project_id",) and v))),
            ("History", _rows(r["history"], lambda h: " ".join(
                str(v) for k, v in h.items() if k not in ("project_id", "history_id") and v))),
        ])

    def _open_admin(self):
        try:
            from education_system.systems.university.domains.research.interfaces.gui.research.pgr import (  # noqa: E501
                pgr_admin_gui,
            )
            pgr_admin_gui.open_window(self.winfo_toplevel(), getattr(self.portal, "auth", None))
        except Exception as exc:
            logger.exception("PGR administration failed to open")
            common.info(self, f"PGR administration could not be opened: {exc}")
