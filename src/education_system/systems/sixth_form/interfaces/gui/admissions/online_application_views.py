"""Online Verification tab: staff check applications from the public form."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox

from education_system.systems.sixth_form.domain.admissions import (
    admissions as adm,
    online_application as oa,
)
from education_system.systems.sixth_form.interfaces.gui.admissions import (
    _admissions_ui as ui,
)

logger = logging.getLogger(__name__)


class OnlineVerificationTab:
    COLS = [("ref", "Reference", 110), ("id", "Applicant", 90),
            ("name", "Name", 180), ("dob", "DOB", 90),
            ("email", "Email", 200), ("school", "School", 160),
            ("subjects", "Choices", 240), ("when", "Submitted", 140),
            ("dupes", "Possible duplicates", 160)]

    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Online Verification")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="View details…",
                   command=self._view).pack(side="left")
        ttk.Button(bar, text="Verify (join pipeline)",
                   command=self._verify).pack(side="left", padx=(12, 4))
        ttk.Button(bar, text="Merge into duplicate…",
                   command=self._merge).pack(side="left")
        ttk.Button(bar, text="Reject (spam / invalid)",
                   command=self._reject).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side="right")
        self.info = tk.StringVar()
        ttk.Label(self.frame, textvariable=self.info, foreground="#555").pack(
            fill="x", padx=8)
        holder = ttk.Frame(self.frame)
        holder.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree = ui.make_tree(holder, self.COLS, height=20)
        self.tree.tag_configure("dupe", background="#fff2c4")
        self.tree.bind("<Double-1>", lambda _e: self._view())
        self.refresh()

    def refresh(self) -> None:
        ui.clear(self.tree)
        try:
            rows = oa.pending()
        except Exception as e:  # noqa: BLE001
            logger.exception("Online applications failed to load")
            self.info.set(f"Error: {e}")
            return
        for s, a in rows:
            dupes = [d.applicant_id for d in oa.current_duplicates(
                a.applicant_id)]
            choices = ", ".join(c.label for c in
                                adm.list_programme_choices(a.applicant_id))
            self.tree.insert("", "end", iid=a.applicant_id, values=(
                s.reference_no, a.applicant_id, a.full_name, a.dob or "",
                a.email or "", a.previous_school or "", choices,
                s.submitted_at, ", ".join(dupes)),
                tags=("dupe",) if dupes else ())
        self.info.set(f"{len(rows)} online application(s) awaiting "
                      "verification. Check identity details and choices, "
                      "then verify, merge into a duplicate, or reject.")

    def _sel(self) -> str | None:
        return ui.require_iid(self.tree, "Online applications")

    def _view(self) -> None:
        aid = self._sel()
        a = adm.get_applicant(aid) if aid else None
        if a is None:
            return
        s = oa.get_submission(applicant_id=aid)
        dupes = oa.current_duplicates(aid)
        lines = [
            f"Reference: {s.reference_no if s else '—'}   Applicant: {aid}",
            f"Name: {a.full_name}   DOB: {a.dob or '—'}",
            f"Email: {a.email or '—'}   Phone: {a.phone or '—'}",
            f"Address: {a.address or '—'}",
            f"School: {a.previous_school or '—'}   ULN: {a.uln or '—'}",
            f"Predicted GCSEs: {a.predicted_gcses or '—'}",
            "Choices: " + (", ".join(c.label for c in
                                     adm.list_programme_choices(aid)) or "—"),
            f"Referee: {a.reference_name or '—'} {a.reference_contact or ''}",
            "", "Possible duplicates:",
        ] + ([f"  {d.applicant_id}  {d.full_name}  {d.dob or ''}  "
              f"{d.email or ''}  [{d.status}]" for d in dupes] or ["  none"])
        if a.notes:
            lines += ["", a.notes]
        ui.show_text(self.frame, f"Online application {aid}", "\n".join(lines))

    def _verify(self) -> None:
        aid = self._sel()
        if not aid:
            return
        if oa.current_duplicates(aid) and not messagebox.askyesno(
                "Verify", "This looks like a duplicate of an existing "
                "applicant. Verify it as a separate application anyway?",
                parent=self.frame):
            return
        v = ui.ask_form(self.frame, "Verify application",
                        [("notes", "Verification notes", "text", None)])
        if v is None:
            return
        try:
            oa.verify(aid, by=ui.current_username(), notes=v["notes"])
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Verify", str(e), parent=self.frame)
        self.refresh()

    def _merge(self) -> None:
        aid = self._sel()
        if not aid:
            return
        dupes = oa.current_duplicates(aid)
        if not dupes:
            messagebox.showinfo("Merge", "No duplicate found for this "
                                "application.", parent=self.frame)
            return
        v = ui.ask_form(self.frame, "Merge into", [
            ("keep", "Keep applicant", "readonly",
             [f"{d.applicant_id} — {d.full_name} [{d.status}]"
              for d in dupes])])
        if not v or not v["keep"]:
            return
        keep = v["keep"].split(" — ")[0]
        try:
            oa.merge_into(aid, keep, by=ui.current_username())
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Merge", str(e), parent=self.frame)
        self.refresh()

    def _reject(self) -> None:
        aid = self._sel()
        if not aid:
            return
        v = ui.ask_form(self.frame, "Reject online application",
                        [("reason", "Reason", "entry", None)],
                        {"reason": "Invalid or spam online application"})
        if v is None:
            return
        if not messagebox.askyesno(
                "Reject", f"Erase {aid}? This cannot be undone.",
                parent=self.frame):
            return
        try:
            oa.reject(aid, by=ui.current_username(), reason=v["reason"])
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Reject", str(e), parent=self.frame)
        self.refresh()
