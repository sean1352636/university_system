"""Student portal tabs for class resources and device loans, plus Pay.

Mixed into :class:`.student_portal_gui.StudentPortalGUI` alongside
:class:`._learner_sections.LearnerSectionsMixin`. Every call passes
``self.sid`` (always ``principal.student_id``); the domain functions
check the signed-in learner may see that id.
"""

from __future__ import annotations

import logging
import pathlib
import tkinter as tk
import webbrowser
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from typing import Any

logger = logging.getLogger(__name__)

_MUTED = "#7f8c8d"


def _dash(v: Any) -> str:
    return "—" if v in (None, "") else str(v)


def _table(parent, columns, *, height: int = 12) -> ttk.Treeview:
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show="headings",
                        height=height)
    for key, text, width in columns:
        tree.heading(key, text=text)
        tree.column(key, width=width, anchor="w")
    bar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=bar.set)
    tree.pack(side="left", fill="both", expand=True)
    bar.pack(side="right", fill="y")
    return tree


class LearnerExtrasMixin:
    """Class Resources and My Devices tabs, and the Pay button."""

    sid: str
    principal: Any
    root: tk.Tk

    # ── Pay ──────────────────────────────────────────────────────────

    def _pay(self) -> None:
        from education_system.systems.sixth_form.domains.finance.interfaces.gui.online_payments.pay_dialog import (
            open_pay_dialog,
        )
        open_pay_dialog(self.root, "student", self.sid)

    # ── Class Resources ──────────────────────────────────────────────

    def _resources(self, f: ttk.Frame) -> None:
        from education_system.systems.sixth_form.domain.academics.class_resources import (
            class_resources as cr,
        )
        rows = cr.resources_for_student(self.sid)
        ttk.Label(f, text="Materials and online tasks your teachers have shared "
                          "with your classes. Double-click to open.",
                  foreground=_MUTED).pack(anchor="w", pady=(0, 6))
        tree = _table(f, (("class", "Class", 150), ("week", "Week", 50),
                          ("topic", "Topic", 160), ("title", "Title", 300),
                          ("kind", "Type", 90), ("due", "Task due", 100),
                          ("seen", "Opened", 70)), height=18)
        by_iid: dict[str, int] = {}
        for s in rows:
            r = s.resource
            iid = tree.insert("", "end", values=(
                _dash(r.group_name or r.course_code), _dash(r.week), _dash(r.topic),
                s.task.title if s.task else r.title, r.kind,
                _dash(s.task.due_date) if s.task else "—",
                "Yes" if s.seen else ""))
            by_iid[iid] = r.resource_id
        if not rows:
            ttk.Label(f, text="Nothing has been shared with your classes yet.").pack(
                anchor="w", pady=(6, 0))

        def open_selected(_e=None) -> None:
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Class Resources", "Select an item first.",
                                       parent=self.root)
                return
            try:
                kind, target = cr.open_resource(by_iid[sel[0]], student_id=self.sid)
            except ValueError as e:
                messagebox.showwarning("Class Resources", str(e), parent=self.root)
                return
            if kind == "file":
                webbrowser.open(pathlib.Path(target).as_uri())
            else:
                webbrowser.open(target)
            tree.set(sel[0], "seen", "Yes")

        tree.bind("<Double-1>", open_selected)
        ttk.Button(f, text="Open", command=open_selected).pack(anchor="w", pady=(6, 0))

    # ── My Devices ───────────────────────────────────────────────────

    def _devices(self, f: ttk.Frame) -> None:
        from education_system.systems.sixth_form.domains.operations.domain.assets import (
            assets,
        )
        from education_system.systems.sixth_form.domains.operations.domain.device_loans import (
            acceptable_use as aup,
            device_loans as dl,
        )
        box = ttk.LabelFrame(f, text="IT acceptable-use policy", padding=8)
        box.pack(fill="x")
        cur = aup.current_aup()
        if cur is None:
            ttk.Label(box, text="No acceptable-use policy has been published yet.").pack(
                anchor="w")
        else:
            accepted = aup.current_acceptance(aup.STUDENT, self.sid)
            ttk.Label(box, text=f"{cur.title} — version {cur.version}").pack(anchor="w")
            if cur.summary:
                ttk.Label(box, text=cur.summary, wraplength=900,
                          foreground=_MUTED).pack(anchor="w", pady=(2, 4))
            if accepted is not None:
                ttk.Label(box, text="You have accepted this version.").pack(anchor="w")
            else:
                def accept() -> None:
                    if not messagebox.askyesno(
                            "Acceptable use",
                            f"I have read and accept {cur.title} (version "
                            f"{cur.version}).", parent=self.root):
                        return
                    try:
                        aup.accept_current()
                    except ValueError as e:
                        messagebox.showwarning("Acceptable use", str(e), parent=self.root)
                        return
                    self._ensure_built(force=True)  # type: ignore[attr-defined]
                ttk.Label(box, text="You need to accept this before you can borrow a "
                                    "device.", foreground="#c0392b").pack(anchor="w")
                ttk.Button(box, text="I accept…", command=accept).pack(anchor="w",
                                                                       pady=(4, 0))
        loans = dl.loans_for_student(self.sid)
        lf = ttk.LabelFrame(f, text="Devices on loan to me", padding=6)
        lf.pack(fill="both", expand=True, pady=(8, 0))
        tree = _table(lf, (("device", "Device", 260), ("tag", "Tag", 90),
                           ("issued", "Issued", 90), ("due", "Due back", 90),
                           ("status", "Status", 90), ("charger", "Charger", 70),
                           ("charge", "Charge", 120)), height=10)
        for ln in loans:
            a = assets.get_asset(ln.asset_id)
            charge = (f"£{ln.charge_amount:,.2f} ({ln.charge_status})"
                      if ln.charge_amount else "")
            tree.insert("", "end", values=(
                a.name if a else f"Asset {ln.asset_id}", a.asset_tag if a else "—",
                ln.issued_on, ln.returned_on and f"Returned {ln.returned_on}" or ln.due_on,
                ln.status, "Yes" if ln.charger_issued else "No", charge))
        if not loans:
            ttk.Label(lf, text="You have no device loans.").pack(anchor="w")
