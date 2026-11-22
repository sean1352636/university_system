"""Admissions window page: archived and merged applicants.

Archived records are hidden from every applicant list but keep
everything; restoring brings them back. A record merged into another
cannot be restored (its rows live on the kept record now). Any of them
can be opened read-only: details and the full timeline.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from education_system.platform.delivery.gui.parented_dialogs import (
    make_toplevel,
    messagebox,
)
from education_system.systems.sixth_form.domain.admissions import (
    admissions as adm,
    record_safety,
)
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)
from education_system.systems.sixth_form.interfaces.gui.admissions import (
    pages_common as pc,
)

TITLE = "Archive"

_DETAIL_FIELDS = (
    ("applicant_id", "Applicant ID"), ("first_name", "First name"),
    ("last_name", "Last name"), ("dob", "Date of birth"), ("email", "Email"),
    ("phone", "Phone"), ("address", "Address"),
    ("previous_school", "Previous school"), ("intake_year", "Intake"),
    ("status", "Status"), ("application_source", "Source"),
    ("submitted_at", "Submitted"), ("subject_1", "Subject 1"),
    ("subject_2", "Subject 2"), ("subject_3", "Subject 3"),
    ("predicted_gcses", "Predicted GCSEs"), ("offer_type", "Offer type"),
    ("offer_conditions", "Offer conditions"),
    ("decision_reason", "Decision reason"),
    ("withdrawal_reason", "Withdrawal reason"),
    ("deferred_from", "Deferred from"), ("archived_at", "Archived"),
    ("archived_by", "Archived by"), ("archive_reason", "Archive reason"),
    ("merged_into", "Merged into"), ("created_at", "Created"),
    ("updated_at", "Last changed"),
)


def open_read_only(parent: tk.Misc, applicant_id: str) -> None:
    """A read-only view of one applicant: details and timeline."""
    ok, a = pc.run(parent, TITLE, adm.get_applicant, applicant_id)
    if not ok:
        return
    if a is None:
        messagebox.showinfo(TITLE, f"No applicant {applicant_id}.",
                            parent=parent.winfo_toplevel())
        return
    ok, events = pc.run(parent, TITLE, adm.list_events, applicant_id)
    win = make_toplevel(parent.winfo_toplevel())
    win.title(f"{a.applicant_id} — {a.full_name} (read-only)")
    win.geometry("1000x680")
    foot = ttk.Frame(win, padding=8)
    foot.pack(side="bottom", fill="x")
    ttk.Button(foot, text="Close", command=win.destroy).pack(side="left")
    state = ("merged into " + a.merged_into if a.merged_into
             else "archived" if a.is_archived else "live")
    ttk.Label(win, text=f"{a.full_name} — {a.status} ({state})",
              font=("TkDefaultFont", 12, "bold"), padding=(8, 8, 8, 2)).pack(
        side="top", anchor="w")
    pane = ttk.PanedWindow(win, orient="horizontal")
    pane.pack(fill="both", expand=True, padx=8, pady=4)
    left = ttk.LabelFrame(pane, text="Details", padding=4)
    right = ttk.LabelFrame(pane, text="Timeline", padding=4)
    pane.add(left, weight=1)
    pane.add(right, weight=1)
    details = pc.make_tree(left, [("field", "Field", 140),
                                  ("value", "Value", 280)], height=20)
    for i, (key, label) in enumerate(_DETAIL_FIELDS):
        value = getattr(a, key, None)
        if value not in (None, ""):
            details.insert("", "end", iid=str(i), values=(
                label, str(value).replace("\n", " ")))
    timeline = pc.make_tree(right, [("at", "When", 140), ("kind", "Kind", 70),
                                    ("who", "By", 90),
                                    ("detail", "What", 320)], height=20)
    for e in events or []:
        timeline.insert("", "end", iid=str(e.id), values=(
            e.at, e.kind, e.actor or "", e.detail.replace("\n", " ")))


class ArchivePage:
    COLS = [("id", "ID", 90), ("name", "Name", 180), ("status", "Status", 120),
            ("intake", "Intake", 70), ("at", "Archived", 140),
            ("by", "By", 100), ("reason", "Reason", 280),
            ("merged", "Merged into", 90)]

    def __init__(self, nb: Any) -> None:
        self.frame = pc.new_page(
            nb, TITLE, "Archived and merged applicants",
            "Archived records are hidden from the applicant lists and cannot "
            "be edited until restored. Merged duplicates stay here for the "
            "record; their data is on the kept applicant.")
        self.editable = pc.can(access.ADMISSIONS)
        bar = ttk.Frame(self.frame)
        bar.pack(side="top", fill="x", pady=(0, 4))
        ttk.Button(bar, text="Open (read-only)", command=self._open).pack(
            side="left", padx=(0, 4))
        ttk.Button(bar, text="Restore…", command=self._restore,
                   state="normal" if self.editable else "disabled").pack(
            side="left", padx=(0, 4))
        ttk.Label(bar, text="Show:").pack(side="left", padx=(12, 2))
        self.kind = ttk.Combobox(bar, state="readonly", width=16,
                                 values=("All", "Archived only",
                                         "Merged only"))
        self.kind.set("All")
        self.kind.pack(side="left")
        self.kind.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        ttk.Label(bar, text="Search:").pack(side="left", padx=(12, 2))
        self.search = ttk.Entry(bar, width=24)
        self.search.pack(side="left")
        self.search.bind("<KeyRelease>", lambda _e: self.refresh())
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(
            side="right")
        self.status = pc.status_line(self.frame)
        self.tree = pc.make_tree(self.frame, self.COLS, height=18)
        self.tree.tag_configure("merged", foreground="#777")
        self.tree.bind("<Double-1>", lambda _e: self._open())
        self._rows: dict[str, adm.Applicant] = {}
        self.refresh()

    def refresh(self) -> None:
        pc.clear(self.tree)
        ok, rows = pc.load(self.status, TITLE, record_safety.list_archived)
        if not ok:
            return
        kind = self.kind.get()
        needle = self.search.get().strip().lower()
        self._rows = {}
        merged = 0
        for a in rows:
            if kind == "Archived only" and a.merged_into:
                continue
            if kind == "Merged only" and not a.merged_into:
                continue
            if needle and needle not in (f"{a.applicant_id} {a.full_name} "
                                         f"{a.email or ''}").lower():
                continue
            merged += bool(a.merged_into)
            self._rows[a.applicant_id] = a
            self.tree.insert("", "end", iid=a.applicant_id,
                             tags=("merged",) if a.merged_into else (),
                             values=(a.applicant_id, a.full_name, a.status,
                                     a.intake_year or "", a.archived_at or "",
                                     a.archived_by or "",
                                     (a.archive_reason or "").replace(
                                         "\n", " "), a.merged_into or ""))
        self.status.set(f"{len(self._rows)} shown · {merged} merged")

    def _open(self) -> None:
        aid = pc.selected(self.tree, TITLE)
        if aid:
            open_read_only(self.frame, aid)

    def _restore(self) -> None:
        aid = pc.selected(self.tree, TITLE)
        if not aid:
            return
        a = self._rows.get(aid)
        if a is not None and not a.merged_into and not messagebox.askyesno(
                TITLE, f"Restore {aid} {a.full_name}? It returns to the "
                f"applicant lists at {a.status}.",
                parent=self.frame.winfo_toplevel()):
            return
        ok, _ = pc.run(self.frame, TITLE, record_safety.restore_applicant, aid)
        if ok:
            self.refresh()
