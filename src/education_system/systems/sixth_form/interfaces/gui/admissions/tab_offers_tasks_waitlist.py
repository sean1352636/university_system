"""Offers, Tasks and Waitlist tabs of the Sixth Form Admissions window.

Split out of ``admissions_views`` (2026-10-22); that module
re-exports every name defined here.
"""
from __future__ import annotations

import datetime as _dt
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.sixth_form.domain.admissions import (
    admissions as data,
)
from education_system.systems.sixth_form.domain.admissions.admissions import (
    Applicant,
    DEFAULT_OFFER_TYPE,
    OPEN_STATUSES,
)
from . import applicant_actions as act
from ._common import _parse_date, _prompt


class OffersTab:
    """Pending offers with expiry alerts and quick decisions (item 46)."""

    COLS = ("id", "name", "offer", "expiry", "left", "conditions", "email")

    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Offers")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="View…", command=self._view).pack(side="left")
        ttk.Button(bar, text="Mark accepted",
                    command=lambda: self._decide("Offer Accepted")).pack(
            side="left", padx=4)
        ttk.Button(bar, text="Mark declined",
                    command=self._declined).pack(side="left", padx=2)
        ttk.Button(bar, text="Set/extend expiry…",
                    command=self._set_expiry).pack(side="left", padx=4)
        ttk.Button(bar, text="Email…", command=self._email).pack(
            side="left", padx=2)
        ttk.Button(bar, text="Expiry reminder…",
                   command=self._expiry_reminder).pack(side="left", padx=2)
        for b in bar.winfo_children():
            if str(b.cget("text")) not in ("View…", "Refresh"):
                act.gate(b, act.can_admissions())
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                  anchor="w").pack(side="bottom", fill="x", padx=8,
                                   pady=(0, 8))
        table = ttk.Frame(self.frame)
        table.pack(fill="both", expand=True, padx=8, pady=4)
        self.tree = ttk.Treeview(table, columns=self.COLS, show="headings")
        widths = {"id": 80, "name": 180, "offer": 110, "expiry": 100,
                  "left": 60, "conditions": 260, "email": 200}
        for c in self.COLS:
            self.tree.heading(c, text=c.capitalize())
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(table, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("expiring", background="#fff2cc")
        self.tree.tag_configure("expired", background="#ffd0d0")
        self.tree.bind("<Double-1>", lambda _e: self._view())

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        rows = data.list_applicants(status="Offer Made")
        today = _dt.date.today()
        expiring = 0
        for a in rows:
            exp = _parse_date(a.offer_expiry)
            left = (exp - today).days if exp else None
            tags: tuple[str, ...] = ()
            if left is not None and left < 0:
                tags = ("expired",)
                expiring += 1
            elif left is not None and left <= 7:
                tags = ("expiring",)
                expiring += 1
            self.tree.insert("", "end", iid=a.applicant_id, values=(
                a.applicant_id, a.full_name, a.offer_type or "—",
                a.offer_expiry or "—",
                left if left is not None else "—",
                a.offer_conditions or "—", a.email or "—"), tags=tags)
        self.count_var.set(
            f"{len(rows)} pending offer(s)."
            + (f"  ⚠ {expiring} expiring or expired." if expiring else ""))

    def _sel(self) -> Applicant | None:
        sel = self.tree.selection()
        return data.get_applicant(sel[0]) if sel else None

    def _view(self) -> None:
        a = self._sel()
        if a is None:
            messagebox.showinfo("View", "Select an offer first.")
            return
        DetailDialog(self.frame.winfo_toplevel(), a, on_change=self.refresh)

    def _decide(self, status: str) -> None:
        a = self._sel()
        if a is None:
            messagebox.showinfo(status, "Select an offer first.")
            return
        if not messagebox.askyesno(status,
                                     f"Set {a.applicant_id} → {status}?"):
            return
        ok, _ = act.attempt(self.frame, status, data.set_status,
                            a.applicant_id, status)
        if ok:
            self.refresh()

    def _declined(self) -> None:
        a = self._sel()
        if a is None:
            messagebox.showinfo("Mark declined", "Select an offer first.")
            return
        act.withdraw_or_decline(self.frame, [a.applicant_id], decline=True,
                                on_done=self.refresh)

    def _expiry_reminder(self) -> None:
        a = self._sel()
        if a is None:
            messagebox.showinfo("Expiry reminder", "Select an offer first.")
            return
        from . import applicant_email
        applicant_email.expiry_warning(self.frame, a.applicant_id,
                                       on_sent=self.refresh)

    def _set_expiry(self) -> None:
        a = self._sel()
        if a is None:
            messagebox.showinfo("Expiry", "Select an offer first.")
            return
        new = _prompt(self.frame, "Offer expiry",
                      "Expiry date (YYYY-MM-DD, blank to clear):",
                      a.offer_expiry or (_dt.date.today()
                                         + _dt.timedelta(days=14)).isoformat())
        if new is None:
            return
        ok, _ = act.attempt(self.frame, "Offer expiry", data.set_offer_expiry,
                            a.applicant_id, new.strip() or None)
        if ok:
            self.refresh()

    def _email(self) -> None:
        a = self._sel()
        if a is None:
            messagebox.showinfo("Email", "Select an offer first.")
            return
        from . import applicant_email
        applicant_email.email_applicant(self.frame, a.applicant_id,
                                        on_sent=self.refresh)


class TasksTab:
    """Actionable worklist across the pipeline (items 47, 50)."""

    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Tasks")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Open selected…",
                    command=self._open).pack(side="left")
        ttk.Button(bar, text="Activity feed…",
                    command=self._activity_feed).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

        self.tree = ttk.Treeview(self.frame, show="tree", selectmode="browse")
        self.tree.pack(fill="both", expand=True, padx=8, pady=4)
        self.tree.bind("<Double-1>", lambda _e: self._open())
        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8, pady=(0, 8))

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        apps = data.list_applicants()
        today = _dt.date.today()

        def bucket(title: str, items: list[tuple[str, str]]) -> None:
            node = self.tree.insert("", "end",
                                     text=f"{title}  ({len(items)})",
                                     open=True)
            for aid, label in items:
                self.tree.insert(node, "end", iid=f"{node}:{aid}",
                                  text=label)

        refs = [(a.applicant_id, f"{a.applicant_id}  {a.full_name} — "
                 f"reference {a.reference_status}")
                for a in apps
                if a.reference_status in ("Not requested", "Requested")
                and a.status in OPEN_STATUSES]
        follow = [(a.applicant_id, f"{a.applicant_id}  {a.full_name} — "
                   f"[{a.status}]")
                  for a in apps if a.follow_up]
        expiring = []
        for a in apps:
            if a.status != "Offer Made":
                continue
            exp = _parse_date(a.offer_expiry)
            if exp and (exp - today).days <= 7:
                left = (exp - today).days
                expiring.append((a.applicant_id,
                                 f"{a.applicant_id}  {a.full_name} — "
                                 f"expires {a.offer_expiry} ({left}d)"))
        awaiting = [(a.applicant_id, f"{a.applicant_id}  {a.full_name}")
                    for a in apps if a.status == "Interviewed"]
        unscheduled = [(a.applicant_id, f"{a.applicant_id}  {a.full_name}")
                       for a in apps
                       if a.status == "Under Review" and not a.interview_date]

        bucket("Outstanding references", refs)
        bucket("Flagged for follow-up / no-show", follow)
        bucket("Offers expiring ≤7 days", expiring)
        bucket("Interviewed — awaiting decision", awaiting)
        bucket("Under review — no interview booked", unscheduled)
        total = len(refs) + len(follow) + len(expiring) + len(awaiting) \
            + len(unscheduled)
        self.count_var.set(f"{total} open task(s).")

    def _open(self) -> None:
        sel = self.tree.selection()
        if not sel or ":" not in sel[0]:
            messagebox.showinfo("Open", "Select a task row (not a heading).")
            return
        aid = sel[0].split(":", 1)[1]
        a = data.get_applicant(aid)
        if a is not None:
            DetailDialog(self.frame.winfo_toplevel(), a,
                          on_change=self.refresh)

    def _activity_feed(self, limit: int = 100) -> None:
        events = []
        for a in data.list_applicants():
            for e in data.list_events(a.applicant_id):
                events.append((e.at, a.applicant_id, e.kind, e.detail))
        events.sort(key=lambda t: t[0], reverse=True)
        lines = [f"Recent activity (latest {limit})", "=" * 60, ""]
        for at, aid, kind, detail in events[:limit]:
            lines.append(f"{at}  {aid:<8} [{kind}]  {detail}")
        if not events:
            lines.append("(no activity recorded)")
        TextViewerDialog(self.frame.winfo_toplevel(),
                          "Activity feed", "\n".join(lines))


class WaitlistTab:
    """Ranked waitlist with promote/demote and make-offer (item 34)."""

    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Waitlist")
        self._build()
        self.refresh()

    def _build(self) -> None:
        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(side="bottom", fill="x", padx=8,
                                    pady=(0, 8))
        bar = ttk.Frame(self.frame)
        bar.pack(side="bottom", fill="x", padx=8, pady=(0, 4))
        ttk.Button(bar, text="▲ Up",
                    command=lambda: self._move(-1)).pack(side="left")
        ttk.Button(bar, text="▼ Down",
                    command=lambda: self._move(1)).pack(side="left", padx=4)
        ttk.Button(bar, text="Make offer",
                    command=self._offer).pack(side="left", padx=12)
        ttk.Button(bar, text="Auto-promote top",
                    command=self._waitlist_auto_promote).pack(side="left")
        ttk.Button(bar, text="Remove from list",
                    command=self._remove).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")
        for b in bar.winfo_children():
            if str(b.cget("text")) != "Refresh":
                act.gate(b, act.can_admissions())
        cols = ("rank", "id", "name", "subjects", "submitted")
        table = ttk.Frame(self.frame)
        table.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree = ttk.Treeview(table, columns=cols, show="headings")
        for c, w in (("rank", 60), ("id", 90), ("name", 200),
                      ("subjects", 320), ("submitted", 110)):
            self.tree.heading(c, text=c.capitalize())
            self.tree.column(c, width=w, anchor="w")
        vs = ttk.Scrollbar(table, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")


    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        rows = data.get_waitlist()
        for r, a in enumerate(rows, start=1):
            self.tree.insert("", "end", iid=a.applicant_id, values=(
                a.waitlist_rank if a.waitlist_rank else r,
                a.applicant_id, a.full_name,
                ", ".join(a.subjects), a.submitted_at))
        self.count_var.set(f"{len(rows)} waitlisted applicant(s).")

    def _sel(self) -> str | None:
        sel = self.tree.selection()
        return sel[0] if sel else None

    def _move(self, direction: int) -> None:
        aid = self._sel()
        if aid is None:
            return
        ok, _ = act.attempt(self.frame, "Waitlist", data.move_waitlist, aid,
                            direction)
        if not ok:
            return
        self.refresh()
        if self.tree.exists(aid):
            self.tree.selection_set(aid)

    def _offer(self) -> None:
        aid = self._sel()
        if aid is None:
            messagebox.showinfo("Make offer", "Select an applicant.")
            return
        a = data.get_applicant(aid)
        if a is not None:
            OfferDialog(self.frame.winfo_toplevel(), a,
                         on_save=self.refresh)

    def _remove(self) -> None:
        aid = self._sel()
        if aid is None:
            messagebox.showinfo("Waitlist", "Select an applicant first.")
            return
        ok, _ = act.attempt(self.frame, "Remove from list",
                            data.set_waitlist_rank, aid, None)
        if ok:
            self.refresh()

    def _waitlist_auto_promote(self) -> None:
        rows = data.get_waitlist()
        if not rows:
            messagebox.showinfo("Auto-promote", "The waitlist is empty.")
            return
        top = rows[0]
        if not messagebox.askyesno(
                "Auto-promote top of waitlist",
                f"A place has opened up — make an offer to the top-ranked "
                f"waitlisted applicant?\n\n"
                f"{top.applicant_id} — {top.full_name} "
                f"(rank {top.waitlist_rank or 1})"):
            return
        if act.make_offer(self.frame, top.applicant_id,
                          offer_type=DEFAULT_OFFER_TYPE,
                          conditions="Promoted from waitlist.",
                          decided_by=act.username()) is None:
            self.refresh()
            return
        ok, _ = act.attempt(self.frame, "Auto-promote", data.set_waitlist_rank,
                            top.applicant_id, None)
        self.refresh()
        if not ok:
            return
        messagebox.showinfo(
            "Auto-promote",
            f"Offer made to {top.applicant_id} ({top.full_name}) and removed "
            f"from the waitlist.")


# Sibling names used only at call time; imported last so any import order works.
from .dialogs_actions import OfferDialog, TextViewerDialog  # noqa: E402
from .dialogs_detail import DetailDialog  # noqa: E402
