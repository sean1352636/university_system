"""Safeguarding, reunion planner, NEET, data quality, dedupe, erasure, webhooks, custom fields, HESA, protected characteristics, custom values, media."""

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
    compliance as alumni_compliance,
    events as alumni_events,
    integrations as alumni_integrations,
    mentoring as alumni_mentoring,
    outcomes as alumni_outcomes,
    records as alumni_records,
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
    _pick_alumnus_dialog,
    _prompt_string,
)
from education_system.platform.delivery.gui.parented_dialogs import make_toplevel


# ── Per-alumnus: Safeguarding ────────────────────────────────────

class SafeguardingTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Safeguarding")
        frm = ttk.Frame(self.frame, padding=10); frm.pack(fill="x")
        rows = [
            ("DBS reference", "dbs_reference"),
            ("DBS issued (YYYY-MM-DD)", "dbs_issued_on"),
            ("DBS expires (YYYY-MM-DD)", "dbs_expires_on"),
            ("Training done (YYYY-MM-DD)", "training_done_on"),
            ("Training expires (YYYY-MM-DD)", "training_expires_on"),
            ("Notes", "notes"),
        ]
        self.entries: dict[str, ttk.Entry] = {}
        for i, (lbl, key) in enumerate(rows):
            ttk.Label(frm, text=lbl + ":").grid(row=i, column=0,
                                                    sticky="w")
            e = ttk.Entry(frm, width=32); e.grid(row=i, column=1,
                                                       sticky="w", pady=2)
            self.entries[key] = e
        self.status_lbl = ttk.Label(frm, text="",
                                       font=("TkDefaultFont", 11, "bold"))
        self.status_lbl.grid(row=len(rows), column=0, columnspan=2,
                               sticky="w", pady=(8, 0))
        bar = ttk.Frame(frm); bar.grid(row=len(rows) + 1, column=0,
                                          columnspan=2, pady=8,
                                          sticky="w")
        ttk.Button(bar, text="Save",
                     command=self._save).pack(side="left")
        ttk.Button(bar, text="Refresh",
                     command=self.refresh).pack(side="left", padx=4)
        self.refresh()

    def refresh(self) -> None:
        sg = alumni_mentoring.get_mentor_safeguarding(self.alumni_id)
        for e in self.entries.values():
            e.delete(0, "end")
        if sg is None:
            self.status_lbl.configure(text="(no record)",
                                          foreground="#888")
        else:
            self.entries["dbs_reference"].insert(0, sg.dbs_reference or "")
            self.entries["dbs_issued_on"].insert(0, sg.dbs_issued_on or "")
            self.entries["dbs_expires_on"].insert(0, sg.dbs_expires_on or "")
            self.entries["training_done_on"].insert(
                0, sg.training_done_on or "")
            self.entries["training_expires_on"].insert(
                0, sg.training_expires_on or "")
            self.entries["notes"].insert(0, sg.notes or "")
            colour = {
                "Cleared": "#2a7", "Pending": "#888",
                "Expiring Soon": "#c80", "Expired": "#a33",
                "Suspended": "#a33"}.get(sg.status, "#666")
            self.status_lbl.configure(text=f"Status: {sg.status}",
                                          foreground=colour)

    def _save(self) -> None:
        try:
            alumni_mentoring.upsert_mentor_safeguarding(
                self.alumni_id,
                **{k: (e.get() or None)
                    for k, e in self.entries.items()})
        except Exception as e:
            messagebox.showerror("Save", str(e)); return
        self.refresh()


# ── Top-level: Safeguarding alerts (cross-alumni) ────────────────

class SafeguardingAlertsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Safeguarding alerts")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Within days:").pack(side="left")
        self.days = ttk.Entry(bar, width=6); self.days.insert(0, "60")
        self.days.pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                     command=self.refresh).pack(side="left", padx=4)
        cols = ("alumni_id", "status", "dbs_expires",
                  "training_expires", "notes")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"alumni_id": 80, "status": 130,
                    "dbs_expires": 120, "training_expires": 130,
                    "notes": 360}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        try:
            d = int(self.days.get() or "60")
        except ValueError:
            messagebox.showerror("Days", "Must be a number"); return
        for s in alumni_mentoring.list_safeguarding_alerts(days=d):
            self.tree.insert(
                "", "end", iid=str(s.alumni_id),
                values=(s.alumni_id, s.status,
                          s.dbs_expires_on or "—",
                          s.training_expires_on or "—",
                          s.notes or ""))


# ══ Events / fundraising / outcomes (items 27–40) ═════════════════

# ── Top-level: Reunion planner ───────────────────────────────────

class ReunionPlannerTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Reunions")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Horizon (months):").pack(side="left")
        self.months = ttk.Entry(bar, width=6); self.months.insert(0, "18")
        self.months.pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                     command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="Create draft events",
                     command=self._create).pack(side="left", padx=12)
        cols = ("proposed_date", "name", "years", "cohort")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"proposed_date": 130, "name": 360, "years": 70,
                    "cohort": 80}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        try:
            m = int(self.months.get() or "18")
        except ValueError:
            return
        for s in alumni_events.suggest_reunions(horizon_months=m):
            self.tree.insert("", "end",
                values=(s.proposed_date, s.proposed_name,
                          s.years_since, s.cohort_size))

    def _create(self) -> None:
        try:
            m = int(self.months.get() or "18")
        except ValueError:
            return
        created = alumni_events.create_reunion_events(horizon_months=m)
        messagebox.showinfo("Reunion planner",
                               f"Created {len(created)} draft event(s)")


# ── Top-level: NEET tracking ─────────────────────────────────────

class NEETTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="NEET")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Leaving year:").pack(side="left")
        self.year = ttk.Entry(bar, width=8); self.year.pack(side="left",
                                                                 padx=4)
        ttk.Button(bar, text="Refresh",
                     command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="Record check…",
                     command=self._record).pack(side="left", padx=12)
        cols = ("months", "cohort", "neet", "not_neet",
                  "unknown", "rate")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"months": 80, "cohort": 80, "neet": 80,
                    "not_neet": 100, "unknown": 80, "rate": 100}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for r in alumni_outcomes.neet_breakdown(
                leaving_year=self.year.get().strip() or None):
            self.tree.insert("", "end",
                values=(f"{r.months_after}m", r.cohort, r.neet,
                          r.not_neet, r.unknown,
                          f"{r.neet_rate_pct}%"))

    def _record(self) -> None:
        aid = _pick_alumnus_dialog(self.frame.winfo_toplevel())
        if aid is None: return
        dlg = tk.Toplevel(self.frame.winfo_toplevel())
        dlg.title("NEET check"); dlg.transient(
            self.frame.winfo_toplevel()); grab_when_viewable(dlg)
        frm = ttk.Frame(dlg, padding=10); frm.pack()
        ttk.Label(frm, text="Months after:").grid(row=0, column=0,
                                                     sticky="w")
        m = ttk.Combobox(frm, values=["3", "6", "12", "24"],
                            state="readonly", width=6)
        m.set("3"); m.grid(row=0, column=1, sticky="w")
        ttk.Label(frm, text="Status:").grid(row=1, column=0, sticky="w")
        st = ttk.Combobox(frm, values=list(NEET_STATUSES),
                              state="readonly", width=20)
        st.set("In Education"); st.grid(row=1, column=1, sticky="w")

        def ok() -> None:
            try:
                alumni_outcomes.record_neet_check(aid,
                    months_after=int(m.get()), status=st.get())
            except Exception as e:
                messagebox.showerror("Record", str(e)); return
            dlg.destroy()
            self.refresh()
        ttk.Button(frm, text="Save", command=ok).grid(
            row=2, column=1, sticky="e", pady=8)


# ── Per-alumnus: NEET checks ─────────────────────────────────────

class NEETChecksTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="NEET")
        cols = ("months", "status", "checked_on", "notes")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings", height=6)
        widths = {"months": 80, "status": 140,
                    "checked_on": 130, "notes": 320}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=4)
        ttk.Label(bar, text="Months:").pack(side="left")
        self.m = ttk.Combobox(bar, values=["3", "6", "12", "24"],
                                 state="readonly", width=5)
        self.m.set("3"); self.m.pack(side="left", padx=4)
        ttk.Label(bar, text="Status:").pack(side="left")
        self.st = ttk.Combobox(bar, values=list(NEET_STATUSES),
                                  state="readonly", width=20)
        self.st.set("In Education"); self.st.pack(side="left", padx=4)
        ttk.Button(bar, text="Record",
                     command=self._add).pack(side="left", padx=4)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for c in alumni_outcomes.list_neet_checks(self.alumni_id):
            self.tree.insert("", "end",
                values=(f"{c.months_after}m", c.status,
                          c.checked_on, c.notes or ""))

    def _add(self) -> None:
        try:
            alumni_outcomes.record_neet_check(self.alumni_id,
                months_after=int(self.m.get()),
                status=self.st.get())
        except Exception as e:
            messagebox.showerror("Record", str(e)); return
        self.refresh()


# ══ Final cluster (items 41–50) ═══════════════════════════════════

# ── Top-level: Data quality dashboard ────────────────────────────

class DataQualityTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Quality")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8, pady=8)
        ttk.Button(bar, text="Refresh",
                     command=self.refresh).pack(side="left")
        self.text = tk.Text(self.frame, height=18, wrap="word",
                              state="disabled")
        self.text.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        q = alumni_compliance.data_quality_report()
        body = (
            f"Total active alumni: {q.total}\n\n"
            f"  Email on file:               {q.with_email_pct}%\n"
            f"  Phone on file:               {q.with_phone_pct}%\n"
            f"  Postal address on file:      {q.with_address_pct}%\n"
            f"  Missing destination:         {q.missing_destination_pct}%\n"
            f"  Stale (no contact > 24mo):   {q.stale_24mo_pct}%\n"
            f"  Hard bounces:                {q.bounce_rate_pct}%\n"
            f"  Opt-in to contact:           {q.opt_in_pct}%\n"
            f"  'Data Storage' consent:      {q.consent_data_storage_pct}%\n"
        )
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", body)
        self.text.configure(state="disabled")


# ── Top-level: Dedupe confidence buckets ─────────────────────────

class DedupeBucketsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Dedupe buckets")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8, pady=8)
        ttk.Button(bar, text="Refresh",
                     command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Batch-merge selected",
                     command=self._batch).pack(side="left", padx=8)
        cols = ("bucket", "score", "keep_id", "merge_id",
                  "keep_name", "merge_name")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"bucket": 110, "score": 70,
                    "keep_id": 70, "merge_id": 70,
                    "keep_name": 220, "merge_name": 220}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        buckets = alumni_compliance.dedupe_buckets()
        for label, rows in (("Very high", buckets.very_high),
                                ("High",      buckets.high),
                                ("Medium",    buckets.medium)):
            for c in rows:
                kp = alumni_records.get_alumnus(c.keep_id)
                mg = alumni_records.get_alumnus(c.merge_id)
                self.tree.insert("", "end",
                    iid=f"{c.keep_id}-{c.merge_id}",
                    values=(label, f"{c.score:.2f}",
                              c.keep_id, c.merge_id,
                              kp.full_name if kp else "—",
                              mg.full_name if mg else "—"))

    def _batch(self) -> None:
        sel = self.tree.selection()
        if not sel: return
        pairs: list[tuple[int, int]] = []
        for iid in sel:
            vals = self.tree.item(iid, "values")
            pairs.append((int(vals[2]), int(vals[3])))
        if not messagebox.askyesno(
                "Batch merge",
                f"Merge {len(pairs)} pair(s)? This is irreversible."):
            return
        ok, errs = alumni_compliance.batch_confirm_merges(pairs)
        messagebox.showinfo("Batch merge",
                               f"Merged {ok}, {len(errs)} error(s)")
        self.refresh()


# ── Top-level: Erasure workflow ──────────────────────────────────

class ErasureTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Erasure")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Status:").pack(side="left")
        self.status = ttk.Combobox(bar,
            values=["(all)", *ERASURE_STATUSES],
            state="readonly", width=18)
        self.status.set("(all)"); self.status.pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                     command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="New request",
                     command=self._new).pack(side="left", padx=12)
        ttk.Button(bar, text="Review",
                     command=self._review).pack(side="left")
        ttk.Button(bar, text="Complete",
                     command=self._complete).pack(side="left", padx=4)
        cols = ("id", "alumni_id", "status", "requested_at",
                  "reviewer", "completed_at")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "alumni_id": 80, "status": 130,
                    "requested_at": 170, "reviewer": 130,
                    "completed_at": 170}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        s = self.status.get()
        status = None if s == "(all)" else s
        for r in alumni_compliance.list_erasure_requests(status=status):
            self.tree.insert("", "end", iid=str(r.request_id),
                values=(r.request_id, r.alumni_id, r.status,
                          r.requested_at, r.reviewer or "—",
                          r.completed_at or "—"))

    def _selected(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _new(self) -> None:
        aid = _pick_alumnus_dialog(self.frame.winfo_toplevel())
        if aid is None: return
        reason = _prompt_string(self.frame.winfo_toplevel(),
                                   "Reason", "Reason (optional):")
        try:
            alumni_compliance.request_erasure(aid, reason=reason)
        except Exception as e:
            messagebox.showerror("Request", str(e)); return
        self.refresh()

    def _review(self) -> None:
        rid = self._selected()
        if rid is None: return
        reviewer = _prompt_string(self.frame.winfo_toplevel(),
                                     "Reviewer", "Reviewer id:")
        if not reviewer: return
        decision = _ask_choice(self.frame, "Decision",
                                  ["Approved", "Rejected"])
        if not decision: return
        try:
            alumni_compliance.review_erasure(rid, reviewer=reviewer,
                                    decision=decision)
        except Exception as e:
            messagebox.showerror("Review", str(e)); return
        self.refresh()

    def _complete(self) -> None:
        rid = self._selected()
        if rid is None: return
        if not messagebox.askyesno(
                "Complete erasure",
                "Anonymise this alumnus's record now? "
                "This cannot be undone."):
            return
        try:
            alumni_compliance.complete_erasure(rid)
        except Exception as e:
            messagebox.showerror("Complete", str(e)); return
        self.refresh()


# ── Top-level: Webhooks ──────────────────────────────────────────

class WebhooksTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Webhooks")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8, pady=8)
        ttk.Button(bar, text="New",
                     command=self._new).pack(side="left")
        ttk.Button(bar, text="Toggle active",
                     command=self._toggle).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                     command=self._delete).pack(side="left")
        ttk.Button(bar, text="Recent events",
                     command=self._events).pack(side="left", padx=12)
        cols = ("id", "url", "active", "event_types")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "url": 320, "active": 70,
                    "event_types": 400}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for w in alumni_integrations.list_webhooks():
            self.tree.insert("", "end", iid=str(w.webhook_id),
                values=(w.webhook_id, w.url,
                          "Yes" if w.active else "No",
                          ", ".join(w.event_types)))

    def _selected(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _new(self) -> None:
        dlg = tk.Toplevel(self.frame.winfo_toplevel())
        dlg.title("Register webhook"); dlg.transient(
            self.frame.winfo_toplevel()); grab_when_viewable(dlg)
        frm = ttk.Frame(dlg, padding=10); frm.pack()
        ttk.Label(frm, text="URL:").grid(row=0, column=0, sticky="w")
        url = ttk.Entry(frm, width=40); url.grid(row=0, column=1,
                                                       sticky="w")
        ttk.Label(frm, text="Secret (optional):").grid(row=1, column=0,
                                                          sticky="w")
        secret = ttk.Entry(frm, width=30); secret.grid(row=1, column=1,
                                                             sticky="w")
        ttk.Label(frm, text="Event types:").grid(row=2, column=0,
                                                    sticky="nw")
        lb = tk.Listbox(frm, selectmode="multiple",
                          height=min(len(WEBHOOK_EVENT_TYPES), 10),
                          exportselection=False)
        for ev in WEBHOOK_EVENT_TYPES:
            lb.insert("end", ev)
        lb.grid(row=2, column=1, sticky="w", pady=2)

        def ok() -> None:
            events = [WEBHOOK_EVENT_TYPES[i] for i in lb.curselection()]
            if not events:
                messagebox.showerror("Events",
                                        "Pick at least one event type")
                return
            try:
                alumni_integrations.register_webhook(url.get(),
                    event_types=events, secret=secret.get() or None)
            except Exception as e:
                messagebox.showerror("Save", str(e)); return
            dlg.destroy()
            self.refresh()
        ttk.Button(frm, text="Save", command=ok).grid(
            row=3, column=1, sticky="e", pady=8)

    def _toggle(self) -> None:
        wid = self._selected()
        if wid is None: return
        vals = self.tree.item(str(wid), "values")
        active = (vals[2] != "Yes")
        try:
            alumni_integrations.set_webhook_active(wid, active)
        except Exception as e:
            messagebox.showerror("Toggle", str(e)); return
        self.refresh()

    def _delete(self) -> None:
        wid = self._selected()
        if wid is None: return
        if not messagebox.askyesno("Delete",
                                      f"Delete webhook #{wid}?"):
            return
        alumni_integrations.delete_webhook(wid)
        self.refresh()

    def _events(self) -> None:
        win = make_toplevel(self.frame.winfo_toplevel())
        win.title("Recent webhook events"); win.geometry("800x500")
        cols = ("id", "queued_at", "event_type",
                  "delivered_at", "last_error")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        widths = {"id": 60, "queued_at": 160, "event_type": 180,
                    "delivered_at": 160, "last_error": 220}
        for c in cols:
            tree.heading(c, text=c.replace("_", " ").title())
            tree.column(c, width=widths[c], anchor="w")
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        for ev in alumni_integrations.list_recent_webhook_events(limit=100):
            tree.insert("", "end",
                values=(ev["event_id"], ev["queued_at"],
                          ev["event_type"],
                          ev["delivered_at"] or "—",
                          ev["last_error"] or ""))


# ── Top-level: Custom fields ─────────────────────────────────────

class CustomFieldsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Custom fields")
        cols = ("id", "name", "label", "type")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "name": 180, "label": 240, "type": 100}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8,
                                                  pady=(0, 8))
        ttk.Button(bar, text="Add",
                     command=self._add).pack(side="left")
        ttk.Button(bar, text="Delete",
                     command=self._delete).pack(side="left", padx=4)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for f in alumni_integrations.list_custom_fields():
            self.tree.insert("", "end", iid=str(f.field_id),
                values=(f.field_id, f.name, f.label, f.type))

    def _add(self) -> None:
        dlg = tk.Toplevel(self.frame.winfo_toplevel())
        dlg.title("Custom field"); dlg.transient(
            self.frame.winfo_toplevel()); grab_when_viewable(dlg)
        frm = ttk.Frame(dlg, padding=10); frm.pack()
        ttk.Label(frm, text="Name (machine):").grid(row=0, column=0,
                                                       sticky="w")
        name = ttk.Entry(frm, width=24); name.grid(row=0, column=1,
                                                         sticky="w")
        ttk.Label(frm, text="Label:").grid(row=1, column=0, sticky="w")
        label = ttk.Entry(frm, width=30); label.grid(row=1, column=1,
                                                          sticky="w")
        ttk.Label(frm, text="Type:").grid(row=2, column=0, sticky="w")
        tp = ttk.Combobox(frm, values=list(CUSTOM_FIELD_TYPES),
                              state="readonly", width=12)
        tp.set("text"); tp.grid(row=2, column=1, sticky="w")

        def ok() -> None:
            try:
                alumni_integrations.add_custom_field(name.get(), label.get(),
                                          type=tp.get())
            except Exception as e:
                messagebox.showerror("Add", str(e)); return
            dlg.destroy()
            self.refresh()
        ttk.Button(frm, text="Save", command=ok).grid(
            row=3, column=1, sticky="e", pady=8)

    def _delete(self) -> None:
        sel = self.tree.selection()
        if not sel: return
        fid = int(sel[0])
        if not messagebox.askyesno("Delete",
                                      f"Delete field #{fid} and all "
                                      "associated values?"):
            return
        alumni_integrations.delete_custom_field(fid)
        self.refresh()


# ── Top-level: HESA benchmarks ───────────────────────────────────

class HESATab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="HESA")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Compare year:").pack(side="left")
        self.year = ttk.Entry(bar, width=8)
        self.year.pack(side="left", padx=4)
        ttk.Button(bar, text="Compare",
                     command=self._compare).pack(side="left", padx=4)
        ttk.Button(bar, text="Upsert benchmark…",
                     command=self._upsert).pack(side="left", padx=12)
        cols = ("metric", "secondary", "hesa", "delta")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"metric": 180, "secondary": 100, "hesa": 100,
                    "delta": 100}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)

    def _compare(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        year = self.year.get().strip()
        if not year:
            messagebox.showerror("Year", "Pick a year"); return
        for d in alumni_outcomes.compare_with_hesa(year):
            sign = "+" if d.delta_pct >= 0 else ""
            self.tree.insert("", "end",
                values=(d.metric, f"{d.school_rate_pct}%",
                          f"{d.hesa_rate_pct}%",
                          f"{sign}{d.delta_pct}%"))

    def _upsert(self) -> None:
        dlg = tk.Toplevel(self.frame.winfo_toplevel())
        dlg.title("HESA benchmark"); dlg.transient(
            self.frame.winfo_toplevel()); grab_when_viewable(dlg)
        frm = ttk.Frame(dlg, padding=10); frm.pack()
        ttk.Label(frm, text="Leaving year:").grid(row=0, column=0,
                                                     sticky="w")
        yr = ttk.Entry(frm, width=10); yr.grid(row=0, column=1,
                                                     sticky="w")
        ttk.Label(frm, text="Metric:").grid(row=1, column=0, sticky="w")
        metric = ttk.Combobox(frm, values=[
            "he_entry", "russell_group", "oxbridge", "postgraduate"],
            state="readonly", width=18)
        metric.grid(row=1, column=1, sticky="w")
        ttk.Label(frm, text="Rate %:").grid(row=2, column=0, sticky="w")
        rate = ttk.Entry(frm, width=10); rate.grid(row=2, column=1,
                                                         sticky="w")
        ttk.Label(frm, text="Source:").grid(row=3, column=0, sticky="w")
        src = ttk.Entry(frm, width=30); src.grid(row=3, column=1,
                                                       sticky="w")

        def ok() -> None:
            try:
                alumni_outcomes.upsert_hesa_benchmark(yr.get(), metric.get(),
                    float(rate.get() or "0"), source=src.get() or None)
            except Exception as e:
                messagebox.showerror("Save", str(e)); return
            dlg.destroy()
        ttk.Button(frm, text="Save", command=ok).grid(
            row=4, column=1, sticky="e", pady=8)


# ── Per-alumnus: Protected characteristics ───────────────────────

class ProtectedCharsTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Protected")
        ttk.Label(self.frame,
                    text="Protected characteristics (used for gap reports).",
                    foreground="#666"
                    ).pack(anchor="w", padx=8, pady=(8, 4))
        frm = ttk.Frame(self.frame, padding=8); frm.pack(fill="x")
        self.vars: dict[str, tk.BooleanVar] = {}
        for i, char in enumerate(PROTECTED_CHARS):
            v = tk.BooleanVar(value=False)
            self.vars[char] = v
            ttk.Checkbutton(frm, text=char, variable=v,
                              command=lambda c=char, vv=v:
                                  self._toggle(c, vv)
                              ).grid(row=i, column=0, sticky="w", pady=2)
        ttk.Label(frm, text="Ethnicity:").grid(row=len(PROTECTED_CHARS),
                                                  column=0, sticky="w",
                                                  pady=(8, 0))
        self.ethnicity = ttk.Entry(frm, width=24)
        self.ethnicity.grid(row=len(PROTECTED_CHARS), column=1,
                                sticky="w", pady=(8, 0))
        ttk.Button(frm, text="Save ethnicity",
                     command=self._save_eth
                     ).grid(row=len(PROTECTED_CHARS) + 1, column=1,
                              sticky="w", pady=8)
        self.refresh()

    def refresh(self) -> None:
        a = alumni_records.get_alumnus(self.alumni_id)
        if a is None: return
        for char, v in self.vars.items():
            v.set(bool(getattr(a, char, 0)))
        self.ethnicity.delete(0, "end")
        self.ethnicity.insert(0, getattr(a, "ethnicity", "") or "")

    def _toggle(self, char: str, v: tk.BooleanVar) -> None:
        try:
            alumni_compliance.set_protected_characteristic(self.alumni_id, char,
                                                  v.get())
        except Exception as e:
            messagebox.showerror("Save", str(e)); self.refresh()

    def _save_eth(self) -> None:
        try:
            alumni_compliance.set_ethnicity(self.alumni_id,
                                  self.ethnicity.get() or None)
        except Exception as e:
            messagebox.showerror("Save", str(e))


# ── Per-alumnus: Custom values ───────────────────────────────────

class CustomValuesTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Custom")
        cols = ("name", "value", "type")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings", height=8)
        widths = {"name": 180, "value": 280, "type": 90}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=4)
        ttk.Label(bar, text="Field:").pack(side="left")
        self.name = ttk.Combobox(bar, state="readonly", width=20)
        self.name.pack(side="left", padx=4)
        ttk.Label(bar, text="Value:").pack(side="left")
        self.value = ttk.Entry(bar, width=24)
        self.value.pack(side="left", padx=4)
        ttk.Button(bar, text="Set",
                     command=self._set).pack(side="left", padx=4)
        self.refresh()

    def refresh(self) -> None:
        fields = alumni_integrations.list_custom_fields()
        types = {f.name: f.type for f in fields}
        self.name.configure(values=[f.name for f in fields])
        for i in self.tree.get_children(): self.tree.delete(i)
        for k, v in alumni_integrations.get_custom_values(self.alumni_id).items():
            self.tree.insert("", "end",
                values=(k, v, types.get(k, "?")))

    def _set(self) -> None:
        if not self.name.get(): return
        try:
            alumni_integrations.set_custom_value(self.alumni_id,
                                      self.name.get(),
                                      self.value.get())
        except Exception as e:
            messagebox.showerror("Set", str(e)); return
        self.value.delete(0, "end")
        self.refresh()


# ── Per-alumnus: Media attachments ───────────────────────────────

class MediaTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Media")
        cols = ("id", "kind", "profile", "consent",
                  "exif_stripped", "file_path")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings", height=8)
        widths = {"id": 50, "kind": 100, "profile": 70,
                    "consent": 70, "exif_stripped": 100,
                    "file_path": 360}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=4)
        ttk.Button(bar, text="Attach…",
                     command=self._attach).pack(side="left")
        ttk.Button(bar, text="Set as profile",
                     command=self._profile).pack(side="left", padx=4)
        ttk.Button(bar, text="Toggle consent",
                     command=self._consent).pack(side="left")
        ttk.Button(bar, text="Delete",
                     command=self._delete).pack(side="left", padx=4)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for m in alumni_integrations.list_media(self.alumni_id):
            self.tree.insert("", "end", iid=str(m.media_id),
                values=(m.media_id, m.kind,
                          "★" if m.is_profile else "",
                          "Y" if m.consent_granted else "N",
                          "Y" if m.exif_stripped else "N",
                          m.file_path))

    def _selected(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _attach(self) -> None:
        from education_system.platform.delivery.gui.parented_dialogs import filedialog as _fd
        path = _fd.askopenfilename(parent=self.frame.winfo_toplevel())
        if not path: return
        kind = _ask_choice(self.frame, "Kind", list(MEDIA_KINDS),
                              default="photo")
        if not kind: return
        consent = messagebox.askyesno("Consent",
                                          "Has the alumnus granted "
                                          "consent for this image?")
        try:
            alumni_integrations.attach_media(self.alumni_id, path, kind=kind,
                consent_granted=consent, strip_exif=True)
        except Exception as e:
            messagebox.showerror("Attach", str(e)); return
        self.refresh()

    def _profile(self) -> None:
        mid = self._selected()
        if mid is None: return
        try:
            alumni_integrations.set_profile_media(self.alumni_id, mid)
        except Exception as e:
            messagebox.showerror("Profile", str(e)); return
        self.refresh()

    def _consent(self) -> None:
        mid = self._selected()
        if mid is None: return
        m = next((x for x in alumni_integrations.list_media(self.alumni_id)
                    if x.media_id == mid), None)
        if not m: return
        try:
            alumni_integrations.set_media_consent(mid, not m.consent_granted)
        except Exception as e:
            messagebox.showerror("Consent", str(e)); return
        self.refresh()

    def _delete(self) -> None:
        mid = self._selected()
        if mid is None: return
        delfile = messagebox.askyesno("Delete",
                                          "Also delete file from disk?")
        alumni_integrations.delete_media(mid, delete_file=delfile)
        self.refresh()
