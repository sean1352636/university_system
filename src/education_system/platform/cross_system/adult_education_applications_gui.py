"""Referrals to Adult Education - the FE college's board (see
``adult_education_applications``).

Hosted by FE College. Lists the college's referrals with Adult Education's
latest decision (with the service, declined, enrolled) and refers a
learner. Adult Education works its end on its *Referrals from FE College*
page; enrolling the learner on a class there completes the referral here.

The platform can't list a college's learners, so the host passes
``learners``: a function returning ``[(student_id, label), ...]``.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from datetime import date
from tkinter import ttk

from education_system.platform.cross_system import adult_education_applications as service
from education_system.platform.delivery.gui.parented_dialogs import messagebox

TITLE = "Referrals to Adult Education"


def render(parent: tk.Misc, source_system: str, *,
           learners: Callable[[], list[tuple[str, str]]], can_refer: bool = True,
           referrer: str = "", actor_user_id: int | None = None) -> None:
    ttk.Label(parent, text=TITLE, font=("", 16, "bold")).pack(anchor="w")
    ttk.Label(parent, foreground="#555", wraplength=860, justify="left", text=(
        "Refer an adult to a community course - English, maths, ESOL, digital skills or "
        "a part-time course. Adult Education records an enquiry and decides; when the "
        "learner enrols on a class there, the referral shows as enrolled here. The FE "
        "place stays open. Support needs only go with the learner's consent; "
        "safeguarding only as a file reference.")).pack(anchor="w", pady=(0, 8))
    cols = (("learner", "Learner", 190), ("course", "Course / subject", 200),
            ("status", "Status", 150), ("sent", "Referred", 100),
            ("reason", "Reason / decision", 320))
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
            rows = service.referrals_from(source_system)
        except Exception as exc:  # noqa: BLE001 - the platform queue unreachable
            status.set(f"The platform's referrals can't be read: {exc}")
            return
        for row in rows:
            decision = row.get("decision_reason") or row.get("reason") or ""
            table.insert("", "end", iid=row["transition_id"], values=(
                row.get("learner") or "", row.get("course") or "", row["label"],
                (row.get("initiated_at") or "")[:10], decision))
        enrolled = sum(1 for r in rows if r["label"] == "Enrolled")
        status.set(f"{len(rows)} referral(s), {enrolled} enrolled")

    buttons = ttk.Frame(parent)
    buttons.pack(fill="x", pady=(8, 0))
    send = ttk.Button(buttons, text="Refer a learner…", command=lambda: _refer_dialog(
        parent, source_system, learners, referrer, actor_user_id, refresh))
    send.pack(side="left")
    if not can_refer:
        send.state(["disabled"])
    ttk.Button(buttons, text="Refresh", command=refresh).pack(side="left", padx=(6, 0))
    ttk.Label(parent, textvariable=status, foreground="#555").pack(anchor="w", pady=(6, 0))
    refresh()


def _refer_dialog(parent: tk.Misc, source_system: str, learners, referrer: str,
                  actor_user_id: int | None, on_done) -> None:
    try:
        options = list(learners())
    except Exception as exc:  # noqa: BLE001
        messagebox.showerror(TITLE, f"The learner list can't be read: {exc}", parent=parent)
        return
    if not options:
        messagebox.showinfo(TITLE, "There are no learners to refer.", parent=parent)
        return
    win = tk.Toplevel(parent.winfo_toplevel())
    win.title("Refer to Adult Education")
    win.transient(parent.winfo_toplevel())
    form = ttk.Frame(win, padding=14)
    form.pack(fill="both", expand=True)
    labels = [label for _id, label in options]
    learner = ttk.Combobox(form, values=labels, width=46)
    course = ttk.Entry(form, width=48)
    start = ttk.Entry(form, width=48)
    start.insert(0, date.today().isoformat())
    who = ttk.Entry(form, width=48)
    who.insert(0, referrer)
    sg = ttk.Entry(form, width=48)
    reason = tk.Text(form, width=48, height=4, wrap="word")
    rows = (("Learner", learner), ("Course or subject", course),
            ("Intended start (YYYY-MM-DD)", start), ("Reason", reason),
            ("Referred by (name)", who), ("Safeguarding file reference", sg))
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
        sid = options[labels.index(learner.get())][0]
        try:
            row = service.refer(
                source_system, str(sid), course=course.get(),
                reason=reason.get("1.0", "end").strip(),
                intended_start=start.get().strip() or None, referrer=who.get().strip(),
                consent=consent.get(), safeguarding_reference=sg.get().strip() or None,
                actor_user_id=actor_user_id)
        except Exception as exc:  # noqa: BLE001 - shown to the user
            messagebox.showerror("Not referred", str(exc), parent=win)
            return
        messagebox.showinfo("Referred", "Adult Education has the referral on its "
                            "Referrals from FE College page.\n\nStatus: "
                            + service.STATUS_LABELS.get(row["status"], row["status"]),
                            parent=win)
        win.destroy()
        on_done()

    ttk.Button(form, text="Send referral", command=submit).grid(
        row=len(rows) + 2, column=1, sticky="e", pady=(10, 0))


__all__ = ["TITLE", "render"]
