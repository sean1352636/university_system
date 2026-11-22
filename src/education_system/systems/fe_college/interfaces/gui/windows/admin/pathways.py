"""Incoming referrals from the Sixth Form, Apprenticeships, Adult Education and the
Training Provider, and linked
learner records. The workflow is the platform's (``fe_applications``)."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from education_system.platform.cross_system.student_view import build_overview, format_overview_text
from education_system.platform.cross_system import fe_applications

TITLE = "Incoming referrals"


def open_window(host) -> None:
    host.clear_content()
    parent = host.content_frame
    ttk.Label(parent, text=TITLE, font=("", 16, "bold")).pack(anchor="w")
    ttk.Label(parent, text="Learners referred by the Sixth Form, an apprenticeship "
                           "provider, Adult Education or the Training Provider (dual "
                           "enrolment is the default).").pack(
        anchor="w", pady=(0, 10))
    ttk.Button(parent, text="Transfer an FE learner to Sixth Form",
               command=lambda: _request_transfer(host)).pack(anchor="w", pady=(0, 10))
    table = ttk.Treeview(
        parent, columns=("source", "learner", "status", "reason"), show="headings", height=14)
    for key, label, width in (("source", "From", 120), ("learner", "Journey", 260),
                              ("status", "Status", 130), ("reason", "Reason", 340)):
        table.heading(key, text=label)
        table.column(key, width=width)
    table.pack(fill="both", expand=True)

    def refresh():
        table.delete(*table.get_children())
        for row in fe_applications.incoming_referrals():
            table.insert("", "end", iid=row["transition_id"], values=(
                fe_applications.SOURCE_LABELS.get(row["source_system"], row["source_system"]),
                row["journey_id"], row["status"], row.get("reason") or ""))

    def selected():
        choice = table.selection()
        if not choice:
            messagebox.showwarning(TITLE, "Select a referral first", parent=host.root)
            return None
        return choice[0]

    def accept():
        transition_id = selected()
        if transition_id:
            consent = messagebox.askyesno(
                TITLE, "Has the learner consented to sharing support information?",
                parent=host.root)
            try:
                fe_applications.accept_referral(
                    transition_id, accepted_by=host.ctl.identity.label, consent=consent)
                refresh()
            except Exception as exc:
                messagebox.showerror(TITLE, str(exc), parent=host.root)

    def enrol():
        transition_id = selected()
        if transition_id:
            row = next((r for r in fe_applications.incoming_referrals()
                        if r["transition_id"] == transition_id), {})
            source = fe_applications.SOURCE_LABELS.get(row.get("source_system"), "the source")
            concurrent = messagebox.askyesno(
                TITLE, f"Keep the learner enrolled at {source} as well (dual enrolment)?",
                parent=host.root)
            try:
                fe_applications.enrol_referral(transition_id, concurrent=concurrent)
                refresh()
            except Exception as exc:
                messagebox.showerror(TITLE, str(exc), parent=host.root)

    def linked():
        transition_id = selected()
        if not transition_id:
            return
        row = next(r for r in fe_applications.incoming_referrals()
                   if r["transition_id"] == transition_id)
        win = tk.Toplevel(host.root)
        win.title("Linked learner record")
        text = tk.Text(win, width=95, height=28, wrap="word")
        text.pack(fill="both", expand=True, padx=10, pady=10)
        text.insert("1.0", format_overview_text(build_overview(row["journey_id"])))
        text.configure(state="disabled")

    buttons = ttk.Frame(parent)
    buttons.pack(fill="x", pady=(10, 0))
    for label, command in (("Accept offer", accept), ("Enrol", enrol),
                           ("Linked record", linked), ("Refresh", refresh)):
        ttk.Button(buttons, text=label, command=command).pack(side="left", padx=(0, 6))
    refresh()
    host.set_status(TITLE)


def _request_transfer(host) -> None:
    from education_system.systems.fe_college.services import sixth_form_transfer

    win = tk.Toplevel(host.root)
    win.title("Transfer to Sixth Form")
    form = ttk.Frame(win, padding=14)
    form.pack(fill="both", expand=True)
    entries = {}
    for row, (key, label) in enumerate((
        ("student_id", "FE learner ID"), ("reason", "Reason for transfer"),
        ("start", "Intended start (YYYY-MM-DD)"))):
        ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=4)
        entries[key] = ttk.Entry(form, width=46)
        entries[key].grid(row=row, column=1, padx=(8, 0), pady=4)
    consent = tk.BooleanVar(value=False)
    ttk.Checkbutton(form, text="Learner consents to sharing support information",
                    variable=consent).grid(row=3, column=0, columnspan=2, sticky="w")

    def submit():
        try:
            result = sixth_form_transfer.request_transfer(
                entries["student_id"].get(), reason=entries["reason"].get(),
                intended_start=entries["start"].get() or None, consent=consent.get())
        except Exception as exc:
            messagebox.showerror("Transfer not requested", str(exc), parent=win)
            return
        messagebox.showinfo("Transfer requested",
                            f"Sixth Form application created.\n{result['transition_id']}",
                            parent=win)
        win.destroy()

    ttk.Button(form, text="Send application", command=submit).grid(
        row=4, column=1, sticky="e", pady=(10, 0))
