"""Consent items on an onboarding checklist, backed by GDPR consent records.

Opening the dialog only reads (``consent_links``); bringing the items in
line with the GDPR register is the explicit "Sync with GDPR records"
button (``sync_consent_items``)."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox

from education_system.systems.sixth_form.domain.admissions.onboarding import (
    onboarding as data,
)
from education_system.systems.sixth_form.interfaces.gui.admissions import (
    _admissions_ui as ui,
)
from education_system.systems.sixth_form.interfaces.gui.admissions.onboarding import (
    onboarding_actions as actions,
)

logger = logging.getLogger(__name__)


class ConsentDialog:
    def __init__(self, parent: tk.Misc, checklist_id: int,
                 on_change=None) -> None:
        self.cid = checklist_id
        self.on_change = on_change
        self.win = ui.new_window(parent, f"Consents — checklist "
                                 f"#{checklist_id}")
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        b_granted = ttk.Button(bar, text="Record granted…",
                               command=lambda: self._record(True))
        b_granted.pack(side="left")
        b_refused = ttk.Button(bar, text="Record refused…",
                               command=lambda: self._record(False))
        b_refused.pack(side="left", padx=4)
        b_sync = ttk.Button(bar, text="Sync with GDPR records",
                            command=self._sync)
        b_sync.pack(side="left", padx=(12, 0))
        ttk.Button(bar, text="Refresh",
                   command=self.refresh).pack(side="left", padx=(12, 0))
        writable = actions.can_write()
        actions.set_write_state([b_granted, b_refused, b_sync], writable)
        if not writable:
            ttk.Label(bar, foreground="#a33",
                      text="Read-only").pack(side="right")
        ttk.Label(self.win, foreground="#555", text=(
            "Each decision is stored in the GDPR consents register "
            "(Governance → GDPR) and ticks the item. Withdrawing a consent "
            "there re-opens the item on the next sync. Opening this window "
            "never changes anything — use \"Sync with GDPR records\".")
            ).pack(fill="x", padx=8)
        holder = ttk.Frame(self.win)
        holder.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree = ui.make_tree(holder, [
            ("task", "Item", 220), ("purpose", "GDPR purpose", 150),
            ("state", "Record", 90), ("item", "Item status", 90),
            ("detail", "Consent", 380)], height=6)
        self.tree.tag_configure("Granted", background="#d8f4d8")
        self.tree.tag_configure("Refused", background="#fff2c4")
        self.tree.tag_configure("Missing", background="#ffd6d6")
        self.tree.tag_configure("Withdrawn", background="#ffd6d6")
        self.tree.tag_configure("Expired", background="#ffd6d6")
        self.refresh()

    def refresh(self) -> None:
        ui.clear(self.tree)
        try:
            links = data.consent_links(self.cid)
        except Exception as e:  # noqa: BLE001
            logger.exception("Consent links failed")
            messagebox.showerror("Consents", str(e), parent=self.win)
            return
        if not links:
            self.tree.insert("", "end", values=(
                "(this checklist has no consent items)", "", "", "", ""))
        for link in links:
            self.tree.insert("", "end", iid=str(link.item.item_id), values=(
                link.item.task_name, link.purpose, link.state,
                link.item.status, link.detail), tags=(link.state,))

    def _record(self, granted: bool) -> None:
        iid = ui.require_iid(self.tree, "Consents")
        if not iid or not iid.isdigit():
            return
        holder: dict = {}

        def run(v: dict) -> None:
            holder["link"] = data.record_consent(
                int(iid), granted=granted, given_by=v["given_by"] or None,
                expires_date=v["expires_date"] or None,
                recorded_by=ui.current_username(), notes=v["notes"] or None)

        v = ui.ask_form(self.win, "Consent " + ("granted" if granted
                                                 else "refused"), [
            ("given_by", "Given by (e.g. parent's name)", "entry", None),
            ("expires_date", "Expires (YYYY-MM-DD, optional)", "entry", None),
            ("notes", "Notes", "text", None)], on_submit=run)
        if v is not None:
            if holder.get("link") is not None:
                self._follow_up(holder["link"])
            self._changed()

    def _follow_up(self, link) -> None:
        """consent_followups.after_consent: a refusal opens one follow-up
        task; a grant ticks an open one. Say what happened."""
        from education_system.systems.sixth_form.domain.admissions.onboarding import (
            consent_followups as cf,
        )
        key = cf.followup_key(link.item.key)
        before = {i.item_id: i.is_done for i in data.list_items(
            checklist_id=link.item.checklist_id) if i.key == key}
        try:
            item = cf.after_consent(link)
        except Exception as e:  # noqa: BLE001 — the consent itself is saved
            logger.exception("Consent follow-up failed")
            messagebox.showwarning(
                "Consent follow-up", f"The consent was recorded, but the "
                f"follow-up task could not be updated:\n{e}",
                parent=self.win)
            return
        if item is None:
            return
        if item.item_id not in before:
            msg = (f"The consent was refused, so a follow-up task was "
                   f"opened on this checklist:\n\n'{item.task_name}'")
        elif item.is_done and not before[item.item_id]:
            msg = (f"Consent is now granted: the follow-up task "
                   f"'{item.task_name}' was ticked.")
        elif not item.is_done:
            msg = (f"A follow-up task is already open: "
                   f"'{item.task_name}'.")
        else:
            return
        messagebox.showinfo("Consent follow-up", msg, parent=self.win)

    def _sync(self) -> None:
        try:
            n = data.sync_consent_items(self.cid)
        except Exception as e:  # noqa: BLE001 — AccessDenied / DB
            logger.warning("Consent sync failed: %s", e)
            messagebox.showerror("Consents", str(e), parent=self.win)
            return
        messagebox.showinfo("Consents", f"{n} item(s) updated.",
                            parent=self.win)
        self._changed()

    def _changed(self) -> None:
        self.refresh()
        if self.on_change:
            self.on_change()
