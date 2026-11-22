"""Admissions window page: retention of unsuccessful applications.

Shows the retention policy, lets governance staff switch it on or off
and set how long applications are kept and which outcomes it covers,
previews the applications it would erase now (dry run), runs it, and
lists past runs. The policy is off until someone with governance turns
it on; that person is recorded as approver of the erasures it makes.
"""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import ttk
from typing import Any

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.sixth_form.domain.admissions import retention
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)
from education_system.systems.sixth_form.interfaces.gui.admissions import (
    pages_common as pc,
)

TITLE = "Retention"


class RetentionPage:
    CAND_COLS = [("id", "ID", 90), ("name", "Name", 200),
                 ("status", "Status", 120), ("intake", "Intake", 75),
                 ("archived", "Archived", 70), ("from", "Clock from", 90),
                 ("due", "Due", 90)]
    RUN_COLS = [("id", "#", 45), ("at", "When", 150), ("by", "Run by", 160),
                ("cands", "Candidates", 80), ("erased", "Erased", 70),
                ("errors", "Errors", 420)]

    def __init__(self, nb: Any) -> None:
        self.frame = pc.new_page(
            nb, TITLE, "Retention of unsuccessful applications",
            "Never touched: enrolled or converted applicants, applications "
            "part-way through conversion, ones with a pending erasure "
            "request, and outcomes the policy does not name. The clock starts "
            "at the later of the cycle's closing date and the decision.")
        self.governance = pc.can(access.GOVERNANCE)
        self.policy_text = tk.StringVar()
        ttk.Label(self.frame, textvariable=self.policy_text, wraplength=1000,
                  justify="left").pack(side="top", anchor="w", pady=(0, 4))

        box = ttk.LabelFrame(self.frame, text="Policy settings (governance)",
                             padding=6)
        box.pack(side="top", fill="x", pady=(0, 6))
        st = "normal" if self.governance else "disabled"
        self.enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(box, text="Policy on", variable=self.enabled,
                        state=st).grid(row=0, column=0, sticky="w")
        ttk.Label(box, text="Keep for (months):").grid(row=0, column=1,
                                                      padx=(16, 4))
        self.months = ttk.Spinbox(box, from_=1, to=120, width=5, state=st)
        self.months.grid(row=0, column=2, sticky="w")
        ttk.Label(box, text="Covers:").grid(row=0, column=3, padx=(16, 4))
        self.status_vars: dict[str, tk.BooleanVar] = {}
        for i, s in enumerate(retention.ELIGIBLE_STATUSES):
            v = tk.BooleanVar(value=False)
            self.status_vars[s] = v
            ttk.Checkbutton(box, text=s, variable=v, state=st).grid(
                row=0, column=4 + i, sticky="w", padx=(0, 6))
        ttk.Button(box, text="Save policy", command=self._save,
                   state=st).grid(row=0, column=10, padx=(12, 0))
        if not self.governance:
            ttk.Label(box, text="Only staff with governance access can "
                      "change the policy or run it.", foreground=pc.MUTED
                      ).grid(row=1, column=0, columnspan=11, sticky="w",
                             pady=(4, 0))

        bar = ttk.Frame(self.frame)
        bar.pack(side="top", fill="x", pady=(0, 2))
        ttk.Button(bar, text="Dry run", command=self._dry_run).pack(
            side="left", padx=(0, 4))
        ttk.Button(bar, text="Run now…", command=self._run,
                   state=st).pack(side="left", padx=(0, 4))
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(
            side="right")
        self.status = pc.status_line(self.frame)

        hist = ttk.LabelFrame(self.frame, text="Run history", padding=4)
        hist.pack(side="bottom", fill="x", pady=(6, 0))
        self.runs = pc.make_tree(hist, self.RUN_COLS, height=5)
        cands = ttk.LabelFrame(self.frame, text="Due for erasure now",
                               padding=4)
        cands.pack(fill="both", expand=True)
        self.tree = pc.make_tree(cands, self.CAND_COLS, height=10)
        self.refresh()

    def refresh(self) -> None:
        ok, pol = pc.load(self.status, TITLE, retention.get_policy)
        if not ok:
            self.policy_text.set("")
            return
        state = "ON" if pol.enabled else "OFF"
        who = (f" — enabled by {pol.enabled_by} on {pol.enabled_at}"
               if pol.enabled and pol.enabled_by else "")
        changed = (f" (last changed by {pol.updated_by}, {pol.updated_at})"
                   if pol.updated_by else "")
        self.policy_text.set(f"{state}{who}. {pol.text}.{changed}")
        self.enabled.set(pol.enabled)
        self.months.configure(state="normal")
        self.months.delete(0, "end")
        self.months.insert(0, str(pol.months))
        if not self.governance:
            self.months.configure(state="disabled")
        for s, v in self.status_vars.items():
            v.set(s in pol.statuses)

        pc.clear(self.tree)
        ok, rows = pc.load(self.status, TITLE, retention.candidates,
                           policy=pol)
        if ok:
            for c in rows:
                self.tree.insert("", "end", iid=c.applicant_id, values=(
                    c.applicant_id, c.name, c.status, c.intake_year or "",
                    pc.yes(c.archived), c.clock_from, c.due_on))
            self.status.set(
                f"{len(rows)} application(s) due under the policy"
                + ("" if pol.enabled else " (preview — the policy is off, "
                   "nothing will be erased)"))
        pc.clear(self.runs)
        ok, runs = pc.load(self.status, TITLE, retention.run_history)
        for r in runs or []:
            errs = ""
            if r.get("errors_json"):
                try:
                    errs = "; ".join(json.loads(r["errors_json"]))
                except ValueError:
                    errs = r["errors_json"]
            self.runs.insert("", "end", iid=str(r["id"]), values=(
                r["id"], r["at"], r.get("run_by") or "", r["candidates"],
                r["erased"], errs))

    def _save(self) -> None:
        statuses = [s for s, v in self.status_vars.items() if v.get()]
        enabling = self.enabled.get()
        if enabling:
            try:
                months = int(self.months.get())
            except ValueError:
                months = self.months.get()
            if not messagebox.askyesno(
                    TITLE, "Save the policy with it ON?\n\nUnsuccessful "
                    f"applications ({', '.join(statuses) or 'none'}) will be "
                    f"erased {months} month(s) after the cycle closes or the "
                    "decision, by the scheduled job, with you recorded as the "
                    "approver.", parent=self.frame.winfo_toplevel()):
                return
        ok, _ = pc.run(self.frame, TITLE, retention.set_policy,
                       enabled=enabling, months=self.months.get(),
                       statuses=statuses)
        if ok:
            self.refresh()

    def _dry_run(self) -> None:
        ok, res = pc.run(self.frame, TITLE, retention.run, dry_run=True)
        if not ok:
            return
        lines = [res.summary + ".", ""]
        lines += [f"  {c.applicant_id}  {c.name}  ({c.status}"
                  f"{', archived' if c.archived else ''}; due {c.due_on})"
                  for c in res.candidates]
        if not res.enabled:
            lines += ["", "The policy is off: a real run would erase nothing."]
        pc.show_text(self.frame, "Retention dry run", "\n".join(lines),
                     save_name="retention_dry_run.txt")

    def _run(self) -> None:
        n = len(self.tree.get_children())
        if not messagebox.askyesno(
                TITLE, f"Run the retention policy now?\n\n{n} application(s) "
                "will be permanently erased (each is logged in the erasure "
                "log). This cannot be undone.",
                parent=self.frame.winfo_toplevel(), icon="warning"):
            return
        ok, res = pc.run(self.frame, TITLE, retention.run, dry_run=False)
        if not ok:
            return
        msg = res.summary + "."
        if res.errors:
            msg += "\n\n" + "\n".join(res.errors[:10])
        (messagebox.showwarning if res.errors else messagebox.showinfo)(
            TITLE, msg, parent=self.frame.winfo_toplevel())
        self.refresh()
