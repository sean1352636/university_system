"""Exams Office tab: certificate deliveries, issue log, unclaimed and retention."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox

from education_system.systems.sixth_form.domain.assessment.exam_entries.exam_entries import (
    EXAM_BOARDS,
    SEASONS,
)
from education_system.systems.sixth_form.domain.assessment.exams_office import (
    certificates as ct,
)
from education_system.systems.sixth_form.interfaces.gui.assessment.exams_office.exams_widgets import (
    guarded,
    FormField,
    clear,
    default_year,
    form_dialog,
    run_action,
    selected_id,
    table,
    text_window,
)

logger = logging.getLogger(__name__)


def build_tab(gui, parent: ttk.Frame) -> None:
    actions = ttk.Frame(parent)
    actions.pack(fill="x", pady=(0, 6))
    panes = ttk.PanedWindow(parent, orient="vertical")
    panes.pack(fill="both", expand=True)
    b_holder = ttk.Frame(panes)
    c_holder = ttk.Frame(panes)
    panes.add(b_holder, weight=1)
    panes.add(c_holder, weight=2)
    c_actions = ttk.Frame(parent)
    c_actions.pack(fill="x", pady=(6, 0))
    unclaimed_var = tk.BooleanVar(value=False)
    state: dict = {}

    @guarded(gui.root)
    def refresh() -> None:
        clear(b_holder)
        rows = ct.list_batches()
        state["btree"] = tree = table(
            b_holder, [("Board", 130), ("Series", 110), ("Received", 90),
                       ("Number", 60), ("Keep unclaimed until", 130), ("Notes", 300)],
            [(b.exam_board, f"{b.season} {b.year}", b.received_date, b.count_received,
              b.retain_until, b.notes) for b in rows],
            iids=[b.batch_id for b in rows], height=6)
        tree.bind("<<TreeviewSelect>>", lambda _e: show())
        show()

    @guarded(gui.root)
    def show() -> None:
        clear(c_holder)
        sel = state["btree"].selection()
        batch_id = int(sel[0]) if sel else None
        rows = ct.list_certificates(batch_id=batch_id, unclaimed_only=unclaimed_var.get())
        state["ctree"] = table(
            c_holder, [("Student", 80), ("Name", 170), ("Board", 120), ("Series", 100),
                       ("Cert ref", 90), ("Issued", 85), ("Method", 180),
                       ("Collected by", 130), ("Signature", 120)],
            [(c.student_id, c.full_name, c.exam_board, c.series, c.certificate_ref,
              c.issued_date, c.method, c.collected_by, c.signature_ref) for c in rows],
            iids=[c.certificate_id for c in rows])
        gui.status_var.set(f"{len(rows)} certificate(s)"
                           + (" unclaimed" if unclaimed_var.get() else ""))

    @guarded(gui.root)
    def new_batch() -> None:
        form_dialog(gui.root, "Certificates received",
                    [FormField("exam_board", "Board", "readonly", EXAM_BOARDS),
                     FormField("season", "Season", "readonly", SEASONS),
                     FormField("year", "Year"),
                     FormField("received_date", "Received date"),
                     FormField("count_received", "Number received"),
                     FormField("notes", "Notes")],
                    ct.record_batch, on_done=refresh,
                    initial={"exam_board": EXAM_BOARDS[0], "season": SEASONS[0],
                             "year": default_year()},
                    note="Every candidate who sat with the board that series is listed "
                         "for issue.")

    @guarded(gui.root)
    def delete_batch() -> None:
        bid = selected_id(state["btree"], gui.root, "a delivery")
        if bid is not None and messagebox.askyesno("Delete", "Delete this delivery?",
                                                   parent=gui.root):
            run_action(gui.root, lambda: ct.delete_batch(bid), then=refresh)

    @guarded(gui.root)
    def issue() -> None:
        cid = selected_id(state["ctree"], gui.root, "a certificate")
        if cid is None:
            return
        form_dialog(gui.root, "Issue certificate",
                    [FormField("method", "Method", "readonly", ct.ISSUE_METHODS, 44),
                     FormField("collected_by", "Collected by"),
                     FormField("signature_ref", "Signature (e.g. issue sheet p.3)"),
                     FormField("issued_date", "Date (blank = today)"),
                     FormField("notes", "Notes")],
                    lambda v: ct.issue(cid, method=v["method"],
                                       collected_by=v["collected_by"] or None,
                                       signature_ref=v["signature_ref"] or None,
                                       issued_date=v["issued_date"] or None,
                                       notes=v["notes"] or None),
                    initial={"method": ct.ISSUE_METHODS[0]}, on_done=show)

    @guarded(gui.root)
    def retention() -> None:
        rows = ct.retention_notices()
        lines = [f"UNCLAIMED CERTIFICATES — RETENTION ({ct.RETENTION_MONTHS} months "
                 "from receipt)", ""]
        for c, left in rows:
            state_ = "may now be destroyed/returned" if left < 0 else f"{left} day(s) left"
            lines.append(f"{c.student_id:<10} {(c.full_name or ''):<26} {c.exam_board:<18} "
                         f"{c.series:<14} received {c.received_date}  keep until "
                         f"{c.retain_until}  {state_}")
        if not rows:
            lines.append("(nothing due)")
        text_window(gui.root, "Certificate retention", "\n".join(lines) + "\n",
                    filename="certificate_retention.txt")

    @guarded(gui.root)
    def unclaimed_list() -> None:
        rows = ct.list_certificates(unclaimed_only=True)
        lines = ["UNCLAIMED CERTIFICATES", ""] + [
            f"{c.student_id:<10} {(c.full_name or ''):<26} {c.exam_board:<18} {c.series}"
            for c in rows]
        text_window(gui.root, "Unclaimed certificates", "\n".join(lines) + "\n",
                    filename="unclaimed_certificates.txt")

    for label, cmd in (("Log delivery…", new_batch), ("Delete delivery", delete_batch),
                       ("Retention notices…", retention),
                       ("Unclaimed list…", unclaimed_list)):
        ttk.Button(actions, text=label, command=cmd).pack(side="left", padx=(0, 6))
    ttk.Button(c_actions, text="Issue selected…", command=issue).pack(side="left")
    ttk.Checkbutton(c_actions, text="Unclaimed only", variable=unclaimed_var,
                    command=show).pack(side="left", padx=12)
    refresh()
