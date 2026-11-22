"""Year 11 Transition tab: a feeder school's CTF read against applicants."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox

from education_system.systems.sixth_form.domain.admissions import (
    year11_transition as y11,
)
from education_system.systems.sixth_form.interfaces.gui.admissions import (
    _admissions_ui as ui,
)

logger = logging.getLogger(__name__)


class Year11TransitionTab:
    COLS = [("name", "Pupil", 200), ("dob", "DOB", 90), ("upn", "UPN", 120),
            ("uln", "ULN", 100), ("applicant", "Applicant", 90),
            ("how", "Matched on", 100), ("gcses", "KS4 GCSEs", 360),
            ("skipped", "Not GCSE grades", 160)]

    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Year 11 Transition")
        self.path: str | None = None
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Open CTF file (applicant context)…",
                   command=self._open).pack(side="left")
        self.apply_btn = ttk.Button(bar, text="Apply to matched applicants",
                                    command=self._apply, state="disabled")
        self.apply_btn.pack(side="left", padx=6)
        self.results_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Record KS4 results as actual GCSEs",
                        variable=self.results_var).pack(side="left")
        ttk.Button(bar, text="Unmatched pupils…",
                   command=self._unmatched).pack(side="left", padx=6)
        self.info = tk.StringVar(value=(
            "Reads a feeder school's Common Transfer File and matches each "
            "pupil to an applicant (ULN, UPN, then name + DOB). Student "
            "records are not touched — use the Integrations CTF import for "
            "enrolled students."
            if y11.available() else
            "The CTF integration module is not available on this install."))
        ttk.Label(self.frame, textvariable=self.info, foreground="#555",
                  wraplength=1100, justify="left").pack(fill="x", padx=8)
        holder = ttk.Frame(self.frame)
        holder.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree = ui.make_tree(holder, self.COLS, height=20)
        self.tree.tag_configure("none", background="#eeeeee")
        self._preview = None

    def _open(self) -> None:
        if not y11.available():
            messagebox.showinfo("Year 11 transition",
                                "The CTF integration is not available.",
                                parent=self.frame)
            return
        path = filedialog.askopenfilename(
            parent=self.frame, title="Common Transfer File",
            filetypes=[("CTF / XML", "*.xml"), ("All files", "*")])
        if not path:
            return
        try:
            pv = y11.preview(path)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Year 11 transition", str(e),
                                 parent=self.frame)
            return
        self.path, self._preview = path, pv
        ui.clear(self.tree)
        for p in pv.pupils:
            self.tree.insert("", "end", iid=str(p.index), values=(
                p.name, p.dob or "", p.upn or "", p.uln or "",
                p.applicant_id or "", p.matched_on or "",
                ", ".join(f"{s} {g}" for s, g in p.gcses),
                ", ".join(p.skipped_results)),
                tags=() if p.applicant_id else ("none",))
        self.info.set(f"{pv.file_name} from {pv.source_school}: "
                      f"{len(pv.pupils)} pupil(s), {len(pv.matched)} matched "
                      f"to applicants, {len(pv.unmatched)} not applied.")
        self.apply_btn.configure(state="normal" if pv.matched else "disabled")

    def _apply(self) -> None:
        if not self.path or not messagebox.askyesno(
                "Year 11 transition", "Fill blanks on the matched applicants"
                + (" and record their KS4 results" if self.results_var.get()
                   else "") + "?", parent=self.frame):
            return
        try:
            res = y11.apply(self.path, record_results=self.results_var.get(),
                            entered_by=ui.current_username())
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Year 11 transition", str(e),
                                 parent=self.frame)
            return
        ui.show_text(self.frame, "CTF applied", "\n".join(
            [f"Applicants updated: {len(res.updated)}",
             f"GCSE results recorded: {res.results_recorded}", ""]
            + res.notes))

    def _unmatched(self) -> None:
        if not self._preview:
            messagebox.showinfo("Year 11 transition", "Open a CTF first.",
                                parent=self.frame)
            return
        ui.show_text(self.frame, "Pupils who have not applied", "\n".join(
            f"{p.name}  {p.dob or ''}  UPN {p.upn or '—'}"
            for p in self._preview.unmatched) or "Every pupil has applied.")
