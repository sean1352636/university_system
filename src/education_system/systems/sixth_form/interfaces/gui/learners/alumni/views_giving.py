"""Fundraising: campaigns, donations, recurring donations, donor pipeline, funds, bequests, matched giving, Gift Aid."""

from __future__ import annotations
from education_system.systems.sixth_form.interfaces.gui._ui import grab_when_viewable

import datetime as _dt
import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from typing import Any, Callable
from education_system.platform import branding
from education_system.systems.sixth_form.domain.learners.alumni import (
    fundraising as alumni_fundraising,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)
from education_system.systems.sixth_form.domain.learners.alumni.models import (
    ACHIEVEMENT_CATEGORIES,
    Alumnus,
    CAMPAIGN_STATUSES,
    APPLICATION_STATUSES,
    BEQUEST_STATUSES,
    CUSTOM_FIELD_TYPES,
    ERASURE_STATUSES,
    WEBHOOK_EVENT_TYPES,
    CHAPTER_ROLES,
    CONNECTION_KINDS,
    DIRECTORY_CONSENT_SCOPE,
    DONOR_STAGES,
    DRIP_STATUSES,
    JOB_STATUSES,
    JOB_TYPES,
    NEET_STATUSES,
    NEWSLETTER_STATUSES,
    PROFICIENCY_LEVELS,
    RECURRING_FREQS,
    RECURRING_STATUSES,
    SAFEGUARDING_STATUSES,
    SOCIAL_PLATFORMS,
    TRACK_KINDS,
    CONSENT_SCOPES,
    DEFAULT_CAMPAIGN_STATUS,
    DEFAULT_DESTINATION,
    DEFAULT_EDUCATION_STATUS,
    DEFAULT_EVENT_STATUS,
    DEFAULT_LEAVING_REASON,
    DEFAULT_PLEDGE_STATUS,
    DEFAULT_RSVP_STATUS,
    DEFAULT_STATUS,
    DESTINATION_TYPES,
    EDUCATION_STATUSES,
    EMAIL_LABELS,
    EVENT_STATUSES,
    EVENT_TYPES,
    GENDER_OPTIONS,
    LEAVING_REASONS,
    MENTORSHIP_STATUSES,
    PAYMENT_METHODS,
    PHONE_LABELS,
    PLEDGE_STATUSES,
    RSVP_STATUSES,
    SALARY_BANDS,
    SECTORS,
    SESSION_FORMATS,
    STATUSES,
    VOLUNTEER_ACTIVITY_TYPES,
)
from education_system.systems.sixth_form.domain.learners.alumni.integrations import MEDIA_KINDS
from education_system.systems.sixth_form.domain.learners.alumni.compliance import PROTECTED_CHARS
from education_system.systems.sixth_form.domain.learners.alumni.engagement import (
    CHAPTER_KINDS,
    MILESTONE_KINDS,
)
from education_system.systems.sixth_form.domain.learners.alumni.comms import (
    COMM_CHANNELS,
    COMM_STATUSES,
)
from education_system.systems.sixth_form.domain.learners.alumni.db import ValidationError
from ._common import (
    _ask_choice,
    _money_str,
    _pick_alumnus_dialog,
    _prompt_string,
    _today,
)
from education_system.platform.delivery.gui.parented_dialogs import make_toplevel


# ══ Campaigns tab (top-level) ════════════════════════════════════

class CampaignsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Campaigns")
        cols = ("id", "name", "status", "target", "raised",
                "pledged", "donors")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "name": 240, "status": 110,
                  "target": 110, "raised": 110, "pledged": 110,
                  "donors": 80}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8,
                                                  pady=(0, 8))
        ttk.Button(bar, text="New campaign",
                    command=self._add).pack(side="left")
        ttk.Button(bar, text="Set status",
                    command=self._set_status).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for c in alumni_fundraising.list_campaigns():
            t = alumni_fundraising.campaign_totals(c.campaign_id)
            self.tree.insert("", "end", iid=str(c.campaign_id),
                              values=(c.campaign_id, c.name, c.status,
                                       _money_str(c.target_pence),
                                       _money_str(t.raised_pence),
                                       _money_str(t.pledged_open_pence),
                                       t.donor_count))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _add(self) -> None:
        CampaignDialog(self.frame.winfo_toplevel(),
                         on_save=self.refresh)

    def _set_status(self) -> None:
        cid = self._selected_id()
        if cid is None: return
        StatusPickerDialog(
            self.frame.winfo_toplevel(),
            title="Campaign status",
            options=CAMPAIGN_STATUSES,
            on_pick=lambda s: (
                alumni_fundraising.update_campaign_status(cid, s), self.refresh()))

    def _delete(self) -> None:
        cid = self._selected_id()
        if cid is None: return
        if messagebox.askyesno(
                "Delete campaign",
                "Donations / pledges will keep their history but "
                "lose the campaign link. Continue?"):
            alumni_fundraising.delete_campaign(cid)
            self.refresh()


class CampaignDialog:
    def __init__(self, parent: tk.Misc,
                 on_save: Callable[[], None]) -> None:
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("New campaign")
        self.win.transient(parent); grab_when_viewable(self.win)
        form = ttk.Frame(self.win, padding=12); form.pack(fill="both",
                                                              expand=True)
        r = 0

        def row(label: str, w: tk.Widget) -> None:
            nonlocal r
            ttk.Label(form, text=label).grid(row=r, column=0,
                                                sticky="e", pady=3)
            w.grid(row=r, column=1, sticky="w", padx=6)
            r += 1

        self.name_e = ttk.Entry(form, width=40)
        self.desc_t = tk.Text(form, width=40, height=3)
        self.target_e = ttk.Entry(form, width=12)
        self.start_e = ttk.Entry(form, width=14)
        self.end_e = ttk.Entry(form, width=14)
        self.status_cb = ttk.Combobox(form, values=CAMPAIGN_STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set(DEFAULT_CAMPAIGN_STATUS)
        row("Name:",      self.name_e)
        ttk.Label(form, text="Description:").grid(row=r, column=0,
                                                       sticky="ne",
                                                       pady=3)
        self.desc_t.grid(row=r, column=1, sticky="w", padx=6); r += 1
        row("Target £:",  self.target_e)
        row("Start:",     self.start_e)
        row("End:",       self.end_e)
        row("Status:",    self.status_cb)
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            alumni_fundraising.create_campaign({
                "name":        self.name_e.get().strip(),
                "description": self.desc_t.get("1.0", "end").strip(),
                "target":      self.target_e.get().strip() or None,
                "start_on":    self.start_e.get().strip(),
                "end_on":      self.end_e.get().strip(),
                "status":      self.status_cb.get(),
            })
        except Exception as e:
            messagebox.showerror("Save failed", str(e)); return
        self.win.destroy()
        self.on_save()


class StatusPickerDialog:
    def __init__(self, parent: tk.Misc, *, title: str,
                 options: tuple[str, ...] | list[str],
                 on_pick: Callable[[str], None]) -> None:
        self.win = tk.Toplevel(parent)
        self.win.title(title)
        self.win.transient(parent); grab_when_viewable(self.win)
        form = ttk.Frame(self.win, padding=12); form.pack()
        cb = ttk.Combobox(form, values=list(options),
                             state="readonly", width=18)
        cb.current(0)
        cb.pack()
        bar = ttk.Frame(form); bar.pack(pady=(8, 0))
        ttk.Button(bar, text="Save", command=lambda: (
            on_pick(cb.get()), self.win.destroy())
            ).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)


# ══ Donations & pledges sub-tab ══════════════════════════════════

class DonationsTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Donations")

        ttk.Label(self.frame, text="Donations",
                    font=("TkDefaultFont", 10, "bold")
                    ).pack(anchor="w", padx=6, pady=(6, 0))
        self.don_tree = ttk.Treeview(
            self.frame,
            columns=("id", "date", "amount", "campaign", "gift_aid",
                      "method"),
            show="headings", height=8)
        widths = {"id": 50, "date": 100, "amount": 100,
                  "campaign": 200, "gift_aid": 70, "method": 130}
        for c in ("id", "date", "amount", "campaign", "gift_aid",
                   "method"):
            self.don_tree.heading(c, text=c.title())
            self.don_tree.column(c, width=widths[c], anchor="w")
        self.don_tree.pack(fill="x", padx=6, pady=4)
        dbar = ttk.Frame(self.frame); dbar.pack(fill="x", padx=6)
        ttk.Button(dbar, text="Record donation",
                    command=self._add_donation).pack(side="left")
        ttk.Button(dbar, text="Delete",
                    command=self._delete_donation).pack(side="left",
                                                           padx=4)

        ttk.Label(self.frame, text="Pledges",
                    font=("TkDefaultFont", 10, "bold")
                    ).pack(anchor="w", padx=6, pady=(12, 0))
        self.pl_tree = ttk.Treeview(
            self.frame,
            columns=("id", "pledged_on", "amount", "campaign",
                      "due_by", "status"),
            show="headings", height=6)
        widths_p = {"id": 50, "pledged_on": 110, "amount": 100,
                    "campaign": 200, "due_by": 110, "status": 100}
        for c in ("id", "pledged_on", "amount", "campaign",
                   "due_by", "status"):
            self.pl_tree.heading(c, text=c.title())
            self.pl_tree.column(c, width=widths_p[c], anchor="w")
        self.pl_tree.pack(fill="x", padx=6, pady=4)
        pbar = ttk.Frame(self.frame); pbar.pack(fill="x", padx=6,
                                                    pady=(0, 6))
        ttk.Button(pbar, text="Add pledge",
                    command=self._add_pledge).pack(side="left")
        ttk.Button(pbar, text="Set status",
                    command=self._set_pledge_status).pack(
            side="left", padx=4)
        ttk.Button(pbar, text="Delete",
                    command=self._delete_pledge).pack(side="left",
                                                         padx=4)
        self.refresh()

    def _campaign_label(self, cid: int | None) -> str:
        if cid is None:
            return "—"
        c = alumni_fundraising.get_campaign(cid)
        return f"#{cid} {c.name}" if c else f"#{cid}"

    def refresh(self) -> None:
        for i in self.don_tree.get_children(): self.don_tree.delete(i)
        for d in alumni_fundraising.list_donations(alumni_id=self.alumni_id):
            self.don_tree.insert("", "end", iid=str(d.donation_id),
                                  values=(d.donation_id, d.donation_date,
                                           _money_str(d.amount_pence),
                                           self._campaign_label(
                                               d.campaign_id),
                                           "✓" if d.gift_aid else "",
                                           d.payment_method or "—"))
        for i in self.pl_tree.get_children(): self.pl_tree.delete(i)
        for p in alumni_fundraising.list_pledges(alumni_id=self.alumni_id):
            self.pl_tree.insert("", "end", iid=str(p.pledge_id),
                                 values=(p.pledge_id, p.pledged_on,
                                          _money_str(p.amount_pence),
                                          self._campaign_label(
                                              p.campaign_id),
                                          p.due_by or "—", p.status))

    def _pick_campaign(self, parent: tk.Misc
                          ) -> int | None:
        campaigns = alumni_fundraising.list_campaigns()
        if not campaigns:
            return None
        win = tk.Toplevel(parent); win.title("Campaign")
        win.transient(parent); grab_when_viewable(win)
        form = ttk.Frame(win, padding=12); form.pack()
        choices = ["(none)"] + [f"#{c.campaign_id} {c.name}"
                                  for c in campaigns]
        cb = ttk.Combobox(form, values=choices, state="readonly",
                             width=40)
        cb.current(0)
        cb.pack()
        chosen: dict[str, int | None] = {"id": None}

        def ok() -> None:
            idx = cb.current()
            chosen["id"] = (campaigns[idx - 1].campaign_id
                              if idx > 0 else None)
            win.destroy()

        bar = ttk.Frame(form); bar.pack(pady=(8, 0))
        ttk.Button(bar, text="Pick", command=ok).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=win.destroy).pack(side="left", padx=8)
        win.wait_window()
        return chosen["id"]

    def _add_donation(self) -> None:
        cid = self._pick_campaign(self.frame.winfo_toplevel())
        win = tk.Toplevel(self.frame.winfo_toplevel())
        win.title("Record donation")
        win.transient(self.frame.winfo_toplevel()); grab_when_viewable(win)
        form = ttk.Frame(win, padding=12); form.pack()
        date_e = ttk.Entry(form, width=14); date_e.insert(0, _today())
        amt_e  = ttk.Entry(form, width=12)
        method_cb = ttk.Combobox(form, values=("",) + PAYMENT_METHODS,
                                    state="readonly", width=18)
        ga_var  = tk.BooleanVar(value=False)
        an_var  = tk.BooleanVar(value=False)
        rest_e  = ttk.Entry(form, width=30)
        notes_e = ttk.Entry(form, width=30)
        rows = (("Date", date_e), ("Amount £", amt_e),
                ("Payment method", method_cb),
                ("Restricted to", rest_e), ("Notes", notes_e))
        for i, (lbl, w) in enumerate(rows):
            ttk.Label(form, text=lbl + ":").grid(row=i, column=0,
                                                      sticky="e",
                                                      pady=3)
            w.grid(row=i, column=1, sticky="w", padx=6)
        ttk.Checkbutton(form, text="Gift Aid",
                          variable=ga_var).grid(row=len(rows),
                                                  column=1,
                                                  sticky="w", padx=6)
        ttk.Checkbutton(form, text="Anonymous",
                          variable=an_var).grid(row=len(rows) + 1,
                                                  column=1,
                                                  sticky="w", padx=6)

        def save() -> None:
            try:
                alumni_fundraising.record_donation(self.alumni_id, {
                    "amount":         amt_e.get().strip(),
                    "campaign_id":    cid,
                    "donation_date":  date_e.get().strip(),
                    "gift_aid":       ga_var.get(),
                    "payment_method": method_cb.get() or None,
                    "anonymous":      an_var.get(),
                    "restricted_to":  rest_e.get().strip(),
                    "notes":          notes_e.get().strip(),
                })
            except Exception as e:
                messagebox.showerror("Save failed", str(e)); return
            win.destroy()
            self.refresh()

        bar = ttk.Frame(form); bar.grid(row=len(rows) + 2, column=0,
                                          columnspan=2,
                                          pady=(10, 0))
        ttk.Button(bar, text="Save", command=save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=win.destroy).pack(side="left", padx=8)

    def _delete_donation(self) -> None:
        sel = self.don_tree.selection()
        if not sel: return
        if messagebox.askyesno("Delete",
                                  "Delete this donation? Irreversible."):
            alumni_fundraising.delete_donation(int(sel[0]))
            self.refresh()

    def _add_pledge(self) -> None:
        cid = self._pick_campaign(self.frame.winfo_toplevel())
        win = tk.Toplevel(self.frame.winfo_toplevel())
        win.title("Add pledge")
        win.transient(self.frame.winfo_toplevel()); grab_when_viewable(win)
        form = ttk.Frame(win, padding=12); form.pack()
        amt_e  = ttk.Entry(form, width=12)
        pdate_e = ttk.Entry(form, width=14); pdate_e.insert(0, _today())
        due_e  = ttk.Entry(form, width=14)
        status_cb = ttk.Combobox(form, values=PLEDGE_STATUSES,
                                    state="readonly", width=14)
        status_cb.set(DEFAULT_PLEDGE_STATUS)
        notes_e = ttk.Entry(form, width=30)
        for i, (lbl, w) in enumerate((("Amount £", amt_e),
                                       ("Pledged on", pdate_e),
                                       ("Due by", due_e),
                                       ("Status", status_cb),
                                       ("Notes", notes_e))):
            ttk.Label(form, text=lbl + ":").grid(row=i, column=0,
                                                      sticky="e",
                                                      pady=3)
            w.grid(row=i, column=1, sticky="w", padx=6)

        def save() -> None:
            try:
                alumni_fundraising.add_pledge(self.alumni_id, {
                    "amount":      amt_e.get().strip(),
                    "campaign_id": cid,
                    "pledged_on":  pdate_e.get().strip(),
                    "due_by":      due_e.get().strip(),
                    "status":      status_cb.get(),
                    "notes":       notes_e.get().strip(),
                })
            except Exception as e:
                messagebox.showerror("Save failed", str(e)); return
            win.destroy()
            self.refresh()

        bar = ttk.Frame(form); bar.grid(row=5, column=0, columnspan=2,
                                          pady=(10, 0))
        ttk.Button(bar, text="Save", command=save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=win.destroy).pack(side="left", padx=8)

    def _set_pledge_status(self) -> None:
        sel = self.pl_tree.selection()
        if not sel: return
        pid = int(sel[0])
        StatusPickerDialog(
            self.frame.winfo_toplevel(),
            title="Pledge status",
            options=PLEDGE_STATUSES,
            on_pick=lambda s: (
                alumni_fundraising.update_pledge_status(pid, s), self.refresh()))

    def _delete_pledge(self) -> None:
        sel = self.pl_tree.selection()
        if not sel: return
        alumni_fundraising.delete_pledge(int(sel[0]))
        self.refresh()


# ── Top-level: Recurring donations ───────────────────────────────

class RecurringDonationsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Recurring")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Status:").pack(side="left")
        self.status = ttk.Combobox(bar,
            values=["(all)", *RECURRING_STATUSES],
            state="readonly", width=10)
        self.status.set("Active"); self.status.pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                     command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="New",
                     command=self._new).pack(side="left", padx=12)
        ttk.Button(bar, text="Set status",
                     command=self._status).pack(side="left")
        ttk.Button(bar, text="Tick now",
                     command=self._tick).pack(side="left", padx=4)
        cols = ("id", "alumni_id", "amount", "frequency",
                  "next_charge_on", "status", "fails")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "alumni_id": 80, "amount": 100,
                    "frequency": 100, "next_charge_on": 130,
                    "status": 90, "fails": 60}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        s = self.status.get()
        status = None if s == "(all)" else s
        for r in alumni_fundraising.list_recurring(status=status):
            self.tree.insert("", "end", iid=str(r.schedule_id),
                values=(r.schedule_id, r.alumni_id,
                          _money_str(r.amount_pence), r.frequency,
                          r.next_charge_on, r.status, r.failure_count))

    def _selected(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _new(self) -> None:
        aid = _pick_alumnus_dialog(self.frame.winfo_toplevel())
        if aid is None: return
        dlg = tk.Toplevel(self.frame.winfo_toplevel())
        dlg.title("New recurring"); dlg.transient(
            self.frame.winfo_toplevel()); grab_when_viewable(dlg)
        frm = ttk.Frame(dlg, padding=10); frm.pack()
        ttk.Label(frm, text="Amount pence:").grid(row=0, column=0,
                                                     sticky="w")
        amt = ttk.Entry(frm, width=10); amt.grid(row=0, column=1,
                                                       sticky="w")
        ttk.Label(frm, text="Frequency:").grid(row=1, column=0,
                                                  sticky="w")
        freq = ttk.Combobox(frm, values=list(RECURRING_FREQS),
                                state="readonly", width=14)
        freq.set("Monthly"); freq.grid(row=1, column=1, sticky="w")
        ttk.Label(frm, text="Next charge (YYYY-MM-DD):").grid(
            row=2, column=0, sticky="w")
        nxt = ttk.Entry(frm, width=14); nxt.grid(row=2, column=1,
                                                       sticky="w")
        ttk.Label(frm, text="Fund code:").grid(row=3, column=0,
                                                  sticky="w")
        fund = ttk.Entry(frm, width=14); fund.grid(row=3, column=1,
                                                         sticky="w")
        ttk.Label(frm, text="Payment method:").grid(row=4, column=0,
                                                       sticky="w")
        pm = ttk.Entry(frm, width=14); pm.grid(row=4, column=1,
                                                     sticky="w")

        def ok() -> None:
            try:
                alumni_fundraising.create_recurring(aid,
                    amount_pence=int(amt.get() or "0"),
                    frequency=freq.get(),
                    next_charge_on=nxt.get() or None,
                    fund_code=fund.get() or None,
                    payment_method=pm.get() or None)
            except Exception as e:
                messagebox.showerror("Create", str(e)); return
            dlg.destroy()
            self.refresh()
        ttk.Button(frm, text="Save", command=ok).grid(
            row=5, column=1, sticky="e", pady=8)

    def _status(self) -> None:
        sid = self._selected()
        if sid is None: return
        st = _ask_choice(self.frame, "Status", list(RECURRING_STATUSES))
        if not st: return
        try:
            alumni_fundraising.set_recurring_status(sid, st)
        except Exception as e:
            messagebox.showerror("Status", str(e)); return
        self.refresh()

    def _tick(self) -> None:
        ticks = alumni_fundraising.tick_recurring()
        ok = sum(1 for t in ticks if t.success)
        messagebox.showinfo("Tick", f"{ok}/{len(ticks)} succeeded")
        self.refresh()


# ── Top-level: Donor pipeline ────────────────────────────────────

class DonorPipelineTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Donor pipeline")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Stage:").pack(side="left")
        self.stage = ttk.Combobox(bar,
            values=["(all)", *DONOR_STAGES],
            state="readonly", width=18)
        self.stage.set("(all)"); self.stage.pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                     command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="Set stage…",
                     command=self._set_stage).pack(side="left", padx=12)
        cols = ("alumni_id", "stage", "owner", "next_action",
                  "next_action_on", "capacity")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"alumni_id": 80, "stage": 140, "owner": 100,
                    "next_action": 240, "next_action_on": 130,
                    "capacity": 110}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        s = self.stage.get()
        stage = None if s == "(all)" else s
        for p in alumni_fundraising.list_donor_pipeline(stage=stage):
            self.tree.insert("", "end", iid=str(p.alumni_id),
                values=(p.alumni_id, p.stage,
                          p.owner_staff_id or "—",
                          p.next_action or "—",
                          p.next_action_on or "—",
                          _money_str(p.capacity_pence)
                          if p.capacity_pence else "—"))

    def _set_stage(self) -> None:
        aid = _pick_alumnus_dialog(self.frame.winfo_toplevel())
        if aid is None: return
        dlg = tk.Toplevel(self.frame.winfo_toplevel())
        dlg.title("Donor stage"); dlg.transient(
            self.frame.winfo_toplevel()); grab_when_viewable(dlg)
        frm = ttk.Frame(dlg, padding=10); frm.pack()
        ttk.Label(frm, text="Stage:").grid(row=0, column=0, sticky="w")
        stage = ttk.Combobox(frm, values=list(DONOR_STAGES),
                                 state="readonly", width=20)
        stage.set("Identification"); stage.grid(row=0, column=1,
                                                      sticky="w")
        ttk.Label(frm, text="Owner staff id:").grid(row=1, column=0,
                                                       sticky="w")
        owner = ttk.Entry(frm, width=20); owner.grid(row=1, column=1,
                                                           sticky="w")
        ttk.Label(frm, text="Next action:").grid(row=2, column=0,
                                                    sticky="w")
        action = ttk.Entry(frm, width=40); action.grid(row=2, column=1,
                                                             sticky="w")
        ttk.Label(frm, text="Next action on:").grid(row=3, column=0,
                                                       sticky="w")
        action_on = ttk.Entry(frm, width=14)
        action_on.grid(row=3, column=1, sticky="w")
        ttk.Label(frm, text="Capacity pence:").grid(row=4, column=0,
                                                       sticky="w")
        cap = ttk.Entry(frm, width=14); cap.grid(row=4, column=1,
                                                       sticky="w")

        def ok() -> None:
            try:
                alumni_fundraising.set_donor_stage(aid, stage.get(),
                    owner_staff_id=owner.get() or None,
                    next_action=action.get() or None,
                    next_action_on=action_on.get() or None,
                    capacity_pence=int(cap.get()) if cap.get() else None)
            except Exception as e:
                messagebox.showerror("Save", str(e)); return
            dlg.destroy()
            self.refresh()
        ttk.Button(frm, text="Save", command=ok).grid(
            row=5, column=1, sticky="e", pady=8)


# ── Top-level: Funds ─────────────────────────────────────────────

class FundsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Funds")
        cols = ("id", "code", "name", "restricted")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "code": 120, "name": 260, "restricted": 100}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8,
                                                  pady=(0, 8))
        ttk.Button(bar, text="Upsert",
                     command=self._upsert).pack(side="left")
        ttk.Button(bar, text="Totals",
                     command=self._totals).pack(side="left", padx=4)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for f in alumni_fundraising.list_funds():
            self.tree.insert("", "end", iid=str(f.fund_id),
                values=(f.fund_id, f.code, f.name,
                          "Yes" if f.restricted else "No"))

    def _upsert(self) -> None:
        dlg = tk.Toplevel(self.frame.winfo_toplevel())
        dlg.title("Fund"); dlg.transient(
            self.frame.winfo_toplevel()); grab_when_viewable(dlg)
        frm = ttk.Frame(dlg, padding=10); frm.pack()
        ttk.Label(frm, text="Code:").grid(row=0, column=0, sticky="w")
        code = ttk.Entry(frm, width=14); code.grid(row=0, column=1,
                                                         sticky="w")
        ttk.Label(frm, text="Name:").grid(row=1, column=0, sticky="w")
        name = ttk.Entry(frm, width=30); name.grid(row=1, column=1,
                                                         sticky="w")
        restr = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, text="Restricted",
                          variable=restr).grid(row=2, column=1, sticky="w")

        def ok() -> None:
            try:
                alumni_fundraising.upsert_fund(code.get(), name.get(),
                                    restricted=restr.get())
            except Exception as e:
                messagebox.showerror("Save", str(e)); return
            dlg.destroy()
            self.refresh()
        ttk.Button(frm, text="Save", command=ok).grid(
            row=3, column=1, sticky="e", pady=8)

    def _totals(self) -> None:
        win = make_toplevel(self.frame.winfo_toplevel())
        win.title("Fund totals"); win.geometry("600x400")
        cols = ("code", "name", "restricted", "raised")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        widths = {"code": 120, "name": 220, "restricted": 100,
                    "raised": 120}
        for c in cols:
            tree.heading(c, text=c.title())
            tree.column(c, width=widths[c], anchor="w")
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        for t in alumni_fundraising.fund_totals():
            tree.insert("", "end",
                values=(t.fund_code, t.fund_name,
                          "Yes" if t.restricted else "No",
                          _money_str(t.raised_pence)))


# ── Top-level: Bequests ──────────────────────────────────────────

class BequestsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Bequests")
        cols = ("id", "alumni_id", "estimated", "status",
                  "confirmed_on", "realised_on", "executor")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "alumni_id": 80, "estimated": 120,
                    "status": 100, "confirmed_on": 120,
                    "realised_on": 120, "executor": 200}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8,
                                                  pady=(0, 8))
        ttk.Button(bar, text="Add",
                     command=self._add).pack(side="left")
        ttk.Button(bar, text="Set status",
                     command=self._status).pack(side="left", padx=4)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for b in alumni_fundraising.list_bequests():
            self.tree.insert("", "end", iid=str(b.bequest_id),
                values=(b.bequest_id, b.alumni_id,
                          _money_str(b.estimated_pence) if b.estimated_pence
                          else "—",
                          b.status, b.confirmed_on or "—",
                          b.realised_on or "—",
                          b.executor_name or "—"))

    def _selected(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _add(self) -> None:
        aid = _pick_alumnus_dialog(self.frame.winfo_toplevel())
        if aid is None: return
        dlg = tk.Toplevel(self.frame.winfo_toplevel())
        dlg.title("Bequest"); dlg.transient(
            self.frame.winfo_toplevel()); grab_when_viewable(dlg)
        frm = ttk.Frame(dlg, padding=10); frm.pack()
        ttk.Label(frm, text="Estimated pence:").grid(row=0, column=0,
                                                        sticky="w")
        est = ttk.Entry(frm, width=14); est.grid(row=0, column=1,
                                                       sticky="w")
        ttk.Label(frm, text="Executor name:").grid(row=1, column=0,
                                                      sticky="w")
        en = ttk.Entry(frm, width=30); en.grid(row=1, column=1,
                                                     sticky="w")
        ttk.Label(frm, text="Executor email:").grid(row=2, column=0,
                                                       sticky="w")
        ee = ttk.Entry(frm, width=30); ee.grid(row=2, column=1,
                                                     sticky="w")
        ttk.Label(frm, text="Confirmed on:").grid(row=3, column=0,
                                                     sticky="w")
        co = ttk.Entry(frm, width=14); co.grid(row=3, column=1,
                                                     sticky="w")

        def ok() -> None:
            try:
                alumni_fundraising.add_bequest(aid,
                    estimated_pence=int(est.get()) if est.get() else None,
                    executor_name=en.get() or None,
                    executor_email=ee.get() or None,
                    confirmed_on=co.get() or None)
            except Exception as e:
                messagebox.showerror("Add", str(e)); return
            dlg.destroy()
            self.refresh()
        ttk.Button(frm, text="Save", command=ok).grid(
            row=4, column=1, sticky="e", pady=8)

    def _status(self) -> None:
        bid = self._selected()
        if bid is None: return
        st = _ask_choice(self.frame, "Status", list(BEQUEST_STATUSES))
        if not st: return
        rdate = _prompt_string(self.frame.winfo_toplevel(),
                                  "Realised on (optional)",
                                  "YYYY-MM-DD or blank:")
        try:
            alumni_fundraising.set_bequest_status(bid, st, realised_on=rdate)
        except Exception as e:
            messagebox.showerror("Status", str(e)); return
        self.refresh()


# ── Top-level: Matched giving ────────────────────────────────────

class MatchedGivingTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Matched giving")
        cols = ("id", "employer", "multiplier", "cap", "notes")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "employer": 240, "multiplier": 100,
                    "cap": 120, "notes": 240}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8,
                                                  pady=(0, 8))
        ttk.Button(bar, text="Upsert",
                     command=self._upsert).pack(side="left")
        ttk.Button(bar, text="Apply to donation…",
                     command=self._apply).pack(side="left", padx=4)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for s in alumni_fundraising.list_matched_schemes():
            self.tree.insert("", "end", iid=str(s.scheme_id),
                values=(s.scheme_id, s.employer,
                          f"×{s.multiplier}",
                          _money_str(s.cap_pence) if s.cap_pence else "—",
                          s.notes or ""))

    def _upsert(self) -> None:
        dlg = tk.Toplevel(self.frame.winfo_toplevel())
        dlg.title("Matched giving scheme"); dlg.transient(
            self.frame.winfo_toplevel()); grab_when_viewable(dlg)
        frm = ttk.Frame(dlg, padding=10); frm.pack()
        ttk.Label(frm, text="Employer:").grid(row=0, column=0,
                                                  sticky="w")
        emp = ttk.Entry(frm, width=30); emp.grid(row=0, column=1,
                                                       sticky="w")
        ttk.Label(frm, text="Multiplier:").grid(row=1, column=0,
                                                   sticky="w")
        mult = ttk.Entry(frm, width=10); mult.insert(0, "1.0")
        mult.grid(row=1, column=1, sticky="w")
        ttk.Label(frm, text="Cap pence (optional):").grid(
            row=2, column=0, sticky="w")
        cap = ttk.Entry(frm, width=14); cap.grid(row=2, column=1,
                                                       sticky="w")

        def ok() -> None:
            try:
                alumni_fundraising.upsert_matched_scheme(emp.get(),
                    multiplier=float(mult.get() or "1.0"),
                    cap_pence=int(cap.get()) if cap.get() else None)
            except Exception as e:
                messagebox.showerror("Save", str(e)); return
            dlg.destroy()
            self.refresh()
        ttk.Button(frm, text="Save", command=ok).grid(
            row=3, column=1, sticky="e", pady=8)

    def _apply(self) -> None:
        did = _prompt_string(self.frame.winfo_toplevel(),
                                "Donation id", "ID:")
        if not did: return
        try:
            matched = alumni_fundraising.auto_apply_matched_giving(int(did))
        except Exception as e:
            messagebox.showerror("Apply", str(e)); return
        messagebox.showinfo("Apply",
                               f"Matched {_money_str(matched)}")


# ── Per-alumnus: Gift Aid ────────────────────────────────────────

class GiftAidTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Gift Aid")
        self.status_lbl = ttk.Label(self.frame, text="",
                                       font=("TkDefaultFont", 11, "bold"))
        self.status_lbl.pack(anchor="w", padx=8, pady=(8, 4))
        frm = ttk.Frame(self.frame, padding=8); frm.pack(fill="x")
        ttk.Label(frm, text="Valid from:").grid(row=0, column=0,
                                                   sticky="w")
        self.vfrom = ttk.Entry(frm, width=14); self.vfrom.grid(
            row=0, column=1, sticky="w")
        ttk.Label(frm, text="Valid until:").grid(row=1, column=0,
                                                    sticky="w")
        self.vuntil = ttk.Entry(frm, width=14); self.vuntil.grid(
            row=1, column=1, sticky="w")
        ttk.Label(frm, text="Full name:").grid(row=2, column=0,
                                                  sticky="w")
        self.name = ttk.Entry(frm, width=30); self.name.grid(
            row=2, column=1, sticky="w")
        ttk.Label(frm, text="Address:").grid(row=3, column=0, sticky="w")
        self.addr = ttk.Entry(frm, width=30); self.addr.grid(
            row=3, column=1, sticky="w")
        ttk.Label(frm, text="Postcode:").grid(row=4, column=0,
                                                 sticky="w")
        self.pc = ttk.Entry(frm, width=14); self.pc.grid(
            row=4, column=1, sticky="w")
        bar = ttk.Frame(frm); bar.grid(row=5, column=0, columnspan=2,
                                          pady=8, sticky="w")
        ttk.Button(bar, text="Add declaration",
                     command=self._add).pack(side="left")
        self.refresh()

    def refresh(self) -> None:
        g = alumni_fundraising.get_active_gift_aid(self.alumni_id)
        if g:
            self.status_lbl.configure(
                text=f"Active declaration #{g.declaration_id} "
                     f"({g.valid_from} → "
                     f"{g.valid_until or 'open'})",
                foreground="#2a7")
        else:
            self.status_lbl.configure(
                text="No active declaration", foreground="#a44")

    def _add(self) -> None:
        try:
            alumni_fundraising.add_gift_aid_declaration(self.alumni_id,
                valid_from=self.vfrom.get(),
                valid_until=self.vuntil.get() or None,
                full_name=self.name.get(),
                address=self.addr.get(),
                postcode=self.pc.get())
        except Exception as e:
            messagebox.showerror("Add", str(e)); return
        for w in (self.vfrom, self.vuntil, self.name,
                    self.addr, self.pc):
            w.delete(0, "end")
        self.refresh()
