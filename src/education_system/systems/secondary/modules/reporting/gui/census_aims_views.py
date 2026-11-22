"""The census "Aims" tab (kept from the old Census / ILR window): learner
aims with the old filters (all / active, by return, learner, type, funding
model, status), New / Edit / Delete, and Open pupil for a linked pupil.
Rules: :mod:`modules.reporting.domain.census_aims`."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.secondary.modules.reporting.domain import census_aims as CA
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.ui.gui.components import widgets as W

_COLUMNS = [("id", "Id", 50), ("learner", "Learner", 90), ("name", "Name", 160),
            ("ref", "Aim ref", 100), ("title", "Title", 200), ("type", "Type", 110),
            ("model", "Funding model", 170), ("start", "Start", 90),
            ("end", "Planned end", 90), ("status", "Status", 110), ("ret", "Return", 60)]
_TAGS = {"muted": {"foreground": "#888"}, "good": "#e7f6ea"}


class AimsTab:
    def __init__(self, tab: ttk.Frame, *, principal: Principal,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.tab, self.principal, self.open_pupil = tab, principal, open_pupil
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.f = {k: tk.StringVar() for k in ("status", "type", "model", "learner", "ret")}
        self.active = tk.BooleanVar(value=False)
        for key, label, values, width in (("status", "Status:", CA.STATUSES, 16),
                                          ("type", "Type:", CA.AIM_TYPES, 14),
                                          ("model", "Funding:", CA.FUNDING_MODELS, 22)):
            ttk.Label(bar, text=label).pack(side="left")
            ttk.Combobox(bar, textvariable=self.f[key], values=["", *values],
                         state="readonly", width=width).pack(side="left", padx=(2, 6))
        ttk.Label(bar, text="Learner:").pack(side="left")
        ttk.Entry(bar, textvariable=self.f["learner"], width=12).pack(side="left", padx=(2, 6))
        ttk.Label(bar, text="Return #:").pack(side="left")
        ttk.Entry(bar, textvariable=self.f["ret"], width=5).pack(side="left", padx=(2, 6))
        ttk.Checkbutton(bar, text="Active only", variable=self.active).pack(side="left")
        ttk.Button(bar, text="Apply", command=self.refresh).pack(side="left", padx=4)
        acts = ttk.Frame(tab)
        acts.pack(fill="x", pady=(0, 4))
        for text, cmd in (("New aim", self.new), ("Edit", self.edit), ("Delete", self.delete),
                          ("Open pupil", self.pupil)):
            ttk.Button(acts, text=text, command=cmd).pack(side="left", padx=(0, 4))
        self.count = ttk.Label(acts, foreground="#666")
        self.count.pack(side="right")
        self.tree = W.tree(tab, _COLUMNS, height=14, stretch={"title", "name"}, tags=_TAGS)
        self.tree.bind("<Double-1>", lambda _e: self.edit())
        self.refresh()

    def _top(self):
        return self.tab.winfo_toplevel()

    def refresh(self) -> None:
        f = {k: v.get().strip() for k, v in self.f.items()}
        try:
            rows = CA.list_aims(actor=self.principal, status=f["status"] or None,
                                aim_type=f["type"] or None, funding_model=f["model"] or None,
                                learner_ref=f["learner"] or None,
                                return_id=int(f["ret"]) if f["ret"].isdigit() else None,
                                active_only=self.active.get())
        except W.ERRORS as e:
            messagebox.showerror("Aims", W.problems(e), parent=self._top())
            return
        self.tree.delete(*self.tree.get_children())
        for a in rows:
            tag = ("good",) if a.status == "Achieved" else () if a.is_active else ("muted",)
            self.tree.insert("", "end", iid=str(a.aim_id), tags=tag, values=(
                a.aim_id, a.learner_ref, a.learner_name or "", a.aim_reference,
                a.aim_title or "", a.aim_type, a.funding_model, a.start_date,
                a.planned_end_date or "", a.status, a.return_id or ""))
        self.count.configure(text=f"{len(rows)} aim(s)")

    def _selected(self) -> CA.Aim | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Aims", "Select an aim first.", parent=self._top())
            return None
        try:
            return CA.get_aim(int(sel[0]), actor=self.principal)
        except W.ERRORS as e:
            messagebox.showerror("Aims", W.problems(e), parent=self._top())
            return None

    def _form(self, a: CA.Aim | None) -> None:
        def v(key: str, default: Any = "") -> Any:
            got = getattr(a, key) if a is not None else None
            return default if got is None else got
        fields = [
            ("return_id", "Return # (blank = none)", v("return_id"), None),
            ("learner_ref", "Learner (admission no., UPN or name)", v("learner_ref"), None),
            ("learner_name", "Learner name", v("learner_name"), None),
            ("ukprn", "UKPRN", v("ukprn"), None), ("uln", "ULN", v("uln"), None),
            ("aim_type", "Aim type", v("aim_type", CA.DEFAULT_AIM_TYPE), list(CA.AIM_TYPES)),
            ("aim_reference", "Aim reference", v("aim_reference"), None),
            ("aim_title", "Aim title", v("aim_title"), None),
            ("funding_model", "Funding model", v("funding_model", CA.DEFAULT_FUNDING_MODEL),
             list(CA.FUNDING_MODELS)),
            ("start_date", "Start date (YYYY-MM-DD)", v("start_date"), None),
            ("planned_end_date", "Planned end date", v("planned_end_date"), None),
            ("actual_end_date", "Actual end date", v("actual_end_date"), None),
            ("completion_code", "Completion code", v("completion_code"),
             ("edit", ["", *(str(c) for c in CA.COMPLETION_CODES)])),
            ("outcome_code", "Outcome code", v("outcome_code"), None),
            ("status", "Status", v("status", CA.DEFAULT_STATUS), list(CA.STATUSES)),
            ("planned_hours", "Planned hours", v("planned_hours"), None),
            ("actual_hours", "Actual hours", v("actual_hours"), None),
            ("funding_band_value", "Funding band value", v("funding_band_value"), None),
            ("delivery_location", "Delivery location", v("delivery_location"), None),
            ("partner_ukprn", "Partner UKPRN", v("partner_ukprn"), None),
            ("notes", "Notes", v("notes"), "text")]

        def save(vals: dict[str, Any]) -> None:
            if a is None:
                CA.create_aim(vals, actor=self.principal)
            else:
                CA.update_aim(a.aim_id, vals, actor=self.principal)
            self.refresh()
        W.form_dialog(self._top(), "New aim" if a is None else f"Edit aim #{a.aim_id}",
                      fields, save, "A learner ref that matches a pupil links the aim to "
                                    "their record.")

    def new(self) -> None:
        self._form(None)

    def edit(self) -> None:
        a = self._selected()
        if a is not None:
            self._form(a)

    def delete(self) -> None:
        a = self._selected()
        if a is None or not messagebox.askyesno("Delete aim", f"Delete aim #{a.aim_id}?",
                                                parent=self._top()):
            return
        try:
            CA.delete_aim(a.aim_id, actor=self.principal)
        except W.ERRORS as e:
            messagebox.showerror("Delete aim", W.problems(e), parent=self._top())
        self.refresh()

    def pupil(self) -> None:
        a = self._selected()
        if a is None:
            return
        if a.pupil_id is None or self.open_pupil is None:
            messagebox.showinfo("Aims", "This aim isn't linked to a pupil record.",
                                parent=self._top())
            return
        self.open_pupil(a.pupil_id)


__all__ = ["AimsTab"]
