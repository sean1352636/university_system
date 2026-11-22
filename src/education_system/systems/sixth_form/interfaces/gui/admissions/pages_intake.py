"""Admissions window page: the secondary-school intake log.

What the cross-system intake did with each progression event from a
secondary school: attached it to an existing applicant, recognised a
student already on file, created a new student, or failed (and why).
"""

from __future__ import annotations

from tkinter import ttk
from typing import Any

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.sixth_form.domain.admissions import (
    college_intake,
)
from education_system.systems.sixth_form.interfaces.gui.admissions import (
    pages_common as pc,
)
from education_system.systems.sixth_form.interfaces.gui.admissions.pages_archive import (
    open_read_only,
)

TITLE = "Intake Log"

_ACTIONS = {"attached": "Attached to applicant",
            "existing student": "Reused existing student",
            "created": "Created student", "failed": "Failed"}


class IntakeLogPage:
    COLS = [("id", "#", 45), ("at", "When", 140), ("action", "What", 170),
            ("journey", "Journey", 120), ("aid", "Applicant", 85),
            ("sid", "Student", 85), ("matched", "Matched on", 110),
            ("linked", "Linked to student", 130), ("detail", "Detail", 360)]

    def __init__(self, nb: Any) -> None:
        self.frame = pc.new_page(
            nb, TITLE, "Secondary intake log",
            "Learners progressing from a secondary school arrive here through "
            "the cross-system intake. An attached journey is linked to the "
            "student when the applicant is converted.")
        bar = ttk.Frame(self.frame)
        bar.pack(side="top", fill="x", pady=(0, 4))
        ttk.Button(bar, text="Open applicant (read-only)",
                   command=self._open).pack(side="left", padx=(0, 4))
        ttk.Label(bar, text="Show:").pack(side="left", padx=(12, 2))
        self.kind = ttk.Combobox(bar, state="readonly", width=24,
                                 values=["All"] + list(_ACTIONS.values()))
        self.kind.set("All")
        self.kind.pack(side="left")
        self.kind.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(
            side="right")
        self.status = pc.status_line(self.frame)
        self.tree = pc.make_tree(self.frame, self.COLS, height=18)
        self.tree.tag_configure("failed", background="#ffd6d6")
        self.tree.bind("<Double-1>", lambda _e: self._open())
        self._rows: dict[str, college_intake.IntakeEntry] = {}
        self.refresh()

    def refresh(self) -> None:
        pc.clear(self.tree)
        ok, rows = pc.load(self.status, TITLE, college_intake.list_intake_log,
                           limit=1000)
        if not ok:
            return
        want = self.kind.get()
        counts: dict[str, int] = {}
        self._rows = {}
        for e in rows:
            label = _ACTIONS.get(e.action, e.action)
            counts[label] = counts.get(label, 0) + 1
            if want != "All" and label != want:
                continue
            self._rows[str(e.id)] = e
            self.tree.insert("", "end", iid=str(e.id),
                             tags=("failed",) if e.action == "failed" else (),
                             values=(e.id, e.at, label, e.journey_id,
                                     e.applicant_id or "", e.student_id or "",
                                     e.matched_on or "", e.linked_at or "",
                                     (e.detail or "").replace("\n", " ")))
        self.status.set(" · ".join(f"{k}: {v}" for k, v in counts.items())
                        or "Nothing has arrived through the intake yet.")

    def _open(self) -> None:
        iid = pc.selected(self.tree, TITLE)
        if not iid:
            return
        e = self._rows.get(iid)
        if e is None or not e.applicant_id:
            messagebox.showinfo(
                TITLE, "This entry has no applicant record (the intake "
                "created or reused a student directly).",
                parent=self.frame.winfo_toplevel())
            return
        open_read_only(self.frame, e.applicant_id)
