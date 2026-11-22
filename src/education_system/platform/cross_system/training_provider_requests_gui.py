"""Training Provider Requests - the sender's board (see
``training_provider_requests``).

Hosted by Apprenticeships and FE College. Lists the sender's requests with
the training provider's decision and latest outcome (booked, certificate
issued, did not attend) and sends a new request. The training provider
works its end on its *Training Requests* page.

The platform can't list a sender's learners, so the host passes
``learners``: a function returning ``[(learner_id, label), ...]``.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from datetime import date, timedelta
from tkinter import ttk

from education_system.platform.cross_system import training_provider_requests as service
from education_system.platform.delivery.gui.parented_dialogs import messagebox

TITLE = "Training Provider Requests"


def render(parent: tk.Misc, source_system: str, *,
           learners: Callable[[], list[tuple[str, str]]], can_request: bool = True,
           referrer: str = "", actor_user_id: int | None = None) -> None:
    ttk.Label(parent, text=TITLE, font=("", 16, "bold")).pack(anchor="w")
    ttk.Label(parent, foreground="#555", wraplength=860, justify="left", text=(
        "Ask the training provider to train a learner on a short course - first aid, "
        "health and safety, a licence to practise. The learner's programme here stays "
        "open. When the provider issues the certificate it comes back here"
        + (" as off-the-job hours awaiting approval." if source_system == "apprenticeships"
           else " and onto the learner's prior attainment.")
        + " Support needs only go with the learner's consent; safeguarding only as a "
          "file reference.")).pack(anchor="w", pady=(0, 8))
    cols = (("learner", "Learner", 170), ("course", "Course", 190),
            ("status", "Status", 150), ("sent", "Sent", 95),
            ("latest", "Training provider's latest", 330))
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    table = ttk.Treeview(frame, columns=[c[0] for c in cols], show="headings", height=14)
    for key, text, width in cols:
        table.heading(key, text=text)
        table.column(key, width=width, anchor="w")
    bar = ttk.Scrollbar(frame, orient="vertical", command=table.yview)
    table.configure(yscrollcommand=bar.set)
    table.pack(side="left", fill="both", expand=True)
    bar.pack(side="right", fill="y")
    status = tk.StringVar()

    def refresh() -> None:
        table.delete(*table.get_children())
        try:
            rows = service.requests_from(source_system)
        except Exception as exc:  # noqa: BLE001 - the platform queue unreachable
            status.set(f"The platform's requests can't be read: {exc}")
            return
        for row in rows:
            latest = row.get("latest") or row.get("decision_reason") or ""
            table.insert("", "end", iid=row["transition_id"], values=(
                row.get("learner") or "", row.get("course") or "", row["label"],
                (row.get("initiated_at") or "")[:10], latest))
        done = sum(1 for r in rows if r["label"] == "Certificated")
        status.set(f"{len(rows)} request(s), {done} certificated")

    def show_outcomes() -> None:
        sel = table.selection()
        if not sel:
            messagebox.showinfo(TITLE, "Select a request first.", parent=parent)
            return
        notes = service.outcomes_for(sel[0])
        text = "\n".join(f"{(n.get('at') or '')[:10]}  "
                         f"{n['note'].removeprefix('Training provider: ')}"
                         for n in notes) or "No outcome from the training provider yet."
        messagebox.showinfo("From the training provider", text, parent=parent)

    buttons = ttk.Frame(parent)
    buttons.pack(fill="x", pady=(8, 0))
    send = ttk.Button(buttons, text="New request…", command=lambda: _request_dialog(
        parent, source_system, learners, referrer, actor_user_id, refresh))
    send.pack(side="left")
    if not can_request:
        send.state(["disabled"])
    ttk.Button(buttons, text="Outcomes…", command=show_outcomes).pack(side="left", padx=(6, 0))
    ttk.Button(buttons, text="Refresh", command=refresh).pack(side="left", padx=(6, 0))
    table.bind("<Double-1>", lambda _e: show_outcomes())
    ttk.Label(parent, textvariable=status, foreground="#555").pack(anchor="w", pady=(6, 0))
    refresh()


def _request_dialog(parent: tk.Misc, source_system: str, learners, referrer: str,
                    actor_user_id: int | None, on_done) -> None:
    try:
        options = list(learners())
    except Exception as exc:  # noqa: BLE001
        messagebox.showerror(TITLE, f"The learner list can't be read: {exc}", parent=parent)
        return
    if not options:
        messagebox.showinfo(TITLE, "There are no learners to send.", parent=parent)
        return
    win = tk.Toplevel(parent.winfo_toplevel())
    win.title("Request to the training provider")
    win.transient(parent.winfo_toplevel())
    form = ttk.Frame(win, padding=14)
    form.pack(fill="both", expand=True)
    labels = [label for _id, label in options]
    learner = ttk.Combobox(form, values=labels, width=46)
    course = ttk.Entry(form, width=48)
    needed = ttk.Entry(form, width=48)
    needed.insert(0, (date.today() + timedelta(days=28)).isoformat())
    payer = ttk.Combobox(form, values=service.PAYERS, state="readonly", width=46)
    payer.set(service.PAYERS[0])
    po = ttk.Entry(form, width=48)
    who = ttk.Entry(form, width=48)
    who.insert(0, referrer)
    sg = ttk.Entry(form, width=48)
    reason = tk.Text(form, width=48, height=4, wrap="word")
    rows = (("Learner", learner), ("Course", course), ("Needed by (YYYY-MM-DD)", needed),
            ("Who pays", payer), ("Purchase order number", po), ("Why", reason),
            ("Requested by (name)", who), ("Safeguarding file reference", sg))
    for n, (text, widget) in enumerate(rows):
        ttk.Label(form, text=text).grid(row=n, column=0, sticky="nw", pady=4)
        widget.grid(row=n, column=1, sticky="w", padx=(8, 0), pady=4)
    ttk.Label(form, foreground="#888", text="A reference only - never the details.").grid(
        row=len(rows), column=1, sticky="w", padx=(8, 0))
    consent = tk.BooleanVar(value=False)
    ttk.Checkbutton(form, variable=consent, text="The learner consents to sharing their "
                    "support needs").grid(row=len(rows) + 1, column=0, columnspan=2,
                                          sticky="w", pady=(6, 0))

    def submit() -> None:
        if learner.get() not in labels:
            messagebox.showwarning(TITLE, "Choose the learner from the list.", parent=win)
            return
        lid = options[labels.index(learner.get())][0]
        try:
            row = service.request(
                source_system, str(lid), course=course.get(),
                reason=reason.get("1.0", "end").strip(),
                needed_by=needed.get().strip() or None, payer=payer.get(),
                po_number=po.get().strip(), referrer=who.get().strip(),
                consent=consent.get(), safeguarding_reference=sg.get().strip() or None,
                actor_user_id=actor_user_id)
        except Exception as exc:  # noqa: BLE001 - shown to the user
            messagebox.showerror("Not sent", str(exc), parent=win)
            return
        messagebox.showinfo("Sent", "The training provider has the request on its "
                            "Training Requests page.\n\nStatus: "
                            + service.STATUS_LABELS.get(row["status"], row["status"]),
                            parent=win)
        win.destroy()
        on_done()

    ttk.Button(form, text="Send request", command=submit).grid(
        row=len(rows) + 2, column=1, sticky="e", pady=(10, 0))


__all__ = ["TITLE", "render"]
