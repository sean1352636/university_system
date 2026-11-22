"""Referral board into FE College, for a sending system (see ``fe_applications``).

Hosted by the Apprenticeships, Adult Education and Training Provider systems (and usable by any source in
``fe_applications.SOURCE_SYSTEMS``): lists the source's referrals with their
live status and, unless read-only, refers a learner. FE College works the
other end in its Incoming referrals screen.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from education_system.platform.cross_system import fe_applications as service
from education_system.platform.delivery.gui.parented_dialogs import messagebox

_STATUS = {"offered": "Offered (FE to accept)", "accepted": "Accepted",
           "handover_approved": "Accepted — awaiting enrolment",
           "admitted": "Enrolled", "completed": "Enrolled", "cancelled": "Cancelled"}


def render(gui, source_system: str, *, parent: tk.Misc, read_only: bool = False) -> None:
    label = service.SOURCE_LABELS.get(source_system, source_system)
    ttk.Label(parent, text="FE College Referrals", font=("", 16, "bold")).pack(anchor="w")
    ttk.Label(parent, foreground="#555", wraplength=760, text=(
        f"Refer a {label.lower()} learner onto an FE College course. FE admissions "
        "accept and enrol; dual enrolment is the default, so the learner keeps "
        "their place here.")).pack(anchor="w", pady=(0, 8))
    table = ttk.Treeview(parent, columns=("status", "reason", "started"),
                         show="headings", height=12)
    for key, text, width in (("status", "Status", 220), ("reason", "Reason", 380),
                             ("started", "Referred", 160)):
        table.heading(key, text=text)
        table.column(key, width=width)
    table.pack(fill="both", expand=True)

    def refresh() -> None:
        table.delete(*table.get_children())
        try:
            rows = service.incoming_referrals(source_system=source_system)
        except Exception as exc:  # noqa: BLE001 - shown, not raised
            messagebox.showerror("FE College Referrals", str(exc), parent=parent)
            return
        for r in rows:
            table.insert("", "end", iid=r["transition_id"], values=(
                _STATUS.get(r["status"], r["status"]), r.get("reason") or "",
                r.get("initiated_at") or ""))

    buttons = ttk.Frame(parent)
    buttons.pack(fill="x", pady=(8, 0))
    refer_button = ttk.Button(buttons, text="Refer a learner…",
                              command=lambda: _refer_dialog(parent, source_system, refresh))
    refer_button.pack(side="left")
    if read_only:
        refer_button.state(["disabled"])
    ttk.Button(buttons, text="Refresh", command=refresh).pack(side="left", padx=(6, 0))
    refresh()


def _refer_dialog(parent: tk.Misc, source_system: str, on_done) -> None:
    win = tk.Toplevel(parent.winfo_toplevel())
    win.title("Refer to FE College")
    win.transient(parent.winfo_toplevel())
    form = ttk.Frame(win, padding=14)
    form.pack(fill="both", expand=True)
    entries: dict[str, ttk.Entry] = {}
    id_label = {"adult_education": "Learner ref (e.g. AE000012)",
                "training_provider": "Learner ref (e.g. TP000012)"}.get(
        source_system, "Learner ID")
    for row, (key, text) in enumerate((("student_id", id_label),
                                       ("pathway", "FE course / pathway"),
                                       ("reason", "Reason for referral"),
                                       ("start", "Intended start (YYYY-MM-DD)"))):
        ttk.Label(form, text=text).grid(row=row, column=0, sticky="w", pady=4)
        entries[key] = ttk.Entry(form, width=44)
        entries[key].grid(row=row, column=1, padx=(8, 0), pady=4)
    consent = tk.BooleanVar(value=False)
    ttk.Checkbutton(form, text="Learner consents to sharing support information",
                    variable=consent).grid(row=4, column=0, columnspan=2, sticky="w")

    def submit() -> None:
        try:
            row = service.refer(
                source_system, entries["student_id"].get().strip(),
                pathway=entries["pathway"].get(), reason=entries["reason"].get(),
                intended_start=entries["start"].get().strip() or None,
                consent=consent.get())
        except Exception as exc:  # noqa: BLE001 - shown to the user
            messagebox.showerror("Not referred", str(exc), parent=win)
            return
        messagebox.showinfo("Referred", "FE College admissions will see the referral "
                            f"in Incoming referrals.\n\n{row['transition_id']}", parent=win)
        win.destroy()
        on_done()

    ttk.Button(form, text="Send referral", command=submit).grid(
        row=5, column=1, sticky="e", pady=(10, 0))


__all__ = ["render"]
