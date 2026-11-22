"""Shared helpers for the Sixth Form alumni views (split from alumni_views)."""

from __future__ import annotations
from education_system.systems.sixth_form.interfaces.gui._ui import grab_when_viewable

import datetime as _dt
import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from typing import Any, Callable
from education_system.platform import branding
from education_system.systems.sixth_form.domain.learners.alumni import records as alumni_records
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


def _today() -> str:
    return _dt.date.today().isoformat()


def _money_str(pence: int | None) -> str:
    if pence is None:
        return "—"
    return f"£{pence / 100:,.2f}"


def _pick_alumnus_dialog(parent: tk.Misc, *,
                            exclude: int | None = None) -> int | None:
    """Modal alumnus picker. Returns the chosen alumni_id or None."""
    rows = [a for a in alumni_records.list_alumni() if a.alumni_id != exclude]
    if not rows:
        messagebox.showinfo("Pick alumnus", "No alumni available.")
        return None
    dlg = tk.Toplevel(parent)
    dlg.title("Pick alumnus")
    dlg.transient(parent)
    grab_when_viewable(dlg)
    tk.Label(dlg, text="Search:").pack(anchor="w", padx=8, pady=(8, 0))
    sv = tk.StringVar()
    ent = ttk.Entry(dlg, textvariable=sv, width=40)
    ent.pack(fill="x", padx=8)
    tree = ttk.Treeview(dlg, columns=("id", "name", "year"),
                          show="headings", height=12)
    tree.heading("id", text="ID")
    tree.heading("name", text="Name")
    tree.heading("year", text="Year")
    tree.column("id", width=60)
    tree.column("name", width=260)
    tree.column("year", width=70)
    tree.pack(fill="both", expand=True, padx=8, pady=8)
    chosen: dict[str, int | None] = {"id": None}

    def repopulate(*_: object) -> None:
        q = sv.get().strip().lower()
        for i in tree.get_children():
            tree.delete(i)
        for a in rows:
            if q and q not in a.full_name.lower() \
                    and q not in (a.leaving_year or ""):
                continue
            tree.insert("", "end", iid=str(a.alumni_id),
                         values=(a.alumni_id, a.full_name,
                                 a.leaving_year or "—"))
    sv.trace_add("write", repopulate)
    repopulate()

    def accept(_e: object = None) -> None:
        sel = tree.selection()
        if not sel: return
        chosen["id"] = int(sel[0])
        dlg.destroy()
    tree.bind("<Double-1>", accept)
    bar = ttk.Frame(dlg); bar.pack(fill="x", padx=8, pady=(0, 8))
    ttk.Button(bar, text="OK", command=accept).pack(side="right")
    ttk.Button(bar, text="Cancel",
                 command=dlg.destroy).pack(side="right", padx=4)
    ent.focus_set()
    parent.wait_window(dlg)
    return chosen["id"]


def _ask_choice(parent: tk.Misc, title: str, options: list[str], *,
                  default: str | None = None) -> str | None:
    dlg = tk.Toplevel(parent.winfo_toplevel())
    dlg.title(title); dlg.transient(parent.winfo_toplevel())
    grab_when_viewable(dlg)
    ttk.Label(dlg, text=title + ":").pack(anchor="w",
                                              padx=8, pady=(8, 0))
    var = tk.StringVar(value=default or options[0])
    cb = ttk.Combobox(dlg, values=options, textvariable=var,
                        state="readonly", width=24)
    cb.pack(padx=8, pady=8)
    out: dict[str, str | None] = {"v": None}

    def accept() -> None:
        out["v"] = var.get(); dlg.destroy()
    ttk.Button(dlg, text="OK",
                 command=accept).pack(pady=(0, 8))
    parent.winfo_toplevel().wait_window(dlg)
    return out["v"]


# ── Per-alumnus: Engagement score ────────────────────────────────

def _prompt_string(parent: tk.Misc, title: str,
                      label: str) -> str | None:
    dlg = tk.Toplevel(parent)
    dlg.title(title); dlg.transient(parent); grab_when_viewable(dlg)
    ttk.Label(dlg, text=label).pack(padx=8, pady=(8, 0), anchor="w")
    var = tk.StringVar()
    ent = ttk.Entry(dlg, textvariable=var, width=30)
    ent.pack(padx=8, pady=8); ent.focus_set()
    out: dict[str, str | None] = {"v": None}

    def ok() -> None:
        out["v"] = var.get().strip() or None
        dlg.destroy()
    ent.bind("<Return>", lambda _e: ok())
    ttk.Button(dlg, text="OK", command=ok).pack(pady=(0, 8))
    parent.wait_window(dlg)
    return out["v"]


# ── Top-level: Job postings board ────────────────────────────────
