"""Admissions window page: conversion, time in stage and reasons.

Breaks the pipeline down by feeder school, programme, cycle or source
(applied → offered → accepted → enrolled), shows how long applicants
spend at each stage and why they withdrew, declined or were turned
down. Every view exports to CSV. Readable with ``admissions`` or
``reports``.
"""

from __future__ import annotations

from tkinter import ttk
from typing import Any

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.sixth_form.domain.admissions import (
    admissions_insights as insights,
)
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)
from education_system.systems.sixth_form.interfaces.gui import popout
from education_system.systems.sixth_form.interfaces.gui.admissions import (
    pages_common as pc,
)

TITLE = "Insights"

_VIEWS = {
    "Conversion by feeder school": ("conversion", "feeder_school"),
    "Conversion by programme": ("conversion", "programme"),
    "Conversion by cycle": ("conversion", "cycle"),
    "Conversion by source": ("conversion", "source"),
    "Time in stage": ("stage", None),
    "Withdrawal / decline / rejection reasons": ("reasons", None),
}

_CONVERSION_COLS = [
    ("group", "Group", 260), ("applied", "Applied", 70),
    ("offered", "Offered", 70), ("accepted", "Accepted", 75),
    ("enrolled", "Enrolled", 70), ("offer_rate", "Offer %", 70),
    ("acceptance_rate", "Accept %", 75), ("enrolment_rate", "Enrol %", 70),
    ("overall_rate", "Overall %", 75), ("feeder_school", "Feeder", 60)]
_STAGE_COLS = [
    ("stage", "Stage", 200), ("applicants", "Passed through", 110),
    ("current", "In it now", 80), ("average_days", "Average days", 100),
    ("median_days", "Median days", 100), ("longest_days", "Longest days", 100)]
_REASON_COLS = [
    ("outcome", "Outcome", 140), ("reason", "Reason", 420),
    ("count", "Count", 70), ("share", "Share %", 80)]


def _pct(v: Any) -> str:
    return "" if v is None else f"{v}"


class InsightsPage:
    def __init__(self, nb: Any) -> None:
        self.frame = pc.new_page(
            nb, TITLE, "Admissions insights",
            "Stages count every status an applicant passed through, so an "
            "applicant offered a place who later withdrew still counts as "
            "offered. Archived applications are left out.")
        self.allowed = pc.can(access.ADMISSIONS) or pc.can(access.REPORTS)
        if not self.allowed:
            pc.denied(self.frame, "admissions reports (needs admissions or "
                      "reports)")
            return
        bar = ttk.Frame(self.frame)
        bar.pack(side="top", fill="x", pady=(0, 4))
        self.cycle = pc.CyclePicker(bar, self.refresh, allow_all=True)
        self.cycle.pack(side="left", padx=(0, 10))
        ttk.Label(bar, text="Show:").pack(side="left")
        self.view = ttk.Combobox(bar, state="readonly", width=40,
                                 values=list(_VIEWS))
        self.view.set(next(iter(_VIEWS)))
        self.view.pack(side="left", padx=(4, 10))
        self.view.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        ttk.Button(bar, text="Export CSV…", command=self._export).pack(
            side="left")
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(
            side="right")
        if not isinstance(nb, popout.FrameBook):
            popout.add_page_button(bar, "Admissions insights", InsightsPage,
                                   padx=(0, 6))
        self.totals = pc.status_line(self.frame)
        self.status = pc.status_line(self.frame)
        self.holder = ttk.Frame(self.frame)
        self.holder.pack(fill="both", expand=True)
        self.tree: ttk.Treeview | None = None
        self._cols: list[tuple[str, str, int]] = []
        self.rows: list[Any] = []
        self.refresh()

    def _table(self, cols: list[tuple[str, str, int]]) -> ttk.Treeview:
        if self.tree is None or cols != self._cols:
            for w in self.holder.winfo_children():
                w.destroy()
            self.tree = pc.make_tree(self.holder, cols, height=18)
            self._cols = cols
        pc.clear(self.tree)
        return self.tree

    def refresh(self) -> None:
        if not self.allowed:
            return
        cyc = self.cycle.get()
        self.status.set("")
        ok, total = pc.load(self.status, TITLE, insights.conversion_totals,
                            cycle=cyc)
        if ok:
            self.totals.set(
                f"{total.group}: {total.applied} applied · {total.offered} "
                f"offered ({_pct(total.offer_rate) or '–'}%) · "
                f"{total.accepted} accepted "
                f"({_pct(total.acceptance_rate) or '–'}%) · {total.enrolled} "
                f"enrolled ({_pct(total.enrolment_rate) or '–'}%) · overall "
                f"{_pct(total.overall_rate) or '–'}%")
        kind, dim = _VIEWS[self.view.get()]
        if kind == "conversion":
            tree = self._table(_CONVERSION_COLS)
            ok, rows = pc.load(self.status, TITLE, insights.conversion_by,
                               dim, cycle=cyc)
            self.rows = rows or []
            for i, r in enumerate(self.rows):
                feeder = ("" if r.is_feeder is None
                          else ("Yes" if r.is_feeder else "No"))
                tree.insert("", "end", iid=str(i), values=(
                    r.group, r.applied, r.offered, r.accepted, r.enrolled,
                    _pct(r.offer_rate), _pct(r.acceptance_rate),
                    _pct(r.enrolment_rate), _pct(r.overall_rate), feeder))
        elif kind == "stage":
            tree = self._table(_STAGE_COLS)
            ok, rows = pc.load(self.status, TITLE, insights.time_in_stage,
                               cycle=cyc)
            self.rows = rows or []
            for i, s in enumerate(self.rows):
                tree.insert("", "end", iid=str(i), values=(
                    s.stage, s.applicants, s.current, pc.fmt(s.average_days),
                    pc.fmt(s.median_days), pc.fmt(s.longest_days)))
        else:
            tree = self._table(_REASON_COLS)
            ok, br = pc.load(self.status, TITLE, insights.reasons_breakdown,
                             cycle=cyc)
            self.rows = br.rows() if ok else []
            for i, d in enumerate(self.rows):
                tree.insert("", "end", iid=str(i), values=(
                    d["outcome"], d["reason"], d["count"],
                    pc.fmt(d["share"])))
        if ok and not self.rows:
            self.status.set("Nothing to show for this selection.")

    def _export(self) -> None:
        text = insights.to_csv(self.rows)
        if not text:
            messagebox.showinfo(TITLE, "Nothing to export.",
                                parent=self.frame.winfo_toplevel())
            return
        kind, dim = _VIEWS[self.view.get()]
        cyc = (self.cycle.get() or "all").replace("/", "-")
        name = f"admissions_{dim or kind}_{cyc}.csv"
        pc.save_file(self.frame, text, name)
