"""MEG tab: minimum expected grades from prior attainment.

Shows each learner's MEG per subject (from the value-added benchmark
table) beside the MTE currently on their Target Setting record, and
writes MEGs into Target Setting on request. Hosted in the Value Added
window (Target Setting's own window is unchanged).
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox

from education_system.systems.sixth_form.domain.assessment.target_setting import (
    meg as data,
)
from education_system.systems.sixth_form.interfaces.gui.governance.compliance.measures.measures_views import (
    run_async,
)

logger = logging.getLogger(__name__)

TITLE = "Minimum expected grades"


class MEGTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="MEG")
        self.rows: list[data.MEGRow] = []
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Subject (blank = all):").pack(side="left")
        self.subject = tk.StringVar()
        ttk.Entry(bar, textvariable=self.subject, width=18).pack(side="left",
                                                                 padx=(2, 8))
        self.overwrite = tk.BooleanVar(value=False)
        ttk.Button(bar, text="Calculate", command=self.refresh).pack(side="left")
        ttk.Checkbutton(bar, text="Replace a different hand-set MTE",
                        variable=self.overwrite).pack(side="left", padx=8)
        ttk.Button(bar, text="Write MEGs to Target Setting",
                   command=self._apply).pack(side="left")
        self.status = ttk.Label(bar, text="", foreground="#666")
        self.status.pack(side="right")
        self.banner = ttk.Label(self.frame, text="", foreground="#8c0d0d",
                                wraplength=1250)
        self.banner.pack(anchor="w", padx=8)
        cols = ("id", "name", "subject", "type", "aps", "meg", "mte",
                "action", "note")
        self.tree = ttk.Treeview(self.frame, columns=cols, show="headings")
        for c, h, w in zip(cols, ("Student", "Name", "Subject", "Type",
                                  "Avg GCSE", "MEG", "Current MTE", "Action",
                                  "Note"),
                           (90, 180, 140, 110, 70, 60, 90, 80, 260)):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.tag_configure("differs", background="#fff7e6")
        vsb = ttk.Scrollbar(self.frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(8, 0),
                       pady=(4, 8))
        vsb.pack(side="right", fill="y", pady=(4, 8))

    def refresh(self) -> None:
        subj = self.subject.get().strip() or None

        def done(rows, err) -> None:
            if err is not None:
                messagebox.showerror(TITLE, str(err), parent=self.frame)
                return
            self.rows = rows
            self.banner.config(
                text="MEGs come from the PLACEHOLDER benchmark table - replace "
                     "it on the Benchmarks tab." if any(r.placeholder
                                                        for r in rows) else "")
            self.tree.delete(*self.tree.get_children())
            for r in rows:
                self.tree.insert("", "end", values=(
                    r.student_id, r.student_name, r.subject,
                    r.qualification_type,
                    "" if r.aps is None else f"{r.aps:.2f}",
                    r.meg_grade or "—", r.current_mte or "—", r.action,
                    r.note), tags=("differs",) if r.action == "differs" else ())

        run_async(self.frame, lambda: data.meg_report(subject=subj), done,
                  status=self.status, busy_text="Calculating…")

    def _apply(self) -> None:
        if not self.rows:
            messagebox.showinfo(TITLE, "Calculate first.", parent=self.frame)
            return
        if not messagebox.askyesno(
                TITLE, f"Write MEGs for {len(self.rows)} row(s) into Target "
                       "Setting?", parent=self.frame):
            return
        try:
            from education_system.systems.sixth_form.domain.governance.user_management import (
                access,
            )
            who = access.current().username or None
        except Exception:
            who = None
        res = data.apply_megs(self.rows, overwrite=self.overwrite.get(),
                              set_by=who)
        msg = res.summary
        if res.skipped:
            msg += "\n\n" + "\n".join(f"{s} {sub}: {why}"
                                      for s, sub, why in res.skipped[:15])
        messagebox.showinfo(TITLE, msg, parent=self.frame)
        self.refresh()


__all__ = ["MEGTab"]
