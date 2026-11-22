"""SEND Service Requests - the school's board (see ``send_referrals``).

Hosted by the Primary and Secondary systems. Lists the school's requests to
the SEND service with the service's latest decision (assessment requested,
agreed or refused, plan issued, ceased), and - for the SENCO - sends a new
request. The SEND service works its end on its own School Requests and EHCP
Tracker pages; its EHCP decisions also update this school's SEN record.

The platform can't list a school's pupils, so the school passes
``pupils``: a function returning ``[(pupil_id, label), ...]`` for its roll.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from datetime import date
from tkinter import ttk

from education_system.platform.cross_system import send_referrals as service
from education_system.platform.delivery.gui.parented_dialogs import messagebox

TITLE = "SEND Service Requests"


def render(parent: tk.Misc, school: str, *, pupils: Callable[[], list[tuple[str, str]]],
           can_request: bool = False, referrer: str = "",
           actor_user_id: int | None = None) -> None:
    ttk.Label(parent, text=TITLE, font=("", 16, "bold")).pack(anchor="w")
    ttk.Label(parent, foreground="#555", wraplength=860, justify="left", text=(
        "Ask the SEND service for advice and support, or make an EHC needs assessment "
        "request. The pupil stays on this school's roll. The service's EHCP decisions come "
        "back here and onto the pupil's SEN record: a final plan issued sets their SEN "
        "status to EHC plan, a ceased plan returns them to SEN support. SEN, medical and "
        "support details only go with the parent's consent; safeguarding only as a file "
        "reference.")).pack(anchor="w", pady=(0, 8))
    cols = (("pupil", "Pupil", 190), ("request", "Request", 210), ("status", "Status", 110),
            ("sent", "Sent", 100), ("latest", "SEND service's latest", 300),
            ("when", "On", 100))
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
            rows = service.requests_from(school)
        except Exception as exc:  # noqa: BLE001 - the platform queue unreachable
            status.set(f"The platform's requests can't be read: {exc}")
            return
        for row in rows:
            table.insert("", "end", iid=row["transition_id"], values=(
                row.get("pupil") or "", row.get("reason") or "", row["label"],
                (row.get("initiated_at") or "")[:10], row.get("latest") or "",
                row.get("latest_at") or ""))
        open_ = sum(1 for r in rows if r["label"] == "Open case")
        status.set(f"{len(rows)} request(s), {open_} open case(s)")

    def show_updates() -> None:
        sel = table.selection()
        if not sel:
            messagebox.showinfo(TITLE, "Select a request first.", parent=parent)
            return
        notes = service.updates_for(sel[0])
        text = "\n".join(f"{(n.get('at') or '')[:10]}  "
                         f"{(n.get('note') or '').removeprefix('SEND service: ')}"
                         for n in notes) or "No updates from the SEND service yet."
        messagebox.showinfo("Updates from the SEND service", text, parent=parent)

    buttons = ttk.Frame(parent)
    buttons.pack(fill="x", pady=(8, 0))
    send = ttk.Button(buttons, text="New request…", command=lambda: _request_dialog(
        parent, school, pupils, referrer, actor_user_id, refresh))
    send.pack(side="left")
    if not can_request:
        send.state(["disabled"])
        ttk.Label(buttons, text="Only the SENCO can send requests.",
                  foreground="#888").pack(side="left", padx=8)
    ttk.Button(buttons, text="Updates…", command=show_updates).pack(side="left", padx=(6, 0))
    ttk.Button(buttons, text="Refresh", command=refresh).pack(side="left", padx=(6, 0))
    table.bind("<Double-1>", lambda _e: show_updates())
    ttk.Label(parent, textvariable=status, foreground="#555").pack(anchor="w", pady=(6, 0))
    refresh()


def _request_dialog(parent: tk.Misc, school: str, pupils, referrer: str,
                    actor_user_id: int | None, on_done) -> None:
    try:
        options = list(pupils())
    except Exception as exc:  # noqa: BLE001
        messagebox.showerror(TITLE, f"The pupil list can't be read: {exc}", parent=parent)
        return
    if not options:
        messagebox.showinfo(TITLE, "There are no pupils on roll.", parent=parent)
        return
    win = tk.Toplevel(parent.winfo_toplevel())
    win.title("Request to the SEND service")
    win.transient(parent.winfo_toplevel())
    form = ttk.Frame(win, padding=14)
    form.pack(fill="both", expand=True)
    labels = [label for _id, label in options]
    pupil = ttk.Combobox(form, values=labels, width=46)
    request = ttk.Combobox(form, values=service.REQUESTS, state="readonly", width=46)
    request.set(service.REQUESTS[0])
    when = ttk.Entry(form, width=48)
    when.insert(0, date.today().isoformat())
    who = ttk.Entry(form, width=48)
    who.insert(0, referrer)
    sg = ttk.Entry(form, width=48)
    summary = tk.Text(form, width=48, height=4, wrap="word")
    tried = tk.Text(form, width=48, height=4, wrap="word")
    rows = (("Pupil", pupil), ("Request", request), ("Date (YYYY-MM-DD)", when),
            ("Why", summary), ("What the school has tried", tried),
            ("Requested by (name)", who), ("Safeguarding file reference", sg))
    for n, (text, widget) in enumerate(rows):
        ttk.Label(form, text=text).grid(row=n, column=0, sticky="nw", pady=4)
        widget.grid(row=n, column=1, sticky="w", padx=(8, 0), pady=4)
    ttk.Label(form, foreground="#888", text="A reference only (e.g. the DSL's file number) - "
              "never the details.").grid(row=len(rows), column=1, sticky="w", padx=(8, 0))
    consent = tk.BooleanVar(value=False)
    ttk.Checkbutton(form, variable=consent, text="The parent consents to sharing SEN, medical "
                    "and support details").grid(row=len(rows) + 1, column=0, columnspan=2,
                                                sticky="w", pady=(6, 0))

    def submit() -> None:
        if pupil.get() not in labels:
            messagebox.showwarning(TITLE, "Choose the pupil from the list.", parent=win)
            return
        pid = options[labels.index(pupil.get())][0]
        try:
            row = service.refer(
                school, str(pid), request=request.get(),
                summary=summary.get("1.0", "end").strip(),
                tried=tried.get("1.0", "end").strip(), referrer=who.get().strip(),
                request_date=when.get().strip() or None, consent=consent.get(),
                safeguarding_reference=sg.get().strip() or None,
                actor_user_id=actor_user_id)
        except Exception as exc:  # noqa: BLE001 - shown to the user
            messagebox.showerror("Not sent", str(exc), parent=win)
            return
        messagebox.showinfo("Sent", "The SEND service has the request on its School "
                            "Requests page.\n\nStatus: " + service.STATUS_LABELS.get(
                                row["status"], row["status"]), parent=win)
        win.destroy()
        on_done()

    ttk.Button(form, text="Send request", command=submit).grid(
        row=len(rows) + 2, column=1, sticky="e", pady=(10, 0))


__all__ = ["TITLE", "render"]
