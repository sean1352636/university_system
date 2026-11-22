"""Referrals to Alternative Provision - the school's board (see ``ap_referrals``).

Hosted by the Primary and Secondary systems. Lists the school's referrals
with where the AP has got to (with it, accepted, placed, declined, left the
AP) and, for staff allowed to refer, sends a new one. The AP works the other
end on its own Referrals page.

The platform can't list a school's pupils, so the school passes
``pupils``: a function returning ``[(pupil_id, label), ...]`` for its roll.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from education_system.platform.cross_system import ap_referrals as service
from education_system.platform.delivery.gui.parented_dialogs import messagebox

TITLE = "Referrals to Alternative Provision"


def render(parent: tk.Misc, school: str, *, pupils: Callable[[], list[tuple[str, str]]],
           can_refer: bool = False, referrer: str = "",
           actor_user_id: int | None = None) -> None:
    ttk.Label(parent, text=TITLE, font=("", 16, "bold")).pack(anchor="w")
    ttk.Label(parent, foreground="#555", wraplength=860, justify="left", text=(
        "Refer a pupil to the alternative provision (PRU / AP). The AP accepts or declines "
        "the referral and starts the placement. With dual registration the pupil stays on "
        "this school's roll; with sole registration (a permanent exclusion) the school "
        "records them as a leaver when the placement starts. SEN, medical, behaviour and "
        "exclusion details only go with the parent's consent; safeguarding only as a "
        "file reference.")).pack(anchor="w", pady=(0, 8))
    cols = (("pupil", "Pupil", 200), ("reason", "Reason", 230), ("status", "Status", 190),
            ("referred", "Referred", 120), ("note", "AP's note", 260))
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
            rows = service.referrals_from(school)
        except Exception as exc:  # noqa: BLE001 - the platform queue unreachable
            status.set(f"The platform's referral queue can't be read: {exc}")
            return
        for row in rows:
            note = row.get("decision_reason") or row.get("cancelled_reason") or ""
            if row.get("placement_ended") is not None:
                note = f"Left the AP {row['placement_ended']}".strip()
            table.insert("", "end", iid=row["transition_id"], values=(
                row.get("pupil") or "", row.get("reason") or "", row["label"],
                (row.get("initiated_at") or "")[:10], note))
        open_ = sum(1 for r in rows if r["status"] not in ("completed", "cancelled"))
        status.set(f"{len(rows)} referral(s), {open_} still with the AP")

    buttons = ttk.Frame(parent)
    buttons.pack(fill="x", pady=(8, 0))
    refer = ttk.Button(buttons, text="Refer a pupil…", command=lambda: _refer_dialog(
        parent, school, pupils, referrer, actor_user_id, refresh))
    refer.pack(side="left")
    if not can_refer:
        refer.state(["disabled"])
        ttk.Label(buttons, text="Only staff who manage admissions can refer.",
                  foreground="#888").pack(side="left", padx=8)
    ttk.Button(buttons, text="Refresh", command=refresh).pack(side="left", padx=(6, 0))
    ttk.Label(parent, textvariable=status, foreground="#555").pack(anchor="w", pady=(6, 0))
    refresh()


def _refer_dialog(parent: tk.Misc, school: str, pupils, referrer: str,
                  actor_user_id: int | None, on_done) -> None:
    try:
        options = list(pupils())
    except Exception as exc:  # noqa: BLE001
        messagebox.showerror(TITLE, f"The pupil list can't be read: {exc}", parent=parent)
        return
    if not options:
        messagebox.showinfo(TITLE, "There are no pupils on roll to refer.", parent=parent)
        return
    win = tk.Toplevel(parent.winfo_toplevel())
    win.title("Refer to Alternative Provision")
    win.transient(parent.winfo_toplevel())
    form = ttk.Frame(win, padding=14)
    form.pack(fill="both", expand=True)
    labels = [label for _id, label in options]
    pupil = ttk.Combobox(form, values=labels, width=46)
    reason = ttk.Combobox(form, values=service.REASONS, state="readonly", width=46)
    reg_labels = list(service.REGISTRATIONS.values())
    registration = ttk.Combobox(form, values=reg_labels, state="readonly", width=46)
    registration.set(reg_labels[0])
    excluded = ttk.Entry(form, width=48)
    who = ttk.Entry(form, width=48)
    who.insert(0, referrer)
    sg = ttk.Entry(form, width=48)
    summary = tk.Text(form, width=48, height=5, wrap="word")
    rows = (("Pupil", pupil), ("Reason", reason), ("Registration", registration),
            ("Exclusion starts (YYYY-MM-DD)", excluded), ("Referred by (name)", who),
            ("Background", summary), ("Safeguarding file reference", sg))
    for n, (text, widget) in enumerate(rows):
        ttk.Label(form, text=text).grid(row=n, column=0, sticky="nw", pady=4)
        widget.grid(row=n, column=1, sticky="w", padx=(8, 0), pady=4)
    ttk.Label(form, foreground="#888", text="A reference only (e.g. the DSL's file number) - "
              "never the details.").grid(row=len(rows), column=1, sticky="w", padx=(8, 0))
    consent = tk.BooleanVar(value=False)
    ttk.Checkbutton(form, variable=consent, text="The parent consents to sharing SEN, medical, "
                    "behaviour and exclusion details").grid(
        row=len(rows) + 1, column=0, columnspan=2, sticky="w", pady=(6, 0))

    def on_reason(_e=None) -> None:
        if reason.get() == service.REASONS[0]:   # permanent exclusion: sole registration
            registration.set(service.REGISTRATIONS[service.SOLE])
    reason.bind("<<ComboboxSelected>>", on_reason)

    def submit() -> None:
        if pupil.get() not in labels:
            messagebox.showwarning(TITLE, "Choose the pupil from the list.", parent=win)
            return
        pid = options[labels.index(pupil.get())][0]
        reg = next(k for k, v in service.REGISTRATIONS.items() if v == registration.get())
        try:
            row = service.refer(
                school, str(pid), reason=reason.get(), registration=reg,
                excluded_from=excluded.get().strip() or None,
                summary=summary.get("1.0", "end").strip(), referrer=who.get().strip(),
                consent=consent.get(), safeguarding_reference=sg.get().strip() or None,
                actor_user_id=actor_user_id)
        except Exception as exc:  # noqa: BLE001 - shown to the user
            messagebox.showerror("Not referred", str(exc), parent=win)
            return
        messagebox.showinfo("Referred", "The alternative provision has the referral on its "
                            "Referrals page.\n\nStatus: " + service.STATUS_LABELS.get(
                                row["status"], row["status"]), parent=win)
        win.destroy()
        on_done()

    ttk.Button(form, text="Send referral", command=submit).grid(
        row=len(rows) + 2, column=1, sticky="e", pady=(10, 0))


__all__ = ["TITLE", "render"]
