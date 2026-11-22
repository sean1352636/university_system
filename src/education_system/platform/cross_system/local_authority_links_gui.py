"""Local Authority - the school's board (see ``local_authority_links``).

Hosted by the Primary and Secondary systems. Two tabs:

* **Notifications** - what this school has told the authority (attendance
  referrals, suspensions and exclusions, children missing education,
  elective home education, EHC needs assessment requests) with the
  authority's latest update on each; the head / admissions office sends a
  new one.
* **School places** - places the authority has allocated at this school and
  where each one is (the child is enrolled on this school's own Admissions
  page - primary - or matched under Incoming pupils - secondary).

The platform can't list a school's pupils, so the school passes ``pupils``:
a function returning ``[(pupil_id, label), ...]`` for its roll.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from datetime import date
from tkinter import ttk

from education_system.platform.cross_system import local_authority_links as service
from education_system.platform.delivery.gui.parented_dialogs import messagebox

TITLE = "Local Authority"
_PREFIX = f"{service.LABEL}: "


def _table(parent: tk.Misc, cols) -> ttk.Treeview:
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    table = ttk.Treeview(frame, columns=[c[0] for c in cols], show="headings", height=12)
    for key, text, width in cols:
        table.heading(key, text=text)
        table.column(key, width=width, anchor="w")
    bar = ttk.Scrollbar(frame, orient="vertical", command=table.yview)
    table.configure(yscrollcommand=bar.set)
    table.pack(side="left", fill="both", expand=True)
    bar.pack(side="right", fill="y")
    return table


def render(parent: tk.Misc, school: str, *, pupils: Callable[[], list[tuple[str, str]]],
           can_notify: bool = False, referrer: str = "",
           actor_user_id: int | None = None) -> None:
    ttk.Label(parent, text=TITLE, font=("", 16, "bold")).pack(anchor="w")
    ttk.Label(parent, foreground="#555", wraplength=860, justify="left", text=(
        "Tell the local authority what it must know - an attendance referral, a "
        "suspension or permanent exclusion, a child missing education, a parent's notice "
        "of home education - or ask for an EHC needs assessment. The pupil stays on this "
        "school's roll. The authority's decisions come back here; its EHC decisions also "
        "update the pupil's SEN record. SEN, medical and exclusion history only go with "
        "the parent's consent; safeguarding only as a file reference.")).pack(
        anchor="w", pady=(0, 8))
    book = ttk.Notebook(parent)
    book.pack(fill="both", expand=True)
    status = tk.StringVar()

    # ── notifications ────────────────────────────────────────────────
    tab = ttk.Frame(book, padding=6)
    book.add(tab, text="Notifications")
    notes = _table(tab, (("pupil", "Pupil", 180), ("kind", "Notification", 200),
                         ("status", "Status", 100), ("sent", "Sent", 95),
                         ("latest", "Authority's latest", 320), ("when", "On", 95)))

    def refresh() -> None:
        for table in (notes, places):
            table.delete(*table.get_children())
        try:
            rows = service.notifications_from(school)
            allocated = service.places_for(school)
        except Exception as exc:  # noqa: BLE001 - the platform queue unreachable
            status.set(f"The platform can't be read: {exc}")
            return
        for row in rows:
            notes.insert("", "end", iid=row["transition_id"], values=(
                row.get("pupil") or "", row.get("reason") or "", row["label"],
                (row.get("initiated_at") or "")[:10], row.get("latest") or "",
                row.get("latest_at") or ""))
        for row in allocated:
            place = row.get("place") or {}
            places.insert("", "end", iid=row["transition_id"], values=(
                row.get("pupil") or "", place.get("round") or row.get("reason") or "",
                place.get("basis") or "", place.get("start_date") or "",
                row["label"], (row.get("initiated_at") or "")[:10]))
        waiting = sum(1 for r in allocated if r["status"] == "handover_approved")
        status.set(f"{len(rows)} notification(s); {len(allocated)} school place(s), "
                   f"{waiting} to admit")

    def show_updates() -> None:
        sel = notes.selection()
        if not sel:
            messagebox.showinfo(TITLE, "Select a notification first.", parent=parent)
            return
        got = service.updates_for(sel[0])
        text = "\n".join(f"{(n.get('at') or '')[:10]}  "
                         f"{(n.get('note') or '').removeprefix(_PREFIX)}"
                         for n in got) or "No updates from the local authority yet."
        messagebox.showinfo("Updates from the local authority", text, parent=parent)

    buttons = ttk.Frame(tab)
    buttons.pack(fill="x", pady=(8, 0))
    send = ttk.Button(buttons, text="New notification…", command=lambda: _notify_dialog(
        parent, school, pupils, referrer, actor_user_id, refresh))
    send.pack(side="left")
    if not can_notify:
        send.state(["disabled"])
        ttk.Label(buttons, text="Only the head or admissions office can send notifications.",
                  foreground="#888").pack(side="left", padx=8)
    ttk.Button(buttons, text="Updates…", command=show_updates).pack(side="left", padx=(6, 0))
    ttk.Button(buttons, text="Refresh", command=refresh).pack(side="left", padx=(6, 0))
    notes.bind("<Double-1>", lambda _e: show_updates())

    # ── school places ────────────────────────────────────────────────
    tab2 = ttk.Frame(book, padding=6)
    book.add(tab2, text="School places")
    ttk.Label(tab2, foreground="#555", wraplength=840, justify="left", text=(
        "Places the local authority allocated at this school (an accepted offer, a fair "
        "access allocation or an upheld appeal). " + (
            "Each one is an accepted application on Admissions: enrol it there when the "
            "child starts." if school == "primary" else
            "Each one is listed under Incoming pupils: match or create the pupil there, "
            "then complete it when the child starts."))).pack(anchor="w", pady=(0, 6))
    places = _table(tab2, (("pupil", "Child", 190), ("round", "Round", 170),
                           ("basis", "Offer basis", 200), ("start", "Starts", 95),
                           ("status", "Status", 170), ("sent", "Allocated", 95)))
    ttk.Button(tab2, text="Refresh", command=refresh).pack(anchor="w", pady=(8, 0))

    ttk.Label(parent, textvariable=status, foreground="#555").pack(anchor="w", pady=(6, 0))
    refresh()


def _notify_dialog(parent: tk.Misc, school: str, pupils, referrer: str,
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
    win.title("Notify the local authority")
    win.transient(parent.winfo_toplevel())
    form = ttk.Frame(win, padding=14)
    form.pack(fill="both", expand=True)
    labels = [label for _id, label in options]
    pupil = ttk.Combobox(form, values=labels, width=46)
    kind = ttk.Combobox(form, values=service.KINDS, state="readonly", width=46)
    kind.set(service.KINDS[0])
    for n, (text, widget) in enumerate((("Pupil", pupil), ("Notification", kind))):
        ttk.Label(form, text=text).grid(row=n, column=0, sticky="nw", pady=4)
        widget.grid(row=n, column=1, sticky="w", padx=(8, 0), pady=4)
    fields = ttk.Frame(form)
    fields.grid(row=2, column=0, columnspan=2, sticky="we")
    inputs: dict[str, Callable[[], str]] = {}

    def build(_event=None) -> None:
        for child in fields.winfo_children():
            child.destroy()
        inputs.clear()
        for n, (key, text, how, choices) in enumerate(service.NOTICE_FIELDS[kind.get()]):
            ttk.Label(fields, text=text, wraplength=200).grid(row=n, column=0, sticky="nw",
                                                              pady=4)
            if how == "text":
                box = tk.Text(fields, width=48, height=4, wrap="word")
                inputs[key] = lambda b=box: b.get("1.0", "end").strip()
            elif how == "choice":
                box = ttk.Combobox(fields, values=choices, state="readonly", width=46)
                inputs[key] = box.get
            else:
                box = ttk.Entry(fields, width=48)
                if how == "date" and key in ("start_date", "notice_date"):
                    box.insert(0, date.today().isoformat())
                inputs[key] = box.get
            box.grid(row=n, column=1, sticky="w", padx=(8, 0), pady=4)

    kind.bind("<<ComboboxSelected>>", build)
    build()
    who = ttk.Entry(form, width=48)
    who.insert(0, referrer)
    sg = ttk.Entry(form, width=48)
    for n, (text, widget) in enumerate((("Sent by (name)", who),
                                        ("Safeguarding file reference", sg)), start=3):
        ttk.Label(form, text=text).grid(row=n, column=0, sticky="nw", pady=4)
        widget.grid(row=n, column=1, sticky="w", padx=(8, 0), pady=4)
    ttk.Label(form, foreground="#888", text="A reference only (e.g. the DSL's file number) - "
              "never the details.").grid(row=5, column=1, sticky="w", padx=(8, 0))
    consent = tk.BooleanVar(value=False)
    ttk.Checkbutton(form, variable=consent, text="The parent consents to sharing SEN, medical "
                    "and exclusion history").grid(row=6, column=0, columnspan=2, sticky="w",
                                                  pady=(6, 0))

    def submit() -> None:
        if pupil.get() not in labels:
            messagebox.showwarning(TITLE, "Choose the pupil from the list.", parent=win)
            return
        pid = options[labels.index(pupil.get())][0]
        details = {key: get() for key, get in inputs.items()}
        try:
            row = service.notify(school, str(pid), kind=kind.get(), details=details,
                                 referrer=who.get().strip(), consent=consent.get(),
                                 safeguarding_reference=sg.get().strip() or None,
                                 actor_user_id=actor_user_id)
        except Exception as exc:  # noqa: BLE001 - shown to the user
            messagebox.showerror("Not sent", str(exc), parent=win)
            return
        messagebox.showinfo("Sent", f"The local authority has the {kind.get().lower()}."
                            "\n\nStatus: " + service.NOTICE_LABELS.get(row["status"],
                                                                       row["status"]),
                            parent=win)
        win.destroy()
        on_done()

    ttk.Button(form, text="Send", command=submit).grid(row=7, column=1, sticky="e",
                                                       pady=(10, 0))


__all__ = ["TITLE", "render"]
