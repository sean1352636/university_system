"""Sixth Form admissions queue for applications from FE College."""

from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import messagebox, simpledialog, ttk

from education_system.systems.fe_college.services import sixth_form_transfer


def open_window(parent) -> None:
    owner = getattr(parent, "root", parent)
    win = tk.Toplevel(owner)
    win.title("Incoming FE Applications")
    frame = ttk.Frame(win, padding=14)
    frame.pack(fill="both", expand=True)
    table = ttk.Treeview(frame, columns=("journey", "status", "reason"), show="headings")
    for key, label, width in (("journey", "Journey", 280), ("status", "Status", 130),
                              ("reason", "Reason", 360)):
        table.heading(key, text=label)
        table.column(key, width=width)
    table.pack(fill="both", expand=True)

    def selected():
        ids = table.selection()
        if not ids:
            messagebox.showwarning("Incoming FE Applications", "Select an application", parent=win)
            return None
        return ids[0]

    def refresh():
        table.delete(*table.get_children())
        for row in sixth_form_transfer.incoming():
            table.insert("", "end", iid=row["transition_id"], values=(
                row["journey_id"], row["status"], row.get("reason") or ""))

    def review():
        transition_id = selected()
        if not transition_id:
            return
        raw = simpledialog.askstring(
            "Subject choices", "Enter exactly three A-level subjects, separated by commas:",
            parent=win)
        if not raw:
            return
        eligible = messagebox.askyesno(
            "GCSE eligibility", "Does the learner meet the GCSE entry requirements?", parent=win)
        try:
            sixth_form_transfer.review_application(
                transition_id, subjects=[part.strip() for part in raw.split(",")],
                gcse_eligible=eligible)
            refresh()
        except Exception as exc:
            messagebox.showerror("Review failed", str(exc), parent=win)

    def accept():
        transition_id = selected()
        if transition_id:
            try:
                sixth_form_transfer.accept_offer(
                    transition_id, accepted_by="Learner",
                    consent=messagebox.askyesno(
                        "Consent", "Share consent-controlled support information?", parent=win))
                refresh()
            except Exception as exc:
                messagebox.showerror("Acceptance failed", str(exc), parent=win)

    def enrol():
        transition_id = selected()
        if not transition_id:
            return
        start = simpledialog.askstring(
            "Start date", "Start date (YYYY-MM-DD):",
            initialvalue=date.today().isoformat(), parent=win)
        if start:
            try:
                sixth_form_transfer.enrol(transition_id, start_date=start)
                refresh()
            except Exception as exc:
                messagebox.showerror("Enrolment not completed", str(exc), parent=win)

    bar = ttk.Frame(frame)
    bar.pack(fill="x", pady=(10, 0))
    for label, command in (("Review eligibility & subjects", review),
                           ("Record acceptance", accept), ("Enrol", enrol),
                           ("Refresh", refresh)):
        ttk.Button(bar, text=label, command=command).pack(side="left", padx=(0, 6))
    refresh()


__all__ = ["open_window"]
