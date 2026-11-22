"""The withdrawal dialog (ILR reason, last day in learning, detail) and
the text shown for each lifecycle result.

Used by every route that withdraws: the enrolment directory and profile,
the edit form's status box, bulk status change, the Withdraw / Reinstate
toggle and the student profile's leaving form."""

from __future__ import annotations

import datetime as _dt
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk
from typing import Callable

from education_system.platform.delivery.gui.date_picker import DatePicker
from education_system.platform.delivery.gui.parented_dialogs import (
    make_toplevel,
    messagebox,
)
from education_system.systems.sixth_form.domain.admissions.enrolments.enrolments import (
    WITHDRAWAL_REASONS,
)


def reason_choices() -> list[str]:
    return [f"{code} — {label}" for code, label in WITHDRAWAL_REASONS]


def reason_code(choice: str) -> str:
    return (choice or "").split(" — ", 1)[0].strip()


@dataclass
class WithdrawalChoice:
    reason: str                 # ILR code
    withdrawal_date: str | None
    detail: str | None
    approved_by: str | None


class WithdrawalDialog:
    """Modeless form; ``on_submit(choice)`` does the work and returns True
    to close (False keeps the form open, e.g. after showing an error)."""

    def __init__(self, parent, *, title: str, heading: str,
                 on_submit: Callable[[WithdrawalChoice], bool],
                 note: str | None = None, show_approved: bool = True,
                 ok_label: str = "Withdraw",
                 default_reason: str | None = None) -> None:
        self.on_submit = on_submit
        self.win = dlg = make_toplevel(parent)
        dlg.title(title)
        dlg.resizable(False, False)
        ttk.Label(dlg, text=heading, font=("", 10, "bold"), wraplength=560,
                  justify="left").grid(row=0, column=0, columnspan=2,
                                       sticky="w", padx=12, pady=(12, 8))
        self.reason_var = tk.StringVar(value=next(
            (c for c in reason_choices() if reason_code(c) == default_reason), ""))
        self.detail_var = tk.StringVar()
        self.approved_var = tk.StringVar()
        self.date_picker = DatePicker(dlg, value=_dt.date.today().isoformat())
        rows: list[tuple[str, tk.Widget]] = [
            ("ILR withdrawal reason:", ttk.Combobox(
                dlg, textvariable=self.reason_var, values=reason_choices(),
                state="readonly", width=60)),
            ("Last day in learning:", self.date_picker),
            ("Detail (optional):", ttk.Entry(dlg, textvariable=self.detail_var,
                                             width=62)),
        ]
        if show_approved:
            rows.append(("Approved by (optional):",
                         ttk.Entry(dlg, textvariable=self.approved_var, width=26)))
        for i, (label, widget) in enumerate(rows, start=1):
            ttk.Label(dlg, text=label).grid(row=i, column=0, sticky="e",
                                            padx=(12, 6), pady=3)
            widget.grid(row=i, column=1, sticky="w", padx=(0, 12), pady=3)
        ttk.Label(dlg, foreground="#555", wraplength=560, justify="left", text=(
            note or "The learning aims of that year are withdrawn too (and "
            "remembered, so a reinstatement reopens them). If it is the "
            "learner's last live enrolment their student record is marked "
            "as left.")).grid(row=len(rows) + 1, column=0, columnspan=2,
                              sticky="w", padx=12, pady=(6, 0))
        bar = ttk.Frame(dlg)
        bar.grid(row=len(rows) + 2, column=0, columnspan=2, sticky="e",
                 padx=12, pady=12)
        ttk.Button(bar, text=ok_label, command=self.ok).pack(side="left", padx=(0, 6))
        ttk.Button(bar, text="Cancel", command=dlg.destroy).pack(side="left")
        dlg.bind("<Escape>", lambda _e: dlg.destroy())
        dlg.grab_set()

    def choice(self) -> WithdrawalChoice | None:
        code = reason_code(self.reason_var.get())
        if not code:
            return None
        return WithdrawalChoice(
            reason=code, withdrawal_date=self.date_picker.get() or None,
            detail=self.detail_var.get().strip() or None,
            approved_by=self.approved_var.get().strip() or None)

    def ok(self) -> None:
        choice = self.choice()
        if choice is None:
            messagebox.showwarning("Reason needed",
                                   "Pick the ILR withdrawal reason.", parent=self.win)
            return
        if self.on_submit(choice):
            self.win.destroy()


# ── Result text ─────────────────────────────────────────────────────

def _bullets(title: str, items) -> list[str]:
    items = list(items)
    return ["", title, *(f"  • {x}" for x in items)] if items else []


def withdrawal_lines(result) -> list[str]:
    """``WithdrawalResult`` as lines for a message box."""
    e = result.enrolment
    lines = [f"Enrolment #{e.enrolment_id} ({e.academic_year}, Year "
             f"{e.year_group}) withdrawn — {e.withdrawal_date}, "
             f"{e.withdrawal_reason_label}."]
    lines += _bullets("Learning aims ended:", result.aims_ended)
    lines += _bullets("Not ended — please check:", result.aim_problems)
    if not result.aims_ended and not result.aim_problems:
        lines += ["", "No active learning aims to end."]
    if result.student_left:
        lines += ["", "This was their last live enrolment: the student record "
                      "is now marked as Left."]
    lines += _bullets("Student record:", result.student_notes)
    return lines


def reinstate_lines(result) -> list[str]:
    """``ReinstateResult`` as lines for a message box."""
    e = result.enrolment
    lines = [f"Enrolment #{e.enrolment_id} ({e.academic_year}, Year "
             f"{e.year_group}) reinstated as {e.status}."]
    lines += _bullets("Learning aims reopened:", result.aims_reopened)
    lines += _bullets("Not reopened — please check:", result.aim_problems)
    if not result.aims_reopened and not result.aim_problems:
        lines += ["", "No learning aims needed reopening."]
    if result.student_reinstated:
        lines += ["", "The student record was put back on roll."]
    lines += _bullets("Student record — and to do now they are back:",
                      result.student_notes)
    return lines


def undo_rollover_lines(result) -> list[str]:
    lines = [f"Rollover run #{result.run_id} undone: {result.reverted} "
             "enrolment(s) put back."]
    lines += _bullets("Left alone (changed since the run):", result.kept)
    lines += _bullets("Aims not reopened — please check:", result.aim_problems)
    return lines
