"""Small staff dialog for referring a Sixth Form learner to FE College."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox

from education_system.systems.sixth_form.domain.progression import post16_pathway


def open_window(parent) -> None:
    # *parent* is the shell object, not a widget — the Tk window hangs off
    # its ``.root``. Both calls below need the unwrapped widget: passing the
    # shell to transient() raises
    #   bad window path name "<...SixthFormMainGUI object at 0x...>"
    owner = getattr(parent, "root", parent)
    win = tk.Toplevel(owner)
    win.title("Refer to FE College")
    win.transient(owner)
    frame = ttk.Frame(win, padding=16)
    frame.pack(fill="both", expand=True)
    fields = {}
    for row, (key, label) in enumerate((
        ("student_id", "Sixth Form student ID"),
        ("pathway", "Requested FE pathway"),
        ("reason", "Reason for referral"),
        ("intended_start", "Intended start (YYYY-MM-DD)"),
    )):
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=4)
        fields[key] = ttk.Entry(frame, width=48)
        fields[key].grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=4)
    consent = tk.BooleanVar(value=False)
    ttk.Checkbutton(
        frame, text="Learner consents to sharing support information",
        variable=consent).grid(row=4, column=0, columnspan=2, sticky="w", pady=8)

    def submit():
        try:
            result = post16_pathway.refer(
                fields["student_id"].get(), pathway=fields["pathway"].get(),
                reason=fields["reason"].get(),
                intended_start=fields["intended_start"].get() or None,
                consent=consent.get())
        except Exception as exc:
            messagebox.showerror("Referral not created", str(exc), parent=win)
            return
        messagebox.showinfo(
            "Referral created",
            f"FE applicant created.\nTransition: {result['transition_id']}", parent=win)
        win.destroy()

    ttk.Button(frame, text="Create referral", command=submit).grid(
        row=5, column=1, sticky="e", pady=(10, 0))
    frame.columnconfigure(1, weight=1)


__all__ = ["open_window"]
