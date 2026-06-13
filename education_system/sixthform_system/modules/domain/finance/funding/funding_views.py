"""Tkinter views for Sixth Form Funding."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from education_system.shared import branding
from education_system.sixthform_system.modules.domain.finance.funding import (
    funding as data,
)
from education_system.sixthform_system.modules.domain.finance.funding.funding import (
    ALLOCATION_STATUSES,
    DEFAULT_ALLOCATION_STATUS,
    DEFAULT_FUNDER,
    DEFAULT_FUNDING_BAND,
    DEFAULT_STREAM_STATUS,
    DEFAULT_STREAM_TYPE,
    FUNDERS,
    FUNDING_BANDS,
    FundingStream,
    LearnerAllocation,
    STREAM_STATUSES,
    STREAM_TYPES,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_STREAM_TAGS = {
    "Planned":    ("#fff7e6", "#7a5800"),
    "Confirmed":  ("#e6f0ff", "#1a3f8c"),
    "Active":     ("#e6f7e6", "#0d6b2a"),
    "Underspent": ("#fff7e6", "#7a5800"),
    "Closed":     ("#dddddd", "#444444"),
    "Reconciled": ("#dddddd", "#444444"),
    "Withdrawn":  ("#ffd1d1", "#8c0d0d"),
}

_ALLOC_TAGS = {
    "Provisional": ("#fff7e6", "#7a5800"),
    "Approved":    ("#e6f0ff", "#1a3f8c"),
    "Active":      ("#e6f7e6", "#0d6b2a"),
    "Suspended":   ("#fff7e6", "#7a5800"),
    "Drawn Down":  ("#d6ffd6", "#0d6b2a"),
    "Closed":      ("#dddddd", "#444444"),
    "Withdrawn":   ("#ffd1d1", "#8c0d0d"),
}


def open_funding_window(parent=None) -> None:
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Funding — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)
    build_funding_notebook(win)


def build_funding_notebook(parent: tk.Misc) -> ttk.Notebook:
    """Build the Funding notebook into *parent* (a Toplevel or Frame)."""
    data.init_db()
    nb = ttk.Notebook(parent)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    StreamsTab(nb, scope="all",            label="All Streams")
    StreamsTab(nb, scope="active",         label="Active")
    StreamsTab(nb, scope="overcommitted",  label="Overcommitted")
    AllocationsTab(nb)
    SummaryTab(nb)
    return nb


class StreamsTab:
    def __init__(self, nb: ttk.Notebook, *,
                 scope: str, label: str) -> None:
        self.scope = scope
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text=label)
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Type:").pack(side="left")
        self.f_type = ttk.Combobox(
            bar, values=("",) + STREAM_TYPES,
            state="readonly", width=24)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Funder:").pack(side="left")
        self.f_funder = ttk.Combobox(
            bar, values=("",) + FUNDERS,
            state="readonly", width=14)
        self.f_funder.current(0)
        self.f_funder.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Year:").pack(side="left")
        self.f_year = ttk.Entry(bar, width=10)
        self.f_year.pack(side="left", padx=(2, 8))
        if self.scope == "all":
            ttk.Label(bar, text="Status:").pack(side="left")
            self.f_status = ttk.Combobox(
                bar, values=("",) + STREAM_STATUSES,
                state="readonly", width=12)
            self.f_status.current(0)
            self.f_status.pack(side="left", padx=(2, 8))
        else:
            self.f_status = None
        ttk.Label(bar, text="Name:").pack(side="left")
        self.f_name = ttk.Entry(bar, width=16)
        self.f_name.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left",
                                                 padx=4)
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left",
                                              padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True,
                            padx=8, pady=4)
        cols = ("id", "ov", "name", "type", "funder",
                "year", "allocated", "committed", "drawn",
                "remaining", "util", "status")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "ov": 40, "name": 240,
                   "type": 200, "funder": 110,
                   "year": 70, "allocated": 110,
                   "committed": 110, "drawn": 110,
                   "remaining": 110, "util": 70,
                   "status": 110}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "ov",
                                                  "util")
                                       else "e"
                                       if c in ("allocated",
                                                  "committed",
                                                  "drawn",
                                                  "remaining")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _STREAM_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        self.tree.tag_configure("overcommitted",
                                  background="#ffd1d1",
                                  foreground="#8c0d0d")
        self.tree.bind("<Double-Button-1>",
                         lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("Edit",       self._edit),
                ("Confirm",    self._confirm),
                ("Activate",   self._activate),
                ("Close",      self._close),
                ("Reconcile",  self._reconcile),
                ("Status",     self._set_status),
                ("Delete",     self._delete),
                ("Refresh",    self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_type.get():
            f["stream_type"] = self.f_type.get()
        if self.f_funder.get():
            f["funder"] = self.f_funder.get()
        if self.f_year.get().strip():
            f["academic_year"] = self.f_year.get().strip()
        if self.f_status is not None and self.f_status.get():
            f["status"] = self.f_status.get()
        if self.f_name.get().strip():
            f["name_like"] = self.f_name.get().strip()
        if self.scope == "active":
            f["active_only"] = True
        elif self.scope == "overcommitted":
            f["overcommitted_only"] = True
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            rows = data.list_streams(**self._filters())
        except ValidationError as e:
            messagebox.showerror("Funding", str(e),
                                    parent=self.frame)
            return
        for s in rows:
            tag = ("overcommitted" if s.is_overcommitted
                     else s.status)
            self.tree.insert(
                "", "end", iid=str(s.stream_id),
                values=(s.stream_id,
                         "!" if s.is_overcommitted else "",
                         s.name, s.stream_type,
                         s.funder, s.academic_year,
                         f"£{s.allocated_amount:,.0f}",
                         f"£{s.committed_amount:,.0f}",
                         f"£{s.drawn_down_amount:,.0f}",
                         f"£{s.remaining:,.0f}",
                         f"{s.utilisation_pct}%",
                         s.status),
                tags=(tag,))
        self.count.config(text=f"{len(rows)} stream(s)")

    def _selected(self) -> FundingStream | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Funding",
                                  "Select a stream first.",
                                  parent=self.frame)
            return None
        return data.get_stream(int(sel[0]))

    def _new(self) -> None:
        if StreamEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        s = self._selected()
        if s and StreamEditor(
                self.frame,
                stream=s).result is not None:
            self.refresh()

    def _run(self, action) -> None:
        s = self._selected()
        if not s:
            return
        try:
            action(s.stream_id)
        except ValidationError as e:
            messagebox.showerror("Funding", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _confirm(self) -> None:
        self._run(data.confirm_stream)

    def _activate(self) -> None:
        self._run(data.activate_stream)

    def _close(self) -> None:
        self._run(data.close_stream)

    def _reconcile(self) -> None:
        self._run(data.reconcile_stream)

    def _set_status(self) -> None:
        s = self._selected()
        if not s:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(STREAM_STATUSES),
                                default=s.status)
        if not new:
            return
        try:
            data.set_stream_status(s.stream_id, new)
        except ValidationError as e:
            messagebox.showerror("Funding", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        s = self._selected()
        if not s:
            return
        if not messagebox.askyesno(
                "Funding",
                f"Delete stream #{s.stream_id}?",
                parent=self.frame):
            return
        data.delete_stream(s.stream_id)
        self.refresh()


class AllocationsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Allocations")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Stream id:").pack(side="left")
        self.f_sid = ttk.Entry(bar, width=8)
        self.f_sid.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Learner:").pack(side="left")
        self.f_ref = ttk.Entry(bar, width=12)
        self.f_ref.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Band:").pack(side="left")
        self.f_band = ttk.Combobox(
            bar, values=("",) + FUNDING_BANDS,
            state="readonly", width=22)
        self.f_band.current(0)
        self.f_band.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(
            bar, values=("",) + ALLOCATION_STATUSES,
            state="readonly", width=14)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left",
                                                 padx=4)
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left",
                                              padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True,
                            padx=8, pady=4)
        cols = ("id", "stream", "learner", "name", "band",
                "start", "end", "value", "committed",
                "drawn", "remaining", "status")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "stream": 60, "learner": 90,
                   "name": 140, "band": 200,
                   "start": 90, "end": 90,
                   "value": 90, "committed": 100,
                   "drawn": 100, "remaining": 100,
                   "status": 110}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "stream")
                                       else "e"
                                       if c in ("value",
                                                  "committed",
                                                  "drawn",
                                                  "remaining")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _ALLOC_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        self.tree.bind("<Double-Button-1>",
                         lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("Edit",      self._edit),
                ("Approve",   self._approve),
                ("Activate",  self._activate),
                ("Suspend",   self._suspend),
                ("Close",     self._close),
                ("Withdraw",  self._withdraw),
                ("Drawdown",  self._drawdown),
                ("Status",    self._set_status),
                ("Delete",    self._delete),
                ("Refresh",   self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_sid.get().strip().isdigit():
            f["stream_id"] = int(self.f_sid.get().strip())
        if self.f_ref.get().strip():
            f["learner_ref"] = self.f_ref.get().strip()
        if self.f_band.get():
            f["funding_band"] = self.f_band.get()
        if self.f_status.get():
            f["status"] = self.f_status.get()
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        rows = data.list_allocations(**self._filters())
        for a in rows:
            self.tree.insert(
                "", "end", iid=str(a.allocation_id),
                values=(a.allocation_id,
                         a.stream_id or "—",
                         a.learner_ref,
                         a.learner_name or "—",
                         a.funding_band, a.starts_on,
                         a.ends_on or "—",
                         f"£{a.band_value:,.2f}",
                         f"£{a.committed_amount:,.2f}",
                         f"£{a.drawn_down_amount:,.2f}",
                         f"£{a.remaining:,.2f}",
                         a.status),
                tags=(a.status,))
        self.count.config(text=f"{len(rows)} allocation(s)")

    def _selected(self) -> LearnerAllocation | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Funding",
                                  "Select an allocation first.",
                                  parent=self.frame)
            return None
        return data.get_allocation(int(sel[0]))

    def _new(self) -> None:
        if AllocationEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        a = self._selected()
        if a and AllocationEditor(
                self.frame,
                allocation=a).result is not None:
            self.refresh()

    def _run(self, action) -> None:
        a = self._selected()
        if not a:
            return
        try:
            action(a.allocation_id)
        except ValidationError as e:
            messagebox.showerror("Funding", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _approve(self) -> None:
        a = self._selected()
        if not a:
            return
        by = _prompt_text(self.frame, "Approved by",
                            initial=a.approved_by or "")
        try:
            data.approve_allocation(
                a.allocation_id,
                approved_by=by or None)
        except ValidationError as e:
            messagebox.showerror("Funding", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _activate(self) -> None:
        self._run(data.activate_allocation)

    def _suspend(self) -> None:
        self._run(data.suspend_allocation)

    def _close(self) -> None:
        self._run(data.close_allocation)

    def _withdraw(self) -> None:
        self._run(data.withdraw_allocation)

    def _drawdown(self) -> None:
        a = self._selected()
        if not a:
            return
        amt = _prompt_text(self.frame,
                             "Drawdown amount (£)",
                             initial="")
        if not amt:
            return
        try:
            data.record_drawdown(a.allocation_id,
                                          amount=float(amt))
        except (ValidationError, ValueError) as e:
            messagebox.showerror("Funding", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _set_status(self) -> None:
        a = self._selected()
        if not a:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(ALLOCATION_STATUSES),
                                default=a.status)
        if not new:
            return
        try:
            data.set_allocation_status(a.allocation_id, new)
        except ValidationError as e:
            messagebox.showerror("Funding", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        a = self._selected()
        if not a:
            return
        if not messagebox.askyesno(
                "Funding",
                f"Delete allocation #{a.allocation_id}?",
                parent=self.frame):
            return
        data.delete_allocation(a.allocation_id)
        self.refresh()


class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8,
                          pady=(4, 8))
        self.refresh()

    def refresh(self) -> None:
        s = data.summary()
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", "Funding Summary\n")
        self.text.insert("end", "=" * 60 + "\n\n")
        self.text.insert("end",
                            f"Total streams        : {s.total_streams}\n"
                            f"Planned              : {s.planned}\n"
                            f"Active               : {s.active}\n"
                            f"Closed / Reconciled  : {s.closed}\n"
                            f"Overcommitted        : {s.overcommitted}\n\n"
                            f"Total allocated      : £{s.total_allocated:,.2f}\n"
                            f"Total committed      : £{s.total_committed:,.2f}\n"
                            f"Total drawn down     : £{s.total_drawn_down:,.2f}\n"
                            f"Total remaining      : £{s.total_remaining:,.2f}\n"
                            f"Avg utilisation      : {s.avg_utilisation_pct}%\n\n"
                            f"Total allocations    : {s.total_allocations}\n"
                            f"Distinct learners    : {s.distinct_learners}\n\n")
        self.text.insert("end", "By stream type:\n")
        for k in STREAM_TYPES:
            n = s.by_stream_type.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<36}: {n}\n")
        self.text.insert("end", "\nBy funder:\n")
        for k in FUNDERS:
            n = s.by_funder.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<22}: {n}\n")
        self.text.insert("end", "\nBy stream status:\n")
        for k in STREAM_STATUSES:
            n = s.by_stream_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<14}: {n}\n")
        self.text.insert("end", "\nBy band:\n")
        for k in FUNDING_BANDS:
            n = s.by_band.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<26}: {n}\n")
        self.text.insert("end", "\nBy allocation status:\n")
        for k in ALLOCATION_STATUSES:
            n = s.by_allocation_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<14}: {n}\n")
        self.text.config(state="disabled")


# ── Editors ──────────────────────────────────────────────

class StreamEditor:
    def __init__(self, parent, *,
                 stream: FundingStream | None = None
                 ) -> None:
        self.stream = stream
        self.result: FundingStream | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Edit stream #{stream.stream_id}"
            if stream else "New stream")
        self.win.geometry("820x680")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if stream:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(3, weight=1)
        self.vars: dict[str, tk.Variable] = {}
        self.texts: dict[str, tk.Text] = {}

        def entry(row, col, label, key, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w",
                padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Entry(body, textvariable=v, width=width).grid(
                row=row, column=col + 1, sticky="ew",
                padx=4, pady=2)

        def combo(row, col, label, key, values, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w",
                padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Combobox(body, textvariable=v, values=values,
                          state="readonly", width=width).grid(
                row=row, column=col + 1, sticky="ew",
                padx=4, pady=2)

        entry(0, 0, "Name*", "name", width=48)
        combo(1, 0, "Type*", "stream_type", STREAM_TYPES)
        combo(1, 2, "Funder*", "funder", FUNDERS)
        entry(2, 0, "Academic year*", "academic_year")
        entry(2, 2, "Reference", "reference")
        entry(3, 0, "Allocated amount (£)*",
                 "allocated_amount")
        combo(3, 2, "Status*", "status", STREAM_STATUSES)
        entry(4, 0, "Starts on", "starts_on")
        entry(4, 2, "Ends on", "ends_on")
        entry(5, 0, "Owner", "owner", width=48)

        ttk.Label(body, text="Notes").grid(
            row=6, column=0, sticky="nw",
            padx=4, pady=(6, 2))
        t = tk.Text(body, height=6, width=72, wrap="word")
        t.grid(row=6, column=1, columnspan=3, sticky="ew",
                  padx=4, pady=(6, 2))
        self.texts["notes"] = t

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right",
                                               padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")

        self.vars["stream_type"].set(DEFAULT_STREAM_TYPE)
        self.vars["funder"].set(DEFAULT_FUNDER)
        self.vars["status"].set(DEFAULT_STREAM_STATUS)
        self.vars["allocated_amount"].set("0")

    def _load(self) -> None:
        s = self.stream
        assert s is not None
        for key in ("name", "stream_type", "funder",
                     "academic_year", "reference",
                     "starts_on", "ends_on", "status",
                     "owner"):
            self.vars[key].set(getattr(s, key) or "")
        self.vars["allocated_amount"].set(
            str(s.allocated_amount))
        self.texts["notes"].delete("1.0", "end")
        self.texts["notes"].insert("1.0", s.notes or "")

    def _save(self) -> None:
        payload: dict = {}
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        if self.stream is not None:
            payload["committed_amount"] = (
                self.stream.committed_amount)
            payload["drawn_down_amount"] = (
                self.stream.drawn_down_amount)
        try:
            if self.stream:
                self.result = data.update_stream(
                    self.stream.stream_id, payload)
            else:
                self.result = data.create_stream(payload)
        except ValidationError as exc:
            messagebox.showerror("Funding", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class AllocationEditor:
    def __init__(self, parent, *,
                 allocation: LearnerAllocation | None = None
                 ) -> None:
        self.allocation = allocation
        self.result: LearnerAllocation | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Edit allocation #{allocation.allocation_id}"
            if allocation else "New allocation")
        self.win.geometry("840x720")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if allocation:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(3, weight=1)
        self.vars: dict[str, tk.Variable] = {}
        self.texts: dict[str, tk.Text] = {}

        def entry(row, col, label, key, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w",
                padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Entry(body, textvariable=v, width=width).grid(
                row=row, column=col + 1, sticky="ew",
                padx=4, pady=2)

        def combo(row, col, label, key, values, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w",
                padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Combobox(body, textvariable=v, values=values,
                          state="readonly", width=width).grid(
                row=row, column=col + 1, sticky="ew",
                padx=4, pady=2)

        entry(0, 0, "Stream id", "stream_id")
        combo(0, 2, "Status*", "status",
                 ALLOCATION_STATUSES)
        entry(1, 0, "Learner ref*", "learner_ref")
        entry(1, 2, "Learner name", "learner_name")
        combo(2, 0, "Band*", "funding_band", FUNDING_BANDS)
        entry(2, 2, "Band value (£)", "band_value")
        entry(3, 0, "Committed (£)", "committed_amount")
        entry(3, 2, "Drawn down (£)", "drawn_down_amount")
        entry(4, 0, "Starts on*", "starts_on")
        entry(4, 2, "Ends on", "ends_on")
        entry(5, 0, "Purpose", "purpose", width=48)
        entry(6, 0, "Approved by", "approved_by",
                 width=48)

        ttk.Label(body, text="Notes").grid(
            row=7, column=0, sticky="nw",
            padx=4, pady=(6, 2))
        t = tk.Text(body, height=5, width=72, wrap="word")
        t.grid(row=7, column=1, columnspan=3, sticky="ew",
                  padx=4, pady=(6, 2))
        self.texts["notes"] = t

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right",
                                               padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")

        self.vars["funding_band"].set(DEFAULT_FUNDING_BAND)
        self.vars["status"].set(DEFAULT_ALLOCATION_STATUS)
        for k in ("band_value", "committed_amount",
                   "drawn_down_amount"):
            self.vars[k].set("0")

    def _load(self) -> None:
        a = self.allocation
        assert a is not None
        self.vars["stream_id"].set(str(a.stream_id or ""))
        for key in ("learner_ref", "learner_name",
                     "funding_band", "starts_on", "ends_on",
                     "status", "purpose", "approved_by"):
            self.vars[key].set(getattr(a, key) or "")
        self.vars["band_value"].set(str(a.band_value))
        self.vars["committed_amount"].set(
            str(a.committed_amount))
        self.vars["drawn_down_amount"].set(
            str(a.drawn_down_amount))
        self.texts["notes"].delete("1.0", "end")
        self.texts["notes"].insert("1.0", a.notes or "")

    def _save(self) -> None:
        payload: dict = {}
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        try:
            if self.allocation:
                self.result = data.update_allocation(
                    self.allocation.allocation_id, payload)
            else:
                self.result = data.create_allocation(payload)
        except ValidationError as exc:
            messagebox.showerror("Funding", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


def _prompt_text(parent, title: str, *,
                  initial: str = "") -> str | None:
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("420x140")
    win.transient(parent); win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(value=initial)
    ttk.Entry(win, textvariable=var).pack(fill="x", padx=8)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = var.get().strip()
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="right",
                                                    padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


def _prompt_choice(parent, title: str, options: list[str], *,
                    default: str | None = None) -> str | None:
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("360x140")
    win.transient(parent); win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(
        value=default or (options[0] if options else ""))
    ttk.Combobox(win, textvariable=var, values=options,
                  state="readonly").pack(fill="x", padx=8)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = var.get()
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="right",
                                                    padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


__all__ = ["open_funding_window"]
